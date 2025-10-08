# Home Server Stack

A complete self-hosted infrastructure for home automation, AI, and network services using Docker Compose.

## 🚀 Services

**Core Services:**
- **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)** - Network-wide ad blocking and DNS server
- **[n8n](https://github.com/n8n-io/n8n)** - Workflow automation platform with AI capabilities
- **[Ollama](https://github.com/ollama/ollama)** - Local AI models (deepseek-coder:6.7b, llama3.2:3b)
- **[WireGuard](https://github.com/wireguard)** - VPN for secure remote access
- **[Bookwyrm](https://github.com/bookwyrm-social/bookwyrm)** - Social reading and book tracking

**Optional:**
- **Monitoring Stack** - Grafana, Prometheus, Alertmanager, Node Exporter, cAdvisor

See [SERVICES.md](SERVICES.md) for the complete catalog including planned services.

## 📋 Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd home-server-stack

# 2. Configure environment
cp .env.example .env
nano .env  # Update SERVER_IP, TIMEZONE, passwords

# 3. Generate SSL certificates (optional, for HTTPS)
cd ssl && ./generate-cert.sh your-domain.com && cd ..

# 4. Run first-time setup
make setup              # Base services only
# OR
make setup-all          # Base + monitoring (Grafana, Prometheus)
```

**Using the Makefile:**
- `make help` - Show all available commands
- `make setup` / `make setup-all` - First time setup
- `make update` / `make update-all` - Update services to latest versions
- `make start` / `make start-all` - Start services
- `make stop` / `make stop-all` - Stop services
- `make logs` / `make logs-all` - View logs from services
- See `make help` for complete list of commands

**Access Services:**
- AdGuard Home: `http://SERVER_IP:80`
- n8n: `https://SERVER_IP:5678`
- Ollama API: `http://SERVER_IP:11434`
- Bookwyrm: `http://SERVER_IP:8000`

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
