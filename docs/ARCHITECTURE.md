# Architecture Overview

System design and technical architecture of the Home Server Stack.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Local Network                        │
│                                                         │
│  ┌──────────┐         ┌──────────────────┐            │
│  │  Client  │────────>│  AdGuard Home    │            │
│  │  Device  │  DNS    │  (Port 53)       │            │
│  └──────────┘  Query  └──────────────────┘            │
│       │                        │                       │
│       │                   DNS Response                 │
│       │                   (SERVER_IP)                  │
│       │                        │                       │
│       v                        v                       │
│  ┌──────────────────────────────────────┐             │
│  │         Traefik Reverse Proxy        │             │
│  │         (Ports 80, 443)              │             │
│  │  ┌────────────────────────────────┐  │             │
│  │  │  Domain-based Router           │  │             │
│  │  │  - *.home.local → Services     │  │             │
│  │  │  - TLS Termination             │  │             │
│  │  │  - Automatic Service Discovery │  │             │
│  │  └────────────────────────────────┘  │             │
│  └──────────────────────────────────────┘             │
│                     │                                  │
│      ┌──────────────┼──────────────┬─────────────┐   │
│      │              │              │             │   │
│      v              v              v             v   │
│  ┌────────┐
│  │  n8n   │
│  │  5678  │
│  └────────┘
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │         Docker Network: homeserver             │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
         │                                        ▲
         │ Port 51820/UDP (WireGuard)            │
         │ Optional: 5678/TCP (n8n webhooks)     │
         ▼                                        │
    Internet ◄──────────────────────────────────►

**Request Flow:**

1. Client requests `https://n8n.home.local`
2. AdGuard Home resolves to `SERVER_IP`
3. Request reaches Traefik on port 443
4. Traefik routes based on `Host` header to n8n container
5. n8n processes request and returns response
6. Traefik returns response to client over HTTPS

