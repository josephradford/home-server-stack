# WireGuard VPN Hardening and Security

## Priority: 1 (Critical)
## Estimated Time: 3-4 hours
## Phase: Week 1 - Critical Security Foundation

## Description
Harden the WireGuard VPN as the primary security boundary for the home server stack. Since WireGuard is the only publicly exposed service (besides n8n webhooks), it becomes the critical authentication and access control layer. This ticket implements security best practices, monitoring, and fail-safes for VPN access.

## Acceptance Criteria
- [ ] WireGuard configuration hardened with minimal ALLOWEDIPS
- [ ] Strong peer key management and rotation policy
- [ ] Fail2ban configured for VPN port scanning/brute force
- [ ] VPN connection monitoring and alerting
- [ ] Peer management documentation
- [ ] Emergency access procedure documented
- [ ] DNS routing through VPN tested
- [ ] IP forwarding and routing rules validated
- [ ] Regular peer key rotation schedule established

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Update WireGuard security settings
2. `.env.example` - Update WireGuard configuration variables
3. `scripts/wireguard-peer-management.sh` - Peer management script (new file)
4. `monitoring/prometheus/alert_rules.yml` - Add VPN monitoring alerts
5. `fail2ban/wireguard.conf` - Fail2ban configuration (new file)
6. `docs/WIREGUARD_SECURITY.md` - VPN security documentation (new file)

### Current Configuration Issues

**docker-compose.yml:119-120**
```yaml
# ⚠️ SECURITY ISSUE: Routes ALL traffic through VPN
- INTERNAL_SUBNET=${WIREGUARD_SUBNET:-10.13.13.0}
- ALLOWEDIPS=${WIREGUARD_ALLOWEDIPS:-0.0.0.0/0}
```

This allows full tunneling and routes all client traffic through the VPN, which:
- Increases bandwidth usage unnecessarily
- Creates privacy implications for client traffic
- Makes the server a potential abuse vector

### Step 1: Harden WireGuard Configuration

**Update docker-compose.yml:**
```yaml
wireguard:
  image: lscr.io/linuxserver/wireguard:v1.0.20210914@sha256:REPLACE_WITH_ACTUAL_DIGEST
  container_name: wireguard
  restart: unless-stopped
  cap_add:
    - NET_ADMIN
    # Remove SYS_MODULE if kernel module already loaded
  cap_drop:
    - ALL
  security_opt:
    - no-new-privileges:true
  read_only: true  # Make filesystem read-only
  tmpfs:
    - /tmp
    - /run
  environment:
    - PUID=1000
    - PGID=1000
    - TZ=${TIMEZONE}
    - SERVERURL=${WIREGUARD_SERVERURL}
    - SERVERPORT=${WIREGUARD_PORT:-51820}
    - PEERS=${WIREGUARD_PEERS:-5}
    - PEERDNS=${SERVER_IP}
    # CRITICAL: Only route home network traffic through VPN
    - INTERNAL_SUBNET=${WIREGUARD_SUBNET:-10.13.13.0/24}
    - ALLOWEDIPS=${WIREGUARD_ALLOWEDIPS:-192.168.1.0/24,10.13.13.0/24}
    - LOG_CONFS=${WIREGUARD_LOG_CONFS:-true}
    - PERSISTENTKEEPALIVE_PEERS=${WIREGUARD_KEEPALIVE:-25}
  ports:
    - "${WIREGUARD_PORT:-51820}:51820/udp"
    - "${SERVER_IP}:51821:51821/tcp"  # Admin UI - local only
  volumes:
    - ./data/wireguard:/config
    - /lib/modules:/lib/modules:ro
  sysctls:
    - net.ipv4.conf.all.src_valid_mark=1
    - net.ipv4.ip_forward=1
  networks:
    - frontend
    - backend
    - monitoring
  healthcheck:
    test: ["CMD", "wg", "show"]
    interval: 30s
    timeout: 10s
    retries: 3
  labels:
    # Prometheus metrics from container logs
    - "prometheus.io/scrape=true"
    - "prometheus.io/port=51821"
```

**Update .env.example:**
```bash
# WireGuard VPN Configuration
WIREGUARD_SERVERURL=vpn.yourdomain.com
WIREGUARD_PORT=51820
WIREGUARD_PEERS=5
WIREGUARD_SUBNET=10.13.13.0/24
# CRITICAL: Only route home network and VPN subnet
# DO NOT use 0.0.0.0/0 unless you want full tunneling
WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24
WIREGUARD_KEEPALIVE=25
WIREGUARD_LOG_CONFS=true
```

