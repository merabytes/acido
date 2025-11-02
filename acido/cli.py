import argparse
import json
import subprocess
import getpass
import sys
import tempfile
from beaupy import select
from azure.mgmt.network.models import ContainerNetworkInterfaceConfiguration, IPConfigurationProfile
from azure.mgmt.storage import StorageManagementClient
from acido.azure_utils.ManagedIdentity import ManagedAuthentication
from acido.azure_utils.BlobManager import BlobManager
from acido.azure_utils.InstanceManager import InstanceManager
from acido.azure_utils.NetworkManager import NetworkManager, NetworkProfile
from acido.utils.functions import chunks, jpath, expanduser, split_file
from acido.utils.lambda_safe_pool import ThreadPoolShim
from huepy import good, bad, info, bold, green, red, orange
import code
import re
import os
import time
from os import mkdir
from acido.utils.decoration import BANNER, __version__
from acido.utils.shell_utils import wait_command, exec_command
from tqdm import tqdm

__author__ = "Xavier Alvarez Delgado (xalvarez@merabytes.com)"
__coauthor__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"

# Constants
ACIDO_CREATE_STEPS = 5  # Number of steps in create_acido_image process

parser = argparse.ArgumentParser()

# Add subparsers for 'create' subcommand
subparsers = parser.add_subparsers(dest='subcommand', help='Subcommands')

# Create subcommand
create_parser = subparsers.add_parser('create', help='Create acido-compatible image from base image')
create_parser.add_argument('base_image', help='Base image name (e.g., "nuclei", "ubuntu:20.04")')
create_parser.add_argument('--image', dest='base_image_url', help='Full Docker image URL to use as base (e.g., "projectdiscovery/nuclei:latest")')

# Configure subcommand (alias for -c/--config)
configure_parser = subparsers.add_parser('configure', help='Configure acido (alias for -c/--config)')

# Regular arguments
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
                    help="Image name (e.g., 'nmap', 'nuclei', 'nuclei:latest') or full URL. Short names will be converted to registry/name-acido:tag format.",
                    action='store',
                    default='ubuntu')
parser.add_argument("--tag",
                    dest="image_tag",
                    help="Image tag (default: latest). Used when --image is a short name.",
                    action='store',
                    default='latest')
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
                    help="Save the output to a file. If not specified, outputs to STDOUT.",
                    action='store')
parser.add_argument("--format",
                    dest="output_format",
                    help="Output format: 'txt' (merged text) or 'json' (JSON with per-container outputs). Default: txt",
                    action='store',
                    choices=['txt', 'json'],
                    default='txt')
parser.add_argument("-q", "--quiet",
                    dest="quiet",
                    help="Suppress verbose output and show progress bar during fleet execution.",
                    action='store_true',
                    default=False)
parser.add_argument("-rwd", "--rm-when-done",
                    dest="rm_when_done",
                    help="Remove the container groups after finish.",
                    action='store_true')
parser.add_argument("--create",
                    dest="create_image",
                    help="Create acido-compatible image from base image (e.g., 'nuclei', 'ubuntu:20.04')",
                    action='store')


args = parser.parse_args()

# Handle 'create' subcommand - map it to create_image for consistency
if args.subcommand == 'create':
    # Use --image value if provided, otherwise use base_image positional arg
    args.create_image = args.base_image_url if hasattr(args, 'base_image_url') and args.base_image_url else args.base_image

# Handle 'configure' subcommand - map it to config flag for consistency
if args.subcommand == 'configure':
    args.config = True

instances_outputs = {}

def build_output(result):
    global instances_outputs
    instances_outputs[result[0]] = [result[1], result[2]]


