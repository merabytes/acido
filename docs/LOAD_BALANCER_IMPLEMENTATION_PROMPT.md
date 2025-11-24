# Load Balancer Implementation Prompt

## Context

You are implementing Azure Load Balancer support for the acido project to enable true bidirectional connectivity with specific, pre-configured public IP addresses for Azure Container Instances.

## Background

**Current State**: The bidirectional port forwarding feature (`--bidirectional` flag) currently uses Azure Container Instances' built-in public IP assignment, which creates a random, unpredictable IP address. The selected IP from `acido ip select` is not actually used.

**Goal**: Implement Azure Load Balancer to route traffic from a specific, user-selected public IP to container instances, enabling use cases that require stable, predictable public IPs (DNS records, firewall rules, VoIP configurations, etc.).

## Complete Documentation Available

All design documents are in `docs/`:
- **START HERE**: `docs/LOAD_BALANCER_IMPLEMENTATION.md` - Complete technical specification
- `docs/PORT_FORWARDING_PROPOSAL.md` - Context on port forwarding
- `docs/PORT_FORWARDING_DIAGRAMS.md` - Architecture diagrams

## Implementation Requirements

### 1. Create LoadBalancerManager Module

**File**: `acido/azure_utils/LoadBalancerManager.py`

Implement a class to manage Azure Load Balancer resources:

```python
class LoadBalancerManager:
    """Manages Azure Load Balancer resources for container bidirectional connectivity"""
    
    def __init__(self, subscription_id, resource_group, credential):
        """Initialize with Azure credentials"""
        self.network_client = NetworkManagementClient(credential, subscription_id)
        self.resource_group = resource_group
    
    def create_load_balancer(self, name, public_ip_id, region):
        """
        Create Azure Load Balancer with frontend IP configuration
        
        Steps:
        1. Create Load Balancer resource
        2. Attach frontend IP configuration with public_ip_id
        3. Create default backend pool
        4. Return load balancer resource
        """
        pass
    
    def create_backend_pool(self, lb_name, pool_name):
        """Create backend pool for container groups"""
        pass
    
    def add_container_to_backend_pool(self, lb_name, pool_name, container_ip, vnet_id):
        """
        Add container IP to backend pool (IP-based)
        
        Note: This requires REST API or ARM template as container groups
        are not natively supported in backend pools
        """
        pass
    
    def create_load_balancing_rules(self, lb_name, frontend_name, backend_pool_name, 
                                   exposed_ports, probe_name):
        """
        Create load balancing rules for each exposed port
        
        Args:
            exposed_ports: List of {"port": 5060, "protocol": "UDP"}
        """
        pass
    
    def create_health_probe(self, lb_name, probe_name, port, protocol="Tcp"):
        """
        Create TCP health probe for container health monitoring
        
        Note: Use TCP probe on primary exposed port
        """
        pass
    
    def delete_load_balancer(self, name):
        """Delete load balancer and all associated resources"""
        pass
    
    def get_load_balancer(self, name):
        """Get load balancer details"""
        pass
    
    def list_load_balancers(self):
        """List all load balancers in resource group"""
        pass
```

### 2. Update NetworkManager

**File**: `acido/azure_utils/NetworkManager.py`

Add Load Balancer-specific network infrastructure methods:

```python
def create_lb_network_infrastructure(self, name, region):
    """
    Create VNet and subnet for Load Balancer containers
    
    Requirements:
    - VNet address space: 10.0.0.0/16
    - Subnet with delegation to Microsoft.ContainerInstance/containerGroups
    - Subnet address space: 10.0.1.0/24
    
    Returns:
        tuple: (vnet_name, subnet_name, subnet_id)
    """
    pass

def tag_ip_with_load_balancer(self, ip_name, lb_name):
    """
    Tag public IP to indicate it has Load Balancer
    
    Tags:
        has_nat_stack: false
        has_load_balancer: true
        lb_name: <lb_name>
        managed_by: acido
    """
    pass
```

### 3. Update CLI Commands

**File**: `acido/cli.py`

#### 3.1 Update `ip create` command

Add `--with-load-balancer` flag:

```python
ip_create_parser.add_argument('--with-load-balancer', dest='with_load_balancer', 
                              action='store_true',
                              help='Create Load Balancer infrastructure with public IP (enables specific IP for bidirectional)')
```

Implementation in `create_ipv4_address()`:

```python
def create_ipv4_address(self, name: str, with_nat_stack: bool = False, 
                       with_load_balancer: bool = False):
    """
    Create public IP with optional infrastructure
    
    Args:
        with_load_balancer: Create Load Balancer infrastructure
        
    When with_load_balancer=True:
    1. Create public IP
    2. Create VNet with container delegation
    3. Create Load Balancer with public IP
    4. Create backend pool
    5. Create basic health probe
    6. Tag all resources
    """
    pass
```

#### 3.2 Update `run` command

Add `--use-load-balancer` flag:

```python
run_parser.add_argument('--use-load-balancer', dest='use_load_balancer',
                       action='store_true',
                       help='Use Load Balancer for bidirectional connectivity (requires IP created with --with-load-balancer)')
```

