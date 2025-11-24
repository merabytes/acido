# Port Forwarding Feature - Executive Summary

## Overview

This document provides a comprehensive proposal for adding port forwarding capabilities to acido, enabling bidirectional network connectivity for Azure Container Instances (ACIs).

## Problem

**Current State**: 
- Acido containers can make **outbound** connections via NAT Gateway ✅
- Acido containers **cannot accept inbound** connections from the internet ❌

**Impact**: 
This limitation prevents use cases that require inbound connectivity:
- VoIP/SIP servers (SIP INVITE from providers)
- Game servers (player connections)
- SSH bastion hosts (remote access)
- Web services on specific ports
- Database direct access (dev/test)
- Custom protocols requiring bidirectional communication

## Proposed Solution

### Recommended Approach: Public IP per Container

Assign dedicated Azure public IP addresses to containers that require inbound connectivity.

#### Why This Approach?

1. **Simple Implementation**: Uses native Azure Container Instance features
2. **Minimal Code Changes**: ~500 lines across 5 files
3. **Backward Compatible**: Existing functionality unchanged
4. **Direct Connectivity**: No intermediary routing complexity
5. **Proven Technology**: Standard Azure feature, well-documented

#### How It Works

```
┌─────────────────────────────────────────────────────┐
│ Current: Egress-only Architecture                   │
│                                                      │
│ Container → NAT Gateway → Public IP → Internet ✅   │
│ Internet → Public IP → ??? → Container ❌           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Proposed: Dual-mode Architecture                    │
│                                                      │
│ Regular Container:                                   │
│   Container → NAT Gateway → Public IP → Internet ✅ │
│                                                      │
│ Port-forwarded Container:                            │
│   Container ↔ Public IP ↔ Internet ✅✅             │
└─────────────────────────────────────────────────────┘
```

## Usage Examples

### VoIP/SIP Server
```bash
# Create public IP (automatically creates voip-ip-vnet and voip-ip-subnet)
acido ip create-forwarding voip-ip --ports 5060:udp --ports 5060:tcp

# Deploy Asterisk server
# Network config automatically derived from --public-ip
acido run asterisk-prod \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --public-ip voip-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  -d 86400

# Result: SIP providers can now send INVITE to your server!
# Uses VNet: voip-ip-vnet, Subnet: voip-ip-subnet (auto-derived)
```

### Game Server
```bash
# Create IP for Minecraft
acido ip create-forwarding minecraft-ip --ports 25565:tcp

# Deploy server (subnet auto-derived from minecraft-ip)
acido run minecraft-server \
  -im minecraft:latest \
  --public-ip minecraft-ip \
  --expose-port 25565:tcp \
  -d 28800

# Players connect to: <public-ip>:25565
```

### Clean Config
```bash
# If you have an old IP in config, clean it:
acido ip clean

# This clears: public_ip_name, public_ip_id, vnet_name, subnet_name, subnet_id
```