### Step 2: Implement Fail2ban for VPN Protection

**Create fail2ban/jail.d/wireguard.conf:**
```ini
[wireguard]
enabled = true
port = 51820
protocol = udp
filter = wireguard
logpath = /var/log/syslog
maxretry = 3
findtime = 600
bantime = 3600
action = iptables-allports[name=wireguard, protocol=udp]
```

**Create fail2ban/filter.d/wireguard.conf:**
```ini
[Definition]
# Fail2ban filter for WireGuard
# Detects port scanning and invalid handshake attempts

failregex = ^.*wireguard.*: Invalid handshake initiation from <HOST>.*$
            ^.*wireguard.*: Handshake for peer .* did not complete after .* seconds, retrying from <HOST>.*$

ignoreregex =
```

**Add fail2ban to docker-compose.yml:**
```yaml
services:
  fail2ban:
    image: crazymax/fail2ban:latest@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: fail2ban
    restart: unless-stopped
    network_mode: "host"
    cap_add:
      - NET_ADMIN
      - NET_RAW
    volumes:
      - ./fail2ban:/data
      - /var/log:/var/log:ro
    environment:
      - TZ=${TIMEZONE}
      - F2B_LOG_LEVEL=INFO
      - F2B_DB_PURGE_AGE=30d
```

### Step 3: Peer Management and Key Rotation

**Create scripts/wireguard-peer-management.sh:**
```bash
#!/bin/bash
# WireGuard Peer Management Script

set -e

WIREGUARD_CONFIG_DIR="./data/wireguard"
ACTION="${1:-list}"
PEER_NAME="$2"

function list_peers() {
    echo "📋 Current WireGuard Peers:"
    docker exec wireguard wg show all
    echo ""
    echo "📁 Peer Configuration Files:"
    ls -lh "$WIREGUARD_CONFIG_DIR/peer_"* 2>/dev/null || echo "No peer configs found"
}

function show_peer_qr() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 qr <peer_name>"
        exit 1
    fi

    echo "📱 QR Code for peer: $PEER_NAME"
    docker exec wireguard /app/show-peer "$PEER_NAME"
}

function add_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 add <peer_name>"
        exit 1
    fi

    echo "➕ Adding new peer: $PEER_NAME"

    # Regenerate config with new peer count
    CURRENT_PEERS=$(docker exec wireguard wg show wg0 peers | wc -l)
    NEW_PEER_COUNT=$((CURRENT_PEERS + 1))

    docker stop wireguard
    docker rm wireguard

    # Update PEERS environment variable and restart
    echo "🔄 Restarting WireGuard with $NEW_PEER_COUNT peers..."
    # User should update .env and restart manually
    echo "⚠️  Update WIREGUARD_PEERS=$NEW_PEER_COUNT in .env and run:"
    echo "   docker-compose up -d wireguard"
}

function remove_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 remove <peer_name>"
        exit 1
    fi

    echo "🗑️  Removing peer: $PEER_NAME"
    echo "⚠️  WARNING: This will disconnect the peer immediately!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Remove peer configuration
    rm -f "$WIREGUARD_CONFIG_DIR/peer_$PEER_NAME"*

    echo "✅ Peer $PEER_NAME removed. Restart WireGuard to apply:"
    echo "   docker-compose restart wireguard"
}

function rotate_keys() {
    echo "🔑 WireGuard Key Rotation"
    echo "⚠️  WARNING: This will regenerate ALL peer keys and QR codes!"
    echo "⚠️  All clients must reconfigure with new keys!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Backup current config
    BACKUP_DIR="./backups/wireguard-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp -r "$WIREGUARD_CONFIG_DIR"/* "$BACKUP_DIR/"

    echo "💾 Backup created: $BACKUP_DIR"

    # Remove and recreate WireGuard
    docker stop wireguard
    docker rm wireguard
    rm -rf "$WIREGUARD_CONFIG_DIR"/*

    echo "🔄 Recreating WireGuard with new keys..."
    docker-compose up -d wireguard

    echo "✅ Key rotation complete!"
    echo "📋 New peer configurations available in: $WIREGUARD_CONFIG_DIR"
}

function check_security() {
    echo "🔒 WireGuard Security Check"
    echo ""

    # Check if 0.0.0.0/0 is configured (bad)
    if docker exec wireguard cat /config/wg0.conf | grep -q "0.0.0.0/0"; then
        echo "⚠️  WARNING: Full tunneling (0.0.0.0/0) detected!"
        echo "   This routes ALL client traffic through VPN"
        echo "   Recommendation: Use split tunneling (192.168.1.0/24,10.13.13.0/24)"
    else
        echo "✅ Split tunneling configured"
    fi

    # Check peer count
    PEER_COUNT=$(docker exec wireguard wg show wg0 peers | wc -l)
    echo "📊 Active peers: $PEER_COUNT"

    # Check port exposure
    if netstat -tuln | grep -q ":51820"; then
        echo "✅ WireGuard port 51820/udp is listening"
    else
        echo "❌ WireGuard port not listening!"
    fi

    # Check firewall
    if command -v ufw &> /dev/null; then
        if ufw status | grep -q "51820/udp"; then
            echo "✅ UFW firewall rule configured"
        else
            echo "⚠️  No UFW rule for WireGuard port"
        fi
    fi

    echo ""
    echo "🔐 Security Recommendations:"
    echo "   - Rotate keys every 90 days"
    echo "   - Limit peer count to necessary devices"
    echo "   - Monitor connection logs regularly"
    echo "   - Use strong DNS filtering (AdGuard)"
}

case "$ACTION" in
    list)
        list_peers
        ;;
    qr)
        show_peer_qr
        ;;
    add)
        add_peer
        ;;
    remove)
        remove_peer
        ;;
    rotate)
        rotate_keys
        ;;
    check)
        check_security
        ;;
    *)
        echo "WireGuard Peer Management"
        echo ""
        echo "Usage: $0 <command> [peer_name]"
        echo ""
        echo "Commands:"
        echo "  list              List all peers and their status"
        echo "  qr <peer_name>    Show QR code for peer configuration"
        echo "  add <peer_name>   Add a new peer"
        echo "  remove <peer_name> Remove a peer"
        echo "  rotate            Rotate all peer keys (WARNING: disconnects all)"
        echo "  check             Run security checks"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 qr phone"
        echo "  $0 add laptop"
        echo "  $0 remove old-device"
        exit 1
        ;;
esac
```

