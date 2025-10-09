# Setup Guide

Complete installation and initial configuration guide for the Home Server Stack.

## Prerequisites

Before starting, ensure you have:
- A dedicated server or machine running Linux (tested on Ubuntu Server 24.04 LTS)
- Docker and Docker Compose installed
- Static IP address configured for your server
- Root or sudo access
- See [REQUIREMENTS.md](REQUIREMENTS.md) for detailed system requirements

## Installation Steps

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd home-server-stack
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

**Required Configuration:**

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVER_IP` | Your server's local IP address | `192.168.1.100` |
| `TIMEZONE` | Your local timezone | `America/New_York`, `Europe/London`, `UTC` |
| `N8N_USER` | Username for n8n access | `admin` |
| `N8N_PASSWORD` | Secure password for n8n | `your_secure_password_here` |
| `N8N_EDITOR_BASE_URL` | External domain for n8n | `https://your-domain:5678` |

**Optional Configuration:**

| Variable | Description | Default |
|----------|-------------|---------|
| `GRAFANA_PASSWORD` | Grafana admin password | `your_secure_grafana_password` |
| `OLLAMA_NUM_PARALLEL` | Concurrent Ollama requests | `2` |
| `OLLAMA_MAX_LOADED_MODELS` | Max models in memory | `2` |
| `N8N_RUNNERS_TASK_TIMEOUT` | n8n task timeout (seconds) | `1800` |

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

### 3. Deploy Stack

Run the automated setup which will:
- Generate SSL certificates automatically (for n8n HTTPS)
- Pull and start all services (core + monitoring)
- Clone the Bookwyrm wrapper

```bash
make setup
```

**What happens during setup:**
- ✅ Environment validation (`.env` file check)
- ✅ SSL certificate generation (if not present)
- ✅ Docker Compose validation
- ✅ Image pulling
- ✅ Services deployment (AdGuard, n8n, Ollama, WireGuard, Habitica, Grafana, Prometheus, etc.)
- ✅ Bookwyrm wrapper cloning

**Note:** SSL certificates are automatically generated for localhost. To regenerate with a custom domain:
```bash
make regenerate-ssl DOMAIN=your-domain.ddns.net
make restart  # Restart services to use new certificates
```

For production TLS certificates, see [security-tickets/04-tls-certificate-monitoring.md](../security-tickets/04-tls-certificate-monitoring.md).

### 4. Configure and Deploy Bookwyrm

After `make setup` completes, configure Bookwyrm:

```bash
cd external/bookwyrm-docker
cp .env.example .env
nano .env  # Configure Bookwyrm settings
```

**Required Bookwyrm configuration:**
- `BOOKWYRM_DOMAIN` - Domain or IP for Bookwyrm
- `BOOKWYRM_SECRET_KEY` - Generate with `openssl rand -base64 45`
- `BOOKWYRM_DB_PASSWORD` - Generate with `openssl rand -base64 32`
- `BOOKWYRM_REDIS_ACTIVITY_PASSWORD` - Generate with `openssl rand -base64 32`
- `BOOKWYRM_REDIS_BROKER_PASSWORD` - Generate with `openssl rand -base64 32`

See [BOOKWYRM.md](BOOKWYRM.md) for detailed Bookwyrm configuration.

Then deploy Bookwyrm:

```bash
cd ../..  # Return to home-server-stack root
make bookwyrm-setup
```

### 5. Verify Deployment

Check that all services are running:

```bash
make status
```

Expected output includes:
- adguard-home
- n8n
- ollama, ollama-setup
- wireguard
- habitica-mongo, habitica-server, habitica-client
- hortusfox-db, hortusfox
- grafana, prometheus, alertmanager, node-exporter, cadvisor
- bookwyrm services (if deployed)

View logs to check for errors:
```bash
make logs
```

Or view specific service logs:
```bash
make logs-n8n
make logs-wireguard
make logs-habitica
make logs-hortusfox
make bookwyrm-logs
```

## Initial Configuration

### AdGuard Home Setup

1. Navigate to `http://SERVER_IP:3000`
2. Click "Get Started" in the setup wizard
3. **Admin Web Interface:**
   - Interface: All interfaces
   - Port: `80` (default)
4. **DNS Server:**
   - Interface: All interfaces
   - Port: `53` (default)
