from acido.azure_utils.ManagedIdentity import ManagedAuthentication
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError
import os

__authors__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

class VaultManager(ManagedAuthentication):
    # TODO: This should be a singleton
    def __init__(self, vault_name=None):
        if not vault_name:
            vault_name = os.getenv("KEY_VAULT_NAME")
        self.vault_name = vault_name
        self.credential = self.get_credential()
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

    def set_secret(self, secret_name, secret_value):
        """
        Create or update a secret in the Key Vault.
        
        Args:
            secret_name: The name/key for the secret
            secret_value: The value to store
            
        Returns:
            KeyVaultSecret: The created/updated secret
        """
        return self.client.set_secret(secret_name, secret_value)

    def delete_secret(self, secret_name):
        """
        Delete a secret from the Key Vault.
        
        Args:
            secret_name: The name/key of the secret to delete
            
        Returns:
            DeletedSecret: Information about the deleted secret
        """
        return self.client.begin_delete_secret(secret_name).result()

    def secret_exists(self, secret_name):
        """
        Check if a secret exists in the Key Vault.
        
        Args:
            secret_name: The name/key of the secret to check
            
        Returns:
            bool: True if the secret exists, False otherwise
        """
        try:
            self.client.get_secret(secret_name)
            return True
        except ResourceNotFoundError:
            return False

    def __getattr__(self, name):
        return self.get_secret(name)