Validation logic:

```python
# In main() where run command is handled
if getattr(args, 'use_load_balancer', False):
    if not getattr(args, 'bidirectional', False):
        print(bad("--use-load-balancer requires --bidirectional"))
        sys.exit(1)
    
    # Check if selected IP has Load Balancer
    if not acido.public_ip_name:
        print(bad("No public IP selected. Run 'acido ip select' first"))
        sys.exit(1)
    
    # Verify IP has Load Balancer infrastructure
    pip = acido.network_manager.get_public_ip(acido.public_ip_name)
    if not pip.tags or pip.tags.get('has_load_balancer') != 'true':
        print(bad(f"Public IP '{acido.public_ip_name}' does not have Load Balancer infrastructure"))
        print(info("Create IP with: acido ip create <name> --with-load-balancer"))
        sys.exit(1)
```

#### 3.3 Add new IP management commands

```python
# acido ip setup-lb <name> - Add Load Balancer to existing IP
# acido ip rm-lb <name> - Remove Load Balancer infrastructure
```

### 4. Update InstanceManager

**File**: `acido/azure_utils/InstanceManager.py`

Update `deploy()` method signature:

```python
def deploy(self, name, image_name, command=None, env_vars=None,
          vnet_name=None, subnet_name=None, exposed_ports=None,
          public_ip_id=None, use_load_balancer=False, lb_name=None,
          max_cpu=4, max_ram=16, ...):
    """
    Deploy container with optional Load Balancer integration
    
    Args:
        use_load_balancer: Use Load Balancer for bidirectional
        lb_name: Load Balancer name to use
        
    When use_load_balancer=True:
    1. Deploy container in VNet (subnet_ids must be provided)
    2. Container gets private IP only (no public IP)
    3. Expose ports on container
    4. After deployment, add container IP to LB backend pool
    5. Create load balancing rules for exposed ports
    """
    pass
```

Key changes in deploy logic:

```python
if use_load_balancer and exposed_ports:
    # No public IP - container uses private IP in VNet
    ip_cfg = None
    
    # Container must be in VNet
    if not vnet_name or not subnet_name:
        raise ValueError("VNet required for Load Balancer mode")
    
    subnet_ids = [ContainerGroupSubnetId(id=self._subnet_id(vnet_name, subnet_name))]
    
    # Create container group with exposed ports but no public IP
    # ... existing container group creation ...
    
    # After successful deployment, register container in LB backend pool
    container_ip = result.ip_address.ip if result.ip_address else None
    if container_ip:
        lb_manager = LoadBalancerManager(...)
        lb_manager.add_container_to_backend_pool(
            lb_name=lb_name,
            pool_name=f"{lb_name}-pool",
            container_ip=container_ip,
            vnet_id=vnet_id
        )
        
        # Create/update load balancing rules for exposed ports
        lb_manager.create_load_balancing_rules(
            lb_name=lb_name,
            frontend_name=f"{lb_name}-frontend",
            backend_pool_name=f"{lb_name}-pool",
            exposed_ports=exposed_ports,
            probe_name=f"{lb_name}-probe"
        )
```

### 5. Update Acido Class

**File**: `acido/cli.py`

Update `run()` method:

```python
def run(self, name, image_name, task=None, bidirectional=False, 
       exposed_ports=None, use_load_balancer=False, ...):
    """
    Run container with optional Load Balancer
    
    When use_load_balancer=True:
    1. Get Load Balancer details from selected IP
    2. Get VNet/subnet for Load Balancer
    3. Pass lb_name and use_load_balancer=True to deploy()
    4. Print Load Balancer public IP (not container IP)
    """
    
    lb_name = None
    lb_public_ip = None
    
    if use_load_balancer:
        # Get Load Balancer info from IP tags
        pip = self.network_manager.get_public_ip(self.public_ip_name)
        lb_name = pip.tags.get('lb_name')
        lb_public_ip = pip.ip_address
        
        # Get VNet info from Load Balancer
        # This should be stored in config or retrieved from LB
        
        print(good(f"Using Load Balancer: {lb_name}"))
        print(good(f"Public IP: {lb_public_ip}"))
    
    # Deploy with Load Balancer settings
    response[name], _ = self.instance_manager.deploy(
        name=name,
        image_name=image_name,
        command=command_to_execute,
        use_load_balancer=use_load_balancer,
        lb_name=lb_name,
        exposed_ports=exposed_ports,
        vnet_name=self.vnet_name if use_load_balancer else None,
        subnet_name=self.subnet_name if use_load_balancer else None,
        ...
    )
    
    # Print Load Balancer IP instead of container IP
    if use_load_balancer:
        print(good(f"Container deployed behind Load Balancer"))
        print(good(f"Public IP: {lb_public_ip}"))
        print(good(f"Exposed ports: {', '.join([f'{p['port']}/{p['protocol']}' for p in exposed_ports])}"))
```

### 6. Documentation Updates

**File**: `README.md`

Add Load Balancer section:

```markdown
### Bidirectional with Specific Public IP (Load Balancer)

For use cases requiring a specific, predictable public IP:

```bash
# Create public IP with Load Balancer infrastructure
acido ip create voip-ip --with-load-balancer
acido ip select voip-ip

