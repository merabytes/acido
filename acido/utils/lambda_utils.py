"""
Common utilities for AWS Lambda handlers.

This module provides reusable functions for parsing events,
building responses, and validating inputs in Lambda functions.
"""

import json


def parse_lambda_event(event):
    """
    Parse and normalize a Lambda event, handling various formats.
    
    Handles:
    - String events (parses as JSON)
    - Events with body wrapper (e.g., from API Gateway)
    - Direct event objects
    
    Args:
        event: The Lambda event (string, dict, or dict with body wrapper)
        
    Returns:
        dict: Normalized event body
    """
    # Parse string events
    if isinstance(event, str):
        event = json.loads(event)
    
    # Handle body wrapper (e.g., from API Gateway)
    if "body" in event:
        body = event.get("body", {})
        # If body is a string, parse it
        if isinstance(body, str):
            body = json.loads(body)
        return body
    
    return event


def build_response(status_code, body, headers=None):
    """
    Build a standardized Lambda response.
    
    Args:
        status_code: HTTP status code
        body: Response body (will be JSON-encoded if not a string)
        headers: Optional dict of response headers
        
    Returns:
        dict: Lambda response object with statusCode, body, and headers
    """
    response = {
        'statusCode': status_code,
        'body': json.dumps(body) if not isinstance(body, str) else body
    }
    
    if headers:
        response['headers'] = headers
    
    return response


def build_error_response(error_message, status_code=400, headers=None):
    """
    Build a standardized error response.
    
    Args:
        error_message: Error message string
        status_code: HTTP status code (default: 400)
        headers: Optional dict of response headers
        
    Returns:
        dict: Lambda error response
    """
    return build_response(status_code, {'error': error_message}, headers)


def validate_required_fields(event, required_fields):
    """
    Validate that all required fields are present in the event.
    
    Args:
        event: Parsed event dict
        required_fields: List of required field names
        
    Returns:
        tuple: (is_valid: bool, missing_fields: list)
    """
    if not event:
        return False, required_fields
    
    missing_fields = [field for field in required_fields if field not in event]
    return len(missing_fields) == 0, missing_fields


def extract_http_method(event):
    """
    Extract HTTP method from various Lambda event formats.
    
    Args:
        event: Lambda event dict
        
    Returns:
        str or None: HTTP method (e.g., 'GET', 'POST', 'OPTIONS') or None
    """
    # Check multiple possible locations for HTTP method
    if "requestContext" in event:
        # Lambda Function URL format
        if "http" in event["requestContext"]:
            return event["requestContext"]["http"].get("method")
        # API Gateway format
        elif "httpMethod" in event["requestContext"]:
            return event["requestContext"].get("httpMethod")
    
    # Direct httpMethod in event (some API Gateway formats)
    if "httpMethod" in event:
        return event.get("httpMethod")
    
    return None


def extract_remote_ip(event, context=None):
    """
    Extract remote IP address from Lambda event or context.
    
    Args:
        event: Lambda event dict
        context: Lambda context object (optional)
        
    Returns:
        str or None: Remote IP address or None if not found
    """
    # Try to get from context
    if context and hasattr(context, 'identity') and hasattr(context.identity, 'sourceIp'):
        return context.identity.sourceIp
    
    # Try to get from event
    if 'requestContext' in event and 'identity' in event['requestContext']:
        return event['requestContext']['identity'].get('sourceIp')
    
    return None
