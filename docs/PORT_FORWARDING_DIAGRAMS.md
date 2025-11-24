# Port Forwarding Architecture Diagrams

## Current Architecture (Egress Only)

```
┌───────────────────────────────────────────────────────────────────┐
│ Azure Resource Group                                              │
│                                                                   │
│                                                                   │
│  ┌─────────────────────┐                                         │
│  │  Public IP Address  │                                         │
│  │   203.0.113.45      │                                         │
│  │   (Standard SKU)    │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             │ Attached to                                        │
│             ▼                                                     │
│  ┌─────────────────────┐                                         │
│  │   NAT Gateway       │                                         │
│  │  (Egress Only)      │                                         │
│  │   - No inbound      │                                         │
│  │   - DNAT not        │                                         │
│  │     supported       │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             │ Routes to                                          │
│             ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Virtual Network (pentest-01-vnet)                     │     │
│  │                                                         │     │
│  │  ┌───────────────────────────────────────────────────┐ │     │
│  │  │ Subnet (pentest-01-subnet) 10.0.1.0/24           │ │     │
│  │  │ Delegated to: Microsoft.ContainerInstance        │ │     │
│  │  │                                                   │ │     │
│  │  │  ┌──────────────────────────────────────────┐   │ │     │
│  │  │  │ Container Group: scanner-fleet-01        │   │ │     │
│  │  │  │ Private IP: 10.0.1.4                     │   │ │     │
│  │  │  │ Public IP: NONE                          │   │ │     │
│  │  │  │                                          │   │ │     │
│  │  │  │  ┌────────────────────┐                 │   │ │     │
│  │  │  │  │ Container: nmap    │                 │   │ │     │
│  │  │  │  │ CPU: 1, RAM: 1GB   │                 │   │ │     │
│  │  │  │  └────────────────────┘                 │   │ │     │
│  │  │  └──────────────────────────────────────────┘   │ │     │
│  │  │                                                   │ │     │
│  │  │  ┌──────────────────────────────────────────┐   │ │     │
│  │  │  │ Container Group: scanner-fleet-02        │   │ │     │
│  │  │  │ Private IP: 10.0.1.5                     │   │ │     │
│  │  │  └──────────────────────────────────────────┘   │ │     │
│  │  └───────────────────────────────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘

Traffic Flow:
  → Outbound: Container → NAT Gateway → Public IP → Internet ✅
  ← Inbound:  Internet → Public IP → NAT Gateway → ??? ❌ NOT POSSIBLE
```

## Proposed Architecture (With Port Forwarding)

### Option 1: Regular Containers (No Change)

```
┌───────────────────────────────────────────────────────────────────┐
│ Azure Resource Group                                              │
│                                                                   │
│  ┌─────────────────────┐                                         │
│  │  NAT Gateway IP     │                                         │
│  │   203.0.113.45      │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             ▼                                                     │
│  ┌─────────────────────┐                                         │
│  │   NAT Gateway       │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Virtual Network                                        │     │
│  │  ┌───────────────────────────────────────────────────┐ │     │
│  │  │ Subnet (delegated)                                │ │     │
│  │  │                                                   │ │     │
│  │  │  ┌──────────────────────────────────────────┐   │ │     │
│  │  │  │ Container Group: regular-scanner         │   │ │     │
│  │  │  │ Private IP: 10.0.1.4                     │   │ │     │
│  │  │  │ Public IP: NONE                          │   │ │     │
│  │  │  │ Ports: NONE exposed                      │   │ │     │
│  │  │  └──────────────────────────────────────────┘   │ │     │
│  │  └───────────────────────────────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘

Traffic Flow:
  → Outbound: Container → NAT Gateway → NAT IP → Internet ✅
  ← Inbound:  Not available (as intended) ✅
```

### Option 2: Port-Forwarded Container (NEW)

```
┌───────────────────────────────────────────────────────────────────┐
│ Azure Resource Group                                              │
│                                                                   │
│  ┌─────────────────────┐                                         │
│  │  VoIP Public IP     │  ← NEW: Dedicated IP for forwarding     │
│  │   203.0.113.100     │                                         │
│  │   (Standard SKU)    │                                         │
│  │  Tags:              │                                         │
│  │   purpose=port-fwd  │                                         │
│  │   ports=5060/UDP    │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             │ Directly attached to container                     │
│             ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Virtual Network                                        │     │
│  │  ┌───────────────────────────────────────────────────┐ │     │
│  │  │ Subnet (delegated)                                │ │     │
│  │  │                                                   │ │     │
│  │  │  ┌──────────────────────────────────────────┐   │ │     │
│  │  │  │ Container Group: voip-server             │   │ │     │
│  │  │  │ Private IP: 10.0.1.6 (for VNet access)   │   │ │     │
│  │  │  │ Public IP: 203.0.113.100 ← ASSIGNED      │   │ │     │
│  │  │  │ Exposed Ports:                           │   │ │     │
│  │  │  │   - 5060/UDP (SIP)                       │   │ │     │
│  │  │  │   - 5060/TCP (SIP)                       │   │ │     │
│  │  │  │                                          │   │ │     │
│  │  │  │  ┌────────────────────┐                 │   │ │     │
│  │  │  │  │ Container: asterisk│                 │   │ │     │
│  │  │  │  │ Listening on 5060  │                 │   │ │     │
│  │  │  │  └────────────────────┘                 │   │ │     │
│  │  │  └──────────────────────────────────────────┘   │ │     │
│  │  └───────────────────────────────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘

Traffic Flow:
  → Outbound: Container → Public IP → Internet ✅
  ← Inbound:  Internet → Public IP:5060 → Container:5060 ✅
  
  Both directions work! ✅✅
```

