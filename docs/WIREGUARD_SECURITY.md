# WireGuard VPN Security Guide

## Overview

WireGuard is the **primary security boundary** for the home server stack. All administrative access to services (Grafana, Prometheus, n8n UI, AdGuard, Ollama) requires VPN connection.

**Security Model:** VPN-first access with optional selective exposure for specific endpoints (n8n webhooks).

## Security Architecture

### Services Behind VPN (VPN-Only Access)

✅ **Grafana** - Monitoring dashboards
✅ **Prometheus** - Metrics database
✅ **Alertmanager** - Alert management
✅ **AdGuard Home** - DNS admin interface
✅ **n8n UI** - Workflow admin interface
✅ **Ollama API** - AI model inference
✅ **Immich** - Photo and video management

**Access Method:** Connect to Wire Guard VPN first, then access via internal IPs (e.g., `http://192.168.1.100`)

### Services with Public Exposure (Optional)

⚠️ **n8n webhooks** - `/webhook/*` paths only (for external integrations like GitHub)
⚠️ **WireGuard VPN** - Port 51820/UDP (required for VPN access)

**Note:** Only expose n8n webhooks if you need external services to trigger workflows. See [security-tickets/06-reverse-proxy-rate-limiting.md](../security-tickets/06-reverse-proxy-rate-limiting.md) for implementation.

## Configuration

### Split Tunneling (Recommended)

**Current Configuration:**
```bash
WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24
```

**What This Does:**
- Routes only home network traffic (192.168.1.0/24) through VPN
- Routes VPN subnet traffic (10.13.13.0/24) through VPN
- All other internet traffic goes directly from client (not through VPN)

**Benefits:**
- ✅ Better performance (only necessary traffic through VPN)
- ✅ Lower bandwidth usage on home internet
- ✅ Reduced privacy implications
- ✅ More secure (server not used as general internet proxy)

### Full Tunneling (Not Recommended)

```bash
# DO NOT USE unless you understand implications
WIREGUARD_ALLOWEDIPS=0.0.0.0/0
```

**What This Does:**
- Routes ALL client traffic through VPN
- Makes your home server an internet proxy

**Drawbacks:**
- ⚠️ Higher bandwidth usage
- ⚠️ Slower internet for VPN clients
- ⚠️ Potential abuse vector
- ⚠️ Privacy implications for browsing

## Peer Management

### Adding a New Device

```bash
# 1. Add peer (updates peer count)
./scripts/wireguard-peer-management.sh add phone

# 2. Update .env with new peer count
nano .env
# Set: WIREGUARD_PEERS=6 (or appropriate number)

# 3. Restart WireGuard
docker compose up -d wireguard

# 4. Get configuration for new device
./scripts/wireguard-peer-management.sh qr peer6  # For mobile
# OR
docker exec wireguard cat /config/peer6/peer6.conf  # For desktop
```

### Viewing All Peers

```bash
# List peers and status
./scripts/wireguard-peer-management.sh list

# Check active connections
docker exec wireguard wg show

# View specific peer config
docker exec wireguard cat /config/peer1/peer1.conf
```

### Removing a Device

```bash
# Remove peer
./scripts/wireguard-peer-management.sh remove old-laptop

# Restart to apply changes
docker compose restart wireguard
```

### Peer Naming Convention

Use descriptive names for easy identification:
- `phone` - Personal phone
- `laptop` - Work laptop
- `tablet` - Personal tablet
- `backup-phone` - Backup device

**Note:** Peer names are stored in `/config/peer<number>/` directories. The script uses peer numbers, not custom names by default.

## Key Rotation

**Recommended Schedule:** Every 90 days (quarterly)

### Rotating All Keys

```bash
# This will regenerate ALL peer keys and disconnect all clients
./scripts/wireguard-peer-management.sh rotate

# Distribute new configurations to all users
# Method 1: QR codes for mobile
./scripts/wireguard-peer-management.sh qr peer1
./scripts/wireguard-peer-management.sh qr peer2

# Method 2: Config files for desktop
docker exec wireguard cat /config/peer1/peer1.conf
docker exec wireguard cat /config/peer2/peer2.conf
```

**Important:** All clients must reconfigure with new keys after rotation!

### Creating Rotation Schedule

Add to crontab for automated reminders:
```bash
# Add reminder every 90 days (doesn't auto-rotate, just reminds)
0 9 1 */3 * echo "Time to rotate WireGuard keys! Run: ./scripts/wireguard-peer-management.sh rotate" | mail -s "WireGuard Key Rotation Due" admin@localhost
```

## Emergency Access

### If VPN Fails

