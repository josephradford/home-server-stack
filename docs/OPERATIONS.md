# Operations Guide

Day-to-day management of the Home Server Stack.

## Managing Services

All services (core + monitoring + Bookwyrm) are managed using the Makefile. The Makefile provides a simplified interface to Docker Compose operations.

### Start/Stop Services

```bash
# Start all services (core + monitoring + Bookwyrm if configured)
make start

# Stop all services
make stop

# Restart all services
make restart
```

### Service Status

```bash
# Check status of all services
make status

# Check resource usage
docker stats

# View service logs
make logs               # All services
make logs-n8n           # n8n only
make logs-wireguard     # WireGuard only
make logs-ollama        # Ollama only
make bookwyrm-logs      # Bookwyrm only

# View logs with Docker Compose directly
docker compose logs [service_name]
docker compose logs -f [service_name]  # Follow in real-time
docker compose logs --tail=100 [service_name]  # Last 100 lines
```

### Bookwyrm Management

Bookwyrm is managed separately but integrates with base commands:

```bash
# Bookwyrm-specific commands
make bookwyrm-start     # Start Bookwyrm
make bookwyrm-stop      # Stop Bookwyrm
make bookwyrm-restart   # Restart Bookwyrm
make bookwyrm-status    # Check Bookwyrm status
make bookwyrm-logs      # View Bookwyrm logs
make bookwyrm-init      # Re-run initialization

# Bookwyrm is automatically included in base commands
make start              # Includes Bookwyrm
make stop               # Includes Bookwyrm
make restart            # Includes Bookwyrm
```

### Individual Service Management

For fine-grained control, use Docker Compose directly:

```bash
# Restart services individually
docker compose restart adguard
docker compose restart n8n
docker compose restart ollama
docker compose restart wireguard
docker compose restart grafana
docker compose restart prometheus

# Rebuild and restart after config changes
docker compose up -d --force-recreate [service_name]

# Remove and recreate container
docker compose rm -f [service_name]
docker compose up -d [service_name]
```

## Updates

### Update All Services

Use the Makefile to update all services (core + monitoring + Bookwyrm):

```bash
# Update all services
make update

# This will:
# 1. Pull latest images for core + monitoring services
# 2. Restart services with new images
# 3. Update Bookwyrm (if deployed)
```

### Update Specific Service

For individual service updates, use Docker Compose directly:

```bash
# Pull specific image
docker compose pull n8n

# Recreate just that service
docker compose up -d n8n

# Verify
docker compose ps n8n
```

### Update Bookwyrm

```bash
# Update Bookwyrm to latest version
make bookwyrm-update

# This will:
# 1. Pull latest Bookwyrm source code
# 2. Rebuild Bookwyrm containers
# 3. Run database migrations
# 4. Restart Bookwyrm services
```

### Rollback

If an update causes issues:

```bash
# Stop services
docker compose down

# Edit docker-compose.yml to pin to previous version
# Example: Change 'n8nio/n8n:latest' to 'n8nio/n8n:1.19.4'
nano docker-compose.yml

# Start with pinned version
docker compose up -d
```

## Backups

### Manual Backup

```bash
# Create backup directory
mkdir -p ~/backups

# Backup all data volumes
sudo tar -czf ~/backups/homeserver-$(date +%Y%m%d-%H%M%S).tar.gz \
  ./data/ \
  ./.env \
  ./docker-compose.yml \
  ./ssl/

# Verify backup
ls -lh ~/backups/
```

### Automated Backups

Create backup script:

```bash
cat > ~/backup-homeserver.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="$HOME/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
STACK_DIR="$HOME/home-server-stack"

mkdir -p "$BACKUP_DIR"

# Backup with timestamp
sudo tar -czf "$BACKUP_DIR/homeserver-$TIMESTAMP.tar.gz" \
  -C "$STACK_DIR" \
  data/ .env docker-compose.yml ssl/

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t homeserver-*.tar.gz | tail -n +8 | xargs rm -f

echo "Backup completed: homeserver-$TIMESTAMP.tar.gz"
EOF

chmod +x ~/backup-homeserver.sh
```

Schedule with cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * $HOME/backup-homeserver.sh >> $HOME/backup.log 2>&1
```

### Restore from Backup

```bash
# Stop services
cd ~/home-server-stack
docker compose down

# Extract backup
sudo tar -xzf ~/backups/homeserver-YYYYMMDD-HHMMSS.tar.gz

# Start services
docker compose up -d

# Verify
docker compose ps
docker compose logs
```

## Monitoring

### Check System Resources

```bash
# Overall system status
htop

