"""
AWS Lambda handler for acido secrets sharing service.

This module provides a OneTimeSecret-like service where secrets can be:
- Created with a generated UUID
- Retrieved and deleted (one-time access)

The service uses Azure KeyVault for secure secret storage.
Optional CloudFlare Turnstile support for bot protection.
"""

import os
import uuid
import traceback
from acido.azure_utils.VaultManager import VaultManager
from acido.utils.lambda_utils import (
    parse_lambda_event,
    build_response,
    build_error_response,
    extract_http_method,
    extract_remote_ip
)
from acido.utils.crypto_utils import encrypt_secret, decrypt_secret, is_encrypted
from acido.utils.turnstile_utils import validate_turnstile


# CORS headers - origin is configurable via CORS_ORIGIN environment variable
CORS_HEADERS = {
    "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "https://secrets.merabytes.com"),
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json"
}


def _handle_healthcheck():
    """Handle healthcheck action."""
    return build_response(200, {
        'status': 'healthy',
        'message': 'Lambda function is running',
        'version': '0.37'
    }, CORS_HEADERS)


def _handle_create_secret(event, vault_manager):
    """Handle secret creation action."""
    secret_value = event.get('secret')
    password = event.get('password')
    
    if not secret_value:
        return build_error_response(
            'Missing required field: secret',
            headers=CORS_HEADERS
        )
    
    # Generate UUID for the secret
    secret_uuid = str(uuid.uuid4())
    
    # Track whether the secret is encrypted
    is_encrypted_flag = False
    
    # Encrypt secret if password is provided
    if password:
        try:
            secret_value = encrypt_secret(secret_value, password)
            is_encrypted_flag = True
        except Exception as e:
            return build_response(500, {
                'error': f'Encryption failed: {str(e)}'
            }, CORS_HEADERS)
    
    # Store secret in Key Vault
    vault_manager.set_secret(secret_uuid, secret_value)
    
    # Store encryption metadata as a separate secret
    # Using a naming convention: {uuid}-metadata
    metadata_key = f"{secret_uuid}-metadata"
    vault_manager.set_secret(metadata_key, "encrypted" if is_encrypted_flag else "plaintext")
    
    # Return success response with UUID
    return build_response(201, {
        'uuid': secret_uuid,
        'message': 'Secret created successfully'
    }, CORS_HEADERS)


def _handle_retrieve_secret(event, vault_manager):
    """Handle secret retrieval and deletion action."""
    secret_uuid = event.get('uuid')
    password = event.get('password')
    
    if not secret_uuid:
        return build_error_response(
            'Missing required field: uuid',
            headers=CORS_HEADERS
        )
    
    # Check if secret exists
    if not vault_manager.secret_exists(secret_uuid):
        return build_response(404, {
            'error': 'Secret not found or already accessed'
        }, CORS_HEADERS)
    
    # Check metadata to determine if secret is encrypted
    metadata_key = f"{secret_uuid}-metadata"
    try:
        metadata_value = vault_manager.get_secret(metadata_key)
        is_encrypted_secret = (metadata_value == "encrypted")
    except Exception:
        # If metadata doesn't exist, fall back to heuristic check for backward compatibility
        secret_value = vault_manager.get_secret(secret_uuid)
        is_encrypted_secret = is_encrypted(secret_value)
    
    # Retrieve the secret value
    secret_value = vault_manager.get_secret(secret_uuid)
    
    # Decrypt secret if it's encrypted
    if is_encrypted_secret:
        if not password:
            # Delete both secret and metadata
            vault_manager.delete_secret(secret_uuid)
            try:
                vault_manager.delete_secret(metadata_key)
            except Exception:
                pass
            return build_response(400, {
                'error': 'Password required for encrypted secret'
            }, CORS_HEADERS)
        
        try:
            secret_value = decrypt_secret(secret_value, password)
        except ValueError as e:
            # Delete the secret and metadata even if decryption fails
            vault_manager.delete_secret(secret_uuid)
            try:
                vault_manager.delete_secret(metadata_key)
            except Exception:
                pass
            return build_response(400, {
                'error': f'Decryption failed: {str(e)}'
            }, CORS_HEADERS)
    
    # Delete the secret and metadata (one-time access)
    vault_manager.delete_secret(secret_uuid)
    try:
        vault_manager.delete_secret(metadata_key)
    except Exception:
        # Metadata might not exist for old secrets
        pass
    
    # Return success response with secret value
    return build_response(200, {
        'secret': secret_value,
        'message': 'Secret retrieved and deleted successfully'
    }, CORS_HEADERS)