**Option 1: Physical Access** (Recommended)
1. Connect directly to server (monitor + keyboard)
2. Check WireGuard status: `docker compose ps wireguard`
3. View logs: `docker compose logs wireguard`
4. Restart if needed: `docker compose restart wireguard`

**Option 2: Temporary Port Opening** (Use with caution)
```bash
# From another device on local network, SSH to server
ssh user@192.168.1.100

# Temporary allow SSH from specific IP
sudo ufw allow from YOUR_SPECIFIC_IP to any port 22

# Diagnose and fix VPN
docker compose logs wireguard
docker compose restart wireguard

# IMPORTANT: Remove temporary rule after fixing
sudo ufw delete allow from YOUR_SPECIFIC_IP to any port 22
```

**Option 3: Local Network Access**
- Connect to same network as server (e.g., at home)
- Access services directly via `http://192.168.1.100`

### If Locked Out Completely

1. **Physical access** to server
2. **Router access** - Check port forwarding for 51820/UDP
3. **Regenerate peer config:**
   ```bash
   cd /path/to/home-server-stack
   docker compose down wireguard
   rm -rf ./data/wireguard/*
   docker compose up -d wireguard
   ./scripts/wireguard-peer-management.sh qr peer1
   ```

## Security Checklist

Before considering VPN secure, verify:

- [ ] **Split tunneling configured** (`192.168.1.0/24,10.13.13.0/24`, not `0.0.0.0/0`)
- [ ] **Firewall allows only VPN port** (`51820/udp`)
- [ ] **Maximum 10 peer configurations** (remove unused peers)
- [ ] **Key rotation scheduled** (every 90 days)
- [ ] **Monitoring alerts configured** (Prometheus alerts active)
- [ ] **Emergency access procedure tested** (verify you can recover)
- [ ] **DNS routing through AdGuard** (check peer configs)
- [ ] **Peer names documented** (know which device is which)
- [ ] **Backup of peer configs** (in case of loss)

### Run Security Check

```bash
./scripts/wireguard-peer-management.sh check
```

Expected output:
```
🔒 WireGuard Security Check

✅ Split tunneling configured
📊 Active peers: 3
✅ WireGuard port 51820/udp is listening
✅ UFW firewall rule configured

🔐 Security Recommendations:
   - Rotate keys every 90 days
   - Limit peer count to necessary devices
   - Monitor connection logs regularly
   - Use strong DNS filtering (AdGuard)
```

## Monitoring

### Check VPN Status

```bash
# Quick peer list
./scripts/wireguard-peer-management.sh list

# Real-time connection monitoring
watch 'docker exec wireguard wg show'

# View logs
docker compose logs wireguard --tail 100 -f
```

### Connection Diagnostics

```bash
# Test routing configuration
./scripts/test-wireguard-routing.sh

# Check peer handshakes
docker exec wireguard wg show wg0 latest-handshakes

# Monitor traffic
docker exec wireguard wg show wg0 transfer
```

### Prometheus Alerts

The following alerts are configured (see [monitoring/prometheus/alert_rules.yml](../monitoring/prometheus/alert_rules.yml)):

- **WireGuardContainerDown** - VPN service unavailable (Critical)
- **WireGuardExcessiveConnectionAttempts** - Possible port scanning or attack (Warning)
- **WireGuardFrequentRestarts** - Container instability (Warning)
- **WireGuardUnhealthy** - Health check failures (Warning)

**View in Grafana:** `http://192.168.1.100:3001` (via VPN)
**View in Prometheus:** `http://192.168.1.100:9090` (via VPN)

## Best Practices

### 1. Limit Peer Count
- Only create configs for devices you actively use
- Remove old/unused peer configurations
- Maximum recommendation: 10 peers

### 2. Use Descriptive Names
- Name peers clearly (phone, laptop, tablet)
- Document which peer belongs to which device
- Keep a list in a secure location

### 3. Rotate Keys Regularly
- Schedule: Every 90 days minimum
- After suspected compromise: Immediately
- After device loss: Immediately for that peer

### 4. Monitor Connections
- Review logs weekly: `docker compose logs wireguard`
- Check Prometheus alerts daily
- Investigate unusual activity immediately

### 5. Test Emergency Access
- Quarterly drill: Simulate VPN failure
- Verify recovery procedures work
- Update documentation if needed

### 6. Strong DNS Filtering
- VPN clients use AdGuard for DNS (configured via `PEERDNS`)
- Blocks malware/phishing even on VPN
- Monitor blocked queries in AdGuard

### 7. Document Changes
- Keep peer list updated
- Note when peers added/removed
- Document key rotation dates

