# Port Forwarding Feature - Complete Documentation Index

**Status**: ✅ Proposal Complete - Ready for Review  
**Version**: 1.0  
**Date**: 2025-11-23  
**Branch**: `copilot/add-port-forwarding-feature`

---

## 📋 Quick Start Guide

### For Decision Makers
→ Read [PORT_FORWARDING_SUMMARY.md](PORT_FORWARDING_SUMMARY.md) (5 min read)
- What problem does this solve?
- What's the recommended solution?
- How much will it cost?
- When can we implement it?

### For Technical Leads
→ Read [PORT_FORWARDING_PROPOSAL.md](PORT_FORWARDING_PROPOSAL.md) (15 min read)
- Complete architecture analysis
- All alternatives evaluated
- Technical specifications
- Security considerations

### For Engineers
→ Read [docs/port_forwarding_implementation.md](docs/port_forwarding_implementation.md) (20 min read)
- Step-by-step code changes
- Complete method signatures
- Testing strategy
- Ready to implement

### For Users/DevOps
→ Read [docs/port_forwarding_examples.md](docs/port_forwarding_examples.md) (15 min read)
- 7 practical use cases
- Complete working examples
- Best practices
- Troubleshooting

### For Visual Learners
→ Read [docs/PORT_FORWARDING_DIAGRAMS.md](docs/PORT_FORWARDING_DIAGRAMS.md) (10 min read)
- Architecture diagrams
- Traffic flow illustrations
- Cost breakdowns
- Security zones

---

## 📚 All Documentation

| Document | Lines | Purpose | Audience |
|----------|-------|---------|----------|
| [PORT_FORWARDING_SUMMARY.md](PORT_FORWARDING_SUMMARY.md) | 461 | Executive summary | Decision makers |
| [PORT_FORWARDING_PROPOSAL.md](PORT_FORWARDING_PROPOSAL.md) | 612 | Technical proposal | Architects, tech leads |
| [docs/port_forwarding_implementation.md](docs/port_forwarding_implementation.md) | 765 | Implementation guide | Engineers |
| [docs/port_forwarding_examples.md](docs/port_forwarding_examples.md) | 435 | Use case examples | Users, DevOps |
| [docs/PORT_FORWARDING_README.md](docs/PORT_FORWARDING_README.md) | 262 | Navigation guide | Everyone |
| [docs/PORT_FORWARDING_DIAGRAMS.md](docs/PORT_FORWARDING_DIAGRAMS.md) | 673 | Visual diagrams | Visual learners |
| **TOTAL** | **3,208** | **Complete proposal** | **All stakeholders** |

---

## 🎯 Problem Statement

**Current State**: Acido containers can make outbound connections via NAT Gateway but **cannot accept inbound connections** from the internet.

**Impact**: This prevents use cases requiring bidirectional connectivity:
- ❌ VoIP/SIP servers (cannot receive incoming calls)
- ❌ Game servers (players cannot connect)
- ❌ SSH bastions (cannot access from internet)
- ❌ Custom protocol servers

**Goal**: Enable containers to accept inbound connections on specific ports while maintaining security and backward compatibility.

---

## ✅ Recommended Solution

### Public IP per Container Approach

**What**: Assign dedicated Azure public IP addresses to containers that require inbound connectivity.

**Why**:
- ✅ Simple implementation (~500 lines of code)
- ✅ Uses standard Azure features (low risk)
- ✅ Reasonable cost (~$13/month per container)
- ✅ Backward compatible (existing containers unchanged)
- ✅ Production-ready

**How**:
```bash
# 1. Create public IP for port forwarding
acido ip create-forwarding voip-ip --ports 5060:udp --ports 5060:tcp

# 2. Deploy container with port forwarding
acido run voip-server \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --public-ip voip-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  -d 86400

# 3. Now your VoIP server can receive inbound SIP calls! ✅
```

---

## 🔍 Key Findings

### Critical Discovery: NAT Gateway Cannot Do Inbound

**Finding**: Azure NAT Gateway does **NOT** support inbound connections or DNAT (Destination NAT).

**Source**: Official Azure documentation

**Impact**: The NAT Gateway approach is technically infeasible. Must use alternative architecture.

**Solution**: Assign public IPs directly to container groups that need inbound connectivity.

---

## 🏗️ Architecture Overview

### Current Architecture (Egress Only)
```
Container → NAT Gateway → Public IP → Internet ✅
Internet → Public IP → NAT Gateway → ??? ❌ (Not possible)
```

### Proposed Architecture (Dual Mode)
```
Regular Container:
  Container → NAT Gateway → Public IP → Internet ✅

Port-Forwarded Container:
  Container ↔ Public IP ↔ Internet ✅✅ (Bidirectional)
```

