from acido.azure_utils.ManagedIdentity import ManagedAuthentication, Resources
from azure.keyvault.secrets import SecretClient
import os

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class VaultManager(ManagedAuthentication):
    # TODO: This should be a singleton
    def __init__(self, vault_name=None):
        if not vault_name:
            vault_name = os.getenv("KEY_VAULT_NAME")
        self.vault_name = vault_name
        self.credential = self.get_credential(Resources.VAULT)
        self.client = self.get_client(self.credential)

    def get_client(self, credential):
        return SecretClient(
            vault_url=f"https://{self.vault_name}.vault.azure.net",
            credential=credential
        )

    def check_access(self, client):
        try:
            name = client.list_properties_of_secrets().next().name
            client.get_secret(name).value
        except Exception:
            return False
        return True

    def get_secret(self, secret_name):
        return self.client.get_secret(secret_name).value

    def __getattr__(self, name):
        return self.get_secret(name)
