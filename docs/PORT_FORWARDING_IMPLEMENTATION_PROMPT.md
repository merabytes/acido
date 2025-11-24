# Port Forwarding Implementation Task - PR Prompt

## Overview

Implement port forwarding feature for Azure Container Instances to enable inbound connectivity. This allows containers to accept incoming connections from the internet on specific ports (e.g., VoIP servers, game servers, SSH bastions).

## Background

**Current State**: Acido containers use NAT Gateway for egress-only connectivity (default behavior).

**Goal**: Enable **single containers** (`acido run`) to accept inbound connections by assigning dedicated Azure public IPs using `--bidirectional` flag.

**Key Finding**: Azure NAT Gateway does NOT support inbound connections or DNAT. Must use public IPs directly on container groups.

**Important**: 
- **Default behavior unchanged**: Containers continue using NAT Gateway for egress
- **Fleet unchanged**: `acido fleet` always uses NAT Gateway (single shared IP for massive scanning)
- **Bidirectional only for run**: `acido run --bidirectional` assigns public IP for inbound connectivity

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
# Create public IP ONLY (no NAT Gateway stack) - NEW BEHAVIOR
acido ip create <name>

# Create public IP WITH full NAT Gateway stack (VNet, Subnet, NAT Gateway)
acido ip create <name> --with-nat-stack

# Select IP for use with subnet
acido ip select <name>
# Shows: "IP 'name' [with NAT stack] selected" or "IP 'name' [standalone] selected"

# List public IPs (shows which have NAT Gateway stack)
acido ip ls
# Output includes indicator: "name [with NAT stack]" or "name [standalone]"

# Clean IP configuration from local config  
acido ip clean

# Deploy with bidirectional connectivity (assigns public IP directly)
acido run <name> --bidirectional --expose-port PORT:PROTOCOL

# Default behavior (egress-only via NAT Gateway) - NO CHANGES
acido run <name>  # Uses NAT Gateway
acido fleet <name>  # Always uses NAT Gateway (no --bidirectional option)

# NEW: Configurable CPU and RAM resources
acido run <name> --cpu <cores> --ram <gb>
acido fleet <name> --cpu <cores> --ram <gb>
```

### 2. Core Features

**Bidirectional Flag** (NEW REQUIREMENT):
- Add `--bidirectional` flag to `run` command ONLY
- When `--bidirectional` is specified, assign public IP directly to container
- Requires `--expose-port` to specify which ports to expose
- NOT available for `fleet` command (fleet always uses NAT Gateway)
- Default behavior: egress-only via NAT Gateway (unchanged)

**IP Management** (NEW REQUIREMENT):
- `acido ip create <name>` - Creates ONLY the public IP (no NAT Gateway stack)
- `acido ip create <name> --with-nat-stack` - Creates public IP WITH full NAT Gateway stack (VNet, Subnet, NAT Gateway)
- `acido ip select <name>` - Shows whether IP has NAT stack or is standalone
  - Display: "IP 'name' [with NAT stack] selected" or "IP 'name' [standalone] selected"
- `acido ip ls` - Lists all IPs with indicator showing which have NAT stack
  - Display format: "name [with NAT stack]" or "name [standalone]"
- Tag public IPs with metadata: `{"has_nat_stack": "true"}` or `{"has_nat_stack": "false"}`

**Configurable CPU and RAM** (NEW REQUIREMENT):
- Add `--cpu` argument to `run` and `fleet` commands (default: varies by command)
- Add `--ram` argument to `run` and `fleet` commands (default: varies by command)
- Pass these values to `InstanceManager.deploy()` as `max_cpu` and `max_ram` parameters
- Validate CPU and RAM values are within Azure Container Instances limits

**Config Warning System**:
- Warn if IP is selected in config but not being used
- Suggest: "To clear config: run 'acido ip clean'"

**IP Clean Command**:
- Clears from config: public_ip_name, public_ip_id, vnet_name, subnet_name, subnet_id

### 3. Code Changes Required (~350 LOC)

#### NetworkManager.py (`acido/azure_utils/NetworkManager.py`)

Modify `create_ip()` method to support optional NAT stack creation:

```python
def create_ip(self, name, with_nat_stack=False):
    """
    Create a public IP address, optionally with full NAT Gateway stack.
    
    Args:
        name (str): Name of the public IP resource
        with_nat_stack (bool): If True, create VNet, Subnet, and NAT Gateway along with IP
    
    Returns:
        tuple: (public_ip_id, ip_address_string)
    """
    # Tag IP to indicate whether it has NAT stack
    tags = {'has_nat_stack': 'true' if with_nat_stack else 'false'}
    
    # Create public IP
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
    
    # If with_nat_stack, create VNet, Subnet, and NAT Gateway
    if with_nat_stack:
        vnet_name = f"{name}-vnet"
        subnet_name = f"{name}-subnet"
        nat_gw_name = f"{name}-nat"
        
        # Create VNet
        self.create_vnet(vnet_name)
        
        # Create Subnet
        self.create_subnet(vnet_name, subnet_name)
        
        # Create NAT Gateway and associate with subnet
        self.create_nat_gateway(nat_gw_name, pip.id, vnet_name, subnet_name)
        
        print(info(f"Created full NAT stack: {vnet_name}/{subnet_name}/{nat_gw_name}"))
    else:
        print(info(f"Created standalone public IP: {name}"))
    
    return pip.id, pip.ip_address