**Key Insight**: Containers can have BOTH subnet connectivity (VNet) AND public IP (internet) simultaneously.

---

## 💰 Cost Analysis

### Per Container Comparison

| Configuration | Components | Monthly Cost |
|---------------|------------|--------------|
| **Regular Container** | Container + shared NAT Gateway | ~$11 |
| **Port-Forwarded** | Container + dedicated Public IP | ~$13 |
| **With Load Balancer** | Container + LB + Public IP | ~$38 |
| **With App Gateway** | Container + AppGW | ~$149 |
| **With Firewall** | Container + Azure Firewall | ~$909 |

**Recommendation**: Public IP per container provides best cost/benefit ratio.

---

## 🛠️ Implementation Plan

### Phase 1: Core Implementation (2-3 days)

**Code Changes** (~500 lines):
1. **NetworkManager.py** - Add 4 methods for forwarding IPs
2. **InstanceManager.py** - Modify `deploy()` to support public IPs
3. **cli.py** - Add 3 new CLI commands
4. **lambda_handler.py** - Add 2 new operations
5. **port_utils.py** - New utility module for port parsing

**New CLI Commands**:
- `acido ip create-forwarding <name> --ports PORT:PROTOCOL`
- `acido ip ls-forwarding`
- `acido run <name> --public-ip <ip> --expose-port PORT:PROTOCOL`

**Testing**:
- Unit tests for port parsing/validation
- Integration tests for end-to-end flows
- Manual verification with real services

### Phase 2: Advanced Features (Future)
- Azure Load Balancer integration
- Port range support (e.g., 10000-20000)
- NSG rule management
- DNS labels for public IPs
- Monitoring and alerting

---

## 📖 Use Cases with Examples

### 1. VoIP/SIP Server (Asterisk)
**Requirements**: Port 5060 UDP/TCP for SIP signaling  
**Cost**: ~$13/month  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-1-voipsip-server-asterisk)

### 2. Minecraft Server
**Requirements**: Port 25565 TCP  
**Cost**: ~$13/month  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-2-minecraft-server)

### 3. SSH Jump Host/Bastion
**Requirements**: Port 22 TCP  
**Cost**: ~$13/month (time-limited for security)  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-3-ssh-jump-host)

### 4. Web Server on Custom Port
**Requirements**: Port 8080 TCP  
**Cost**: ~$13/month  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-4-web-server-with-custom-port)

### 5. Gaming Server (CS:GO)
**Requirements**: Ports 27015 TCP/UDP, 27020 UDP  
**Cost**: ~$13/month  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-5-gaming-server-csgo)

### 6. Database Access (Dev Only)
**Requirements**: Port 5432 TCP (PostgreSQL)  
**Cost**: ~$13/month  
**⚠️ Warning**: Development only, never expose production DBs  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-6-database-direct-access-development-only)