# Disk usage
df -h
du -sh ./data/*

# Docker disk usage
docker system df

# Container resource usage
docker stats
```

### View Logs

```bash
# All services
docker compose logs

# Specific service, last 100 lines
docker compose logs --tail=100 n8n

# Follow logs (real-time)
docker compose logs -f ollama

# Filter by time
docker compose logs --since 1h adguard
docker compose logs --since "2025-01-07T10:00:00"
```

### Check Service Health

```bash
# AdGuard Home
curl -I http://localhost:80

# n8n
curl -k -I https://localhost:5678

# Ollama
curl http://localhost:11434/api/version

# Prometheus (if monitoring enabled)
curl http://localhost:9090/-/healthy

# Grafana
curl -I http://localhost:3001/api/health
```

## Maintenance Tasks

### Clean Up Docker

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (⚠️ dangerous!)
docker volume prune

# Remove stopped containers
docker container prune

# Full cleanup
docker system prune -a --volumes
```

**Warning:** `docker volume prune` can delete data. Only use if you're sure volumes are unused.

### Rotate Logs

Docker logs can grow large:

```bash
# Check log sizes
du -sh /var/lib/docker/containers/*/*-json.log

# Configure log rotation in docker-compose.yml
services:
  service_name:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Database Maintenance (n8n)

```bash
# n8n uses SQLite by default
# Check database size
docker exec n8n du -sh /home/node/.n8n/database.sqlite

# Vacuum database (compact)
docker exec n8n sqlite3 /home/node/.n8n/database.sqlite "VACUUM;"
```

### Clear Prometheus Data

If Prometheus storage grows too large:

```bash
# Stop Prometheus
docker compose stop prometheus

# Delete old data
sudo rm -rf ./data/prometheus/data/*

# Start Prometheus
docker compose start prometheus
```

## Configuration Changes

### Update Environment Variables

```bash
# Edit .env
nano .env

# Restart affected services
docker compose up -d --force-recreate [service_name]

# Example: After changing n8n password
docker compose up -d --force-recreate n8n
```

### Modify Service Configuration

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Apply changes
docker compose up -d

# Verify
docker compose ps
docker compose logs [service_name]
```

### Add New Service

1. Edit `docker-compose.yml`
2. Add service definition
3. Update `.env.example` with new variables
4. Update `.env` with actual values
5. Deploy: `docker compose up -d`

## Managing Traefik Reverse Proxy

### Viewing Traefik Status

```bash
# Check Traefik container
docker ps | grep traefik

# View Traefik logs
docker logs traefik

# View access logs
tail -f data/traefik/logs/access.log

# Check Traefik health
docker inspect traefik | grep -A 10 Health
```

### Reloading Traefik Configuration

Traefik automatically detects Docker label changes. Just restart the service:

```bash
# Add/update labels in docker-compose.yml
nano docker-compose.yml

# Restart service with new labels
docker compose up -d servicename

# Traefik discovers changes automatically (no Traefik restart needed)
```

### Traefik Troubleshooting

**Check active routers:**
```bash
docker exec traefik traefik healthcheck
curl http://localhost:8080/api/http/routers | jq
```

**View service discovery:**
```bash
docker exec traefik cat /etc/traefik/traefik.yml
```

**Test routing manually:**
```bash
# Test HTTP redirect
curl -I http://servicename.home.local

# Test HTTPS access
curl -Ik https://servicename.home.local
```

### Common Traefik Issues

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#traefik-issues) for detailed solutions.

## Performance Optimization

### Limit Resource Usage

Edit `docker-compose.yml` to add resource limits:

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

Apply changes:
```bash
docker compose up -d --force-recreate ollama
```

### Monitor Performance

```bash
# Real-time container stats
docker stats

# Check system load
uptime
top

# Disk I/O
iotop

# Network usage
nethogs
```

## Security Maintenance

### Update System

```bash
# Update OS packages
sudo apt update && sudo apt upgrade -y

# Reboot if kernel updated
sudo reboot
```

### Review Logs for Issues

```bash
# Check AdGuard for blocked domains
docker compose logs adguard | grep "blocked"

# Check n8n for failed auth
docker compose logs n8n | grep "authentication"

# Check WireGuard connections
docker compose logs wireguard | grep "peer"
```

### Renew SSL Certificates

If using Let's Encrypt (see [security-tickets/04-tls-certificate-monitoring.md](../security-tickets/04-tls-certificate-monitoring.md)):

```bash
# Manual renewal
docker compose exec certbot certbot renew

# Check expiry
openssl x509 -in ssl/server.crt -noout -dates
```

### Review Security Tickets

Periodically check progress on [security-tickets/README.md](../security-tickets/README.md).

## Troubleshooting

For common issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Quick Diagnostics:**

```bash
# Check all services
docker compose ps

# Check Docker daemon
sudo systemctl status docker

# Check disk space
df -h

# Check memory
free -h

# Check network
ss -tlnp | grep -E ':(53|80|5678|11434|51820)'

# Full system check
~/home-server-stack/scripts/health-check.sh  # (if you create one)
```

## References

- [SETUP.md](SETUP.md) - Initial setup
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [MONITORING_DEPLOYMENT.md](MONITORING_DEPLOYMENT.md) - Monitoring setup
- [security-tickets/10-automated-backups.md](../security-tickets/10-automated-backups.md) - Advanced backup strategies
