# Ticket 12: Security Hardening for Public Exposure

**Priority:** High
**Estimated Time:** 2 hours
**Category:** Security
**Status:** ⬜ Pending
**Dependencies:** Ticket 11 (SSL certificates) complete

## Overview

Implement comprehensive security measures to protect your homelab now that `webhook.example.com` will be publicly accessible. This includes rate limiting, IP filtering, monitoring, and fail2ban protection.

## Current Security Posture

**Exposed Services:**
- WireGuard VPN (port 51820) - Already secure
- n8n webhook endpoint (port 5678) - Currently bypasses Traefik (TO BE FIXED)
- Future: Webhook endpoints via Traefik on 443

**Protected Services (VPN/Local Only):**
- All admin interfaces
- All internal services
- Traefik dashboard

## Security Layers to Implement

### Layer 1: Traefik Middleware Security

Create security middleware chains for different exposure levels:

**File:** `docker-compose.yml` (Traefik labels section)

```yaml
traefik:
  # ... existing config ...
  labels:
    # ... existing labels ...
    
    # Security Headers Middleware
    - "traefik.http.middlewares.security-headers.headers.frameDeny=true"
    - "traefik.http.middlewares.security-headers.headers.browserXssFilter=true"
    - "traefik.http.middlewares.security-headers.headers.contentTypeNosniff=true"
    - "traefik.http.middlewares.security-headers.headers.stsSeconds=31536000"
    - "traefik.http.middlewares.security-headers.headers.stsIncludeSubdomains=true"
    - "traefik.http.middlewares.security-headers.headers.stsPreload=true"
    
    # Rate Limiting for Webhooks (generous for legitimate use)
    - "traefik.http.middlewares.webhook-ratelimit.ratelimit.average=100"
    - "traefik.http.middlewares.webhook-ratelimit.ratelimit.period=1m"
    - "traefik.http.middlewares.webhook-ratelimit.ratelimit.burst=50"
    
    # Strict Rate Limiting for Admin Access
    - "traefik.http.middlewares.admin-ratelimit.ratelimit.average=10"
    - "traefik.http.middlewares.admin-ratelimit.ratelimit.period=1m"
    - "traefik.http.middlewares.admin-ratelimit.ratelimit.burst=5"
    
    # IP Whitelist for Internal Services (RFC1918 + VPN)
    - "traefik.http.middlewares.internal-only.ipwhitelist.sourcerange=192.168.0.0/16,172.16.0.0/12,10.0.0.0/8"
    
    # Webhook Security Chain
    - "traefik.http.middlewares.webhook-secure.chain.middlewares=security-headers,webhook-ratelimit"
    
    # Admin Security Chain  
    - "traefik.http.middlewares.admin-secure.chain.middlewares=internal-only,security-headers,admin-ratelimit"
```

### Layer 2: Fail2ban Protection

Protect against brute force and scanning attempts.

**File:** `docker-compose.yml` (new service)

```yaml
fail2ban:
  image: crazymax/fail2ban:latest
  container_name: fail2ban
  restart: unless-stopped
  cap_add:
    - NET_ADMIN
    - NET_RAW
  environment:
    - TZ=${TZ}
    - F2B_DB_PURGE_AGE=30d
    - F2B_LOG_LEVEL=INFO
  volumes:
    - ./data/fail2ban:/data
    - ./data/traefik/logs:/var/log/traefik:ro
    - ./config/fail2ban/jail.local:/etc/fail2ban/jail.local:ro
    - ./config/fail2ban/filter.d:/etc/fail2ban/filter.d:ro
  network_mode: host
```

**File:** `config/fail2ban/jail.local`

```ini
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
ignoreip = 127.0.0.1/8 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12

[traefik-auth]
enabled = true
port = http,https
filter = traefik-auth
logpath = /var/log/traefik/access.log
maxretry = 3

[traefik-webhook]
enabled = true
port = http,https
filter = traefik-webhook
logpath = /var/log/traefik/access.log
maxretry = 20
findtime = 1m
bantime = 10m

[traefik-scanner]
enabled = true
port = http,https  
filter = traefik-scanner
logpath = /var/log/traefik/access.log
maxretry = 10
findtime = 1m
bantime = 24h
```

**File:** `config/fail2ban/filter.d/traefik-auth.conf`

```ini
[Definition]
failregex = ^.* 401 .* "-" "-" \d+ "-" ".*" ".*" ".*" "<HOST>".*$
ignoreregex =
```

**File:** `config/fail2ban/filter.d/traefik-webhook.conf`

```ini
[Definition]
failregex = ^.* (429|503) .* "-" "-" \d+ "-" ".*" ".*" ".*" "<HOST>".*$
ignoreregex =
```

**File:** `config/fail2ban/filter.d/traefik-scanner.conf`

```ini
[Definition]
failregex = ^.* 404 .* "-" "-" \d+ "-" ".*" ".*" ".*" "<HOST>".*$
            ^.* ".*(/\.\.|/etc/passwd|/wp-admin|/phpMyAdmin|/admin).*" \d{3} .* "<HOST>".*$
ignoreregex =
```

### Layer 3: UFW Firewall Rules

Configure Ubuntu firewall for defense in depth.

**Script:** `scripts/setup-firewall.sh`

```bash
#!/bin/bash

# Reset UFW
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (adjust port if needed)
sudo ufw allow 22/tcp comment 'SSH'

# Allow WireGuard VPN
sudo ufw allow 51820/udp comment 'WireGuard VPN'

# Allow HTTP/HTTPS only from Traefik
sudo ufw allow 80/tcp comment 'HTTP for Traefik'
sudo ufw allow 443/tcp comment 'HTTPS for Traefik'

# Allow internal network full access
sudo ufw allow from 192.168.1.0/24 comment 'Local Network'

# Allow WireGuard clients (adjust subnet)
sudo ufw allow from 10.0.0.0/24 comment 'WireGuard Clients'

# Rate limiting for SSH
sudo ufw limit ssh/tcp

# Enable UFW
sudo ufw --force enable
sudo ufw status verbose
```

