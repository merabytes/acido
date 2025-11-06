# Implementation Summary: Lambda Handler JSON API & IP Management Refactoring

## Problem Statement (Spanish)
Me gustaría que lambda_handler.py me permitiera controlar todos los argumentos de argparse de Acido mediante JSON. Quiero tener una API REST que me permita usar el CLI a distancia desde un portal que sólo soporta HTTP y que de la ejecución se encargue Lambda. De momento quiero poder usar acido fleet, acido run, acido ls, acido rm.

También cambia 'acido create ip <nombre>' -> 'acido ip create <nombre>' y cambiar --ip para que pueda hacer 'acido ip ls' y acido ip rm y usar estos metodos en la clase Acido como hago con las instancias.

## Solution Overview

### 1. Lambda Handler Enhancements ✅

**Added Operations:**
- `ls`: List all container instances
- `rm`: Remove container instances by name or pattern

**Total Operations Supported:**
1. `fleet` - Multiple instances for distributed scanning
2. `run` - Single ephemeral instance with auto-cleanup
3. `ls` - List all container instances
4. `rm` - Remove container instances

### 2. IP Address Management Refactoring ✅

**CLI Command Changes:**

| Old Command | New Command | Description |
|-------------|-------------|-------------|
| `acido --create-ip <name>` | `acido ip create <name>` | Create IPv4 address |
| `acido --ip` | `acido ip select` | Select IPv4 address |
| N/A | `acido ip ls` | List all IPv4 addresses |
| N/A | `acido ip rm <name>` | Remove IPv4 address |

**New Acido Class Methods:**
- `ls_ip(interactive=True)` - List all IPv4 addresses
- `rm_ip(name)` - Remove IPv4 address and network resources

## Technical Details

### Lambda Handler API

All operations accept JSON payloads and return structured responses:

```python
# List operation
event = {"operation": "ls"}
response = {
    "statusCode": 200,
    "body": {
        "operation": "ls",
        "instances": [
            {"container_group": "fleet-1", "containers": ["c1", "c2"]}
        ]
    }
}

# Remove operation
event = {"operation": "rm", "name": "fleet-1"}
response = {
    "statusCode": 200,
    "body": {
        "operation": "rm",
        "result": {"removed": "fleet-1"}
    }
}
```

### CLI Structure

```
acido
├── create <base_image>         # Create acido-compatible image
├── configure                    # Configure acido
├── fleet <fleet_name>          # Create fleet of containers
├── run <name>                  # Run single ephemeral instance
├── ls                          # List all instances
├── rm <name>                   # Remove instances
├── ip                          # IP address management
│   ├── create <name>           # Create IPv4 address
│   ├── ls                      # List IPv4 addresses
│   ├── rm <name>               # Remove IPv4 address
│   └── select                  # Select IPv4 address
├── select <pattern>            # Select instances by pattern
└── exec <command>              # Execute command on instances
```

## Files Modified

1. **lambda_handler.py**
   - Added `_execute_ls()` function
   - Added `_execute_rm()` function
   - Updated `VALID_OPERATIONS` to include 'ls' and 'rm'
   - Updated validation logic for new operations
   - Enhanced docstring with all operation examples

2. **acido/cli.py**
   - Added IP subparser with sub-subparsers (create/ls/rm/select)
   - Added `ls_ip()` method to Acido class
   - Added `rm_ip()` method to Acido class
   - Updated argument parsing to handle IP subcommands
   - Updated main() to call IP management methods

3. **tests/test_lambda_handler.py**
   - Added `test_ls_operation()`
   - Added `test_rm_operation()`
   - Added `test_rm_missing_name()`

4. **LAMBDA_API_EXAMPLES.md** (NEW)
   - Comprehensive examples for all operations
   - CLI equivalents table
   - Error response examples
   - Environment variables documentation

## Testing Results

### Unit Tests
- **Total Tests**: 65
- **Status**: ✅ All passing
- **Coverage**:
  - lambda_handler: 11 tests
  - lambda_handler_run: 9 tests
  - lambda_handler_secrets: 43 tests
  - lambda_integration: 2 tests

### Manual Testing
- ✅ CLI command help for all subcommands
- ✅ IP subcommand structure
- ✅ Lambda handler API with mock Acido
- ✅ Backward compatibility verified

### Quality Checks
- ✅ Code review: No issues
- ✅ Security scan (CodeQL): No vulnerabilities
- ✅ Import validation: All modules load correctly

## Usage Examples

### Lambda Handler (REST API)

```bash
# List instances
curl -X POST https://api.example.com/acido \
  -d '{"operation": "ls"}'

# Remove instances
curl -X POST https://api.example.com/acido \
  -d '{"operation": "rm", "name": "fleet-*"}'

# Create fleet
curl -X POST https://api.example.com/acido \
  -d '{
    "operation": "fleet",
    "image": "nmap",
    "targets": ["example.com"],
    "task": "nmap -iL input"
  }'
```

### CLI

```bash
# IP management
acido ip create my-ip-1
acido ip ls
acido ip select
acido ip rm my-ip-1

# Instance management
acido fleet myfleet -im nmap -t "nmap -iL input"
acido ls
acido rm myfleet
```

## Backward Compatibility

- ✅ All existing functionality preserved
- ✅ Old-style CLI arguments still work
- ✅ Default operation remains 'fleet' for backward compatibility
- ✅ Existing tests continue to pass

## Documentation

- Created `LAMBDA_API_EXAMPLES.md` with comprehensive examples
- Updated lambda_handler docstring with all operations
- Included CLI equivalents table
- Added error handling documentation

## Benefits

1. **REST API Integration**: Portal can now control all acido operations via HTTP
2. **Improved UX**: IP management uses intuitive subcommands
3. **Consistency**: IP commands follow same pattern as instance management
4. **Flexibility**: All operations accessible via JSON or CLI
5. **Maintainability**: Clear separation of concerns, well-tested

## Future Enhancements

Potential additions (not in current scope):
- Add IP operations to lambda_handler API
- Add select operation to lambda_handler
- Add exec operation to lambda_handler
- Add create operation to lambda_handler for image building