# Deploy with Load Balancer
acido run voip-server \
  -im asterisk:latest \
  --task "./start.sh" \
  --bidirectional \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --use-load-balancer \
  --cpu 4 --ram 8

# Container is accessible via the voip-ip public IP
```

**Note**: Load Balancer adds ~$18-50/month cost per IP. See `docs/LOAD_BALANCER_IMPLEMENTATION.md` for details.

**Default bidirectional mode** (without `--use-load-balancer`) uses Azure-assigned random IPs at no additional cost.
```

### 7. Lambda Handler Updates

**File**: `lambda_handler.py`

Add support for Load Balancer parameters:

```python
def _execute_run(acido, name, image_name, task, duration, cleanup, regions=None,
                bidirectional=False, exposed_ports=None, max_cpu=4, max_ram=16,
                entrypoint=None, use_load_balancer=False):
    """Execute run with Load Balancer support"""
    
    return acido.run(
        name=name,
        image_name=full_image_url,
        task=task,
        bidirectional=bidirectional,
        exposed_ports=exposed_ports,
        use_load_balancer=use_load_balancer,
        ...
    )

# In handler:
if operation == 'run':
    use_load_balancer = event.get('use_load_balancer', False)
    
    # Validate
    if use_load_balancer and not bidirectional:
        return build_error_response('use_load_balancer requires bidirectional=true')
```

## Testing Strategy

### Unit Tests

Create `tests/test_load_balancer.py`:

```python
def test_create_load_balancer():
    """Test Load Balancer creation with public IP"""
    pass

def test_backend_pool_registration():
    """Test adding container IP to backend pool"""
    pass

def test_load_balancing_rules():
    """Test creating rules for multiple ports"""
    pass

def test_health_probe_configuration():
    """Test health probe setup"""
    pass
```

### Integration Tests

1. **End-to-end deployment**:
   - Create IP with Load Balancer
   - Deploy container with `--use-load-balancer`
   - Verify traffic routing through public IP
   - Test all exposed ports

2. **Multi-port testing**:
   - Deploy with TCP and UDP ports
   - Verify each port routes correctly

3. **Health probe testing**:
   - Stop container
   - Verify health probe detects failure
   - Restart container
   - Verify health probe detects recovery

### Manual Testing Checklist

- [ ] Create IP with `--with-load-balancer`
- [ ] Verify Load Balancer resources created
- [ ] Deploy container with `--use-load-balancer`
- [ ] Verify container gets private IP
- [ ] Verify traffic reaches container via public IP
- [ ] Test multiple exposed ports
- [ ] Test container restart
- [ ] Test cleanup (`acido rm`)
- [ ] Verify all resources deleted properly

## Edge Cases to Handle

1. **Container restart**: Update backend pool with new IP
2. **Load Balancer already exists**: Reuse or error
3. **Backend pool full**: Handle capacity limits
4. **Health probe failure**: Document behavior
5. **Multiple containers**: Not supported initially (document limitation)
6. **Cross-region**: Load Balancer and container must be same region
7. **Cleanup failures**: Ensure resources don't leak

## Cost Documentation

Document in README and implementation guide:

- Load Balancer Basic: ~$18/month
- Load Balancer Standard: ~$40-50/month
- Data transfer: ~$0.005/GB
- Total: Approximately $18-50/month per Load Balancer

## Migration and Backward Compatibility

1. **Default behavior unchanged**: Bidirectional without `--use-load-balancer` uses random IPs
2. **Opt-in feature**: Load Balancer is explicitly enabled via flags
3. **No breaking changes**: Existing workflows continue to work
4. **Clear documentation**: Explain differences and when to use each approach

## Success Criteria

- [ ] Users can create IP with `--with-load-balancer`
- [ ] Containers deployed with `--use-load-balancer` use the selected public IP
- [ ] Traffic routes correctly through Load Balancer to container
- [ ] Multiple ports and protocols work
- [ ] Health probes monitor container health
- [ ] Resources clean up properly
- [ ] Documentation is clear and complete
- [ ] Costs are documented
- [ ] Backward compatibility maintained

## Questions to Resolve During Implementation

1. **Backend Pool Registration**: Confirm IP-based backend pool works with containers
2. **ARM Templates**: May need ARM templates for some operations
3. **Health Probe Protocol**: TCP vs HTTP - decide default
4. **Multiple Containers**: Phase 2 feature or initial support?
5. **Application Gateway**: Consider as alternative?

## References

- `docs/LOAD_BALANCER_IMPLEMENTATION.md` - Complete technical specification
- `docs/PORT_FORWARDING_PROPOSAL.md` - Original port forwarding design
- Azure Load Balancer SDK documentation
- Azure Container Instances networking documentation

## Priority

**High** - This addresses a fundamental limitation discovered during testing where users cannot control which public IP their containers receive, breaking critical use cases requiring stable IPs.

## Estimated Effort

- **Core Implementation**: 3-5 days
- **Testing & Documentation**: 1-2 days
- **Total**: 4-7 days

Good luck with the implementation! 🚀
