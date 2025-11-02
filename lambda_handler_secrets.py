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
from acido.azure_utils.VaultManager import VaultManager


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
        "turnstile_token": "optional-cloudflare-turnstile-token"
    }
    
    Expected event format for retrieving/deleting a secret:
    {
        "action": "retrieve",
        "uuid": "generated-uuid-here",
        "turnstile_token": "optional-cloudflare-turnstile-token"
    }
    
    Or with body wrapper (from API Gateway):
    {
        "body": {
            "action": "create",
            "secret": "my-secret-value",
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
            
            if not secret_value:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': 'Missing required field: secret'
                    })
                }
            
            # Generate UUID for the secret
            secret_uuid = str(uuid.uuid4())
            
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
