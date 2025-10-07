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

# Ollama Configuration
OLLAMA_NUM_PARALLEL=2          # Concurrent requests (reduce if low RAM)
OLLAMA_MAX_LOADED_MODELS=2     # Max models in memory
OLLAMA_LOAD_TIMEOUT=600        # Model load timeout (seconds)

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

### Ollama

Configuration via environment variables.

**Model Management:**
```bash
# List models
docker exec ollama ollama list

# Pull models
docker exec ollama ollama pull llama3.2:3b

# Remove models
docker exec ollama ollama rm model-name

# Show model info
docker exec ollama ollama show llama3.2:3b
```

**Performance Tuning:**
```bash
# Low RAM (8 GB): Single model, low parallelism
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1

# Medium RAM (16 GB): Moderate parallelism
OLLAMA_NUM_PARALLEL=2
OLLAMA_MAX_LOADED_MODELS=2

# High RAM (32+ GB): High parallelism
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=3
```

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

## SSL/TLS Configuration

### Self-Signed Certificates (Development)

Generated via `ssl/generate-cert.sh`:
```bash
cd ssl
./generate-cert.sh your-domain.com
```

**Files:**
- `ssl/server.key` - Private key
- `ssl/server.crt` - Certificate

**Expiry:** 365 days (regenerate annually)

### Let's Encrypt (Production)

See [security-tickets/04-tls-certificate-monitoring.md](../security-tickets/04-tls-certificate-monitoring.md) for Let's Encrypt setup with automatic renewal.

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

# Test Ollama
curl http://SERVER_IP:11434/api/version

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
  - [Ollama](https://ollama.ai/library)
  - [WireGuard](https://www.wireguard.com/)
