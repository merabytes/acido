# Port Forwarding Implementation Task - PR Prompt

## Overview

Implement port forwarding feature for Azure Container Instances to enable inbound connectivity. This allows containers to accept incoming connections from the internet on specific ports (e.g., VoIP servers, game servers, SSH bastions).

## Background

**Current State**: Acido containers can only make outbound connections via NAT Gateway.

**Goal**: Enable containers to accept inbound connections by assigning dedicated Azure public IPs.

**Key Finding**: Azure NAT Gateway does NOT support inbound connections or DNAT. Must use public IPs directly on container groups.

## Complete Documentation Available

All proposal documents are in `docs/`:
- **START HERE**: `docs/PORT_FORWARDING_INDEX.md` - Master index
- `docs/PORT_FORWARDING_SUMMARY.md` - Executive summary
- `docs/PORT_FORWARDING_PROPOSAL.md` - Technical proposal with alternatives
- `docs/port_forwarding_implementation.md` - Step-by-step implementation guide (YOUR MAIN REFERENCE)
- `docs/port_forwarding_examples.md` - 7 practical use cases
- `docs/PORT_FORWARDING_DIAGRAMS.md` - Architecture diagrams

## Implementation Requirements

### 1. New CLI Commands

```bash
# Create public IP for port forwarding
acido ip create-forwarding <name> --ports PORT:PROTOCOL

# List port-forwarding enabled IPs
acido ip ls-forwarding

# Clean IP configuration from local config
acido ip clean

# Deploy with port forwarding (network config auto-derived from --public-ip)
acido run <name> --public-ip <ip> --expose-port PORT:PROTOCOL

# Fleet with network configuration
acido fleet <name> --public-ip <ip>

# NEW: Configurable CPU and RAM resources
acido run <name> --cpu <cores> --ram <gb>
acido fleet <name> --cpu <cores> --ram <gb>
```

### 2. Core Features

**Configurable CPU and RAM** (NEW REQUIREMENT):
- Add `--cpu` argument to `run` and `fleet` commands (default: varies by command)
- Add `--ram` argument to `run` and `fleet` commands (default: varies by command)
- Pass these values to `InstanceManager.deploy()` as `max_cpu` and `max_ram` parameters
- Validate CPU and RAM values are within Azure Container Instances limits

**Automatic Subnet Derivation**:
- When `--public-ip voip-ip` is specified, automatically derive:
  - VNet: `voip-ip-vnet`
  - Subnet: `voip-ip-subnet`
- No need to run `acido ip select` or read from config
- Works for both `acido.run()` and `acido.fleet()`

**Config Warning System**:
- Warn if IP is selected in config but `--public-ip` not specified
- Display: "Warning: IP 'old-ip' is selected in config but --public-ip not specified"
- Suggest: "To clear config: run 'acido ip clean'"

**IP Clean Command**:
- Clears from config: public_ip_name, public_ip_id, vnet_name, subnet_name, subnet_id

### 3. Code Changes Required (~500 LOC)

#### NetworkManager.py (`acido/azure_utils/NetworkManager.py`)

Add new methods:

```python
def create_forwarding_ip(self, name, ports=None):
    """
    Create a public IP for port forwarding with optional port metadata.
    
    Args:
        name (str): Name of the public IP resource
        ports (list, optional): List of port dicts [{"port": 5060, "protocol": "UDP"}]
    
    Returns:
        tuple: (public_ip_id, ip_address_string)
    """
    tags = {'purpose': 'port-forwarding'}
    if ports:
        tags['ports'] = ','.join([f"{p['port']}/{p['protocol']}" for p in ports])
    
    params = {
        'location': self.location,
        'public_ip_allocation_method': 'Static',
        'public_ip_address_version': 'IPv4',
        'sku': PublicIPAddressSku(name='Standard', tier='Regional'),
        'tags': tags
    }
    
    pip = self._client.public_ip_addresses.begin_create_or_update(
        self.resource_group, name, params
    ).result()
    
    return pip.id, pip.ip_address

def get_public_ip(self, name):
    """Get public IP resource by name."""
    return self._client.public_ip_addresses.get(self.resource_group, name)

def list_forwarding_ips(self):
    """List all public IPs tagged for port forwarding."""
    all_ips = self._client.public_ip_addresses.list(self.resource_group)
    forwarding_ips = []
    
    for ip in all_ips:
        if ip.tags and ip.tags.get('purpose') == 'port-forwarding':
            forwarding_ips.append({
                'id': ip.id,
                'name': ip.name,
                'ip_address': ip.ip_address,
                'location': ip.location,
                'ports': ip.tags.get('ports', 'N/A')
            })
    
    return forwarding_ips

def delete_forwarding_ip(self, name):
    """Delete a port forwarding public IP."""
    try:
        self._client.public_ip_addresses.begin_delete(
            self.resource_group, name
        ).result()
        return True
    except Exception:
        return False
```

