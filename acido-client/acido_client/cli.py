"""
Command-line interface for acido-client.

Provides a CLI for interacting with acido Lambda functions via REST API.
"""

import sys
import json
import argparse
from typing import Optional, List
from .client import AcidoClient, AcidoClientError
from . import __version__


def format_output(data: dict, pretty: bool = True) -> str:
    """
    Format output data as JSON.
    
    Args:
        data: Data to format
        pretty: Whether to use pretty printing (default: True)
        
    Returns:
        JSON string
    """
    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser for CLI.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='REST API client for acido Lambda functions',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'acido-client {__version__}'
    )
    
    parser.add_argument(
        '--lambda-url',
        help='Lambda function URL (default: from LAMBDA_FUNCTION_URL env var)',
        default=None
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Request timeout in seconds (default: 300)'
    )
    
    parser.add_argument(
        '--no-pretty',
        action='store_true',
        help='Disable pretty-printing of JSON output'
    )
    
    # Create subparsers for operations
    subparsers = parser.add_subparsers(dest='operation', help='Operation to perform')
    
    # Fleet operation
    fleet_parser = subparsers.add_parser(
        'fleet',
        help='Deploy multiple container instances for distributed scanning'
    )
    fleet_parser.add_argument(
        '--image',
        required=True,
        help='Container image name (e.g., kali-rolling)'
    )
    fleet_parser.add_argument(
        '--targets',
        nargs='+',
        required=True,
        help='List of target domains/IPs to scan'
    )
    fleet_parser.add_argument(
        '--task',
        required=True,
        help='Command to execute (use "input" as placeholder for targets file)'
    )
    fleet_parser.add_argument(
        '--fleet-name',
        default='lambda-fleet',
        help='Fleet name (default: lambda-fleet)'
    )
    fleet_parser.add_argument(
        '--num-instances',
        type=int,
        help='Number of instances (default: number of targets)'
    )
    fleet_parser.add_argument(
        '--region',
        default='westeurope',
        help='Azure region (default: westeurope)'
    )
    fleet_parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Disable auto-cleanup after completion'
    )
    
    # Run operation
    run_parser = subparsers.add_parser(
        'run',
        help='Deploy single ephemeral instance with auto-cleanup'
    )
    run_parser.add_argument(
        '--name',
        required=True,
        help='Instance name'
    )
    run_parser.add_argument(
        '--image',
        required=True,
        help='Container image name (e.g., github-runner)'
    )
    run_parser.add_argument(
        '--task',
        required=True,
        help='Command to execute (e.g., ./run.sh)'
    )
    run_parser.add_argument(
        '--duration',
        type=int,
        default=900,
        help='Maximum runtime in seconds (default: 900)'
    )
    run_parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Disable auto-cleanup after completion'
    )
    run_parser.add_argument(
        '--region',
        default='westeurope',
        help='Azure region (default: westeurope)'
    )
    
    # List operation
    subparsers.add_parser(
        'ls',
        help='List all container instances'
    )
    
    # Remove operation
    rm_parser = subparsers.add_parser(
        'rm',
        help='Remove container instances'
    )
    rm_parser.add_argument(
        '--name',
        required=True,
        help='Instance name or pattern (supports wildcards like "fleet*")'
    )
    
    # IP Create operation
    ip_create_parser = subparsers.add_parser(
        'ip-create',
        help='Create IPv4 address and network profile'
    )
    ip_create_parser.add_argument(
        '--name',
        required=True,
        help='Name for the IPv4 address resource'
    )
    
    # IP List operation
    subparsers.add_parser(
        'ip-ls',
        help='List all IPv4 addresses'
    )
    
    # IP Remove operation
    ip_rm_parser = subparsers.add_parser(
        'ip-rm',
        help='Remove IPv4 address and network profile'
    )
    ip_rm_parser.add_argument(
        '--name',
        required=True,
        help='Name of the IPv4 address resource to remove'
    )
    
    return parser


def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Check if operation was specified
    if not args.operation:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Initialize client
        client = AcidoClient(
            lambda_url=args.lambda_url,
            timeout=args.timeout
        )
        
        # Execute operation
        result = None
        
        if args.operation == 'fleet':
            result = client.fleet(
                image=args.image,
                targets=args.targets,
                task=args.task,
                fleet_name=args.fleet_name,
                num_instances=args.num_instances,
                region=args.region,
                rm_when_done=not args.no_cleanup
            )
        
        elif args.operation == 'run':
            result = client.run(
                name=args.name,
                image=args.image,
                task=args.task,
                duration=args.duration,
                cleanup=not args.no_cleanup,
                region=args.region
            )
        
        elif args.operation == 'ls':
            result = client.ls()
        
        elif args.operation == 'rm':
            result = client.rm(name=args.name)
        
        elif args.operation == 'ip-create':
            result = client.ip_create(name=args.name)
        
        elif args.operation == 'ip-ls':
            result = client.ip_ls()
        
        elif args.operation == 'ip-rm':
            result = client.ip_rm(name=args.name)
        
        else:
            print(f"Unknown operation: {args.operation}", file=sys.stderr)
            sys.exit(1)
        
        # Print result
        print(format_output(result, pretty=not args.no_pretty))
        sys.exit(0)
        
    except AcidoClientError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