**Benefits:**
- Clean URLs (no ports to remember)
- Centralized SSL/TLS
- Easy to add new services
- Automatic service discovery
```

## Core Components

### Traefik
**Purpose:** Reverse proxy and ingress controller

**Architecture:**
- HTTP/HTTPS reverse proxy
- Automatic service discovery via Docker labels
- Self-signed TLS certificate generation
- Domain-based routing

**Data Flow:**
```
Client Request (https://service.home.local)
    ↓
Traefik (port 443) - Check Host header
    ↓
Route to matching service (via Docker labels)
    ↓
Service processes request
    ↓
Traefik returns response with TLS
```

**Integration Points:**
- All services via Docker labels
- AdGuard Home for DNS resolution
- Self-signed certificates for HTTPS

**Storage:**
- Config: Docker labels in compose files
- Certificates: `./data/traefik/certs/`
- Logs: `./data/traefik/logs/`

### AdGuard Home
**Purpose:** Network-wide ad blocking and DNS server

**Architecture:**
- Acts as DNS resolver for all network devices
- Filters DNS queries against blocklists
- Provides DHCP server (optional)
- Web UI for management

**Data Flow:**
```
Device DNS Query → AdGuard (port 53)
                ↓
         Check Blocklists
                ↓
         Allowed? → Upstream DNS (1.1.1.1, 8.8.8.8)
         Blocked? → Return NXDOMAIN
```

**Storage:**
- Config: `./data/adguard/conf/`
- Logs: `./data/adguard/work/`
- Database: SQLite

### n8n
**Purpose:** Workflow automation platform

**Architecture:**
- Node.js application
- SQLite database (default)
- Webhook server
- HTTP/HTTPS API

**Data Flow:**
```
Trigger (Webhook/Schedule/Event)
    ↓
n8n Workflow Execution Engine
    ↓
Node Processing (HTTP, Transform, AI, etc.)
    ↓
Output Actions (Email, Slack, Database, etc.)
```

**Integration Points:**
- External APIs via HTTP nodes
- Webhooks: `https://SERVER_IP:5678/webhook/*`

**Storage:**
- Workflows: `./data/n8n/database.sqlite`
- Files: `./data/n8n/files/`
- Logs: Container stdout

### WireGuard
**Purpose:** Secure VPN access to home network

**Architecture:**
- Kernel-level VPN (very fast)
- UDP-based protocol
- Peer-to-peer encryption
- Automatic key management

**Data Flow:**
```
VPN Client (peer) → WireGuard (port 51820/UDP)
    ↓
Decrypt & Route to home network (192.168.1.0/24)
    ↓
Access Internal Services
    ↓
Encrypt & Route back to peer
```

**Storage:**
- Config: `./data/wireguard/wg0.conf`
- Peer configs: `./data/wireguard/peer*/`
- Keys: `./data/wireguard/server/`

## Docker Compose Architecture

**Modular Compose Files:**

The stack uses multiple compose files for better organization:

```yaml
docker-compose.yml              # Core services (AdGuard, n8n, WireGuard, Traefik)
docker-compose.monitoring.yml   # Monitoring stack (Grafana, Prometheus, etc.)
```

**Composition:**
```bash
# All files are automatically included via Makefile
COMPOSE := docker compose -f docker-compose.yml \
                          -f docker-compose.monitoring.yml
```

**Benefits:**
- **Modularity:** Each service group in its own file
- **Maintainability:** Easier to manage individual service configurations
- **Flexibility:** Can deploy subsets by excluding compose files
- **Clarity:** Clear separation of concerns

**Shared Resources:**
- All services use the `homeserver` bridge network (external reference in modular files)
- Environment variables defined in `.env` are accessible to all compose files

## Network Architecture

### Docker Network

**homeserver bridge network:**
- All services connected
- Internal DNS resolution (service names)
- Isolated from host network (except exposed ports)

**Service Communication:**
```yaml
grafana → prometheus:9090 (metrics)
prometheus → node-exporter:9100 (system metrics)
prometheus → cadvisor:8080 (container metrics)
```

### Port Bindings

**Bound to SERVER_IP (internal only):**
- 53/TCP+UDP: AdGuard DNS
- 80/TCP: Traefik HTTP (redirects to HTTPS)
- 443/TCP: Traefik HTTPS (all service access)
- 8080/TCP: Traefik Dashboard
- 8888/TCP: AdGuard UI (legacy direct access)
- 5678/TCP: n8n (legacy direct access)

**Bound to 0.0.0.0 (external via router):**
- 51820/UDP: WireGuard VPN

**VPN-First Security Model:**
```
Internet
    │
    ├── 51820/UDP (WireGuard) ─────► VPN Connected
    │                                    │
    │                                    ▼
    └── 5678/TCP (n8n webhooks) ───► Path: /webhook/* → Public
        (optional)                    Path: /* → VPN/LAN Only
```

## Data Persistence

### Storage Structure

```
home-server-stack/
├── data/                           # Persistent data (mounted volumes)
│   ├── adguard/
│   │   ├── conf/                  # Configuration files
│   │   └── work/                  # Logs and database
│   ├── n8n/
│   │   ├── database.sqlite        # Workflows and executions
│   │   └── files/                 # Uploaded files
│   ├── ollama/
│   │   ├── models/                # AI models (20-50 GB)
│   │   └── manifests/             # Model metadata
│   ├── wireguard/
│   │   ├── wg0.conf              # Server config
│   │   └── peer*/                # Client configs
│   ├── habitica/
│   │   ├── db/                    # MongoDB database
│   │   └── dbconf/                # MongoDB config
│   ├── bookwyrm/                  # Bookwyrm data (via wrapper)
│   ├── grafana/                   # Dashboards and datasources
│   ├── prometheus/                # Metrics database
│   └── alertmanager/              # Alert state
├── ssl/                           # SSL certificates
│   ├── server.key                 # Private key
│   └── server.crt                 # Certificate
├── monitoring/                     # Monitoring configs
│   ├── prometheus/
│   ├── grafana/
│   └── alertmanager/
├── docker-compose.yml             # Core services
├── docker-compose.monitoring.yml  # Monitoring stack
└── .env                           # Environment configuration
```

### Data Volumes

All services use bind mounts (not Docker volumes) for easier backup and access.

**Backup Strategy:**
```bash
# Full backup
tar -czf backup.tar.gz data/ .env ssl/

# Restore
tar -xzf backup.tar.gz
docker compose up -d
```

## Security Architecture

### VPN-First Model

**Primary Security Boundary:** WireGuard VPN

```
┌─────────────────────────────────────┐
│         Internet (Untrusted)        │
└─────────────────┬───────────────────┘
                  │
          Port 51820/UDP Only
                  │
        ┌─────────▼────────┐
        │   WireGuard VPN   │ ◄── Authentication & Encryption
        └─────────┬────────┘
                  │
    ┌─────────────▼─────────────┐
    │   Home Network (Trusted)   │
    │  ┌──────────────────────┐  │
    │  │ All Services (VPN)   │  │
    │  │ - AdGuard, Grafana   │  │
    │  │ - n8n UI, Prometheus │  │
    │  └──────────────────────┘  │
    └───────────────────────────┘
```

**Optional: Hybrid Exposure (n8n webhooks only):**
```
Internet → Port 5678 → Reverse Proxy
                          │
                          ├── /webhook/* → n8n (Public)
                          └── /* → Reject (VPN only)
```

### Authentication Layers

**Layer 1 - VPN (Primary):**
- WireGuard peer authentication
- Public/private key cryptography
- No VPN = No access

**Layer 2 - Service (Secondary):**
- n8n: Basic auth (username/password)
- AdGuard: Admin login
- Grafana: Admin login
- Prometheus/Alertmanager: No auth (VPN-protected)

**Future: Layer 3 - SSO (Optional):**
- Authentik for centralized auth (see security-tickets/08)
- MFA support
- LDAP/OAuth integration

## Monitoring Architecture

### Metrics Flow

```
┌─────────────────────────────────────────────────────┐
│                    Data Sources                      │
├─────────────────────────────────────────────────────┤
│ Node Exporter → System metrics (CPU, RAM, Disk)    │
│ cAdvisor → Container metrics (Docker)               │
└───────────────┬─────────────────────────────────────┘
                │
                ▼ Scrape (every 15s)
        ┌──────────────┐
        │  Prometheus   │ ◄── Time-series database
        └───────┬──────┘
                │
                ├─► Alertmanager (alerts)
                └─► Grafana (dashboards)
```

### Alert Flow

```
Prometheus Evaluates Rules (every 15s)
    ↓
Alert Triggered? → Alertmanager
    ↓
Grouping & Deduplication
    ↓
Route to Receivers:
    ├── Webhook (http://127.0.0.1:5001/)
    ├── Email (optional)
    └── Slack (optional)
```

## Deployment Architecture

### Single Server (Current)

```
Physical Server
    │
    ├── Ubuntu Server 24.04 LTS
    │   ├── Docker Engine
    │   │   ├── homeserver network
    │   │   │   ├── adguard container
    │   │   │   ├── n8n container
    │   │   │   ├── traefik container
    │   │   │   └── wireguard container
    │   │   └── monitoring network (optional)
    │   │       ├── grafana
    │   │       ├── prometheus
    │   │       └── exporters
    │   └── Host Storage
    │       └── /home/user/home-server-stack/data/
    └── Network Interface (192.168.1.100)
```

### Future: Multi-Server (k3s)

See [K3S_MIGRATION_PLAN.md](K3S_MIGRATION_PLAN.md) for detailed architecture.

```
Server 1 (Control Plane)            Server 2 (Worker)
    │                                   │
    ├── k3s control-plane               ├── k3s agent
    ├── adguard (DaemonSet)            ├── n8n
    ├── wireguard (DaemonSet)          └── monitoring agents
    └── monitoring stack
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Orchestration** | Docker Compose | Container management |
| **Containerization** | Docker | Application isolation |
| **OS** | Ubuntu Server 24.04 | Host operating system |
| **Networking** | Bridge Network | Container networking |
| **Storage** | Bind Mounts | Data persistence |
| **Reverse Proxy** | Traefik | Domain-based routing + TLS |
| **DNS** | AdGuard Home | Network DNS + ad blocking |
| **VPN** | WireGuard | Secure remote access |
| **Automation** | n8n | Workflow automation |
| **Monitoring** | Prometheus | Metrics collection |
| **Visualization** | Grafana | Dashboards |
| **Alerting** | Alertmanager | Alert management |

## Performance Considerations

### Resource Allocation

**Typical Resource Usage:**
```
Service          CPU (Idle)  CPU (Active)  RAM (Idle)  RAM (Active)
────────────────────────────────────────────────────────────────────
AdGuard Home     1%          5%            100 MB      200 MB
n8n              1%          10%           200 MB      500 MB
WireGuard        1%          5%            50 MB       100 MB
Traefik          1%          3%            50 MB       100 MB
Monitoring       5%          15%           800 MB      1.5 GB
────────────────────────────────────────────────────────────────────
Total            9%          38%           1.2 GB      2.4 GB
```

**Bottlenecks:**
- **Disk I/O:** Prometheus writes
- **Network:** VPN throughput (usually not an issue on LAN)

### Scaling Strategies

**Vertical Scaling (current):**
- Add more RAM for workflow processing
- Faster CPU for better performance
- SSD for better I/O

**Horizontal Scaling (future):**
- k3s cluster (see K3S_MIGRATION_PLAN.md)
- Distribute services across servers
- Load balancing with MetalLB
- High availability with replicas

## Failure Modes & Recovery

### Service Failures

**Container crash:**
- Docker restart policy: `unless-stopped`
- Service automatically restarts
- Check logs: `docker compose logs [service]`

**Out of memory:**
- Check n8n workflow memory usage
- Reduce concurrent workflows
- Add swap space

**Disk full:**
- Check: `df -h`
- Clean: `docker system prune`
- Increase storage or add retention policies

### System Recovery

**Full system failure:**
1. Restore from backup
2. Extract to `home-server-stack/`
3. Run: `docker compose up -d`
4. Verify services

**Partial failure:**
- Stop service: `docker compose stop [service]`
- Check logs, fix issue
- Restart: `docker compose up -d [service]`

### Data Recovery

All critical data in `./data/`:
- Regular backups (daily recommended)
- Test restore procedures
- Keep backups offsite (cloud, external drive)

## References

- [Setup Guide](SETUP.md) - Installation instructions
- [Operations Guide](OPERATIONS.md) - Day-to-day management
- [Requirements](REQUIREMENTS.md) - Hardware/software needs
- [K3S Migration Plan](K3S_MIGRATION_PLAN.md) - Future architecture
- [Security Roadmap](../security-tickets/README.md) - Security implementation
