"""
CloudFlare Turnstile validation utilities.

Provides bot protection through CloudFlare Turnstile token validation.
"""

import os
import requests


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
