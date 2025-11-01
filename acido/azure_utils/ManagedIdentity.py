from azure.identity import AzureCliCredential
from azure.mgmt.resource import SubscriptionClient
import azure.identity
import os as _os
import jwt as _jwt
import getpass
from huepy import *
import sys
import traceback
import logging

# Suppress Azure CLI credential warnings when using alternative credentials
logging.getLogger('azure.identity').setLevel(logging.ERROR)

__author__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class ManagedAuthentication:

    @property
    def client_id(self) -> str:
        return _os.getenv("IDENTITY_CLIENT_ID")

    def get_credential(self, resource):
        drivers = {
            "cloud": [
                self.get_environment_credential,
                self.get_managed_credential
            ],
            "local": [
                self.get_environment_credential,
                self.get_cli_credential,
                self.get_client_secret_credential
            ]
        }
        
        driver_list = "local"

        if self.is_cloud():
            driver_list = "cloud"

        if hasattr(self, "check_access"):
            ok = False
            for driver in drivers[driver_list]:
                credential = driver(resource)
                if not credential:
                    continue
                client = self.get_client(credential)
                if self.check_access(client):
                    ok = True
                    return credential
            if not ok:
                print("No permissions granted for the given credentials.")
        else:
            return drivers[driver_list][0](resource)

    def get_managed_credential(self, resource):
        return self._get_managed_identity_credential()

    def _get_managed_identity_credential(self):
        return azure.identity.ManagedIdentityCredential(
            client_id=self.client_id
        )

    def get_cli_credential(self, resource):
        try:
            cred = AzureCliCredential()
        except Exception:
            # Silently return None to allow fallback to other credential methods
            return None
        return cred

    def get_client_secret_credential(self, resource):
        tenant_id = input("Enter TENANT_ID: ")
        client_id = input("Enter CLIENT_ID: ")
        client_secret = getpass.getpass("Enter CLIENT_SECRET: ")
        return azure.identity.ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )

    def get_environment_credential(self, resource):
        if self._environment_ok() is False:
            return False
        return azure.identity.EnvironmentCredential()

    def _environment_ok(self):
        checks = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
        for check in checks:
            if check not in _os.environ:
                return False
        return True

    def is_cloud(self):
        force = "INSTANCE_NAME" in _os.environ
        auto = "MSI_ENDPOINT" in _os.environ
        auto = auto or "MSI_SECRET" in _os.environ
        return force or auto

    def extract_subscription(self, credential):
        if isinstance(credential, AzureCliCredential):
            return SubscriptionClient(credential).subscriptions.list().next().id.split("/")[2]
        else:
            if credential:
                print(type(credential))
                obj = _jwt.decode(credential.get_token(Resources._msi["blob"]).token, options={"verify_signature": False})
                return obj['xms_mirid'].split("/")[2]
            else:
                print(bad('Please run az login to refresh credentials.'))
                sys.exit()


class Resources:
    _managed_identity = ["vault"]
    _msi = {
        "instance": "https://management.azure.com/",
        "blob": "https://storage.azure.com/"
    }

    INSTANCE = "instance"
    VAULT = "vault"
    BLOB = "blob"
    NETWORK = "network"