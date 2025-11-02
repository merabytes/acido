"""
AWS Lambda handler for acido secrets sharing service.

This module provides a OneTimeSecret-like service where secrets can be:
- Created with a generated UUID
- Retrieved and deleted (one-time access)

The service uses Azure KeyVault for secure secret storage.
Optional CloudFlare Turnstile support for bot protection.
"""

import json
import os
import traceback
import uuid
import requests
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from acido.azure_utils.VaultManager import VaultManager


def encrypt_secret(secret_value: str, password: str) -> str:
    """
    Encrypt a secret using AES-256 with a password.
    
    Args:
        secret_value: The secret to encrypt
        password: The password to use for encryption
        
    Returns:
        str: Base64-encoded encrypted secret with IV prepended
    """
    # Derive a 256-bit key from the password using SHA-256
    key = hashlib.sha256(password.encode()).digest()
    
    # Generate a random 128-bit IV
    iv = os.urandom(16)
    
    # Create cipher and encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad the secret to be a multiple of 16 bytes (AES block size)
    secret_bytes = secret_value.encode()
    padding_length = 16 - (len(secret_bytes) % 16)
    padded_secret = secret_bytes + bytes([padding_length] * padding_length)
    
    # Encrypt the padded secret
    encrypted = encryptor.update(padded_secret) + encryptor.finalize()
    
    # Prepend IV to encrypted data and encode as base64
    return base64.b64encode(iv + encrypted).decode()


def decrypt_secret(encrypted_value: str, password: str) -> str:
    """
    Decrypt a secret using AES-256 with a password.
    
    Args:
        encrypted_value: Base64-encoded encrypted secret with IV prepended
        password: The password to use for decryption
        
    Returns:
        str: Decrypted secret
        
    Raises:
        ValueError: If decryption fails (wrong password or corrupted data)
    """
    try:
        # Derive the same 256-bit key from the password
        key = hashlib.sha256(password.encode()).digest()
        
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_value.encode())
        
        # Extract IV (first 16 bytes) and ciphertext
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        # Create cipher and decrypt
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # Decrypt
        padded_secret = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Validate and remove padding
        padding_length = padded_secret[-1]
        
        # Validate padding (PKCS7)
        if padding_length > 16 or padding_length == 0:
            raise ValueError("Invalid padding - likely wrong password")
        
        # Check that all padding bytes are the same
        for i in range(padding_length):
            if padded_secret[-(i+1)] != padding_length:
                raise ValueError("Invalid padding - likely wrong password")
        
        secret_bytes = padded_secret[:-padding_length]
        
        # Attempt to decode as UTF-8 to further validate
        return secret_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError("Decryption failed. Invalid password or corrupted data")
    except Exception as e:
        raise ValueError(f"Decryption failed. Invalid password or corrupted data: {str(e)}")


def validate_turnstile(token, remoteip=None) -> bool:
    """
    Validate CloudFlare Turnstile token.
    
    Args:
        token: The Turnstile response token from the client
        remoteip: Optional remote IP address of the client
        
    Returns:
        bool: True if validation succeeds, False otherwise
    """
    secret = os.environ.get('CF_SECRET_KEY')
    if not secret:
        # If CF_SECRET_KEY is not set, skip validation
        return True
    
    data = {'secret': secret, 'response': token}
    if remoteip:
        data['remoteip'] = remoteip
    
    try:
        response = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data)
        result = response.json()
        return result.get("success", False)
    except Exception:
        # If validation fails due to network or other issues, reject
        return False