5. **Create Admin Account:**
   - Set admin username
   - Set a strong password
6. Click "Next" through remaining steps
7. After setup, access admin panel at `http://SERVER_IP:80`

**Recommended Settings:**
- **Filters > DNS blocklists:** Enable default lists
- **Settings > DNS settings:**
  - Upstream DNS: `1.1.1.1`, `8.8.8.8`
  - Enable parallel requests
  - Enable DNSSEC
- **Settings > Encryption:** Keep disabled for local network (VPN handles encryption)

### n8n Setup

1. Navigate to `https://SERVER_IP:5678`
2. Accept the self-signed certificate warning:
   - Chrome/Edge: Click "Advanced" → "Proceed to [your-domain] (unsafe)"
   - Firefox: Click "Advanced" → "Accept the Risk and Continue"
3. Login with credentials from `.env` file:
   - Username: Value from `N8N_USER`
   - Password: Value from `N8N_PASSWORD`
4. You'll see the n8n welcome screen
5. Create your first workflow or explore templates

**First Steps in n8n:**
- Click "New workflow" to start from scratch
- Or browse "Templates" for pre-built workflows
- Test Ollama integration: Add an "Ollama" node and connect to `http://ollama:11434`

### Ollama Model Verification

The initial setup automatically downloads two models:
- `deepseek-coder:6.7b` (coding assistant)
- `llama3.2:3b` (general chat)

Verify models are downloaded:

```bash
docker exec ollama ollama list
```

Expected output:
```
NAME                    ID              SIZE    MODIFIED
deepseek-coder:6.7b     xxxxx           4.8 GB  X minutes ago
llama3.2:3b             xxxxx           2.0 GB  X minutes ago
```

Test the models:

```bash
# Test general chat model
curl http://SERVER_IP:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Hello, how are you?",
  "stream": false
}'

# Test coding assistant
curl http://SERVER_IP:11434/api/generate -d '{
  "model": "deepseek-coder:6.7b",
  "prompt": "Write a Python function to calculate fibonacci numbers",
  "stream": false
}'
```

See [AI_MODELS.md](AI_MODELS.md) for model management.

### WireGuard VPN Setup

WireGuard automatically generates peer configurations on first run.

**Get Client Configuration:**

```bash
# View all peer configs
docker exec wireguard ls /config/peer*

# Display QR code for mobile (peer1)
docker exec wireguard /app/show-peer 1

# Get config file for desktop (peer1)
docker exec wireguard cat /config/peer1/peer1.conf
```

**Connect Clients:**

1. **Mobile (iOS/Android):**
   - Install WireGuard app
   - Scan QR code displayed above
   - Enable the connection

2. **Desktop (Windows/macOS/Linux):**
   - Install WireGuard client
   - Import the `.conf` file
   - Activate the tunnel

After connecting, verify VPN access:
```bash
# From VPN client, test accessing internal services
curl http://192.168.1.100:80  # AdGuard
curl https://192.168.1.100:5678  # n8n
```

See [REMOTE_ACCESS.md](REMOTE_ACCESS.md) for advanced VPN configuration.

### Habitica Setup

Habitica is automatically deployed and accessible at `http://SERVER_IP:8080`.

1. Navigate to `http://SERVER_IP:8080`
2. Create your account:
   - Email address
   - Username
   - Password
3. Complete the character creation wizard
4. Start tracking your habits and tasks!

