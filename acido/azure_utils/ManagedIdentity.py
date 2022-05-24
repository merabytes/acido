import traceback
import azure.common.credentials
import azure.identity
import msrestazure.azure_active_directory
import os as _os
import jwt as _jwt
import getpass
from huepy import *
import sys

__author__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class ManagedAuthentication:

    @property
    def client_id(self) -> str:
        return _os.getenv("MSI_CLIENT_ID")

    def get_credential(self, resource):
        drivers = {
            "cloud": [
                self.get_managed_credential,
                self.get_environment_credential
            ],
            "local": [
                self.get_cli_credential,
                self.get_environment_credential,
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
        if resource in Resources._managed_identity:
            return self._get_managed_identity_credential()
        elif Resources._msi.get(resource) is not None:
            return self._get_msi_credential(
                Resources._msi.get(resource)
            )
        else:
            raise NotImplementedError(f"Unrecognized resource: {resource}")

    def _get_managed_identity_credential(self):
        return azure.identity.ManagedIdentityCredential(
            client_id=self.client_id
        )

    def _get_msi_credential(self, resource):
        return msrestazure.azure_active_directory.MSIAuthentication(
            resource=resource,
            client_id=self.client_id
        )

    def get_cli_credential(self, resource):
        try:
            cred, sub = azure.common.credentials.get_azure_cli_credentials()
        except Exception:
            import traceback
            print(traceback.format_exc())
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
        if isinstance(credential, azure.common.credentials._CliCredentials):
            return azure.common.credentials.get_azure_cli_credentials()[1]
        else:
            if credential:
                obj = _jwt.decode(credential.token['access_token'], verify=False)
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