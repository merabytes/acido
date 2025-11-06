from azure.identity import (
    AzureCliCredential,
    ManagedIdentityCredential,
    ClientSecretCredential,
    EnvironmentCredential,
)
from azure.mgmt.resource import SubscriptionClient
import azure.identity
import os as _os
import jwt as _jwt
import sys
import logging
from typing import Iterable

logging.getLogger('azure.identity').setLevel(logging.ERROR)


def _as_scope(url: str) -> str:
    return url.rstrip("/") + "/.default"


class Resources:
    # central place for resource endpoints
    _msi = {
        "instance": "https://management.azure.com/",
        "blob": "https://storage.azure.com/",
        "vault": "https://vault.azure.net/",
    }
    INSTANCE = "instance"
    VAULT = "vault"
    BLOB = "blob"


class ManagedIdentity:
    """
    get_credential() prefers Managed Identity if MANAGED_IDENTITY_CLIENT_ID is present;
    otherwise uses ClientSecretCredential. For service principals, validates only against
    ARM (management) to avoid unnecessary Key Vault / Blob grants.
    """

    # ---------------- Public API ----------------

    @property
    def client_id(self) -> str:
        return _os.getenv("MANAGED_IDENTITY_CLIENT_ID")

    def get_credential(self, scope_keys: Iterable[str] = ("instance",)):
        """
        Returns a credential validated against at least one of the requested scopes.
        Priority:
          1) Managed Identity if MANAGED_IDENTITY_CLIENT_ID is set
          2) ClientSecretCredential (env-only; fail fast if missing)
        Notes:
          - For SP usage, keep scope_keys=("instance",) so we only test ARM.
        """
        # 1) Prefer Managed Identity when client id is configured
        if self.client_id:
            mi = self._get_managed_identity_credential()
            if self._ensure_any_scope(mi, scope_keys):
                return mi
            # fall through to SP only if MI cannot get any requested scope

        # 2) Client Secret (env-only; do not prompt to keep non-interactive)
        sp = self._get_client_secret_credential()
        if self._ensure_any_scope(sp, ("instance",)):  # ARM-only for SP
            return sp

        scopes = ", ".join(f"{k}={Resources._msi.get(k, '?')}" for k in scope_keys)
        raise RuntimeError(
            "Unable to acquire an access token for any of the requested scopes. "
            f"Scopes tried: {scopes}. Verify credentials and permissions."
        )

    def extract_subscription(self, credential) -> str:
        """
        Resolve subscription id in this order:
          1) AZURE_SUBSCRIPTION_ID env var (recommended)
          2) SubscriptionClient(...).subscriptions.list()  (works if directory perms allow)
          3) Decode ARM token and read xms_mirid (best-effort fallback)
        """
        env_sub = _os.getenv("AZURE_SUBSCRIPTION_ID")
        if env_sub:
            return env_sub

        # Try ARM list (may fail for SPs without directory read permission)
        try:
            subs = SubscriptionClient(credential).subscriptions.list()
            first = next(iter(subs))
            return first.subscription_id
        except Exception:
            pass

        # Last resort: decode an ARM token and read xms_mirid
        try:
            token = credential.get_token(_as_scope(Resources._msi["instance"])).token
            obj = _jwt.decode(token, options={"verify_signature": False})
            mirid = obj.get("xms_mirid")
            if mirid:
                # format: /subscriptions/<id>/resourceGroups/...
                return mirid.split("/")[2]
        except Exception:
            pass

        raise RuntimeError(
            "Unable to resolve subscription id. Set AZURE_SUBSCRIPTION_ID or grant permission to list subscriptions."
        )

    # ---------------- Helpers ----------------

    def _ensure_any_scope(self, cred, scope_keys):
        for key in scope_keys:
            url = Resources._msi.get(key)
            if not url:
                continue
            scope = _as_scope(url)
            try:
                cred.get_token(scope)
                return True
            except Exception as e:
                continue
        return False


    def _get_managed_identity_credential(self) -> ManagedIdentityCredential:
        # For user-assigned MI, MANAGED_IDENTITY_CLIENT_ID must be set in the environment
        return ManagedIdentityCredential(client_id=self.client_id)

    def _get_client_secret_credential(self) -> ClientSecretCredential:
        tenant_id = _os.getenv("AZURE_TENANT_ID")
        client_id = _os.getenv("AZURE_CLIENT_ID")
        client_secret = _os.getenv("AZURE_CLIENT_SECRET")

        missing = [k for k, v in {
            "AZURE_TENANT_ID": tenant_id,
            "AZURE_CLIENT_ID": client_id,
            "AZURE_CLIENT_SECRET": client_secret,
        }.items() if not v]
        if missing:
            raise RuntimeError(
                f"Missing required env vars for ClientSecretCredential: {', '.join(missing)}"
            )

        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )

    # Optional convenience (kept for parity with your original class)

    def get_managed_credential(self) -> ManagedIdentityCredential:
        return self._get_managed_identity_credential()

    def get_cli_credential(self):
        try:
            return AzureCliCredential()
        except Exception:
            return None

    def get_environment_credential(self):
        if not self._environment_ok():
            return None
        return EnvironmentCredential()

    def _environment_ok(self) -> bool:
        checks = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
        return all(check in _os.environ for check in checks)