def list_ips_with_stack_info(self):
    """List all public IPs with indicator if they have NAT stack."""
    all_ips = self._client.public_ip_addresses.list(self.resource_group)
    ips_info = []
    
    for ip in all_ips:
        has_nat_stack = ip.tags.get('has_nat_stack', 'false') == 'true' if ip.tags else False
        ips_info.append({
            'id': ip.id,
            'name': ip.name,
            'ip_address': ip.ip_address,
            'location': ip.location,
            'has_nat_stack': has_nat_stack,
            'display': f"{ip.name} [{'with NAT stack' if has_nat_stack else 'standalone'}]"
        })
    
    return ips_info
```

#### InstanceManager.py (`acido/azure_utils/InstanceManager.py`)

Modify `deploy()` method to accept new parameters:

```python
def deploy(self, name, ..., bidirectional=False, exposed_ports=None):
    """
    Deploy container group with optional bidirectional connectivity.
    
    New Args:
        bidirectional (bool, optional): If True, assign public IP for inbound connectivity
        exposed_ports (list, optional): List of port dicts [{"port": 5060, "protocol": "UDP"}]
    """
    # ... existing code ...
    
    # Configure IP address
    ip_cfg = None
    
    if bidirectional and exposed_ports:
        # Bidirectional mode: Public IP with specific ports (no subnet)
        print(info("Configuring bidirectional connectivity with public IP"))
        ip_cfg = IpAddress(
            type="Public",
            ports=[Port(protocol=p["protocol"], port=p["port"]) 
                   for p in exposed_ports]
        )
        # When using public IP, do NOT use subnet
        subnet_ids = None
    elif expose_private_port:
        # Private IP mode (existing functionality)
        ip_cfg = IpAddress(type="Private", ports=[Port(protocol="TCP", port=expose_private_port)])
        # Keep subnet for VNet connectivity
    else:
        # Default: No IP mode - Pure NAT Gateway egress (CURRENT BEHAVIOR)
        ip_cfg = None
        # Keep subnet for NAT Gateway
    
    # ... rest of existing code ...
    
    cg = ContainerGroup(
        location=location,
        containers=deploy_instances,
        os_type=os_type,
        ip_address=ip_cfg,  # Public IP only if bidirectional=True
        image_registry_credentials=ir_credentials,
        restart_policy=restart_policy,
        tags=tags,
        subnet_ids=subnet_ids,  # None if bidirectional, otherwise use subnet
        identity=...
    )
```

#### cli.py (`acido/cli.py`)

Add new subcommands and handler methods:

```python
# IP create subcommand - MODIFIED to support optional NAT stack
ip_create_parser = ip_subparsers.add_parser('create', help='Create a public IP address')
ip_create_parser.add_argument('name', help='Name for the public IP address')
ip_create_parser.add_argument('--with-nat-stack', dest='with_nat_stack', action='store_true',
                              help='Create full NAT Gateway stack (VNet, Subnet, NAT Gateway) along with IP')

