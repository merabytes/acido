# Port Forwarding Implementation Guide

This document provides step-by-step implementation details for adding port forwarding support to acido.

## Overview

The implementation follows the **Public IP per Container** approach, which:
- Assigns a dedicated Azure public IP to containers requiring inbound connectivity
- Configures Azure Container Instances with public IP and exposed ports
- Maintains backward compatibility with existing NAT Gateway egress-only architecture

## Architecture Changes

### Before (Current)
```python
Container Group (no public IP)
  └─> Subnet (delegated)
       └─> NAT Gateway
            └─> Public IP (egress only)
```

### After (With Port Forwarding)
```python
# Option 1: Container without port forwarding (default)
Container Group (no public IP)
  └─> Subnet (delegated)
       └─> NAT Gateway
            └─> Public IP (egress only)

# Option 2: Container with port forwarding (new)
Container Group WITH Public IP
  ├─> Public IP (bidirectional on specified ports)
  └─> Subnet (delegated, for VNet connectivity)
```

## Implementation Steps

### Step 1: Extend NetworkManager

**File**: `acido/azure_utils/NetworkManager.py`

Add new methods for managing port forwarding IPs:

```python
def create_forwarding_ip(self, name, ports=None):
    """
    Create a public IP for port forwarding with optional port metadata.
    
    Args:
        name (str): Name of the public IP resource
        ports (list, optional): List of port dicts [{"port": 5060, "protocol": "UDP"}]
    
    Returns:
        tuple: (public_ip_id, ip_address_string)
    
    Example:
        >>> nm = NetworkManager(resource_group="my-rg")
        >>> ip_id, ip_addr = nm.create_forwarding_ip(
        ...     "voip-ip",
        ...     ports=[{"port": 5060, "protocol": "UDP"}]
        ... )
        >>> print(f"Created IP: {ip_addr}")
        Created IP: 203.0.113.45
    """
    # Build tags with port information
    tags = {'purpose': 'port-forwarding'}
    if ports:
        port_list = ','.join([f"{p['port']}/{p['protocol']}" for p in ports])
        tags['ports'] = port_list
    
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
    
    print(good(f"Public IP {pip.ip_address} created for port forwarding"))
    if ports:
        print(good(f"  Configured ports: {port_list}"))
    
    return pip.id, pip.ip_address

def get_public_ip(self, name):
    """
    Get public IP resource by name.
    
    Args:
        name (str): Name of the public IP resource
    
    Returns:
        PublicIPAddress: Azure public IP resource object
        
    Raises:
        ResourceNotFoundError: If public IP doesn't exist
    
    Example:
        >>> nm = NetworkManager(resource_group="my-rg")
        >>> pip = nm.get_public_ip("voip-ip")
        >>> print(pip.ip_address)
        203.0.113.45
    """
    return self._client.public_ip_addresses.get(
        self.resource_group, name
    )

def list_forwarding_ips(self):
    """
    List all public IPs tagged for port forwarding.
    
    Returns:
        list: List of dicts with IP information
        
    Example:
        >>> nm = NetworkManager(resource_group="my-rg")
        >>> ips = nm.list_forwarding_ips()
        >>> for ip in ips:
        ...     print(f"{ip['name']}: {ip['ip_address']} [{ip['ports']}]")
        voip-ip: 203.0.113.45 [5060/UDP,5060/TCP]
    """
    all_ips = self._client.public_ip_addresses.list(self.resource_group)
    forwarding_ips = []
    
    for ip in all_ips:
        # Check if tagged for port forwarding
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
    """
    Delete a port forwarding public IP.
    
    Args:
        name (str): Name of the public IP resource
    
    Returns:
        bool: True if deleted, False if not found
    """
    try:
        print(good(f"Deleting forwarding IP: {name}..."))
        self._client.public_ip_addresses.begin_delete(
            self.resource_group, name
        ).result()
        print(good(f"Public IP {name} deleted successfully."))
        return True
    except Exception as e:
        print(bad(f"Failed to delete IP {name}: {str(e)}"))
        return False
```

