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

# Valid operation types
VALID_OPERATIONS = ['fleet', 'run', 'ls', 'rm', 'ip_create', 'ip_ls', 'ip_rm']

def _validate_targets(targets):
    """Validate targets parameter."""
    return targets and isinstance(targets, list)


def _normalize_regions(event):
    """
    Normalize regions parameter from event.
    
    Supports both 'regions' (list) and 'region' (string) for backward compatibility.
    Converts strings to lists and handles None/missing values.
    
    Args:
        event: Lambda event dictionary
        
    Returns:
        list: List of regions (defaults to ['westeurope'] if not specified)
    """
    # Try 'regions' first (new format), then fall back to 'region' (old format)
    regions = event.get('regions', event.get('region', None))
    
    if regions is None:
        return ['westeurope']
    elif isinstance(regions, str):
        return [regions]
    else:
        return regions


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


def _execute_fleet(acido, fleet_name, num_instances, image_name, task, input_file, regions=None):
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
        pool=pool,
        regions=regions
    )


def _execute_run(acido, name, image_name, task, duration, cleanup, regions=None):
    """Execute run operation (single ephemeral instance) and return response and outputs."""
    full_image_url = acido.build_image_url(image_name)
    
    return acido.run(
        name=name,
        image_name=full_image_url,
        task=task,
        duration=duration,
        write_to_file=None,
        output_format='json',
        quiet=True,
        cleanup=cleanup,
        regions=regions
    )


def _execute_ls(acido):
    """Execute ls operation to list all container instances."""
    all_instances, instances_named = acido.ls(interactive=False)
    
    # Format the response
    instances_list = []
    for cg_name, containers in instances_named.items():
        instances_list.append({
            'container_group': cg_name,
            'containers': containers
        })
    
    return instances_list


def _execute_rm(acido, name):
    """Execute rm operation to remove container instances."""
    acido.rm(name)
    return {'removed': name}


def _execute_ip_create(acido, name):
    """Execute ip_create operation to create IPv4 address and network profile."""
    acido.create_ipv4_address(name)
    return {'created': name}


def _execute_ip_ls(acido):
    """Execute ip_ls operation to list all IPv4 addresses."""
    ip_addresses_info = acido.ls_ip(interactive=False)
    return ip_addresses_info if ip_addresses_info else []


def _execute_ip_rm(acido, name):
    """Execute ip_rm operation to remove IPv4 address and network profile."""
    success = acido.rm_ip(name)
    return {'removed': name, 'success': success}