### Lambda Invocation
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
  "duration": 86400
}
```

## Implementation Plan

### Phase 1: Core Implementation (Recommended)

**Deliverables**:
1. New CLI commands:
   - `acido ip create-forwarding <name> --ports PORT:PROTOCOL`
   - `acido ip ls-forwarding`
   - `acido ip clean` (clean IP config from local config)
   - `acido run --public-ip <name> --expose-port PORT:PROTOCOL`
   - `acido fleet --public-ip <name>` (for network configuration)

2. Automatic subnet derivation:
   - When `--public-ip` is specified, automatically derive VNet/subnet
   - VNet: `{public_ip_name}-vnet`
   - Subnet: `{public_ip_name}-subnet`
   - No need to run `acido ip select` or read from config

3. Config warning system:
   - Warn if IP is in config but `--public-ip` not specified
   - Suggest using `acido ip clean` to clear old config

4. Code changes:
   - **NetworkManager.py**: Add `create_forwarding_ip()`, `list_forwarding_ips()`
   - **InstanceManager.py**: Modify `deploy()` to accept `public_ip_name` and `exposed_ports`
   - **cli.py**: Add new commands, automatic subnet derivation, config warnings
   - **lambda_handler.py**: Support new operations
   - **port_utils.py**: Port parsing and validation utilities

3. Documentation:
   - PORT_FORWARDING_PROPOSAL.md (architecture and analysis)
   - docs/port_forwarding_examples.md (practical use cases)
   - docs/port_forwarding_implementation.md (code guide)

**Effort**: 2-3 days including tests and docs

### Phase 2: Advanced Features (Future)

**Optional Enhancements**:
- Azure Load Balancer integration for HA
- Port ranges (e.g., 10000-20000 for RTP)
- DNS labels for public IPs
- NSG (Network Security Group) rule management
- Monitoring and alerting integration

**Effort**: Additional 3-5 days per feature

## Cost Analysis

### Per Container with Port Forwarding

| Resource | Cost/Hour | Cost/Month | Notes |
|----------|-----------|------------|-------|
| Public IP (Standard) | $0.005 | ~$3.60 | Per IP, required |
| Container Instance | $0.013 | ~$9.40 | 1 vCPU, 1GB RAM |
| Data Transfer | Variable | ~$0.087/GB | Egress only |
| **Total (24/7)** | **$0.018** | **~$13** | + data transfer |

### Comparison with Alternatives

| Solution | Monthly Cost | Pros | Cons |
|----------|--------------|------|------|
| **Public IP per Container** | **~$13** | Simple, direct | One IP per container |
| Load Balancer | ~$29 + instances | HA, multiple backends | Complex for single container |
| Azure Firewall | ~$900 | Enterprise security | Extremely expensive |
| NAT Gateway Only | Not applicable | N/A | Cannot do inbound |

**Recommendation**: Public IP approach provides best cost/simplicity tradeoff.

## Alternative Approaches Considered

### 1. Azure Load Balancer
**Status**: Viable for Phase 2
- **Pro**: High availability with multiple backends
- **Pro**: Health probes and automatic failover
- **Con**: Higher cost (~$29/month)
- **Con**: Overkill for single container use cases

### 2. Azure Application Gateway
**Status**: Not recommended
- **Pro**: Layer 7 features (SSL, WAF, URL routing)
- **Con**: Very expensive (~$140/month minimum)
- **Con**: HTTP/HTTPS only, cannot handle UDP/SIP
- **Con**: Over-engineered for port forwarding

### 3. Azure Firewall
**Status**: Not recommended
- **Pro**: Enterprise-grade DNAT support
- **Pro**: Advanced threat intelligence
- **Con**: Extremely expensive (~$900/month)
- **Con**: Requires complex hub-spoke topology

### 4. NAT Gateway Inbound Rules
**Status**: Not possible
- **Finding**: Azure NAT Gateway does NOT support inbound connections
- **Source**: Official Azure documentation
- **Result**: This approach is technically infeasible

## Security Considerations

### 1. Exposure Risk
- Containers with public IPs are directly internet-accessible
- Requires application-level security (auth, rate limiting)
- Consider DDoS protection for production workloads

### 2. Recommended Mitigations
- Use auto-cleanup (`-d` duration) for temporary services
- Implement NSG rules for source IP filtering
- Enable application-level authentication
- Monitor for abuse and anomalous traffic

### 3. Best Practices
```bash
# Use short durations for testing
acido run test-server --public-ip test-ip --expose-port 8080:tcp -d 600

# Enable cleanup for temporary services
acido run temp-service --public-ip temp-ip --expose-port 9000:tcp -d 3600

# Only use --no-cleanup for production services with proper security
acido run prod-service --public-ip prod-ip --expose-port 443:tcp --no-cleanup
```

## Technical Specifications

### Azure Resources Created

1. **Public IP Address**
   - Type: Static
   - SKU: Standard
   - Version: IPv4
   - Tags: `purpose=port-forwarding`, `ports=5060/UDP,5060/TCP`

2. **Container Group**
   - IP Configuration: Public with specific ports
   - Subnet: Still connected to delegated subnet (for VNet connectivity)
   - Network Mode: Dual (Public IP + Subnet)

### API Changes

#### New Methods
- `NetworkManager.create_forwarding_ip(name, ports)`
- `NetworkManager.list_forwarding_ips()`
- `NetworkManager.get_public_ip(name)`
- `InstanceManager.deploy(..., public_ip_name, exposed_ports)`

#### New CLI Commands
- `acido ip create-forwarding <name> --ports PORT:PROTOCOL`
- `acido ip ls-forwarding`
- `acido run ... --public-ip <name> --expose-port PORT:PROTOCOL`

#### New Lambda Operations
- `ip_create_forwarding`: Create forwarding IP
- `ip_ls_forwarding`: List forwarding IPs
- `run` (enhanced): Support `public_ip_name` and `exposed_ports`

## Testing Strategy

### 1. Unit Tests
- Port specification parsing
- Port and protocol validation
- Public IP creation logic
- Container deployment with ports

### 2. Integration Tests
- End-to-end: Create IP → Deploy container → Test connectivity
- VoIP scenario: SIP INVITE handling
- Multi-protocol: UDP + TCP on same port

### 3. Manual Verification
```bash
# Deploy test HTTP server
acido ip create-forwarding test-ip --ports 8080:tcp
acido run nginx-test -im nginx:alpine --public-ip test-ip --expose-port 8080:tcp -d 600

# Test connectivity
curl http://<public-ip>:8080

