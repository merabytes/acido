from azure.identity import (
    AzureCliCredential,
    ManagedIdentityCredential,
    EnvironmentCredential,
    ClientSecretCredential
)
from azure.mgmt.resource import SubscriptionClient
import azure.identity
import os as _os
import jwt as _jwt
import getpass
from huepy import bad
import sys
import traceback
import logging

# Suppress Azure CLI credential warnings when using alternative credentials
logging.getLogger('azure.identity').setLevel(logging.ERROR)

__author__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

def _as_scope(url: str) -> str:
    # turn "https://storage.azure.com/" into "https://storage.azure.com/.default"
    return url.rstrip("/") + "/.default"

class ManagedAuthentication:

    @property
    def client_id(self) -> str:
        return _os.getenv("MANAGED_IDENTITY_CLIENT_ID")

    def get_credential(self):
        drivers = {
            "cloud": [
                self.get_environment_credential,
                self.get_managed_credential,
                self.get_cli_credential
            ],
            "local": [
                self.get_environment_credential,
                self.get_cli_credential,
                self.get_client_secret_credential
            ]
        }

        driver_list = "cloud" if self.is_cloud() else "local"

        def credential_works(cred) -> bool:
            try:
                # ARM scope is a lightweight sanity check
                cred.get_token(_as_scope(Resources._msi["instance"]))
                return True
            except Exception:
                return False

        # If a check_access hook exists, use it to validate the client as well.
        for driver in drivers[driver_list]:
            cred = driver()
            if not cred:
                continue
            if hasattr(self, "check_access"):
                try:
                    client = self.get_client(cred)
                    if self.check_access(client):
                        return cred
                except Exception:
                    continue
            else:
                if credential_works(cred):
                    return cred

        print("No permissions granted for the available credentials.")
        return None

    def get_managed_credential(self):
        return self._get_managed_identity_credential()

    def _get_managed_identity_credential(self):
        return azure.identity.ManagedIdentityCredential(
            client_id=self.client_id
        )

    def get_cli_credential(self):
        try:
            return AzureCliCredential()
        except Exception:
            # Silently return None to allow fallback to other credential methods
            return None

    def get_client_secret_credential(self):
        tenant_id = input("Enter TENANT_ID: ")
        client_id = input("Enter CLIENT_ID: ")
        client_secret = getpass.getpass("Enter CLIENT_SECRET: ")
        return azure.identity.ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )

    def get_environment_credential(self):
        if not self._environment_ok():
            return None
        return azure.identity.EnvironmentCredential()

    def _environment_ok(self):
        checks = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
        return all(check in _os.environ for check in checks)

    def is_cloud(self):
        force = "INSTANCE_NAME" in _os.environ
        auto = "MSI_ENDPOINT" in _os.environ or "MSI_SECRET" in _os.environ
        return force or auto

    def extract_subscription(self, credential):
        # 1) Azure CLI: list subscriptions directly
        if isinstance(credential, (AzureCliCredential, azure.identity._credentials.azure_cli.AzureCliCredential)):
            try:
                subs = SubscriptionClient(credential).subscriptions.list()
                first = next(iter(subs))
                return first.subscription_id
            except StopIteration:
                print(bad("No subscriptions found for the current Azure CLI context."))
                sys.exit(1)

        # Helper: try ARM list using whatever credential we have
        def try_arm_list():
            try:
                subs = SubscriptionClient(credential).subscriptions.list()
                first = next(iter(subs))
                return first.subscription_id
            except Exception:
                return None

        # 2) Managed Identity: first try ARM list; if not allowed, decode xms_mirid
        if isinstance(credential, ManagedIdentityCredential):
            sub_id = try_arm_list()
            if sub_id:
                return sub_id
            # Fallback: get a token (blob scope is fine—now correctly formed) and read xms_mirid
            token = credential.get_token(_as_scope(Resources._msi["blob"])).token
            obj = _jwt.decode(token, options={"verify_signature": False})
            mirid = obj.get("xms_mirid")
            if mirid:
                return mirid.split("/")[2]
            # As a second fallback, try ARM scope for the same trick
            token = credential.get_token(_as_scope(Resources._msi["instance"])).token
            obj = _jwt.decode(token, options={"verify_signature": False})
            mirid = obj.get("xms_mirid")
            if mirid:
                return mirid.split("/")[2]
            print(bad("Could not determine subscription id from Managed Identity token."))
            sys.exit(1)

        # 3) Environment / ClientSecret / other credentials:
        # Prefer ARM list; if not permitted, try decoding xms_mirid from an ARM-scoped token.
        if isinstance(credential, (EnvironmentCredential, ClientSecretCredential)) or credential:
            sub_id = try_arm_list()
            if sub_id:
                return sub_id
            try:
                token = credential.get_token(_as_scope(Resources._msi["instance"])).token
                obj = _jwt.decode(token, options={"verify_signature": False})
                mirid = obj.get("xms_mirid")
                if mirid:
                    return mirid.split("/")[2]
            except Exception:
                pass
            print(bad("Unable to resolve subscription id. Ensure the credential has ARM access or run az login."))
            sys.exit(1)
        
        import code
        code.interact(local=locals())

        # 4) No credential available
        print(bad("Please run az login or provide valid credentials."))
        sys.exit(1)


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