## Side-by-Side Comparison

```
┌──────────────────────────────────────┬──────────────────────────────────────┐
│  Current (Egress Only)               │  Proposed (Port Forwarding)          │
├──────────────────────────────────────┼──────────────────────────────────────┤
│                                      │                                      │
│  Internet                            │  Internet                            │
│     ↕                                │     ↕                                │
│  Public IP (203.0.113.45)            │  Public IP (203.0.113.100)           │
│     ↕                                │     ↕ (Direct attach)                │
│  NAT Gateway                         │  Container Group                     │
│     ↕                                │     ↕                                │
│  Subnet                              │  Also on Subnet (10.0.1.6)           │
│     ↕                                │                                      │
│  Container (10.0.1.4)                │  Dual connectivity:                  │
│     No public IP                     │    - Public IP for inbound           │
│     Egress only                      │    - Subnet for VNet access          │
│                                      │                                      │
│  ✅ Can make outbound connections    │  ✅ Can make outbound connections    │
│  ❌ Cannot accept inbound            │  ✅ Can accept inbound on ports      │
│                                      │                                      │
│  Use for:                            │  Use for:                            │
│  - Scanners                          │  - VoIP servers                      │
│  - Web scrapers                      │  - Game servers                      │
│  - API consumers                     │  - SSH bastions                      │
│  - Batch jobs                        │  - Web services                      │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

## Multi-Region Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Azure Multi-Region                                │
│                                                                             │
│  ┌───────────────────────────┐    ┌───────────────────────────┐           │
│  │  Region: westeurope       │    │  Region: eastus           │           │
│  │                           │    │                           │           │
│  │  ┌─────────────────────┐  │    │  ┌─────────────────────┐  │           │
│  │  │ Public IP           │  │    │  │ Public IP           │  │           │
│  │  │ 203.0.113.100       │  │    │  │ 198.51.100.50       │  │           │
│  │  └──────────┬──────────┘  │    │  └──────────┬──────────┘  │           │
│  │             │              │    │             │              │           │
│  │             ▼              │    │             ▼              │           │
│  │  ┌─────────────────────┐  │    │  ┌─────────────────────┐  │           │
│  │  │ VoIP Server EU      │  │    │  │ VoIP Server US      │  │           │
│  │  │ Port 5060           │  │    │  │ Port 5060           │  │           │
│  │  └─────────────────────┘  │    │  └─────────────────────┘  │           │
│  └───────────────────────────┘    └───────────────────────────┘           │
│                                                                             │
│  Each region has independent:                                              │
│  - Public IP                                                               │
│  - Virtual Network                                                         │
│  - NAT Gateway (for regular containers)                                   │
│  - Container Groups                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Client connects to geographically closest server for lower latency.
```

## Component Interactions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Port Forwarding Component Flow                          │
└─────────────────────────────────────────────────────────────────────────────┘

  User CLI Command:
  ┌────────────────────────────────────────────────────────────┐
  │ acido ip create-forwarding voip-ip --ports 5060:udp        │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ CLI Parser (cli.py)                                        │
  │ - Validates port specification                             │
  │ - Calls acido.create_forwarding_ip()                       │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ Acido Class (cli.py)                                       │
  │ - Parses port specs (PORT:PROTOCOL)                        │
  │ - Calls network_manager.create_forwarding_ip()             │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ NetworkManager (azure_utils/NetworkManager.py)             │
  │ - Creates Azure Public IP resource                         │
  │ - Sets tags: purpose=port-forwarding, ports=5060/UDP       │
  │ - Returns (pip_id, ip_address)                             │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ Azure API                                                  │
  │ - Provisions public IP: 203.0.113.100                      │
  │ - Static allocation, Standard SKU                          │
  └────────────────────────────────────────────────────────────┘


  User Deployment:
  ┌────────────────────────────────────────────────────────────┐
  │ acido run voip --public-ip voip-ip --expose-port 5060:udp  │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ Acido.run() (cli.py)                                       │
  │ - Validates public-ip exists                               │
  │ - Parses exposed ports                                     │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ InstanceManager.deploy() (azure_utils/InstanceManager.py)  │
  │ - Creates IpAddress config (type=Public)                   │
  │ - Adds Port objects for each exposed port                  │
  │ - Builds ContainerGroup with ip_address                    │
  └────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────────────────────┐
  │ Azure API                                                  │
  │ - Provisions container with public IP 203.0.113.100        │
  │ - Exposes port 5060/UDP on that IP                         │
  │ - Container is now accessible from internet!               │
  └────────────────────────────────────────────────────────────┘
