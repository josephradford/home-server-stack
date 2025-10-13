# Add Traefik Labels to Initial Services

## Priority: 2 (High)
## Estimated Time: 1-2 hours
## Phase: Week 1 - Initial Rollout

## Description
Configure Traefik labels for 3 straightforward services to validate the domain-based routing setup. Starting with simpler services (Glance, HortusFox, Grafana) before moving to complex ones (n8n, Bookwyrm).

## Acceptance Criteria
- [ ] Traefik labels added to Glance service
- [ ] Traefik labels added to HortusFox service
- [ ] Traefik labels added to Grafana service
- [ ] All 3 services accessible via .home.local domains
- [ ] HTTPS working (self-signed certificates accepted)
- [ ] Original IP:port access still functional (backward compatibility)
- [ ] No service disruption during label addition

## Technical Implementation Details

### Services to Configure
1. **Glance** (glance.home.local) - Simple dashboard, no auth required by Traefik
2. **HortusFox** (hortusfox.home.local) - Simple web app with own auth
3. **Grafana** (grafana.home.local) - Monitoring dashboard with own auth

### Files to Modify
1. `docker-compose.yml` - Add labels to glance service
2. `docker-compose.monitoring.yml` - Add labels to grafana service
3. `docker-compose.yml` - Add labels to hortusfox service

### Glance Configuration
Add to glance service in `docker-compose.yml`:

```yaml
  glance:
    image: glanceapp/glance:${GLANCE_VERSION:-latest}
    container_name: glance
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:${GLANCE_PORT:-8282}:8080"  # Keep for backward compatibility
    environment:
      - TZ=${TIMEZONE}
    volumes:
      - ./data/glance:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - homeserver

    # ADD THESE LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router (redirect to HTTPS)
      - "traefik.http.routers.glance-http.rule=Host(`glance.home.local`)"
      - "traefik.http.routers.glance-http.entrypoints=web"
      - "traefik.http.routers.glance-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.glance.rule=Host(`glance.home.local`)"
      - "traefik.http.routers.glance.entrypoints=websecure"
      - "traefik.http.routers.glance.tls=true"

      # Service
      - "traefik.http.services.glance.loadbalancer.server.port=8080"

      # Middleware for redirect
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"

    healthcheck:
      test: ["CMD-SHELL", "wget --quiet --tries=1 --spider http://localhost:8080 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### HortusFox Configuration
Add to hortusfox service in `docker-compose.yml`:

```yaml
  hortusfox:
    image: ghcr.io/danielbrendel/hortusfox-web:${HORTUSFOX_VERSION:-latest}
    container_name: hortusfox
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:8181:80"  # Keep for backward compatibility
    environment:
      - APP_ADMIN_EMAIL=${HORTUSFOX_ADMIN_EMAIL}
      - APP_ADMIN_PASSWORD=${HORTUSFOX_ADMIN_PASSWORD}
      - APP_TIMEZONE=${TIMEZONE}
      - DB_HOST=hortusfox-db
      - DB_PORT=3306
      - DB_DATABASE=${HORTUSFOX_DB_NAME:-hortusfox}
      - DB_USERNAME=${HORTUSFOX_DB_USER:-hortusfox}
      - DB_PASSWORD=${HORTUSFOX_DB_PASSWORD}
      - DB_CHARSET=utf8mb4
    volumes:
      - ./data/hortusfox/images:/var/www/html/public/img
      - ./data/hortusfox/logs:/var/www/html/app/logs
      - ./data/hortusfox/backup:/var/www/html/public/backup
      - ./data/hortusfox/themes:/var/www/html/public/themes
      - ./data/hortusfox/migrate:/var/www/html/app/migrations
    networks:
      - homeserver
    depends_on:
      hortusfox-db:
        condition: service_healthy

    # ADD THESE LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.hortusfox-http.rule=Host(`hortusfox.home.local`)"
      - "traefik.http.routers.hortusfox-http.entrypoints=web"
      - "traefik.http.routers.hortusfox-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.hortusfox.rule=Host(`hortusfox.home.local`)"
      - "traefik.http.routers.hortusfox.entrypoints=websecure"
      - "traefik.http.routers.hortusfox.tls=true"

      # Service
      - "traefik.http.services.hortusfox.loadbalancer.server.port=80"

    healthcheck:
      test: ["CMD-SHELL", "wget --quiet --tries=1 --spider http://localhost:80 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### Grafana Configuration
Add to grafana service in `docker-compose.monitoring.yml`:

```yaml
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:3001:3000"  # Keep for backward compatibility
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    networks:
      - homeserver

    # ADD THESE LABELS:
    labels:
      - "traefik.enable=true"

      # HTTP Router
      - "traefik.http.routers.grafana-http.rule=Host(`grafana.home.local`)"
      - "traefik.http.routers.grafana-http.entrypoints=web"
      - "traefik.http.routers.grafana-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.grafana.rule=Host(`grafana.home.local`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.tls=true"

      # Service
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"
```

### Deployment Steps
```bash
# 1. Add labels to docker-compose.yml (glance, hortusfox)
nano docker-compose.yml

# 2. Add labels to docker-compose.monitoring.yml (grafana)
nano docker-compose.monitoring.yml

# 3. Recreate services with new labels (no downtime)
docker compose up -d glance
docker compose up -d hortusfox
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d grafana

# 4. Verify Traefik discovered the services
docker logs traefik | grep -E "(glance|hortusfox|grafana)"

# 5. Check Traefik dashboard for new routers
curl http://localhost:8080/api/http/routers | jq
```

### Testing Commands
```bash
# Test from server (replace SERVER_IP with actual IP)
SERVER_IP=192.168.1.100

# Test Glance
curl -k https://glance.home.local
curl -I http://${SERVER_IP}:8282  # Verify old access still works

# Test HortusFox
curl -k https://hortusfox.home.local
curl -I http://${SERVER_IP}:8181  # Verify old access still works

# Test Grafana
curl -k https://grafana.home.local
curl -I http://${SERVER_IP}:3001  # Verify old access still works

# Check Traefik routers
docker exec traefik traefik healthcheck
```

### Testing Checklist
- [ ] Glance accessible via https://glance.home.local (accept cert warning)
- [ ] Glance accessible via http://glance.home.local (redirects to HTTPS)
- [ ] Glance still accessible via http://SERVER_IP:8282
- [ ] HortusFox accessible via https://hortusfox.home.local
- [ ] HortusFox still accessible via http://SERVER_IP:8181
- [ ] Grafana accessible via https://grafana.home.local
- [ ] Grafana still accessible via http://SERVER_IP:3001
- [ ] All services functional (can login, view data, etc.)
- [ ] Traefik dashboard shows 3 new routers

## Success Metrics
- 3 services accessible via .home.local domains
- HTTPS working with self-signed certificates
- HTTP automatically redirects to HTTPS
- Backward compatibility maintained (IP:port still works)
- No errors in service logs
- Traefik access logs showing successful routing

## Dependencies
- Ticket 01: Traefik deployment completed
- Ticket 02: AdGuard moved to port 8888
- Ticket 04: DNS rewrites configured in AdGuard

## Risk Considerations
- Minimal risk - labels don't affect existing functionality
- Services remain accessible via IP:port during transition
- Brief container restart when applying labels
- Self-signed certificate warnings in browsers

## Rollback Plan
```bash
# Remove labels from docker-compose files
# Restart services without labels
docker compose up -d glance hortusfox
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d grafana

# Services continue working via IP:port
```

## Next Steps
After completion:
- Proceed to ticket 05 (Test and verify 3 services)
- Then ticket 06 (Configure n8n with Traefik)

## Notes
- Labels are non-destructive - they only add new access methods
- Keep port mappings for backward compatibility initially
- Can remove port mappings later once domain access is verified
- Self-signed cert warnings are expected and normal