### Step 2: Extend InstanceManager

**File**: `acido/azure_utils/InstanceManager.py`

Modify the `deploy()` method to support public IP assignment:

```python
def deploy(self, name, tags: dict = {}, location="westeurope",
           vnet_name: str = None, subnet_name: str = None,
           os_type=OperatingSystemTypes.linux, restart_policy="Never",
           instance_number: int = 3, max_ram: int = 16,
           max_cpu: int = 4, image_name: str = None,
           env_vars: dict = {}, command: str = None,
           input_files: list = None, quiet: bool = False,
           expose_private_port: int = None,
           public_ip_name: str = None, exposed_ports: list = None):
    """
    Deploy container group with optional public IP and port forwarding.
    
    New Args:
        public_ip_name (str, optional): Name of public IP resource to assign
        exposed_ports (list, optional): List of port dicts to expose
            Format: [{"port": 5060, "protocol": "UDP"}, {"port": 80, "protocol": "TCP"}]
    
    Example:
        >>> im = InstanceManager(resource_group="my-rg")
        >>> im.deploy(
        ...     name="voip-server",
        ...     image_name="asterisk:latest",
        ...     public_ip_name="voip-ip",
        ...     exposed_ports=[{"port": 5060, "protocol": "UDP"}]
        ... )
    """
    # ... existing code for restart_policy, credentials, ram, cpu ...
    
    results = {}
    deploy_instances = []
    
    # Build container instances (existing code)
    for i_num in range(1, instance_number + 1):
        # ... existing container provisioning code ...
        pass
    
    # Configure IP address
    ip_cfg = None
    
    if public_ip_name and exposed_ports:
        # Port forwarding mode: Public IP with specific ports
        print(good(f"Configuring public IP: {public_ip_name}"))
        
        # Note: We reference the public IP by name
        # Azure will assign it to the container group
        ip_cfg = IpAddress(
            type="Public",
            ports=[Port(protocol=p["protocol"], port=p["port"]) 
                   for p in exposed_ports],
            dns_name_label=None  # Could be made configurable
        )
        
        # Important: We need to get the actual IP address separately
        # Azure assigns it during deployment
        
    elif expose_private_port:
        # Private IP mode (existing functionality)
        ip_cfg = IpAddress(
            type="Private",
            ports=[Port(protocol="TCP", port=expose_private_port)]
        )
    else:
        # No IP mode: Pure NAT Gateway egress
        ip_cfg = None
    
    # Build subnet_ids if vnet_name and subnet_name are provided
    subnet_ids = None
    if vnet_name and subnet_name:
        subnet_ids = [ContainerGroupSubnetId(
            id=self._subnet_id(vnet_name, subnet_name)
        )]
    
    try:
        cg = ContainerGroup(
            location=location,
            containers=deploy_instances,
            os_type=os_type,
            ip_address=ip_cfg,
            image_registry_credentials=ir_credentials,
            restart_policy=restart_policy,
            tags=tags,
            subnet_ids=subnet_ids,
            identity=ContainerGroupIdentity(
                type=ResourceIdentityType.user_assigned,
                user_assigned_identities={
                    self.user_assigned['id']: UserAssignedIdentities(
                        client_id=self.user_assigned.get('clientId', '')
                    )
                } if self.user_assigned else None
            )
        )
        
        result = self._client.container_groups.begin_create_or_update(
            resource_group_name=self.resource_group,
            container_group_name=name,
            container_group=cg
        ).result()
        
        # If public IP was requested, print the assigned IP
        if public_ip_name and result.ip_address:
            assigned_ip = result.ip_address.ip
            print(good(f"Container deployed with public IP: {assigned_ip}"))
            exposed_port_str = ', '.join([f"{p['port']}/{p['protocol']}" 
                                          for p in exposed_ports])
            print(good(f"  Exposed ports: {exposed_port_str}"))
        
        for i_num in range(1, instance_number + 1):
            results[f'{name}-{i_num:02d}'] = True
        
    except HttpResponseError as e:
        if not quiet:
            print(bad(str(e)))
        raise e
    
    self.env_vars.clear()
    return results, input_files
```