# IP ls subcommand - MODIFIED to show NAT stack info
# (existing parser, just update the handler to use list_ips_with_stack_info())

# IP select subcommand - MODIFIED to show NAT stack info
# (existing parser, just update the handler to display stack info)

# IP clean subcommand (keep existing)
ip_clean_parser = ip_subparsers.add_parser('clean', help='Clean IP configuration from local config')

# Add to run_parser ONLY (NOT fleet)
run_parser.add_argument('--bidirectional', dest='bidirectional', action='store_true',
                       help='Enable bidirectional connectivity (assigns public IP for inbound connections)')
run_parser.add_argument('--expose-port', dest='expose_ports', action='append',
                       help='Port to expose (format: PORT:PROTOCOL). Requires --bidirectional.')

# NEW: Add CPU and RAM arguments to run_parser
run_parser.add_argument('--cpu', dest='cpu', type=float, default=1.0,
                       help='CPU cores to allocate (default: 1.0, max: 4.0)')
run_parser.add_argument('--ram', dest='ram', type=float, default=1.0,
                       help='RAM in GB to allocate (default: 1.0, max: 16.0)')

# NEW: Add CPU and RAM arguments to fleet_parser (NO --bidirectional flag)
fleet_parser.add_argument('--cpu', dest='cpu', type=float, default=4.0,
                         help='Total CPU cores for fleet (default: 4.0, distributed across instances)')
fleet_parser.add_argument('--ram', dest='ram', type=float, default=16.0,
                         help='Total RAM in GB for fleet (default: 16.0, distributed across instances)')
```

Add Acido class methods:

```python
def create_ip(self, name, with_nat_stack=False):
    """Create a public IP, optionally with NAT Gateway stack."""
    if self.network_manager:
        ip_id, ip_address = self.network_manager.create_ip(name, with_nat_stack=with_nat_stack)
        print(good(f"Public IP created: {name} ({ip_address})"))
        if with_nat_stack:
            print(info(f"Created with full NAT Gateway stack"))
        return ip_id, ip_address
    else:
        print(bad("Network manager not available"))
        return None, None

def list_ips(self):
    """List all public IPs with NAT stack indicator."""
    if self.network_manager:
        ips = self.network_manager.list_ips_with_stack_info()
        if ips:
            print(info("Public IP Addresses:"))
            for ip in ips:
                print(f"  - {ip['display']} ({ip['ip_address']})")
        else:
            print(info("No public IP addresses found"))
        return ips
    else:
        print(bad("Network manager not available"))
        return []

def select_ip(self, name):
    """Select an IP and show whether it has NAT stack."""
    if self.network_manager:
        ip = self.network_manager.get_public_ip(name)
        if ip:
            has_nat_stack = ip.tags.get('has_nat_stack', 'false') == 'true' if ip.tags else False
            stack_info = "with NAT stack" if has_nat_stack else "standalone"
            
            self.public_ip_name = name
            self.public_ip_id = ip.id
            self._save_config()
            
            print(good(f"IP '{name}' [{stack_info}] selected"))
            print(info(f"IP Address: {ip.ip_address}"))
        else:
            print(bad(f"IP '{name}' not found"))
    else:
        print(bad("Network manager not available"))

def clean_ip_config(self):
    """Clean IP configuration from local config."""
    self.public_ip_name = None
    self.public_ip_id = None
    self.vnet_name = None
    self.subnet_name = None
    self.subnet_id = None
    self._save_config()
    print(good("IP configuration cleaned"))
```

Add command handlers in main execution block:

```python
# Handle IP subcommands
if args.subcommand == 'ip':
    if args.ip_subcommand == 'create':
        acido.create_ip(args.name, with_nat_stack=args.with_nat_stack)
    elif args.ip_subcommand == 'ls':
        acido.list_ips()
    elif args.ip_subcommand == 'select':
        acido.select_ip(args.name)
    elif args.ip_subcommand == 'clean':
        acido.clean_ip_config()

