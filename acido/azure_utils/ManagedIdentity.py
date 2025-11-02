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
import logging
from typing import Iterable, Tuple

logging.getLogger('azure.identity').setLevel(logging.ERROR)

__author__ = "Juan Ramón Higueras Pica (jrhigueras@dabbleam.com)"
__coauthor__ = "Xavier Álvarez Delgado (xalvarez@merabytes.com)"

def _as_scope(url: str) -> str:
    return url.rstrip("/") + "/.default"


class ManagedIdentity:
    """
    get_credential() prefers Managed Identity if MANAGED_IDENTITY_CLIENT_ID is present;
    otherwise uses ClientSecretCredential. In both cases, validates by acquiring a token
    for ANY of the requested scopes (vault/blob/instance).
    """

    @property
    def client_id(self) -> str:
        return _os.getenv("MANAGED_IDENTITY_CLIENT_ID")

    def get_credential(self, scope_keys: Iterable[str] = ("vault", "blob", "instance")):
        """
        Returns a credential validated against at least one of the provided scopes.
        Priority:
          1) Managed Identity if MANAGED_IDENTITY_CLIENT_ID is set
          2) ClientSecretCredential (env-first, prompt-if-missing)
        """
        # 1) Prefer Managed Identity when client id is configured
        if self.client_id:
            mi = self._get_managed_identity_credential()
            if self._ensure_any_scope(mi, scope_keys):
                return mi
            # fall through to SP only if MI cannot get any requested scope

        # 2) Client Secret (env-first; prompt for missing)
        sp = self.get_client_secret_credential()
        if self._ensure_any_scope(sp, scope_keys):
            return sp

        scopes = ", ".join(f"{k}={Resources._msi.get(k, '?')}" for k in scope_keys)
        raise RuntimeError(
            "Unable to acquire an access token for any of the requested scopes. "
            f"Scopes tried: {scopes}. Verify credentials and permissions."
        )

    # ---- Helpers ------------------------------------------------------------
    def _ensure_any_scope(self, cred, scope_keys: Iterable[str]) -> bool:
        for key in scope_keys:
            url = Resources._msi.get(key)
            if not url:
                continue
            try:
                cred.get_token(_as_scope(url))
                return True
            except Exception:
                continue
        return False

    # Individual builders kept for completeness / reuse
    def get_managed_credential(self):
        return self._get_managed_identity_credential()

    def _get_managed_identity_credential(self):
        return azure.identity.ManagedIdentityCredential(client_id=self.client_id)

    def get_cli_credential(self):
        try:
            return AzureCliCredential()
        except Exception:
            return None

    def get_client_secret_credential(self):
        tenant_id = _os.getenv("AZURE_TENANT_ID")
        client_id = _os.getenv("AZURE_CLIENT_ID")
        client_secret = _os.getenv("AZURE_CLIENT_SECRET")

        if not tenant_id:
            tenant_id = input("Enter AZURE_TENANT_ID: ")
        if not client_id:
            client_id = input("Enter AZURE_CLIENT_ID: ")
        if not client_secret:
            client_secret = getpass.getpass("Enter AZURE_CLIENT_SECRET: ")

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

    # --- Subscription extraction with Vault fallback (unchanged logic) -------
    def extract_subscription(self, credential):
        if isinstance(credential, (AzureCliCredential, azure.identity._credentials.azure_cli.AzureCliCredential)):
            try:
                subs = SubscriptionClient(credential).subscriptions.list()
                first = next(iter(subs))
                return first.subscription_id
            except StopIteration:
                print(bad("No subscriptions found for the current Azure CLI context."))
                sys.exit(1)

        def try_arm_list():
            try:
                subs = SubscriptionClient(credential).subscriptions.list()
                first = next(iter(subs))
                return first.subscription_id
            except Exception:
                return None

        def sub_from_scope(scope_key: str):
            try:
                token = credential.get_token(_as_scope(Resources._msi[scope_key])).token
                obj = _jwt.decode(token, options={"verify_signature": False})
                mirid = obj.get("xms_mirid")
                if mirid:
                    return mirid.split("/")[2]
            except Exception:
                pass
            return None

        if isinstance(credential, ManagedIdentityCredential):
            sub_id = try_arm_list()
            if sub_id:
                return sub_id
            for scope in ("vault", "blob", "instance"):
                sub_id = sub_from_scope(scope)
                if sub_id:
                    return sub_id
            print(bad("Could not determine subscription id from Managed Identity token."))
            sys.exit(1)

        sub_id = try_arm_list()
        if sub_id:
            return sub_id
        for scope in ("instance", "vault", "blob"):
            sub_id = sub_from_scope(scope)
            if sub_id:
                return sub_id
        print(bad("Unable to resolve subscription id. Ensure the credential has ARM access or run az login."))
        sys.exit(1)


class Resources:
    _managed_identity = ["vault"]
    _msi = {
        "instance": "https://management.azure.com/",
        "blob": "https://storage.azure.com/",
        "vault": "https://vault.azure.net/",
    }

    INSTANCE = "instance"
    VAULT = "vault"
    BLOB = "blob"
    NETWORK = "network"
