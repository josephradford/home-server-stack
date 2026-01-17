# Configure n8n with Traefik

## Priority: 2 (High)
## Estimated Time: 1.5-2 hours
## Phase: Week 2 - Complex Services

## Description
Migrate n8n from its built-in SSL configuration to Traefik-managed routing. This requires updating n8n's environment variables, disabling built-in SSL, configuring Traefik labels, and updating webhook URLs.

## Acceptance Criteria
- [ ] n8n accessible via https://n8n.${DOMAIN}
- [ ] Built-in n8n SSL disabled (Traefik handles SSL)
- [ ] n8n running in HTTP mode internally
- [ ] Traefik labels configured for n8n service
- [ ] Webhook URLs updated to use new domain
- [ ] n8n editor accessible and functional
- [ ] Existing workflows continue working
- [ ] External webhooks still functional
- [ ] No errors in n8n logs

## Technical Implementation Details

### Current n8n Configuration
n8n currently has built-in SSL with self-signed certificates:
- Accessible at: `https://SERVER_IP:5678`
- Uses `N8N_PROTOCOL=https`
- Has `N8N_SSL_KEY` and `N8N_SSL_CERT` configured
- Direct port exposure on 5678

### Target Configuration
After migration:
- Accessible at: `https://n8n.${DOMAIN}`
- n8n runs in HTTP mode internally
- Traefik handles SSL termination
- No direct port exposure needed (optional: keep for backward compatibility)

### Files to Modify
1. `docker-compose.yml` - Update n8n service configuration and labels
2. `.env` - Update n8n environment variables

### Step 1: Update Environment Variables (.env)

**Current values:**
```bash
N8N_PROTOCOL=https
N8N_SSL_KEY=/ssl/server.key
N8N_SSL_CERT=/ssl/server.crt
N8N_EDITOR_BASE_URL=https://your-domain:5678
WEBHOOK_URL=https://${SERVER_IP}:5678/
```

**New values:**
```bash
# Change protocol to http (Traefik handles HTTPS)
N8N_PROTOCOL=http

# Remove or comment out SSL cert paths (not needed)
# N8N_SSL_KEY=/ssl/server.key
# N8N_SSL_CERT=/ssl/server.crt

# Update to new domain-based URLs
N8N_EDITOR_BASE_URL=https://n8n.${DOMAIN}
WEBHOOK_URL=https://n8n.${DOMAIN}/

# Keep other settings unchanged
N8N_USER=admin
N8N_PASSWORD=your_secure_password_here
N8N_SECURE_COOKIE=true
# ... rest of n8n settings ...
```

### Step 2: Update docker-compose.yml

**Current configuration:**
```yaml
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    user: "1000:1000"
    ports:
      - "${SERVER_IP}:5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=${SERVER_IP}
      - N8N_PORT=5678
      - N8N_PROTOCOL=${N8N_PROTOCOL}
      - N8N_SSL_KEY=${N8N_SSL_KEY}
      - N8N_SSL_CERT=${N8N_SSL_CERT}
      - WEBHOOK_URL=https://${SERVER_IP}:5678/
      - N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL}
      - GENERIC_TIMEZONE=${TIMEZONE}
      - N8N_SECURE_COOKIE=${N8N_SECURE_COOKIE}
      # ... other settings ...
    volumes:
      - ./data/n8n:/home/node/.n8n
      - ./ssl:/ssl:ro
    networks:
      - homeserver
    depends_on:
      - ollama
      - n8n-init
```

