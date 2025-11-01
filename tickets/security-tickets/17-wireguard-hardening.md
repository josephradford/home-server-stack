# WireGuard VPN Hardening and Security

## Priority: 1 (Critical)
## Estimated Time: 1-2 hours (reduced from 3-4 hours - 70% complete)
## Phase: Week 1 - Critical Security Foundation

> **📋 Current State:**
> - ✅ Split tunneling **already configured** (192.168.1.0/24, 10.13.13.0/24)
> - ✅ Peer management script **already exists** (`scripts/wireguard-peer-management.sh`)
> - ✅ Routing test script **already exists** (`scripts/test-wireguard-routing.sh`)
> - ✅ Security documentation **already exists** (`docs/WIREGUARD_SECURITY.md`)
> - ❌ **Missing:** Fail2ban jail for WireGuard
> - ❌ **Missing:** Prometheus monitoring and alerts for VPN

## Description
Harden the WireGuard VPN as the primary security boundary for the home server stack. Since WireGuard is the only publicly exposed service (besides n8n webhooks), it becomes the critical authentication and access control layer. This ticket completes the remaining monitoring and intrusion detection for VPN access.

**Note:** Most hardening is already implemented. This ticket focuses on adding fail2ban protection and Prometheus monitoring for the existing WireGuard setup.

## Acceptance Criteria
- [x] WireGuard configuration hardened with minimal ALLOWEDIPS ✅ **DONE**
- [x] Strong peer key management and rotation policy ✅ **DONE** (`scripts/wireguard-peer-management.sh`)
- [ ] Fail2ban configured for VPN port scanning/brute force ❌ **TODO**
- [ ] VPN connection monitoring and alerting ❌ **TODO**
- [x] Peer management documentation ✅ **DONE** (`docs/WIREGUARD_SECURITY.md`)
- [x] Emergency access procedure documented ✅ **DONE** (`docs/WIREGUARD_SECURITY.md`)
- [x] DNS routing through VPN tested ✅ **DONE** (`scripts/test-wireguard-routing.sh`)
- [x] IP forwarding and routing rules validated ✅ **DONE** (`scripts/test-wireguard-routing.sh`)
- [x] Regular peer key rotation schedule established ✅ **DONE** (documented in security guide)

## Technical Implementation Details

### Files to Create/Modify
1. ~~`docker-compose.yml`~~ - ✅ **DONE** - WireGuard security settings already hardened
2. ~~`.env.example`~~ - ✅ **DONE** - WireGuard configuration variables documented
3. ~~`scripts/wireguard-peer-management.sh`~~ - ✅ **DONE** - Peer management script exists
4. `monitoring/prometheus/alert_rules.yml` - ❌ **TODO** - Add VPN monitoring alerts
5. `config/fail2ban/filter.d/wireguard.conf` - ❌ **TODO** - Fail2ban filter configuration
6. `config/fail2ban/jail.local` - ❌ **TODO** - Add WireGuard jail
7. ~~`docs/WIREGUARD_SECURITY.md`~~ - ✅ **DONE** - VPN security documentation exists

### ✅ Already Implemented (Reference Only - DO NOT MODIFY)

#### WireGuard Configuration (docker-compose.network.yml:28-31)
```yaml
# ✅ SECURE: Split tunneling configured
- INTERNAL_SUBNET=${WIREGUARD_SUBNET:-10.13.13.0/24}
- ALLOWEDIPS=${WIREGUARD_ALLOWEDIPS:-192.168.1.0/24,10.13.13.0/24}
```

**Benefits:**
- ✅ Only routes home network traffic through VPN
- ✅ Prevents full tunneling bandwidth abuse
- ✅ Reduces privacy implications for client traffic

#### Peer Management (`scripts/wireguard-peer-management.sh`)
Already implemented with commands:
- `list` - List all peers and their status
- `qr <peer_name>` - Show QR code for peer configuration
- `add <peer_name>` - Add a new peer
- `remove <peer_name>` - Remove a peer
- `rotate` - Rotate all peer keys
- `check` - Run security checks

#### Security Documentation (`docs/WIREGUARD_SECURITY.md`)
Already documented:
- VPN-first security architecture
- Peer management procedures
- Emergency access procedures
- Security checklist
- Best practices

### ❌ Remaining Work

### Step 1: Add WireGuard Fail2ban Protection

**Note:** Fail2ban container already exists (`docker-compose.network.yml`), we just need to add WireGuard-specific configuration.

**Update `config/fail2ban/jail.local`** - Add WireGuard jail:
```ini
# ... existing jails (traefik-auth, traefik-webhook, traefik-scanner) ...

[wireguard]
enabled = true
port = 51820
protocol = udp
filter = wireguard
logpath = /var/log/syslog
maxretry = 5
findtime = 10m
bantime = 1h
action = iptables-allports[name=wireguard, protocol=udp]
```

**Create `config/fail2ban/filter.d/wireguard.conf`:**
```ini
[Definition]
# Fail2ban filter for WireGuard
# Detects port scanning and invalid handshake attempts

failregex = ^.*wireguard.*: Invalid handshake initiation from <HOST>.*$
            ^.*wireguard.*: Handshake for peer .* did not complete after .* seconds, retrying from <HOST>.*$

ignoreregex =
```

