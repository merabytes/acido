from acido.azure_utils.ManagedIdentity import ManagedAuthentication, Resources
from acido.utils.decoration import __version__
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    ContainerGroup, Container, ImageRegistryCredential, ResourceRequirements,
    ResourceRequests, OperatingSystemTypes, EnvironmentVariable,
    ContainerGroupNetworkProtocol, ResourceIdentityType, ContainerExec, ContainerExecRequestTerminalSize, ContainerExecResponse)
from azure.mgmt.containerinstance.models import ContainerGroupIdentity, ContainerGroupIdentityUserAssignedIdentitiesValue
from msrestazure.azure_exceptions import CloudError
from huepy import *
from shlex import quote

__authors__ = "Juan Ramón Higueras Pica (juanramon.higueras@wsg127.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"


class InstanceManager(ManagedAuthentication):
    def __init__(self, resource_group, login: bool = True, user_assigned: str = None):
        if login:
            credential = self.get_credential(Resources.INSTANCE)
            subscription = self.extract_subscription(credential)
            self._client = ContainerInstanceManagementClient(
                credential,
                subscription
            )
        self.resource_group = resource_group
        self.image_registry_credentials = None
        self.env_vars = {}
        self.instances = []
        self.user_assigned = user_assigned

    def login_image_registry(self, server, username, password):
        image_registry_credentials = ImageRegistryCredential(
            server=server,
            username=username,
            password=password
        )
        self.image_registry_credentials = image_registry_credentials

    def provision(
        self, 
        name, 
        memory: float = 1, 
        cpu: float = 1, 
        ports=None,
        command=[
            'sleep',
            'infinity'
        ], 
        image = 'ubuntu:20.04',
        env_vars: dict = {}
    ):
        env = {}

        for env_key, env_val in env_vars.items():
            env[env_key] = EnvironmentVariable(
            name=env_key,
            value=env_val
        )
        resource_request = ResourceRequests(
            memory_in_gb=memory,
            cpu=cpu
        )
        resource_requirement = ResourceRequirements(
            requests=resource_request
        )
        instance = Container(
            name=name,
            image=image,
            resources=resource_requirement,
            command=command,
            ports=ports,
            environment_variables=list(env.values())
        )
        return instance

    def deploy(
        self, name, tags: dict = {}, location="westeurope",
        ip_address=None, os_type=OperatingSystemTypes.linux,
        restart_policy="Never", network_profile=None, 
        instance_number: int = 3, max_ram: int = 16, 
        max_cpu: int = 4, image_name: str =None,
        env_vars: dict = {}, command: str = None,
        input_files: list = None
    ):
        restart_policies = ["Always", "OnFailure", "Never"]
        if restart_policy not in restart_policies:
            raise ValueError((
                "Unsupported restart policy \"%s\"."
                "Please use one of the following: %s"
                % (restart_policy, ", ".join(restart_policies))
            ))
        if not self.image_registry_credentials:
            ir_credentials = []
        
        if self.image_registry_credentials:
            ir_credentials = [self.image_registry_credentials]

        if network_profile:
            network_profile = ContainerGroupNetworkProtocol(id=network_profile)

        max_ram = "{:.1f}".format(max_ram / (instance_number + 1))
        max_cpu = "{:.1f}".format(max_cpu / (instance_number + 1)) 

        ok = False
        
        results = {}

        deploy_instances = []

        if command:
            command = f"python3 -m acido.cli -sh {quote(command)}"

        for i_num in range(1, instance_number + 1):
            env_vars['INSTANCE_NAME'] = f'{name}-{i_num:02d}'
            scan_cmd = command

            if input_files:
                file_uuid = input_files.pop(0)
                upload_command = f"python3 -m acido.cli -d {file_uuid}"
                if scan_cmd:
                    scan_cmd = upload_command + " && " + scan_cmd
                else:
                    scan_cmd = upload_command

            if scan_cmd:
                deploy_instances.append(
                    self.provision(
                        f'{name}-{i_num:02d}', 
                        memory=float(max_ram), 
                        cpu=float(max_cpu), 
                        image=image_name,
                        env_vars=env_vars,
                        command=["/bin/sh", "-c", scan_cmd]
                        )
                )
            else:
                deploy_instances.append(
                    self.provision(
                        f'{name}-{i_num:02d}', 
                        memory=float(max_ram), 
                        cpu=float(max_cpu), 
                        image=image_name,
                        env_vars=env_vars,
                        command=scan_cmd
                        )
                    )

        try:
            cg = ContainerGroup(
                location=location,
                containers=deploy_instances,
                os_type=os_type,
                ip_address=ip_address,
                image_registry_credentials=ir_credentials,  # noqa: E501
                restart_policy=restart_policy,
                tags=tags,
                network_profile=network_profile,
                identity=ContainerGroupIdentity(
                    type=ResourceIdentityType.user_assigned,
                    user_assigned_identities={
                        self.user_assigned['id']: ContainerGroupIdentityUserAssignedIdentitiesValue(client_id=self.user_assigned['clientId'])
                    }
                )
            )
            self._client.container_groups.create_or_update(
                resource_group_name=self.resource_group,
                container_group_name=name,
                container_group=cg
            )
            ok = True
            for i_num in range(1, instance_number + 1):
                results[f'{name}-{i_num:02d}'] = ok
        except CloudError as e:
            ok = False
            print(bad(e.message))
            raise e

        self.env_vars.clear()
        return results, input_files

    def rm(self, group_name):
        try:
            self._client.container_groups.delete(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except Exception as e:
            print(str(e))
            return False
        return True

    def get(self, group_name):
        try:
            cg = self._client.container_groups.get(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except CloudError as e:
            if e.status_code == 404:
                return False
            else:
                print(bad(e.message))
        return cg

    def ls(self):
        try:
            cg = self._client.container_groups.list_by_resource_group(
                resource_group_name=self.resource_group,
            )
        except CloudError as e:
            print(bad(e.message))
            return []
        return cg

    def restart(self, group_name):
        try:
            self._client.container_groups.restart(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except CloudError as e:
            if e.status_code == 404:
                return False
            else:
                # We don't know what is happening, maybe transitioning?
                print(str(e))
        return True

    def stop(self, group_name):
        try:
            self._client.container_groups.stop(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except CloudError as e:
            print(str(e))
            return False
        return True

    def start(self, group_name):
        try:
            self._client.container_groups.start(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except CloudError as e:
            if e.status_code == 404:
                return False
            else:
                # We don't know what is happening, maybe transitioning?
                print(str(e))
        return True
