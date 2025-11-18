# Quick Start - Local Development

Get the stack running locally on your Mac in 3 commands:

## Setup (One-Time)

```bash
# 1. Setup local environment
make local-setup
```

This creates `.env.local`, validates configuration, and starts all services.

## Access Services

Once running, open these URLs:

- **Homepage Dashboard**: http://localhost:3000 ⭐ (start here)
- **n8n Workflows**: http://localhost:5678 (user: admin, pass: admin)
- **Home Assistant**: http://localhost:8123
- **Actual Budget**: http://localhost:5006
- **Grafana**: http://localhost:3001 (user: admin, pass: admin)
- **Traefik Dashboard**: http://localhost:8080
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

## Daily Commands

```bash
# Start services
make local-start

# View logs
make local-logs

# Check status
make local-status

# Restart after changes
make local-restart

# Stop when done
make local-stop
```

## Deploy to Server

```bash
# Deploy current branch to your server
make deploy SERVER=user@192.168.1.100

# Deploy specific branch
make deploy SERVER=joe@homeserver.local BRANCH=feature/new-service
```

## Development Workflow

1. **Make changes** to docker-compose files or configs
2. **Test locally**: `make local-restart && make local-logs`
3. **Commit**: `git add . && git commit -m "Description"`
4. **Push**: `git push`
5. **Deploy**: `make deploy SERVER=user@server`

## What's Disabled Locally?

- **AdGuard Home** - No DNS-based routing needed
- **WireGuard VPN** - Requires Linux kernel modules
- **Fail2ban** - Not needed for local testing
- **SSL/TLS** - Uses HTTP for simplicity

## Troubleshooting

```bash
# View all logs
make local-logs

# Check what's running
make local-status

# Reset everything
make local-clean
rm -rf ./data/
make local-setup
```

## Full Documentation

See [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md) for complete guide.