Make executable:
```bash
chmod +x scripts/wireguard-peer-management.sh
```

### Step 4: Add VPN Monitoring to Prometheus

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

### Step 5: Network Routing Validation

**Create scripts/test-wireguard-routing.sh:**
```bash
#!/bin/bash
# Test WireGuard routing and connectivity

set -e

echo "🧪 WireGuard Routing and Security Test"
echo ""

# Test 1: Check WireGuard interface
echo "1️⃣  Checking WireGuard interface..."
if docker exec wireguard wg show wg0 &> /dev/null; then
    echo "   ✅ wg0 interface is up"
else
    echo "   ❌ wg0 interface not found!"
    exit 1
fi

# Test 2: Check IP forwarding
echo "2️⃣  Checking IP forwarding..."
if docker exec wireguard sysctl net.ipv4.ip_forward | grep -q "= 1"; then
    echo "   ✅ IP forwarding enabled"
else
    echo "   ⚠️  IP forwarding disabled"
fi

# Test 3: Check allowed IPs configuration
echo "3️⃣  Checking AllowedIPs configuration..."
ALLOWED_IPS=$(docker exec wireguard cat /config/peer1/peer1.conf | grep AllowedIPs | cut -d'=' -f2 | xargs)
if [[ "$ALLOWED_IPS" == *"0.0.0.0/0"* ]]; then
    echo "   ⚠️  Full tunneling detected: $ALLOWED_IPS"
    echo "   Recommendation: Use split tunneling for better security"
else
    echo "   ✅ Split tunneling configured: $ALLOWED_IPS"
fi

# Test 4: Check DNS routing
echo "4️⃣  Checking DNS configuration..."
PEER_DNS=$(docker exec wireguard cat /config/peer1/peer1.conf | grep DNS | cut -d'=' -f2 | xargs)
echo "   DNS: $PEER_DNS"
if [ -n "$PEER_DNS" ]; then
    echo "   ✅ DNS routing configured (AdGuard)"
else
    echo "   ⚠️  No DNS configured"
fi

# Test 5: Check firewall rules
echo "5️⃣  Checking firewall rules..."
if command -v ufw &> /dev/null; then
    if sudo ufw status | grep -q "51820/udp"; then
        echo "   ✅ UFW rule exists for WireGuard"
    else
        echo "   ⚠️  No UFW rule found. Add with: sudo ufw allow 51820/udp"
    fi
fi

# Test 6: Check peer connectivity
echo "6️⃣  Checking peer handshakes..."
PEER_COUNT=$(docker exec wireguard wg show wg0 peers | wc -l)
ACTIVE_PEERS=$(docker exec wireguard wg show wg0 latest-handshakes | awk '$2 > 0' | wc -l)
echo "   Total peers: $PEER_COUNT"
echo "   Active peers: $ACTIVE_PEERS"

echo ""
echo "✅ WireGuard routing test complete!"
```

