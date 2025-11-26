# Automatic Firewall Rule Creation with --expose-ip

## Overview

The `--expose-ip` flag enables automatic creation of Azure Firewall rules when running containers with `acido run`. This feature eliminates the need to manually configure firewall rules using `acido firewall add-rule` commands.

## What Does It Do?

When you use `--expose-ip` with `--bidirectional` and `--expose-port`, acido automatically creates:

1. **Route Table**: Routes all traffic (0.0.0.0/0) from the container subnet through the Azure Firewall
2. **Network Rules**: Allows outbound traffic from containers (10.0.2.0/24) to any destination
3. **NAT Rules**: Creates DNAT rules to forward traffic from the specified public IP addresses to the container's private IP

**Important**: `--expose-ip` can be specified multiple times to create NAT rules for multiple public IP addresses. Each IP/port combination creates a separate NAT rule.

## Requirements

- **Configured Firewall**: You must have an Azure Firewall configured using `acido firewall create`
- **--expose-port**: You must specify at least one port to expose
- **--bidirectional**: You must use the bidirectional flag to enable this mode
- **--expose-ip**: Specify one or more public IP addresses

## Usage

### Basic Example (Single IP)

```bash
# Create a firewall first (one-time setup)
acido firewall create my-firewall --vnet my-vnet --public-ip my-firewall-ip

# Run a container with automatic firewall rules for a single public IP
acido run voip-server \
  --image asterisk \
  --bidirectional \
  --expose-ip 20.50.100.1 \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --duration 3600
```

### Multiple IP Addresses

You can expose the same container on multiple public IPs by specifying `--expose-ip` multiple times:

```bash
# Expose container on two different public IPs
acido run multi-ip-service \
  --image nginx \
  --bidirectional \
  --expose-ip 20.50.100.1 \
  --expose-ip 20.50.100.2 \
  --expose-port 80:tcp \
  --expose-port 443:tcp \
  --duration 7200
```

This creates NAT rules for:
- `20.50.100.1:80` → container:80 (TCP)
- `20.50.100.1:443` → container:443 (TCP)
- `20.50.100.2:80` → container:80 (TCP)
- `20.50.100.2:443` → container:443 (TCP)

### What Happens Behind the Scenes

1. **Route Table Creation**:
   - Name: `container-ingress-subnet-route-table`
   - Route: `0.0.0.0/0` → Firewall Private IP (e.g., `10.0.0.4`)
   - Next Hop Type: VirtualAppliance

2. **Network Rule Creation**:
   - Collection: `acido-container-outbound`
   - Rule Name: `<container-name>-outbound-rule`
   - Source: `10.0.2.0/24` (container subnet)
   - Destination: `*` (any)
   - Ports: All ports specified in --expose-port
   - Protocols: All protocols specified in --expose-port

3. **NAT Rule Creation** (one per IP/port combination):
   - Collection: `acido-auto-nat`
   - Rule Name: `<container-name>-nat-<ip-address>-<port>-<protocol>` (IP dots replaced with dashes)
   - Source: `*` (any source IP)
   - Destination: Specified public IP address from --expose-ip
   - Destination Port: The exposed port
   - Translated Address: `10.0.2.4` (first container in subnet)
   - Translated Port: Same as destination port
   - Protocol: TCP, UDP, or both

**Note**: With multiple IPs and multiple ports, the number of NAT rules created = (number of IPs) × (number of ports)

## Multiple Ports Example

```bash
acido run web-server \
  --image nginx \
  --bidirectional \
  --expose-ip 20.50.100.1 \
  --expose-port 80:tcp \
  --expose-port 443:tcp \
  --expose-port 8080:tcp \
  --duration 7200
```

This creates:
- 1 route table
- 1 network rule (with ports 80, 443, 8080)
- 3 NAT rules (one for each port on the single IP)

## Port Ranges

You can also specify port ranges and multiple IPs:

```bash
acido run game-server \
  --image game-image \
  --bidirectional \
  --expose-ip 20.50.100.1 \
  --expose-ip 20.50.100.2 \
  --expose-port 25565:tcp \
  --expose-port 10000-10099:udp \
  --duration 86400
```

This creates:
- 1 route table
- 1 network rule (with ports 25565 and 10000-10099)
- 202 NAT rules (2 IPs × 101 ports: 1 TCP + 100 UDP per IP)

## Accessing Your Container

After the container is created, you can access it using the specified public IPs:

```bash
# For VoIP example with IP 20.50.100.1:
sip:user@20.50.100.1:5060

# For web server example:
http://20.50.100.1:80
http://20.50.100.2:80
```

## Error Scenarios

### No Firewall Configured

```bash
acido run test --expose-ip 20.50.100.1 --expose-port 80:tcp
```

**Error**: `--expose-ip requires a configured firewall`

