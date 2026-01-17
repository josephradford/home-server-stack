# Configuration Guide

Detailed configuration options for all services in the Home Server Stack.

## Environment Variables

All configuration is managed through `.env` file. See `.env.example` for all available options.

### Core Configuration

```bash
# Server Settings
SERVER_IP=192.168.1.100        # Your server's static IP
TIMEZONE=UTC                    # Your timezone (e.g., America/New_York)

# n8n Configuration
N8N_USER=admin                          # n8n username
N8N_PASSWORD=your_secure_password      # n8n password (change this!)
N8N_EDITOR_BASE_URL=https://your-domain:5678  # External URL
N8N_PROTOCOL=https                      # http or https
N8N_SSL_KEY=/ssl/server.key            # SSL key path
N8N_SSL_CERT=/ssl/server.crt           # SSL cert path
N8N_SECURE_COOKIE=true                 # Secure cookie flag


# WireGuard VPN Configuration
WIREGUARD_SERVERURL=your-public-ip-or-domain.com
WIREGUARD_PORT=51820
WIREGUARD_PEERS=5              # Number of client configs to generate
WIREGUARD_SUBNET=10.13.13.0    # VPN subnet
WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24  # Routed traffic

# Monitoring (Optional)
GRAFANA_PASSWORD=your_secure_grafana_password
```

## Service-Specific Configuration

### AdGuard Home

Configured via web UI at `http://SERVER_IP:80`.

**Recommended Settings:**

**DNS Settings:**
- Upstream DNS servers: `1.1.1.1`, `8.8.8.8`, `9.9.9.9`
- Enable parallel queries
- Enable DNSSEC

**Filter Settings:**
- Enable AdGuard DNS filter
- Enable default blocklists
- Custom rules: Add in Settings > DNS blocklists > Add blocklist

**Query Log:**
- Log retention: 7-30 days
- Location: `/opt/adguardhome/work/data/querylog.json`

**Advanced:**
- Rate limit: 20 queries/second per client
- EDNS Client Subnet: Enable for better CDN routing

### n8n

Configuration via environment variables in `.env`.

**Authentication:**
- Basic auth (default): Username + password
- For OAuth/LDAP: See https://docs.n8n.io/hosting/authentication/

**Execution Settings:**
```bash
N8N_RUNNERS_ENABLED=true              # Enable task runners
N8N_BLOCK_ENV_ACCESS_IN_NODE=false    # Allow env vars in workflows
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
N8N_RUNNERS_TASK_TIMEOUT=1800         # 30 minutes
EXECUTIONS_TIMEOUT=1800               # 30 minutes
EXECUTIONS_TIMEOUT_MAX=3600           # 1 hour max
```

**Database:**
- Default: SQLite (`/home/node/.n8n/database.sqlite`)
- For PostgreSQL/MySQL: See https://docs.n8n.io/hosting/configuration/configuration-methods/

**Webhooks:**
- Webhook URL: `${N8N_EDITOR_BASE_URL}/webhook/`
- Test webhooks: `${N8N_EDITOR_BASE_URL}/webhook-test/`

### WireGuard

Configuration via environment variables and auto-generated configs.

**Basic Settings:**
```bash
WIREGUARD_SERVERURL=your-domain.com    # Public IP or domain
WIREGUARD_PORT=51820                    # UDP port (forward on router)
WIREGUARD_PEERS=5                       # Number of clients
WIREGUARD_SUBNET=10.13.13.0            # VPN subnet
```

**Allowed IPs:**
```bash
# Full tunnel (all traffic through VPN)
WIREGUARD_ALLOWEDIPS=0.0.0.0/0

# Split tunnel (only home network)
WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24
```

**Peer Management:**
```bash
# View peer configs
docker exec wireguard ls /config/peer*

# Show QR code for peer 1
docker exec wireguard /app/show-peer 1

# Get config file
docker exec wireguard cat /config/peer1/peer1.conf
```

## Traefik Reverse Proxy Configuration

### Overview

Traefik provides domain-based routing for all services using Docker labels for automatic service discovery.

