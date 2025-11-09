# Network Architecture Refactoring

## Overview
Refactored from NetworkProfile-based architecture to modern subnet delegation with NAT Gateway for region-agnostic deployment.

## Changes Summary

### Before (NetworkProfile Architecture)
```
Public IP → Network Profile → Container Network Interface Config → IP Config Profile → Containers
```

### After (Subnet Delegation Architecture)
```
Public IP → NAT Gateway → Delegated Subnet → Container Groups (via subnet_ids)
```

## Key Benefits

1. **Region-Agnostic**: No hardcoded region in NetworkManager
2. **Simplified**: Removed NetworkProfile complexity
3. **Modern ACI**: Uses subnet delegation (Microsoft recommended approach)
4. **Shared Egress**: All containers use same public IP via NAT Gateway
5. **Scalable**: Works with multi-region deployment

## Implementation Details

### NetworkManager Changes
- **Removed**:
  - `delete_resources()` - deleted NetworkProfile
  - `get_network_profile()` - retrieved NetworkProfile
  - `create_network_profile()` - created NetworkProfile
  
- **Added**:
  - `delete_stack()` - Deletes NAT GW → Subnet → VNet → PIP in correct order
  
- **Modified**:
  - `create_subnet()` - Now creates NAT Gateway with public IP
  - `create_ipv4()` - Returns PIP ID instead of object
  - Uses `self.location` instead of hardcoded 'westeurope'

### InstanceManager Changes
- **Removed**:
  - `network_profile` parameter from `__init__()` and `deploy()`
  - `self.network_profile` attribute
  
- **Added**:
  - `_subnet_id()` - Constructs subnet resource ID
  - `vnet_name` and `subnet_name` parameters to `deploy()`
  - `subnet_ids` parameter using `SubResource` for container groups
  - `expose_private_port` parameter for internal VNet communication
  - `self.subscription_id` for subnet ID construction
  - `IpAddress` and `Port` imports for private networking

- **Modified**:
  - Container groups now use `subnet_ids` instead of `network_profile`
  - IP address config only for private port exposure

### Acido Class Changes
- **Removed**:
  - `self.network_profile` attribute
  - NetworkProfile-related imports (`ContainerNetworkInterfaceConfiguration`, `IPConfigurationProfile`, `NetworkProfile`)
  
- **Added**:
  - `self.public_ip_name` - Name of the public IP
  - `self.public_ip_id` - Azure resource ID of public IP
  - `self.vnet_name` - Virtual network name
  - `self.subnet_name` - Subnet name
  - `self.subnet_id` - Subnet resource ID (optional)
  
- **Modified Methods**:
  - `create_ipv4_address()` - Creates PIP + VNet + Subnet with NAT Gateway (no NetworkProfile)
  - `select_ipv4_address()` - Selects PIP and derives vnet/subnet names by convention
  - `rm_ip()` - Uses `delete_stack()` to remove NAT GW, Subnet, VNet, and PIP
  - `_save_config()` - Persists new network fields instead of network_profile
  - `fleet()` - Passes `vnet_name` and `subnet_name` to deploy
  - `run()` - Passes `vnet_name` and `subnet_name` to deploy

## Usage Pattern

### Create Network Stack
```python
acido.create_ipv4_address("my-ip")
# Creates:
# - Public IP: my-ip
# - VNet: my-ip-vnet
# - Subnet: my-ip-subnet (delegated to containerGroups)
# - NAT Gateway: my-ip-subnet-nat-gw (attached to subnet)
```

### Deploy Containers
```python
acido.fleet(
    fleet_name="scan",
    instance_num=100,
    regions=["westeurope", "eastus", "westus2"]
)
# Each container group uses:
# - vnet_name: my-ip-vnet
# - subnet_name: my-ip-subnet
# - Egress via NAT Gateway with my-ip
```

### Cleanup
```python
acido.rm_ip("my-ip")
# Deletes in order:
# 1. NAT Gateway: my-ip-subnet-nat-gw
# 2. Subnet: my-ip-subnet
# 3. VNet: my-ip-vnet
# 4. Public IP: my-ip
```

## Naming Convention

| Resource | Naming Pattern | Example |
|----------|---------------|---------|
| Public IP | `{name}` | `pentest-01` |
| VNet | `{name}-vnet` | `pentest-01-vnet` |
| Subnet | `{name}-subnet` | `pentest-01-subnet` |
| NAT Gateway | `{name}-subnet-nat-gw` | `pentest-01-subnet-nat-gw` |

## Backward Compatibility

- Existing container groups without subnet config will work (no subnet_ids)
- Old configs without vnet_name/subnet_name load correctly (None values)
- Migration: Users need to run `create_ipv4_address()` or `select_ipv4_address()` to populate new fields

## Multi-Region Considerations

- Each region deployment uses the same vnet_name/subnet_name
- Subnets are region-specific (created per region as needed)
- NAT Gateway ensures all containers in a region share the same egress IP
- The `location` parameter in `deploy()` determines which region

## Security & Best Practices

- NAT Gateway provides secure egress without exposing containers
- Subnet delegation restricts subnet use to container groups only
- Standard SKU public IP required for NAT Gateway
- Clean up container groups before deleting network stack
