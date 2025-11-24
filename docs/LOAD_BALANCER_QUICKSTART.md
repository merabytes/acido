# Load Balancer Implementation - Quick Reference

## Why This Is Needed

**Problem**: Azure Container Instances does not support assigning a pre-existing public IP directly to a container group. When using `IpAddress(type="Public")`, Azure always creates a random new public IP.

**Impact**: Current `--bidirectional` mode works for inbound connectivity but users cannot control or predict which public IP their container receives.

**Solution**: Implement Azure Load Balancer to route traffic from a specific public IP to containers.

## Documentation Files

| File | Purpose |
|------|---------|
| `LOAD_BALANCER_IMPLEMENTATION.md` | Complete technical specification and architecture |
| `LOAD_BALANCER_IMPLEMENTATION_PROMPT.md` | Detailed implementation guide and prompt |
| `LOAD_BALANCER_QUICKSTART.md` | This file - quick reference |

## Architecture

```
User Traffic → Public IP (User-Selected)
             → Load Balancer (Frontend)
             → Backend Pool
             → Container Group (Private IP)
             → Container Instance
```

## Key Components to Implement

### 1. LoadBalancerManager (`acido/azure_utils/LoadBalancerManager.py`)
- Create/delete Load Balancer resources
- Manage backend pools
- Configure load balancing rules
- Setup health probes

### 2. NetworkManager Updates (`acido/azure_utils/NetworkManager.py`)
- Create VNet with container delegation
- Manage Load Balancer network infrastructure
- Tag resources appropriately

### 3. CLI Updates (`acido/cli.py`)
- Add `--with-load-balancer` flag to `acido ip create`
- Add `--use-load-balancer` flag to `acido run`
- Add validation logic
- Update help text

### 4. InstanceManager Updates (`acido/azure_utils/InstanceManager.py`)
- Deploy containers in VNet without public IP
- Register container IP in backend pool
- Create load balancing rules for exposed ports

## New CLI Commands

```bash
# Create IP with Load Balancer infrastructure
acido ip create <name> --with-load-balancer

# Deploy container using Load Balancer
acido run <name> \
  -im <image> \
  --bidirectional \
  --expose-port <port>:<protocol> \
  --use-load-balancer

# List IPs (shows Load Balancer indicator)
acido ip ls
# Output: voip-ip [with Load Balancer], nat-ip [with NAT stack]

# Remove Load Balancer infrastructure (future)
acido ip rm-lb <name>
```

## Implementation Phases

### Phase 1: Core Load Balancer Management
- Implement LoadBalancerManager class
- Create/delete Load Balancer with public IP
- Create backend pools and health probes
- Tag resources

### Phase 2: Container Integration
- Update InstanceManager.deploy()
- Deploy containers in VNet
- Register containers in backend pool
- Create load balancing rules

### Phase 3: CLI & Validation
- Add CLI flags
- Implement validation logic
- Error handling

### Phase 4: Documentation & Testing
- Update README
- Write unit tests
- Integration testing
- Document costs

## Technical Challenges

### 1. Backend Pool Registration
**Challenge**: Container groups aren't natively supported in Load Balancer backend pools.

**Solution**: Use IP-based backend pool registration via REST API or ARM template.

### 2. Dynamic IP Assignment
**Challenge**: Container private IPs change on restart.

**Solution**: Update backend pool after each deployment/restart.

### 3. Health Probes
**Challenge**: Not all containers have HTTP endpoints.

**Solution**: Use TCP health probes on primary exposed port.

## Cost Impact

- Load Balancer Basic: ~$18/month
- Load Balancer Standard: ~$40-50/month
- Data transfer: ~$0.005/GB
- **Total**: ~$18-50/month per Load Balancer

**Note**: Document clearly as opt-in feature.

## Testing Checklist

- [ ] Create IP with Load Balancer
- [ ] Deploy container with `--use-load-balancer`
- [ ] Verify traffic routes through public IP
- [ ] Test multiple ports (TCP + UDP)
- [ ] Test health probes
- [ ] Test container restart
- [ ] Test cleanup (resource deletion)
- [ ] Verify cost estimations

## Success Criteria

✅ Containers deployed with predictable, stable public IPs  
✅ Traffic routes correctly through Load Balancer  
✅ Multiple ports/protocols supported  
✅ Health monitoring works  
✅ Clean resource lifecycle  
✅ Backward compatible (no breaking changes)  
✅ Clear cost documentation  

## Migration Path

**For existing users**:
1. Current bidirectional mode (random IP) remains default - no breaking changes
2. Load Balancer mode is opt-in via `--use-load-balancer` flag
3. Document differences and when to use each

**Example**:
```bash
# Before (random IP, free)
acido run voip -im asterisk:latest --bidirectional --expose-port 5060:udp

# After (specific IP, Load Balancer cost)
acido ip create voip-ip --with-load-balancer
acido ip select voip-ip
acido run voip -im asterisk:latest --bidirectional --expose-port 5060:udp --use-load-balancer
```

## Quick Start for Implementer

1. Read `LOAD_BALANCER_IMPLEMENTATION.md` for full technical details
2. Read `LOAD_BALANCER_IMPLEMENTATION_PROMPT.md` for step-by-step guide
3. Start with Phase 1: Implement LoadBalancerManager
4. Test each phase before moving to next
5. Document as you go

## Questions?

Refer to:
- `LOAD_BALANCER_IMPLEMENTATION.md` - Technical details
- `LOAD_BALANCER_IMPLEMENTATION_PROMPT.md` - Implementation steps
- Azure Load Balancer documentation
- Azure Container Instances networking documentation

## Priority: HIGH

This addresses a fundamental architectural limitation that prevents users from using acido for critical production workloads requiring stable, predictable public IPs.