# Handle run command with bidirectional
elif args.subcommand == 'run':
    # Parse exposed ports
    exposed_ports = None
    if args.expose_ports:
        exposed_ports = []
        for spec in args.expose_ports:
            port, protocol = spec.split(':')
            exposed_ports.append({"port": int(port), "protocol": protocol.upper()})
    
    # Validate: If expose_ports is set, bidirectional must also be set
    if exposed_ports and not args.bidirectional:
        print(bad("--expose-port requires --bidirectional to be specified"))
        sys.exit(1)
    
    # Validate: If bidirectional is set, expose_ports must also be set
    if args.bidirectional and not exposed_ports:
        print(bad("--bidirectional requires --expose-port to be specified"))
        sys.exit(1)
    
    # Call run with bidirectional parameters
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
        bidirectional=args.bidirectional,  # NEW: Pass bidirectional flag
        exposed_ports=exposed_ports,
        cpu=args.cpu,  # NEW: Pass CPU argument
        ram=args.ram   # NEW: Pass RAM argument
    )

# Fleet command - NO CHANGES (always uses NAT Gateway)
elif args.subcommand == 'fleet':
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
        max_cpu=args.cpu,  # NEW: Pass CPU argument (total for fleet)
        max_ram=args.ram   # NEW: Pass RAM argument (total for fleet)
    )
```

Update `run()` method signature to accept new parameters:

```python
def run(self, name: str, image_name: str, task: str = None, duration: int = 900,
        write_to_file: str = None, output_format: str = 'txt', 
        quiet: bool = False, cleanup: bool = True, regions=None,
        bidirectional: bool = False, exposed_ports: list = None,
        cpu: float = 1.0, ram: float = 1.0):  # NEW: CPU and RAM parameters
    """
    Run a single ephemeral container instance.
    
    New Args:
        bidirectional (bool, optional): Enable bidirectional connectivity (assigns public IP)
        exposed_ports (list, optional): List of port dicts to expose (requires bidirectional=True)
        cpu (float, optional): CPU cores to allocate (default: 1.0, max: 4.0)
        ram (float, optional): RAM in GB to allocate (default: 1.0, max: 16.0)
    """
    # Validate CPU and RAM
    if cpu < 0.1 or cpu > 4.0:
        raise ValueError(f"CPU must be between 0.1 and 4.0, got {cpu}")
    if ram < 0.1 or ram > 16.0:
        raise ValueError(f"RAM must be between 0.1 and 16.0 GB, got {ram}")
    
    # ... existing code ...
    
    # Pass bidirectional and ports to instance_manager.deploy()
    result = self.instance_manager.deploy(
        name=name,
        image_name=full_image_url,
        command=task,
        location=selected_region,
        env_vars=env_vars,
        quiet=quiet,
        bidirectional=bidirectional,  # NEW: Pass bidirectional flag
        exposed_ports=exposed_ports,
        max_cpu=cpu,  # Pass CPU
        max_ram=ram,  # Pass RAM
        instance_number=1  # Single instance for run command
    )