def _handle_check_secret(event, vault_manager):
    """Handle checking if a secret is encrypted without retrieving it."""
    secret_uuid = event.get('uuid')
    
    if not secret_uuid:
        return build_error_response(
            'Missing required field: uuid',
            headers=CORS_HEADERS
        )
    
    # Check if secret exists
    if not vault_manager.secret_exists(secret_uuid):
        return build_response(404, {
            'error': 'Secret not found or already accessed'
        }, CORS_HEADERS)
    
    # Check metadata to determine if secret is encrypted (bulletproof method)
    metadata_key = f"{secret_uuid}-metadata"
    try:
        metadata_value = vault_manager.get_secret(metadata_key)
        encrypted = (metadata_value == "encrypted")
    except Exception:
        # If metadata doesn't exist, fall back to heuristic check for backward compatibility
        secret_value = vault_manager.get_secret(secret_uuid)
        encrypted = is_encrypted(secret_value)
    
    # Return check result
    return build_response(200, {
        'encrypted': encrypted,
        'requires_password': encrypted
    }, CORS_HEADERS)


def lambda_handler(event, context):
    """
    AWS Lambda handler for secrets sharing service.
    
    Expected event format for creating a secret:
    {
        "action": "create",
        "secret": "my-secret-value",
        "password": "optional-password-for-encryption",
        "turnstile_token": "cloudflare-turnstile-token"
    }
    
    Expected event format for retrieving/deleting a secret:
    {
        "action": "retrieve",
        "uuid": "generated-uuid-here",
        "password": "password-if-encrypted",
        "turnstile_token": "cloudflare-turnstile-token"
    }
    
    Expected event format for checking if a secret is encrypted:
    {
        "action": "check",
        "uuid": "generated-uuid-here",
        "turnstile_token": "cloudflare-turnstile-token"
    }
    
    Expected event format for healthcheck:
    {
        "action": "healthcheck"
    }
    
    Or with body wrapper (from API Gateway):
    {
        "body": {
            "action": "create",
            "secret": "my-secret-value",
            "password": "optional-password-for-encryption",
            "turnstile_token": "cloudflare-turnstile-token"
        }
    }
    
    Environment variables required:
    - KEY_VAULT_NAME: Azure Key Vault name
    - AZURE_TENANT_ID
    - AZURE_CLIENT_ID
    - AZURE_CLIENT_SECRET
    - CF_SECRET_KEY: CloudFlare Turnstile secret key (bot protection is always enabled)
    
    Environment variables optional:
    - CORS_ORIGIN: CORS origin URL (default: https://secrets.merabytes.com)
    
    Password-based encryption:
    - If "password" is provided during creation, the secret will be encrypted with AES-256
    - The same password must be provided during retrieval to decrypt the secret
    - If no password is provided, the secret is stored as-is (backward compatible)
    
    Returns:
        dict: Response with statusCode and body containing operation result
    """
    # Parse event first to handle string inputs
    original_event = event
    event = parse_lambda_event(event)
    
    # Handle OPTIONS preflight request
    http_method = extract_http_method(original_event)
    if http_method == "OPTIONS":
        return build_response(200, {"message": "CORS preflight OK"}, CORS_HEADERS)
    
    # Validate required fields
    if not event:
        return build_error_response(
            'Missing event body. Expected fields: action, secret (for create), uuid (for retrieve/check)',
            headers=CORS_HEADERS
        )
    
    action = event.get('action')
    
    # Handle healthcheck action (no turnstile validation required)
    if action == 'healthcheck':
        return _handle_healthcheck()
    
    # Validate action
    if not action or action not in ['create', 'retrieve', 'check']:
        return build_error_response(
            'Invalid or missing action. Must be "create", "retrieve", "check", or "healthcheck"',
            headers=CORS_HEADERS
        )
    
    # Validate CloudFlare Turnstile token (required for create/retrieve/check)
    turnstile_token = event.get('turnstile_token')
    
    if not turnstile_token:
        return build_error_response(
            'Missing required field: turnstile_token (bot protection enabled)',
            headers=CORS_HEADERS
        )
    
    # Extract remote IP and validate turnstile
    remoteip = extract_remote_ip(original_event, context)
    
    if not validate_turnstile(turnstile_token, remoteip):
        return build_response(403, {
            'error': 'Invalid or expired Turnstile token'
        }, CORS_HEADERS)
    
    try:
        # Initialize VaultManager with Azure Key Vault
        vault_manager = VaultManager()
        
        if action == 'create':
            return _handle_create_secret(event, vault_manager)
        elif action == 'retrieve':
            return _handle_retrieve_secret(event, vault_manager)
        elif action == 'check':
            return _handle_check_secret(event, vault_manager)
        
    except Exception as e:
        # Return error response
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        return build_response(500, error_details, CORS_HEADERS)