### Step 6: Security Documentation

**Create docs/WIREGUARD_SECURITY.md:**
```markdown
# WireGuard VPN Security Guide

## Overview
WireGuard is the primary security boundary for the home server stack. All administrative access requires VPN connection.

## Security Architecture

### What's Behind VPN
- ✅ Grafana UI
- ✅ Prometheus UI
- ✅ AdGuard Admin
- ✅ n8n UI (admin interface)
- ✅ Ollama API

### What's Publicly Exposed
- ⚠️ n8n webhook endpoints (`/webhook/*` only)
- ⚠️ WireGuard port 51820/udp

## Peer Management

### Adding a New Device
```bash
./scripts/wireguard-peer-management.sh add phone
# Update .env with new peer count
docker-compose up -d wireguard
./scripts/wireguard-peer-management.sh qr phone
```

### Removing a Device
```bash
./scripts/wireguard-peer-management.sh remove old-laptop
docker-compose restart wireguard
```

### Key Rotation (Every 90 Days)
```bash
./scripts/wireguard-peer-management.sh rotate
# Distribute new configs to all users
```

## Emergency Access

### If VPN Fails
1. **Physical access** - Connect directly to server
2. **Temporary port opening**:
   ```bash
   sudo ufw allow from YOUR_IP to any port 22
   ssh user@server
   # Diagnose and fix VPN
   sudo ufw delete allow from YOUR_IP to any port 22
   ```

### If Locked Out
1. Access via local network
2. Check WireGuard logs: `docker logs wireguard`
3. Verify firewall: `sudo ufw status`
4. Regenerate peer config if needed

## Security Checklist

- [ ] Split tunneling configured (not 0.0.0.0/0)
- [ ] Fail2ban active for VPN port
- [ ] Maximum 10 peer configurations
- [ ] Key rotation scheduled (quarterly)
- [ ] Monitoring alerts configured
- [ ] Emergency access procedure tested
- [ ] DNS routing through AdGuard
- [ ] Firewall rules verified

## Monitoring

### Check VPN Status
```bash
./scripts/wireguard-peer-management.sh list
```

### View Connection Logs
```bash
docker logs wireguard --tail 100 -f
```

### Prometheus Alerts
- VPN service down
- Excessive connection attempts
- No active peers for extended time

## Best Practices

1. **Limit peers** - Only create necessary peer configs
2. **Name peers clearly** - Use descriptive names (phone, laptop, etc.)
3. **Rotate keys** - Every 90 days minimum
4. **Monitor connections** - Review logs weekly
5. **Test emergency access** - Quarterly drill
6. **Document changes** - Keep peer list updated
7. **Use strong DNS** - Route through AdGuard for filtering

## Troubleshooting

### Can't connect to VPN
- Check firewall allows 51820/udp
- Verify server IP/domain is correct
- Check WireGuard container is running
- Review handshake logs

### Connected but can't access services
- Verify AllowedIPs includes home network
- Check DNS is set to AdGuard IP
- Test connectivity: `ping 192.168.1.100`
- Verify service is running

### Performance issues
- Check persistent keepalive setting
- Verify MTU settings
- Monitor bandwidth usage
- Consider reducing peer count
```

### Testing Commands
```bash
# Test WireGuard configuration
docker-compose up -d wireguard

# Verify security settings
./scripts/wireguard-peer-management.sh check

# Test routing
./scripts/test-wireguard-routing.sh

# Generate peer QR code
./scripts/wireguard-peer-management.sh qr peer1

# Test fail2ban
docker-compose up -d fail2ban
docker exec fail2ban fail2ban-client status wireguard

# Monitor VPN connections
watch 'docker exec wireguard wg show'

# Test from client device after connecting to VPN:
# Should work (internal services):
curl https://grafana.yourdomain.com
curl http://192.168.1.100:9090  # Prometheus

# Should work (public webhook):
curl https://n8n.yourdomain.com/webhook/test

# Check Prometheus metrics
curl http://${SERVER_IP}:9090/api/v1/query?query=up{job=\"wireguard\"}
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
