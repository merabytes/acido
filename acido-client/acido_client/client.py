"""
REST API client for acido Lambda functions.

This module provides the AcidoClient class for interacting with acido Lambda functions
via HTTP requests, supporting all lambda_handler operations.
"""

import os
import json
import requests
from typing import Optional, List, Dict, Any


class AcidoClientError(Exception):
    """Base exception for AcidoClient errors."""
    pass


class AcidoClient:
    """
    REST API client for acido Lambda functions.
    
    Provides methods to interact with all supported lambda_handler operations:
    - fleet: Deploy multiple container instances for distributed scanning
    - run: Deploy single ephemeral instance with auto-cleanup
    - ls: List all container instances
    - rm: Remove container instances
    - ip_create: Create IPv4 address and network profile
    - ip_ls: List all IPv4 addresses
    - ip_rm: Remove IPv4 address and network profile
    
    Args:
        lambda_url: URL of the Lambda function. If not provided, reads from
                   LAMBDA_FUNCTION_URL environment variable.
        timeout: Request timeout in seconds (default: 300)
    
    Raises:
        AcidoClientError: If lambda_url is not provided and LAMBDA_FUNCTION_URL
                         environment variable is not set.
    
    Example:
        >>> client = AcidoClient()
        >>> response = client.fleet(
        ...     image="kali-rolling",
        ...     targets=["merabytes.com"],
        ...     task="nmap -iL input -p 0-1000"
        ... )
    """
    
    def __init__(self, lambda_url: Optional[str] = None, timeout: int = 300):
        """
        Initialize AcidoClient.
        
        Args:
            lambda_url: URL of the Lambda function. If not provided, reads from
                       LAMBDA_FUNCTION_URL environment variable.
            timeout: Request timeout in seconds (default: 300)
        """
        self.lambda_url = lambda_url or os.environ.get('LAMBDA_FUNCTION_URL')
        if not self.lambda_url:
            raise AcidoClientError(
                "lambda_url must be provided or LAMBDA_FUNCTION_URL environment "
                "variable must be set"
            )
        
        # Ensure URL ends with /
        if not self.lambda_url.endswith('/'):
            self.lambda_url += '/'
        
        self.timeout = timeout
        self.session = requests.Session()
    
    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP POST request to Lambda function.
        
        Args:
            payload: Request payload dictionary
            
        Returns:
            Response body as dictionary
            
        Raises:
            AcidoClientError: If request fails or returns error status
        """
        try:
            response = self.session.post(
                self.lambda_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Check for error in response body
            if isinstance(result, dict):
                status_code = result.get('statusCode', 200)
                if status_code >= 400:
                    body = result.get('body', {})
                    if isinstance(body, str):
                        body = json.loads(body)
                    error_msg = body.get('error', 'Unknown error')
                    raise AcidoClientError(
                        f"Lambda function returned error (status {status_code}): {error_msg}"
                    )
                
                # Extract body if present
                body = result.get('body')
                if body:
                    if isinstance(body, str):
                        return json.loads(body)
                    return body
                return result
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise AcidoClientError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise AcidoClientError(f"Failed to parse response: {str(e)}")
    
    def fleet(
        self,
        image: str,
        targets: List[str],
        task: str,
        fleet_name: str = "lambda-fleet",
        num_instances: Optional[int] = None,
        region: str = "westeurope",
        rm_when_done: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy multiple container instances for distributed scanning.
        
        Args:
            image: Container image name (e.g., "kali-rolling")
            targets: List of target domains/IPs to scan
            task: Command to execute (use 'input' as placeholder for targets file)
            fleet_name: Name for the fleet (default: "lambda-fleet")
            num_instances: Number of instances to deploy (default: len(targets))
            region: Azure region (default: "westeurope")
            rm_when_done: Auto-cleanup after completion (default: True)
            
        Returns:
            Response dictionary with operation results
            
        Example:
            >>> response = client.fleet(
            ...     image="kali-rolling",
            ...     targets=["merabytes.com", "uber.com"],
            ...     task="nmap -iL input -p 0-1000"
            ... )
        """
        payload = {
            "operation": "fleet",
            "image": image,
            "targets": targets,
            "task": task,
            "fleet_name": fleet_name,
            "region": region,
            "rm_when_done": rm_when_done
        }
        
        if num_instances is not None:
            payload["num_instances"] = num_instances
        
        return self._make_request(payload)
    
    def run(
        self,
        name: str,
        image: str,
        task: str,
        duration: int = 900,
        cleanup: bool = True,
        region: str = "westeurope"
    ) -> Dict[str, Any]:
        """
        Deploy single ephemeral instance with auto-cleanup.
        
        Useful for GitHub runners or other temporary workloads.
        
        Args:
            name: Instance name
            image: Container image name (e.g., "github-runner")
            task: Command to execute (e.g., "./run.sh")
            duration: Maximum runtime in seconds (default: 900 = 15 minutes)
            cleanup: Auto-cleanup after completion (default: True)
            region: Azure region (default: "westeurope")
            
        Returns:
            Response dictionary with operation results
            
        Example:
            >>> response = client.run(
            ...     name="github-runner-01",
            ...     image="github-runner",
            ...     task="./run.sh",
            ...     duration=900
            ... )
        """
        payload = {
            "operation": "run",
            "name": name,
            "image": image,
            "task": task,
            "duration": duration,
            "cleanup": cleanup,
            "region": region
        }
        
        return self._make_request(payload)
    
    def ls(self) -> Dict[str, Any]:
        """
        List all container instances.
        
        Returns:
            Response dictionary with list of instances
            
        Example:
            >>> response = client.ls()
            >>> for instance in response.get('instances', []):
            ...     print(instance['container_group'])
        """
        payload = {
            "operation": "ls"
        }
        
        return self._make_request(payload)
    
    def rm(self, name: str) -> Dict[str, Any]:
        """
        Remove container instances.
        
        Supports wildcards (e.g., "fleet*" to remove all instances starting with "fleet").
        
        Args:
            name: Instance name or pattern (supports wildcards)
            
        Returns:
            Response dictionary with removal result
            
        Example:
            >>> response = client.rm(name="fleet*")
        """
        payload = {
            "operation": "rm",
            "name": name
        }
        
        return self._make_request(payload)
    
    def ip_create(self, name: str) -> Dict[str, Any]:
        """
        Create IPv4 address and network profile.
        
        Args:
            name: Name for the IPv4 address resource
            
        Returns:
            Response dictionary with creation result
            
        Example:
            >>> response = client.ip_create(name="pentest-ip")
        """
        payload = {
            "operation": "ip_create",
            "name": name
        }
        
        return self._make_request(payload)
    
    def ip_ls(self) -> Dict[str, Any]:
        """
        List all IPv4 addresses.
        
        Returns:
            Response dictionary with list of IPv4 addresses
            
        Example:
            >>> response = client.ip_ls()
            >>> for ip_info in response.get('ip_addresses', []):
            ...     print(ip_info)
        """
        payload = {
            "operation": "ip_ls"
        }
        
        return self._make_request(payload)
    
    def ip_rm(self, name: str) -> Dict[str, Any]:
        """
        Remove IPv4 address and network profile.
        
        Args:
            name: Name of the IPv4 address resource to remove
            
        Returns:
            Response dictionary with removal result
            
        Example:
            >>> response = client.ip_rm(name="pentest-ip")
        """
        payload = {
            "operation": "ip_rm",
            "name": name
        }
        
        return self._make_request(payload)
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
