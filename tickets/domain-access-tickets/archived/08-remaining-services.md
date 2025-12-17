# Configure Remaining Services with Traefik

## Priority: 3 (Medium)
## Estimated Time: 2-3 hours
## Phase: Week 2-3 - Complete Rollout

## Description
Add Traefik labels to all remaining services (AdGuard Home, Ollama, Habitica, Prometheus, Alertmanager) to complete the domain-based access migration. This completes the rollout to all services in the stack.

## Acceptance Criteria
- [ ] AdGuard Home accessible via https://adguard.${DOMAIN}
- [ ] Ollama API accessible via https://ollama.${DOMAIN}
- [ ] Habitica accessible via https://habitica.${DOMAIN}
- [ ] Prometheus accessible via https://prometheus.${DOMAIN}
- [ ] Alertmanager accessible via https://alerts.${DOMAIN}
- [ ] All services functional via domain names
- [ ] Backward compatibility maintained (IP:port access)
- [ ] No service disruptions during migration
- [ ] All services show up in Traefik dashboard

## Services to Configure

1. **AdGuard Home** - adguard.${DOMAIN} (port 8888)
2. **Ollama** - ollama.${DOMAIN} (port 11434)
3. **Habitica** - habitica.${DOMAIN} (port 8080)
4. **Prometheus** - prometheus.${DOMAIN} (port 9090)
5. **Alertmanager** - alerts.${DOMAIN} (port 9093)

## Technical Implementation Details

### 1. AdGuard Home Configuration

**File:** `docker-compose.yml`

**Note:** AdGuard is now on port 8888 (moved in ticket 02)

```yaml
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard-home
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:53:53/tcp"
      - "${SERVER_IP}:53:53/udp"
      - "${SERVER_IP}:3000:3000/tcp"
      - "${SERVER_IP}:8888:80/tcp"  # Admin interface on 8888
    volumes:
      - ./data/adguard/work:/opt/adguardhome/work
      - ./data/adguard/conf:/opt/adguardhome/conf
    networks:
      - homeserver

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.adguard-http.rule=Host(`adguard.${DOMAIN}`)"
      - "traefik.http.routers.adguard-http.entrypoints=web"
      - "traefik.http.routers.adguard-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.adguard.rule=Host(`adguard.${DOMAIN}`)"
      - "traefik.http.routers.adguard.entrypoints=websecure"
      - "traefik.http.routers.adguard.tls=true"

      # Service - point to internal port 80 (maps to external 8888)
      - "traefik.http.services.adguard.loadbalancer.server.port=80"

      # Middleware
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
```

### 2. Ollama Configuration

**File:** `docker-compose.yml`

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:11434:11434"  # Keep for backward compatibility
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-1}
      - OLLAMA_MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS:-1}
      - OLLAMA_LOAD_TIMEOUT=${OLLAMA_LOAD_TIMEOUT:-600}
    volumes:
      - ./data/ollama:/root/.ollama
    networks:
      - homeserver

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.ollama-http.rule=Host(`ollama.${DOMAIN}`)"
      - "traefik.http.routers.ollama-http.entrypoints=web"
      - "traefik.http.routers.ollama-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.ollama.rule=Host(`ollama.${DOMAIN}`)"
      - "traefik.http.routers.ollama.entrypoints=websecure"
      - "traefik.http.routers.ollama.tls=true"

      # Service
      - "traefik.http.services.ollama.loadbalancer.server.port=11434"
```

### 3. Habitica Configuration

**File:** `docker-compose.habitica.yml`

Find the habitica web service:

```yaml
  habitica:
    image: habitica/habitica:${HABITICA_VERSION:-latest}
    container_name: habitica
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:8080:8080"  # Keep for backward compatibility
    environment:
      # ... existing environment ...
      - BASE_URL=${HABITICA_BASE_URL}  # Update this in .env to https://habitica.${DOMAIN}
      # ... rest of env vars ...
    volumes:
      # ... existing volumes ...
    networks:
      - homeserver
    depends_on:
      # ... dependencies ...

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.habitica-http.rule=Host(`habitica.${DOMAIN}`)"
      - "traefik.http.routers.habitica-http.entrypoints=web"
      - "traefik.http.routers.habitica-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.habitica.rule=Host(`habitica.${DOMAIN}`)"
      - "traefik.http.routers.habitica.entrypoints=websecure"
      - "traefik.http.routers.habitica.tls=true"

      # Service
      - "traefik.http.services.habitica.loadbalancer.server.port=8080"
