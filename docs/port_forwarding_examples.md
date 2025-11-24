# Port Forwarding Examples

This document provides practical examples of port forwarding use cases with acido.

## Example 1: VoIP/SIP Server (Asterisk)

### Scenario
Deploy an Asterisk VoIP server that can:
- Accept incoming SIP calls from external providers
- Register with external SIP trunks
- Handle bidirectional RTP media streams

### Requirements
- Port 5060 UDP/TCP (SIP signaling)
- Port 5061 TCP (SIP TLS)
- Ports 10000-20000 UDP (RTP media - configurable)

### Setup

```bash
# 1. Create public IP for VoIP server
# This automatically creates the network stack: asterisk-ip, asterisk-ip-vnet, asterisk-ip-subnet
acido ip create-forwarding asterisk-ip \
  --ports 5060:udp \
  --ports 5060:tcp \
  --ports 5061:tcp

# 2. Build Asterisk image (if not already built)
acido create asterisk --image asterisk:latest

# 3. Deploy Asterisk with port forwarding
# Note: Subnet configuration is automatically derived from --public-ip parameter
# No need to run 'acido ip select' or read from config!
acido run asterisk-prod \
  -im asterisk \
  -t "./start-asterisk.sh" \
  --public-ip asterisk-ip \
  --expose-port 5060:udp \
  --expose-port 5060:tcp \
  --expose-port 5061:tcp \
  -d 86400  # 24 hours

# The command automatically uses:
#   - VNet: asterisk-ip-vnet
#   - Subnet: asterisk-ip-subnet
# (derived from public IP name 'asterisk-ip')

# 4. Get the public IP address
acido ip ls
# Output: asterisk-ip (203.0.113.45) [Ports: 5060/UDP, 5060/TCP, 5061/TCP]

# 5. Configure SIP trunk with IP 203.0.113.45:5060
# Now external providers can send SIP INVITE to your server!

# 6. Clean up when done
acido rm asterisk-prod
acido ip rm asterisk-ip  # Removes IP, VNet, subnet, and NAT gateway
```

### Important Notes

**Automatic Network Configuration:**
- When you specify `--public-ip asterisk-ip`, the system automatically derives:
  - VNet name: `asterisk-ip-vnet`
  - Subnet name: `asterisk-ip-subnet`
- No need to manually select IP or read from config file!

**Config Warnings:**
If you have an IP selected in your config (via `acido ip select`) but don't specify `--public-ip`, you'll see:
```
Warning: IP 'old-ip' is selected in config but --public-ip not specified
The container will use NAT Gateway for egress only (no port forwarding)
To use port forwarding: add --public-ip old-ip
To clear config: run 'acido ip clean'
```

**Cleaning Config:**
```bash
# Remove stored IP configuration from local config
acido ip clean
```

### Docker Image Example

```dockerfile
# Dockerfile.asterisk
FROM alpine:latest

RUN apk add --no-cache asterisk asterisk-sample-config

# Copy custom configuration
COPY asterisk-config/ /etc/asterisk/

# Configure Asterisk to use container's private IP
RUN sed -i 's/bindaddr=0.0.0.0/bindaddr=0.0.0.0/' /etc/asterisk/sip.conf

EXPOSE 5060/udp 5060/tcp 5061/tcp

CMD ["/usr/sbin/asterisk", "-f", "-vvv"]
```

### Lambda Deployment

```json
{
  "operation": "run",
  "name": "asterisk-prod",
  "image": "asterisk",
  "task": "/usr/sbin/asterisk -f -vvv",
  "public_ip_name": "asterisk-ip",
  "exposed_ports": [
    {"port": 5060, "protocol": "UDP"},
    {"port": 5060, "protocol": "TCP"},
    {"port": 5061, "protocol": "TCP"}
  ],
  "duration": 86400,
  "regions": ["westeurope"]
}
```

## Example 2: Minecraft Server

### Scenario
Host a Minecraft server accessible from the internet.

### Requirements
- Port 25565 TCP (Minecraft Java Edition)
- Port 19132 UDP (Minecraft Bedrock Edition - optional)

### Setup

