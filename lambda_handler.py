"""
AWS Lambda handler for acido - distributed security scanning framework.

This module provides Lambda function compatibility for acido, allowing it to be
invoked via AWS Lambda with JSON payloads containing scan configurations.
"""

import json
import os
import sys
from acido.cli import Acido
from multiprocessing.pool import ThreadPool

def lambda_handler(event, context):
    """
    AWS Lambda handler for acido distributed scanning.
    
    Expected event format:
    {
        "image": "nmap",
        "targets": ["merabytes.com", "uber.com", "facebook.com"],
        "task": "nmap -iL input -p 0-1000"
    }
    
    Or with body wrapper:
    {
        "body": {
            "image": "nmap",
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
    
    Returns:
        dict: Response with statusCode and body containing fleet outputs
    """
    
    # Parse event
    if isinstance(event, str):
        event = json.loads(event)
        
    event = event.get("body", {})
    
    # If body was a string, parse it
    if isinstance(event, str):
        event = json.loads(event)
    
    # Validate required fields
    if not event:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Missing event body. Expected fields: image, targets, task'
            })
        }
    
    required_fields = ['image', 'targets', 'task']
    missing_fields = [field for field in required_fields if field not in event]
    
    if missing_fields:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            })
        }
    
    # Extract parameters
    image_name = event.get('image')
    targets = event.get('targets', [])
    task = event.get('task')
    fleet_name = event.get('fleet_name', 'lambda-fleet')
    num_instances = event.get('num_instances', len(targets) if targets else 1)
    
    # Validate targets
    if not targets or not isinstance(targets, list):
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'targets must be a non-empty list'
            })
        }
    
    try:
        # Create temporary input file with targets
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            input_file = f.name
            f.write('\n'.join(targets))
        
        # Initialize acido with environment-based configuration
        # The Acido class will automatically load from environment variables
        acido = Acido(check_config=True)
        
        # Create thread pool for fleet operations
        pool = ThreadPool(processes=30)
        
        # Make pool available globally for the fleet operation
        import acido.cli as cli_module
        cli_module.pool = pool
        
        # Build full image URL
        full_image_url = acido.build_image_url(image_name)
        
        # Execute fleet operation
        response, outputs = acido.fleet(
            fleet_name=fleet_name,
            instance_num=num_instances,
            image_name=full_image_url,
            scan_cmd=task,
            input_file=input_file,
            wait=None,
            write_to_file=None,
            output_format='json',
            interactive=False,
            quiet=True
        )
        
        # Clean up temporary input file
        try:
            os.unlink(input_file)
        except:
            pass
        
        # Clean up containers if requested
        if event.get('rm_when_done', True):
            acido.rm(fleet_name if num_instances <= 10 else f'{fleet_name}*')
        
        # Return successful response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'fleet_name': fleet_name,
                'instances': num_instances,
                'image': image_name,
                'outputs': outputs
            })
        }
        
    except Exception as e:
        # Return error response
        import traceback
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        
        return {
            'statusCode': 500,
            'body': json.dumps(error_details)
        }
