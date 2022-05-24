from azure.storage.blob import BlobServiceClient
from uuid import uuid4 as uuid
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from acido.azure_utils.ManagedIdentity import ManagedAuthentication, Resources
from huepy import *
import os

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class BlobManager(ManagedAuthentication):
    service_client = None
    container_client = None
    uuid = None

    def __init__(
        self,
        resource_group: str = None,
        account_name: str = None,
        account_key: str = None,
        conn_str: str = None,
    ):  
        conn_str = os.getenv('BLOB_CONNECTION', None)
        if account_name and account_key:
            self.service_client = BlobManager.auth(account_name, account_key)
            self.account_name = account_name
            self.account_key = account_key
        elif conn_str:
            self.service_client = BlobServiceClient.from_connection_string(
                conn_str
            )
        else:
            resource_group_name = resource_group
            self.url = f"https://{account_name}.blob.core.windows.net"
            credential = self.get_credential(Resources.BLOB)
            subscription = self.extract_subscription(credential)
            self._resource_client = ResourceManagementClient(credential, subscription)
            self._client = StorageManagementClient(
                credential,
                subscription
            )
            availability_result = self._client.storage_accounts.check_name_availability(
                { "name": account_name }
            )
            if availability_result:
                poller = self._client.storage_accounts.begin_create(resource_group_name, account_name,
                parameters={
                        "location" : "westeurope",
                        "kind": "StorageV2",
                        "sku": {"name": "Standard_LRS"}
                    }
                )
                poller.result()
                print(good(f'Selecting I/O storage account ({account_name}).'))
            
            account_key = self._client.storage_accounts.list_keys(resource_group_name, account_name).keys[0].value
            self.account_name = account_name
            self.account_key = account_key
            self.service_client = self.auth(
                self.account_name,
                self.account_key
            )

    @staticmethod
    def auth(account_name: str, account_key: str):
        conn_str = (
            "DefaultEndpointsProtocol=https;"
            "AccountName={name};AccountKey={key};"
            "EndpointSuffix=core.windows.net"
        )
        return BlobServiceClient.from_connection_string(
            conn_str=conn_str.format(name=account_name, key=account_key)
        )

    def check_access(self, client: BlobServiceClient) -> bool:
        try:
            client.list_containers().next()
        except Exception as e:
            print(e)
            return False
        return True

    def get_client(self, credential) -> BlobServiceClient:
        return BlobServiceClient(self.url, credential=credential)

    def use_container(
        self,
        container_name: str,
        create_if_not_exists: bool = False
    ) -> bool:
        self.container_client = self.service_client.get_container_client(
            container_name
        )
        try:
            self.container_client.get_container_properties()
        except ResourceNotFoundError as e:
            if e.status_code == 404 and create_if_not_exists:
                self.container_client.create_container()
                self.container_client = self.service_client.get_container_client(
                    container_name
                )
            else:
                return False
        return True

    def ls(self):
        if not self.container_client:
            return []
        return self.container_client.list_blobs(include=['metadata', 'tags'])

    def upload(
        self,
        data,
        filename: str = None,
        overwrite: bool = False,
        metadata: dict = {}
    ):
        # TODO: try to guess mimetype
        # see https://docs.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.contentsettings?view=azure-python
        # My guess is to use python-magic
        if not self.container_client:
            return False
        if not filename:
            filename = self.generate_uuid()
        if self.uuid is not None:
            self.uuid = None
        return self.container_client.upload_blob(
            name=filename,
            data=data,
            overwrite=overwrite,
            metadata=metadata,
            length=len(data)
        ), filename

    def download(self, filename: str):
        if not self.container_client:
            return False
        return self.container_client.download_blob(filename).content_as_bytes()

    def get_metadata(self, filename: str) -> dict:
        if not self.container_client:
            return {}
        return self.container_client.get_blob_client(filename).get_blob_properties().metadata or {}

    def set_metadata(self, filename: str, metadata: dict):
        if not self.container_client:
            return {}
        self.container_client.get_blob_client(filename).set_blob_metadata(metadata)

    def get_tags(self, filename: str) -> dict:
        if not self.container_client:
            return {}
        return self.container_client.get_blob_client(filename).get_blob_tags() or {}

    def set_tags(self, filename: str, tags: dict) -> dict:
        if not self.container_client:
            return {}
        self.container_client.get_blob_client(filename).set_blob_tags(tags)

    def get_properties(self, filename: str) -> dict:
        if not self.container_client:
            return {}

        return dict(self.container_client.get_blob_client(filename).get_blob_properties()) or {}

    def rm(self, filename: str):
        if not self.container_client:
            return False
        return self.container_client.delete_blob(filename)

    def get_uuid(self) -> str:
        if not self.uuid:
            return self.generate_uuid()
        else:
            return self.uuid

    @staticmethod
    def download_private_url(url, key: str):
        url = url.replace("https://", "")
        account_name = url.split(".")[0]
        client = BlobManager.auth(account_name, key)
        container, blob = url.split("/")[1:]
        return client.get_blob_client(
            container=container,
            blob=blob
        ).download_blob()

    def generate_uuid(self) -> str:
        self.uuid = str(uuid())
        for file in self.ls():
            if file['name'] == self.uuid:
                return self.generate_uuid()
        return self.uuid
