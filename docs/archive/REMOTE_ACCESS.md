# Remote Access Setup

Guide for securely accessing your home server from outside your network.

## ⚠️ Security Warning

**VPN-First Approach Strongly Recommended**

This project follows a **VPN-first security model**. Before exposing services to the internet, review [security-tickets/README.md](../security-tickets/README.md).

**Recommended:** Use WireGuard VPN for all remote access.
**Not Recommended:** Port forwarding services directly (high security risk).

## Option 1: WireGuard VPN (Recommended)

### Setup

1. **Ensure WireGuard is running:**
   ```bash
   docker compose ps wireguard
   ```

2. **Configure router port forwarding:**
   - Port: `51820` (UDP)
   - Forward to: `SERVER_IP` (your server's internal IP)

3. **Get client configuration:**
   ```bash
   # For mobile (QR code)
   docker exec wireguard /app/show-peer 1
   
   # For desktop (config file)
   docker exec wireguard cat /config/peer1/peer1.conf
   ```

4. **Install WireGuard client:**
   - **iOS/Android:** Install WireGuard app, scan QR code
   - **Windows/macOS/Linux:** Install WireGuard, import `.conf` file

5. **Connect and test:**
   - Enable VPN connection
   - Access services via internal IPs:
     - AdGuard: `http://192.168.1.100:80`
     - n8n: `https://192.168.1.100:5678`
     - Grafana: `http://192.168.1.100:3001`

### Security Benefits

- ✅ All traffic encrypted (military-grade)
- ✅ Single port exposed (51820/UDP)
- ✅ No service credentials exposed to internet
- ✅ Full network access (DNS, services, etc.)
- ✅ Modern, audited protocol

See [security-tickets/17-wireguard-hardening.md](../security-tickets/17-wireguard-hardening.md) for hardening.

## Option 2: Hybrid Approach (VPN + Selective Exposure)

For external webhooks (GitHub, APIs) while keeping admin interfaces private.

### Use Case

- n8n webhooks need to receive events from GitHub, APIs, etc.
- Admin interfaces (n8n UI, Grafana, AdGuard) remain VPN-only

### Implementation

**Expose only webhook paths:**
1. Deploy reverse proxy (Nginx or Traefik)
2. Configure path-based routing:
   - `/webhook/*` → Public (with rate limiting)
   - `/*` → VPN/LAN only

See [security-tickets/06-reverse-proxy-rate-limiting.md](../security-tickets/06-reverse-proxy-rate-limiting.md) for implementation.

**Router configuration:**
```
Port 51820/UDP → SERVER_IP (WireGuard)
Port 5678/TCP  → SERVER_IP (n8n webhooks only, with path filtering)
```

## Option 3: Direct Port Forwarding (Not Recommended)

⚠️ **High Security Risk** - Only use if you understand the implications.

### Router Configuration

Access your router (usually `192.168.1.1` or `192.168.0.1`) and add port forwarding rules:

| Service | External Port | Internal IP | Internal Port | Protocol |
|---------|---------------|-------------|---------------|----------|
| n8n | 5678 | SERVER_IP | 5678 | TCP |

**Do NOT forward:**
- Port 53 (DNS) - Becomes open resolver
- Port 80 (AdGuard) - Admin interface exposed
- Port 9090/3001 (Monitoring) - Sensitive data exposed

### Security Mitigations

If you must use direct port forwarding:

1. **Change default ports:**
   ```bash
   # Use non-standard external port
   # Router: 15678 (external) → 5678 (internal)
   ```

2. **Enable fail2ban:**
   See [security-tickets/README.md](../security-tickets/README.md)

3. **Use Let's Encrypt certificates:**
   See [security-tickets/04-tls-certificate-monitoring.md](../security-tickets/04-tls-certificate-monitoring.md)

4. **Monitor access logs:**
   ```bash
   docker compose logs n8n | grep -i auth
   docker compose logs adguard | grep -i blocked
   ```

5. **Set up alerts:**
   See [MONITORING_DEPLOYMENT.md](MONITORING_DEPLOYMENT.md)

## Dynamic DNS

If your ISP assigns dynamic IP addresses, use DDNS to maintain consistent access.

### Recommended Providers

- **DuckDNS** - Free, easy setup
- **No-IP** - Free tier available
- **Cloudflare** - Free with domain

### DuckDNS Setup Example

1. **Create account:** https://www.duckdns.org/
2. **Create subdomain:** `yourhomeserver.duckdns.org`
3. **Install updater on server:**

```bash
# Create update script
cat > ~/duckdns-update.sh <<'SCRIPT'
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=yourhomeserver&token=YOUR-TOKEN&ip=" | curl -k -o ~/duckdns.log -K -
SCRIPT

chmod +x ~/duckdns-update.sh

# Test
~/duckdns-update.sh
cat ~/duckdns.log  # Should show "OK"

# Add to cron (update every 5 minutes)
crontab -e
# Add: */5 * * * * ~/duckdns-update.sh >/dev/null 2>&1
```

4. **Update `.env`:**
   ```bash
   N8N_EDITOR_BASE_URL=https://yourhomeserver.duckdns.org:5678
   WIREGUARD_SERVERURL=yourhomeserver.duckdns.org
   ```

5. **Restart services:**
   ```bash
   docker compose up -d --force-recreate n8n wireguard
   ```

## Cloudflare Tunnel (Alternative)

Cloudflare Tunnel provides secure access without port forwarding.

### Advantages

- ✅ No ports opened on router
- ✅ DDoS protection
- ✅ Free SSL certificates
- ✅ Access control via Cloudflare dashboard

### Disadvantages

- ⚠️ Requires Cloudflare account
- ⚠️ Traffic routes through Cloudflare
- ⚠️ Additional complexity

### Setup Overview

1. Create Cloudflare account and add domain
2. Install `cloudflared` on server
3. Create tunnel and configure routes
4. Point domain to tunnel

See: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

## Testing Remote Access

### From Outside Network

**Test with mobile data (disable WiFi):**

```bash
# Test VPN
ping 192.168.1.100

# Test n8n
curl -k -I https://yourhomeserver.duckdns.org:5678

# Test webhook
curl -X POST https://yourhomeserver.duckdns.org:5678/webhook/test
```

### Security Checks

```bash
# Check open ports (from external tool)
# Visit: https://www.yougetsignal.com/tools/open-ports/

# Should see:
# ✅ 51820/UDP - Open (WireGuard)
# ❌ 53 - Closed (DNS not exposed)
# ❌ 80 - Closed (AdGuard not exposed)
# ❌ 9090 - Closed (Prometheus not exposed)

# Check for unauthorized access
docker compose logs | grep -i "unauthorized\|forbidden\|denied"
```

## Firewall Configuration (Server)

If using `ufw` firewall on server:

```bash
# Allow SSH (important!)
sudo ufw allow 22/tcp

# Allow WireGuard
sudo ufw allow 51820/udp

# If exposing n8n webhooks (not recommended)
sudo ufw allow 5678/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## Mobile Access Best Practices

1. **Always use VPN** when accessing sensitive services
2. **Use strong passwords** for VPN and services
3. **Enable MFA** where available (future: Authentik)
4. **Regularly update** WireGuard app and server
5. **Monitor logs** for suspicious activity

## ISP Considerations

### Port Blocking

Some ISPs block common ports:
- **Port 80/443:** Often blocked on residential plans
- **Port 53:** Usually blocked (open resolver risk)
- **Solution:** Use non-standard ports or VPN

### CGNAT (Carrier-Grade NAT)

If your ISP uses CGNAT, you won't have a unique public IP:
- **Check:** Visit https://www.whatismyip.com/ - Does it match your router's WAN IP?
- **Solution:** Cloudflare Tunnel, Tailscale, or ask ISP for dedicated IP

### Upload Speed

Home upload speeds are typically limited:
- **Test:** https://www.speedtest.net/
- **Impact:** Slow remote access if <10 Mbps upload
- **Solution:** Optimize services, use CDN for large files

## Troubleshooting

### Cannot Connect via VPN

```bash
# Check WireGuard is running
docker compose ps wireguard

# Check router port forwarding (51820/UDP)
# Test from external: sudo nmap -sU -p 51820 YOUR_PUBLIC_IP

# Check WireGuard logs
docker compose logs wireguard

# Regenerate peer config
docker compose down wireguard
sudo rm -rf ./data/wireguard/*
docker compose up -d wireguard
```

### VPN Connected but Services Unreachable

```bash
# Check allowed IPs in client config
# Should include: 192.168.1.0/24,10.13.13.0/24

# Check DNS
# WireGuard should set DNS to AdGuard IP (192.168.1.100)

# Test from VPN client
ping 192.168.1.100
curl http://192.168.1.100:80
```

### Dynamic DNS Not Updating

```bash
# Check update script
~/duckdns-update.sh
cat ~/duckdns.log

# Should show "OK"
# If "KO", check token and domain name

# Check cron is running
crontab -l
grep CRON /var/log/syslog
```

## References

- [WireGuard Hardening](../security-tickets/17-wireguard-hardening.md)
- [Network Segmentation](../security-tickets/05-network-segmentation.md)
- [Reverse Proxy Setup](../security-tickets/06-reverse-proxy-rate-limiting.md)
- [Security Roadmap](../security-tickets/README.md)
