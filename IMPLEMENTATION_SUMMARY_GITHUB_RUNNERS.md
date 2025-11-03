# Implementation Summary: GitHub Self-Hosted Runners Support

## Overview

This implementation adds support for running ephemeral GitHub self-hosted worker containers using acido on Azure Container Instances, with a specific focus on AWS Lambda compatibility (15-minute execution limit).

## Changes Made

### 1. New CLI Subcommand: `run`

**File**: `acido/cli.py`

Added a new `run` subcommand that creates a single ephemeral container instance with automatic cleanup after a specified duration.

**Syntax**:
```bash
acido run <name> -im <image> -t <task> -d <duration> [options]
```

**Key Features**:
- Single container instance (not a fleet)
- Configurable duration (default: 900s, max: 900s)
- Auto-cleanup after duration expires
- Optional output capture
- Quiet mode with progress bar

**Implementation Details**:
- Parser definition: Lines 59-68
- Subcommand handling: Lines 211-214
- Main function integration: Lines 1591-1606
- Method implementation: Lines 650-779

**Security**:
- Duration is validated and capped at 900 seconds
- Task command is passed to `deploy()` which uses `shlex.quote()` for shell escaping
- No user-provided paths or file system operations

### 2. Extended Lambda Handler

**File**: `lambda_handler.py`

Extended the Lambda handler to support two operation modes:

1. **Fleet mode** (default, existing functionality): Multiple containers for distributed scanning
2. **Run mode** (new): Single ephemeral instance for GitHub runners

**API Changes**:
- Added `operation` field to event payload (optional, defaults to "fleet" for backward compatibility)
- New `_execute_run()` helper function for run operations
- Field validation moved before Acido initialization for proper error responses

**Example Payloads**:

Run operation:
```json
{
  "operation": "run",
  "name": "github-runner-01",
  "image": "github-runner",
  "task": "./run.sh --url https://github.com/myorg/myrepo --token ${RUNNER_TOKEN}",
  "duration": 900,
  "cleanup": true
}
```

Fleet operation (backward compatible):
```json
{
  "image": "nmap",
  "targets": ["example.com"],
  "task": "nmap -iL input"
}
```

**Security**:
- Proper validation of required fields before initialization
- Operation type validation (only "fleet" or "run" allowed)
- Duration validation enforced at Lambda level

### 3. Documentation

**New Files**:

1. **GITHUB_RUNNERS.md**: Comprehensive guide for using acido with GitHub self-hosted runners
   - Quick start guide
   - CLI and Lambda usage examples
   - Architecture diagram
   - Use cases (on-demand CI/CD, Lambda orchestration, parallel jobs)
   - Security considerations
   - Troubleshooting guide
   - Cost optimization tips

2. **examples/example_lambda_github_runner_payload.json**: Example Lambda payload for GitHub runners

**Updated Files**:

1. **README.md**: 
   - Added "GitHub Self-Hosted Runners" to table of contents
   - Added `run` subcommand to CLI reference
   - Added new section about GitHub runners with quick examples

2. **LAMBDA.md**:
   - Updated to document both operation modes (fleet and run)
   - Added parameter documentation for both operations
   - Added response format examples for both operations

### 4. Tests

**File**: `tests/test_lambda_handler_run.py`

Comprehensive test suite for the run operation:

- `test_run_operation_missing_required_fields`: Validates error handling for missing fields
- `test_run_operation_invalid_operation`: Validates operation type validation
- `test_run_operation_successful_execution`: Tests successful run execution
- `test_run_operation_default_duration`: Validates default duration (900s)
- `test_run_operation_default_cleanup`: Validates default cleanup (true)
- `test_run_operation_no_cleanup`: Tests cleanup disabled
- `test_run_operation_exception_handling`: Tests exception handling
- `test_backward_compatibility_fleet_operation`: Ensures fleet operation still works
- `test_default_operation_is_fleet`: Validates backward compatibility (default to fleet)

**Test Results**: All 9 tests pass, plus all 8 existing lambda handler tests pass

## Architecture

```
User/GitHub Actions
      ↓
  AWS Lambda (acido handler)
      ↓
  [operation validation]
      ↓
  ┌─────────────┬──────────────┐
  │             │              │
Fleet Mode    Run Mode     (new)
  │             │
  └─────────────┴──────────────┘
      ↓
Azure Container Instance
      ↓
  [Container execution]
      ↓
  [Auto-cleanup after duration]
```

## Use Cases

### 1. GitHub Self-Hosted Runners

Spin up ephemeral GitHub runner containers that:
- Run for a specific duration (e.g., 15 minutes)
- Automatically clean up after completion
- Can be orchestrated via AWS Lambda
- Cost-effective (pay only for runtime)

### 2. Lambda-Based Orchestration

AWS Lambda can orchestrate container creation with:
- Up to 15 minutes of execution time
- Automatic cleanup within Lambda execution
- Serverless invocation model
- Integration with GitHub Actions workflows

### 3. Temporary CI/CD Workers

Create on-demand workers for:
- Specific build jobs
- Parallel test execution
- Time-limited operations
- No idle infrastructure costs

## Backward Compatibility

✅ All changes are backward compatible:
- Existing fleet operations continue to work
- Default operation is "fleet" when not specified
- No breaking changes to CLI or Lambda API
- All existing tests pass

## Security Considerations

✅ Security measures implemented:

1. **Command Injection Prevention**: All commands are properly quoted using `shlex.quote()`
2. **Duration Validation**: Capped at 900 seconds to prevent abuse
3. **Input Validation**: Required fields validated before processing
4. **Operation Type Validation**: Only "fleet" and "run" operations allowed
5. **Error Handling**: Proper error responses for validation failures
6. **No Hardcoded Secrets**: All credentials from environment variables

## Testing

All tests pass:
- 9 new tests for run operation
- 8 existing tests for fleet operation
- Total: 17 tests, 0 failures

## Future Enhancements

Potential improvements for future releases:

1. **Dynamic Duration**: Support longer durations for non-Lambda use cases
2. **Multiple Instances**: Support multiple ephemeral instances in run mode
3. **Scheduled Cleanup**: Support delayed cleanup (e.g., cleanup after job completion rather than duration)
4. **GitHub API Integration**: Automatic runner token generation
5. **Runner Pooling**: Pre-create runner containers for faster startup

## References

- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [AWS Lambda Limits](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [Azure Container Instances](https://docs.microsoft.com/en-us/azure/container-instances/)
