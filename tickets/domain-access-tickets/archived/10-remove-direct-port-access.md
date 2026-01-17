# Ticket 10: Remove Direct Port Access

**Priority:** Medium
**Estimated Time:** 1-2 hours
**Category:** Security & Cleanup
**Status:** ✅ Complete
**Dependencies:** Tickets 01-09 complete, 1-2 week monitoring period
**Completed:** 2025-10-17

## Overview

Remove direct IP:port access to services, forcing all traffic through Traefik reverse proxy. This completes the domain-based access migration by eliminating the legacy access method and ensuring all services use HTTPS via Traefik.

## Current Situation

Services are currently accessible via **two methods**:

1. ✅ **Domain-based (via Traefik):** `https://n8n.${DOMAIN}`
2. ⚠️ **Direct IP:port:** `http://192.168.1.101:5678`

The direct IP:port bindings were kept for backward compatibility during the migration, but they:
- Bypass Traefik's HTTPS enforcement
- Allow plain HTTP access
- Create two sources of truth for service access
- Are potentially less secure

## Goal

Force all service access through Traefik by:
1. Removing direct port bindings from `docker-compose.yml`
2. Using Docker `expose` instead of `ports` for internal-only exposure
3. Ensuring services are only accessible via `https://*.${DOMAIN}`

## Services to Update

### Main Services (docker-compose.yml)

| Service | Current Port Binding | New Configuration |
|---------|---------------------|-------------------|
| n8n | `${SERVER_IP}:5678:5678` | `expose: [5678]` |
| Glance | `${SERVER_IP}:8282:8080` | `expose: [8080]` |
| HortusFox | `${SERVER_IP}:8181:80` | `expose: [80]` |

### Monitoring Services (docker-compose.monitoring.yml)

| Service | Current Port Binding | New Configuration |
|---------|---------------------|-------------------|
| Grafana | `${SERVER_IP}:3001:3000` | `expose: [3000]` |

### Services to Keep Port Bindings

These services **should keep** their port bindings as they serve specific purposes:

| Service | Port Binding | Reason |
|---------|-------------|--------|
| AdGuard | `${SERVER_IP}:53:53/tcp/udp` | DNS service (required for domain resolution) |
| AdGuard | `${SERVER_IP}:8888:80` | Keep for emergency access if Traefik fails |
| Traefik | `${SERVER_IP}:80:80` | Entry point for HTTP traffic |
| Traefik | `${SERVER_IP}:443:443` | Entry point for HTTPS traffic |
| Prometheus | `${SERVER_IP}:9090:9090` | Direct access for metrics scraping |
| Alertmanager | `${SERVER_IP}:9093:9093` | Direct access for alert management |
| WireGuard | `51820:51820/udp` | VPN entry point |
| WireGuard UI | `${SERVER_IP}:51821:51821` | VPN management interface |
| Ollama | `${SERVER_IP}:11434:11434` | API access for AI workloads |
| Habitica | `${SERVER_IP}:8080:3000` | Keep for now (no Traefik labels yet) |
| Bookwyrm | `${SERVER_IP}:8000:8000` | Keep for now (external wrapper project) |

## Implementation Steps

### Step 1: Update docker-compose.yml

**n8n service:**
```yaml
n8n:
  image: n8nio/n8n:latest
  container_name: n8n
  restart: unless-stopped
  user: "1000:1000"
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:5678:5678"

  # ADD: expose section (internal Docker network only)
  expose:
    - 5678

  environment:
    # ... existing environment variables ...
  volumes:
    - ./data/n8n:/home/node/.n8n
  networks:
    - homeserver
  labels:
    # ... existing Traefik labels ...
```

**Glance service:**
```yaml
glance:
  image: glanceapp/glance:${GLANCE_VERSION:-latest}
  container_name: glance
  restart: unless-stopped
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:${GLANCE_PORT:-8282}:8080"

  # ADD: expose section
  expose:
    - 8080

  environment:
    # ... existing environment variables ...
  labels:
    # ... existing Traefik labels ...
```

**HortusFox service:**
```yaml
hortusfox:
  image: ghcr.io/danielbrendel/hortusfox-web:${HORTUSFOX_VERSION:-latest}
  container_name: hortusfox
  restart: unless-stopped
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:8181:80"

  # ADD: expose section
  expose:
    - 80

  environment:
    # ... existing environment variables ...
  labels:
    # ... existing Traefik labels ...
```

### Step 2: Update docker-compose.monitoring.yml

**Grafana service:**
```yaml
grafana:
  image: grafana/grafana:latest
  container_name: grafana
  restart: unless-stopped
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:3001:3000"

  # ADD: expose section
  expose:
    - 3000

  environment:
    # ... existing environment variables ...
  labels:
    # ... existing Traefik labels ...
```

