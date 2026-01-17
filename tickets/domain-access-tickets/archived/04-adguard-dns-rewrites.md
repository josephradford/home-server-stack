# Configure AdGuard Home DNS Rewrites

## Priority: 1 (Critical - Required for Domain Access)
## Estimated Time: 30 minutes
## Phase: Week 1 - Foundation

## Description
Configure DNS rewrites in AdGuard Home configuration file to resolve *.${DOMAIN} domains to the home server IP address. This enables clients on the local network to access services via domain names instead of IP:port combinations.

## Acceptance Criteria
- [ ] DNS rewrites added to AdGuard Home configuration file
- [ ] Wildcard rewrite (*.${DOMAIN}) configured to point to SERVER_IP
- [ ] AdGuard Home configuration reloaded without service restart
- [ ] DNS resolution tested from client device
- [ ] All planned domains resolve correctly
- [ ] No impact on existing DNS functionality

## Technical Implementation Details

### File to Modify
`data/adguard/conf/AdGuardHome.yaml`

### Current AdGuardHome.yaml Structure
The configuration file includes a `filtering` section where DNS rewrites are stored:

```yaml
# ... other configuration ...

dns:
  # ... dns settings ...

filtering:
  rewrites:
    # Existing rewrites (if any)
    - domain: example.local
      answer: 192.168.1.100
```

### DNS Rewrites to Add

**Option 1: Wildcard Rewrite (Recommended)**
```yaml
filtering:
  rewrites:
    # Wildcard for all ${DOMAIN} domains
    - domain: "*.${DOMAIN}"
      answer: "${SERVER_IP}"
```

**Option 2: Individual Domain Rewrites (More Explicit)**
```yaml
filtering:
  rewrites:
    # Reverse proxy and services
    - domain: traefik.${DOMAIN}
      answer: 192.168.1.100
    - domain: adguard.${DOMAIN}
      answer: 192.168.1.100
    - domain: n8n.${DOMAIN}
      answer: 192.168.1.100
    - domain: ollama.${DOMAIN}
      answer: 192.168.1.100
    - domain: glance.${DOMAIN}
      answer: 192.168.1.100
    - domain: hortusfox.${DOMAIN}
      answer: 192.168.1.100
    - domain: grafana.${DOMAIN}
      answer: 192.168.1.100
    - domain: prometheus.${DOMAIN}
      answer: 192.168.1.100
    - domain: alerts.${DOMAIN}
      answer: 192.168.1.100
    - domain: habitica.${DOMAIN}
      answer: 192.168.1.100
    - domain: bookwyrm.${DOMAIN}
      answer: 192.168.1.100
```

**Recommendation:** Use Option 1 (wildcard) for simplicity. New services will automatically resolve without config changes.

### Implementation Steps

```bash
# 1. Backup current AdGuard configuration
cp data/adguard/conf/AdGuardHome.yaml data/adguard/conf/AdGuardHome.yaml.backup

# 2. Edit the configuration file
nano data/adguard/conf/AdGuardHome.yaml

# 3. Locate the filtering section, add rewrites under it
# If filtering section doesn't exist, create it:
# filtering:
#   rewrites:
#     - domain: "*.${DOMAIN}"
#       answer: "192.168.1.100"

# 4. Validate YAML syntax
docker run --rm -v $(pwd)/data/adguard/conf:/config mikefarah/yq eval data/adguard/conf/AdGuardHome.yaml > /dev/null

# 5. Option A: Reload AdGuard configuration without restart
# AdGuard v0.107.0+ supports config reload via API
curl -X POST http://${SERVER_IP}:8888/control/reload \
  -H "Content-Type: application/json" \
  --user "admin:your_password"

# 5. Option B: Restart AdGuard container (if reload not available)
docker compose restart adguard

# Wait for AdGuard to start
sleep 5

# 6. Verify AdGuard is running
docker ps | grep adguard
```

### Alternative: Using AdGuard CLI (if available)
```bash
# Reload configuration
docker exec adguard-home /opt/adguardhome/AdGuardHome --config /opt/adguardhome/conf/AdGuardHome.yaml --check-config
```

### Testing Commands

```bash
# From a client device on the network that uses AdGuard as DNS:

# Test wildcard domain resolution
nslookup glance.${DOMAIN}
nslookup grafana.${DOMAIN}
nslookup n8n.${DOMAIN}

# Expected output for each:
# Server:  192.168.1.100
# Address: 192.168.1.100#53
#
# Name:    glance.${DOMAIN}
# Address: 192.168.1.100

# Test from the server itself
dig @${SERVER_IP} glance.${DOMAIN} +short
# Should return: 192.168.1.100

# Test non-${DOMAIN} domains still work (internet DNS)
nslookup google.com
```

### Testing Checklist
- [ ] `nslookup glance.${DOMAIN}` resolves to SERVER_IP
- [ ] `nslookup hortusfox.${DOMAIN}` resolves to SERVER_IP
- [ ] `nslookup grafana.${DOMAIN}` resolves to SERVER_IP
- [ ] `nslookup n8n.${DOMAIN}` resolves to SERVER_IP
- [ ] `nslookup bookwyrm.${DOMAIN}` resolves to SERVER_IP
- [ ] `nslookup traefik.${DOMAIN}` resolves to SERVER_IP
- [ ] Regular internet DNS still works (google.com, etc.)
- [ ] No errors in AdGuard logs

### Example AdGuardHome.yaml Section
```yaml
# AdGuard Home Configuration
# ...

dns:
  bind_hosts:
    - 0.0.0.0
  port: 53
  # ... other dns settings ...

filtering:
  enabled: true
  rewrites:
    # Domain-based access for home server services
    - domain: "*.${DOMAIN}"
      answer: "192.168.1.100"
  # ... other filtering settings ...
```

## Success Metrics
- All *.${DOMAIN} domains resolve to SERVER_IP
- DNS resolution time < 50ms for local domains
- No impact on external DNS queries
- No errors in AdGuard logs
- Configuration persists after AdGuard restart

## Dependencies
- AdGuard Home deployed and running
- SERVER_IP defined and known
- Client devices configured to use AdGuard as DNS server

## Risk Considerations
- **Configuration syntax errors** could break AdGuard - Always backup first
- Brief DNS interruption if restart required (~5-10 seconds)
- Wildcard might conflict with future domains - unlikely for .local TLD
- Ensure .local TLD doesn't conflict with mDNS/Bonjour (rare)

## Rollback Plan
```bash
# Restore backup configuration
cp data/adguard/conf/AdGuardHome.yaml.backup data/adguard/conf/AdGuardHome.yaml

# Restart AdGuard
docker compose restart adguard

# Verify
docker logs adguard-home | tail -20
```

## Next Steps
After completion:
- Test DNS resolution from multiple client devices
- Proceed to ticket 03 or 05 (Service configuration and testing)
- Update documentation with new domain names

## Notes
- AdGuard Home supports both wildcards and specific domain rewrites
- Wildcard rewrite is more flexible for adding new services
- The `.local` TLD is reserved for local network use (RFC 6762)
- AdGuard v0.107.0+ supports configuration reload without restart
- For older versions, container restart is required
- DNS changes take effect immediately after reload/restart
- Clients with DNS caching may need cache flush: `ipconfig /flushdns` (Windows) or `sudo dscacheutil -flushcache` (macOS)