### 7. Docker Registry
**Requirements**: Port 5000 TCP  
**Cost**: ~$13/month  
**Documentation**: [See full example →](docs/port_forwarding_examples.md#example-7-multi-port-application-docker-registry)

---

## 🔒 Security Considerations

### Risks
1. **Direct Internet Exposure**: Containers with public IPs are accessible from anywhere
2. **DDoS Potential**: Exposed services are targets for attacks
3. **Application Security**: Must implement auth, rate limiting at app level

### Mitigations
1. **Auto-Cleanup**: Use duration limits (`-d`) for temporary services
2. **Application-Level Auth**: Enforce authentication in the application
3. **Rate Limiting**: Implement at application layer
4. **Monitoring**: Track and alert on anomalous traffic
5. **Time-Limited Access**: Use short durations for testing/dev

### Best Practices
```bash
# ✅ Good: Time-limited test server
acido run test-server --public-ip test-ip --expose-port 8080:tcp -d 600

# ✅ Good: Production with proper security
acido run prod-service --public-ip prod-ip --expose-port 443:tcp --no-cleanup
# (Ensure HTTPS, auth, monitoring in the application)

# ❌ Bad: Long-running exposed service without protection
acido run exposed-db --public-ip db-ip --expose-port 5432:tcp --no-cleanup
# (Never do this!)
```

---

## 🧪 Testing Strategy

### Unit Tests
- Port specification parsing (`5060:udp` → `{port: 5060, protocol: "UDP"}`)
- Port number validation (1-65535)
- Protocol validation (TCP/UDP only)
- Public IP creation logic
- Container deployment with ports

### Integration Tests
- End-to-end: Create IP → Deploy container → Test connectivity
- VoIP scenario: SIP INVITE handling
- Multi-protocol: UDP + TCP on same port
- Cleanup verification

### Manual Verification
```bash
# Deploy test HTTP server
acido ip create-forwarding test-ip --ports 8080:tcp
acido run nginx-test -im nginx:alpine --public-ip test-ip --expose-port 8080:tcp -d 600

# Test connectivity
curl http://<public-ip>:8080

# Verify cleanup after 10 minutes
```

---

## 🔄 Backward Compatibility

✅ **100% Backward Compatible**

- All changes are additive (no breaking changes)
- Existing containers continue to work unchanged
- NAT Gateway remains default for egress
- No changes to configuration file format
- No changes to existing APIs

**Migration**: None required. Feature is opt-in.

```bash
# Old way (still works)
acido run scanner -im nmap -t "nmap -iL input" -d 3600

# New way (opt-in for port forwarding)
acido run voip -im asterisk --public-ip voip-ip --expose-port 5060:udp -d 86400
```

---

## 📊 Alternatives Considered

| Solution | Status | Pros | Cons | Cost/Month |
|----------|--------|------|------|------------|
| **Public IP per Container** | ✅ Recommended | Simple, direct | One IP per container | ~$13 |
| **Load Balancer** | ⏳ Phase 2 | HA, multiple backends | Complex for single container | ~$29 |
| **Application Gateway** | ❌ Not recommended | SSL, WAF, routing | Very expensive, HTTP only | ~$140 |
| **Azure Firewall** | ❌ Not recommended | Enterprise features | Extremely expensive | ~$900 |
| **NAT Gateway Inbound** | ❌ Not possible | N/A | Azure doesn't support it | N/A |

**Decision**: Proceed with Public IP per Container for Phase 1.

---

## 📅 Timeline

### Week 1: Implementation
- Days 1-2: Core implementation (NetworkManager, InstanceManager)
- Days 3-4: CLI commands and Lambda support
- Days 5-6: Testing and bug fixes
- Day 7: Documentation updates

### Week 2: Review and Polish
- Code review and refinements
- Additional testing scenarios
- Documentation review
- User acceptance testing

### Week 3: Release
- Merge to main branch
- Release notes and changelog
- Announcement (blog post, social media)
- User onboarding materials

---

## ✅ Success Criteria

### Functional Requirements
- ✅ Create dedicated public IPs for port forwarding
- ✅ Deploy containers with specific exposed ports
- ✅ Support both TCP and UDP protocols
- ✅ List and manage forwarding IPs
- ✅ Lambda operation support
- ✅ Maintain 100% backward compatibility

### Non-Functional Requirements
- ✅ Simple CLI interface (3 new commands)
- ✅ Minimal code changes (~500 lines)
- ✅ Clear documentation with examples
- ✅ Reasonable cost (~$13/month per container)
- ✅ Production-ready implementation
- ✅ Comprehensive testing

---

## 🚀 Next Steps

### For Review/Approval
1. Review [PORT_FORWARDING_SUMMARY.md](PORT_FORWARDING_SUMMARY.md) for high-level overview
2. Review [PORT_FORWARDING_PROPOSAL.md](PORT_FORWARDING_PROPOSAL.md) for technical details
3. Approve/reject the proposal
4. Provide feedback or request changes

### For Implementation (After Approval)
1. Create feature branch from main
2. Follow [docs/port_forwarding_implementation.md](docs/port_forwarding_implementation.md)
3. Implement Phase 1 features
4. Write and run tests
5. Update documentation
6. Submit PR for review

### For Questions
- Architecture questions → See [PROPOSAL](PORT_FORWARDING_PROPOSAL.md)
- Implementation details → See [IMPLEMENTATION](docs/port_forwarding_implementation.md)
- Usage examples → See [EXAMPLES](docs/port_forwarding_examples.md)
- Visual aids → See [DIAGRAMS](docs/PORT_FORWARDING_DIAGRAMS.md)

---

## 📞 Contact

**Proposal Author**: Copilot SWE Agent  
**Acido Authors**: Xavier Álvarez, Juan Ramón Higueras Pica  
**Repository**: [merabytes/acido](https://github.com/merabytes/acido)  
**Branch**: `copilot/add-port-forwarding-feature`

---

## 📄 Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-23 | 1.0 | Initial proposal complete |

---

## 🙏 Acknowledgments

- Azure Container Instances documentation
- Azure NAT Gateway research
- Acido community and contributors
- Original acido architecture by Xavier & Juan

---

**End of Index** | [Back to Top ↑](#port-forwarding-feature---complete-documentation-index)