### Step 3: Update Documentation

**Files to update:**

1. **README.md** - Remove IP:port references in "Access your services" section
2. **docs/DOMAIN-BASED-ACCESS.md** - Update "Direct Access" column to show "N/A (Traefik only)"
3. **Makefile** - Update setup/help output to only show domain-based URLs

**Example Makefile change:**
```makefile
# Before:
@echo "  - Glance:       http://$$SERVER_IP:8282"

# After:
@echo "  - Glance:       https://glance.${DOMAIN}"
```

### Step 4: Update .env.example

Remove `GLANCE_PORT` variable as it's no longer needed:
```bash
# REMOVE:
# GLANCE_PORT=8282
```

### Step 5: Test All Services

After deploying changes:

```bash
# Restart services
docker compose down
docker compose up -d

# Run domain access tests
make test-domain-access

# Verify direct access is blocked
curl http://192.168.1.101:5678     # Should fail/refuse connection
curl http://192.168.1.101:8282     # Should fail/refuse connection
curl http://192.168.1.101:8181     # Should fail/refuse connection

# Verify domain access works
curl -k https://n8n.${DOMAIN}      # Should work
curl -k https://glance.${DOMAIN}   # Should work
curl -k https://hortusfox.${DOMAIN} # Should work
curl -k https://grafana.${DOMAIN}  # Should work
```

## Testing Checklist

- [ ] All services start successfully after changes
- [ ] Domain-based access works: `make test-domain-access` passes
- [ ] Direct IP:port access is blocked (connection refused)
- [ ] Traefik dashboard shows all services as healthy
- [ ] No errors in Traefik logs: `docker logs traefik`
- [ ] Services function normally via domain names
- [ ] Browser can access all services via HTTPS domains
- [ ] VPN clients can access services via domain names

## Rollback Plan

If issues occur:

1. **Revert docker-compose changes:**
   ```bash
   git revert HEAD
   docker compose up -d
   ```

2. **Emergency port restore:**
   Add port bindings back to affected services and restart

3. **Test access:**
   Verify both domain and direct access work again

## Success Criteria

- ✅ All configured services accessible only via `https://*.${DOMAIN}`
- ✅ Direct IP:port access returns "connection refused" for migrated services
- ✅ No service downtime during migration
- ✅ No errors in service or Traefik logs
- ✅ Documentation updated to reflect domain-only access
- ✅ Test suite passes all checks

## Security Benefits

✅ **Enforced HTTPS** - All traffic goes through Traefik's SSL termination
✅ **Single entry point** - Easier to monitor and control access
✅ **No HTTP bypass** - Can't skip HTTPS by using direct IP:port
✅ **Consistent authentication** - All access goes through Traefik middleware
✅ **Centralized logging** - All requests logged by Traefik

## User Impact

### Breaking Changes

⚠️ **Users can no longer access services via IP:port**

**Before:**
- `http://192.168.1.101:5678` ✅ Works
- `https://n8n.${DOMAIN}` ✅ Works

**After:**
- `http://192.168.1.101:5678` ❌ Connection refused
- `https://n8n.${DOMAIN}` ✅ Works

### Migration Notice

Users should be notified:

```
⚠️ Important: Direct IP:port access has been disabled

Services are now only accessible via domain names:
- n8n:       https://n8n.${DOMAIN}
- Glance:    https://glance.${DOMAIN}
- HortusFox: https://hortusfox.${DOMAIN}
- Grafana:   https://grafana.${DOMAIN}

Update your bookmarks and workflows accordingly.

Why? This ensures all traffic uses HTTPS and provides better security.
```

## Notes

- Complete this ticket only after 1-2 week monitoring period
- Ensure domain-based access is stable and reliable
- Consider user feedback before removing port bindings
- AdGuard port binding (8888) kept for emergency Traefik-bypass access
- Services not yet configured with Traefik (Habitica, Bookwyrm) keep port bindings
- Monitoring services (Prometheus, Alertmanager) keep direct access for scraping

## Related Tickets

- **Ticket 01:** Traefik Deployment (foundation)
- **Ticket 03:** Initial Service Labels (Traefik configuration)
- **Ticket 05:** Test Initial Services (validation)
- **Ticket 06:** n8n Configuration (service migration)
- **Ticket 09:** Update Documentation (docs update)

## Future Enhancements

After this ticket is complete, consider:

1. **Add authentication middleware** - Protect services without built-in auth
2. **Implement rate limiting** - Prevent brute force attacks
3. **Add fail2ban** - Block IPs after failed auth attempts
4. **Configure mkcert** - Locally-trusted certificates (no browser warnings)
5. **Add OAuth2 proxy** - Centralized SSO for all services

---

**Created:** 2025-01-15
**Target Completion:** After 1-2 week monitoring period following ticket 09
