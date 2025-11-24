# Load Balancer Implementation for True Bidirectional Connectivity

## Problem Statement

**Current Limitation**: Azure Container Instances does NOT support directly assigning a pre-existing public IP to a container group. When using `IpAddress(type="Public")`, Azure always provisions a NEW random public IP, regardless of any `public_ip_id` passed to the deployment.

**Impact**:
- Containers in bidirectional mode get random Azure-assigned IPs
- The selected IP from `acido ip select` is not actually used
- Users cannot predict or control which public IP their container will receive
- This breaks use cases requiring stable, pre-configured public IPs (DNS records, firewall rules, etc.)

## Proposed Solution: Azure Load Balancer Integration

Implement Azure Load Balancer to route traffic from a specific public IP to the container group's auto-assigned IP.

### Architecture Overview

```
Internet Traffic
    ↓
Pre-existing Public IP (User-Selected)
    ↓
Azure Load Balancer (Frontend)
    ↓
Backend Pool → Container Group (Auto-assigned IP)
    ↓
Container Instance (Exposed Ports)
```

### Key Components

1. **Public IP**: Pre-existing IP resource (already created via `acido ip create`)
2. **Load Balancer**: Azure Load Balancer resource with:
   - Frontend IP Configuration (using the pre-existing public IP)
   - Backend Pool (containing the container group)
   - Load Balancing Rules (for each exposed port)
   - Health Probes (to monitor container health)
3. **Container Group**: Deployed with VNet integration and exposed ports

## Implementation Requirements

### 1. New CLI Flag

```bash
# Create Load Balancer infrastructure with public IP
acido ip create <name> --with-load-balancer

# Or add to existing IP
acido ip setup-lb <name>
```

### 2. Load Balancer Manager Module

Create `acido/azure_utils/LoadBalancerManager.py`:

```python
class LoadBalancerManager:
    """Manages Azure Load Balancer resources for container bidirectional connectivity"""
    
    def __init__(self, subscription_id, resource_group, credential):
        self.network_client = NetworkManagementClient(credential, subscription_id)
        self.resource_group = resource_group
    
    def create_load_balancer(self, name, public_ip_id, region):
        """
        Create Azure Load Balancer with public IP attached
        
        Args:
            name: Load balancer name
            public_ip_id: Resource ID of pre-existing public IP
            region: Azure region
            
        Returns:
            Load balancer resource
        """
        pass
    
    def add_backend_pool(self, lb_name, pool_name):
        """Create backend pool for container groups"""
        pass
    
    def create_load_balancing_rules(self, lb_name, exposed_ports):
        """
        Create load balancing rules for exposed ports
        
        Args:
            lb_name: Load balancer name
            exposed_ports: List of {"port": 5060, "protocol": "UDP"}
        """
        pass
    
    def create_health_probe(self, lb_name, probe_name, port, protocol):
        """Create health probe to monitor container"""
        pass
    
    def get_backend_pool_id(self, lb_name, pool_name):
        """Get backend pool resource ID"""
        pass
    
    def delete_load_balancer(self, name):
        """Delete load balancer and associated resources"""
        pass
```

### 3. VNet Integration Requirements

For Load Balancer to work, container groups MUST be deployed in a VNet:

```python
# Create VNet and Subnet for Load Balancer
def create_lb_network_infrastructure(name, region):
    """
    Create VNet and subnet for load-balanced container groups
    
    Args:
        name: Base name for resources
        region: Azure region
        
    Returns:
        vnet_name, subnet_name, subnet_id
    """
    vnet_name = f"{name}-lb-vnet"
    subnet_name = f"{name}-lb-subnet"
    
    # Create VNet
    vnet = create_vnet(
        name=vnet_name,
        region=region,
        address_prefix="10.0.0.0/16"
    )
    
    # Create subnet for containers
    subnet = create_subnet(
        vnet_name=vnet_name,
        subnet_name=subnet_name,
        address_prefix="10.0.1.0/24",
        delegations=[{
            "name": "aciDelegation",
            "service_name": "Microsoft.ContainerInstance/containerGroups"
        }]
    )
    
    return vnet_name, subnet_name, subnet.id
```

### 4. Container Deployment Changes

Update `InstanceManager.deploy()` to support Load Balancer backend pool:

```python
def deploy(self, name, image_name, exposed_ports=None, 
          lb_backend_pool_id=None, vnet_name=None, subnet_name=None, ...):
    """
    Deploy container with optional Load Balancer integration
    
    Args:
        lb_backend_pool_id: Resource ID of Load Balancer backend pool
        
    When lb_backend_pool_id is provided:
    - Container group is deployed in VNet
    - Container group is added to Load Balancer backend pool
    - Ports are exposed on container but IpAddress type is NOT Public
    """
    
    # For Load Balancer mode: containers in VNet with private IPs
    if lb_backend_pool_id:
        ip_cfg = None  # No public IP on container group
        subnet_ids = [ContainerGroupSubnetId(id=subnet_id)]
        
        # Add to Load Balancer backend pool (requires custom resource definition)
        # This may need ARM template deployment or REST API calls
```

### 5. Metadata Tagging

Tag resources to track Load Balancer infrastructure:

```python
# Public IP tags
{
    "has_nat_stack": "false",
    "has_load_balancer": "true",
    "lb_name": "voip-lb",
    "managed_by": "acido"
}

# Load Balancer tags
{
    "managed_by": "acido",
    "public_ip_name": "voip",
    "created_for": "bidirectional_containers"
}

# VNet tags
{
    "managed_by": "acido",
    "purpose": "load_balancer",
    "associated_lb": "voip-lb"
}
```

## Implementation Steps

### Phase 1: Core Load Balancer Management

1. **Create LoadBalancerManager class**
   - Implement basic CRUD operations for Load Balancer
   - Create/delete frontend IP configuration
   - Create/delete backend pools
   - Create/delete load balancing rules
   - Create/delete health probes

2. **Update NetworkManager**
   - Add methods to create VNet with container delegation
   - Add methods to create dedicated subnets for LB containers
   - Track Load Balancer associations with public IPs

3. **Update IP creation command**
   ```bash
   acido ip create <name> --with-load-balancer
   ```
   - Creates public IP
   - Creates VNet with delegated subnet
   - Creates Load Balancer with public IP attached
   - Creates backend pool
   - Tags all resources appropriately

### Phase 2: Container Integration

1. **Update InstanceManager.deploy()**
   - Accept `lb_backend_pool_id` parameter
   - Deploy containers in VNet when Load Balancer is used
   - Configure containers without public IP (private only)
   - Expose ports on containers (for LB to route to)

2. **Load Balancer Rule Creation**
   - For each exposed port, create load balancing rule
   - Protocol mapping: TCP/UDP
   - Port mapping: Frontend port → Backend port
   - Health probe configuration

3. **Backend Pool Registration**
   - Register container group IP in backend pool
   - This may require ARM template or REST API
   - Container group must be in same VNet as Load Balancer

### Phase 3: CLI Updates

1. **Update `acido run` command**
   ```bash
   acido run voip-server \
     -im asterisk:latest \
     --task "./start.sh" \
     --bidirectional \
     --expose-port 5060:udp \
     --expose-port 5060:tcp \
     --use-load-balancer  # NEW FLAG
   ```

2. **Validation logic**
   - Check if selected IP has Load Balancer (`has_load_balancer` tag)
   - If `--use-load-balancer` is specified, verify IP has LB infrastructure
   - Error if Load Balancer doesn't exist

3. **Update `acido ip` commands**
   ```bash
   # List IPs with LB indicator
   acido ip ls
   # Output: voip [with Load Balancer], nat-ip [with NAT stack]
   
   # Remove Load Balancer infrastructure
   acido ip rm-lb <name>
   ```

### Phase 4: Documentation and Testing

1. **User Documentation**
   - Update README with Load Balancer examples
   - Document cost implications
   - Document limitations and requirements
   - Migration guide from current bidirectional mode

2. **Testing**
   - Unit tests for LoadBalancerManager
   - Integration tests for end-to-end deployment
   - Validate traffic routing through Load Balancer
   - Test health probes and failover

## Technical Challenges

### 1. Backend Pool Registration

**Challenge**: Azure Load Balancer backend pools typically reference VMs or VM Scale Sets. Container groups are not directly supported as backend pool members in the standard way.

**Solutions**:
- **Option A**: Use Application Gateway instead (supports more backend types)
- **Option B**: Use IP-based backend pool (requires REST API or ARM template)
- **Option C**: Deploy containers with network profile and register IPs

