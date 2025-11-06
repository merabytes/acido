from acido.azure_utils.ManagedIdentity import ManagedIdentity
from acido.utils.decoration import __version__
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    ContainerGroup, Container, ImageRegistryCredential, ResourceRequirements,
    ResourceRequests, OperatingSystemTypes, EnvironmentVariable,
    ResourceIdentityType, ContainerGroupIdentity, UserAssignedIdentities
)
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from huepy import bad
from shlex import quote
import logging

__authors__ = "Juan Ramón Higueras Pica (juanramon.higueras@wsg127.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

logger = logging.getLogger('msrest.serialization')
logger.disabled = True


class InstanceManager(ManagedIdentity):
    """
    Manages Azure Container Instances using either Managed Identity or ClientSecret credentials.
    Credentials are validated against the ARM (instance) scope.
    """

    def __init__(self, resource_group, login: bool = True, user_assigned: dict = {}, network_profile=None):
        if login:
            # ✅ Use instance (ARM) scope for authentication
            credential = self.get_credential(scope_keys=("instance",))
            subscription = self.extract_subscription(credential)
            self._client = ContainerInstanceManagementClient(
                credential,
                subscription
            )
        self.resource_group = resource_group
        self.image_registry_credentials = None
        self.network_profile = network_profile
        self.env_vars = {}
        self.instances = []
        self.user_assigned = user_assigned

    def login_image_registry(self, server, username, password):
        self.image_registry_credentials = ImageRegistryCredential(
            server=server,
            username=username,
            password=password
        )

    def provision(self, name, memory: float = 1, cpu: float = 1, ports=None,
                  command=['sleep', 'infinity'],
                  image='ubuntu:20.04', env_vars: dict = {}):
        env = {
            k: EnvironmentVariable(name=k, value=v)
            for k, v in env_vars.items()
        }

        resource_request = ResourceRequests(memory_in_gb=memory, cpu=cpu)
        resource_requirement = ResourceRequirements(requests=resource_request)

        instance = Container(
            name=name,
            image=image,
            resources=resource_requirement,
            command=command,
            ports=ports,
            environment_variables=list(env.values())
        )
        return instance

    def deploy(self, name, tags: dict = {}, location="westeurope",
               ip_address=None, os_type=OperatingSystemTypes.linux,
               restart_policy="Never", network_profile=None,
               instance_number: int = 3, max_ram: int = 16,
               max_cpu: int = 4, image_name: str = None,
               env_vars: dict = {}, command: str = None,
               input_files: list = None, quiet: bool = False):
        restart_policies = ["Always", "OnFailure", "Never"]
        if restart_policy not in restart_policies:
            raise ValueError(
                f"Unsupported restart policy '{restart_policy}'. Use one of: {', '.join(restart_policies)}"
            )

        ir_credentials = [self.image_registry_credentials] if self.image_registry_credentials else []

        max_ram = "{:.1f}".format(max_ram / (instance_number + 1))
        max_cpu = "{:.1f}".format(max_cpu / (instance_number + 1))

        results = {}
        deploy_instances = []

        for i_num in range(1, instance_number + 1):
            env_vars['INSTANCE_NAME'] = f'{name}-{i_num:02d}'
            scan_cmd = command

            if input_files:
                file_uuid = input_files.pop(0)
                # Pass input UUID via environment variable instead of chained command
                env_vars['ACIDO_INPUT_UUID'] = file_uuid

            deploy_instances.append(
                self.provision(
                    f'{name}-{i_num:02d}',
                    memory=float(max_ram),
                    cpu=float(max_cpu),
                    image=image_name,
                    env_vars=env_vars,
                    command=["/opt/acido-venv/bin/acido", "-sh", command] if scan_cmd else None
                )
            )

        try:
            cg = ContainerGroup(
                location=location,
                containers=deploy_instances,
                os_type=os_type,
                ip_address=ip_address,
                image_registry_credentials=ir_credentials,
                restart_policy=restart_policy,
                tags=tags,
                network_profile=self.network_profile,
                identity=ContainerGroupIdentity(
                    type=ResourceIdentityType.user_assigned,
                    user_assigned_identities={
                        self.user_assigned['id']: UserAssignedIdentities(
                            client_id=self.user_assigned.get('clientId', '')
                        )
                    }
                )
            )
            self._client.container_groups.begin_create_or_update(
                resource_group_name=self.resource_group,
                container_group_name=name,
                container_group=cg
            ).result()

            for i_num in range(1, instance_number + 1):
                results[f'{name}-{i_num:02d}'] = True

        except HttpResponseError as e:
            if not quiet:
                print(bad(str(e)))
            raise e

        self.env_vars.clear()
        return results, input_files

    def rm(self, group_name: str) -> bool:
        try:
            poller = self._client.container_groups.begin_delete(
                resource_group_name=self.resource_group,
                container_group_name=group_name,
            )
            poller.result()
            return True
        except ResourceNotFoundError:
            print(f"Container group '{group_name}' not found.")
            return False
        except HttpResponseError as e:
            print(f"Delete failed: {e}")
            return False

    def get(self, group_name):
        try:
            cg = self._client.container_groups.get(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except HttpResponseError as e:
            if e.status_code == 404:
                return False
            print(bad(str(e)))
            return None
        return cg

    def ls(self):
        try:
            return self._client.container_groups.list_by_resource_group(
                resource_group_name=self.resource_group
            )
        except HttpResponseError as e:
            print(bad(str(e)))
            return []

    def restart(self, group_name):
        try:
            self._client.container_groups.restart(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except HttpResponseError as e:
            if e.status_code == 404:
                return False
            print(str(e))
        return True

    def stop(self, group_name):
        try:
            self._client.container_groups.stop(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except HttpResponseError as e:
            print(str(e))
            return False
        return True

    def start(self, group_name):
        try:
            self._client.container_groups.start(
                resource_group_name=self.resource_group,
                container_group_name=group_name
            )
        except HttpResponseError as e:
            if e.status_code == 404:
                return False
            print(str(e))
        return True

    def get_container_logs(self, container_group_name: str, container_name: str, tail: int = None, timestamps: bool = False) -> str:
        logs = self._client.containers.list_logs(
            resource_group_name=self.resource_group,
            container_group_name=container_group_name,
            container_name=container_name,
            tail=tail,
            timestamps=timestamps
        )
        return logs.content