#### InstanceManager.py (`acido/azure_utils/InstanceManager.py`)

Modify `deploy()` method to accept new parameters:

```python
def deploy(self, name, ..., public_ip_name=None, exposed_ports=None):
    """
    Deploy container group with optional public IP and port forwarding.
    
    New Args:
        public_ip_name (str, optional): Name of public IP resource
        exposed_ports (list, optional): List of port dicts [{"port": 5060, "protocol": "UDP"}]
    """
    # ... existing code ...
    
    # Configure IP address
    ip_cfg = None
    
    if public_ip_name and exposed_ports:
        # Port forwarding mode: Public IP with specific ports
        ip_cfg = IpAddress(
            type="Public",
            ports=[Port(protocol=p["protocol"], port=p["port"]) 
                   for p in exposed_ports]
        )
    elif expose_private_port:
        # Private IP mode (existing functionality)
        ip_cfg = IpAddress(type="Private", ports=[Port(protocol="TCP", port=expose_private_port)])
    else:
        # No IP mode: Pure NAT Gateway egress
        ip_cfg = None
    
    # ... rest of existing code ...
    
    cg = ContainerGroup(
        location=location,
        containers=deploy_instances,
        os_type=os_type,
        ip_address=ip_cfg,  # Public IP with forwarded ports or None
        image_registry_credentials=ir_credentials,
        restart_policy=restart_policy,
        tags=tags,
        subnet_ids=subnet_ids,
        identity=...
    )
```

#### cli.py (`acido/cli.py`)

Add new subcommands and handler methods:

```python
# IP clean subcommand
ip_clean_parser = ip_subparsers.add_parser('clean', help='Clean IP configuration from local config')

# IP create-forwarding subcommand
ip_forwarding_parser = ip_subparsers.add_parser('create-forwarding', help='Create a public IP configured for port forwarding')
ip_forwarding_parser.add_argument('name', help='Name for the public IP address')
ip_forwarding_parser.add_argument('--ports', dest='forward_ports', action='append', 
                                  help='Port to forward (format: PORT:PROTOCOL)')

# IP ls-forwarding subcommand
ip_ls_forwarding_parser = ip_subparsers.add_parser('ls-forwarding', help='List public IPs configured for port forwarding')

# Add to run_parser
run_parser.add_argument('--public-ip', dest='public_ip_name', 
                       help='Name of public IP to use for port forwarding. Subnet config automatically derived.')
run_parser.add_argument('--expose-port', dest='expose_ports', action='append',
                       help='Port to expose (format: PORT:PROTOCOL). Requires --public-ip.')

# NEW: Add CPU and RAM arguments to run_parser
run_parser.add_argument('--cpu', dest='cpu', type=float, default=1.0,
                       help='CPU cores to allocate (default: 1.0, max: 4.0)')
run_parser.add_argument('--ram', dest='ram', type=float, default=1.0,
                       help='RAM in GB to allocate (default: 1.0, max: 16.0)')

# Add to fleet_parser
fleet_parser.add_argument('--public-ip', dest='public_ip_name',
                         help='Name of public IP for network configuration.')

# NEW: Add CPU and RAM arguments to fleet_parser
fleet_parser.add_argument('--cpu', dest='cpu', type=float, default=4.0,
                         help='Total CPU cores for fleet (default: 4.0, distributed across instances)')
fleet_parser.add_argument('--ram', dest='ram', type=float, default=16.0,
                         help='Total RAM in GB for fleet (default: 16.0, distributed across instances)')
```

