import argparse
from asyncore import write
import json
import traceback
import subprocess
from beaupy import select
from azure.mgmt.network.models import ContainerNetworkInterfaceConfiguration, ContainerNetworkInterfaceIpConfiguration, IPConfigurationProfile
from azure.mgmt.containerinstance.models import ContainerGroupNetworkProfile
from acido.azure_utils.BlobManager import BlobManager
from acido.azure_utils.InstanceManager import *
from acido.azure_utils.NetworkManager import *
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
from acido.utils.shell_utils import wait_command, exec_command

__author__ = "Xavier Alvarez Delgado (xalvarez@merabytes.com)"
__coauthor__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"

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
parser.add_argument("--create-ip",
                    dest="create_ip",
                    help="Create a new IPv4 address.",
                    action='store',
                    default='')
parser.add_argument("--ip",
                    dest="ipv4_address",
                    help="Route containers through an specific IPv4 address.",
                    action='store_true',
                    default=False)
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
parser.add_argument("-o", "--output",
                    dest="write_to_file",
                    help="Save the output of the machines in JSON format.",
                    action='store')
parser.add_argument("-rwd", "--rm-when-done",
                    dest="rm_when_done",
                    help="Remove the container groups after finish.",
                    action='store_true')


args = parser.parse_args()
instances_outputs = {}