```bash
# 1. Create public IP for Minecraft
acido ip create-forwarding minecraft-ip --ports 25565:tcp

# 2. Build Minecraft image
acido create minecraft --image itzg/minecraft-server:latest

# 3. Deploy Minecraft server
acido run minecraft-survival \
  -im minecraft \
  -t "java -Xmx2G -Xms2G -jar server.jar nogui" \
  --public-ip minecraft-ip \
  --expose-port 25565:tcp \
  -d 86400

# 4. Get server IP
acido ip ls
# Output: minecraft-ip (203.0.113.50) [Ports: 25565/TCP]

# 5. Connect using 203.0.113.50:25565 in Minecraft
```

### Environment Variables

```bash
# Deploy with custom world and settings
acido run minecraft-creative \
  -im minecraft \
  --public-ip minecraft-ip \
  --expose-port 25565:tcp \
  -d 86400
  
# In container environment (via Dockerfile or Lambda):
ENV EULA=TRUE
ENV MODE=creative
ENV DIFFICULTY=peaceful
ENV MAX_PLAYERS=20
ENV VIEW_DISTANCE=16
```

## Example 3: SSH Jump Host

### Scenario
Deploy a temporary SSH bastion/jump host for secure access to private resources.

### Requirements
- Port 22 TCP (SSH)

### Setup

```bash
# 1. Create SSH jump host IP
acido ip create-forwarding ssh-bastion --ports 22:tcp

# 2. Create custom SSH container with your public key
cat > Dockerfile.ssh-bastion <<EOF
FROM alpine:latest
RUN apk add --no-cache openssh-server
RUN ssh-keygen -A
RUN mkdir -p /root/.ssh
COPY authorized_keys /root/.ssh/
RUN chmod 600 /root/.ssh/authorized_keys
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
EOF

# 3. Build and push
docker build -t myregistry.azurecr.io/ssh-bastion:latest -f Dockerfile.ssh-bastion .
docker push myregistry.azurecr.io/ssh-bastion:latest

# 4. Deploy
acido run ssh-bastion-01 \
  -im ssh-bastion \
  --public-ip ssh-bastion \
  --expose-port 22:tcp \
  -d 3600  # 1 hour ephemeral access

# 5. Connect
acido ip ls  # Get IP
ssh root@203.0.113.60

# 6. Auto-cleanup after 1 hour
```

## Example 4: Web Server with Custom Port

### Scenario
Deploy a web application on a non-standard port for testing.

### Requirements
- Port 8080 TCP (HTTP)

### Setup

```bash
# 1. Create web server IP
acido ip create-forwarding webapp-ip --ports 8080:tcp

# 2. Deploy web server
acido run webapp-test \
  -im nginx:alpine \
  -t "nginx -g 'daemon off;'" \
  --public-ip webapp-ip \
  --expose-port 8080:tcp \
  -d 7200  # 2 hours

# 3. Test
curl http://$(acido ip ls | grep webapp-ip | awk '{print $2}'):8080

# 4. Auto-cleanup after 2 hours
```

## Example 5: Gaming Server (CS:GO)

### Scenario
Deploy a Counter-Strike: Global Offensive dedicated server.

### Requirements
- Port 27015 TCP/UDP (Game port)
- Port 27020 UDP (SourceTV port)

### Setup

```bash
# 1. Create gaming server IP
acido ip create-forwarding csgo-ip \
  --ports 27015:tcp \
  --ports 27015:udp \
  --ports 27020:udp

# 2. Deploy CS:GO server
acido run csgo-server \
  -im cm2network/csgo:latest \
  --public-ip csgo-ip \
  --expose-port 27015:tcp \
  --expose-port 27015:udp \
  --expose-port 27020:udp \
  -d 28800  # 8 hours

# 3. Server will be accessible at:
# IP: <public-ip>:27015
```

## Example 6: Database Direct Access (Development Only)

### Scenario
Expose a PostgreSQL database for temporary external access (development/testing only).

**⚠️ WARNING**: This is for development only. Never expose production databases!

### Requirements
- Port 5432 TCP (PostgreSQL)

### Setup

```bash
# 1. Create database IP
acido ip create-forwarding dev-db-ip --ports 5432:tcp

# 2. Deploy PostgreSQL with password
acido run postgres-dev \
  -im postgres:14 \
  -t "postgres" \
  --public-ip dev-db-ip \
  --expose-port 5432:tcp \
  -d 3600  # 1 hour only

# 3. Connect
psql -h <public-ip> -U postgres -d mydb

# 4. Auto-cleanup after 1 hour for security
```

