# Test Initial Three Services

## Priority: 2 (High)
## Estimated Time: 1 hour
## Phase: Week 1 - Validation

## Description
Thoroughly test the three initially configured services (Glance, HortusFox, Grafana) to ensure domain-based access is working correctly, services are fully functional, and both old and new access methods work.

## Acceptance Criteria
- [ ] All 3 services accessible via https://*.home.local domains
- [ ] All 3 services still accessible via IP:port (backward compatibility)
- [ ] HTTP redirects to HTTPS correctly
- [ ] SSL/TLS certificates accepted (self-signed warning expected)
- [ ] Service functionality verified (login, data display, operations)
- [ ] No errors in service logs
- [ ] No errors in Traefik logs
- [ ] Performance acceptable (no significant latency increase)

## Services to Test

### 1. Glance (glance.home.local)
### 2. HortusFox (hortusfox.home.local)
### 3. Grafana (grafana.home.local)

## Testing Checklist

### DNS Resolution Tests
From a client device on the local network:

```bash
# Test DNS resolution
nslookup glance.home.local
# Expected: resolves to SERVER_IP (e.g., 192.168.1.100)

nslookup hortusfox.home.local
# Expected: resolves to SERVER_IP

nslookup grafana.home.local
# Expected: resolves to SERVER_IP

# Verify from server
dig @192.168.1.100 glance.home.local +short
dig @192.168.1.100 hortusfox.home.local +short
dig @192.168.1.100 grafana.home.local +short
```

**Expected Results:**
- [ ] All domains resolve to SERVER_IP
- [ ] Resolution time < 50ms
- [ ] No DNS errors

### HTTP/HTTPS Tests

#### Test 1: Glance Dashboard
```bash
# From server
curl -I http://glance.home.local
# Expected: 301/302 redirect to https://glance.home.local

curl -Ik https://glance.home.local
# Expected: 200 OK (k flag ignores cert warnings)

# From browser (client device)
# 1. Navigate to http://glance.home.local
#    Expected: Automatic redirect to HTTPS
# 2. Accept self-signed certificate warning
#    Expected: Glance dashboard loads normally
# 3. Verify widgets load correctly
#    Expected: RSS feeds, bookmarks, etc. display
# 4. Test backward compatibility: http://192.168.1.100:8282
#    Expected: Glance loads normally (no redirect)
```

**Glance Test Checklist:**
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads with self-signed cert
- [ ] Dashboard displays correctly
- [ ] Widgets load (RSS, Docker stats, etc.)
- [ ] No console errors in browser dev tools
- [ ] IP:port access still works

#### Test 2: HortusFox Plant Management
```bash
# From server
curl -I http://hortusfox.home.local
# Expected: 301/302 redirect to https://hortusfox.home.local

curl -Ik https://hortusfox.home.local
# Expected: 200 OK

# From browser
# 1. Navigate to https://hortusfox.home.local
# 2. Login with credentials from .env
#    Username: HORTUSFOX_ADMIN_EMAIL
#    Password: HORTUSFOX_ADMIN_PASSWORD
# 3. Verify dashboard loads
# 4. Test navigation (Plants, Tasks, etc.)
# 5. Test backward compatibility: http://192.168.1.100:8181
```

**HortusFox Test Checklist:**
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads successfully
- [ ] Login works correctly
- [ ] Dashboard displays plant data
- [ ] Navigation functional
- [ ] Database connection working (no connection errors)
- [ ] Images load correctly
- [ ] IP:port access still works

#### Test 3: Grafana Monitoring
```bash
# From server
curl -I http://grafana.home.local
# Expected: 301/302 redirect to https://grafana.home.local

curl -Ik https://grafana.home.local/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}

# From browser
# 1. Navigate to https://grafana.home.local
# 2. Login with credentials
#    Username: admin
#    Password: GRAFANA_PASSWORD from .env
# 3. Verify dashboards load
# 4. Check data sources (Prometheus)
# 5. View metrics and graphs
# 6. Test backward compatibility: http://192.168.1.100:3001
```

**Grafana Test Checklist:**
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads successfully
- [ ] Login works correctly
- [ ] Dashboards display
- [ ] Prometheus data source connected
- [ ] Metrics graphs rendering
- [ ] No data query errors
- [ ] IP:port access still works

### Traefik Validation Tests

```bash
# Check Traefik logs for routing
docker logs traefik --tail 100 | grep -E "(glance|hortusfox|grafana)"

# Check for errors
docker logs traefik --tail 100 | grep -i error

# View access logs
tail -f data/traefik/logs/access.log

# Check Traefik dashboard (if configured)
curl -k https://traefik.home.local
```

**Traefik Checklist:**
- [ ] No errors in Traefik logs
- [ ] Access logs show successful routing
- [ ] HTTP status codes are 200 (success) or 301/302 (redirect)
- [ ] All 3 routers visible in Traefik dashboard
- [ ] TLS certificates issued for all 3 services

### Service Logs Tests

```bash
# Check each service for errors
docker logs glance --tail 50
docker logs hortusfox --tail 50
docker logs grafana --tail 50

# Check health status
docker inspect glance | grep -A 10 Health
docker inspect hortusfox | grep -A 10 Health
docker inspect grafana | grep -A 10 Health
```

**Service Logs Checklist:**
- [ ] No errors in Glance logs
- [ ] No errors in HortusFox logs
- [ ] No errors in Grafana logs
- [ ] All services passing health checks
- [ ] No connection issues to databases (HortusFox → MariaDB, Grafana → Prometheus)

### Performance Tests

