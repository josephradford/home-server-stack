# Local Development Guide

This guide explains how to run the home server stack locally on your Mac for testing and development, and how to deploy changes to your production server.

## Overview

The stack supports two environments:

1. **Local Development** (macOS with Docker Desktop)
   - Simplified setup without SSL/DNS
   - Direct port access (localhost:PORT)
   - No WireGuard/Fail2ban (macOS limitations)
   - Perfect for testing configuration changes

2. **Production Server** (Ubuntu Server)
   - Full SSL/DNS with Let's Encrypt
   - Domain-based routing via Traefik
   - Complete security stack
   - Real home automation

## Quick Start - Local Development

### 1. First Time Setup

```bash
# Clone the repository (if not already done)
git clone <your-repo-url>
cd home-server-stack

# Setup local environment (one-time)
make local-setup
```

This will:
- Create `.env.local` from template
- Validate configuration
- Create data directories
- Start all services

### 2. Access Your Services

Once running, access services directly via localhost:

- **Homepage Dashboard**: http://localhost:3000
- **Traefik Dashboard**: http://localhost:8080
- **n8n**: http://localhost:5678 (user: admin, pass: admin)
- **Home Assistant**: http://localhost:8123
- **Actual Budget**: http://localhost:5006
- **Grafana**: http://localhost:3001 (user: admin, pass: admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### 3. Daily Development Workflow

```bash
# Start services
make local-start

# View logs (all services)
make local-logs

# View status
make local-status

# Restart after config changes
make local-restart

# Stop when done
make local-stop
```

## What's Different in Local Mode?

The `docker-compose.local.yml` override file makes these changes:

### Disabled Services
- **AdGuard Home**: Not needed (no DNS-based routing locally)
- **WireGuard VPN**: Requires Linux kernel modules
- **Fail2ban**: Not needed for local testing

### Simplified Configuration
- **No SSL/TLS**: Services use HTTP instead of HTTPS
- **Direct Port Access**: All services expose ports on localhost
- **No Middleware**: Security middlewares disabled for easy access
- **Simpler Environment**: `.env.local` has minimal required values

### Port Mappings

| Service | Port | URL |
|---------|------|-----|
| Homepage | 3000 | http://localhost:3000 |
| Traefik Dashboard | 8080 | http://localhost:8080 |
| n8n | 5678 | http://localhost:5678 |
| Home Assistant | 8123 | http://localhost:8123 |
| Actual Budget | 5006 | http://localhost:5006 |
| Grafana | 3001 | http://localhost:3001 |
| Prometheus | 9090 | http://localhost:9090 |
| Alertmanager | 9093 | http://localhost:9093 |

## Deploying to Production Server

### Option 1: Automated Deployment (Recommended)

The easiest way to deploy changes:

```bash
# Deploy current branch to server
make deploy SERVER=user@192.168.1.100

# Deploy specific branch
make deploy SERVER=joe@homeserver.local BRANCH=feature/new-service

# Deploy to custom path
REMOTE_PATH=/opt/home-server make deploy SERVER=user@server
```

The deployment script will:
1. Check your local git status
2. Push changes to the repository
3. SSH to server and pull changes
4. Validate configuration
5. Pull updated Docker images
6. Restart services
7. Show service status

### Option 2: Manual Deployment

SSH to your server and pull changes manually:

```bash
# SSH to server
ssh user@192.168.1.100

# Navigate to stack directory
cd ~/home-server-stack

# Pull latest changes
git pull

# Validate configuration
make validate

# Update and restart services
make update

# Check status
make status
```

### Option 3: Git-Based Workflow

Set up a git remote on your server:

```bash
# On your server, create a bare repository
ssh user@192.168.1.100
git init --bare ~/home-server-stack.git

# Create post-receive hook to auto-deploy
cat > ~/home-server-stack.git/hooks/post-receive << 'EOF'
#!/bin/bash
GIT_WORK_TREE=/home/user/home-server-stack git checkout -f
cd /home/user/home-server-stack
make update
EOF
chmod +x ~/home-server-stack.git/hooks/post-receive

# On your local machine, add remote
git remote add production user@192.168.1.100:~/home-server-stack.git

# Deploy by pushing
git push production main
```

## Configuration Management

### Environment Files

You'll maintain two `.env` files:

1. **`.env.local`** (your Mac)
   - Committed as `.env.local.example`
   - Simple values for local testing
   - No real API keys needed

2. **`.env`** (production server)
   - NOT committed to git
   - Real credentials and API keys
   - Domain and SSL configuration

### Synchronizing Configuration

When you add new environment variables:

1. Add to `.env.example` with comments
2. Add to `.env.local.example` with test values
3. Update your local `.env.local`
4. SSH to server and update production `.env`

```bash
# Compare local and production configs
diff .env.local.example .env.example

# Check what variables changed on server
ssh user@server 'cd ~/home-server-stack && git diff .env.example'
```