### Configuration Files

- **docker-compose.yml** - Contains Traefik service definition and labels for core services
- **docker-compose.monitoring.yml** - Contains labels for monitoring services

### Adding New Services

To add a new service with domain access:

1. Add service to docker-compose.yml
2. Connect to `homeserver` network
3. Add Traefik labels:

```yaml
services:
  myservice:
    image: myservice:latest
    container_name: myservice
    networks:
      - homeserver
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myservice.rule=Host(`myservice.${DOMAIN}`)"
      - "traefik.http.routers.myservice.entrypoints=websecure"
      - "traefik.http.routers.myservice.tls=true"
      - "traefik.http.services.myservice.loadbalancer.server.port=8080"  # Internal port
```

4. Add DNS rewrite to AdGuard (already covered by wildcard `*.${DOMAIN}`)
5. Deploy: `docker compose up -d myservice`

### Traefik Dashboard

Access Traefik's dashboard at `https://traefik.${DOMAIN}`

**Login credentials:**
- Username: `admin` (fixed)
- Password: Set via `TRAEFIK_PASSWORD` in `.env`

**Setup:**
1. Add `TRAEFIK_PASSWORD=your_secure_password` to `.env`
2. Run `make traefik-password` to generate the hashed password
3. Traefik will automatically restart with the new credentials

**Changing password:**
```bash
# Edit .env and change TRAEFIK_PASSWORD
nano .env

# Regenerate hashed password and restart Traefik
make traefik-password
```

**Note:** The password is hashed using htpasswd (bcrypt) and stored as `TRAEFIK_DASHBOARD_USERS` in `.env`. Don't edit this variable manually - always use `make traefik-password` to regenerate it.

The dashboard shows:
- Active routers and their rules
- Connected services and health
- Middleware configuration
- TLS certificate status
- Access logs

### SSL/TLS Configuration

By default, Traefik generates self-signed certificates for all services (browser warnings expected).

**Certificate storage:**
`data/traefik/certs/`

