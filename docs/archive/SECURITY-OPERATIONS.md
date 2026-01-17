# Security Operations Guide

Complete guide for managing and monitoring the security features of the home server stack.

## Overview

The stack implements four layers of security:
1. **UFW Firewall** - Network-level filtering
2. **Traefik Middleware** - Application-level access control
3. **Fail2ban** - Automated attack response
4. **Prometheus Monitoring** - Real-time security alerting

## Security Setup

### Initial Setup

```bash
# 1. Configure firewall (run on server)
sudo ./scripts/setup-firewall.sh

# 2. Start fail2ban
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d fail2ban

# 3. Verify services are protected
# From internet (should fail with 403):
curl -I https://n8n.yourdomain.com

# From local network (should work):
curl -I https://n8n.yourdomain.com
```

## Monitoring Security

### Real-time Monitoring

**Watch Traefik access logs:**
```bash
# All access
sudo docker logs -f traefik

# Only errors
sudo docker logs -f traefik 2>&1 | grep -E '(4[0-9]{2}|5[0-9]{2})'

# Exclude local network traffic
tail -f data/traefik/logs/access.log | grep -v "192.168"
```

**Watch fail2ban activity:**
```bash
# All activity
sudo docker logs -f fail2ban

# Ban/unban events only
sudo docker logs -f fail2ban | grep -E "(Ban|Unban)"
```

### Check Current Status

**Fail2ban status:**
```bash
# List all jails
sudo docker exec fail2ban fail2ban-client status

# Check specific jail
sudo docker exec fail2ban fail2ban-client status traefik-auth

# View banned IPs
sudo docker exec fail2ban fail2ban-client status traefik-scanner | grep "Banned IP"
```

**Firewall status:**
```bash
sudo ufw status verbose
```

**Active connections:**
```bash
# All established connections
sudo netstat -tupn | grep ESTABLISHED

# Group by source IP
sudo netstat -tupn | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn
```

## Responding to Incidents

### Investigating Suspicious Activity

**1. Check recent access patterns:**
```bash
# View last 100 access log entries
tail -100 data/traefik/logs/access.log

# Find specific IP activity
grep "1.2.3.4" data/traefik/logs/access.log

# Count requests by IP
awk '{print $1}' data/traefik/logs/access.log | sort | uniq -c | sort -rn | head -20
```

**2. Check fail2ban logs:**
```bash
# Recent bans
sudo docker exec fail2ban fail2ban-client status traefik-auth

# View fail2ban database
sudo docker exec fail2ban sqlite3 /data/db/fail2ban.sqlite3 "SELECT * FROM bans ORDER BY timeofban DESC LIMIT 10;"
```

**3. Check Prometheus alerts:**
```bash
# View active alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

### Blocking an IP Address

**Temporary block (via fail2ban):**
```bash
# Ban an IP
sudo docker exec fail2ban fail2ban-client set traefik-auth banip 1.2.3.4

# Unban an IP
sudo docker exec fail2ban fail2ban-client set traefik-auth unbanip 1.2.3.4
```

**Permanent block (via UFW):**
```bash
# Block specific IP
sudo ufw deny from 1.2.3.4

# Block IP range
sudo ufw deny from 1.2.3.0/24

# Remove block
sudo ufw delete deny from 1.2.3.4
```

### If You're Locked Out

If middleware blocks your legitimate IP:

**1. SSH into server:**
```bash
ssh joe@192.168.1.101
```

**2. Temporarily disable middleware:**
```bash
cd ~/home-server-stack

# Edit docker-compose.yml and comment out middleware line:
# - "traefik.http.routers.n8n.middlewares=admin-secure"

# Restart Traefik
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart traefik
```

**3. Or add your IP to whitelist:**
```bash
# Edit docker-compose.yml, update internal-only middleware:
# - "traefik.http.middlewares.internal-only.ipwhitelist.sourcerange=192.168.0.0/16,YOUR_IP/32,10.0.0.0/8"

# Restart Traefik
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart traefik
```

## Security Configuration

### Adjusting Rate Limits

Edit `docker-compose.yml`:

**For admin services:**
```yaml
# Current: 10 requests/min
- "traefik.http.middlewares.admin-ratelimit.ratelimit.average=10"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.period=1m"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.burst=5"

# More strict (slower attacks):
- "traefik.http.middlewares.admin-ratelimit.ratelimit.average=5"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.period=1m"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.burst=3"