```bash
# Measure response times
time curl -Ik https://glance.home.local
time curl -Ik https://hortusfox.home.local
time curl -Ik https://grafana.home.local

# Compare with direct access
time curl -Ik http://192.168.1.100:8282
time curl -Ik http://192.168.1.100:8181
time curl -Ik http://192.168.1.100:3001
```

**Performance Checklist:**
- [ ] Domain access response time < 500ms
- [ ] No significant latency increase vs IP:port access (< 50ms overhead)
- [ ] Page load times acceptable in browser
- [ ] No timeouts or slow responses

### Browser Testing Matrix

Test from multiple client devices/browsers:

| Service | Chrome | Firefox | Safari | Mobile |
|---------|--------|---------|--------|--------|
| Glance  | [ ]    | [ ]     | [ ]    | [ ]    |
| HortusFox | [ ]  | [ ]     | [ ]    | [ ]    |
| Grafana | [ ]    | [ ]     | [ ]    | [ ]    |

**Browser Test Checklist:**
- [ ] SSL cert warning displays correctly
- [ ] Can accept cert and proceed
- [ ] Pages load fully
- [ ] No mixed content warnings
- [ ] Cookies/sessions work correctly
- [ ] Logout/login functions work

## Success Metrics

### Functional Metrics
- 100% of services accessible via domain names
- 100% of services retain IP:port access
- 100% of service features working correctly
- Zero service errors in logs

### Performance Metrics
- DNS resolution: < 50ms
- HTTP → HTTPS redirect: < 100ms
- Page load time: comparable to IP:port access
- Traefik routing overhead: < 50ms

### Reliability Metrics
- No 502/503 errors (Bad Gateway/Service Unavailable)
- No timeout errors
- All health checks passing
- 100% uptime during testing period

## Common Issues and Solutions

### Issue: DNS not resolving
**Solution:**
```bash
# Flush DNS cache on client
# Windows: ipconfig /flushdns
# macOS: sudo dscacheutil -flushcache
# Linux: sudo systemd-resolve --flush-caches

# Verify DNS server setting
# Ensure client is using SERVER_IP as DNS
```

### Issue: SSL certificate errors (unable to proceed)
**Solution:**
```bash
# Accept self-signed certificate in browser
# Click "Advanced" → "Proceed to site"
# Certificate warnings are expected for self-signed certs
```

### Issue: 502 Bad Gateway error
**Solution:**
```bash
# Check service is running
docker ps | grep <service>

# Check Traefik can reach service
docker exec traefik ping <service-container-name>

# Check service port matches label
docker port <service-container-name>

# Verify Traefik labels are correct
docker inspect <service> | grep -A 20 Labels
```

### Issue: Redirect loop
**Solution:**
```bash
# Check for conflicting redirect middlewares
# Verify entrypoint configuration
# Check service doesn't force its own redirects
```

## Testing Script

Create a comprehensive test script:

```bash
#!/bin/bash
# test-domain-access.sh

SERVER_IP="192.168.1.100"
SERVICES=("glance" "hortusfox" "grafana")
DOMAINS=("glance.home.local" "hortusfox.home.local" "grafana.home.local")

echo "=== Domain Access Testing ==="

# DNS Resolution Test
echo -e "\n1. Testing DNS Resolution..."
for domain in "${DOMAINS[@]}"; do
    result=$(dig @${SERVER_IP} $domain +short)
    if [ "$result" == "$SERVER_IP" ]; then
        echo "✓ $domain resolves correctly to $SERVER_IP"
    else
        echo "✗ $domain resolution failed (got: $result)"
    fi
done

# HTTP to HTTPS Redirect Test
echo -e "\n2. Testing HTTP → HTTPS Redirects..."
for domain in "${DOMAINS[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" http://$domain)
    if [ "$status" == "301" ] || [ "$status" == "302" ] || [ "$status" == "308" ]; then
        echo "✓ $domain HTTP redirects correctly (status: $status)"
    else
        echo "✗ $domain redirect failed (status: $status)"
    fi
done

# HTTPS Connectivity Test
echo -e "\n3. Testing HTTPS Connectivity..."
for domain in "${DOMAINS[@]}"; do
    status=$(curl -k -s -o /dev/null -w "%{http_code}" https://$domain)
    if [ "$status" == "200" ]; then
        echo "✓ $domain HTTPS accessible (status: 200)"
    else
        echo "✗ $domain HTTPS failed (status: $status)"
    fi
done

# Service Health Test
echo -e "\n4. Testing Service Health..."
for service in "${SERVICES[@]}"; do
    health=$(docker inspect $service | jq -r '.[0].State.Health.Status // "no-health-check"')
    echo "  $service: $health"
done

# Traefik Router Test
echo -e "\n5. Testing Traefik Routers..."
routers=$(docker exec traefik traefik healthcheck 2>&1)
echo "$routers"

echo -e "\n=== Testing Complete ==="
```

## Dependencies
- Ticket 01: Traefik deployment completed
- Ticket 02: AdGuard port migration completed
- Ticket 03: Service labels configured
- Ticket 04: DNS rewrites configured

## Risk Considerations
- Testing may reveal configuration issues requiring fixes
- Self-signed certificates require manual acceptance
- Some browsers may be more restrictive with self-signed certs

## Rollback Plan
If major issues discovered:
```bash
# Services remain accessible via IP:port
# Can remove Traefik labels and continue with old method
# DNS rewrites can be removed if needed
```

## Next Steps
After successful testing:
- Document any issues found and solutions
- Proceed to ticket 06 (n8n configuration)
- Update README with new access URLs

## Notes
- Self-signed certificate warnings are expected and normal
- First-time SSL certificate acceptance required per browser
- Testing should be done from actual client devices, not just server
- Keep IP:port access for at least 1-2 weeks during transition