## Testing Workflow

### Before Committing Changes

1. **Test locally first**:
   ```bash
   make local-start
   make local-logs
   # Verify services work correctly
   ```

2. **Validate configuration**:
   ```bash
   make validate
   ```

3. **Commit and push**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```

4. **Deploy to server**:
   ```bash
   make deploy SERVER=user@server
   ```

### Testing Specific Services

```bash
# Test n8n workflows locally
open http://localhost:5678

# Test Home Assistant automations
open http://localhost:8123

# Check monitoring dashboards
open http://localhost:3001  # Grafana
open http://localhost:9090  # Prometheus
```

## Troubleshooting Local Development

### Services Won't Start

```bash
# Check what's using ports
lsof -i :3000  # Homepage
lsof -i :8080  # Traefik
lsof -i :5678  # n8n

# View detailed logs
make local-logs

# Check service status
make local-status
```

### Configuration Errors

```bash
# Validate docker-compose syntax
docker compose -f docker-compose.yml \
  -f docker-compose.network.yml \
  -f docker-compose.monitoring.yml \
  -f docker-compose.dashboard.yml \
  -f docker-compose.local.yml \
  --env-file .env.local config
```

### Permission Issues

```bash
# Fix data directory permissions
sudo chown -R $(id -u):$(id -g) ./data/
```

### Reset Local Environment

```bash
# Stop and remove everything
make local-clean

# Remove all data (start fresh)
rm -rf ./data/

# Setup again
make local-setup
```

## Common Development Tasks

### Adding a New Service

1. **Add to `docker-compose.yml`**:
   ```yaml
   myservice:
     image: myservice:latest
     container_name: myservice
     expose:
       - 8080
     labels:
       - "traefik.enable=true"
       - "traefik.http.routers.myservice.rule=Host(`myservice.${DOMAIN}`)"
       # ... other labels
   ```

2. **Add local override to `docker-compose.local.yml`**:
   ```yaml
   myservice:
     ports:
       - "8080:8080"
     labels:
       - "traefik.http.routers.myservice.rule=Host(`localhost`)"
       - "traefik.http.routers.myservice.entrypoints=web"
   ```

3. **Test locally**:
   ```bash
   make local-restart
   open http://localhost:8080
   ```

4. **Deploy to server**:
   ```bash
   git add docker-compose.yml docker-compose.local.yml
   git commit -m "Add myservice"
   git push
   make deploy SERVER=user@server
   ```

### Modifying Environment Variables

1. Update `.env.example` and `.env.local.example`
2. Update your local `.env.local`
3. Test locally
4. SSH to server and update production `.env`
5. Deploy

### Testing Configuration Changes

```bash
# Edit docker-compose files
vim docker-compose.yml

# Test locally without committing
make local-restart
make local-logs

# If it works, commit and deploy
git commit -am "Update configuration"
make deploy SERVER=user@server
```

## Best Practices

### 1. Always Test Locally First

- Never commit untested changes
- Verify services start correctly
- Check logs for errors

### 2. Use Feature Branches

```bash
# Create feature branch
git checkout -b feature/new-service

# Test locally
make local-setup

# Deploy to test on server
make deploy SERVER=user@server BRANCH=feature/new-service

# Merge when stable
git checkout main
git merge feature/new-service
```

### 3. Keep Environments in Sync

- Regularly update `.env.example` with new variables
- Document production-only configuration in `docs/CONFIGURATION.md`
- Use same Docker image versions in both environments

### 4. Monitor Production After Deployment

```bash
# After deploying, watch logs
ssh user@server 'cd ~/home-server-stack && make logs'

# Check service health
ssh user@server 'cd ~/home-server-stack && make status'

# Check Grafana dashboards
open https://grafana.yourdomain.com
```

## Comparison: Local vs Production

| Feature | Local Development | Production Server |
|---------|------------------|------------------|
| Operating System | macOS | Ubuntu Server |
| Docker | Docker Desktop | Docker Engine |
| Domain Access | localhost:PORT | service.domain.com |
| SSL/TLS | No (HTTP only) | Yes (Let's Encrypt) |
| DNS Server | No AdGuard | AdGuard Home |
| VPN Access | Disabled | WireGuard |
| Security Stack | Minimal | Full (Fail2ban, etc.) |
| Purpose | Testing/Development | Production Use |
| Data Persistence | Temporary/Disposable | Long-term Storage |

## Getting Help

If you encounter issues:

1. Check logs: `make local-logs` or `make logs-<service>`
2. Verify status: `make local-status`
3. Review `docs/TROUBLESHOOTING.md`
4. Check service-specific documentation in `docs/`

## Next Steps

- Read [`CONFIGURATION.md`](./CONFIGURATION.md) for detailed service configuration
- See [`OPERATIONS.md`](./OPERATIONS.md) for maintenance procedures
- Review [`ARCHITECTURE.md`](./ARCHITECTURE.md) to understand the system design
