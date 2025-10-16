# Home Server Stack

A complete self-hosted infrastructure for home automation, AI, and network services using Docker Compose.

## 🚀 Services

**Core Services:**
- **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)** - Network-wide ad blocking and DNS server
- **[n8n](https://github.com/n8n-io/n8n)** - Workflow automation platform with AI capabilities
- **[Ollama](https://github.com/ollama/ollama)** - Local AI models (deepseek-coder:6.7b, llama3.2:3b)
- **[WireGuard](https://github.com/wireguard)** - VPN for secure remote access
- **[Habitica](https://github.com/HabitRPG/habitica)** - Gamified habit and task tracker
- **[Bookwyrm](https://github.com/bookwyrm-social/bookwyrm)** - Social reading and book tracking (via [external wrapper](https://github.com/josephradford/bookwyrm-docker))
- **[HortusFox](https://github.com/danielbrendel/hortusfox-web)** - Collaborative plant management
- **[Glance](https://github.com/glanceapp/glance)** - Personal dashboard and homepage

**Monitoring Stack:**
- **[Grafana](https://github.com/grafana/grafana)** - Metrics visualization and dashboards
- **[Prometheus](https://github.com/prometheus/prometheus)** - Metrics collection and alerting
- **[Alertmanager](https://github.com/prometheus/alertmanager)** - Alert routing and management
- **[Node Exporter](https://github.com/prometheus/node_exporter)** - System metrics exporter
- **[cAdvisor](https://github.com/google/cadvisor)** - Container metrics

See [SERVICES.md](SERVICES.md) for the complete catalog including planned services.

## 📋 Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd home-server-stack

# 2. Configure environment
cp .env.example .env
nano .env  # Update SERVER_IP, TIMEZONE, passwords

# 3. Run first-time setup (includes all services + monitoring)
# SSL certificates are automatically generated
make setup

# 4. Configure Bookwyrm (one-time)
cd external/bookwyrm-docker
cp .env.example .env
nano .env  # Configure Bookwyrm settings

# 5. Deploy Bookwyrm
make bookwyrm-setup
```

**Note:**
- SSL certificates are self-signed for local network use
- You'll need to accept security warnings in your browser on first visit
- This is normal and expected for local-only services
- For browsers that don't allow proceeding, see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#ssl-certificate-issues)
- The first `make setup` will deploy all core services and monitoring, and clone the Bookwyrm wrapper
- Configure and deploy Bookwyrm separately using `make bookwyrm-setup`

**Using the Makefile:**
- `make help` - Show all available commands
- `make setup` - First time setup (all services + monitoring)
- `make bookwyrm-setup` - Deploy Bookwyrm (after configuring .env)
- `make update` - Update all services to latest versions
- `make start` - Start all services
- `make stop` - Stop all services
- `make logs` - View logs from all services
- See `make help` for complete list of commands

**Access Services:**

All services are accessible via domain names on your local network:

- **Traefik Dashboard:** `https://traefik.home.local`
- **AdGuard Home:** `https://adguard.home.local` (DNS admin)
- **n8n:** `https://n8n.home.local` (Workflow automation)
- **Glance:** `https://glance.home.local` (Dashboard)
- **HortusFox:** `https://hortusfox.home.local` (Plant management)
- **Habitica:** `https://habitica.home.local` (Habit tracker)
- **Bookwyrm:** `https://bookwyrm.home.local` (Book tracking)
- **Ollama API:** `https://ollama.home.local` (AI models)
- **Grafana:** `https://grafana.home.local` (Monitoring)
- **Prometheus:** `https://prometheus.home.local` (Metrics)
- **Alertmanager:** `https://alerts.home.local` (Alerts)

**Note:** Services are accessible via domain names thanks to Traefik reverse proxy and AdGuard Home DNS. Your devices must use AdGuard Home as their DNS server (configured automatically if DHCP points to the server).

**Direct IP Access:** Some services remain accessible via IP:port for specific operational needs:
- AdGuard Home: `http://SERVER_IP:8888` (emergency access if Traefik fails)
- Ollama API: `http://SERVER_IP:11434` (direct API access for AI workloads)
- Prometheus: `http://SERVER_IP:9090` (metrics scraping)
- Alertmanager: `http://SERVER_IP:9093` (alert management)
- See [SERVICES.md](SERVICES.md) for complete list

See **[docs/SETUP.md](docs/SETUP.md)** for detailed installation instructions.

## 📚 Documentation

### Getting Started
- **[Setup Guide](docs/SETUP.md)** - Complete installation and initial setup
- **[Configuration Guide](docs/CONFIGURATION.md)** - Service configuration and customization
- **[Requirements](docs/REQUIREMENTS.md)** - System requirements and resource usage

### Operations
- **[Operations Guide](docs/OPERATIONS.md)** - Managing services, updates, backups
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Monitoring Deployment](docs/MONITORING_DEPLOYMENT.md)** - Optional monitoring stack setup

### Monitoring & Alerts
- **[Alerts Reference](docs/ALERTS.md)** - Alert definitions and response procedures
- **[Operations Runbook](docs/RUNBOOK.md)** - Detailed troubleshooting for all alerts
- **[Known Issues](docs/KNOWN_ISSUES.md)** - Known bugs and workarounds

### Advanced
- **[Remote Access Setup](docs/REMOTE_ACCESS.md)** - Port forwarding and VPN configuration
- **[AI Models Guide](docs/AI_MODELS.md)** - Ollama model management
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and data persistence

### Implementation Tickets
- **[Monitoring Tickets](monitoring-tickets/README.md)** - Monitoring implementation roadmap
- **[Security Tickets](security-tickets/README.md)** - Security hardening roadmap (VPN-first strategy)

## 🔐 Security

This project follows a **VPN-first security model**. See [security-tickets/README.md](security-tickets/README.md) for the complete security roadmap.

**Key Security Features:**
- VPN-first access (WireGuard primary boundary)
- Selective public exposure (n8n webhooks only)
- Pre-commit secret scanning
- Pinned Docker image versions
- Regular security audits

See **[SECURITY.md](SECURITY.md)** for security policy and reporting vulnerabilities.

## 🤝 Contributing

Contributions are welcome! See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidelines on:
- Submitting bug reports and feature requests
- Development workflow and branching strategy
- Pull request process

## 📊 System Requirements

**Minimum:**
- 8 GB RAM (16 GB recommended)
- 500 GB storage (1 TB recommended)
- Linux-based OS (tested on Ubuntu Server 24.04 LTS)
- Docker and Docker Compose installed

See **[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)** for detailed requirements.

## 📄 License

This project is open source. Individual services maintain their own licenses:
- AdGuard Home: GPL-3.0
- n8n: Fair-code (Sustainable Use License)
- Ollama: MIT
- Grafana: AGPL-3.0
- Prometheus: Apache-2.0

## 💬 Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
- **Service-specific docs**:
  - [AdGuard Home](https://adguard.com/kb/)
  - [n8n](https://docs.n8n.io/)
  - [Ollama](https://ollama.ai/)

---

**Project Status:** Active Development
**Latest Update:** 2025-10-16