**Recommended**: Option B (IP-based backend pool)

```python
# Using REST API to add container IP to backend pool
backend_pool_config = {
    "properties": {
        "loadBalancerBackendAddresses": [
            {
                "name": f"{container_name}-backend-address",
                "properties": {
                    "ipAddress": container_private_ip,
                    "virtualNetwork": {
                        "id": vnet_id
                    }
                }
            }
        ]
    }
}
```

### 2. Dynamic IP Assignment

**Challenge**: Container groups get dynamic private IPs that may change on restart.

**Solutions**:
- Update backend pool after each container deployment
- Use DNS-based service discovery
- Reserve specific IP ranges for containers

**Recommended**: Update backend pool after deployment

### 3. Health Probes

**Challenge**: Containers may not have HTTP endpoints for health checks.

**Solutions**:
- TCP health probes on exposed ports
- Add health endpoint to container images
- Use liveness/readiness probe from container definition

**Recommended**: TCP probes on primary exposed port

### 4. Multiple Ports/Protocols

**Challenge**: Load Balancer requires separate rules for each port/protocol combination.

**Solution**: Dynamically create load balancing rules for all exposed ports

```python
for exposed_port in exposed_ports:
    rule_name = f"rule-{exposed_port['port']}-{exposed_port['protocol']}"
    create_load_balancing_rule(
        lb_name=lb_name,
        rule_name=rule_name,
        frontend_port=exposed_port['port'],
        backend_port=exposed_port['port'],
        protocol=exposed_port['protocol'],
        backend_pool_id=backend_pool_id,
        probe_id=probe_id
    )
```

## Cost Implications

**Additional Azure Resources**:
- Load Balancer: ~$18-25/month (Basic tier) or ~$40-50/month (Standard tier)
- VNet: No additional cost
- Additional data transfer through Load Balancer: ~$0.005/GB

**Total Additional Cost**: Approximately $18-50/month per Load Balancer

**Recommendation**: Document costs clearly and make this opt-in feature

## Alternative: Application Gateway

**Consideration**: Azure Application Gateway (Layer 7 load balancer) offers:
- More flexible routing
- SSL termination
- Web Application Firewall
- Better container integration

**Tradeoff**: Higher cost (~$125-250/month) but more features

**Recommendation**: Start with basic Load Balancer, consider Application Gateway for future enhancement

## Migration Path

### For Existing Users

1. **Document current limitation**
   - Update README to explain current bidirectional mode uses random IPs
   - Clarify that selected IP is not currently used in bidirectional mode

2. **Provide migration guide**
   ```bash
   # Old: Random IP assignment
   acido run voip -im asterisk:latest --bidirectional --expose-port 5060:udp
   
   # New: Specific IP via Load Balancer
   acido ip create voip-ip --with-load-balancer
   acido ip select voip-ip
   acido run voip -im asterisk:latest --bidirectional --expose-port 5060:udp --use-load-balancer
   ```

3. **Backward compatibility**
   - Keep current behavior as default (random IP, no LB)
   - Load Balancer mode is opt-in via flag
   - No breaking changes to existing workflows

## Success Criteria

1. ✅ Users can deploy containers with predictable, stable public IPs
2. ✅ Traffic to selected public IP routes to container
3. ✅ Multiple ports/protocols supported
4. ✅ Health monitoring and failover works
5. ✅ Clear documentation of costs and tradeoffs
6. ✅ Backward compatible with existing deployments
7. ✅ Clean resource lifecycle management (create/delete)

## Future Enhancements

1. **Auto-scaling**: Integrate with Azure Container Instances scaling
2. **Multiple Containers**: Load balance across multiple container groups
3. **SSL/TLS Termination**: Add certificate management
4. **WAF Integration**: Add web application firewall for HTTP services
5. **Application Gateway**: Upgrade to Layer 7 load balancing

## References

- [Azure Load Balancer Documentation](https://docs.microsoft.com/en-us/azure/load-balancer/)
- [Azure Container Instances Networking](https://docs.microsoft.com/en-us/azure/container-instances/container-instances-virtual-network-concepts)
- [Load Balancer Backend Pool Configuration](https://docs.microsoft.com/en-us/azure/load-balancer/backend-pool-management)