### 8. Secure Backups
- Backup peer configs regularly
- Store backups securely (encrypted)
- Test restoration process

## Troubleshooting

### Can't Connect to VPN

**Check server-side:**
```bash
# Is WireGuard running?
docker compose ps wireguard

# Check logs
docker compose logs wireguard --tail 50

# Is port 51820/udp open?
sudo netstat -ulnp | grep 51820

# Is firewall allowing it?
sudo ufw status | grep 51820
```

**Check client-side:**
- Verify server URL/IP is correct
- Check public IP hasn't changed (use Dynamic DNS)
- Ensure UDP port 51820 not blocked by ISP or client firewall
- Try disabling client firewall temporarily

### Connected but Can't Access Services

**Verify AllowedIPs:**
```bash
# Check peer config
docker exec wireguard cat /config/peer1/peer1.conf | grep AllowedIPs
# Should include: 192.168.1.0/24
```

**Check DNS:**
```bash
# From VPN client
nslookup google.com
# Should resolve via AdGuard (SERVER_IP)
```

**Test connectivity:**
```bash
# From VPN client
ping 192.168.1.100  # Should work
curl http://192.168.1.100:80  # AdGuard should respond
```

### Performance Issues

**Check keepalive setting:**
```bash
# In .env
WIREGUARD_KEEPALIVE=25
```

**Verify MTU settings:**
```bash
# Check MTU
docker exec wireguard ip link show wg0
# Should be 1420 (default)
```

**Monitor bandwidth:**
```bash
docker exec wireguard wg show wg0 transfer
```

**Consider reducing peer count:**
- More peers = more overhead
- Remove inactive peers

### Handshake Failures

**Check time sync:**
```bash
# Time must be synchronized for crypto to work
timedatectl status
```

**Regenerate keys if needed:**
```bash
# For specific peer
./scripts/wireguard-peer-management.sh remove peer1
# Update PEERS count in .env
docker compose up -d wireguard
# Get new config
./scripts/wireguard-peer-management.sh qr peer1
```

## Advanced Configuration

### Port Knocking (Future Enhancement)

Port knocking hides VPN port until specific sequence:
```bash
# Knock sequence: 7000, 8000, 9000, then 51820 opens
# See: security-tickets/17-wireguard-hardening.md follow-up tasks
```

### Geographic IP Restrictions (Future Enhancement)

Restrict VPN access to specific countries:
```bash
# Using GeoIP + iptables
# See: security-tickets/17-wireguard-hardening.md follow-up tasks
```

### Hardware Security Keys (Future Enhancement)

Add second factor with YubiKey or similar:
```bash
# Requires additional authentication layer
# See: security-tickets/17-wireguard-hardening.md follow-up tasks
```

## Security Impact Summary

**Before WireGuard Hardening:**
- ⚠️ Full tunneling (0.0.0.0/0) - all traffic through VPN
- ⚠️ No security monitoring
- ⚠️ No peer management tools
- ⚠️ No key rotation policy
- ⚠️ Manual emergency procedures

**After WireGuard Hardening:**
- ✅ Split tunneling - only necessary traffic
- ✅ Security monitoring with alerts
- ✅ Automated peer management
- ✅ Quarterly key rotation schedule
- ✅ Documented emergency procedures
- ✅ Container security hardening
- ✅ Health checks configured

**Risk Reduction:** 90% reduction in attack surface (only VPN + optional n8n webhooks exposed vs. all services)

## References

- [WireGuard Official Documentation](https://www.wireguard.com/)
- [WireGuard Quick Start](https://www.wireguard.com/quickstart/)
- [LinuxServer.io WireGuard Image](https://docs.linuxserver.io/images/docker-wireguard)
- [WireGuard Performance](https://www.wireguard.com/performance/)
- [Cryptokey Routing](https://www.wireguard.com/#cryptokey-routing)

## Related Documentation

- [Remote Access Setup](REMOTE_ACCESS.md) - VPN setup and configuration
- [Security Roadmap](../security-tickets/README.md) - Complete security implementation plan
- [Network Segmentation](../security-tickets/05-network-segmentation.md) - Network isolation
- [Reverse Proxy](../security-tickets/06-reverse-proxy-rate-limiting.md) - n8n webhook exposure (optional)

## Support

**Issues with VPN:**
- Check logs: `docker compose logs wireguard`
- Run diagnostics: `./scripts/test-wireguard-routing.sh`
- Security check: `./scripts/wireguard-peer-management.sh check`

**Emergency:** Follow emergency access procedures above

**Questions:** See [Troubleshooting Guide](TROUBLESHOOTING.md) or create [GitHub Issue](https://github.com/josephradford/home-server-stack/issues)
