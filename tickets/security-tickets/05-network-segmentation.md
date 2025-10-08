# Implement Network Segmentation

## Priority: 2 (High)
## Estimated Time: 3-4 hours
## Phase: Week 2 - High Priority Security

> **🔒 VPN-First Strategy Note:**
> This ticket implements network segmentation for a **hybrid VPN + selective exposure** architecture. Most services are only accessible via WireGuard VPN (ticket #17). Only n8n webhooks are publicly exposed for external integrations. Network segmentation provides defense-in-depth if the VPN is compromised.

## Description
Implement multiple Docker networks to segment services based on their security requirements and trust levels. This creates isolation layers that limit lateral movement in case of VPN or service compromise. In the VPN-first model, frontend network hosts services accessible via VPN, while only n8n webhook paths are exposed to the public internet.

## Acceptance Criteria
- [ ] Three-tier network architecture implemented (frontend, backend, monitoring)
- [ ] Services assigned to appropriate networks based on function
- [ ] Internal-only services isolated from external access
- [ ] Network policies documented
- [ ] Inter-network communication tested and verified
- [ ] Firewall rules documented for host-level protection

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Add multiple networks
2. `docker-compose.monitoring.yml` - Connect monitoring to appropriate networks
3. `docs/NETWORK_ARCHITECTURE.md` - Document network design (new file)
4. `scripts/firewall-rules.sh` - UFW/iptables configuration (new file)

### Current State (Single Network)
```yaml
networks:
  homeserver:
    driver: bridge
```

All services communicate on one flat network - no isolation.

### Proposed Three-Tier Architecture

```yaml
networks:
  # Frontend network - exposed services
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.1.0/24

  # Backend network - internal services only
  backend:
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.20.2.0/24

  # Monitoring network - observability services
  monitoring:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.20.3.0/24
```

### Updated Service Network Assignments

**docker-compose.yml:**
```yaml
services:
  adguard:
    # Public DNS service
    networks:
      - frontend
      - monitoring  # For metrics collection

  n8n:
    # Workflow automation (needs external + internal access)
    networks:
      - frontend    # For webhook access
      - backend     # For database/internal services
      - monitoring

  ollama:
    # AI service (internal only)
    networks:
      - backend     # Only accessible to n8n
      - monitoring

  n8n-init:
    networks:
      - backend

  ollama-setup:
    networks:
      - backend
```

**docker-compose.monitoring.yml:**
```yaml
services:
  prometheus:
    # Connects to all networks to scrape metrics
    networks:
      - frontend
      - backend
      - monitoring

  grafana:
    # User interface
    networks:
      - frontend
      - monitoring

  alertmanager:
    networks:
      - monitoring

  node-exporter:
    networks:
      - monitoring

  cadvisor:
    # Needs access to collect metrics from all containers
    networks:
      - frontend
      - backend
      - monitoring

  blackbox-exporter:
    networks:
      - frontend
      - monitoring
```

### Host Firewall Configuration (VPN-First Model)

Create `scripts/firewall-rules.sh`:
```bash
#!/bin/bash
# UFW firewall rules for home server (VPN-First Strategy)
# Only WireGuard VPN and n8n webhooks are publicly exposed

set -e

echo "Configuring UFW firewall rules (VPN-First)..."

# Reset UFW
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# SSH access (adjust port if needed - consider restricting to local network)
ufw allow from 192.168.0.0/16 to any port 22 proto tcp comment 'SSH - local network only'

# WireGuard VPN - PRIMARY PUBLIC ENTRY POINT
ufw allow 51820/udp comment 'WireGuard VPN'

# n8n webhooks ONLY - for external integrations (GitHub, etc.)
# Note: Use reverse proxy to restrict to /webhook/* paths only
ufw allow 5678/tcp comment 'n8n webhooks (public)'

# DNS (AdGuard Home) - LOCAL NETWORK ONLY
# Access via VPN after connection
ufw allow from 192.168.0.0/16 to any port 53 proto tcp comment 'DNS TCP - local'
ufw allow from 192.168.0.0/16 to any port 53 proto udp comment 'DNS UDP - local'
ufw allow from 10.13.13.0/24 to any port 53 proto tcp comment 'DNS TCP - VPN'
ufw allow from 10.13.13.0/24 to any port 53 proto udp comment 'DNS UDP - VPN'

# AdGuard Home admin - VPN/LOCAL ONLY
ufw allow from 192.168.0.0/16 to any port 80 proto tcp comment 'AdGuard HTTP - local'
ufw allow from 192.168.0.0/16 to any port 3000 proto tcp comment 'AdGuard setup - local'
ufw allow from 10.13.13.0/24 to any port 80 proto tcp comment 'AdGuard HTTP - VPN'
ufw allow from 10.13.13.0/24 to any port 3000 proto tcp comment 'AdGuard setup - VPN'

# Grafana - VPN/LOCAL ONLY
ufw allow from 192.168.0.0/16 to any port 3001 proto tcp comment 'Grafana - local'
ufw allow from 10.13.13.0/24 to any port 3001 proto tcp comment 'Grafana - VPN'

# Prometheus - VPN/LOCAL ONLY (sensitive metrics)
ufw allow from 192.168.0.0/16 to any port 9090 proto tcp comment 'Prometheus - local'
ufw allow from 10.13.13.0/24 to any port 9090 proto tcp comment 'Prometheus - VPN'

# n8n Admin UI - VPN/LOCAL ONLY (non-webhook paths handled by reverse proxy)
# The reverse proxy will enforce /webhook/* public, everything else VPN-only

# BLOCK Ollama from external access - internal Docker network only
ufw deny 11434/tcp comment 'Ollama - internal only'

# Docker network interfaces
ufw allow in on docker0
ufw allow in on br-+  # Docker bridge networks

# Enable UFW
ufw --force enable

# Show status
ufw status numbered

echo "✅ Firewall configured successfully"
echo ""
echo "Public exposure:"
echo "  - WireGuard VPN: 51820/udp"
echo "  - n8n webhooks: 5678/tcp (restrict to /webhook/* in reverse proxy)"
echo ""
echo "VPN/Local only:"
echo "  - AdGuard, Grafana, Prometheus, n8n UI"
```

### Network Policy Documentation

Create `docs/NETWORK_ARCHITECTURE.md`:
```markdown
# Network Architecture

## Network Segmentation

### Frontend Network (172.20.1.0/24)
**Purpose**: Services accessible from external networks
**Services**:
- AdGuard Home (DNS, web admin)
- n8n (webhook endpoints)
- Grafana (dashboards)
- Blackbox Exporter (probes)

**Security**: Exposed to internet, requires strong authentication

### Backend Network (172.20.2.0/24)
**Purpose**: Internal services not accessible from outside
**Services**:
- Ollama (AI inference)
- n8n-init (initialization)
- ollama-setup (initialization)

**Security**: Internal only, no external routing

### Monitoring Network (172.20.3.0/24)
**Purpose**: Observability and metrics collection
**Services**:
- Prometheus
- Alertmanager
- Node Exporter
- cAdvisor

**Security**: Internal only, contains sensitive metrics

## Communication Flows (VPN-First Hybrid Model)

```
┌─────────────────────────────────────────────────────────┐
│                       Internet                          │
└──────────┬────────────────────────────┬─────────────────┘
           │                            │
           │ WireGuard VPN         n8n Webhooks Only
           │ (51820/udp)           (5678/tcp /webhook/*)
           │                            │
    ┌──────▼──────┐              ┌─────▼──────┐
    │  VPN Tunnel │              │  Reverse   │
    │  (Primary)  │              │   Proxy    │
    └──────┬──────┘              └─────┬──────┘
           │                            │
           │ Authenticated Access       │ Public Webhooks
           │                            │
┌──────────▼────────────────────────────▼───────────────┐
│              Frontend Network (VPN + Public)          │
│  ┌──────────┐  ┌──────┐  ┌─────────┐  ┌──────────┐   │
│  │ AdGuard  │  │ n8n  │  │ Grafana │  │WireGuard │   │
│  │  (VPN)   │  │(Hyb) │  │  (VPN)  │  │          │   │
│  └──────────┘  └───┬──┘  └─────────┘  └──────────┘   │
└────────────────────┼──────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│         Backend Network (Internal Only)         │
│  ┌──────────┐  ┌────────────┐                  │
│  │ Ollama   │◄─┤ n8n (API)  │                  │
│  │(Internal)│  │            │                  │
│  └──────────┘  └────────────┘                  │
└─────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│      Monitoring Network (Internal Only)         │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Prometheus │  │ cAdvisor │  │ NodeExp  │    │
│  │   (VPN)    │  │  (VPN)   │  │  (VPN)   │    │
│  └────────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────┘
```

## Access Control Matrix (VPN-First)

| Service | Frontend | Backend | Monitoring | External | VPN Required |
|---------|----------|---------|------------|----------|--------------|
| WireGuard | ✅ | ✅ | ✅ | ✅ (Public) | N/A |
| n8n UI | ✅ | ✅ | ✅ | ❌ | ✅ Yes |
| n8n Webhooks | ✅ | ✅ | ✅ | ✅ (Public) | ❌ No |
| AdGuard Home | ✅ | ❌ | ✅ | ❌ | ✅ Yes |
| Grafana | ✅ | ❌ | ✅ | ❌ | ✅ Yes |
| Prometheus | ❌ | ❌ | ✅ | ❌ | ✅ Yes |
| Ollama | ❌ | ✅ | ✅ | ❌ | ✅ Yes |

## Port Exposure Policy (VPN-First)

### ✅ Exposed to Public Internet
- **51820/udp** - WireGuard VPN (PRIMARY ENTRY POINT)
- **5678/tcp** - n8n webhooks ONLY (`/webhook/*` paths)
  - Reverse proxy enforces path restrictions
  - Rate limiting required
  - All other n8n paths require VPN

### 🔐 VPN or Local Network Only
- **53/tcp+udp** - AdGuard DNS
- **80/tcp** - AdGuard admin
- **3000/tcp** - AdGuard setup
- **3001/tcp** - Grafana
- **9090/tcp** - Prometheus
- **5678/tcp** - n8n UI (non-webhook paths)

### 🔒 Internal Docker Networks Only (Not exposed to host)
- **11434/tcp** - Ollama (backend network only)
- **8080/tcp** - cAdvisor
- **9093/tcp** - Alertmanager
- **9100/tcp** - Node Exporter
- **9115/tcp** - Blackbox Exporter
- **51821/tcp** - WireGuard admin UI (bound to SERVER_IP only)
```

### Testing Commands
```bash
# Apply new network configuration
docker compose down
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Verify network creation
docker network ls
docker network inspect home-server-stack_frontend
docker network inspect home-server-stack_backend
docker network inspect home-server-stack_monitoring

# Test connectivity between services
# n8n should reach ollama (backend)
docker exec n8n ping -c 3 ollama

# Grafana should NOT reach ollama (different networks)
docker exec grafana ping -c 3 ollama  # Should fail

# Prometheus should reach all services (multi-network)
docker exec prometheus ping -c 3 adguard
docker exec prometheus ping -c 3 n8n
docker exec prometheus ping -c 3 ollama

# Test firewall rules
sudo ufw status numbered

# Test external access (from another machine)
# Should work:
curl https://SERVER_IP:5678
nslookup example.com SERVER_IP

# Should be blocked:
curl http://SERVER_IP:11434  # Ollama should timeout
curl http://SERVER_IP:9090   # Prometheus should timeout (if external)

# Scan open ports from external network
nmap -p- SERVER_IP
```

## Success Metrics
- Three distinct Docker networks created
- Services isolated by security tier
- Backend services inaccessible from internet
- Prometheus can scrape all metrics
- No unexpected network connectivity
- Firewall rules applied and tested

## Dependencies
- Docker network driver support
- UFW or iptables installed
- Network understanding and testing capability

## Risk Considerations
- **Service Disruption**: Network changes may break existing connectivity
- **Complexity**: Multi-network setup harder to troubleshoot
- **Monitoring**: Prometheus needs multi-network access
- **DNS**: Internal DNS resolution may need configuration

## Rollback Plan
```bash
# Revert to single network
git revert <commit-hash>

# Restart services
docker compose down
docker compose up -d

# Disable firewall if needed
sudo ufw disable
```

## Security Impact (VPN-First Model)
- **Before**: Flat network, any compromised container can reach all others, multiple public-facing services
- **After**: Layered defense with VPN boundary, limited lateral movement, only VPN + n8n webhooks exposed
- **Risk Reduction**:
  - 90% reduction in public attack surface (only 2 ports vs many)
  - 60% reduction in lateral movement if VPN compromised
  - Defense-in-depth: VPN breach still limited by network segmentation

## References
- [Docker Network Security](https://docs.docker.com/network/network-tutorial-standalone/)
- [UFW Documentation](https://help.ubuntu.com/community/UFW)
- [Defense in Depth](https://owasp.org/www-community/Defense_in_Depth)

## Follow-up Tasks
- Implement network policy enforcement (Calico/Cilium)
- Add VPN requirement for admin interfaces
- Configure network monitoring and anomaly detection
- Document emergency access procedures
