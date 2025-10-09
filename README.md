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
- SSL certificates for n8n are automatically generated during `make setup`
- To regenerate with a custom domain: `make regenerate-ssl DOMAIN=your-domain.com`
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
- AdGuard Home: `http://SERVER_IP:80`
- n8n: `https://SERVER_IP:5678`
- Ollama API: `http://SERVER_IP:11434`
- Habitica: `http://SERVER_IP:8080`
- Bookwyrm: `http://SERVER_IP:8000`
- HortusFox: `http://SERVER_IP:8181`
- Grafana: `http://SERVER_IP:3001`
- Prometheus: `http://SERVER_IP:9090`
- Alertmanager: `http://SERVER_IP:9093`

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
**Latest Update:** 2025-01-07