# More lenient (faster legitimate use):
- "traefik.http.middlewares.admin-ratelimit.ratelimit.average=20"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.period=1m"
- "traefik.http.middlewares.admin-ratelimit.ratelimit.burst=10"
```

After changes:
```bash
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart traefik
```

### Adjusting Fail2ban Rules

Edit `config/fail2ban/jail.local`:

**Make rules stricter:**
```ini
[traefik-auth]
maxretry = 2      # Ban after 2 failures (was 3)
bantime = 2h      # Ban for 2 hours (was 1h)
```

**Make rules more lenient:**
```ini
[traefik-auth]
maxretry = 5      # Ban after 5 failures (was 3)
bantime = 30m     # Ban for 30 minutes (was 1h)
```

After changes:
```bash
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart fail2ban
```

### Adding Custom Fail2ban Filters

Create `config/fail2ban/filter.d/custom.conf`:
```ini
[Definition]
failregex = ^.* "YOUR_PATTERN_HERE" .* "<HOST>".*$
ignoreregex =
```

Add jail in `config/fail2ban/jail.local`:
```ini
[custom-jail]
enabled = true
port = http,https
filter = custom
logpath = /var/log/traefik/access.log
maxretry = 10
findtime = 1m
bantime = 1h
```

Restart fail2ban to apply.

## Security Best Practices

### Regular Audits

**Weekly checks:**
```bash
# 1. Review banned IPs
sudo docker exec fail2ban fail2ban-client status | grep "Currently banned"

# 2. Check for high-volume IPs
awk '{print $1}' data/traefik/logs/access.log | sort | uniq -c | sort -rn | head -20

# 3. Review Prometheus security alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.category=="security")'
```

**Monthly tasks:**
- Review and tune rate limits based on usage
- Update fail2ban rules if new attack patterns emerge
- Check for security updates: `docker compose pull`
- Review firewall rules: `sudo ufw status numbered`

### Backup Security Configuration

```bash
# Backup security configs
tar -czf security-backup-$(date +%Y%m%d).tar.gz \
  config/fail2ban/ \
  data/fail2ban/db/ \
  .env

# Backup firewall rules
sudo ufw status numbered > firewall-rules-backup.txt
```

## Troubleshooting

### Fail2ban Not Banning

**Check if jails are running:**
```bash
sudo docker exec fail2ban fail2ban-client status
```

**Check if logs are being read:**
```bash
sudo docker exec fail2ban fail2ban-client get traefik-auth logpath
```

**Test filter manually:**
```bash
# Test if filter matches log entries
sudo docker exec fail2ban fail2ban-regex /var/log/traefik/access.log /etc/fail2ban/filter.d/traefik-auth.conf
```

### Middleware Not Working

**Verify middleware is loaded:**
```bash
sudo docker logs traefik 2>&1 | grep "middleware"
```

**Check router configuration:**
```bash
sudo docker exec traefik wget -q -O - http://localhost:8080/api/http/routers | jq '.[] | {name: .name, middlewares: .middlewares}'
```

**Force Traefik to reload:**
```bash
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml stop traefik
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml rm -f traefik
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d traefik
```

### High False Positive Rate

If fail2ban is banning legitimate users:

**Whitelist specific IPs:**
Edit `config/fail2ban/jail.local`:
```ini
[DEFAULT]
ignoreip = 127.0.0.1/8 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 YOUR_IP_HERE
```

**Increase thresholds:**
```ini
[traefik-auth]
maxretry = 5      # Increase from 3
findtime = 15m    # Increase window from 10m
```

## Emergency Procedures

### Under Active Attack

**1. Immediate response:**
```bash
# Enable aggressive fail2ban mode
sudo docker exec fail2ban fail2ban-client set traefik-scanner maxretry 3
sudo docker exec fail2ban fail2ban-client set traefik-scanner bantime 86400  # 24h
```

**2. Block attack source:**
```bash
# If attacks from specific country/ASN, block entire range
sudo ufw deny from ATTACKER_RANGE/24
```

**3. Temporarily disable public access:**
```bash
# Block all non-local traffic at firewall level
sudo ufw deny 80/tcp
sudo ufw deny 443/tcp

# Re-enable after attack subsides
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### System Compromise Suspected

**1. Isolate immediately:**
```bash
# Disable all external access
sudo ufw default deny incoming
sudo ufw reload
```

**2. Collect evidence:**
```bash
# Copy logs before they're rotated
sudo tar -czf incident-logs-$(date +%Y%m%d-%H%M).tar.gz \
  data/traefik/logs/ \
  data/fail2ban/ \
  /var/log/
```

**3. Investigate:**
```bash
# Check for modified files
sudo find /opt -type f -mtime -1

# Check active connections
sudo netstat -tupn

# Check running processes
sudo docker ps -a
```

**4. Rotate credentials:**
```bash
# Change all passwords in .env
# Regenerate API keys
# Restart all services
```

## Additional Resources

- **Traefik Middleware Docs**: https://doc.traefik.io/traefik/middlewares/overview/
- **Fail2ban Manual**: https://www.fail2ban.org/wiki/index.php/Manual
- **UFW Guide**: https://help.ubuntu.com/community/UFW
- **Project Security Policy**: ../SECURITY.md