```

## Cost Breakdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Monthly Cost per Component                               │
└─────────────────────────────────────────────────────────────────────────────┘

  Regular Container (Egress Only):
  ┌─────────────────────────────────────────┐
  │ Component              Cost/Month       │
  ├─────────────────────────────────────────┤
  │ Container Instance     $9.40            │
  │ (1 vCPU, 1GB RAM)                       │
  │                                         │
  │ Shared NAT Gateway     ~$1.00*          │
  │ (amortized)                             │
  │                                         │
  │ Public IP (shared)     ~$0.50*          │
  │ (amortized)                             │
  │                                         │
  │ TOTAL:                 ~$11/month       │
  └─────────────────────────────────────────┘

  Port-Forwarded Container:
  ┌─────────────────────────────────────────┐
  │ Component              Cost/Month       │
  ├─────────────────────────────────────────┤
  │ Container Instance     $9.40            │
  │ (1 vCPU, 1GB RAM)                       │
  │                                         │
  │ Dedicated Public IP    $3.60            │
  │ (Standard SKU)                          │
  │                                         │
  │ Data Transfer Out      ~$0.087/GB       │
  │ (varies by usage)                       │
  │                                         │
  │ TOTAL:                 ~$13/month       │
  │                        + data transfer  │
  └─────────────────────────────────────────┘

  * Shared costs divided across multiple containers
```

## Security Zones

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Security Architecture                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ INTERNET (Untrusted)                                           │
  │   - External clients                                           │
  │   - SIP providers                                              │
  │   - Game players                                               │
  │   - Potential attackers                                        │
  └─────────────────────┬──────────────────────────────────────────┘
                        │
         ═══════════════╪═══════════════  Security Boundary
                        │
  ┌─────────────────────▼──────────────────────────────────────────┐
  │ PUBLIC IP LAYER                                                │
  │   ┌──────────────┐         ┌──────────────┐                   │
  │   │ Public IP 1  │         │ Public IP 2  │                   │
  │   │ Port 5060    │         │ Port 25565   │                   │
  │   └──────┬───────┘         └──────┬───────┘                   │
  └──────────┼────────────────────────┼───────────────────────────┘
             │                        │
  ┌──────────▼────────────────────────▼───────────────────────────┐
  │ CONTAINER LAYER (Semi-Trusted)                                │
  │   ┌────────────────────┐    ┌────────────────────┐           │
  │   │ VoIP Container     │    │ Game Container     │           │
  │   │ - Auth required    │    │ - Player auth      │           │
  │   │ - Rate limiting    │    │ - Anti-cheat       │           │
  │   │ - Logging enabled  │    │ - Monitoring       │           │
  │   └──────┬─────────────┘    └──────┬─────────────┘           │
  │          │                          │                         │
  │          └──────────┬───────────────┘                         │
  └─────────────────────┼─────────────────────────────────────────┘
                        │
  ┌─────────────────────▼─────────────────────────────────────────┐
  │ VIRTUAL NETWORK (Trusted)                                     │
  │   - Internal services                                         │
  │   - Database connections                                      │
  │   - Monitoring agents                                         │
  │   - Management tools                                          │
  └───────────────────────────────────────────────────────────────┘

  Security Controls:
  ✅ Application-level authentication
  ✅ Rate limiting at app layer
  ✅ Logging and monitoring
  ✅ Auto-cleanup (time-limited exposure)
  ✅ VNet segmentation
  ⚠️  No NSG rules (optional enhancement)
  ⚠️  No WAF (would need App Gateway)
```

## Legend

```
Symbols Used:
  ┌─┐   Box/Container
  │ │   Vertical line
  ─ ─   Horizontal line
  └─┘   Box bottom
  ▼     Arrow down
  ↕     Arrow bidirectional
  ✅    Supported/Working
  ❌    Not supported/Blocked
  ⚠️    Warning/Caution
  
Network Flow:
  →     Outbound traffic
  ←     Inbound traffic
  ↔     Bidirectional traffic
  
Hierarchy:
  ┬     Branch down
  ├     Branch right
  └     End branch
```
