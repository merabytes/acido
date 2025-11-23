# Port Forwarding Feature Proposal

## Overview

This document proposes a feature to enable port forwarding from the NAT Gateway public IP to specific Azure Container Instances (ACIs). This would enable bidirectional connectivity for use cases like VoIP servers, SIP trunking, game servers, and other applications requiring inbound connections.

## Problem Statement

Currently, acido creates network stacks with:
- Public IP Address (static, Standard SKU)
- NAT Gateway (for egress traffic)
- Virtual Network with delegated subnet
- Container Groups without public IP addresses

This architecture provides:
✅ **Egress**: Containers can make outbound connections using the NAT Gateway's public IP
❌ **Ingress**: No way to receive inbound connections to specific containers

### Use Case Example: VoIP/SIP Server

A VoIP server requires:
- **Inbound UDP/TCP** on port 5060 (SIP signaling) from external SIP providers
- **Outbound connections** to SIP providers for registration and calls
- **Bidirectional RTP** for media streams (dynamic port range)

Current limitations:
- Cannot receive incoming SIP INVITE requests
- Cannot accept inbound SIP registrations
- Limited to client-initiated connections only

## Azure Architecture Analysis

### Current Architecture

```
┌─────────────────────────────────────────────────┐
│ Resource Group                                  │
│                                                 │
│  ┌────────────────┐                            │
│  │ Public IP      │                            │
│  │ (Standard SKU) │                            │
│  └───────┬────────┘                            │
│          │                                      │
│          ▼                                      │
│  ┌────────────────┐      ┌──────────────────┐ │
│  │ NAT Gateway    │─────▶│ Virtual Network  │ │
│  │ (Egress only)  │      │                  │ │
│  └────────────────┘      │  ┌─────────────┐ │ │
│                          │  │ Subnet      │ │ │
│                          │  │ (delegated) │ │ │
│                          │  │             │ │ │
│                          │  │  ┌────────┐ │ │ │
│                          │  │  │ ACI 1  │ │ │ │
│                          │  │  │(no IP) │ │ │ │
│                          │  │  └────────┘ │ │ │
│                          │  │  ┌────────┐ │ │ │
│                          │  │  │ ACI 2  │ │ │ │
│                          │  │  │(no IP) │ │ │ │
│                          │  │  └────────┘ │ │ │
│                          │  └─────────────┘ │ │
│                          └──────────────────┘ │
└─────────────────────────────────────────────────┘

Traffic Flow:
→ Outbound: ACI → NAT Gateway → Public IP → Internet ✅
← Inbound:  Internet → Public IP → ??? → ACI ❌ (Not possible)
```

### Azure NAT Gateway Limitations

**Important Finding**: Azure NAT Gateway does **NOT** support inbound connections or port forwarding.

From Azure documentation:
> "NAT Gateway provides outbound connectivity from a virtual network to the internet. NAT Gateway doesn't provide inbound connectivity initiated from the internet."

This means our current NAT Gateway architecture **cannot** be extended to support port forwarding without architectural changes.

## Proposed Solutions

### Solution 1: Public IP per Container (Recommended for Simplicity)

Assign a dedicated public IP address directly to specific container groups that require inbound connectivity.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Resource Group                                              │
│                                                             │
│  ┌────────────────┐                                        │
│  │ NAT Gateway IP │ (for regular egress traffic)          │
│  └───────┬────────┘                                        │
│          │                                                  │
│          ▼                                                  │
│  ┌────────────────┐      ┌──────────────────────────────┐ │
│  │ NAT Gateway    │─────▶│ Virtual Network              │ │
│  └────────────────┘      │                              │ │
│                          │  ┌─────────────────────────┐ │ │
│                          │  │ Subnet (delegated)      │ │ │
│  ┌─────────────────┐    │  │                         │ │ │
│  │ VoIP Public IP  │    │  │  ┌────────────────────┐ │ │ │
│  │ (Port 5060)     │────┼──┼─▶│ ACI-VoIP           │ │ │ │
│  └─────────────────┘    │  │  │ (Public IP)        │ │ │ │
│                          │  │  │ Port: 5060 UDP/TCP │ │ │ │
│                          │  │  └────────────────────┘ │ │ │
│                          │  │                         │ │ │
│                          │  │  ┌────────────────────┐ │ │ │
│                          │  │  │ ACI-Regular        │ │ │ │
│                          │  │  │ (No Public IP)     │ │ │ │
│                          │  │  └────────────────────┘ │ │ │
│                          │  └─────────────────────────┘ │ │
│                          └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