## Example 7: Multi-Port Application (Docker Registry)

### Scenario
Run a private Docker registry accessible from internet.

### Requirements
- Port 5000 TCP (Registry API)

### Setup

```bash
# 1. Create registry IP
acido ip create-forwarding registry-ip --ports 5000:tcp

# 2. Deploy Docker registry
acido run docker-registry \
  -im registry:2 \
  --public-ip registry-ip \
  --expose-port 5000:tcp \
  -d 86400

# 3. Use the registry
docker tag myimage:latest <public-ip>:5000/myimage:latest
docker push <public-ip>:5000/myimage:latest
```

## Cost Comparison

### Scenario: Single VoIP Server (24/7)

| Solution | Monthly Cost | Pros | Cons |
|----------|--------------|------|------|
| Public IP per Container | ~$36 | Simple, direct | One IP per container |
| NAT Gateway Only | N/A | N/A | Cannot receive inbound |
| Load Balancer | ~$29 + IP | HA, multiple backends | Complex for single container |
| Azure Firewall | ~$900 | Enterprise features | Extremely expensive |

### Scenario: 10 Game Servers (12 hours/day)

| Solution | Monthly Cost | Pros | Cons |
|----------|--------------|------|------|
| Public IP per Container | ~$180 | Independent IPs | 10 public IPs needed |
| Load Balancer | ~$29 | Shared IP | Cannot do port-per-server |

## Best Practices

### 1. Security

```bash
# Always set auto-cleanup for exposed services
acido run risky-service \
  --public-ip temp-ip \
  --expose-port 8080:tcp \
  -d 3600  # Max 1 hour

# Use --no-cleanup only for long-running production services
acido run prod-service \
  --public-ip prod-ip \
  --expose-port 443:tcp \
  --no-cleanup
```

### 2. Cost Management

```bash
# List all forwarding IPs with tags
acido ip ls --show-tags

# Remove unused IPs immediately
acido ip rm unused-ip-1 unused-ip-2

# Use shorter durations for testing
acido run test-server \
  --public-ip test-ip \
  --expose-port 8080:tcp \
  -d 600  # 10 minutes only
```

### 3. Monitoring

```bash
# Check container status
acido ls

# Monitor logs (if implemented)
acido logs voip-server

# Check public IP assignments
acido ip ls --verbose
```

### 4. High Availability

For production services, consider using Load Balancer:

```bash
# Phase 2 feature (future)
acido lb create prod-lb \
  --frontend-port 443:tcp \
  --backend-port 8443

acido run prod-backend-01 \
  --load-balancer prod-lb \
  --backend-port 8443

acido run prod-backend-02 \
  --load-balancer prod-lb \
  --backend-port 8443
```

## Troubleshooting

### Issue: Cannot connect to forwarded port

**Check 1**: Verify container is running
```bash
acido ls | grep myserver
```

**Check 2**: Verify public IP assignment
```bash
acido ip ls | grep myserver-ip
```

**Check 3**: Test from container side
```bash
acido exec myserver "netstat -tulpn | grep <port>"
```

**Check 4**: Check Azure NSG rules (if configured)
```bash
# Via Azure CLI
az network nsg rule list --resource-group <rg> --nsg-name <nsg>
```

### Issue: Wrong public IP returned

**Solution**: Ensure `--public-ip` matches created IP name
```bash
# Created IP name must match
acido ip create-forwarding my-ip --ports 8080:tcp
acido run server --public-ip my-ip  # Exact match!
```

### Issue: Port already in use

**Solution**: Each public IP can only expose each port once
```bash
# Wrong: Two containers with same IP and port
acido run server1 --public-ip shared --expose-port 80:tcp
acido run server2 --public-ip shared --expose-port 80:tcp  # ERROR!

# Correct: Use different IPs
acido ip create-forwarding ip1 --ports 80:tcp
acido ip create-forwarding ip2 --ports 80:tcp
acido run server1 --public-ip ip1 --expose-port 80:tcp
acido run server2 --public-ip ip2 --expose-port 80:tcp
```

## References

- [Azure Container Instances Networking](https://learn.microsoft.com/en-us/azure/container-instances/container-instances-virtual-network-concepts)
- [Azure NAT Gateway](https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview)
- [Azure Public IP Addresses](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-addresses)
- [Azure Load Balancer](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview)
