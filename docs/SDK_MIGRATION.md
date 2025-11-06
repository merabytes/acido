# Azure SDK Migration for Container Log Retrieval

## Overview

This document describes the migration from Azure CLI (`az container`) to Azure SDK for retrieving container logs. This change resolves the issue where `az container logs` commands fail in AWS Lambda environments.

## Changes Made

### 1. InstanceManager Enhancement (`acido/azure_utils/InstanceManager.py`)

Added a new method `get_container_logs()` that uses the Azure Container Instance Management Client SDK:

```python
def get_container_logs(self, container_group_name: str, container_name: str, 
                      tail: int = None, timestamps: bool = False) -> str:
    """
    Retrieve logs from a container using Azure SDK.
    
    Args:
        container_group_name: Name of the container group
        container_name: Name of the container within the group
        tail: Optional number of lines to return from the end of logs
        timestamps: Whether to include timestamps in the logs
        
    Returns:
        str: Container logs as a string
    """
    logs = self._client.containers.list_logs(
        resource_group_name=self.resource_group,
        container_group_name=container_group_name,
        container_name=container_name,
        tail=tail,
        timestamps=timestamps
    )
    return logs.content
```

### 2. Shell Utils Update (`acido/utils/shell_utils.py`)

Updated `wait_command()` function to:
- Accept an optional `instance_manager` parameter
- Use SDK-based log retrieval when `instance_manager` is provided
- Fall back to CLI for backward compatibility (when `instance_manager` is None)
- Properly handle both `subprocess.CalledProcessError` and `HttpResponseError` exceptions

```python
def wait_command(rg, cg, cont, wait=None, instance_manager=None):
    """
    Wait for a command to complete by polling container logs.
    
    Args:
        rg: Resource group name (kept for backward compatibility)
        cg: Container group name
        cont: Container name
        wait: Optional timeout in seconds
        instance_manager: InstanceManager instance for retrieving logs via Azure SDK
        
    Returns:
        tuple: (container_name, command_uuid, exception)
    """
    # ... implementation uses instance_manager.get_container_logs() when available
```

### 3. CLI Update (`acido/cli.py`)

Modified the `fleet()` method to pass `self.instance_manager` to `wait_command()`:

```python
result = pool.apply_async(wait_command, 
                          (self.rg, cg, cont, wait, self.instance_manager), 
                          callback=build_output)
```

### 4. Dependencies (`requirements.txt`)

Explicitly added `azure-mgmt-containerinstance` to ensure the SDK is available:

```
azure-mgmt-containerinstance
```

### 5. Test Updates

#### Fixed Existing Tests (`test_lambda_handler.py`)
- Updated all `ThreadPool` mock references to `ThreadPoolShim`

#### New Unit Tests (`test_instance_manager_logs.py`)
- Tests for `InstanceManager.get_container_logs()` method
  - Success case
  - With tail parameter
  - Error handling
- Tests for `wait_command()` with SDK
  - With instance_manager
  - Timeout scenarios
  - Exception in logs
  - SDK errors

#### New Integration Tests (`test_lambda_integration.py`)
- Lambda context simulation (no az CLI available)
- Verification that SDK is used instead of CLI
- End-to-end Lambda fleet operation

### 6. CI/CD Pipeline (`..github/workflows/ci.yml`)

Added unit test execution to the CI pipeline:

```yaml
- name: Run unit tests
  run: |
    python -m unittest discover -s . -p "test_*.py" -v
```

## Benefits

1. **Lambda Compatibility**: Works in AWS Lambda where Azure CLI is not available
2. **Better Performance**: Direct SDK calls are more efficient than subprocess execution
3. **Better Error Handling**: Proper exception types (HttpResponseError) instead of subprocess errors
4. **Backward Compatibility**: Falls back to CLI when instance_manager is not provided
5. **Testability**: SDK calls are easier to mock and test

## Authentication

The SDK uses the same authentication mechanism as other Azure operations:
- In Lambda: Uses `EnvironmentCredential` with `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and `AZURE_CLIENT_SECRET`
- Locally: Uses `ManagedIdentity` or `DefaultAzureCredential`

## Usage Example

### Command Line Usage (unchanged)
```bash
acido -f lambda-fleet -im kali-rolling -t 'nmap -iL input -p 0-1000' -i 'file.txt' -n 3 -o output --rm-when-done
```

### Lambda Payload (unchanged)
```json
{
  "image": "kali-rolling",
  "targets": ["merabytes.com", "uber.com"],
  "task": "nmap -iL input -p 0-1000",
  "num_instances": 3
}
```

## Testing

Run all tests:
```bash
python -m unittest discover -s . -p "test_*.py" -v
```

Run specific test suites:
```bash
python -m unittest test_instance_manager_logs -v
python -m unittest test_lambda_integration -v
python -m unittest test_lambda_handler -v
```

All 17 tests pass successfully.

## Note on exec_command

The `exec_command()` function in `shell_utils.py` still uses `az container exec` via tmux for interactive command execution. This function is:
- Not used in Lambda fleet operations (only used in the `exec` CLI method)
- Requires interactive terminal access which is not available in Lambda
- Not part of the primary Lambda workflow

If interactive execution in Lambda is needed in the future, an alternative approach using the Azure SDK's `execute_command` API would need to be implemented.