def lambda_handler(event, context):
    """
    AWS Lambda handler for acido distributed scanning and ephemeral runners.
    
    Supports seven operations:
    
    1. Fleet operation (default) - Multiple container instances for distributed scanning:
    {
        "operation": "fleet",  // optional, default is fleet
        "image": "kali-rolling",
        "targets": ["merabytes.com", "uber.com", "facebook.com"],
        "task": "nmap -iL input -p 0-1000",
        "regions": ["westeurope", "eastus", "westus2"]  // optional, can be single region string or list
    }
    
    2. Run operation - Single ephemeral instance with auto-cleanup (e.g., for GitHub runners):
    {
        "operation": "run",
        "name": "github-runner-01",
        "image": "github-runner",
        "task": "./run.sh",
        "duration": 900,  // optional, default 900s (15min)
        "cleanup": true,  // optional, default true
        "regions": ["westeurope", "eastus"]  // optional, can be single region string or list
    }
    
    3. List operation - List all container instances:
    {
        "operation": "ls"
    }
    
    4. Remove operation - Remove container instances:
    {
        "operation": "rm",
        "name": "container-group-name"  // can use wildcards like "fleet*"
    }
    
    5. IP Create operation - Create IPv4 address and network profile:
    {
        "operation": "ip_create",
        "name": "pentest-ip"
    }
    
    6. IP List operation - List all IPv4 addresses:
    {
        "operation": "ip_ls"
    }
    
    7. IP Remove operation - Remove IPv4 address and network profile:
    {
        "operation": "ip_rm",
        "name": "pentest-ip"
    }
    
    Or with body wrapper:
    {
        "body": {
            "operation": "run",
            "name": "github-runner-01",
            ...
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
        dict: Response with statusCode and body containing outputs
    """
    # Parse event
    event = parse_lambda_event(event)
    
    # Validate event body exists
    if not event:
        return build_error_response(
            'Missing event body'
        )
    
    # Determine operation type (default to 'fleet' for backward compatibility)
    operation = event.get('operation', 'fleet')
    
    if operation not in VALID_OPERATIONS:
        return build_error_response(
            f'Invalid operation: {operation}. Must be one of: {", ".join(VALID_OPERATIONS)}'
        )
    
    # Validate required fields based on operation type before initializing Acido
    if operation == 'run':
        required_fields = ['image', 'name', 'task']
        is_valid, missing_fields = validate_required_fields(event, required_fields)
        
        if not is_valid:
            return build_error_response(
                f'Missing required fields for run operation: {", ".join(missing_fields)}'
            )
    elif operation == 'rm':
        # rm operation requires 'name' field
        required_fields = ['name']
        is_valid, missing_fields = validate_required_fields(event, required_fields)
        
        if not is_valid:
            return build_error_response(
                f'Missing required fields for rm operation: {", ".join(missing_fields)}'
            )
    elif operation == 'ls':
        # ls operation doesn't require any additional fields
        pass
    elif operation == 'ip_create':
        # ip_create operation requires 'name' field
        required_fields = ['name']
        is_valid, missing_fields = validate_required_fields(event, required_fields)
        
        if not is_valid:
            return build_error_response(
                f'Missing required fields for ip_create operation: {", ".join(missing_fields)}'
            )
    elif operation == 'ip_ls':
        # ip_ls operation doesn't require any additional fields
        pass
    elif operation == 'ip_rm':
        # ip_rm operation requires 'name' field
        required_fields = ['name']
        is_valid, missing_fields = validate_required_fields(event, required_fields)
        
        if not is_valid:
            return build_error_response(
                f'Missing required fields for ip_rm operation: {", ".join(missing_fields)}'
            )
    else:  # operation == 'fleet'
        required_fields = ['image', 'targets', 'task']
        is_valid, missing_fields = validate_required_fields(event, required_fields)
        
        if not is_valid:
            return build_error_response(
                f'Missing required fields for fleet operation: {", ".join(missing_fields)}'
            )
        
        # Validate targets for fleet operation
        targets = event.get('targets', [])
        if not _validate_targets(targets):
            return build_error_response('targets must be a non-empty list')
    
    # Validate and execute based on operation type
    try:
        # Initialize acido with environment-based configuration
        acido = Acido(check_config=True)
        
        if operation == 'run':
            # Run operation: single ephemeral instance
            # Extract parameters for run operation
            name = event.get('name')
            image_name = event.get('image')
            task = event.get('task')
            duration = event.get('duration', 900)  # Default 15 minutes
            cleanup = event.get('cleanup', True)  # Default to auto-cleanup
            regions = _normalize_regions(event)
            
            # Execute run operation
            response, outputs = _execute_run(
                acido, name, image_name, task, duration, cleanup, regions
            )
            
            # Return successful response
            return build_response(200, {
                'operation': 'run',
                'name': name,
                'image': image_name,
                'duration': duration,
                'cleanup': cleanup,
                'regions': regions,
                'outputs': outputs
            })
        
        elif operation == 'ls':
            # List operation: list all container instances
            instances_list = _execute_ls(acido)
            
            # Return successful response
            return build_response(200, {
                'operation': 'ls',
                'instances': instances_list
            })
        
        elif operation == 'rm':
            # Remove operation: remove container instances
            name = event.get('name')
            result = _execute_rm(acido, name)
            
            # Return successful response
            return build_response(200, {
                'operation': 'rm',
                'result': result
            })
        
        elif operation == 'ip_create':
            # IP Create operation: create IPv4 address and network profile
            name = event.get('name')
            result = _execute_ip_create(acido, name)
            
            # Return successful response
            return build_response(200, {
                'operation': 'ip_create',
                'result': result
            })
        
        elif operation == 'ip_ls':
            # IP List operation: list all IPv4 addresses
            ip_addresses = _execute_ip_ls(acido)
            
            # Return successful response
            return build_response(200, {
                'operation': 'ip_ls',
                'ip_addresses': ip_addresses
            })
        
        elif operation == 'ip_rm':
            # IP Remove operation: remove IPv4 address and network profile
            name = event.get('name')
            result = _execute_ip_rm(acido, name)
            
            # Return successful response
            return build_response(200, {
                'operation': 'ip_rm',
                'result': result
            })
            
        else:  # operation == 'fleet'
            # Fleet operation: multiple instances for distributed scanning
            # Extract parameters for fleet operation
            image_name = event.get('image')
            targets = event.get('targets', [])
            task = event.get('task')
            fleet_name = event.get('fleet_name', 'lambda-fleet')
            num_instances = event.get('num_instances', len(targets) if targets else 1)
            regions = _normalize_regions(event)
            
            # Create temporary input file with targets
            input_file = _create_input_file(targets)
            
            # Execute fleet operation
            response, outputs = _execute_fleet(
                acido, fleet_name, num_instances, image_name, task, input_file, regions
            )
            
            # Clean up temporary input file
            _cleanup_file(input_file)
            
            # Clean up containers if requested
            if event.get('rm_when_done', True):
                acido.rm(fleet_name if num_instances <= 10 else f'{fleet_name}*')
            
            # Return successful response
            return build_response(200, {
                'operation': 'fleet',
                'fleet_name': fleet_name,
                'instances': num_instances,
                'image': image_name,
                'regions': regions,
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