Traffic Flow:
VoIP Container:
  → Outbound: ACI-VoIP → Public IP → Internet ✅
  ← Inbound:  Internet → VoIP Public IP:5060 → ACI-VoIP ✅

Regular Containers:
  → Outbound: ACI → NAT Gateway → NAT Gateway IP → Internet ✅
  ← Inbound:  Not allowed ✅
```

#### Implementation

1. **New CLI Command**: `acido ip create-forwarding`
   ```bash
   acido ip create-forwarding voip-ip --ports 5060:udp,5060:tcp
   ```

2. **Modified Container Deployment**: Add optional `--public-ip` flag
   ```bash
   acido run voip-server \
     -im asterisk:latest \
     -t "./start-asterisk.sh" \
     --public-ip voip-ip \
     --ports 5060:udp,5060:tcp
   ```

3. **New NetworkManager Methods**:
   ```python
   def create_public_ip_with_ports(self, name, ports):
       """
       Create a public IP configured for specific port forwarding.
       
       Args:
           name: Name of the public IP
           ports: List of port configurations [{"port": 5060, "protocol": "UDP"}]
       
       Returns:
           Public IP resource ID
       """
       pass
   
   def list_forwarding_ips(self):
       """List all public IPs configured for port forwarding."""
       pass
   ```

4. **Modified InstanceManager.deploy()**:
   ```python
   def deploy(self, name, ..., public_ip_name=None, exposed_ports=None):
       """
       Deploy container group with optional public IP.
       
       Args:
           public_ip_name: Name of public IP to assign (optional)
           exposed_ports: List of ports to expose [{"port": 5060, "protocol": "UDP"}]
       """
       if public_ip_name and exposed_ports:
           # Get the public IP resource
           pip = self.network_manager.get_public_ip(public_ip_name)
           
           # Configure IpAddress with Public type
           ip_cfg = IpAddress(
               type="Public",
               ports=[Port(protocol=p["protocol"], port=p["port"]) for p in exposed_ports],
               ip=pip.ip_address
           )
       else:
           # Use private IP or no IP (NAT Gateway egress only)
           ip_cfg = None
   ```

#### Pros
- ✅ **Simple to implement**: Builds on existing ACI public IP support
- ✅ **Direct connectivity**: No intermediary routing/forwarding
- ✅ **Works with subnet delegation**: Compatible with current architecture
- ✅ **Per-container control**: Each container can have different ports
- ✅ **Standard Azure feature**: No custom networking required

#### Cons
- ❌ **Cost**: Each public IP costs ~$3-4/month
- ❌ **IP limit**: Azure subscription limits on public IPs
- ❌ **No port translation**: Cannot map external port 80 to internal 8080
- ❌ **One IP per container**: Cannot share one IP across multiple ACIs

#### Cost Analysis
- Public IP (Standard): ~$0.005/hour = ~$3.60/month
- NAT Gateway: ~$0.045/hour = ~$32.40/month
- Data processing: ~$0.045/GB

**Total for 1 VoIP server**: ~$36/month + data

### Solution 2: Azure Load Balancer (Recommended for Production)

Use Azure Load Balancer for port forwarding to multiple backend containers.

#### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Resource Group                                               │
│                                                              │
│  ┌───────────────────┐                                      │
│  │ Load Balancer     │                                      │
│  │ Public IP         │                                      │
│  │ (Standard SKU)    │                                      │
│  └─────────┬─────────┘                                      │
│            │                                                 │
│            │ Frontend: 0.0.0.0:5060                         │
│            │                                                 │
│  ┌─────────▼──────────────────────────────────────────┐    │
│  │ Load Balancing Rules                               │    │
│  │ - Port 5060 UDP → Backend Pool (port 5060)        │    │
│  │ - Port 5060 TCP → Backend Pool (port 5060)        │    │
│  └─────────┬──────────────────────────────────────────┘    │
│            │                                                 │
│            │                                                 │
│            ▼                                                 │
│  ┌─────────────────────────┐      ┌──────────────────────┐ │
│  │ Backend Pool            │      │ Virtual Network      │ │
│  │ (Private IP addresses)  │      │                      │ │
│  └─────────┬───────────────┘      │  ┌─────────────────┐ │ │
│            │                       │  │ Subnet          │ │ │
│            ├──────────────────────┼──┼▶┌──────────────┐│ │ │
│            │                       │  │ │ ACI-VoIP-01  ││ │ │
│            │                       │  │ │(10.0.1.4)    ││ │ │
│            │                       │  │ │Port 5060     ││ │ │
│            │                       │  │ └──────────────┘│ │ │
│            │                       │  │ ┌──────────────┐│ │ │
│            └──────────────────────┼──┼▶│ ACI-VoIP-02  ││ │ │
│                                    │  │ │(10.0.1.5)    ││ │ │
│                                    │  │ │Port 5060     ││ │ │
│                                    │  │ └──────────────┘│ │ │
│                                    │  └─────────────────┘ │ │
│                                    └──────────────────────┘ │
└──────────────────────────────────────────────────────────────┘

Traffic Flow:
← Inbound:  Internet → LB Public IP:5060 → Backend Pool → ACI-VoIP-0X ✅
→ Outbound: ACI → NAT Gateway → Internet ✅
```

