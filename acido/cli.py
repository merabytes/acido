import argparse
import json
import traceback
import subprocess
from acido.azure_utils.BlobManager import BlobManager
from acido.azure_utils.InstanceManager import *
from acido.azure_utils.ManagedIdentity import ManagedAuthentication
from msrestazure.azure_exceptions import CloudError
from acido.utils.functions import chunks, jpath, expanduser, split_file
from huepy import good, bad, info, bold, green, red, orange
from multiprocessing.pool import ThreadPool
import code
import re
import os
import sys
import time
from os import mkdir, getenv
from acido.utils.decoration import BANNER, __version__

__author__ = "Xavier Alvarez Delgado (xalvarez@merabytes.com)"
__coauthor__ = "Juan Ramón Higueras Pica (juanramon.higueras@wsg127.com)"

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config",
                    dest="config",
                    help="Start configuration of acido.",
                    action='store_true')
parser.add_argument("-f", "--fleet",
                    dest="fleet",
                    help="Create new fleet.",
                    action='store')
parser.add_argument("-im", "--image",
                    dest="image_name",
                    help="Deploy an specific image.",
                    action='store',
                    default='ubuntu:20.04')
parser.add_argument("-n", "--num-instances",
                    dest="num_instances",
                    help="Instances that the operation affect",
                    action='store')
parser.add_argument("-t", "--task",
                    dest="task",
                    help="Execute command as an entrypoint in the fleet.",
                    action='store')
parser.add_argument("-e", "--exec",
                    dest="exec_cmd",
                    help="Execute command on the selected instances.",
                    action='store')
parser.add_argument("-i", "--input-file",
                    dest="input_file",
                    help="The name of the file to use on the task.",
                    action='store')
parser.add_argument("-w", "--wait",
                    dest="wait",
                    help="Set max timeout for the instance to finish.",
                    action='store')
parser.add_argument("-s", "--select",
                    dest="select",
                    help="Select instances matching name/regex.",
                    action='store')
parser.add_argument("-l", "--list",
                    dest="list_instances",
                    help="List all instances.",
                    action='store_true')
parser.add_argument("-r", "--rm",
                    dest="remove",
                    help="Remove instances matching name/regex.",
                    action='store')
parser.add_argument("-in", "--interactive",
                    dest="interactive",
                    help="Start interactive acido session.",
                    action='store_true')
parser.add_argument("-sh", "--shell",
                    dest="shell",
                    help="Execute command and upload to blob.",
                    action='store')
parser.add_argument("-d", "--download",
                    dest="download_input",
                    help="Download file contents remotely from the acido blob.",
                    action='store')


args = parser.parse_args()

instances_inputs = {}
instances_outputs = {}

def build_output(result):
    global instances_outputs
    instances_outputs[result[0]] = [result[1], result[2]]

def exec_command(rg, cg, cont, command, max_retries, input_file):
    env = os.environ.copy()
    env["PATH"] = "/usr/sbin:/sbin:" + env["PATH"]
    # Kill tmux window
    subprocess.Popen(["tmux", "kill-session", "-t", cont], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    subprocess.Popen(["tmux", "new-session", "-d", "-s", cont], env=env)
    time.sleep(5)
    subprocess.Popen(["tmux", "send-keys", "-t", cont,
                    f"az container exec -g {rg} -n {cg} --container-name {cont} --exec-command /bin/bash", "Enter",
                    ], env=env)
    time.sleep(15)
    if input_file:
        subprocess.Popen(["tmux", "send-keys", "-t", cont, f"python3 -m acido.cli -d {input_file}", "Enter"], env=env)
        time.sleep(5)
    subprocess.Popen(["tmux", "send-keys", "-t", cont, f"nohup python3 -m acido.cli -sh '{command}' > temp &", "Enter"], env=env)
    time.sleep(2)
    subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)

    output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env).decode()

    time.sleep(4)

    retries = 0
    failed = False
    exception = None
    command_uuid = None

    while 'Done' not in output:

        retries += 1

        if retries > max_retries:
            exception = 'TIMEOUT REACHED'
            failed = True
            break

        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(1)
        output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env).decode()

        if 'Exit' in output:
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
            time.sleep(2)
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "cat temp", "Enter", "Enter"], env=env)
            time.sleep(2)
            subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
            time.sleep(2)
            try:
                exception = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env)
                exception = exception.decode()
                exception = exception.split('cat temp')[1].strip()
            except Exception as e:
                exception = 'ERROR PARSING'
                print(bad(f'Error capturing output from: {bold(cont)}'))
            failed = True
            break
        if 'Done' in output:
            failed = False
            break

    if not failed:
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(2)
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "cat temp", "Enter", "Enter"], env=env)
        time.sleep(10)
        subprocess.Popen(["tmux", "send-keys", "-t", cont, "Enter"], env=env)
        time.sleep(2)
        try:
            output = subprocess.check_output(["tmux", "capture-pane", "-pt", cont], env=env)
            output = output.decode()
            command_uuid = output.split('command: ')[1].split('\n')[0].strip()
        except Exception as e:
            command_uuid = None
            print(bad(f'Error capturing output from: {bold(cont)}'))
    else:
        print(bad(f'Exception ocurred while executing "{command}" from: {bold(cont)}'))

    # Kill shell
    subprocess.Popen(["tmux", "send-keys", "-t", cont, "(rm temp && exit)", "Enter"], env=env)
    time.sleep(1)
    # Kill tmux window
    subprocess.Popen(["tmux", "kill-session", "-t", cont], env=env)

    return cont, command_uuid, exception