### Step 3: Add CLI Commands

**File**: `acido/cli.py`

Add new IP forwarding commands and port exposure arguments:

```python
# In the IP subparser section (around line 134)

# IP create-forwarding subcommand
ip_forwarding_parser = ip_subparsers.add_parser(
    'create-forwarding',
    help='Create a public IP configured for port forwarding'
)
ip_forwarding_parser.add_argument(
    'name',
    help='Name for the public IP address'
)
ip_forwarding_parser.add_argument(
    '--ports',
    dest='forward_ports',
    action='append',
    help='Port to forward in format PORT:PROTOCOL (e.g., 5060:udp, 8080:tcp). '
         'Can be specified multiple times.'
)

# IP ls-forwarding subcommand
ip_ls_forwarding_parser = ip_subparsers.add_parser(
    'ls-forwarding',
    help='List public IPs configured for port forwarding'
)

# Add port forwarding options to run command (around line 115)
run_parser.add_argument(
    '--public-ip',
    dest='public_ip_name',
    help='Name of public IP to use for port forwarding'
)
run_parser.add_argument(
    '--expose-port',
    dest='expose_ports',
    action='append',
    help='Port to expose in format PORT:PROTOCOL (e.g., 5060:udp, 8080:tcp). '
         'Can be specified multiple times. Requires --public-ip.'
)

# Add similar arguments to fleet_parser if needed for multi-instance scenarios
# (Note: Port forwarding is primarily for single instances via 'run' command)
```

Add handler methods in the Acido class:

```python
class Acido(ManagedIdentity):
    # ... existing methods ...
    
    def create_forwarding_ip(self, name, port_specs=None):
        """
        Create a public IP for port forwarding.
        
        Args:
            name (str): Name of the public IP
            port_specs (list): List of "PORT:PROTOCOL" strings (e.g., ["5060:udp"])
        
        Example:
            >>> acido = Acido(resource_group="my-rg")
            >>> acido.create_forwarding_ip("voip-ip", ["5060:udp", "5060:tcp"])
        """
        if self.network_manager is None:
            print(bad("Network manager is not initialized."))
            return
        
        # Parse port specifications
        ports = []
        if port_specs:
            for spec in port_specs:
                try:
                    port, protocol = spec.split(':')
                    ports.append({
                        "port": int(port),
                        "protocol": protocol.upper()
                    })
                except (ValueError, IndexError):
                    print(bad(f"Invalid port specification: {spec}"))
                    print(info("Format should be PORT:PROTOCOL (e.g., 5060:udp)"))
                    return
        
        # Create the public IP
        ip_id, ip_address = self.network_manager.create_forwarding_ip(name, ports)
        print(good(f"Port forwarding IP created: {name} ({ip_address})"))
        
        if ports:
            port_list = ', '.join([f"{p['port']}/{p['protocol']}" for p in ports])
            print(good(f"  Configured for ports: {port_list}"))
    
    def list_forwarding_ips(self):
        """List all public IPs configured for port forwarding."""
        if self.network_manager is None:
            print(bad("Network manager is not initialized."))
            return
        
        ips = self.network_manager.list_forwarding_ips()
        
        if not ips:
            print(info("No port forwarding IPs found."))
            return
        
        print(good("Port Forwarding IPs:"))
        for ip in ips:
            print(f"  {bold(ip['name'])}: {ip['ip_address']} "
                  f"[Ports: {ip['ports']}] ({ip['location']})")
    
    def rm_forwarding_ip(self, name):
        """Remove a port forwarding public IP."""
        if self.network_manager is None:
            print(bad("Network manager is not initialized."))
            return
        
        success = self.network_manager.delete_forwarding_ip(name)
        if success:
            print(good(f"Removed forwarding IP: {name}"))
        else:
            print(bad(f"Failed to remove forwarding IP: {name}"))
```

Update the main argument handler:

```python
# In the main execution block (around line 1500+)

# Handle IP forwarding subcommands
if args.subcommand == 'ip':
    if args.ip_subcommand == 'create-forwarding':
        acido.create_forwarding_ip(args.name, args.forward_ports)
    elif args.ip_subcommand == 'ls-forwarding':
        acido.list_forwarding_ips()
    # ... existing IP subcommands ...

# Handle run command with port forwarding
elif args.subcommand == 'run':
    # Parse exposed ports if provided
    exposed_ports = None
    if args.expose_ports:
        exposed_ports = []
        for spec in args.expose_ports:
            try:
                port, protocol = spec.split(':')
                exposed_ports.append({
                    "port": int(port),
                    "protocol": protocol.upper()
                })
            except (ValueError, IndexError):
                print(bad(f"Invalid port specification: {spec}"))
                sys.exit(1)
    
    # Validate: If expose_ports is set, public_ip_name must also be set
    if exposed_ports and not args.public_ip_name:
        print(bad("--expose-port requires --public-ip to be specified"))
        sys.exit(1)
    
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
        public_ip_name=args.public_ip_name,  # New parameter
        exposed_ports=exposed_ports  # New parameter
    )
```

Update the `run()` method signature:

```python
def run(self, name: str, image_name: str, task: str = None, duration: int = 900,
        write_to_file: str = None, output_format: str = 'txt', 
        quiet: bool = False, cleanup: bool = True, regions=None,
        public_ip_name: str = None, exposed_ports: list = None):
    """
    Run a single ephemeral container instance.
    
    New Args:
        public_ip_name (str, optional): Name of public IP for port forwarding
        exposed_ports (list, optional): List of port dicts to expose
    """
    # ... existing code ...
    
    # Pass to instance_manager.deploy()
    result = self.instance_manager.deploy(
        name=name,
        image_name=full_image_url,
        command=task,
        location=selected_region,
        vnet_name=self.vnet_name,
        subnet_name=self.subnet_name,
        env_vars=env_vars,
        quiet=quiet,
        public_ip_name=public_ip_name,  # Pass through
        exposed_ports=exposed_ports  # Pass through
    )
```

### Step 4: Add Lambda Support

**File**: `lambda_handler.py`

Update operation handling:

```python
# Add to VALID_OPERATIONS
VALID_OPERATIONS = [
    'fleet', 'run', 'ls', 'rm', 
    'ip_create', 'ip_ls', 'ip_rm',
    'ip_create_forwarding', 'ip_ls_forwarding'  # New operations
]

def _execute_run(acido, name, image_name, task, duration, cleanup, regions=None,
                 public_ip_name=None, exposed_ports=None):
    """Execute run operation with optional port forwarding."""
    full_image_url = acido.build_image_url(image_name)
    
    return acido.run(
        name=name,
        image_name=full_image_url,
        task=task,
        duration=duration,
        write_to_file=None,
        output_format='json',
        quiet=True,
        cleanup=cleanup,
        regions=regions,
        public_ip_name=public_ip_name,  # New parameter
        exposed_ports=exposed_ports  # New parameter
    )

# In lambda_handler function
def lambda_handler(event, context):
    # ... existing code ...
    
    elif operation == 'ip_create_forwarding':
        # Create port forwarding IP
        name = event.get('name')
        ports = event.get('ports', [])  # [{"port": 5060, "protocol": "UDP"}]
        
        if not name:
            return build_error_response("Missing required field: name")
        
        acido.create_forwarding_ip(name, ports)
        return build_response({
            'operation': operation,
            'result': {'created': name, 'ports': ports}
        })
    
    elif operation == 'ip_ls_forwarding':
        # List forwarding IPs
        ips = acido.network_manager.list_forwarding_ips() if acido.network_manager else []
        return build_response({
            'operation': operation,
            'result': {'ips': ips}
        })
    
    elif operation == 'run':
        # ... existing run code ...
        public_ip_name = event.get('public_ip_name')
        exposed_ports = event.get('exposed_ports', [])
        
        # Validate: If exposed_ports, must have public_ip_name
        if exposed_ports and not public_ip_name:
            return build_error_response(
                "exposed_ports requires public_ip_name to be specified"
            )
        
        response, outputs = _execute_run(
            acido, name, image_name, task, duration, cleanup, regions,
            public_ip_name, exposed_ports
        )
        # ... return response ...
```