#### Implementation

1. **New CLI Command**:
   ```bash
   acido lb create voip-lb \
     --frontend-port 5060:udp,5060:tcp \
     --backend-port 5060
   ```

2. **Load Balancer Deployment**:
   ```bash
   acido run voip-server-01 \
     -im asterisk:latest \
     -t "./start.sh" \
     --load-balancer voip-lb \
     --backend-port 5060
   ```

3. **New LoadBalancerManager Class**:
   ```python
   class LoadBalancerManager:
       def create_load_balancer(self, name, frontend_ports):
           """Create Azure Load Balancer with frontend IP and ports."""
           pass
       
       def add_backend_pool_member(self, lb_name, container_ip):
           """Add container to backend pool."""
           pass
       
       def create_lb_rules(self, lb_name, frontend_port, backend_port, protocol):
           """Create load balancing rule."""
           pass
   ```

#### Pros
- ✅ **Highly available**: Supports multiple backend containers
- ✅ **Production-grade**: Azure-managed load balancing
- ✅ **Health probes**: Automatic failover for unhealthy containers
- ✅ **Single IP**: Multiple containers share one public IP
- ✅ **Port translation**: Map different frontend/backend ports

#### Cons
- ❌ **Complex setup**: Requires Load Balancer + Backend Pools
- ❌ **Higher cost**: Load Balancer + Public IP costs
- ❌ **Overkill for single container**: Not ideal for simple use cases
- ❌ **Additional Azure resource**: More infrastructure to manage

#### Cost Analysis
- Load Balancer (Standard): ~$0.025/hour = ~$18/month
- Public IP (Standard): ~$0.005/hour = ~$3.60/month
- Data processing: ~$0.005/GB
- LB rules: ~$0.010/hour per rule = ~$7.20/month

**Total for 1 rule**: ~$29/month + data

### Solution 3: Azure Application Gateway (Advanced)

Use Application Gateway for Layer 7 (HTTP/HTTPS) traffic with advanced features.

#### Use Cases
- Web applications requiring SSL termination
- Path-based routing to different containers
- Web Application Firewall (WAF)
- URL rewriting

#### Pros
- ✅ **Layer 7 features**: SSL offloading, URL routing, WAF
- ✅ **Autoscaling**: Can scale based on traffic
- ✅ **Advanced routing**: Host/path-based routing