### Layer 4: Monitoring and Alerting

**File:** `docker-compose.yml` (update Prometheus/Alertmanager)

Add alert rules for security events:

**File:** `config/prometheus/alerts.yml`

```yaml
groups:
  - name: security
    interval: 30s
    rules:
      - alert: HighWebhookRate
        expr: rate(traefik_service_requests_total{service="webhook-n8n"}[5m]) > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High webhook request rate detected"
          description: "Webhook endpoint receiving {{ $value }} requests per second"
      
      - alert: TooMany401Errors
        expr: rate(traefik_service_requests_total{code="401"}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Authentication failures detected"
          description: "Multiple 401 errors - possible brute force attempt"
      
      - alert: TooMany404Errors
        expr: rate(traefik_service_requests_total{code="404"}[5m]) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Scanning activity detected"
          description: "High rate of 404 errors - possible scanning"
```

### Layer 5: Log Aggregation and Analysis

**File:** `docker-compose.yml` (optional but recommended)

```yaml
loki:
  image: grafana/loki:latest
  container_name: loki
  restart: unless-stopped
  volumes:
    - ./data/loki:/loki
    - ./config/loki/loki-config.yml:/etc/loki/loki-config.yml:ro
  command: -config.file=/etc/loki/loki-config.yml
  networks:
    - homeserver

promtail:
  image: grafana/promtail:latest
  container_name: promtail
  restart: unless-stopped
  volumes:
    - ./data/traefik/logs:/var/log/traefik:ro
    - ./config/promtail/promtail-config.yml:/etc/promtail/promtail-config.yml:ro
    - /var/log:/var/log:ro
  command: -config.file=/etc/promtail/promtail-config.yml
  networks:
    - homeserver
```

## Implementation Checklist

### Immediate (Before Public Exposure)
- [ ] Configure Traefik security middleware
- [ ] Set up rate limiting for webhooks
- [ ] Enable security headers
- [ ] Configure IP whitelisting for admin services

### Within 24 Hours
- [ ] Deploy fail2ban with Traefik filters
- [ ] Configure UFW firewall rules
- [ ] Set up basic Prometheus alerts
- [ ] Test rate limiting works

### Within 1 Week
- [ ] Review and tune rate limits based on usage
- [ ] Set up log aggregation with Loki
- [ ] Create Grafana dashboard for security metrics
- [ ] Document incident response procedure

## Testing Security

### Test Rate Limiting
```bash
# Should get rate limited after threshold
for i in {1..150}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://webhook.example.com/webhook/test
  sleep 0.1
done
```

### Test Fail2ban
```bash
# Trigger auth failures (should get banned after 3 attempts)
for i in {1..5}; do
  curl -u wrong:wrong https://n8n.home.example.com
done

# Check if banned
sudo fail2ban-client status traefik-auth
```

### Test Security Headers
```bash
# Check security headers are present
curl -I https://webhook.example.com | grep -i "strict-transport"
```

## Monitoring Commands

### View Current Connections
```bash
# Active connections to your server
sudo netstat -tupn | grep ESTABLISHED

# Connections by IP
sudo netstat -tupn | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn
```

### Check Fail2ban Status
```bash
# List all jails
sudo fail2ban-client status

# Check specific jail
sudo fail2ban-client status traefik-webhook

# Unban an IP (if needed)
sudo fail2ban-client unban <IP>
```

### Monitor Logs in Real-time
```bash
# Watch Traefik access logs
tail -f data/traefik/logs/access.log | grep -v "192.168"

# Watch for 4xx/5xx errors
tail -f data/traefik/logs/access.log | grep -E '" (4|5)[0-9]{2} '

# Watch fail2ban actions
docker logs -f fail2ban | grep "Ban\|Unban"
```

## Security Best Practices

### Do's
- ✅ Regularly review access logs
- ✅ Keep rate limits as strict as possible
- ✅ Use VPN for all admin access
- ✅ Monitor for unusual patterns
- ✅ Keep Docker images updated
- ✅ Backup configuration regularly

### Don'ts
- ❌ Don't expose admin interfaces publicly
- ❌ Don't use default passwords
- ❌ Don't ignore security alerts
- ❌ Don't whitelist broad IP ranges
- ❌ Don't disable rate limiting for convenience

## Incident Response Plan

### If You Detect an Attack

1. **Immediate:**
   ```bash
   # Block attacker IP immediately
   sudo ufw insert 1 deny from <ATTACKER_IP>
   ```

2. **Investigate:**
   - Check logs for entry point
   - Look for any successful authentications
   - Check for modified files

3. **Remediate:**
   - Rotate all passwords
   - Review and patch vulnerability
   - Consider temporarily disabling public access

4. **Document:**
   - Record what happened
   - Note indicators of compromise
   - Update security rules

## Success Criteria

- ✅ Rate limiting active on all public endpoints
- ✅ Fail2ban protecting against brute force
- ✅ Security headers on all responses
- ✅ Monitoring alerts configured
- ✅ Firewall rules enforced
- ✅ Logs being collected and reviewed
- ✅ Can detect and auto-ban malicious IPs

## Next Steps

- **Ticket 13:** Configure n8n Webhook Architecture (public webhook, private admin)

---

**Created:** 2025-01-15
**Complexity:** Medium-High
**Ongoing:** Requires regular monitoring and tuning