# Testing admin-secure Middleware

## What Was Applied

All administrative services now have `admin-secure` middleware applied, which enforces:

1. **IP Whitelist** - Only allows access from:
   - `192.168.0.0/16` - Local network (e.g., 192.168.1.x)
   - `172.16.0.0/12` - Docker internal networks
   - `10.0.0.0/8` - WireGuard VPN (10.13.13.x)

2. **Security Headers** - HSTS, XSS protection, frame deny, etc.

3. **Rate Limiting** - Max 10 requests/min per IP (burst 5)

## Services Protected

- ✅ n8n (https://n8n.radsrv.com)
- ✅ AdGuard Home (https://adguard.radsrv.com)
- ✅ Grafana (https://grafana.radsrv.com)
- ✅ Prometheus (https://prometheus.radsrv.com)
- ✅ Alertmanager (https://alerts.radsrv.com)
- ✅ Traefik Dashboard (https://traefik.radsrv.com)

## Testing Steps

### On Remote Server

```bash
# 1. Pull latest changes
cd ~/home-server-stack
sudo git pull

# 2. Restart services to apply middleware
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart traefik
# Wait 5 seconds for Traefik to reload
sleep 5

# 3. Check Traefik logs for middleware loading
sudo docker logs traefik 2>&1 | grep -i middleware
```

### From Your Mac (Outside Network - Should FAIL)

```bash
# These should all return HTTP 403 Forbidden
curl -I https://n8n.radsrv.com
curl -I https://grafana.radsrv.com
curl -I https://prometheus.radsrv.com
curl -I https://traefik.radsrv.com
```

**Expected Result:** `HTTP/2 403` (Forbidden)

### From Local Network (Should WORK)

```bash
# From a device on 192.168.1.x network
curl -I https://n8n.radsrv.com
curl -I https://grafana.radsrv.com
```

**Expected Result:** `HTTP/2 200` or `HTTP/2 302` (normal responses)

### Via WireGuard VPN (Should WORK)

```bash
# 1. Connect to WireGuard VPN first
# Your IP should be in 10.13.13.x range

# 2. Then test access
curl -I https://n8n.radsrv.com
curl -I https://grafana.radsrv.com
```

**Expected Result:** `HTTP/2 200` or `HTTP/2 302` (normal responses)

## Expected Behavior

| Location | IP Range | Access |
|----------|----------|--------|
| Internet (your Mac without VPN) | Public IP | ❌ 403 Forbidden |
| Local Network (home devices) | 192.168.1.x | ✅ Allowed |
| WireGuard VPN | 10.13.13.x | ✅ Allowed |
| Docker containers | 172.17.x.x | ✅ Allowed |

## Troubleshooting

### If everything returns 403 (even local network):

1. Check your local network subnet matches the whitelist:
   ```bash
   ip addr | grep inet
   ```

2. If your network is different (e.g., 192.168.0.x or 10.0.x.x), update the middleware in docker-compose.yml:
   ```yaml
   - "traefik.http.middlewares.internal-only.ipwhitelist.sourcerange=YOUR_NETWORK/16,172.16.0.0/12,10.0.0.0/8"
   ```

### If everything still works from the internet:

1. Check if middleware is actually loaded:
   ```bash
   sudo docker logs traefik 2>&1 | tail -50
   ```

2. Verify container was restarted:
   ```bash
   sudo docker ps | grep traefik
   # Check the "Created" time - should be recent
   ```

3. Force recreate Traefik:
   ```bash
   sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml stop traefik
   sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml rm -f traefik
   sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d traefik
   ```

## Rollback (If Needed)

If something goes wrong and you're locked out:

```bash
# SSH into server
ssh joe@192.168.1.101

# Remove middleware temporarily
cd ~/home-server-stack
git stash

# Restart Traefik
sudo docker compose -f docker-compose.yml -f docker-compose.monitoring.yml restart traefik
```

## Important Note for n8n Webhooks

The n8n service now blocks ALL external access, including webhooks. When you need to expose webhooks publicly, you'll need to create a separate router for webhook paths. See the TODO comment in docker-compose.yml at the n8n service for details.

Ticket-13 will implement the proper webhook architecture with split routing.