#### Cons
- ❌ **Expensive**: ~$140/month minimum
- ❌ **HTTP/HTTPS only**: Not suitable for UDP/SIP
- ❌ **Complexity**: Over-engineered for simple port forwarding
- ❌ **Not for VoIP**: Cannot handle UDP SIP or RTP

**Not recommended for this use case.**

### Solution 4: Azure Firewall (Enterprise)

Enterprise-grade firewall with DNAT (Destination NAT) support.

#### Pros
- ✅ **Full DNAT support**: True port forwarding
- ✅ **FQDN filtering**: Control outbound by domain
- ✅ **Threat intelligence**: Built-in security

#### Cons
- ❌ **Very expensive**: ~$1.25/hour = ~$900/month
- ❌ **Enterprise feature**: Overkill for most use cases
- ❌ **Complex setup**: Requires hub-spoke topology

**Not recommended unless security requirements justify the cost.**

## Recommended Implementation Plan

### Phase 1: Basic Port Forwarding (Public IP per Container)

**Target**: Enable port forwarding for single containers with dedicated public IPs

#### Changes Required

1. **NetworkManager.py**:
   ```python
   def create_forwarding_ip(self, name, ports=None):
       """
       Create a public IP configured for port forwarding.
       
       Args:
           name: Name of the public IP
           ports: List of port configs [{"port": 5060, "protocol": "UDP"}] (optional)
       
       Returns:
           Public IP resource ID and IP address
       """
       params = {
           'location': self.location,
           'public_ip_allocation_method': 'Static',
           'public_ip_address_version': 'IPv4',
           'sku': PublicIPAddressSku(name='Standard', tier='Regional'),
           'tags': {
               'purpose': 'port-forwarding',
               'ports': ','.join([f"{p['port']}/{p['protocol']}" for p in (ports or [])])
           }
       }
       pip = self._client.public_ip_addresses.begin_create_or_update(
           self.resource_group, name, params
       ).result()
       return pip.id, pip.ip_address
   
   def get_public_ip(self, name):
       """Get public IP resource by name."""
       return self._client.public_ip_addresses.get(
           self.resource_group, name
       )
   ```

2. **InstanceManager.py**:
   ```python
   def deploy(self, name, ..., public_ip_name=None, exposed_ports=None):
       """
       Deploy container with optional public IP and port forwarding.
       
       Args:
           public_ip_name: Name of public IP to use for forwarding
           exposed_ports: List of ports [{"port": 5060, "protocol": "UDP"}]
       """
       # Build IP configuration
       ip_cfg = None
       if public_ip_name and exposed_ports:
           # Get the public IP
           pip = self.network_client.get_public_ip(public_ip_name)
           
           # Configure public IP with ports
           ip_cfg = IpAddress(
               type="Public",
               ip=pip.ip_address,
               ports=[Port(protocol=p["protocol"], port=p["port"]) 
                      for p in exposed_ports],
               dns_name_label=None  # Optional: add DNS label
           )
       
       # Add ip_address to ContainerGroup
       cg = ContainerGroup(
           location=location,
           containers=deploy_instances,
           os_type=os_type,
           ip_address=ip_cfg,  # Public IP with forwarded ports
           image_registry_credentials=ir_credentials,
           restart_policy=restart_policy,
           subnet_ids=subnet_ids,  # Still use subnet for VNet integration
           ...
       )
   ```

3. **cli.py - New commands**:
   ```python
   # IP forwarding create
   ip_forwarding_parser = ip_subparsers.add_parser(
       'create-forwarding', 
       help='Create public IP for port forwarding'
   )
   ip_forwarding_parser.add_argument('name', help='IP name')
   ip_forwarding_parser.add_argument(
       '--ports', 
       action='append',
       help='Port to forward (format: PORT:PROTOCOL, e.g., 5060:udp)'
   )
   
   # Run with port forwarding
   run_parser.add_argument(
       '--public-ip',
       dest='public_ip_name',
       help='Public IP to use for port forwarding'
   )
   run_parser.add_argument(
       '--expose-port',
       dest='expose_ports',
       action='append',
       help='Port to expose (format: PORT:PROTOCOL)'
   )
   ```

