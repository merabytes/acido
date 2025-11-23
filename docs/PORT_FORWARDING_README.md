# Port Forwarding Documentation

This directory contains comprehensive documentation for the port forwarding feature proposal for acido.

## Documents Overview

### 1. [PORT_FORWARDING_SUMMARY.md](../PORT_FORWARDING_SUMMARY.md) ⭐ Start Here
**Executive Summary** - High-level overview for decision makers

- Problem statement and impact
- Recommended solution with rationale
- Cost analysis and comparisons
- Implementation timeline
- Risk assessment
- Quick reference guide

**Best for**: Product managers, architects, stakeholders

### 2. [PORT_FORWARDING_PROPOSAL.md](../PORT_FORWARDING_PROPOSAL.md)
**Technical Proposal** - Complete architecture analysis

- Detailed current architecture review
- Azure NAT Gateway limitations research
- Four alternative solutions evaluated
- Complete cost-benefit analysis
- Security considerations
- Technical specifications
- Open questions and recommendations

**Best for**: Technical leads, architects, engineers evaluating options

### 3. [port_forwarding_implementation.md](./port_forwarding_implementation.md)
**Implementation Guide** - Step-by-step code changes

- Exact code modifications needed
- Complete method signatures
- NetworkManager extensions
- InstanceManager updates
- CLI command additions
- Lambda handler changes
- Helper utilities
- Unit test examples
- Integration testing plan

**Best for**: Engineers implementing the feature

### 4. [port_forwarding_examples.md](./port_forwarding_examples.md)
**Practical Examples** - Real-world use cases

Seven complete examples:
1. VoIP/SIP Server (Asterisk) - with Dockerfile
2. Minecraft Server
3. SSH Jump Host/Bastion
4. Web Server on Custom Port
5. Gaming Server (CS:GO)
6. Database Direct Access (dev only)
7. Docker Registry

Plus:
- Cost comparisons
- Best practices
- Troubleshooting guide
- Security guidelines

**Best for**: End users, solution architects, DevOps engineers

## Quick Navigation

### I want to...

**Understand the feature**
→ Start with [PORT_FORWARDING_SUMMARY.md](../PORT_FORWARDING_SUMMARY.md)

**Evaluate technical options**
→ Read [PORT_FORWARDING_PROPOSAL.md](../PORT_FORWARDING_PROPOSAL.md)

**Implement the feature**
→ Follow [port_forwarding_implementation.md](./port_forwarding_implementation.md)

**See practical examples**
→ Browse [port_forwarding_examples.md](./port_forwarding_examples.md)

**Understand costs**
→ See cost sections in SUMMARY or PROPOSAL

**Review security**
→ Security sections in all documents

## Feature Summary

### What It Does
Enables Azure Container Instances to accept inbound connections from the internet by assigning dedicated public IP addresses with specific port forwarding rules.

### Use Cases
- VoIP/SIP servers
- Game servers (Minecraft, CS:GO, etc.)
- SSH bastion hosts
- Web services on custom ports
- Temporary database access
- Custom protocol servers

### How It Works
```bash
# Create public IP for port forwarding
acido ip create-forwarding voip-ip --ports 5060:udp --ports 5060:tcp

# Deploy container with forwarding
acido run voip-server \
  -im asterisk:latest \
  --public-ip voip-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  -d 86400

# Now your VoIP server can receive calls!
```

### Architecture
```
Before (Egress Only):
  Container → NAT Gateway → Public IP → Internet ✅
  Internet → Public IP → ??? → Container ❌

After (With Port Forwarding):
  Container ↔ Public IP ↔ Internet ✅✅
```

### Cost
- ~$13/month per container with port forwarding
- Includes: Public IP (~$3.60) + Container (~$9.40) + data transfer
- Compare to: Load Balancer (~$29), Azure Firewall (~$900)

### Implementation Status
**Status**: Proposal phase - ready for review and approval

**Estimated Effort**: 2-3 days for Phase 1 implementation
- ~500 lines of code
- 4 new methods in NetworkManager
- CLI command additions
- Lambda operation support
- Comprehensive tests and docs

## Document Relationships

```
PORT_FORWARDING_SUMMARY.md
    ├─ Quick overview
    ├─ Decision rationale
    └─ References detailed docs ↓

PORT_FORWARDING_PROPOSAL.md
    ├─ Architecture deep dive
    ├─ All alternatives evaluated
    ├─ Cost/benefit analysis
    └─ Technical specifications

port_forwarding_implementation.md
    ├─ Step-by-step code guide
    ├─ Exact changes needed
    ├─ Testing strategy
    └─ Implementation ready

port_forwarding_examples.md
    ├─ 7 practical use cases
    ├─ Complete code examples
    ├─ Best practices
    └─ Troubleshooting
```

## Key Decisions

### ✅ Recommended: Public IP per Container (Phase 1)
- Simple implementation
- Direct connectivity
- Reasonable cost (~$13/month)
- Foundation for future enhancements

### ⏳ Future: Azure Load Balancer (Phase 2)
- High availability
- Multiple backend containers
- Higher cost (~$29/month)
- For production workloads

### ❌ Not Recommended: Application Gateway
- Very expensive (~$140/month)
- HTTP/HTTPS only
- Overkill for port forwarding

### ❌ Not Recommended: Azure Firewall
- Extremely expensive (~$900/month)
- Enterprise-only use case
- Complex setup

### ❌ Not Possible: NAT Gateway Inbound
- Azure NAT Gateway does NOT support inbound connections
- Technically infeasible
- Must use alternative approach

## Implementation Roadmap

### Phase 1: Core Implementation (2-3 days)
- [ ] Extend NetworkManager with forwarding IP methods
- [ ] Modify InstanceManager.deploy() for public IPs
- [ ] Add CLI commands (ip create-forwarding, etc.)
- [ ] Update Lambda handler
- [ ] Add port utilities
- [ ] Write unit tests
- [ ] Update documentation

### Phase 2: Advanced Features (Future)
- [ ] Azure Load Balancer integration
- [ ] Port range support (e.g., 10000-20000)
- [ ] DNS labels for public IPs
- [ ] NSG rule management
- [ ] Monitoring and alerting

## Testing Checklist

- [ ] Unit tests: Port parsing and validation
- [ ] Unit tests: IP creation logic
- [ ] Integration: Create IP → Deploy → Test connectivity
- [ ] Integration: VoIP scenario (SIP INVITE)
- [ ] Integration: Multi-protocol (UDP + TCP)
- [ ] Manual: HTTP server test
- [ ] Manual: Cost verification
- [ ] Security: Exposure risk assessment
- [ ] Cleanup: Resource deletion verification

## Contributing

When updating these documents:

1. **Summary**: Update high-level info and decisions
2. **Proposal**: Add technical details and alternatives
3. **Implementation**: Keep code examples current
4. **Examples**: Add new use cases as discovered
5. **This README**: Update navigation and status

Maintain consistency across all documents.

## Questions or Issues?

- Architecture questions → See PROPOSAL
- Implementation details → See IMPLEMENTATION
- Usage examples → See EXAMPLES
- General overview → See SUMMARY

## License

Same as main acido project (MIT License)

## Authors

- Copilot SWE Agent (proposal and documentation)
- Xavier Álvarez (original acido author)
- Juan Ramón Higueras Pica (network architecture)

---

**Last Updated**: 2025-11-23  
**Version**: 1.0  
**Status**: Proposal Ready for Review