```

**Also update .env:**
```bash
HABITICA_BASE_URL=https://habitica.${DOMAIN}
```

### 4. Prometheus Configuration

**File:** `docker-compose.monitoring.yml`

```yaml
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9090:9090"  # Keep for backward compatibility
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - homeserver

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.prometheus-http.rule=Host(`prometheus.${DOMAIN}`)"
      - "traefik.http.routers.prometheus-http.entrypoints=web"
      - "traefik.http.routers.prometheus-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.prometheus.rule=Host(`prometheus.${DOMAIN}`)"
      - "traefik.http.routers.prometheus.entrypoints=websecure"
      - "traefik.http.routers.prometheus.tls=true"

      # Service
      - "traefik.http.services.prometheus.loadbalancer.server.port=9090"
```

### 5. Alertmanager Configuration

**File:** `docker-compose.monitoring.yml`

```yaml
  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9093:9093"  # Keep for backward compatibility
    volumes:
      - ./monitoring/alertmanager:/etc/alertmanager
    networks:
      - homeserver

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.alertmanager-http.rule=Host(`alerts.${DOMAIN}`)"
      - "traefik.http.routers.alertmanager-http.entrypoints=web"
      - "traefik.http.routers.alertmanager-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.alertmanager.rule=Host(`alerts.${DOMAIN}`)"
      - "traefik.http.routers.alertmanager.entrypoints=websecure"
      - "traefik.http.routers.alertmanager.tls=true"

      # Service
      - "traefik.http.services.alertmanager.loadbalancer.server.port=9093"
```

## Deployment Steps

```bash
# 1. Update .env file for Habitica BASE_URL
nano .env
# Change HABITICA_BASE_URL to https://habitica.${DOMAIN}

# 2. Add labels to docker-compose.yml (adguard, ollama)
nano docker-compose.yml

# 3. Add labels to docker-compose.habitica.yml
nano docker-compose.habitica.yml

# 4. Add labels to docker-compose.monitoring.yml (prometheus, alertmanager)
nano docker-compose.monitoring.yml

# 5. Restart services with new labels (no downtime)
docker compose up -d adguard
docker compose up -d ollama

# 6. Restart Habitica
docker compose -f docker-compose.yml -f docker-compose.habitica.yml up -d habitica

# 7. Restart monitoring services
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d prometheus alertmanager

# 8. Verify all services registered with Traefik
docker logs traefik | grep -E "(adguard|ollama|habitica|prometheus|alertmanager)"

# 9. Check Traefik dashboard
curl http://localhost:8080/api/http/routers | jq
```

## Testing Checklist

### AdGuard Home Tests
```bash
# DNS resolution
nslookup adguard.${DOMAIN}

# HTTP redirect
curl -I http://adguard.${DOMAIN}

# HTTPS access
curl -Ik https://adguard.${DOMAIN}

# Functionality
- [ ] Can access admin interface
- [ ] Can login with credentials
- [ ] DNS settings visible
- [ ] Query log accessible
- [ ] Filters working
- [ ] Backward compat: http://SERVER_IP:8888
```

### Ollama API Tests
```bash
# DNS resolution
nslookup ollama.${DOMAIN}

# HTTP redirect
curl -I http://ollama.${DOMAIN}

# HTTPS access
curl -Ik https://ollama.${DOMAIN}

# API test
curl -k https://ollama.${DOMAIN}/api/version
# Expected: {"version":"..."}

# List models
curl -k https://ollama.${DOMAIN}/api/tags
# Expected: {"models":[...]}

# Test from n8n (update Ollama host if hardcoded)
- [ ] n8n AI nodes can reach Ollama
- [ ] Backward compat: http://SERVER_IP:11434
```

### Habitica Tests
```bash
# DNS resolution
nslookup habitica.${DOMAIN}

# HTTP redirect
curl -I http://habitica.${DOMAIN}

# HTTPS access
curl -Ik https://habitica.${DOMAIN}

# Functionality
- [ ] Homepage loads
- [ ] Can login
- [ ] User dashboard displays
- [ ] Tasks visible
- [ ] Habits functional
- [ ] Party/guild features work
- [ ] Backward compat: http://SERVER_IP:8080
```

### Prometheus Tests
```bash
# DNS resolution
nslookup prometheus.${DOMAIN}

# HTTP redirect
curl -I http://prometheus.${DOMAIN}

# HTTPS access
curl -Ik https://prometheus.${DOMAIN}

# API test
curl -k https://prometheus.${DOMAIN}/api/v1/status/config

# Functionality
- [ ] Web UI loads
- [ ] Targets page shows all services
- [ ] Targets are "UP"
- [ ] Can query metrics
- [ ] Graphs render correctly
- [ ] Alerts page accessible
- [ ] Backward compat: http://SERVER_IP:9090
```

### Alertmanager Tests
```bash
# DNS resolution
nslookup alerts.${DOMAIN}

