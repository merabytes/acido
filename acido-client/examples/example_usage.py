#!/usr/bin/env python3
"""
Example usage of acido-client Python API.

This script demonstrates how to use the AcidoClient class to interact with
acido Lambda functions.
"""

import os
from acido_client import AcidoClient, AcidoClientError


def main():
    """Main example function."""
    # Get Lambda URL from environment
    lambda_url = os.environ.get('LAMBDA_FUNCTION_URL')
    if not lambda_url:
        print("Error: LAMBDA_FUNCTION_URL environment variable is not set")
        print("Please set it to your Lambda function URL:")
        print("  export LAMBDA_FUNCTION_URL='https://your-lambda-url.lambda-url.region.on.aws/'")
        return 1
    
    # Initialize client
    print(f"Connecting to Lambda at: {lambda_url}")
    client = AcidoClient(lambda_url=lambda_url)
    
    try:
        # Example 1: List container instances
        print("\n=== Example 1: List Container Instances ===")
        response = client.ls()
        print(f"Response: {response}")
        
        # Example 2: Fleet operation (commented out to avoid actually creating instances)
        print("\n=== Example 2: Fleet Operation (example only) ===")
        print("To run a fleet operation, you would call:")
        print("""
        response = client.fleet(
            image="kali-rolling",
            targets=["merabytes.com", "uber.com"],
            task="nmap -iL input -p 0-1000",
            fleet_name="example-fleet",
            region="westeurope"
        )
        """)
        
        # Example 3: Run operation (commented out to avoid actually creating instances)
        print("\n=== Example 3: Run Operation (example only) ===")
        print("To run a single ephemeral instance, you would call:")
        print("""
        response = client.run(
            name="github-runner-01",
            image="github-runner",
            task="./run.sh",
            duration=900,
            cleanup=True,
            region="westeurope"
        )
        """)
        
        # Example 4: IP List operation
        print("\n=== Example 4: List IPv4 Addresses ===")
        response = client.ip_ls()
        print(f"Response: {response}")
        
        # Example 5: Using context manager
        print("\n=== Example 5: Using Context Manager ===")
        with AcidoClient(lambda_url=lambda_url) as ctx_client:
            response = ctx_client.ls()
            print(f"Response: {response}")
        
        print("\n=== All examples completed successfully! ===")
        return 0
        
    except AcidoClientError as e:
        print(f"\nError: {e}")
        return 1
    finally:
        client.close()


if __name__ == '__main__':
    exit(main())