def lambda_handler(event, context):
    """
    AWS Lambda handler for secrets sharing service.
    
    Expected event format for creating a secret:
    {
        "action": "create",
        "secret": "my-secret-value",
        "password": "optional-password-for-encryption",
        "turnstile_token": "optional-cloudflare-turnstile-token"
    }
    
    Expected event format for retrieving/deleting a secret:
    {
        "action": "retrieve",
        "uuid": "generated-uuid-here",
        "password": "password-if-encrypted",
        "turnstile_token": "optional-cloudflare-turnstile-token"
    }
    
    Or with body wrapper (from API Gateway):
    {
        "body": {
            "action": "create",
            "secret": "my-secret-value",
            "password": "optional-password-for-encryption",
            "turnstile_token": "optional-cloudflare-turnstile-token"
        }
    }
    
    Environment variables required:
    - KEY_VAULT_NAME: Azure Key Vault name
    - AZURE_TENANT_ID
    - AZURE_CLIENT_ID
    - AZURE_CLIENT_SECRET
    
    Environment variables optional:
    - CF_SECRET_KEY: CloudFlare Turnstile secret key (enables bot protection)
    
    Password-based encryption:
    - If "password" is provided during creation, the secret will be encrypted with AES-256
    - The same password must be provided during retrieval to decrypt the secret
    - If no password is provided, the secret is stored as-is (backward compatible)
    
    Returns:
        dict: Response with statusCode and body containing operation result
    """
    
    # Parse event
    if isinstance(event, str):
        event = json.loads(event)
    
    # Handle body wrapper (e.g., from API Gateway)
    if "body" in event:
        event = event.get("body", {})
        if isinstance(event, str):
            event = json.loads(event)
    
    # Validate required fields
    if not event:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Missing event body. Expected fields: action, secret (for create) or uuid (for retrieve)'
            })
        }
    
    action = event.get('action')
    
    if not action or action not in ['create', 'retrieve']:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid or missing action. Must be either "create" or "retrieve"'
            })
        }
    
    # Validate CloudFlare Turnstile token if CF_SECRET_KEY is set
    if os.environ.get('CF_SECRET_KEY'):
        turnstile_token = event.get('turnstile_token')
        
        if not turnstile_token:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required field: turnstile_token (bot protection enabled)'
                })
            }
        
        # Extract remote IP from context or event
        remoteip = None
        if context and hasattr(context, 'identity') and hasattr(context.identity, 'sourceIp'):
            remoteip = context.identity.sourceIp
        elif 'requestContext' in event and 'identity' in event['requestContext']:
            remoteip = event['requestContext']['identity'].get('sourceIp')
        
        if not validate_turnstile(turnstile_token, remoteip):
            return {
                'statusCode': 403,
                'body': json.dumps({
                    'error': 'Invalid or expired Turnstile token'
                })
            }
    
    try:
        # Initialize VaultManager with Azure Key Vault
        vault_manager = VaultManager()
        
        if action == 'create':
            # Create a new secret
            secret_value = event.get('secret')
            password = event.get('password')  # Optional password for encryption
            
            if not secret_value:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing required field: secret'
                    })
                }
            
            # Generate UUID for the secret
            secret_uuid = str(uuid.uuid4())
            
            # Encrypt secret if password is provided
            if password:
                try:
                    secret_value = encrypt_secret(secret_value, password)
                except Exception as e:
                    return {
                        'statusCode': 500,
                        'body': json.dumps({
                            'error': f'Encryption failed: {str(e)}'
                        })
                    }
            
            # Store secret in Key Vault
            vault_manager.set_secret(secret_uuid, secret_value)
            
            # Return success response with UUID
            return {
                'statusCode': 201,
                'body': json.dumps({
                    'uuid': secret_uuid,
                    'message': 'Secret created successfully'
                })
            }
        
        elif action == 'retrieve':
            # Retrieve and delete a secret (one-time access)
            secret_uuid = event.get('uuid')
            password = event.get('password')  # Optional password for decryption
            
            if not secret_uuid:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing required field: uuid'
                    })
                }
            
            # Check if secret exists
            if not vault_manager.secret_exists(secret_uuid):
                return {
                    'statusCode': 404,
                    'body': json.dumps({
                        'error': 'Secret not found or already accessed'
                    })
                }
            
            # Retrieve the secret value
            secret_value = vault_manager.get_secret(secret_uuid)
            
            # Decrypt secret if password is provided
            if password:
                try:
                    secret_value = decrypt_secret(secret_value, password)
                except ValueError as e:
                    # Delete the secret even if decryption fails
                    vault_manager.delete_secret(secret_uuid)
                    return {
                        'statusCode': 400,
                        'body': json.dumps({
                            'error': f'Decryption failed: {str(e)}'
                        })
                    }
            
            # Delete the secret (one-time access)
            vault_manager.delete_secret(secret_uuid)
            
            # Return success response with secret value
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'secret': secret_value,
                    'message': 'Secret retrieved and deleted successfully'
                })
            }
        
    except Exception as e:
        # Return error response
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return {
            'statusCode': 500,
            'body': json.dumps(error_details)
        }