**For trusted Let's Encrypt certificates:**
See the [SSL Certificate Setup](#ssl-certificate-setup) section below for complete instructions using `make ssl-setup`.

### Security Middleware

The stack includes pre-configured security middleware for protecting services.

#### Built-in Middleware Chains

**admin-secure** - For admin interfaces (applied to all admin services):
```yaml
# Combines: IP whitelist + security headers + rate limiting
- "traefik.http.routers.myservice.middlewares=admin-secure"
```

**Components:**
- IP Whitelist: Only 192.168.0.0/16, 172.16.0.0/12, 10.0.0.0/8 (local + VPN)
- Security Headers: HSTS, XSS protection, frame deny, content-type nosniff
- Rate Limiting: 10 requests/min (burst 5)

**Services using admin-secure:**
- n8n (editor/UI)
- AdGuard Home
- Grafana
- Prometheus
- Alertmanager
- Traefik Dashboard (with basic auth)

**webhook-secure** - For public webhook endpoints (ready for future use):
```yaml
# Combines: Security headers + generous rate limiting
- "traefik.http.routers.webhook.middlewares=webhook-secure"
```

**Components:**
- Security Headers: Same as admin-secure
- Rate Limiting: 100 requests/min (burst 50)
- No IP restrictions (public access allowed)

#### Custom Middleware Examples

**Basic Auth:**
```yaml
- "traefik.http.middlewares.myauth.basicauth.users=admin:$$apr1$$..."
- "traefik.http.routers.myservice.middlewares=myauth"
```

**Custom Rate Limiting:**
```yaml
- "traefik.http.middlewares.custom-limit.ratelimit.average=50"
- "traefik.http.middlewares.custom-limit.ratelimit.period=1m"
- "traefik.http.middlewares.custom-limit.ratelimit.burst=10"
- "traefik.http.routers.myservice.middlewares=custom-limit"
```

**Custom IP Whitelist:**
```yaml
- "traefik.http.middlewares.custom-whitelist.ipwhitelist.sourcerange=192.168.1.0/24,10.0.0.0/8"
- "traefik.http.routers.myservice.middlewares=custom-whitelist"
```

**Combining Multiple Middleware:**
```yaml
# Create a chain
- "traefik.http.middlewares.my-chain.chain.middlewares=myauth,custom-limit,security-headers"
- "traefik.http.routers.myservice.middlewares=my-chain"
```

**Note:** All middleware definitions are in `docker-compose.yml` under the Traefik service labels.

### Monitoring Stack (Optional)

#### Grafana

Access at `http://SERVER_IP:3001`

**Configuration:**
- Admin password: Set via `GRAFANA_PASSWORD` in `.env`
- Data source: Prometheus (auto-configured)
- Dashboards: Pre-loaded from `monitoring/grafana/dashboards/`

**Customization:**
- Edit `monitoring/grafana/grafana.ini`
- Add custom dashboards in `monitoring/grafana/dashboards/`

#### Prometheus

Access at `http://SERVER_IP:9090`

**Configuration:**
- Main config: `monitoring/prometheus/prometheus.yml`
- Alert rules: `monitoring/prometheus/alert_rules.yml`
- Retention: 30 days (configurable)

**Add Scrape Targets:**
Edit `monitoring/prometheus/prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'my-service'
    static_configs:
      - targets: ['my-service:9090']
```

#### Alertmanager

Access at `http://SERVER_IP:9093`

**Configuration:**
- Config: `monitoring/alertmanager/alertmanager.yml`
- Default: Webhook to `http://127.0.0.1:5001/`

**Add Email Alerts:**
Edit `monitoring/alertmanager/alertmanager.yml`:
```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your-email@gmail.com'
        auth_password: 'your-app-password'
```

## SSL Certificate Setup

This stack supports two SSL certificate options:

### Option 1: Self-Signed Certificates (Default)
- Automatically generated by Traefik
- Works out of the box, no configuration needed
- Requires accepting browser security warnings
- Suitable for local network use only

### Option 2: Let's Encrypt Trusted Certificates

For trusted SSL certificates that don't require browser warnings.

#### Prerequisites
- Own a domain name (e.g., `example.com`)
- Domain hosted on [Gandi](https://www.gandi.net/)
- Gandi Personal Access Token with "Manage domain name technical configurations" permission

#### Environment Variables

Add these to your `.env` file:
```bash
DOMAIN=example.com
ACME_EMAIL=your-email@example.com
GANDIV5_PERSONAL_ACCESS_TOKEN=your-gandi-token
```

#### Setup Commands

```bash
# Complete SSL setup (installs certbot, generates certs, configures auto-renewal)
make ssl-setup

# Or run individual steps:
make ssl-copy-certs           # Copy certs to Traefik
make ssl-configure-traefik    # Configure Traefik file provider
make ssl-setup-renewal        # Setup auto-renewal
make ssl-renew-test          # Test renewal (dry run)
```

#### Implementation Details

This setup uses **certbot with the Gandi DNS plugin** instead of Traefik's built-in ACME integration.

**Why certbot instead of Traefik ACME?**
- Traefik v3.2's Lego library (v4.21.0) has compatibility issues with Gandi API v5
- Manual API tests succeed, but Lego consistently returns 403 errors during DNS-01 challenge
- certbot with `certbot-dns-gandi` plugin works reliably with the same credentials
- See `scripts/setup-certbot-gandi.sh` for implementation details

**How it works:**
1. certbot generates wildcard certificate for `*.DOMAIN` and `DOMAIN` via DNS-01 challenge
2. Certificates stored in `/etc/letsencrypt/live/DOMAIN/`
3. Copied to `./data/traefik/certs/` for Traefik access
4. Traefik configured to use file provider instead of built-in ACME
5. Post-renewal hook automatically copies renewed certs and reloads Traefik

**Auto-Renewal:**
- certbot runs twice daily via snap timer
- Certificates renewed 30 days before expiry
- Post-renewal hook copies new certs to Traefik and restarts container
- Check logs: `sudo tail -f /var/log/certbot-traefik-reload.log`

**Certificate Details:**
- Wildcard certificate covers `*.DOMAIN` and `DOMAIN`
- Valid for 90 days, auto-renews at 60 days
- Issued by Let's Encrypt
- Trusted by all major browsers

#### Troubleshooting SSL Certificates

**Current Implementation (certbot + file provider):**
- Certificates: `./data/traefik/certs/DOMAIN.crt` (644) and `DOMAIN.key` (600)
- Dynamic config: `./config/traefik/dynamic-certs.yml` must exist
- Check if file provider loaded: `docker compose logs traefik | grep "file.Provider"`
- Check if certs loaded: `docker compose logs traefik | grep "Adding certificate"`
- Verify certs in container: `docker exec traefik ls -la /certs/`
- After config changes, must recreate container: `make ssl-configure-traefik`
- Browser caching: Browsers may cache old certificates - clear cache or use Cmd+Shift+R

**Troubleshooting certbot:**
- View certificates: `sudo certbot certificates`
- Test renewal: `sudo certbot renew --dry-run`
- Check Gandi credentials: `sudo cat /etc/letsencrypt/gandi/gandi.ini`
- Renewal logs: `sudo tail -f /var/log/certbot-traefik-reload.log`
- Verify DNS propagation: `dig @1.1.1.1 ${DOMAIN} +short`

#### Scripts

SSL certificate management scripts in `scripts/`:

- **setup-certbot-gandi.sh** - Install certbot and generate certificate
  - Installs certbot via snap and certbot-dns-gandi via pip3
  - Handles Ubuntu 24.04 externally-managed Python environment
  - Creates Gandi API credentials file
  - Generates wildcard cert via DNS-01 challenge

- **copy-certs-to-traefik.sh** - Copy certificates to Traefik
  - Copies from `/etc/letsencrypt/live/` to `./data/traefik/certs/`
  - Sets proper ownership and permissions

- **configure-traefik-file-provider.sh** - Configure Traefik file provider
  - Creates `./config/traefik/dynamic-certs.yml`
  - Configures Traefik to load certificates from file

- **setup-cert-renewal.sh** - Setup automatic renewal
  - Creates post-renewal hook at `/etc/letsencrypt/renewal-hooks/deploy/traefik-reload.sh`
  - Hook copies renewed certs and restarts Traefik
  - Tests renewal with dry run

## Docker Compose Customization

### Resource Limits

Edit `docker-compose.yml`:
```yaml
services:
  ollama:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          memory: 2G
```

### Log Rotation

```yaml
services:
  n8n:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Port Changes

```yaml
services:
  grafana:
    ports:
      - "${SERVER_IP}:3001:3000"  # Change 3001 to desired port
```

## Applying Configuration Changes

After editing `.env`:
```bash
# Restart affected services
docker compose up -d --force-recreate [service_name]
```

After editing `docker-compose.yml`:
```bash
# Apply changes
docker compose up -d
```

After editing service configs (Prometheus, Grafana, etc.):
```bash
# Restart specific service
docker compose restart [service_name]
```

## Configuration Validation

### Verify Environment Variables

```bash
# Check current config
cat .env

# Validate required variables are set
docker compose config
```

### Test Service Configuration

```bash
# Test AdGuard DNS
nslookup google.com SERVER_IP

# Test n8n access
curl -k -I https://SERVER_IP:5678

# Test WireGuard (from connected client)
ping 192.168.1.100
```

## Backup Configuration

Always backup configuration before changes:
```bash
cp .env .env.backup
cp docker-compose.yml docker-compose.yml.backup
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env docker-compose.yml ssl/ monitoring/
```

## References

- [Setup Guide](SETUP.md)
- [Operations Guide](OPERATIONS.md)
- [AI Models Guide](AI_MODELS.md)
- [Remote Access Setup](REMOTE_ACCESS.md)
- Service-specific docs:
  - [AdGuard Home](https://adguard.com/kb/)
  - [n8n](https://docs.n8n.io/)
  - [WireGuard](https://www.wireguard.com/)
  - [Traefik](https://doc.traefik.io/traefik/)