def fleet(self, fleet_name: str, instance_num: int, image_name: str,
          scan_cmd: str = None, input_file: str = None, wait: int = None,
          write_to_file: str = None, output_format: str = 'txt',
          quiet: bool = False, rm_when_done: bool = False, regions=None,
          max_cpu: float = 4.0, max_ram: float = 16.0):  # NEW: CPU and RAM parameters
    """
    Deploy a fleet of container instances.
    
    NOTE: Fleet ALWAYS uses NAT Gateway for egress (no bidirectional support).
    
    New Args:
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
    # NOTE: bidirectional is NOT passed - fleet always uses NAT Gateway
    results = self.instance_manager.deploy(
        name=fleet_name,
        image_name=full_image_url,
        command=scan_cmd,
        location=selected_region,
        env_vars=env_vars,
        quiet=quiet,
        max_cpu=max_cpu,  # Pass total CPU
        max_ram=max_ram,  # Pass total RAM
        instance_number=instance_num
    )
```
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

Update existing operations:

```python
VALID_OPERATIONS = [
    'fleet', 'run', 'ls', 'rm', 
    'ip_create', 'ip_ls', 'ip_rm',
    'ip_clean'  # Only add ip_clean
]

def lambda_handler(event, context):
    # ... existing code ...
    
    elif operation == 'ip_clean':
        acido.clean_ip_config()
        return build_response({'operation': operation, 'result': {'message': 'IP configuration cleaned'}})
    
    elif operation == 'run':
        bidirectional = event.get('bidirectional', False)  # NEW: Get bidirectional flag
        exposed_ports = event.get('exposed_ports', [])
        cpu = event.get('cpu', 1.0)  # NEW: Get CPU from event
        ram = event.get('ram', 1.0)  # NEW: Get RAM from event
        
        response, outputs = acido.run(
            name=name,
            image_name=full_image_url,
            task=task,
            duration=duration,
            bidirectional=bidirectional,  # NEW: Pass bidirectional flag
            exposed_ports=exposed_ports,
            cpu=cpu,  # NEW: Pass CPU
            ram=ram   # NEW: Pass RAM
        )
        # ... return response ...
    
    elif operation == 'fleet':
        # Fleet unchanged - always uses NAT Gateway
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
            max_cpu=max_cpu,  # NEW: Pass CPU
            max_ram=max_ram   # NEW: Pass RAM
        )
        # ... return response ...
```
        
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
# 1. Test creating standalone IP (no NAT stack)
acido ip create test-ip

# 2. Verify IP was created and shows as standalone
acido ip ls
# Should show: "test-ip [standalone]"

# 3. Test creating IP with NAT stack
acido ip create full-stack-ip --with-nat-stack

# 4. Verify IP shows with NAT stack
acido ip ls
# Should show: "full-stack-ip [with NAT stack]"

# 5. Select IP and verify indicator
acido ip select test-ip
# Should show: "IP 'test-ip' [standalone] selected"

# 6. Deploy test container with bidirectional
acido run test-server \
  -im nginx:alpine \
  --bidirectional \
  --expose-port 8080:tcp \
  -d 600

# 7. Get public IP and test connectivity
# (container gets its own public IP for bidirectional)
# Test by accessing the container's public IP on port 8080

# 8. Test config clean
acido ip clean

# 9. Cleanup
acido rm test-server
acido ip rm test-ip
acido ip rm full-stack-ip
```

### 5. Implementation Steps

1. **Phase 1**: NetworkManager extensions
   - Modify `create_ip()` to accept `with_nat_stack` parameter
   - Implement `list_ips_with_stack_info()` to show NAT stack indicator
   - Update IP tagging with `has_nat_stack` metadata

2. **Phase 2**: InstanceManager modifications
   - Modify `deploy()` to accept `bidirectional` and `exposed_ports`
   - Add IP configuration logic for bidirectional mode

3. **Phase 3**: CLI commands
   - Modify `ip create` subcommand to accept `--with-nat-stack` flag
   - Update `ip ls` to show NAT stack indicator
   - Update `ip select` to show NAT stack indicator
   - Add `ip clean` subcommand
   - Add `--bidirectional` and `--expose-port` arguments to `run` command ONLY
   - **NEW**: Add `--cpu` and `--ram` arguments to `run` command
   - **NEW**: Add `--cpu` and `--ram` arguments to `fleet` command

4. **Phase 4**: Acido class methods
   - Update `create_ip()` to pass `with_nat_stack` parameter
   - Update `list_ips()` to use `list_ips_with_stack_info()`
   - Update `select_ip()` to display NAT stack indicator
   - Implement `clean_ip_config()`
   - Update `run()` method signature with bidirectional, CPU and RAM parameters
   - Update `fleet()` method signature with CPU and RAM parameters (NO bidirectional)

5. **Phase 5**: Command handlers
   - Update IP create/ls/select handlers with NAT stack info
   - Add IP clean subcommand handler
   - Add bidirectional validation logic for `run`
   - **NEW**: Add CPU and RAM validation and passing to methods

6. **Phase 6**: Lambda support
   - Add `ip_clean` to `VALID_OPERATIONS`
   - Implement `ip_clean` handler
   - Update `run` operation with bidirectional support
   - **NEW**: Support CPU and RAM parameters in Lambda events

7. **Phase 7**: Testing
   - Write unit tests for bidirectional flag
   - Manual integration testing
   - Document test results

8. **Phase 8**: Documentation updates
   - Update README.md with bidirectional section
   - Update LAMBDA.md with new operations
   - Add examples to user-facing docs

### 6. Example Usage (Final Result)

```bash
# Create standalone IP (for bidirectional containers)
acido ip create voip-ip

# Create IP with full NAT Gateway stack (for fleet scanning)
acido ip create fleet-ip --with-nat-stack

# List IPs with stack indicator
acido ip ls
# Output:
#   - voip-ip [standalone] (x.x.x.x)
#   - fleet-ip [with NAT stack] (y.y.y.y)

# Select IP and see stack status
acido ip select voip-ip
# Output: "IP 'voip-ip' [standalone] selected"

# Deploy VoIP server with bidirectional connectivity and custom resources
acido run asterisk-prod \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --bidirectional \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --cpu 2.0 \
  --ram 4.0 \
  -d 86400

# System assigns public IP directly to container (no subnet/NAT Gateway)
# Supports both inbound and outbound connectivity

# Default behavior unchanged (egress-only via NAT Gateway)
acido run nginx-server \
  -im nginx:latest \
  -d 3600

# Fleet always uses NAT Gateway (no --bidirectional option)
acido fleet scan-fleet \
  -im nmap:latest \
  -t "nmap -iL input" \
  --cpu 10.0 \
  --ram 20.0 \
  -n 10

# Clean config when done
acido ip clean

# Remove everything
acido rm asterisk-prod
acido ip rm voip-ip
acido ip rm fleet-ip
```

### 7. Lambda Example

```json
{
  "operation": "run",
  "name": "voip-server",
  "image": "asterisk",
  "task": "./start-asterisk.sh",
  "bidirectional": true,
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
- ✅ `ip clean` command clears config
- ✅ **Bidirectional connectivity** works end-to-end (inbound connectivity verified)
- ✅ **Default behavior unchanged** (egress-only via NAT Gateway works)
- ✅ **Fleet always uses NAT Gateway** (no bidirectional support)
- ✅ **NEW**: CPU and RAM arguments work for both `run` and `fleet` commands
- ✅ **NEW**: Resource limits are validated (CPU: 0.1-4.0 for run, 0.1-100 for fleet; RAM: 0.1-16 for run, 0.1-256 for fleet)
- ✅ Lambda operations function correctly
- ✅ Unit tests pass
- ✅ Integration tests pass
- ✅ Documentation is complete and accurate
- ✅ **100% Backward compatibility maintained** (no breaking changes)

### 9. Important Notes

- **100% Backward Compatible**: Default behavior unchanged - containers use NAT Gateway for egress-only
- **Bidirectional Only for Run**: `--bidirectional` flag only available for `acido run`, NOT for `acido fleet`
- **Fleet Always Uses NAT Gateway**: Fleet containers share single egress IP (useful for massive scanning)
- **NEW - IP Creation Flexibility**:
  - `acido ip create <name>` - Creates standalone IP (no NAT Gateway stack) - suitable for bidirectional containers
  - `acido ip create <name> --with-nat-stack` - Creates IP WITH full NAT Gateway stack (VNet, Subnet, NAT Gateway) - suitable for fleet egress
  - All IPs are tagged with `has_nat_stack` metadata for easy identification
  - `acido ip ls` shows which IPs have NAT stack: "name [with NAT stack]" or "name [standalone]"
  - `acido ip select` shows stack status when selecting an IP
- **Cost**: 
  - Default (egress-only): ~$9.40/month per container
  - With `--bidirectional`: ~$13/month per container (adds Public IP $3.60)
  - NAT Gateway stack: Additional costs for VNet, Subnet, NAT Gateway (~$30-50/month)
- **Security**: Containers with `--bidirectional` are directly exposed to internet - ensure application-level auth and rate limiting
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

**Estimated Effort**: 1-2 days for Phase 1 implementation (simplified approach)

**Priority**: High - This enables critical use cases (VoIP, game servers, SSH bastions)

**Risk**: Low - Uses standard Azure features, backward compatible, flexible IP management