Add Acido class methods:

```python
def create_forwarding_ip(self, name, port_specs=None):
    """Create a public IP for port forwarding."""
    # Parse port specs and call network_manager.create_forwarding_ip()

def list_forwarding_ips(self):
    """List all public IPs configured for port forwarding."""
    # Call network_manager.list_forwarding_ips()

def rm_forwarding_ip(self, name):
    """Remove a port forwarding public IP."""
    # Call network_manager.delete_forwarding_ip()

def clean_ip_config(self):
    """Clean IP configuration from local config."""
    self.public_ip_name = None
    self.public_ip_id = None
    self.vnet_name = None
    self.subnet_name = None
    self.subnet_id = None
    self._save_config()

def _derive_subnet_from_public_ip(self, public_ip_name):
    """Automatically derive subnet configuration from public IP name."""
    return f"{public_ip_name}-vnet", f"{public_ip_name}-subnet"
```

Add command handlers in main execution block:

```python
# Handle IP forwarding subcommands
if args.subcommand == 'ip':
    if args.ip_subcommand == 'create-forwarding':
        acido.create_forwarding_ip(args.name, args.forward_ports)
    elif args.ip_subcommand == 'ls-forwarding':
        acido.list_forwarding_ips()
    elif args.ip_subcommand == 'clean':
        acido.clean_ip_config()

# Handle run command with port forwarding
elif args.subcommand == 'run':
    # Warn if IP is selected in config but --public-ip is not specified
    if acido.public_ip_name and not args.public_ip_name:
        print(orange(f"Warning: IP '{acido.public_ip_name}' is selected in config but --public-ip not specified"))
        print(info("To use port forwarding: add --public-ip {acido.public_ip_name}"))
        print(info("To clear config: run 'acido ip clean'"))
    
    # Parse exposed ports
    exposed_ports = None
    if args.expose_ports:
        exposed_ports = []
        for spec in args.expose_ports:
            port, protocol = spec.split(':')
            exposed_ports.append({"port": int(port), "protocol": protocol.upper()})
    
    # Validate: If expose_ports is set, public_ip_name must also be set
    if exposed_ports and not args.public_ip_name:
        print(bad("--expose-port requires --public-ip to be specified"))
        sys.exit(1)
    
    # Automatically derive subnet from public IP if specified
    vnet_name = None
    subnet_name = None
    if args.public_ip_name:
        vnet_name, subnet_name = acido._derive_subnet_from_public_ip(args.public_ip_name)
        print(info(f"Using network: {vnet_name}/{subnet_name} (derived from {args.public_ip_name})"))
    
    # Call run with port forwarding parameters
    acido.run(
        name=args.name,
        image_name=args.image_name,
        task=args.task,
        duration=args.duration,
        write_to_file=args.write_to_file,
        output_format=args.output_format,
        quiet=args.quiet,
        cleanup=not args.no_cleanup,
        regions=args.region,
        public_ip_name=args.public_ip_name,
        exposed_ports=exposed_ports,
        vnet_name=vnet_name,
        subnet_name=subnet_name,
        cpu=args.cpu,  # NEW: Pass CPU argument
        ram=args.ram   # NEW: Pass RAM argument
    )

# Similar updates for fleet command
elif args.subcommand == 'fleet':
    # ... existing warning and validation code ...
    
    # Automatically derive subnet from public IP if specified
    vnet_name = None
    subnet_name = None
    if args.public_ip_name:
        vnet_name, subnet_name = acido._derive_subnet_from_public_ip(args.public_ip_name)
    
    acido.fleet(
        fleet_name=args.fleet_name,
        instance_num=args.num_instances,
        image_name=args.image_name,
        scan_cmd=args.task,
        input_file=args.input_file,
        wait=args.wait,
        write_to_file=args.write_to_file,
        output_format=args.output_format,
        quiet=args.quiet,
        rm_when_done=args.rm_when_done,
        regions=args.region,
        vnet_name=vnet_name,
        subnet_name=subnet_name,
        max_cpu=args.cpu,  # NEW: Pass CPU argument (total for fleet)
        max_ram=args.ram   # NEW: Pass RAM argument (total for fleet)
    )
```