def build_output(result):
    global instances_outputs
    instances_outputs[result[0]] = [result[1], result[2]]


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
        self.network_profile = None

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
            print(bad('Error while trying to get/create user assigned identity.'))
            self.user_assigned = None

        im = InstanceManager(self.rg, login, self.user_assigned, self.network_profile)
        im.login_image_registry(
            self.image_registry_server, 
            self.image_registry_username, 
            self.image_registry_password
        )
        self.instance_manager = im
        self.blob_manager = BlobManager(resource_group=self.rg, account_name='acido')
        self.blob_manager.use_container(container_name='acido', create_if_not_exists=True)
        self.all_instances, self.instances_named = self.ls(interactive=False)

        self.network_manager = NetworkManager(resource_group=self.rg)

        if args.create_ip:
            public_ip_name = args.create_ip
            self.create_ipv4_address(public_ip_name)
            self.select_ipv4_address()

        if args.ipv4_address:
            self.select_ipv4_address()
        
        self.instance_manager.network_profile = self.network_profile


    def _save_config(self):
        home = expanduser("~")
        config = {
            'rg': self.rg,
            'selected_instances' : self.selected_instances,
            'image_registry_username': self.image_registry_username,
            'image_registry_password': self.image_registry_password,
            'image_registry_server': self.image_registry_server,
            'user_assigned_id': self.user_assigned,
            'network_profile': self.network_profile
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
            if key == 'rg' and self.rg is not None:
                continue
            else:
                setattr(self, key, value)

        self._save_config()

    def create_ipv4_address(self, public_ip_name):
        if self.network_manager is None:
            print(bad("Network manager is not initialized. Please provide a resource group."))
            return
        
        # Step 0: Delete NetworkProfile
        # self.network_manager.delete_resources(public_ip_name)

        # Step 1: Create a new Public IP Address
        ipv4_address_id = self.network_manager.create_ipv4(public_ip_name)

        # Step 2: Create a Virtual Network
        vnet_name = f'{public_ip_name}-vnet'
        subnet_name = f'{public_ip_name}-subnet'
        vnet_params = self.network_manager.create_virtual_network(vnet_name)
        subnet_params = self.network_manager.create_subnet(vnet_name, subnet_name, ip_address=ipv4_address_id)

        # Step 3: Create a Network Profile
        network_profile_name = f'{public_ip_name}-network-profile'
        container_network_interface_config = ContainerNetworkInterfaceConfiguration(
            name=f'{public_ip_name}-cnic',
            ip_configurations=[
                IPConfigurationProfile(
                    name=f'{public_ip_name}-ip-config',
                    subnet=subnet_params
                )
            ]
        )
        network_profile_params = NetworkProfile(
            location='westeurope',  # replace 'your-location' with your actual Azure location
            container_network_interface_configurations=[container_network_interface_config]
        )
        network_profile = self.network_manager.create_network_profile(
            network_profile_name, network_profile_params)
        
        self.network_profile = {'id': network_profile.id}

        self._save_config()

        print(good(f"Network Profile {network_profile_name} created successfully."))


    def select_ipv4_address(self):
        if self.network_manager is None:
            print(bad("Network manager is not initialized. Please provide a resource group."))
            return
        
        ip_addresses_info = self.network_manager.list_ipv4()
        
        # Create a list of IP addresses and an associated descriptive list
        ip_addresses = [info['ip_address'] for info in ip_addresses_info if info['ip_address']]  # Filter out None values
        ip_descriptions = [f"{info['name']} ({info['ip_address']})" for info in ip_addresses_info if info['ip_address']]  # Filter out None values
        
        # Now use beaupy to create an interactive selector.
        print(good("Please select an IP address:"))
        selected_description = select(ip_descriptions, cursor_style="cyan")
        
        # Extract the selected IP address from the description
        selected_ip_address = selected_description.split(' ')[-1][1:-1]  # Assumes the format is 'name (ip_address)'
        network_profile_prefix = selected_description.split(' ')[0]  # Assumes the format is 'name (ip_address)'
        self.network_profile = {'id': self.network_manager.get_network_profile(resource_name=network_profile_prefix).id}
        self._save_config()
        
        print(good(f"You selected IP address: {selected_ip_address} from network profile {self.network_profile}"))

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

    def fleet(self, fleet_name, instance_num=3, image_name=None, scan_cmd=None, input_file=None, wait=None, write_to_file=None, interactive=True):
        response = {}
        input_files = None
        if instance_num > 10:
            instance_num_groups = list(chunks(range(1, instance_num + 1), 10))
            
            if input_file:
                input_filenames = split_file(input_file, instance_num)
                input_files = [self.save_input(f) for f in input_filenames]
                print(good(f'Uploaded {len(input_files)} target lists.'))

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
                            network_profile=self.network_profile,
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
                network_profile=self.network_profile,
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
            print(good('Waiting 4 minutes until the machines get provisioned...'))
            time.sleep(240)
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
            
            if write_to_file:
                open(write_to_file, 'w').write(json.dumps(outputs, indent=4))
                print(good(f'Saved container outputs at: {write_to_file}.json'))
                open(f'all_{write_to_file}.txt', 'w').write('\n'.join([o.rstrip() for o in outputs.values()]))
                print(good(f'Saved merged outputs at: all_{write_to_file}.txt'))

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
        output = None
        try:
            output = subprocess.check_output(command.split(' '))
            file, filename = self.blob_manager.upload(
                output
            )
            if file:
                print(good(f'Executed command: {filename}'))
        except subprocess.CalledProcessError as e:
            print(bad(f'Exception occurred.'))
        return output

    def save_input(self, filename: str = None):
        file_contents = open(filename, 'rb').read()
        file, filename = self.blob_manager.upload(
            file_contents
        )
        if file:
            return filename
        else:
            print(bad(f'Exception occurred while uploading file.'))
            return None
    
    def load_input(self, command_uuid: str = None, filename: str = 'input', write_to_file: bool = False):
        if command_uuid:
            input_file = self.blob_manager.download(command_uuid)
            if write_to_file:
                open(filename, 'wb').write(input_file)
                print(good(f'File loaded successfully.'))
        return input_file

    def exec(self, command, max_retries=60, input_file: str = None, write_to_file: str =None):
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
        
        if write_to_file:
            open(f'{write_to_file}.json', 'w').write(json.dumps(outputs, indent=4))
            print(good(f'Saved JSON output at: {write_to_file}'))
            open(f'all_{write_to_file}', 'w').write('\n'.join([o.rstrip() for o in outputs.values()]))
            print(good(f'Saved merged outputs at: {write_to_file}'))


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
        args.num_instances = int(args.num_instances) if args.num_instances else 1
        acido.fleet(
            fleet_name=args.fleet, 
            instance_num=int(args.num_instances) if args.num_instances else 1, 
            image_name=args.image_name, 
            scan_cmd=args.task, 
            input_file=args.input_file, 
            wait=int(args.wait) if args.wait else None, 
            write_to_file=args.write_to_file,
            interactive=bool(args.interactive)
        )
        if args.rm_when_done:
            acido.rm(args.fleet if args.num_instances <= 10 else f'{args.fleet}*')
    if args.select:
        acido.select(selection=args.select, interactive=bool(args.interactive))
    if args.exec_cmd:
        pool = ThreadPool(processes=30)
        acido.exec(
            command=args.exec_cmd, 
            max_retries=int(args.wait) if args.wait else 60, 
            input_file=args.input_file,
            write_to_file=args.write_to_file
        )
    if args.remove:
        acido.rm(args.remove)
    if args.interactive:
        code.interact(banner=f'acido {__version__}', local=locals())