**Updated configuration:**
```yaml
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    user: "1000:1000"
    ports:
      # OPTIONAL: Keep for backward compatibility during transition
      - "${SERVER_IP}:5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}

      # Changed: Use n8n container name instead of SERVER_IP for internal routing
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678

      # Changed: Protocol is HTTP internally, Traefik handles HTTPS
      - N8N_PROTOCOL=${N8N_PROTOCOL}

      # Removed: SSL cert paths (Traefik handles SSL)
      # - N8N_SSL_KEY=${N8N_SSL_KEY}
      # - N8N_SSL_CERT=${N8N_SSL_CERT}

      # Changed: Use new domain-based URLs from .env
      - WEBHOOK_URL=${WEBHOOK_URL}
      - N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL}

      - GENERIC_TIMEZONE=${TIMEZONE}
      - N8N_SECURE_COOKIE=${N8N_SECURE_COOKIE}
      - N8N_RUNNERS_TASK_TIMEOUT=${N8N_RUNNERS_TASK_TIMEOUT}
      - EXECUTIONS_TIMEOUT=${EXECUTIONS_TIMEOUT}
      - EXECUTIONS_TIMEOUT_MAX=${EXECUTIONS_TIMEOUT_MAX}

    volumes:
      - ./data/n8n:/home/node/.n8n
      # Removed: SSL volume mount (no longer needed)
      # - ./ssl:/ssl:ro
    networks:
      - homeserver
    depends_on:
      - ollama
      - n8n-init

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router (redirect to HTTPS)
      - "traefik.http.routers.n8n-http.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n-http.entrypoints=web"
      - "traefik.http.routers.n8n-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls=true"

      # Service configuration
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
      - "traefik.http.services.n8n.loadbalancer.server.scheme=http"

      # Middleware for HTTPS redirect
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
```

### Step 3: Migration Procedure

```bash
# 1. Backup current configuration
cp .env .env.backup
cp docker-compose.yml docker-compose.yml.backup

# 2. Update .env file
nano .env
# Update the variables as shown above

# 3. Update docker-compose.yml
nano docker-compose.yml
# Add Traefik labels and update environment section

# 4. Stop n8n container
docker compose stop n8n

# 5. Start n8n with new configuration
docker compose up -d n8n

# 6. Check n8n logs for any errors
docker logs n8n --tail 50

# 7. Verify n8n is running
docker ps | grep n8n
```

### Testing Commands

```bash
# Test DNS resolution
nslookup n8n.${DOMAIN}
# Expected: resolves to SERVER_IP

# Test HTTP redirect
curl -I http://n8n.${DOMAIN}
# Expected: 301/302 redirect to https://n8n.${DOMAIN}

# Test HTTPS access (ignore cert warning)
curl -Ik https://n8n.${DOMAIN}
# Expected: 200 OK

# Test n8n API
curl -Ik https://n8n.${DOMAIN}/healthz
# Expected: 200 OK, {"status":"ok"}

# Test basic auth
curl -Ik -u admin:your_password https://n8n.${DOMAIN}/
# Expected: 200 OK

# Check Traefik logs
docker logs traefik | grep n8n

# Check n8n logs
docker logs n8n | grep -i error
```

### Testing Checklist

#### Basic Access Tests
- [ ] DNS resolves n8n.${DOMAIN} to SERVER_IP
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads with self-signed cert
- [ ] n8n editor loads at https://n8n.${DOMAIN}
- [ ] Basic auth prompts for credentials
- [ ] Login works with N8N_USER and N8N_PASSWORD
- [ ] Backward compatibility: https://SERVER_IP:5678 still works (if port kept)

#### Functionality Tests
- [ ] n8n editor interface loads completely
- [ ] Existing workflows visible in workflow list
- [ ] Can open and view workflow details
- [ ] Can create new workflow
- [ ] Can execute test workflow
- [ ] Workflow execution history accessible
- [ ] Settings page accessible