Update `run()` and `fleet()` method signatures to accept new parameters:

```python
def run(self, name: str, image_name: str, task: str = None, duration: int = 900,
        write_to_file: str = None, output_format: str = 'txt', 
        quiet: bool = False, cleanup: bool = True, regions=None,
        public_ip_name: str = None, exposed_ports: list = None,
        vnet_name: str = None, subnet_name: str = None,
        cpu: float = 1.0, ram: float = 1.0):  # NEW: CPU and RAM parameters
    """
    Run a single ephemeral container instance.
    
    New Args:
        public_ip_name (str, optional): Name of public IP for port forwarding
        exposed_ports (list, optional): List of port dicts to expose
        vnet_name (str, optional): VNet name (auto-derived from public_ip if not provided)
        subnet_name (str, optional): Subnet name (auto-derived from public_ip if not provided)
        cpu (float, optional): CPU cores to allocate (default: 1.0, max: 4.0)
        ram (float, optional): RAM in GB to allocate (default: 1.0, max: 16.0)
    """
    # Validate CPU and RAM
    if cpu < 0.1 or cpu > 4.0:
        raise ValueError(f"CPU must be between 0.1 and 4.0, got {cpu}")
    if ram < 0.1 or ram > 16.0:
        raise ValueError(f"RAM must be between 0.1 and 16.0 GB, got {ram}")
    
    # ... existing code ...
    
    # Pass CPU and RAM to instance_manager.deploy()
    result = self.instance_manager.deploy(
        name=name,
        image_name=full_image_url,
        command=task,
        location=selected_region,
        vnet_name=vnet_name,
        subnet_name=subnet_name,
        env_vars=env_vars,
        quiet=quiet,
        public_ip_name=public_ip_name,
        exposed_ports=exposed_ports,
        max_cpu=cpu,  # Pass CPU
        max_ram=ram,  # Pass RAM
        instance_number=1  # Single instance for run command
    )

def fleet(self, fleet_name: str, instance_num: int, image_name: str,
          scan_cmd: str = None, input_file: str = None, wait: int = None,
          write_to_file: str = None, output_format: str = 'txt',
          quiet: bool = False, rm_when_done: bool = False, regions=None,
          vnet_name: str = None, subnet_name: str = None,
          max_cpu: float = 4.0, max_ram: float = 16.0):  # NEW: CPU and RAM parameters
    """
    Deploy a fleet of container instances.
    
    New Args:
        vnet_name (str, optional): VNet name (auto-derived from public_ip if not provided)
        subnet_name (str, optional): Subnet name (auto-derived from public_ip if not provided)
        max_cpu (float, optional): Total CPU cores for fleet (default: 4.0, distributed across instances)
        max_ram (float, optional): Total RAM in GB for fleet (default: 16.0, distributed across instances)
    """
    # Validate CPU and RAM
    if max_cpu < 0.1 or max_cpu > 100.0:  # Higher limit for fleets
        raise ValueError(f"Total CPU must be between 0.1 and 100.0, got {max_cpu}")
    if max_ram < 0.1 or max_ram > 256.0:  # Higher limit for fleets
        raise ValueError(f"Total RAM must be between 0.1 and 256.0 GB, got {max_ram}")
    
    # ... existing code ...
    
    # Pass CPU and RAM to instance_manager.deploy()
    results = self.instance_manager.deploy(
        name=fleet_name,
        image_name=full_image_url,
        command=scan_cmd,
        location=selected_region,
        vnet_name=vnet_name,
        subnet_name=subnet_name,
        env_vars=env_vars,
        quiet=quiet,
        max_cpu=max_cpu,  # Pass total CPU
        max_ram=max_ram,  # Pass total RAM
        instance_number=instance_num
    )
```

#### lambda_handler.py (`lambda_handler.py`)

Add new operations:

```python
VALID_OPERATIONS = [
    'fleet', 'run', 'ls', 'rm', 
    'ip_create', 'ip_ls', 'ip_rm',
    'ip_create_forwarding', 'ip_ls_forwarding', 'ip_clean'
]

def lambda_handler(event, context):
    # ... existing code ...
    
    elif operation == 'ip_create_forwarding':
        name = event.get('name')
        ports = event.get('ports', [])
        acido.create_forwarding_ip(name, ports)
        return build_response({'operation': operation, 'result': {'created': name, 'ports': ports}})
    
    elif operation == 'ip_ls_forwarding':
        ips = acido.network_manager.list_forwarding_ips() if acido.network_manager else []
        return build_response({'operation': operation, 'result': {'ips': ips}})
    
    elif operation == 'ip_clean':
        acido.clean_ip_config()
        return build_response({'operation': operation, 'result': {'message': 'IP configuration cleaned'}})
    
    elif operation == 'run':
        public_ip_name = event.get('public_ip_name')
        exposed_ports = event.get('exposed_ports', [])
        cpu = event.get('cpu', 1.0)  # NEW: Get CPU from event
        ram = event.get('ram', 1.0)  # NEW: Get RAM from event
        
        # Automatically derive subnet from public IP
        vnet_name = None
        subnet_name = None
        if public_ip_name:
            vnet_name, subnet_name = acido._derive_subnet_from_public_ip(public_ip_name)
        
        response, outputs = acido.run(
            name=name,
            image_name=full_image_url,
            task=task,
            duration=duration,
            public_ip_name=public_ip_name,
            exposed_ports=exposed_ports,
            vnet_name=vnet_name,
            subnet_name=subnet_name,
            cpu=cpu,  # NEW: Pass CPU
            ram=ram   # NEW: Pass RAM
        )
        # ... return response ...
    
    elif operation == 'fleet':
        # ... existing fleet code ...
        max_cpu = event.get('max_cpu', 4.0)  # NEW: Get CPU from event
        max_ram = event.get('max_ram', 16.0)  # NEW: Get RAM from event
        
        response, outputs = acido.fleet(
            fleet_name=fleet_name,
            instance_num=instance_num,
            image_name=full_image_url,
            scan_cmd=task,
            input_file=input_file,
            wait=wait,
            quiet=True,
            regions=regions,
            vnet_name=vnet_name,
            subnet_name=subnet_name,
            max_cpu=max_cpu,  # NEW: Pass CPU
            max_ram=max_ram   # NEW: Pass RAM
        )
        # ... return response ...
```

#### port_utils.py (`acido/utils/port_utils.py`) - NEW FILE

Create helper utilities:

```python
"""Utilities for handling port specifications and validation."""

def parse_port_spec(port_spec):
    """Parse port specification string like '5060:udp'."""
    try:
        port, protocol = port_spec.split(':')
        return {"port": int(port), "protocol": protocol.upper()}
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid port specification: {port_spec}. Format: PORT:PROTOCOL")

def validate_port(port):
    """Validate port number (1-65535)."""
    if not isinstance(port, int):
        raise ValueError(f"Port must be an integer, got {type(port)}")
    if port < 1 or port > 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port}")
    return True

def validate_protocol(protocol):
    """Validate protocol (TCP or UDP)."""
    protocol = protocol.upper()
    if protocol not in ['TCP', 'UDP']:
        raise ValueError(f"Protocol must be TCP or UDP, got {protocol}")
    return True

def format_port_list(ports):
    """Format list of ports for display."""
    return ', '.join([f"{p['port']}/{p['protocol']}" for p in ports])
```

### 4. Testing Requirements

#### Unit Tests (`tests/test_port_forwarding.py` - NEW FILE)