def wait_command(rg, cg, cont, wait=None):
    time_spent = 0
    exception = None
    command_uuid = None
    container_logs = subprocess.check_output(
        f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
        shell=True
    )
    container_logs = container_logs.decode()

    while True:
        container_logs = subprocess.check_output(
        f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
        shell=True
        )
        container_logs = container_logs.decode()

        if wait and time_spent > wait:
            exception = 'TIMEOUT REACHED'
            break
        if 'command: ' in container_logs:
            command_uuid = container_logs.split('command: ')[1].strip()
            break
        if 'Exception' in container_logs:
            exception = container_logs
            break
        time.sleep(1)
        time_spent += 1

    return cont, command_uuid, exception


class Acido(object):

    if args.interactive:
        print(red(BANNER))

    def __init__(self, rg: str = None, login: bool = True):

        self.selected_instances = []
        self.image_registry_server = None
        self.image_registry_username = None
        self.image_registry_password = None
        self.user_assigned = None
        self.rg = None

        if rg:
            self.rg = rg

        self.io_blob = None

        try:
            self.rows, self.cols = os.popen('stty size', 'r').read().split()
        except:
            self.rows, self.cols = 55, 160
        
        try:
            self._load_config()
        except FileNotFoundError:
            self.setup()
        

        try:
            az_identity_list = subprocess.check_output(f'az identity create --resource-group {self.rg} --name acido', shell=True)
            az_identity_list = json.loads(az_identity_list)
            self.user_assigned = az_identity_list
        except Exception as e:
            self.user_assigned = None

        im = InstanceManager(self.rg, login, self.user_assigned)
        im.login_image_registry(
            self.image_registry_server, 
            self.image_registry_username, 
            self.image_registry_password
        )
        self.instance_manager = im
        self.blob_manager = BlobManager(resource_group=self.rg, account_name='acido')
        self.blob_manager.use_container(container_name='acido', create_if_not_exists=True)
        self.all_instances, self.instances_named = self.ls(interactive=False)

    def _save_config(self):
        home = expanduser("~")
        config = {
            'rg': self.rg,
            'selected_instances' : self.selected_instances,
            'image_registry_username': self.image_registry_username,
            'image_registry_password': self.image_registry_password,
            'image_registry_server': self.image_registry_server,
            'user_assigned_id': self.user_assigned
        }

        try:
            mkdir(jpath(f'{home}', '.acido'))
        except:
            pass

        try:
            mkdir(jpath(f'{home}', '.acido', 'logs'))
        except:
            pass

        with open(jpath(f'{home}', '.acido', 'config.json'), 'w') as conf:
            conf.write(json.dumps(config, indent=4))
            conf.close()

        return True
        

    def _load_config(self):
        home = expanduser("~")
        with open(jpath(f'{home}', '.acido', 'config.json'), 'r') as conf:
            config = json.loads(conf.read())
        
        for key, value in config.items():
            if key == 'rg' and self.rg:
                continue
            setattr(self, key, value)

        self._save_config()


    def ls(self, interactive=True):
        all_instances = {}
        all_instances_names = {}
        all_instances_states = {}
        all_names = []
        instances = self.instance_manager.ls()
        while instances:
            try:
                container_group = instances.next()
                all_instances[container_group.name] = [c for c in container_group.containers]
                all_instances_names[container_group.name] = [c.name for c in container_group.containers]
                all_instances_states[container_group.name] = green(container_group.provisioning_state) if container_group.provisioning_state == 'Succeeded' else orange(container_group.provisioning_state)
                all_names += [c.name for c in container_group.containers]
            except StopIteration:
                break
        if interactive:
            print(good(f"Listing all instances: [ {bold(' '.join(all_names))} ]"))
            print(good(f"Container group status: [ {' '.join([f'{bold(cg)}: {status}' for cg, status in all_instances_states.items()])} ]"))
        return None if interactive else all_instances, all_instances_names
    
    def select(self, selection, interactive=True):
        self.all_instances, self.instances_named = self.ls(interactive=False)
        selection = f'^{selection.replace("*", "(.*)")}$'
        self.selected_instances = [scg for scg, i in self.instances_named.items() if bool(re.match(selection, scg))]
        self._save_config()
        print(good(f"Selected all instances of group/s: [ {bold(' '.join(self.selected_instances))} ]"))
        return None if interactive else self.selected_instances

    def fleet(self, fleet_name, instance_num=3, image_name=None, scan_cmd=None, input_file=None, wait=None, interactive=True):
        response = {}
        input_files = None
        if instance_num > 10:
            instance_num_groups = list(chunks(range(1, instance_num + 1), 10))
            
            if input_file:
                input_filenames = split_file(input_file, instance_num)
                input_files = [self.save_input(f) for f in input_filenames]

            for cg_n, ins_num in enumerate(instance_num_groups):
                last_instance = len(ins_num)
                env_vars = {
                    'RG': self.rg,
                    'IMAGE_REGISTRY_SERVER': self.image_registry_server,
                    'IMAGE_REGISTRY_USERNAME': self.image_registry_username,
                    'IMAGE_REGISTRY_PASSWORD': self.image_registry_password,
                    'BLOB_CONNECTION': (
                        "DefaultEndpointsProtocol=https;"
                        f"AccountName={self.blob_manager.account_name};AccountKey={self.blob_manager.account_key};"
                        "EndpointSuffix=core.windows.net"
                    )
                }
                group_name = f'{fleet_name}-{cg_n+1:02d}'

                if group_name not in response.keys():
                    response[group_name] = []
                
                response[group_name], input_files = self.instance_manager.deploy(
                            name=group_name, 
                            instance_number=last_instance, 
                            image_name=image_name,
                            input_files=input_files,
                            command=scan_cmd,
                            env_vars=env_vars)
        else:

            if input_file:
                input_filenames = split_file(input_file, instance_num)
                input_files = [self.save_input(f) for f in input_filenames]

            env_vars = {
                    'RG': self.rg,
                    'IMAGE_REGISTRY_SERVER': self.image_registry_server,
                    'IMAGE_REGISTRY_USERNAME': self.image_registry_username,
                    'IMAGE_REGISTRY_PASSWORD': self.image_registry_password,
                    'BLOB_CONNECTION': (
                        "DefaultEndpointsProtocol=https;"
                        f"AccountName={self.blob_manager.account_name};AccountKey={self.blob_manager.account_key};"
                        "EndpointSuffix=core.windows.net"
                    )
            }

            response[fleet_name], input_files = self.instance_manager.deploy(
                name=fleet_name, 
                instance_number=instance_num, 
                image_name=image_name,
                command=scan_cmd,
                env_vars=env_vars,
                input_files=input_files)
        
        os.system('rm -f /tmp/acido-input*')

        all_names = []
        all_groups = []
        results = []
        outputs = {}

        for cg, containers in response.items():
            all_groups.append(cg)
            all_names += list(containers.keys())

        print(good(f"Successfully created new group/s: [ {bold(' '.join(all_groups))} ]"))
        print(good(f"Successfully created new instance/s: [ {bold(' '.join(all_names))} ]"))

        if scan_cmd:
            print(good('Waiting 2 minutes until the machines get provisioned...'))
            time.sleep(120)
            print(good('Waiting for outputs...'))

            for cg, containers in response.items():
                for cont in list(containers.keys()):
                    result = pool.apply_async(wait_command, 
                                                (self.rg, cg, cont, wait), 
                                                callback=build_output)
                    results.append(result)

            results = [result.wait() for result in results]

            for c, o in instances_outputs.items():
                command_uuid, exception = o
                if command_uuid:
                    output = self.load_input(command_uuid)
                    print(good(f'Executed command on {bold(c)}. Output: [\n{output.decode().strip()}\n]'))
                    outputs[c] = output.decode()
                elif exception:
                    print(bad(f'Executed command on {bold(c)} Output: [\n{exception}\n]'))

        return None if interactive else response, outputs
    

    def rm(self, selection):
        self.all_instances, self.instances_named = self.ls(interactive=False)
        response = {}
        selection = f'^{selection.replace("*", "(.*)")}$'
        removable_instances = [cg for cg, i in self.instances_named.items() if bool(re.match(selection, cg))]

        for erased_group in removable_instances:
            response[erased_group] = self.instance_manager.rm(erased_group)

        for group, status in response.items():
            if status:
                print(good(f'Successfully erased {group} and all its instances.'))
            else:
                print(bad(f'Error while erasing {group} and its instances. Maybe its already deleted?'))
        return

    def save_output(self, command: list = None):
        try:
            output = subprocess.check_output(command.split(' '))
            file, filename = self.blob_manager.upload(
                output
            )
            if file:
                print(good(f'Executed command: {filename}'))
        except subprocess.CalledProcessError as e:
            print(good(f'Exception occurred.'))
        return output

    def save_input(self, filename: str = None):
        file_contents = open(filename, 'rb').read()
        file, filename = self.blob_manager.upload(
            file_contents
        )
        if file:
            print(good(f'Uploaded input: {filename}'))
        return filename
    
    def load_input(self, command_uuid: str = None, filename: str = 'input', write_to_file: bool = False):
        if command_uuid:
            input_file = self.blob_manager.download(command_uuid)
            if write_to_file:
                open(filename, 'wb').write(input_file)
                print(good(f'File loaded successfully.'))
        return input_file

    def exec(self, command, max_retries=60, input_file: str = None):
        global instances_outputs
        self.all_instances, self.instances_named = self.ls(interactive=False)
        results = []
        executed = False
        if not self.selected_instances:
            print(bad('You didn\'t select any containers to execute the command.'))
            return

        if input_file:
            number_of_containers = 0
            for cg, containers in self.instances_named.items():
                if cg in self.selected_instances:
                    for cont in containers:
                        number_of_containers += 1

            input_files = split_file(input_file, number_of_containers)
            input_file_index = 0
            
            for cg, containers in self.instances_named.items():
                if cg in self.selected_instances:
                    for cont in containers:
                        executed = True
                        result = pool.apply_async(exec_command, 
                                                (self.rg, cg, cont, command, max_retries, input_files[input_file_index]), 
                                                callback=build_output)
                        results.append(result)
                        input_file_index += 1
        else:
            for cg, containers in self.instances_named.items():
                if cg in self.selected_instances:
                    for cont in containers:
                        executed = True
                        result = pool.apply_async(exec_command, 
                                                (self.rg, cg, cont, command, max_retries, input_file), 
                                                callback=build_output)
                        results.append(result)
        
        if not executed:
            print(bad('An error happened. You probably didn\'t select any containers to execute the command.'))
            return
        
        results = [result.wait() for result in results]
        outputs = {}

        for c, o in instances_outputs.items():
            command_uuid, exception = o
            if command_uuid:
                output = self.load_input(command_uuid)
                print(good(f'Executed command on {bold(c)}. Output: [\n{output.decode().strip()}\n]'))
                outputs[c] = output.decode()
            elif exception:
                if max_retries == 0:
                    print(good(f'Executed command on {bold(c)}'))
                else:
                    print(bad(f'Executed command on {bold(c)} Output: [\n{exception}\n]'))

        instances_outputs = {}

        return outputs

    def setup(self):
        rg = os.getenv('RG') if os.getenv('RG', None) else input(info('Please provide a Resource Group Name to deploy the ACIs: '))
        self.rg = rg
        image_registry_server = os.getenv('IMAGE_REGISTRY_SERVER') if os.getenv('RG', None) else input(info('Image Registry Server: '))
        image_registry_username = os.getenv('IMAGE_REGISTRY_USERNAME') if os.getenv('IMAGE_REGISTRY_USERNAME', None) else input(info('Image Registry Username: '))
        image_registry_password = os.getenv('IMAGE_REGISTRY_PASSWORD') if os.getenv('IMAGE_REGISTRY_PASSWORD', None) else input(info('Image Registry Password: '))
        self.selected_instances = []
        self.image_registry_server = image_registry_server
        self.image_registry_username = image_registry_username
        self.image_registry_password = image_registry_password
        self._save_config()

if __name__ == "__main__":
    acido = Acido()
    if args.config:
        acido.setup()
    if args.list_instances:
        acido.ls(interactive=True)
    if args.shell:
        acido.save_output(args.shell)
    if args.download_input:
        acido.load_input(args.download_input, write_to_file=True)
    if args.fleet:
        pool = ThreadPool(processes=30)
        acido.fleet(
            fleet_name=args.fleet, 
            instance_num=int(args.num_instances) if args.num_instances else 1, 
            image_name=args.image_name, 
            scan_cmd=args.task, 
            input_file=args.input_file, 
            wait=int(args.wait) if args.wait else None, 
            interactive=bool(args.interactive)
        )
    if args.select:
        acido.select(selection=args.select, interactive=bool(args.interactive))
    if args.exec_cmd:
        pool = ThreadPool(processes=30)
        acido.exec(command=args.exec_cmd, max_retries=int(args.wait) if args.wait else 60, input_file=args.input_file)
    if args.remove:
        acido.rm(args.remove)
    if args.interactive:
        code.interact(banner=f'acido {__version__}', local=locals())