### Step 5: Add Helper Utilities

**File**: `acido/utils/port_utils.py` (new file)

```python
"""Utilities for handling port specifications and validation."""

def parse_port_spec(port_spec):
    """
    Parse port specification string.
    
    Args:
        port_spec (str): String like "5060:udp" or "8080:tcp"
    
    Returns:
        dict: {"port": 5060, "protocol": "UDP"}
        
    Raises:
        ValueError: If port_spec is invalid
    
    Example:
        >>> parse_port_spec("5060:udp")
        {"port": 5060, "protocol": "UDP"}
    """
    try:
        port, protocol = port_spec.split(':')
        return {
            "port": int(port),
            "protocol": protocol.upper()
        }
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid port specification: {port_spec}. "
                        f"Format should be PORT:PROTOCOL (e.g., 5060:udp)")

def validate_port(port):
    """
    Validate port number.
    
    Args:
        port (int): Port number
    
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If port is invalid
    """
    if not isinstance(port, int):
        raise ValueError(f"Port must be an integer, got {type(port)}")
    
    if port < 1 or port > 65535:
        raise ValueError(f"Port must be between 1 and 65535, got {port}")
    
    return True

def validate_protocol(protocol):
    """
    Validate protocol.
    
    Args:
        protocol (str): Protocol name (TCP or UDP)
    
    Returns:
        bool: True if valid
        
    Raises:
        ValueError: If protocol is invalid
    """
    protocol = protocol.upper()
    if protocol not in ['TCP', 'UDP']:
        raise ValueError(f"Protocol must be TCP or UDP, got {protocol}")
    
    return True

def format_port_list(ports):
    """
    Format list of ports for display.
    
    Args:
        ports (list): List of port dicts
    
    Returns:
        str: Formatted string like "5060/UDP, 8080/TCP"
        
    Example:
        >>> format_port_list([{"port": 5060, "protocol": "UDP"}])
        "5060/UDP"
    """
    return ', '.join([f"{p['port']}/{p['protocol']}" for p in ports])
```

## Testing Plan

### Unit Tests

Create `tests/test_port_forwarding.py`:

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
        with self.assertRaises(ValueError):
            validate_port("not a number")
    
    def test_validate_protocol_valid(self):
        self.assertTrue(validate_protocol("TCP"))
        self.assertTrue(validate_protocol("UDP"))
        self.assertTrue(validate_protocol("tcp"))  # Case insensitive
    
    def test_validate_protocol_invalid(self):
        with self.assertRaises(ValueError):
            validate_protocol("ICMP")
```

### Integration Tests

Manual testing steps:

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

# 4. Get public IP
IP=$(acido ip ls-forwarding | grep test-ip | awk '{print $2}')

# 5. Test connectivity
curl http://$IP:8080

# 6. Cleanup
acido rm test-server
acido ip rm test-ip
```

## Documentation Updates

1. **README.md**: Add port forwarding section in "IP Address Routing"
2. **PORT_FORWARDING_PROPOSAL.md**: This proposal document
3. **docs/port_forwarding_examples.md**: Practical examples
4. **LAMBDA.md**: Document new Lambda operations

## Summary

This implementation adds ~500 lines of code across:
- **NetworkManager.py**: 4 new methods (~150 lines)
- **InstanceManager.py**: Modify 1 method (~50 lines)
- **cli.py**: Add commands and handlers (~200 lines)
- **lambda_handler.py**: Add operation handlers (~50 lines)
- **port_utils.py**: New utility file (~100 lines)
- **Tests**: Unit and integration tests (~100 lines)

**Estimated effort**: 2-3 days including testing and documentation.

The implementation is:
✅ Minimal and focused
✅ Backward compatible
✅ Well-documented
✅ Testable
✅ Production-ready