# Verify cleanup
acido rm nginx-test
acido ip rm test-ip
```

## Documentation Deliverables

✅ **PORT_FORWARDING_PROPOSAL.md**
- Comprehensive architecture analysis
- All alternatives evaluated
- Cost analysis
- Technical specifications

✅ **docs/port_forwarding_examples.md**
- 7 practical use cases
- VoIP/SIP server
- Game servers (Minecraft, CS:GO)
- SSH bastion
- Web servers
- Database access
- Cost comparisons
- Troubleshooting guide

✅ **docs/port_forwarding_implementation.md**
- Step-by-step code changes
- Complete method signatures
- Example implementations
- Testing plan
- Helper utilities

✅ **This Executive Summary**
- High-level overview
- Key decisions and rationale
- Usage examples
- Quick reference

## Backward Compatibility

✅ **100% Backward Compatible**
- All changes are additive
- Existing containers work unchanged
- No breaking changes to API
- No changes to configuration format
- Containers without `--public-ip` continue using NAT Gateway

## Migration Path

**Current users**: No action required
- Existing deployments continue to work
- NAT Gateway egress remains default behavior

**New feature adoption**:
```bash
# Old way (still works)
acido run scanner -im nmap -t "nmap -iL input" -d 3600

# New way (opt-in for port forwarding)
acido run voip-server -im asterisk --public-ip voip-ip --expose-port 5060:udp -d 86400
```

## Success Metrics

### Functional Requirements
- ✅ Create dedicated public IPs for port forwarding
- ✅ Deploy containers with specific exposed ports
- ✅ Support both TCP and UDP protocols
- ✅ List and manage forwarding IPs
- ✅ Lambda operation support
- ✅ Maintain backward compatibility

### Non-Functional Requirements
- ✅ Simple CLI interface (3 new commands)
- ✅ Minimal code changes (~500 lines)
- ✅ Clear documentation with examples
- ✅ Reasonable cost (~$13/month per container)
- ✅ Production-ready implementation

## Timeline

### Week 1-2: Phase 1 Implementation
- Day 1-2: Core implementation (NetworkManager, InstanceManager)
- Day 3-4: CLI commands and Lambda support
- Day 5-6: Testing and bug fixes
- Day 7: Documentation updates

### Week 3: Review and Polish
- Code review and refinements
- Additional testing scenarios
- Documentation review
- User acceptance testing

### Week 4: Release
- Merge to main branch
- Release notes
- Blog post / announcement
- User onboarding materials

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Cost overruns | Medium | Low | Clear cost warnings in docs |
| Security exposure | High | Medium | Auto-cleanup by default, security guide |
| Azure quota limits | Low | Low | Document quota requirements |
| Breaking changes | High | Very Low | 100% additive implementation |
| Complexity creep | Medium | Low | Strict scope: Phase 1 only initially |

## Decision: Proceed with Phase 1

**Recommendation**: Implement Phase 1 (Public IP per Container) approach.

**Rationale**:
1. ✅ Addresses core use case (VoIP, game servers, etc.)
2. ✅ Simple, maintainable implementation
3. ✅ Reasonable cost for target use cases
4. ✅ Standard Azure features (low risk)
5. ✅ Foundation for future enhancements

**Next Steps**:
1. Review and approve this proposal
2. Begin Phase 1 implementation
3. Conduct user testing with VoIP scenario
4. Iterate based on feedback
5. Release to production

## References

- Azure Container Instances: https://learn.microsoft.com/en-us/azure/container-instances/
- Azure NAT Gateway: https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview
- Azure Public IPs: https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses
- Azure Load Balancer: https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview

## Appendix: Key Code Snippets

### Creating Forwarding IP
```python
# In NetworkManager.py
def create_forwarding_ip(self, name, ports=None):
    tags = {'purpose': 'port-forwarding'}
    if ports:
        tags['ports'] = ','.join([f"{p['port']}/{p['protocol']}" for p in ports])
    
    params = {
        'location': self.location,
        'public_ip_allocation_method': 'Static',
        'sku': PublicIPAddressSku(name='Standard'),
        'tags': tags
    }
    pip = self._client.public_ip_addresses.begin_create_or_update(
        self.resource_group, name, params
    ).result()
    return pip.id, pip.ip_address
```

### Deploying with Port Forwarding
```python
# In InstanceManager.py
if public_ip_name and exposed_ports:
    ip_cfg = IpAddress(
        type="Public",
        ports=[Port(protocol=p["protocol"], port=p["port"]) 
               for p in exposed_ports]
    )

cg = ContainerGroup(
    location=location,
    containers=deploy_instances,
    ip_address=ip_cfg,  # Public IP with forwarded ports
    subnet_ids=subnet_ids,  # Still connected to subnet
    ...
)
```

### CLI Usage
```bash
# Create, deploy, test, cleanup
acido ip create-forwarding voip-ip --ports 5060:udp
acido run voip -im asterisk --public-ip voip-ip --expose-port 5060:udp -d 3600
curl sip:<public-ip>:5060
acido rm voip && acido ip rm voip-ip
```

---

**Document Version**: 1.0  
**Date**: 2025-11-23  
**Status**: Proposal Ready for Review  
**Authors**: Copilot SWE Agent  
**Reviewers**: Xavier Álvarez, Juan Ramón Higueras Pica