```python
import unittest
from acido.utils.port_utils import parse_port_spec, validate_port, validate_protocol

class TestPortUtils(unittest.TestCase):
    def test_parse_port_spec_valid(self):
        result = parse_port_spec("5060:udp")
        self.assertEqual(result["port"], 5060)
        self.assertEqual(result["protocol"], "UDP")
    
    def test_parse_port_spec_tcp(self):
        result = parse_port_spec("8080:tcp")
        self.assertEqual(result["port"], 8080)
        self.assertEqual(result["protocol"], "TCP")
    
    def test_parse_port_spec_invalid(self):
        with self.assertRaises(ValueError):
            parse_port_spec("invalid")
    
    def test_validate_port_valid(self):
        self.assertTrue(validate_port(5060))
        self.assertTrue(validate_port(80))
        self.assertTrue(validate_port(65535))
    
    def test_validate_port_invalid(self):
        with self.assertRaises(ValueError):
            validate_port(0)
        with self.assertRaises(ValueError):
            validate_port(65536)
    
    def test_validate_protocol_valid(self):
        self.assertTrue(validate_protocol("TCP"))
        self.assertTrue(validate_protocol("UDP"))
        self.assertTrue(validate_protocol("tcp"))  # Case insensitive
    
    def test_validate_protocol_invalid(self):
        with self.assertRaises(ValueError):
            validate_protocol("ICMP")
```

#### Integration Tests

Manual testing steps (documented in `docs/port_forwarding_implementation.md`):

```bash
# 1. Test creating forwarding IP
acido ip create-forwarding test-ip --ports 8080:tcp

# 2. Verify IP was created
acido ip ls-forwarding

# 3. Deploy test container
acido run test-server \
  -im nginx:alpine \
  --public-ip test-ip \
  --expose-port 8080:tcp \
  -d 600

# 4. Get public IP and test connectivity
IP=$(acido ip ls-forwarding | grep test-ip | awk '{print $2}')
curl http://$IP:8080

# 5. Test config clean
acido ip clean

# 6. Cleanup
acido rm test-server
acido ip rm test-ip
```

### 5. Implementation Steps

1. **Phase 1**: NetworkManager extensions
   - Implement `create_forwarding_ip()`
   - Implement `list_forwarding_ips()`
   - Implement `get_public_ip()`
   - Implement `delete_forwarding_ip()`

2. **Phase 2**: InstanceManager modifications
   - Modify `deploy()` to accept `public_ip_name` and `exposed_ports`
   - Add IP configuration logic for port forwarding

3. **Phase 3**: CLI commands
   - Add `ip create-forwarding` subcommand
   - Add `ip ls-forwarding` subcommand
   - Add `ip clean` subcommand
   - Add `--public-ip` and `--expose-port` arguments to `run` command
   - Add `--public-ip` argument to `fleet` command
   - **NEW**: Add `--cpu` and `--ram` arguments to `run` command
   - **NEW**: Add `--cpu` and `--ram` arguments to `fleet` command

4. **Phase 4**: Acido class methods
   - Implement `create_forwarding_ip()`
   - Implement `list_forwarding_ips()`
   - Implement `rm_forwarding_ip()`
   - Implement `clean_ip_config()`
   - Implement `_derive_subnet_from_public_ip()`
   - Update `run()` method signature with CPU and RAM parameters
   - Update `fleet()` method signature with CPU and RAM parameters

5. **Phase 5**: Command handlers
   - Add IP forwarding subcommand handlers
   - Add config warning logic for `run` and `fleet`
   - Add automatic subnet derivation logic
   - **NEW**: Add CPU and RAM validation and passing to methods

6. **Phase 6**: Lambda support
   - Add new operations to `VALID_OPERATIONS`
   - Implement `ip_create_forwarding` handler
   - Implement `ip_ls_forwarding` handler
   - Implement `ip_clean` handler
   - Update `run` operation with automatic subnet derivation
   - **NEW**: Support CPU and RAM parameters in Lambda events

7. **Phase 7**: Helper utilities
   - Create `port_utils.py` with port parsing/validation

8. **Phase 8**: Testing
   - Write unit tests for port utilities
   - Manual integration testing
   - Document test results

9. **Phase 9**: Documentation updates
   - Update README.md with port forwarding section
   - Update LAMBDA.md with new operations
   - Add examples to user-facing docs

### 6. Example Usage (Final Result)

