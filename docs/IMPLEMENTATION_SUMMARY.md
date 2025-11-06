# Implementation Summary: Azure SDK Migration

## Problem Statement
The `az container logs` CLI command was failing in AWS Lambda environments, causing the fleet operation to return HTTP 500 errors with the message:
```
"error": "Command 'az container logs --resource-group *** --name lambda-fleet --container-name lambda-fleet-01' returned non-zero exit status 1."
```

## Solution Implemented
Replaced subprocess-based Azure CLI calls with Azure SDK's native Python API for container log retrieval.

## Files Changed

### 1. `acido/azure_utils/InstanceManager.py`
**Added**: `get_container_logs()` method
- Uses `ContainerInstanceManagementClient.containers.list_logs()`
- Supports `tail` and `timestamps` parameters
- Returns container logs as a string
- Properly handles `HttpResponseError` exceptions

### 2. `acido/utils/shell_utils.py`
**Modified**: `wait_command()` function
- Added `instance_manager` parameter (optional)
- Uses SDK when `instance_manager` is provided
- Falls back to CLI for backward compatibility
- Improved error handling for both subprocess and SDK errors
- Fixed potential IndexError in UUID parsing

### 3. `acido/cli.py`
**Modified**: `fleet()` method
- Passes `self.instance_manager` to `wait_command()`
- Line 519: Updated `pool.apply_async()` call

### 4. `requirements.txt`
**Modified**: Added explicit dependency
- Added `azure-mgmt-containerinstance`
- Standardized package naming to hyphen notation

### 5. `.github/workflows/ci.yml`
**Added**: Unit test execution
- New step: "Run unit tests" in CI pipeline
- Runs on every PR and push to main

### 6. Test Files (New)
**Created**: `test_instance_manager_logs.py` (7 tests)
- Tests for `InstanceManager.get_container_logs()`
- Tests for `wait_command()` with SDK

**Created**: `test_lambda_integration.py` (2 tests)
- Lambda context simulation
- End-to-end integration tests

**Modified**: `test_lambda_handler.py`
- Fixed ThreadPool references to ThreadPoolShim

### 7. Documentation (New)
**Created**: `SDK_MIGRATION.md`
- Comprehensive migration guide
- Usage examples
- API documentation

## Test Results

### Test Coverage
- **Total Tests**: 17
- **Original Tests**: 8 (all passing)
- **New Unit Tests**: 7 (all passing)
- **New Integration Tests**: 2 (all passing)

### Test Execution
```bash
$ python -m unittest discover -s . -p "test_*.py" -v
Ran 17 tests in 2.015s
OK
```

## Security Analysis
✅ CodeQL Analysis: **No vulnerabilities found**
- Actions: No alerts
- Python: No alerts

## Authentication
The SDK uses Azure's native authentication mechanisms:
- **Lambda Environment**: `EnvironmentCredential` with:
  - `AZURE_TENANT_ID`
  - `AZURE_CLIENT_ID`
  - `AZURE_CLIENT_SECRET`
- **Local Environment**: `ManagedIdentity` or `DefaultAzureCredential`

## Backward Compatibility
The implementation maintains full backward compatibility:
- CLI-based execution still works when `instance_manager` is not provided
- All existing tests pass without modification (except ThreadPool name fix)
- No breaking changes to the API

## Performance Improvements
1. **Faster Execution**: Direct SDK calls eliminate subprocess overhead
2. **Better Error Messages**: Native Python exceptions instead of subprocess errors
3. **Lower Memory Usage**: No need to spawn shell processes

## Usage Example

### Before (CLI-based)
```python
# Subprocess call (fails in Lambda)
container_logs = subprocess.check_output(
    f'az container logs --resource-group {rg} --name {cg} --container-name {cont}', 
    shell=True
).decode()
```

### After (SDK-based)
```python
# Native SDK call (works everywhere)
container_logs = instance_manager.get_container_logs(cg, cont)
```

## Verification Steps
1. ✅ All unit tests pass
2. ✅ All integration tests pass
3. ✅ Code review feedback addressed
4. ✅ Security scan completed (no issues)
5. ✅ CI pipeline updated and validated
6. ✅ Documentation created

## Command to Test
```bash
# Set required environment variables
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-secret"
export AZURE_RESOURCE_GROUP="your-rg"
export IMAGE_REGISTRY_SERVER="your-registry.azurecr.io"
export IMAGE_REGISTRY_USERNAME="your-username"
export IMAGE_REGISTRY_PASSWORD="your-password"
export STORAGE_ACCOUNT_NAME="your-storage"
export MANAGED_IDENTITY_ID="/subscriptions/.../userAssignedIdentities/..."
export MANAGED_IDENTITY_CLIENT_ID="your-managed-identity-client-id"

# Run the fleet command
acido -f lambda-fleet -im kali-rolling -t 'nmap -iL input -p 0-1000' -i 'file.txt' -n 3 -o output --rm-when-done
```

## Lambda Payload Example
```json
{
  "image": "kali-rolling",
  "targets": ["merabytes.com", "uber.com"],
  "task": "nmap -iL input -p 0-1000",
  "num_instances": 3
}
```

## Future Considerations
The `exec_command()` function still uses `az container exec` for interactive execution. This is:
- Not used in Lambda fleet operations
- Only used by the CLI `exec` method
- Requires terminal access (not available in Lambda)

If interactive command execution is needed in Lambda in the future, consider implementing it using Azure SDK's `execute_command` API.

## Conclusion
The implementation successfully resolves the Lambda compatibility issue while maintaining backward compatibility, improving performance, and adding comprehensive test coverage. All tests pass, and no security vulnerabilities were detected.