4. **Helper Functions**:
   ```python
   def parse_port_spec(port_spec):
       """
       Parse port specification string.
       
       Args:
           port_spec: String like "5060:udp" or "8080:tcp"
       
       Returns:
           dict: {"port": 5060, "protocol": "UDP"}
       """
       port, protocol = port_spec.split(':')
       return {
           "port": int(port),
           "protocol": protocol.upper()
       }
   ```

#### Usage Examples

```bash
# Create a public IP for VoIP server
acido ip create-forwarding voip-ip --ports 5060:udp --ports 5060:tcp

# List forwarding IPs
acido ip ls

# Deploy VoIP server with port forwarding
acido run voip-server \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --public-ip voip-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp

# Check the public IP
acido ip ls
# Output: voip-ip (203.0.113.45) [Ports: 5060/UDP, 5060/TCP]

# Remove the server and IP
acido rm voip-server
acido ip rm voip-ip
```

#### Lambda Support

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
  "duration": 900
}
```

### Phase 2: Load Balancer Support (Future Enhancement)

For high-availability scenarios requiring multiple backend containers.

**Implementation**: Create `LoadBalancerManager` class and integrate with deployment flow.

## Security Considerations

1. **Firewall Rules**: 
   - Consider implementing NSG (Network Security Group) rules
   - Only allow traffic on specified ports
   - Add source IP restrictions if needed

2. **Container Security**:
   - Containers with public IPs are directly exposed to internet
   - Ensure application-level security (authentication, rate limiting)
   - Consider DDoS protection for production

3. **Monitoring**:
   - Track inbound connections
   - Monitor for abuse/attacks
   - Set up alerts for anomalous traffic

## Testing Plan

1. **Unit Tests**:
   - Test port specification parsing
   - Test public IP creation with ports
   - Test container deployment with public IP

2. **Integration Tests**:
   - Deploy VoIP server container
   - Verify inbound connectivity on port 5060
   - Verify outbound connectivity through NAT Gateway
   - Test port forwarding with UDP and TCP

3. **Manual Verification**:
   ```bash
   # Deploy test server
   acido ip create-forwarding test-ip --ports 8080:tcp
   acido run test-server \
     -im nginx:alpine \
     --public-ip test-ip \
     --expose-port 8080:tcp
   
   # Test connectivity
   curl http://<public-ip>:8080
   
   # Cleanup
   acido rm test-server
   acido ip rm test-ip
   ```

## Documentation Updates Required

1. **README.md**: Add port forwarding section with examples
2. **New file**: `PORT_FORWARDING.md` with detailed guide
3. **LAMBDA.md**: Document port forwarding operations
4. **CLI help**: Update command descriptions

## Backward Compatibility

- All changes are **additive**: Existing functionality remains unchanged
- Containers without `--public-ip` continue to use NAT Gateway for egress
- No breaking changes to existing API or configuration

## Open Questions

1. **Cost visibility**: Should we warn users about public IP costs?
2. **Port validation**: Should we validate common ports (e.g., warn about port 22)?
3. **DNS labels**: Should we support custom DNS labels for public IPs?
4. **Multiple IPs**: Should one container support multiple public IPs?
5. **Port ranges**: Should we support port ranges (e.g., 5060-5090)?

## Conclusion

**Recommended Approach**: Implement **Phase 1 (Public IP per Container)** first.

This provides:
- Simple, straightforward implementation
- Direct compatibility with Azure Container Instances
- Sufficient for most use cases (VoIP, game servers, etc.)
- Foundation for future enhancements (Load Balancer support)

The implementation requires:
- ~3 new methods in NetworkManager
- ~1 modified method in InstanceManager
- ~3 new CLI commands
- ~100-150 lines of code
- Comprehensive testing and documentation

Estimated effort: **2-3 days** for complete implementation with tests and docs.
