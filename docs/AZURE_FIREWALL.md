# Azure Firewall Integration (Solution 4 - Enterprise)

This document describes how to use Azure Firewall with DNAT (Destination NAT) for enterprise-grade port forwarding to Azure Container Instances.

## ⚠️ Important: Cost Warning

**Azure Firewall is an ENTERPRISE solution with significant costs:**
- **~$1.25/hour (~$900/month)** for the firewall itself
- Additional data processing charges
- Suitable for organizations with enterprise security requirements

**For most use cases**, consider using the `--bidirectional` flag (Solution 1) instead:
- **~$13/month** per container
- Direct public IP assignment
- Simpler setup
- See [Port Forwarding (Bidirectional Connectivity)](#port-forwarding-bidirectional-connectivity) in README.md

## When to Use Azure Firewall

Use Azure Firewall when you need:
- ✅ **Enterprise security features**: Threat intelligence, FQDN filtering
- ✅ **Centralized port forwarding**: Multiple containers behind one firewall
- ✅ **Advanced network rules**: Complex traffic filtering and routing
- ✅ **Hub-spoke topology**: Enterprise network architecture
- ✅ **Compliance requirements**: Regulatory requirements for firewall-based security

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ Resource Group                                                │
│                                                               │
│  ┌──────────────────┐                                        │
│  │ Public IP        │                                        │
│  │ (Firewall IP)    │                                        │
│  │ 20.0.0.1         │                                        │
│  └────────┬─────────┘                                        │
│           │                                                   │
│           ▼                                                   │
│  ┌──────────────────┐      ┌──────────────────────────────┐ │
│  │ Azure Firewall   │      │ Virtual Network               │ │
│  │ (DNAT Rules)     │      │                               │ │
│  │ - 5060:UDP       │──────┼─────┐                         │ │
│  │   → 10.0.1.4     │      │     │                         │ │
│  │ - 8080:TCP       │      │  ┌──▼──────────────────────┐ │ │
│  │   → 10.0.1.5     │      │  │ AzureFirewallSubnet     │ │ │
│  └──────────────────┘      │  │ (Firewall subnet)       │ │ │
│                             │  └─────────────────────────┘ │ │
│                             │                               │ │
│                             │  ┌──────────────────────────┐ │ │
│                             │  │ Delegated Subnet         │ │ │
│                             │  │                          │ │ │
│                             │  │  ┌─────────────────────┐ │ │ │
│                             │  │  │ Container Group     │ │ │ │
│                             │  │  │ (VoIP Server)       │ │ │ │
│                             │  │  │ Private IP: 10.0.1.4│ │ │ │
│                             │  │  │ Port: 5060 UDP      │ │ │ │
│                             │  │  └─────────────────────┘ │ │ │
│                             │  │                          │ │ │
│                             │  │  ┌─────────────────────┐ │ │ │
│                             │  │  │ Container Group     │ │ │ │
│                             │  │  │ (Web Server)        │ │ │ │
│                             │  │  │ Private IP: 10.0.1.5│ │ │ │
│                             │  │  │ Port: 8080 TCP      │ │ │ │
│                             │  │  └─────────────────────┘ │ │ │
│                             │  └──────────────────────────┘ │ │
│                             └──────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘

Traffic Flow:
Internet → 20.0.0.1:5060 → Azure Firewall (DNAT) → 10.0.1.4:5060 (VoIP)
Internet → 20.0.0.1:8080 → Azure Firewall (DNAT) → 10.0.1.5:8080 (Web)
```

## Prerequisites

1. **Resource Group**: Azure resource group
2. **No manual setup required**: The `acido firewall create` command automatically creates:
   - Virtual Network (VNet)
   - `AzureFirewallSubnet` (minimum /26 for firewall)
   - `container-ingress-subnet` (for container instances)
   - Public IP for the firewall
3. **Budget**: ~$900/month for firewall + container costs

## Quick Start

### Step 1: Create Azure Firewall (Auto-creates full network stack)

```bash
# Create resource group (if not exists)
az group create --name acido-firewall-rg --location westeurope

# Create Azure Firewall with full network stack (~$900/month)
# This automatically creates: VNet, AzureFirewallSubnet, container subnet, and Public IP
acido firewall create my-firewall \
  --vnet my-vnet \
  --subnet AzureFirewallSubnet \
  --public-ip fw-public-ip
```

This will take 5-10 minutes to deploy and automatically creates:
- Public IP: `fw-public-ip`
- Virtual Network: `my-vnet` (10.0.0.0/16)
- Firewall Subnet: `AzureFirewallSubnet` (10.0.0.0/26)
- Container Subnet: `container-ingress-subnet` (10.0.2.0/24)

### Step 2: Deploy Container with Private IP

```bash
# Deploy VoIP server - automatically uses firewall ingress subnet
acido run voip-server \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --cpu 2 \
  --ram 4 \
  -d 86400

# Container automatically gets:
# - Private IP in container-ingress-subnet
# - FIREWALL_PUBLIC_IP environment variable
# - FIREWALL_NAME environment variable

# Get the container's private IP
acido ls
# Note the private IP (e.g., 10.0.2.4)
```

### Step 3: Add DNAT Rule to Forward Traffic

```bash
# The firewall public IP is already injected in the container as FIREWALL_PUBLIC_IP
# You can also get it from the firewall config or Azure portal

# Add DNAT rule to forward UDP port 5060 to container
acido firewall add-rule my-firewall \
  --rule-name voip-sip-udp \
  --collection voip-rules \
  --dest-ip <FIREWALL_PUBLIC_IP> \
  --dest-port 5060 \
  --target-ip 10.0.2.4 \
  --target-port 5060 \
  --protocol UDP

# Add DNAT rule for TCP as well
acido firewall add-rule my-firewall \
  --rule-name voip-sip-tcp \
  --collection voip-rules \
  --dest-ip <FIREWALL_PUBLIC_IP> \
  --dest-port 5060 \
  --target-ip 10.0.2.4 \
  --target-port 5060 \
  --protocol TCP
```

### Step 4: Test Connectivity

```bash
# Test TCP connectivity
telnet <FIREWALL_PUBLIC_IP> 5060
```

### Step 5: List and Manage Firewalls

```bash
# List all firewalls
acido firewall ls

# Remove DNAT rule
acido firewall delete-rule my-firewall \
  --rule-name voip-sip-udp \
  --collection voip-rules

# Remove firewall and entire network stack (saves ~$900/month)
acido firewall rm my-firewall
# This deletes:
# - Azure Firewall
# - Virtual Network (VNet)
# - All subnets (AzureFirewallSubnet, container-ingress-subnet)
# - Clears firewall configuration from config
```

## CLI Commands

### Firewall Management

```bash
# Create firewall
acido firewall create <name> \
  --vnet <vnet-name> \
  --subnet <subnet-name> \
  --public-ip <public-ip-name>

# List firewalls
acido firewall ls

# Remove firewall and network stack
acido firewall rm <name>
# Deletes: Firewall, VNet, all subnets, and clears config
```

### DNAT Rule Management

```bash
# Add DNAT rule
acido firewall add-rule <firewall-name> \
  --rule-name <rule-name> \
  --collection <collection-name> \
  --source <source-ip> \  # Optional, defaults to "*" (any)
  --dest-ip <firewall-public-ip> \
  --dest-port <port> \
  --target-ip <container-private-ip> \
  --target-port <port> \
  --protocol <TCP|UDP|Any>

# Delete DNAT rule
acido firewall delete-rule <firewall-name> \
  --rule-name <rule-name> \
  --collection <collection-name>
```

## Examples

### Example 1: VoIP Server (Asterisk)

```bash
# 1. Create firewall infrastructure
acido ip create voip-ip --with-nat-stack
acido firewall create voip-firewall \
  --vnet voip-ip-vnet \
  --subnet AzureFirewallSubnet \
  --public-ip voip-ip

# 2. Deploy VoIP server with private IP
acido run asterisk-prod \
  -im asterisk:latest \
  -t "./start-asterisk.sh" \
  --cpu 4 \
  --ram 8 \
  -d 86400

# 3. Get container private IP (assume 10.0.1.4)
# 4. Add DNAT rules for SIP signaling
acido firewall add-rule voip-firewall \
  --rule-name sip-udp \
  --collection voip \
  --dest-ip <FW_PUBLIC_IP> \
  --dest-port 5060 \
  --target-ip 10.0.1.4 \
  --target-port 5060 \
  --protocol UDP

# 5. Test: External SIP clients can now connect to <FW_PUBLIC_IP>:5060
```

### Example 2: Multiple Containers Behind One Firewall

```bash
# Deploy multiple containers
acido run web-server \
  -im nginx:latest \
  --cpu 2 --ram 4 -d 86400

acido run api-server \
  -im myapi:latest \
  --cpu 2 --ram 4 -d 86400

# Forward different ports to different containers
acido firewall add-rule my-firewall \
  --rule-name web-http \
  --collection web-rules \
  --dest-ip <FW_PUBLIC_IP> \
  --dest-port 80 \
  --target-ip 10.0.1.5 \
  --target-port 80 \
  --protocol TCP

acido firewall add-rule my-firewall \
  --rule-name api-https \
  --collection web-rules \
  --dest-ip <FW_PUBLIC_IP> \
  --dest-port 443 \
  --target-ip 10.0.1.6 \
  --target-port 443 \
  --protocol TCP
```

### Example 3: Using Port Ranges

Port ranges are useful when you need to expose multiple consecutive ports (e.g., RTP media streams, game server ports).

```bash
# Deploy game server with port range for player connections
acido run game-server \
  -im myapp/gameserver:latest \
  -t "./start.sh" \
  --expose-port 7777:tcp \
  --expose-port 27015-27020:udp \
  --cpu 4 --ram 8

# This automatically creates:
# - 1 DNAT rule for TCP port 7777
# - 6 DNAT rules for UDP ports 27015, 27016, 27017, 27018, 27019, 27020

# Deploy VoIP server with RTP port range
acido run voip-server \
  -im asterisk:latest \
  -t "./start.sh" \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --expose-port 10000-10099:udp \
  --cpu 4 --ram 8

# This creates 102 DNAT rules total:
# - 2 for SIP signaling (5060 UDP/TCP)
# - 100 for RTP media streams (10000-10099 UDP)
```

**Port Range Limits:**
- Maximum 100 ports per range specification
- Ranges are expanded: `5060-5062:udp` creates rules for 5060, 5061, and 5062
- Format: `START_PORT-END_PORT:PROTOCOL` (e.g., `10000-10099:udp`)

## Comparison: Firewall vs Bidirectional

| Feature | Firewall (Solution 4) | Bidirectional (Solution 1) |
|---------|----------------------|----------------------------|
| **Cost** | ~$900/month | ~$13/month per container |
| **Complexity** | High (hub-spoke) | Low (direct IP) |
| **Security Features** | Advanced (FQDN, threat intel) | Basic (NSG rules) |
| **Centralized Control** | ✅ Yes | ❌ No |
| **Multiple Containers** | ✅ Shared firewall | ⚠️ One IP per container |
| **Port Translation** | ✅ Yes | ❌ No |
| **Setup Time** | 5-10 minutes | 1-2 minutes |
| **Use Case** | Enterprise | Individual containers |

## Troubleshooting

### Firewall creation takes too long
Azure Firewall deployment typically takes 5-10 minutes. If it takes longer than 15 minutes, check Azure Portal for deployment status.

### DNAT rule not working
1. Verify firewall public IP: `az network public-ip show ...`
2. Check container private IP: `acido ls`
3. Verify subnet configuration
4. Check NSG rules (if any)
5. Test internal connectivity first

### High costs
Azure Firewall is expensive (~$900/month). Consider:
- Using `--bidirectional` flag for individual containers (~$13/month)
- Consolidating multiple containers behind one firewall
- Using firewall only for production environments

## Best Practices

1. **Cost Management**:
   - Use firewall only when enterprise features are needed
   - Consider `--bidirectional` for dev/test environments
   - Monitor monthly costs in Azure Portal

2. **Security**:
   - Restrict source IPs in DNAT rules when possible
   - Use Network Security Groups (NSGs) for additional filtering
   - Enable Azure Firewall threat intelligence

3. **Network Design**:
   - Use /26 or larger subnet for Azure Firewall
   - Plan IP address space carefully
   - Document all DNAT rules

4. **Operations**:
   - Use descriptive names for rules and collections
   - Tag resources for cost tracking
   - Monitor firewall logs in Azure Monitor

## References

- [Azure Firewall Documentation](https://docs.microsoft.com/azure/firewall/)
- [Azure Firewall DNAT Rules](https://docs.microsoft.com/azure/firewall/tutorial-firewall-dnat)
- [Port Forwarding Proposal](../docs/PORT_FORWARDING_PROPOSAL.md)
- [Solution Comparison](../docs/PORT_FORWARDING_SUMMARY.md)

## Support

For issues or questions:
1. Check [GitHub Issues](https://github.com/merabytes/acido/issues)
2. Review documentation in `docs/` directory
3. Contact: Xavier Álvarez (xalvarez@merabytes.com)