#### Webhook Tests
- [ ] Webhook URLs show new domain (https://n8n.${DOMAIN}/webhook/...)
- [ ] Test webhook node with new URL
- [ ] Webhook receives POST request correctly
- [ ] Webhook execution appears in logs
- [ ] Production webhook URLs work

Example test workflow:
```javascript
// Create simple webhook workflow:
// 1. Add Webhook node (GET method, path: /test)
// 2. Add Set node to return data
// 3. Activate workflow
// 4. Test: curl https://n8n.${DOMAIN}/webhook/test
// Expected: Returns data from Set node
```

#### Integration Tests
- [ ] Ollama integration still works (AI nodes)
- [ ] HTTP Request nodes work
- [ ] External API integrations functional
- [ ] Scheduled workflows trigger correctly
- [ ] Manual workflow execution works

#### Log and Monitoring Tests
```bash
# Check for SSL/TLS errors
docker logs n8n | grep -i ssl
# Expected: No SSL-related errors

# Check for connection errors
docker logs n8n | grep -i error
# Expected: No connection errors

# Check for webhook errors
docker logs n8n | grep -i webhook
# Expected: Webhook registration successful

# Verify n8n health
curl https://n8n.${DOMAIN}/healthz
# Expected: {"status":"ok"}
```

## Success Metrics
- n8n accessible via https://n8n.${DOMAIN}
- All existing workflows continue working
- Webhook URLs updated to new domain
- No SSL/TLS errors in logs
- Login and authentication working
- Editor fully functional
- Workflow execution successful
- Response time comparable to before

## Common Issues and Solutions

### Issue: n8n shows "Cannot connect to server"
**Solution:**
```bash
# Check n8n is running
docker ps | grep n8n

# Check n8n logs
docker logs n8n --tail 100

# Verify N8N_PROTOCOL is set to http in .env
grep N8N_PROTOCOL .env

# Restart n8n
docker compose restart n8n
```

### Issue: Webhooks return 404
**Solution:**
```bash
# Verify WEBHOOK_URL is correct in .env
grep WEBHOOK_URL .env
# Should be: WEBHOOK_URL=https://n8n.${DOMAIN}/

# Restart n8n to apply new webhook URL
docker compose restart n8n

# Re-activate workflows to register webhooks
# In n8n editor: Deactivate then Activate each workflow
```

### Issue: "Mixed content" warnings
**Solution:**
```bash
# Ensure N8N_PROTOCOL=http (not https) in .env
# Traefik handles HTTPS externally
# n8n runs HTTP internally

# Ensure N8N_SECURE_COOKIE=true is set
# This allows cookies over HTTPS even though n8n runs HTTP internally
```

### Issue: External webhooks not accessible
**Solution:**
```bash
# If webhooks need to be accessible from internet:
# 1. Ensure firewall/router port forwarding is configured
# 2. Update WEBHOOK_URL to use public domain/IP
# 3. Consider separate webhook entrypoint if needed

# For local-only webhooks, current setup is fine
```

## Dependencies
- Ticket 01: Traefik deployment completed
- Ticket 04: DNS rewrites configured
- Ticket 05: Initial services tested successfully

## Risk Considerations
- n8n is a critical service for workflows - test thoroughly
- Webhook URL changes may require re-activating workflows
- External integrations calling webhooks need URL updates
- Brief downtime during container restart (~10-15 seconds)
- Backup workflows before making changes

## Rollback Plan
```bash
# Restore original configuration
cp .env.backup .env
cp docker-compose.yml.backup docker-compose.yml

# Restart n8n
docker compose up -d n8n

# Verify
curl -k https://192.168.1.100:5678
```

## Next Steps
After completion:
- Update any external services calling n8n webhooks
- Re-activate workflows to register new webhook URLs
- Proceed to ticket 07 (Bookwyrm configuration)
- Document webhook URL migration in runbook

## Notes
- n8n can run in HTTP mode with Traefik handling HTTPS (recommended)
- N8N_SECURE_COOKIE=true ensures cookies work over HTTPS
- Keep SSL volume mount if you want fallback option
- Consider creating backup of n8n data before migration: `cp -r data/n8n data/n8n.backup`
- Webhook URLs in workflows will need to be updated if hardcoded
- External webhook consumers need URL updates if applicable
