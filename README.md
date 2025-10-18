# Home Server Stack

A complete self-hosted infrastructure for home automation, AI, and network services using Docker Compose.

## 🚀 Services

**Core Services:**
- **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)** - Network-wide ad blocking and DNS server
- **[n8n](https://github.com/n8n-io/n8n)** - Workflow automation platform
- **[WireGuard](https://github.com/wireguard)** - VPN for secure remote access
- **[Traefik](https://github.com/traefik/traefik)** - Reverse proxy for domain-based service access

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
make setup
```

**Note:** `make setup` will optionally prompt you to configure Let's Encrypt SSL certificates if your `.env` includes `DOMAIN`, `ACME_EMAIL`, and `GANDIV5_PERSONAL_ACCESS_TOKEN`. Otherwise, services use self-signed certificates (browser warnings expected).

**Using the Makefile:**
- `make help` - Show all available commands
- `make setup` - First time setup (all services + monitoring)
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
- **Grafana:** `https://grafana.home.local` (Monitoring)
- **Prometheus:** `https://prometheus.home.local` (Metrics)
- **Alertmanager:** `https://alerts.home.local` (Alerts)

**Note:** Services are accessible via domain names thanks to Traefik reverse proxy and AdGuard Home DNS. Your devices must use AdGuard Home as their DNS server (configured automatically if DHCP points to the server).

**Direct IP Access:** Some services remain accessible via IP:port for specific operational needs:
- AdGuard Home: `http://SERVER_IP:8888` (emergency access if Traefik fails)
- Prometheus: `http://SERVER_IP:9090` (metrics scraping)
- Alertmanager: `http://SERVER_IP:9093` (alert management)
- See [SERVICES.md](SERVICES.md) for complete list

See **[docs/SETUP.md](docs/SETUP.md)** for detailed installation instructions.

## 🔒 SSL Certificates

By default, services use **self-signed certificates** (browser warnings expected). For **trusted Let's Encrypt certificates**, see **[docs/CONFIGURATION.md#ssl-certificate-setup](docs/CONFIGURATION.md#ssl-certificate-setup)** for complete setup instructions using `make ssl-setup`.

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
- Traefik: MIT
- Grafana: AGPL-3.0
- Prometheus: Apache-2.0

## 💬 Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
- **Service-specific docs**:
  - [AdGuard Home](https://adguard.com/kb/)
  - [n8n](https://docs.n8n.io/)
  - [Traefik](https://doc.traefik.io/traefik/)

---

**Project Status:** Active Development
**Latest Update:** 2025-10-16
