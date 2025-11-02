from acido.azure_utils.ManagedIdentity import ManagedIdentity
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError
import os

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class VaultManager(ManagedIdentity):
    # TODO: This should be a singleton
    def __init__(self, vault_name=None):
        if not vault_name:
            vault_name = os.getenv("KEY_VAULT_NAME")
        if not vault_name:
            raise RuntimeError("KEY_VAULT_NAME is required (env var or ctor arg).")
        self.vault_name = vault_name

        # Prefer MI if MANAGED_IDENTITY_CLIENT_ID is set; otherwise SP.
        # Validate specifically for Key Vault.
        self.credential = self.get_credential(scope_keys=("vault",))
        self.client = self.get_client(self.credential)

    def get_client(self, credential):
        return SecretClient(
            vault_url=f"https://{self.vault_name}.vault.azure.net",
            credential=credential
        )

    def check_access(self, client):
        try:
            pager = client.list_properties_of_secrets()
            first = next(iter(pager), None)
            if not first:
                return True
            client.get_secret(first.name).value
            return True
        except Exception:
            return False

    def get_secret(self, secret_name):
        return self.client.get_secret(secret_name).value

    def set_secret(self, secret_name, secret_value):
        return self.client.set_secret(secret_name, secret_value)

    def delete_secret(self, secret_name):
        return self.client.begin_delete_secret(secret_name).result()

    def secret_exists(self, secret_name):
        try:
            self.client.get_secret(secret_name)
            return True
        except ResourceNotFoundError:
            return False

    def __getattr__(self, name):
        return self.get_secret(name)
