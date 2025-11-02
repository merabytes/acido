"""
AWS Lambda handler for acido - distributed security scanning framework.

This module provides Lambda function compatibility for acido, allowing it to be
invoked via AWS Lambda with JSON payloads containing scan configurations.
"""

import os
import tempfile
import traceback
from acido.cli import Acido
from acido.utils.lambda_safe_pool import ThreadPoolShim
from acido.utils.lambda_utils import (
    parse_lambda_event,
    build_response,
    build_error_response,
    validate_required_fields
)

def _validate_targets(targets):
    """Validate targets parameter."""
    return targets and isinstance(targets, list)


def _create_input_file(targets):
    """Create temporary input file with targets."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write('\n'.join(targets))
        return f.name


def _cleanup_file(filepath):
    """Clean up temporary file, ignoring errors."""
    try:
        os.unlink(filepath)
    except (OSError, FileNotFoundError):
        pass


def _execute_fleet(acido, fleet_name, num_instances, image_name, task, input_file):
    """Execute fleet operation and return response and outputs."""
    pool = ThreadPoolShim(processes=30)
    full_image_url = acido.build_image_url(image_name)
    
    return acido.fleet(
        fleet_name=fleet_name,
        instance_num=num_instances,
        image_name=full_image_url,
        scan_cmd=task,
        input_file=input_file,
        wait=None,
        write_to_file=None,
        output_format='json',
        interactive=False,
        quiet=True,
        pool=pool
    )


def lambda_handler(event, context):
    """
    AWS Lambda handler for acido distributed scanning.
    
    Expected event format:
    {
        "image": "kali-rolling",
        "targets": ["merabytes.com", "uber.com", "facebook.com"],
        "task": "nmap -iL input -p 0-1000"
    }
    
    Or with body wrapper:
    {
        "body": {
            "image": "kali-rolling",
            "targets": ["merabytes.com", "uber.com", "facebook.com"],
            "task": "nmap -iL input -p 0-1000"
        }
    }
    
    Environment variables required:
    - AZURE_TENANT_ID
    - AZURE_CLIENT_ID
    - AZURE_CLIENT_SECRET
    - AZURE_RESOURCE_GROUP
    - IMAGE_REGISTRY_SERVER
    - IMAGE_REGISTRY_USERNAME
    - IMAGE_REGISTRY_PASSWORD
    - STORAGE_ACCOUNT_NAME
    - STORAGE_ACCOUNT_KEY (optional, if not provided will use Azure SDK to fetch)
    - MANAGED_IDENTITY_ID (optional, user-assigned managed identity resource ID)
    - MANAGED_IDENTITY_CLIENT_ID (optional, user-assigned managed identity client ID)
    
    Returns:
        dict: Response with statusCode and body containing fleet outputs
    """
    # Parse event
    event = parse_lambda_event(event)
    
    # Validate event body exists
    if not event:
        return build_error_response(
            'Missing event body. Expected fields: image, targets, task'
        )
    
    # Validate required fields
    required_fields = ['image', 'targets', 'task']
    is_valid, missing_fields = validate_required_fields(event, required_fields)
    
    if not is_valid:
        return build_error_response(
            f'Missing required fields: {", ".join(missing_fields)}'
        )
    
    # Extract parameters
    image_name = event.get('image')
    targets = event.get('targets', [])
    task = event.get('task')
    fleet_name = event.get('fleet_name', 'lambda-fleet')
    num_instances = event.get('num_instances', len(targets) if targets else 1)
    
    # Validate targets
    if not _validate_targets(targets):
        return build_error_response('targets must be a non-empty list')
    
    try:
        # Create temporary input file with targets
        input_file = _create_input_file(targets)
        
        # Initialize acido with environment-based configuration
        acido = Acido(check_config=True)
        
        # Execute fleet operation
        response, outputs = _execute_fleet(
            acido, fleet_name, num_instances, image_name, task, input_file
        )
        
        # Clean up temporary input file
        _cleanup_file(input_file)
        
        # Clean up containers if requested
        if event.get('rm_when_done', True):
            acido.rm(fleet_name if num_instances <= 10 else f'{fleet_name}*')
        
        # Return successful response
        return build_response(200, {
            'fleet_name': fleet_name,
            'instances': num_instances,
            'image': image_name,
            'outputs': outputs
        })
        
    except Exception as e:
        # Return error response
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        return build_response(500, error_details)