**Restart fail2ban** to apply changes:
```bash
docker compose -f docker-compose.yml -f docker-compose.network.yml restart fail2ban
```

### Step 2: Add VPN Monitoring to Prometheus

**Note:** WireGuard doesn't natively export Prometheus metrics. We'll monitor container health and create alerts based on service availability.

**Update monitoring/prometheus/prometheus.yml:**
```yaml
scrape_configs:
  # ... existing configs ...

  - job_name: 'wireguard'
    static_configs:
      - targets: ['${SERVER_IP}:51821']
    metrics_path: '/metrics'
```

**Update monitoring/prometheus/alert_rules.yml:**
```yaml
groups:
  # ... existing groups ...

  - name: vpn_alerts
    rules:
      - alert: WireGuardDown
        expr: up{job="wireguard"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "WireGuard VPN is down"
          description: "WireGuard service is not responding. All remote access is unavailable."

      - alert: WireGuardNoActivePeers
        expr: wireguard_peers_total == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "No active WireGuard peers"
          description: "No devices connected to VPN for 10+ minutes."

      - alert: WireGuardExcessivePeers
        expr: wireguard_peers_total > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Unusual number of WireGuard peers"
          description: "{{ $value }} peers connected. Expected maximum: 10. Possible unauthorized access."

      - alert: WireGuardHandshakeFailures
        expr: rate(wireguard_handshake_failures_total[5m]) > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High WireGuard handshake failure rate"
          description: "{{ $value }} handshake failures per second. Possible brute force attempt."

      - alert: Fail2banWireGuardBans
        expr: fail2ban_banned_ips{jail="wireguard"} > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "IPs banned by Fail2ban for WireGuard attacks"
          description: "{{ $value }} IPs have been banned for attacking WireGuard."
```

**Note:** These alerts assume WireGuard exports metrics. If metrics are not available, the alerts will not fire. Consider using a WireGuard exporter like `prometheus-wireguard-exporter` for detailed metrics.

### Testing Commands

```bash
# 1. Test fail2ban WireGuard jail configuration
docker compose -f docker-compose.yml -f docker-compose.network.yml restart fail2ban

# Check fail2ban status
docker exec fail2ban fail2ban-client status

# Check WireGuard jail specifically
docker exec fail2ban fail2ban-client status wireguard

# View fail2ban logs
docker logs fail2ban --tail 50 -f

# 2. Test Prometheus monitoring (if WireGuard metrics are available)
# Check if WireGuard is being scraped
curl -s http://${SERVER_IP}:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="wireguard")'

# Test VPN alerts are loaded
curl -s http://${SERVER_IP}:9090/api/v1/rules | jq '.data.groups[] | select(.name=="vpn_alerts")'

# Check WireGuard service status
curl http://${SERVER_IP}:9090/api/v1/query?query=up{job=\"wireguard\"}

# 3. Verify existing features still work (already implemented)
./scripts/wireguard-peer-management.sh check
./scripts/test-wireguard-routing.sh

# 4. Monitor VPN connections
watch 'docker exec wireguard wg show'

# 5. Test from client device after connecting to VPN
curl https://grafana.${DOMAIN}  # Should work
curl https://n8n.${DOMAIN}     # Should work
```

## Success Metrics
- WireGuard connects reliably from all devices
- Split tunneling routing only home network traffic
- Fail2ban blocking suspicious connection attempts
- All admin services accessible only via VPN
- DNS routing through AdGuard working
- Monitoring alerts functioning
- Emergency access procedure verified

## Dependencies
- UFW or iptables installed
- Fail2ban container deployed
- Prometheus monitoring configured
- Domain name for peer configs (optional)

## Risk Considerations
- **Single Point of Failure**: VPN down = no remote access
- **Key Compromise**: If private key leaked, full access granted
- **Misconfiguration**: Could lock yourself out
- **Port Scanning**: VPN port is publicly exposed

## Rollback Plan
```bash
# If WireGuard breaks access:
# 1. Access via local network
# 2. Stop WireGuard
docker-compose stop wireguard

# 3. Temporarily open firewall for direct access
sudo ufw allow 22/tcp

# 4. Fix and restart
docker-compose up -d wireguard

# 5. Close temporary access
sudo ufw delete allow 22/tcp
```

## Security Impact
- **Before**: No VPN, direct service exposure, basic auth only
- **After**: VPN-first access, network-level authentication, defense in depth
- **Risk Reduction**: 90% reduction in attack surface (only VPN + n8n webhooks exposed)

## References
- [WireGuard Official Docs](https://www.wireguard.com/)
- [WireGuard Best Practices](https://www.wireguard.com/quickstart/)
- [LinuxServer.io WireGuard](https://docs.linuxserver.io/images/docker-wireguard)

## Follow-up Tasks
- Implement hardware security key support
- Add geographic IP restrictions
- Configure port knocking for VPN port
- Implement automated peer expiration
- Add VPN connection analytics dashboard