# HTTP redirect
curl -I http://alerts.${DOMAIN}

# HTTPS access
curl -Ik https://alerts.${DOMAIN}

# API test
curl -k https://alerts.${DOMAIN}/api/v1/status

# Functionality
- [ ] Web UI loads
- [ ] Alerts page accessible
- [ ] Alert configuration visible
- [ ] Silences page works
- [ ] Can view active alerts
- [ ] Backward compat: http://SERVER_IP:9093
```

### Integration Tests

#### n8n → Ollama Integration
```bash
# Update n8n workflows using Ollama
# Change Ollama host from SERVER_IP:11434 to ollama.${DOMAIN}
- [ ] n8n can connect to Ollama via domain
- [ ] AI nodes execute successfully
```

#### Grafana → Prometheus Integration
```bash
# Prometheus datasource in Grafana might need update
# Check if datasource URL needs changing
- [ ] Grafana can query Prometheus data
- [ ] Dashboards load metrics correctly
```

#### Prometheus → Alertmanager Integration
```bash
# Check Prometheus alerting config
# monitoring/prometheus/prometheus.yml should have:
# alertmanagers:
#   - static_configs:
#     - targets: ['alertmanager:9093']
# (Docker network name resolution works, no change needed)
- [ ] Prometheus sends alerts to Alertmanager
- [ ] Test alert appears in Alertmanager
```

## Success Metrics
- All 5 services accessible via .${DOMAIN} domains
- 100% backward compatibility (IP:port still works)
- All service functionality intact
- No errors in service logs
- No errors in Traefik logs
- Integration between services working
- Traefik dashboard shows all routers

## Common Issues and Solutions

### Issue: AdGuard admin interface shows blank page
**Solution:**
```bash
# AdGuard may need configuration for trusted proxies
# Edit data/adguard/conf/AdGuardHome.yaml
# Add under dns section:
# trusted_proxies:
#   - 172.16.0.0/12  # Docker network range
docker compose restart adguard
```

### Issue: Ollama API returns 502 Bad Gateway
**Solution:**
```bash
# Check Ollama is running
docker ps | grep ollama

# Check Ollama logs
docker logs ollama

# Verify port in label matches container port
docker port ollama

# Test direct access
docker exec ollama curl http://localhost:11434/api/version
```

### Issue: Habitica shows "Unable to connect to server"
**Solution:**
```bash
# Check HABITICA_BASE_URL in .env matches domain
grep HABITICA_BASE_URL .env

# Restart Habitica
docker compose -f docker-compose.yml -f docker-compose.habitica.yml restart habitica

# Check MongoDB connection
docker compose -f docker-compose.yml -f docker-compose.habitica.yml logs habitica-db
```

### Issue: Prometheus targets showing as down
**Solution:**
```bash
# Targets use Docker internal network, no change needed
# If using external targets, update prometheus.yml
# Verify services are reachable from Prometheus container
docker exec prometheus wget -qO- http://node-exporter:9100/metrics
```

## Environment Variable Updates

Update `.env` file:
```bash
# Habitica
HABITICA_BASE_URL=https://habitica.${DOMAIN}

# Consider updating these for consistency (optional):
N8N_EDITOR_BASE_URL=https://n8n.${DOMAIN}
WEBHOOK_URL=https://n8n.${DOMAIN}/
```

## Dependencies
- Ticket 01: Traefik deployment completed
- Ticket 02: AdGuard moved to port 8888
- Ticket 04: DNS rewrites configured
- Tickets 05-07: Initial services tested and working

## Risk Considerations
- Multiple services updated at once - test each individually
- Integration points may need URL updates
- Brief restarts for each service (~10 seconds each)
- Monitor logs closely for any connection errors

## Rollback Plan
```bash
# Remove labels from docker-compose files
# Restart services
docker compose up -d adguard ollama
docker compose -f docker-compose.yml -f docker-compose.habitica.yml up -d habitica
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d prometheus alertmanager

# Services continue working via IP:port
```

## Next Steps
After completion:
- Proceed to ticket 09 (Update documentation)
- Monitor all services for 24-48 hours
- Consider removing direct port mappings after validation
- Update any scripts or automation using IP:port

## Notes
- Services using Docker network names for internal communication need no changes
- Only external access URLs need domain updates
- Keep port mappings for gradual migration
- Monitoring services (Prometheus, Alertmanager) use internal names for scraping
- Consider adding authentication middleware for services without built-in auth