**Solution**: Create a firewall first using `acido firewall create`

### Missing --expose-port

```bash
acido run test --bidirectional --expose-ip 20.50.100.1
```

**Error**: `--expose-ip requires --expose-port to be specified`

**Solution**: Add `--expose-port` flag with at least one port

### Missing --bidirectional

If you use `--expose-ip` without `--bidirectional`, the automatic rule creation will not happen. You must use both flags together.

## Cost Considerations

Using `--expose-ip` with Azure Firewall has a significant cost:

- **Azure Firewall**: ~$1.25/hour (~$900/month)
- **Additional costs**: Data processing charges apply

### When to Use --expose-ip

✅ **Use when**:
- You need enterprise-grade security
- You need centralized firewall management
- You're already using Azure Firewall for other purposes
- You need advanced threat protection

❌ **Don't use when**:
- You just need simple port forwarding
- Cost is a primary concern
- You only need temporary access

### Alternative: Direct Public IP (--bidirectional only)

For simple use cases, use `--bidirectional` without `--expose-ip`:

```bash
acido run test-server \
  --bidirectional \
  --expose-port 80:tcp \
  --duration 600
```

**Cost**: ~$13/month for public IP (much cheaper than firewall)

## Flag Combinations

| Flags | Behavior | Use Case |
|-------|----------|----------|
| `--expose-port` | Container with port exposed (no inbound) | Default, current functionality |
| `--expose-port --bidirectional` | Direct public IP assignment | Simple port forwarding (~$13/month) |
| `--expose-port --bidirectional --expose-ip` | Firewall with automatic rules | Enterprise security (~$900/month) |

## Cleanup

When the container is deleted (auto-cleanup or manual), the firewall rules remain. To clean up:

```bash
# Remove specific NAT rules
acido firewall delete-rule my-firewall \
  --rule-name voip-server-nat-5060-udp \
  --collection acido-auto-nat

# Or delete the entire firewall
acido firewall rm my-firewall
```

## Troubleshooting

### Rules Not Created

Check logs for error messages. Common issues:
- Insufficient permissions to modify firewall
- Route table already exists
- Network rule collection limit reached

### Can't Access Container

1. Verify firewall public IP: `acido firewall ls`
2. Check NAT rules are created: View in Azure Portal
3. Verify container is running: `acido ls`
4. Check network connectivity from source

### Subnet Issues

If the container subnet doesn't exist, acido will try to create it. Ensure:
- VNet has address space available (10.0.2.0/24)
- No conflicting subnets exist

## Advanced: Manual Rule Management

While `--expose-ip` automates rule creation, you can still use manual commands:

```bash
# View firewall details
acido firewall ls

# Add custom rule
acido firewall add-rule my-firewall \
  --rule-name custom-rule \
  --dest-ip <firewall-public-ip> \
  --dest-port 9000 \
  --target-ip 10.0.2.5 \
  --target-port 9000 \
  --protocol TCP

# Delete rule
acido firewall delete-rule my-firewall \
  --rule-name custom-rule
```

## Implementation Details

### Route Table
- **Name**: `<subnet-name>-route-table`
- **Route**: 0.0.0.0/0 → Firewall Private IP
- **Associated**: Container subnet

### Network Rule
- **Collection**: `acido-container-outbound`
- **Priority**: 200
- **Action**: Allow
- **Source**: 10.0.2.0/24
- **Destination**: * (any)

### NAT Rules
- **Collection**: `acido-auto-nat`
- **Priority**: 100
- **Action**: DNAT
- **Source**: * (any)
- **Destination**: Firewall Public IP
- **Translated**: Container Private IP (10.0.2.4)

## Lambda/API Usage

The `--expose-ip` flag is also supported via Lambda handler. You can specify multiple IPs:

```json
{
  "operation": "run",
  "name": "api-server",
  "image": "api-image",
  "bidirectional": true,
  "expose_ips": ["20.50.100.1", "20.50.100.2"],
  "exposed_ports": [
    {"port": 8080, "protocol": "TCP"},
    {"port": 8443, "protocol": "TCP"}
  ],
  "duration": 900
}
```

This creates 4 NAT rules (2 IPs × 2 ports).

## Best Practices

1. **Use descriptive names**: Name containers clearly to identify NAT rules later
2. **Limit port ranges**: Large port ranges create many NAT rules
3. **Clean up**: Remove unused rules to avoid clutter
4. **Monitor costs**: Azure Firewall costs add up quickly
5. **Test first**: Use `--bidirectional` alone for testing before adding firewall
6. **Document rules**: Keep track of which containers use which ports

## Summary

The `--expose-ip` flag provides enterprise-grade port forwarding through Azure Firewall with automatic rule creation, eliminating manual firewall configuration. Use it when you need centralized security management, but be aware of the significant cost (~$900/month).