See the [Habitica documentation](https://habitica.fandom.com/wiki/Habitica_Wiki) for usage guides.

### HortusFox Setup

HortusFox is automatically deployed and accessible at `http://SERVER_IP:8181`.

1. Navigate to `http://SERVER_IP:8181`
2. Login with admin credentials from `.env` file:
   - Email: Value from `HORTUSFOX_ADMIN_EMAIL`
   - Password: Value from `HORTUSFOX_ADMIN_PASSWORD`
3. Complete the initial setup:
   - Set up your first location (e.g., "Living Room", "Garden")
   - Add plant species to your database
   - Start tracking your plants!
4. Configure plant care tasks and reminders

**Key Features:**
- Plant inventory management
- Care task scheduling and reminders
- Photo galleries for plants
- Location-based organization
- Collaborative plant management for households

See the [HortusFox documentation](https://github.com/danielbrendel/hortusfox-web) for detailed usage.

### Bookwyrm Setup

After deploying Bookwyrm with `make bookwyrm-setup`:

1. Navigate to `http://SERVER_IP:8000`
2. Create admin account using the admin code from setup logs:
   ```bash
   make bookwyrm-logs | grep "admin code"
   ```
3. Configure your Bookwyrm instance:
   - Site name and description
   - Registration settings (open/invite-only)
   - Federated network preferences

See [BOOKWYRM.md](BOOKWYRM.md) for detailed configuration and usage.

## Monitoring Stack

The monitoring stack is automatically deployed and provides comprehensive observability:

### Access Grafana

1. Navigate to `http://SERVER_IP:3001`
2. Login with:
   - Username: `admin`
   - Password: Value from `GRAFANA_PASSWORD` in `.env`
3. Navigate to **Dashboards** → **Browse**
4. Open pre-configured dashboards:
   - **System Overview** - CPU, memory, disk, network metrics
   - **Container Health** - Docker container status and resources
   - **Resource Utilization** - Historical trends and top consumers

### Verify Prometheus

1. Navigate to `http://SERVER_IP:9090`
2. Go to **Status** → **Targets**
3. Verify all targets are "UP":
   - prometheus
   - node-exporter
   - cadvisor
   - adguard
   - n8n (if configured)
   - ollama (if configured)

### Configure Alertmanager

Alertmanager is pre-configured to send alerts to a webhook at `http://127.0.0.1:5001/`.

To configure email/Slack/other notifications:

```bash
nano monitoring/alertmanager/alertmanager.yml
```

See [MONITORING_DEPLOYMENT.md](MONITORING_DEPLOYMENT.md) for detailed monitoring setup.

## Post-Installation

### Security Checklist

- [ ] Changed all default passwords
- [ ] Generated strong SSL certificates
- [ ] Reviewed `.env` file (no secrets committed)
- [ ] Configured firewall rules (if applicable)
- [ ] WireGuard VPN configured and tested
- [ ] Reviewed [security-tickets/README.md](../security-tickets/README.md) for hardening roadmap

### Network Configuration

**For local-only access (recommended):**
- No additional configuration needed
- Access all services via local IP or VPN

**For remote access (not recommended without VPN):**
- See [REMOTE_ACCESS.md](REMOTE_ACCESS.md) for port forwarding
- **Warning:** Only expose services you absolutely need externally
- Use WireGuard VPN for secure remote access instead

### Backup Configuration

Set up regular backups of your data:

```bash
# Create backup directory
mkdir -p ~/backups

# Backup data volumes
sudo tar -czf ~/backups/homeserver-$(date +%Y%m%d).tar.gz ./data/

# Backup configurations
cp .env ~/backups/.env.$(date +%Y%m%d)
```

Consider automating backups with cron (see [security-tickets/10-automated-backups.md](../security-tickets/10-automated-backups.md)).

## Next Steps

1. **Configure DNS:**
   - Update your router to use AdGuard Home as DNS server
   - Or configure device-specific DNS settings

2. **Create n8n Workflows:**
   - Explore n8n templates
   - Connect to Ollama for AI-powered automations
   - Set up integrations with external services

3. **Download Additional AI Models:**
   - See [AI_MODELS.md](AI_MODELS.md) for recommended models
   - Browse available models at https://ollama.ai/library

4. **Harden Security:**
   - Follow [security-tickets/README.md](../security-tickets/README.md)
   - Start with Phase 1 (Critical) tickets
   - Implement VPN-first access strategy

5. **Set Up Monitoring (if not already):**
   - Deploy monitoring stack
   - Configure alerts
   - Set up dashboards

## Troubleshooting

If you encounter issues during setup, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common problems and solutions.

**Quick Checks:**

```bash
# Check service status
docker compose ps

# View service logs
docker compose logs [service_name]

# Restart a service
docker compose restart [service_name]

# Verify Docker is running
sudo systemctl status docker

# Check port availability
sudo netstat -tlnp | grep -E ':(53|80|5678|11434|51820)'
```

## Support

- **Documentation:** [docs/](.) directory
- **Issues:** [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
- **Service Docs:** [AdGuard](https://adguard.com/kb/), [n8n](https://docs.n8n.io/), [Ollama](https://ollama.ai/)