class Acido(object):

    if args.interactive:
        print(red(BANNER))

    def __init__(self, rg: str = None, login: bool = True, check_config: bool = True):

        self.selected_instances = []
        self.image_registry_server = None
        self.image_registry_username = None
        self.image_registry_password = None
        self.docker_username = None
        self.docker_password = None
        self.storage_account = None
        self.user_assigned = {}
        self.rg = None
        self.network_profile = None

        if rg:
            self.rg = rg

        self.io_blob = None

        # If explicitly running config, just run it
        if args.config:
            self.setup()
            return
        
        # Check if environment variables are set for auto-configuration
        env_config_available = all([
            os.getenv('AZURE_RESOURCE_GROUP'),
            os.getenv('IMAGE_REGISTRY_SERVER'),
            os.getenv('IMAGE_REGISTRY_USERNAME'),
            os.getenv('IMAGE_REGISTRY_PASSWORD'),
            os.getenv('STORAGE_ACCOUNT_NAME')
        ])
        
        # Try to load config
        config_exists = False
        try:
            self._load_config()
            config_exists = True
        except FileNotFoundError:
            # No config file exists
            if env_config_available:
                # Auto-configure from environment variables
                self.rg = os.getenv('AZURE_RESOURCE_GROUP')
                self.image_registry_server = os.getenv('IMAGE_REGISTRY_SERVER')
                self.image_registry_username = os.getenv('IMAGE_REGISTRY_USERNAME')
                self.image_registry_password = os.getenv('IMAGE_REGISTRY_PASSWORD')
                self.storage_account = os.getenv('STORAGE_ACCOUNT_NAME')
                self.selected_instances = []
                config_exists = True
                info('Auto-configured from environment variables.')
            elif check_config:
                # If user is trying to run a command that requires config, prompt them
                print(bad('No configuration found.'))
                print(info('Please run "acido -c" to configure acido first, or use "acido -h" for help.'))
                sys.exit(1)
            else:
                # Only for -h or similar cases where config is not needed
                return
        
        # Load Docker Hub credentials from environment (if available)
        # These are used for pulling base images from Docker Hub
        self.docker_username = os.getenv('DOCKER_USERNAME')
        self.docker_password = os.getenv('DOCKER_PASSWORD')
        
        # Load managed identity from environment variables if provided
        managed_identity_id = os.getenv('MANAGED_IDENTITY_ID')
        managed_identity_client_id = os.getenv('MANAGED_IDENTITY_CLIENT_ID')
        if managed_identity_id and managed_identity_client_id:
            self.user_assigned = {
                'id': managed_identity_id,
                'clientId': managed_identity_client_id
            }
        # Only try to create identity via Azure CLI if managed identity env vars are not already set
        elif not managed_identity_client_id and not os.getenv('INSTANCE_NAME', None):
            try:
                az_identity_list = subprocess.check_output(f'az identity create --resource-group {self.rg} --name acido', shell=True)
                az_identity_list = json.loads(az_identity_list)
                self.user_assigned = az_identity_list
            except Exception as e:
                print(bad('Error while trying to get/create user assigned identity.'))
                print(info('Continuing without user-assigned identity. Some features may not work.'))


        im = InstanceManager(self.rg, login, self.user_assigned, self.network_profile)
        im.login_image_registry(
            self.image_registry_server, 
            self.image_registry_username, 
            self.image_registry_password
        )
        self.instance_manager = im
        self.blob_manager = BlobManager(resource_group=self.rg, account_name=self.storage_account)
        info(f'Using storage account "{self.storage_account}" and storage container "acido"...')
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
            'storage_account': self.storage_account,
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

    def fleet(self, fleet_name, instance_num=3, image_name=None, scan_cmd=None, input_file=None, wait=None, write_to_file=None, output_format='txt', interactive=True, quiet=False):
        response = {}
        input_files = None
        
        # Helper function to print only if not quiet
        def print_if_not_quiet(msg):
            if not quiet:
                print(msg)
        
        if instance_num > 10:
            instance_num_groups = list(chunks(range(1, instance_num + 1), 10))
            
            if input_file:
                input_filenames = split_file(input_file, instance_num)
                input_files = [self.save_input(f) for f in input_filenames]
                print_if_not_quiet(good(f'Uploaded {len(input_files)} target lists.'))

            for cg_n, ins_num in enumerate(instance_num_groups):
                last_instance = len(ins_num)
                env_vars = {
                    'AZURE_RESOURCE_GROUP': self.rg,
                    'IMAGE_REGISTRY_SERVER': self.image_registry_server,
                    'IMAGE_REGISTRY_USERNAME': self.image_registry_username,
                    'IMAGE_REGISTRY_PASSWORD': self.image_registry_password,
                    'STORAGE_ACCOUNT_NAME': self.storage_account,
                    'STORAGE_ACCOUNT_KEY': self.blob_manager.account_key,
                    'MANAGED_IDENTITY_ID': self.user_assigned.get('id', None),
                    'MANAGED_IDENTITY_CLIENT_ID': self.user_assigned.get('clientId', None),
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
                            env_vars=env_vars,
                            quiet=quiet)
        else:

            if input_file:
                input_filenames = split_file(input_file, instance_num)
                input_files = [self.save_input(f) for f in input_filenames]

            env_vars = {
                    'AZURE_RESOURCE_GROUP': self.rg,
                    'IMAGE_REGISTRY_SERVER': self.image_registry_server,
                    'IMAGE_REGISTRY_USERNAME': self.image_registry_username,
                    'IMAGE_REGISTRY_PASSWORD': self.image_registry_password,
                    'STORAGE_ACCOUNT_NAME': self.storage_account,
                    'STORAGE_ACCOUNT_KEY': self.blob_manager.account_key,
                    'MANAGED_IDENTITY_ID': self.user_assigned.get('id', None),
                    'MANAGED_IDENTITY_CLIENT_ID': self.user_assigned.get('clientId', None),
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
                input_files=input_files,
                quiet=quiet)
        
        os.system('rm -f /tmp/acido-input*')

        all_names = []
        all_groups = []
        results = []
        outputs = {}

        for cg, containers in response.items():
            all_groups.append(cg)
            all_names += list(containers.keys())

        print_if_not_quiet(good(f"Successfully created new group/s: [ {bold(' '.join(all_groups))} ]"))
        print_if_not_quiet(good(f"Successfully created new instance/s: [ {bold(' '.join(all_names))} ]"))

        if scan_cmd:
            if quiet:
                # Use progress bar when quiet mode
                pbar = tqdm(total=3, desc="Fleet execution", unit="step")
                pbar.set_description("Provisioning containers")
                time.sleep(60)
                pbar.update(1)
                
                pbar.set_description("Executing commands")
            else:
                print(good('Waiting 1 minute until the container/s group/s gets provisioned...'))
                time.sleep(60)
                print(good('Waiting for outputs...'))

            for cg, containers in response.items():
                for cont in list(containers.keys()):
                    result = pool.apply_async(wait_command, 
                                                (self.rg, cg, cont, wait), 
                                                callback=build_output)
                    results.append(result)

            results = [result.wait() for result in results]
            
            if quiet:
                pbar.update(1)
                pbar.set_description("Collecting outputs")

            for c, o in instances_outputs.items():
                command_uuid, exception = o
                if command_uuid:
                    output = self.load_input(command_uuid)
                    if not quiet:
                        print(good(f'Executed command on {bold(c)}. Output: [\n{output.decode().strip()}\n]'))
                    outputs[c] = output.decode()
                elif exception:
                    if not quiet:
                        print(bad(f'Executed command on {bold(c)} Output: [\n{exception}\n]'))
            
            if quiet:
                pbar.update(1)
                pbar.close()
            
            # Handle output
            if write_to_file:
                # Save to file
                if output_format == 'json':
                    with open(write_to_file, 'w') as f:
                        f.write(json.dumps(outputs, indent=4))
                    print_if_not_quiet(good(f'Saved container outputs at: {write_to_file}'))
                else:  # txt format
                    with open(write_to_file, 'w') as f:
                        f.write('\n'.join([o.rstrip() for o in outputs.values()]))
                    print_if_not_quiet(good(f'Saved merged outputs at: {write_to_file}'))
            else:
                # Output to STDOUT
                if output_format == 'json':
                    print(json.dumps(outputs, indent=4))
                else:  # txt format
                    print('\n'.join([o.rstrip() for o in outputs.values()]))

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
        rg = os.getenv('AZURE_RESOURCE_GROUP') if os.getenv('AZURE_RESOURCE_GROUP', None) else input(info('Please provide a Resource Group Name to deploy the ACIs: '))
        self.rg = rg
        image_registry_server = os.getenv('IMAGE_REGISTRY_SERVER') if os.getenv('IMAGE_REGISTRY_SERVER', None) else input(info('Image Registry Server: '))
        image_registry_username = os.getenv('IMAGE_REGISTRY_USERNAME') if os.getenv('IMAGE_REGISTRY_USERNAME', None) else input(info('Image Registry Username: '))
        image_registry_password = os.getenv('IMAGE_REGISTRY_PASSWORD') if os.getenv('IMAGE_REGISTRY_PASSWORD', None) else getpass.getpass(info('Image Registry Password: '))
        storage_account = os.getenv('STORAGE_ACCOUNT_NAME') if os.getenv('STORAGE_ACCOUNT_NAME', None) else input(info('Storage Account Name to Use: '))
        
        if not os.getenv('STORAGE_ACCOUNT_NAME', None):
            auth = ManagedAuthentication()
            credential = auth.get_credential()
            subscription = auth.extract_subscription(credential)
            client = StorageManagementClient(
                credential,
                subscription
            )
            availability_result = client.storage_accounts.check_name_availability(
                    { "name": storage_account }
                )
            while not availability_result:
                bad(f'Storage account name "{storage_account}" is not available. Please select another one.')
                storage_account = input(info('Storage Account Name to Use: '))
                availability_result = client.storage_accounts.check_name_availability(
                    { "name": storage_account }
                )
            info(f'Creating storage account "{storage_account}"...')
            poller = client.storage_accounts.begin_create(self.rg, storage_account,
                parameters={
                        "location" : "westeurope",
                        "kind": "StorageV2",
                        "sku": {"name": "Standard_LRS"}
                    }
                )
            poller.result()
            good('Storage account created.')
        
        self.selected_instances = []
        self.image_registry_server = image_registry_server
        self.image_registry_username = image_registry_username
        self.image_registry_password = image_registry_password
        self.storage_account = storage_account
        self._save_config()

    def build_image_url(self, image_name: str, tag: str = 'latest') -> str:
        """
        Build full image URL from short name or return the full URL if already provided.
        
        For fleet operations: Converts short names to registry/name-acido:tag format.
        Examples:
            'nuclei' -> 'registry.azurecr.io/nuclei-acido:latest'
            'nuclei:v2' -> 'registry.azurecr.io/nuclei-acido:v2'
            'registry.azurecr.io/nuclei-acido:latest' -> 'registry.azurecr.io/nuclei-acido:latest' (unchanged)
        
        Args:
            image_name: Short image name (e.g., 'nmap', 'nuclei:v2') or full URL
            tag: Image tag (default: 'latest'), used only for short names without tags
        
        Returns:
            Full image URL with registry server and tag
        """
        # Check if it's already a full URL with registry (contains a dot in the first part before /)
        if '/' in image_name:
            first_part = image_name.split('/')[0]
            if '.' in first_part or '://' in image_name:
                # It's already a full URL with registry
                return image_name
        
        # Extract image name and tag if present
        if ':' in image_name:
            base_name, image_tag = image_name.rsplit(':', 1)
        else:
            base_name = image_name
            image_tag = tag
        
        # Build full URL with -acido suffix
        return f"{self.image_registry_server}/{base_name}-acido:{image_tag}"

    def _validate_image_name(self, image_name: str) -> bool:
        """
        Validate Docker image name using allowlist approach to prevent command injection.
        
        Valid Docker image names can only contain:
        - Letters (a-z, A-Z)
        - Digits (0-9)
        - Dots (.)
        - Hyphens (-)
        - Underscores (_)
        - Colons (:) for tags/ports
        - Slashes (/) for namespaces/registries
        - At signs (@) for digests
        
        Any other character will cause validation to fail.
        
        Returns:
            bool: True if valid, False otherwise
        """
        # Allowlist approach: only allow specific characters used in Docker image names
        # This is more secure than blacklisting dangerous characters
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_:/@')
        
        # Check if all characters in the image name are in the allowlist
        if not all(char in allowed_chars for char in image_name):
            return False
        
        # Additional validation: must start and end with alphanumeric
        # (single character names are allowed)
        if not image_name:
            return False
        
        if not (image_name[0].isalnum() and image_name[-1].isalnum()):
            return False
        
        return True

    def _detect_distro(self, base_image: str, quiet: bool = False) -> dict:
        """Detect the base OS/distro of the Docker image by running it and checking package managers."""
        if not quiet:
            print(info(f'Analyzing base image: {base_image}'))
        
        # Validate image name to prevent command injection
        if not self._validate_image_name(base_image):
            if not quiet:
                print(bad(f'Invalid Docker image name: {base_image}'))
                print(info('Image names should only contain alphanumeric characters, dots, hyphens, underscores, colons, and slashes.'))
                print(info('Defaulting to Debian-based configuration...'))
            return {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        
        # Login to Docker Hub if credentials are available (for private images or rate limiting)
        if self.docker_username and self.docker_password:
            if not quiet:
                print(info('Logging in to Docker Hub...'))
            # Use subprocess.run with list to avoid shell injection
            result = subprocess.run(
                ['docker', 'login', '-u', self.docker_username, '--password-stdin'],
                input=self.docker_password.encode(),
                capture_output=True,
                text=False
            )
            if result.returncode != 0:
                if not quiet:
                    print(bad(f'Warning: Failed to login to Docker Hub'))
                    print(info('Continuing without Docker Hub authentication...'))
        
        # Pull the image first
        result = subprocess.run(['docker', 'pull', base_image], capture_output=True, text=True)
        
        if result.returncode != 0:
            if not quiet:
                print(bad(f'Failed to pull image: {result.stderr}'))
                print(info('Defaulting to Debian-based configuration...'))
            return {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
        
        # Method 1: Check /etc/os-release for distro information
        if not quiet:
            print(info('Detecting distro by checking OS release info...'))
        result = subprocess.run(
            ['docker', 'run', '--rm', '--entrypoint', '', base_image, 'sh', '-c',
             'cat /etc/os-release 2>/dev/null || cat /etc/alpine-release 2>/dev/null || echo unknown'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout:
            os_info = result.stdout.lower()
            
            # Check for Alpine
            if 'alpine' in os_info:
                if not quiet:
                    print(good('Detected Alpine Linux'))
                return {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
            
            # Check for Debian/Ubuntu/Kali
            if 'debian' in os_info or 'ubuntu' in os_info or 'kali' in os_info:
                if not quiet:
                    print(good('Detected Debian/Ubuntu/Kali'))
                return {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
            
            # Check for RHEL/CentOS/Fedora
            if 'rhel' in os_info or 'centos' in os_info or 'fedora' in os_info or 'red hat' in os_info:
                if not quiet:
                    print(good('Detected RHEL/CentOS/Fedora'))
                # Check if dnf or yum is available
                pkg_check = subprocess.run(
                    ['docker', 'run', '--rm', '--entrypoint', '', base_image, 'sh', '-c',
                     'which dnf 2>/dev/null || which yum 2>/dev/null'],
                    capture_output=True, text=True
                )
                pkg_manager = 'dnf' if 'dnf' in pkg_check.stdout else 'yum'
                return {'type': 'rhel', 'python_pkg': 'python3', 'pkg_manager': pkg_manager, 'needs_break_packages': False}
        
        # Method 2: Check which package managers are available
        if not quiet:
            print(info('Detecting distro by checking available package managers...'))
        result = subprocess.run(
            ['docker', 'run', '--rm', '--entrypoint', '', base_image, 'sh', '-c',
             'which apk apt-get yum dnf 2>/dev/null || true'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout:
            pkg_managers = result.stdout.strip()
            
            # Check in order of specificity
            if 'apk' in pkg_managers:
                if not quiet:
                    print(good('Detected Alpine Linux (via apk)'))
                return {'type': 'alpine', 'python_pkg': 'python3', 'pkg_manager': 'apk', 'needs_break_packages': False}
            elif 'apt-get' in pkg_managers:
                if not quiet:
                    print(good('Detected Debian/Ubuntu (via apt-get)'))
                return {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}
            elif 'dnf' in pkg_managers:
                if not quiet:
                    print(good('Detected Fedora/RHEL (via dnf)'))
                return {'type': 'rhel', 'python_pkg': 'python3', 'pkg_manager': 'dnf', 'needs_break_packages': False}
            elif 'yum' in pkg_managers:
                if not quiet:
                    print(good('Detected CentOS/RHEL (via yum)'))
                return {'type': 'rhel', 'python_pkg': 'python3', 'pkg_manager': 'yum', 'needs_break_packages': False}
        
        # Default to Debian if detection fails
        if not quiet:
            print(info('Could not reliably detect distro, defaulting to Debian-based configuration...'))
        return {'type': 'debian', 'python_pkg': 'python3', 'pkg_manager': 'apt-get', 'needs_break_packages': True}

    def _generate_dockerfile(self, base_image: str, distro_info: dict) -> str:
        """Generate Dockerfile content based on distro."""
        
        if distro_info['type'] == 'alpine':
            return f"""FROM {base_image}

# Install Python and build dependencies required for psutil and other native extensions
RUN apk update && apk add --no-cache python3 py3-pip gcc python3-dev musl-dev linux-headers

# Install acido (psutil will build from source)
RUN python3 -m pip install --break-system-packages acido

ENTRYPOINT []
CMD ["sleep", "infinity"]
"""
        elif distro_info['type'] == 'rhel':
            pkg_manager = distro_info['pkg_manager']
            # Validate pkg_manager to prevent injection
            if pkg_manager not in ['yum', 'dnf']:
                pkg_manager = 'yum'  # Default to yum if invalid
            return f"""FROM {base_image}

# Install Python and build dependencies required for psutil and other native extensions
RUN {pkg_manager} update -y && {pkg_manager} install -y python3 python3-pip gcc python3-devel && {pkg_manager} clean all

# Install acido (psutil will build from source)
RUN python3 -m pip install acido

ENTRYPOINT []
CMD ["sleep", "infinity"]
"""
        else:  # Debian/Ubuntu-based
            # Check if we need --break-system-packages flag
            pip_flags = ' --break-system-packages' if distro_info.get('needs_break_packages', False) else ''
            return f"""FROM {base_image}

# Install Python and build dependencies required for psutil and other native extensions
RUN apt-get update && apt-get install -y python3 python3-pip build-essential python3-dev && rm -rf /var/lib/apt/lists/*

# Install acido (psutil will build from source)
RUN python3 -m pip install{pip_flags} acido

ENTRYPOINT []
CMD ["sleep", "infinity"]
"""

    def create_acido_image(self, base_image: str, quiet: bool = False):
        """
        Create an acido-compatible Docker image from a base image.
        
        Args:
            base_image: Base Docker image name (e.g., 'nuclei', 'ubuntu:20.04')
            quiet: Suppress verbose output and show progress bar
        
        Returns:
            str: The new image name if successful, None otherwise
        """
        # Validate Docker is available
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                if not quiet:
                    print(bad('Docker is not installed or not accessible.'))
                    print(info('Please install Docker and ensure it is in your PATH.'))
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if not quiet:
                print(bad('Docker is not installed or not accessible.'))
                print(info('Please install Docker and ensure it is in your PATH.'))
            return None
        
        # Validate image name before using it
        if not self._validate_image_name(base_image):
            if not quiet:
                print(bad(f'Invalid Docker image name: {base_image}'))
                print(info('Image names should only contain alphanumeric characters, dots, hyphens, underscores, colons, and slashes.'))
            return None
        
        # Initialize progress bar if quiet mode
        pbar = None
        if quiet:
            pbar = tqdm(total=ACIDO_CREATE_STEPS, desc="Creating acido image", unit="step")
            pbar.set_description("Detecting distro")
        
        # Determine OS/package manager from base image
        distro_info = self._detect_distro(base_image, quiet=quiet)
        
        if quiet and pbar:
            pbar.update(1)
            pbar.set_description("Generating Dockerfile")
        
        # Generate Dockerfile content
        dockerfile_content = self._generate_dockerfile(base_image, distro_info)
        
        # Create temporary directory and Dockerfile
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = os.path.join(tmpdir, 'Dockerfile')
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            
            if quiet and pbar:
                pbar.update(1)
                pbar.set_description("Building image")
            
            # Build the image
            # Extract image name and tag from base_image (last component after /)
            last_component = base_image.split('/')[-1]
            if ':' in last_component:
                image_base_name, image_tag = last_component.rsplit(':', 1)
            else:
                image_base_name = last_component
                image_tag = 'latest'
            new_image_name = f"{self.image_registry_server}/{image_base_name}-acido:{image_tag}"
            
            # Validate new image name too
            if not self._validate_image_name(new_image_name):
                if not quiet:
                    print(bad(f'Generated invalid image name: {new_image_name}'))
                if pbar:
                    pbar.close()
                return None
            
            if not quiet:
                print(good(f'Building image: {new_image_name}'))
                print(info(f'Using distro type: {distro_info["type"]}'))
            
            result = subprocess.run(
                ['docker', 'build', '-t', new_image_name, tmpdir],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                if not quiet:
                    print(bad(f'Failed to build image:'))
                    print(result.stderr)
                if pbar:
                    pbar.close()
                return None
            
            # Show build output only if not quiet
            if not quiet and result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f'  {line}')
            
            if not quiet:
                print(good(f'Successfully built {new_image_name}'))
            
            if quiet and pbar:
                pbar.update(1)
                pbar.set_description("Logging in to registry")
            
            # Login to registry
            if not quiet:
                print(info(f'Logging in to registry...'))
            result = subprocess.run(
                ['docker', 'login', self.image_registry_server, '-u', self.image_registry_username, 
                 '--password-stdin'],
                input=self.image_registry_password.encode(),
                capture_output=True,
                text=False
            )
            
            if result.returncode != 0:
                if not quiet:
                    print(bad(f'Failed to login to registry'))
                if pbar:
                    pbar.close()
                return None
            
            if quiet and pbar:
                pbar.update(1)
                pbar.set_description("Pushing to registry")
            
            # Push to registry
            if not quiet:
                print(info(f'Pushing to registry...'))
            result = subprocess.run(
                ['docker', 'push', new_image_name],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                if not quiet:
                    print(bad(f'Failed to push image:'))
                    print(result.stderr)
                if pbar:
                    pbar.close()
                return None
            
            # Show push output only if not quiet
            if not quiet and result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f'  {line}')
            
            if quiet and pbar:
                pbar.update(1)
                pbar.close()
            
            # Extract short name for user-friendly message
            short_name = f"{image_base_name}-acido:{image_tag}"
            
            if not quiet:
                print(good(f'Successfully pushed {new_image_name}'))
                print(info(f'You can now use this image with: acido -f myfleet -im {short_name}'))
            
            return new_image_name

def main():
    """Main entry point for the acido CLI."""
    # Check if user is just asking for help - no config needed
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help']):
        if len(sys.argv) == 1:
            # No arguments provided - show help message
            print(info('Welcome to acido! Use "acido -h" for help or "acido -c" to configure.'))
            sys.exit(0)
        else:
            # -h flag provided, let argparse handle it
            parser.parse_args()
            return
    
    # For -c/--config flag, config check is not needed
    if args.config:
        acido = Acido(check_config=False)
        # setup() is already called in __init__ when args.config is True
        return
    
    # For interactive mode, need config
    if args.interactive:
        acido = Acido()
        code.interact(banner=f'acido {__version__}', local=locals())
        return
    
    # For all other commands, check if config exists
    acido = Acido()
    
    if args.list_instances:
        acido.ls(interactive=True)
    if args.shell:
        acido.save_output(args.shell)
    if args.download_input:
        acido.load_input(args.download_input, write_to_file=True)
    if args.fleet:
        pool = ThreadPoolShim(processes=30)
        args.num_instances = int(args.num_instances) if args.num_instances else 1
        # Build full image URL from short name or keep full URL
        full_image_url = acido.build_image_url(args.image_name, args.image_tag)
        acido.fleet(
            fleet_name=args.fleet, 
            instance_num=int(args.num_instances) if args.num_instances else 1, 
            image_name=full_image_url, 
            scan_cmd=args.task, 
            input_file=args.input_file, 
            wait=int(args.wait) if args.wait else None, 
            write_to_file=args.write_to_file,
            output_format=args.output_format,
            interactive=bool(args.interactive),
            quiet=args.quiet
        )
        if args.rm_when_done:
            acido.rm(args.fleet if args.num_instances <= 10 else f'{args.fleet}*')
    if args.select:
        acido.select(selection=args.select, interactive=bool(args.interactive))
    if args.exec_cmd:
        pool = ThreadPoolShim(processes=30)
        acido.exec(
            command=args.exec_cmd, 
            max_retries=int(args.wait) if args.wait else 60, 
            input_file=args.input_file,
            write_to_file=args.write_to_file
        )
    if args.remove:
        acido.rm(args.remove)
    if args.create_image:
        acido.create_acido_image(args.create_image, quiet=args.quiet)

if __name__ == "__main__":
    main()