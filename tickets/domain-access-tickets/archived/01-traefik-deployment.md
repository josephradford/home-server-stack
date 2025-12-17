# Deploy Traefik Reverse Proxy

## Priority: 1 (Critical - Foundation)
## Estimated Time: 2-3 hours
## Phase: Week 1 - Foundation

## Description
Deploy Traefik as the reverse proxy to enable domain-based access to all services. Traefik will handle routing based on hostnames, automatic service discovery via Docker labels, and SSL/TLS termination.

## Acceptance Criteria
- [ ] Traefik service added to docker-compose.yml
- [ ] Traefik configured with web (80) and websecure (443) entrypoints
- [ ] Docker provider enabled for automatic service discovery
- [ ] Traefik dashboard accessible at traefik.${DOMAIN}
- [ ] SSL/TLS configured with automatic certificate generation
- [ ] HTTP to HTTPS redirect enabled
- [ ] Traefik container running and healthy
- [ ] Access logs enabled for monitoring

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Add Traefik service
2. `config/traefik/traefik.yml` - Static configuration (optional)
3. `config/traefik/dynamic/` - Dynamic configuration directory
4. `.env` - Add Traefik-related environment variables (if needed)

### Traefik Service Configuration
Add to `docker-compose.yml`:

```yaml
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    command:
      # API and Dashboard
      - "--api.dashboard=true"
      - "--api.insecure=false"

      # Docker provider
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=homeserver"

      # Entrypoints
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"

      # HTTP to HTTPS redirect
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.web.http.redirections.entrypoint.scheme=https"

      # TLS
      - "--entrypoints.websecure.http.tls=true"

      # Logging
      - "--accesslog=true"
      - "--accesslog.filepath=/var/log/traefik/access.log"
      - "--log.level=INFO"

    ports:
      - "${SERVER_IP}:80:80"
      - "${SERVER_IP}:443:443"

    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./data/traefik/certs:/certs
      - ./data/traefik/logs:/var/log/traefik
      - ./config/traefik:/etc/traefik:ro

    networks:
      - homeserver

    labels:
      # Enable Traefik for the dashboard
      - "traefik.enable=true"

      # Dashboard router
      - "traefik.http.routers.dashboard.rule=Host(`traefik.${DOMAIN}`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls=true"
      - "traefik.http.routers.dashboard.service=api@internal"

      # Dashboard middleware (basic auth recommended)
      - "traefik.http.middlewares.dashboard-auth.basicauth.users=admin:$$apr1$$..." # Generate with htpasswd
      - "traefik.http.routers.dashboard.middlewares=dashboard-auth"

    healthcheck:
      test: ["CMD", "traefik", "healthcheck", "--ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Generate Basic Auth Password
```bash
# Install htpasswd if needed
sudo apt-get install apache2-utils

# Generate password (replace 'admin' and 'your_password')
htpasswd -nb admin your_password

# Output format: admin:$apr1$...
# Use this in the basicauth.users label (escape $ as $$)
```

### Testing Commands
```bash
# Start Traefik
docker compose up -d traefik

# Check Traefik logs
docker logs traefik

# Verify Traefik is running
docker ps | grep traefik

# Check Traefik health
docker inspect traefik | grep -A 10 Health

# Test Traefik API (from server)
curl http://localhost:80/api/http/routers

# Add DNS rewrite in AdGuard first, then test dashboard
curl -k https://traefik.${DOMAIN}
```

### Directory Structure to Create
```
data/
  traefik/
    certs/          # SSL certificates storage
    logs/           # Access logs
config/
  traefik/
    dynamic/        # Dynamic configuration files (optional)
```

## Success Metrics
- Traefik container running and passing health checks
- Traefik dashboard accessible at https://traefik.${DOMAIN} (after DNS setup)
- No port conflicts with existing services
- Docker provider discovering containers
- Access logs being written to data/traefik/logs/

## Dependencies
- Docker and Docker Compose installed
- SERVER_IP defined in .env
- Port 80 and 443 available (will need to move AdGuard first - see ticket 02)
- homeserver network exists

## Risk Considerations
- **Port 80 conflict with AdGuard Home** - Must complete ticket 02 first
- Resource usage: ~50-100MB RAM
- Initial SSL certificate warnings for self-signed certs
- Ensure Docker socket permissions are secure (read-only mount)

## Rollback Plan
```bash
# Stop Traefik
docker compose stop traefik

# Remove Traefik container
docker compose rm -f traefik

# Services remain accessible via original IP:port
```

## Next Steps
After completion:
- Proceed to ticket 02 (Move AdGuard to avoid port conflict)
- Then ticket 03 (Configure initial services with Traefik labels)

## Notes
- Traefik v3.0 is used (latest stable as of 2025)
- Self-signed certificates will be generated automatically
- For production, consider using Let's Encrypt DNS challenge
- Dashboard authentication is important for security