```bash
# Create network stack with port forwarding IP
acido ip create-forwarding voip-ip --ports 5060:udp --ports 5060:tcp

# Deploy VoIP server with automatic network configuration and custom resources
acido run asterisk-prod \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --public-ip voip-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --cpu 2.0 \
  --ram 4.0 \
  -d 86400

# System automatically uses:
#   VNet: voip-ip-vnet
#   Subnet: voip-ip-subnet
# No need to run 'acido ip select' or read from config!

# List forwarding IPs
acido ip ls-forwarding

# Clean config when done
acido ip clean

# Remove everything
acido rm asterisk-prod
acido ip rm voip-ip
```

### 7. Lambda Example

```json
{
  "operation": "run",
  "name": "voip-server",
  "image": "asterisk",
  "task": "./start-asterisk.sh",
  "public_ip_name": "voip-ip",
  "exposed_ports": [
    {"port": 5060, "protocol": "UDP"},
    {"port": 5060, "protocol": "TCP"}
  ],
  "cpu": 2.0,
  "ram": 4.0,
  "duration": 86400
}
```

Fleet example with custom resources:
```json
{
  "operation": "fleet",
  "fleet_name": "scan-fleet",
  "instance_num": 10,
  "image": "nmap",
  "task": "nmap -iL input",
  "input_file": "targets.txt",
  "max_cpu": 10.0,
  "max_ram": 20.0,
  "regions": ["westeurope", "eastus"]
}
```

### 8. Success Criteria

- ✅ All CLI commands work as documented
- ✅ Automatic subnet derivation functions correctly
- ✅ Config warnings display when appropriate
- ✅ `ip clean` command clears config
- ✅ Port forwarding works end-to-end (inbound connectivity verified)
- ✅ **NEW**: CPU and RAM arguments work for both `run` and `fleet` commands
- ✅ **NEW**: Resource limits are validated (CPU: 0.1-4.0 for run, 0.1-100 for fleet; RAM: 0.1-16 for run, 0.1-256 for fleet)
- ✅ Lambda operations function correctly
- ✅ Unit tests pass
- ✅ Integration tests pass
- ✅ Documentation is complete and accurate
- ✅ Backward compatibility maintained (no breaking changes)

### 9. Important Notes

- **100% Backward Compatible**: Existing containers without `--public-ip` continue to use NAT Gateway for egress
- **No Config Dependency**: Automatic subnet derivation eliminates need to read from config file
- **Cost**: ~$13/month per container with port forwarding (Public IP $3.60 + Container $9.40)
- **Security**: Containers with public IPs are directly exposed to internet - ensure application-level auth and rate limiting
- **NEW - Resource Limits**: Azure Container Instances resource limits:
  - **Single Container (run)**: CPU: 0.1-4.0 cores, RAM: 0.1-16.0 GB
  - **Fleet (total across instances)**: CPU: 0.1-100+ cores, RAM: 0.1-256+ GB
  - Resources are distributed across instances in a fleet (e.g., 10 instances with 10 CPU = 1 CPU per instance)
  - Default for `run`: 1.0 CPU, 1.0 GB RAM
  - Default for `fleet`: 4.0 CPU, 16.0 GB RAM (distributed across instances)

### 10. Reference Documentation

Read these files in order:
1. `docs/PORT_FORWARDING_INDEX.md` - Start here for overview
2. `docs/port_forwarding_implementation.md` - Your main implementation guide
3. `docs/PORT_FORWARDING_PROPOSAL.md` - For understanding alternatives and architecture
4. `docs/port_forwarding_examples.md` - For usage examples
5. `docs/PORT_FORWARDING_DIAGRAMS.md` - For visual architecture reference

### 11. Questions?

If anything is unclear:
1. Check the detailed implementation guide: `docs/port_forwarding_implementation.md`
2. Review the architecture diagrams: `docs/PORT_FORWARDING_DIAGRAMS.md`
3. Look at the examples: `docs/port_forwarding_examples.md`
4. Ask for clarification with specific code sections

---

**Estimated Effort**: 2-3 days for Phase 1 implementation (all features listed above)

**Priority**: High - This enables critical use cases (VoIP, game servers, SSH bastions)

**Risk**: Low - Uses standard Azure features, backward compatible, well-documented
