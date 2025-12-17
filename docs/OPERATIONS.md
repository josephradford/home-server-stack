# Operations Guide

Day-to-day management of the Home Server Stack.

## Managing Services

All services are managed using the Makefile for common operations.

### Quick Commands

```bash
# Start/stop/restart all services
make start
make stop
make restart

# Check status
make status

# View logs
make logs               # All services
make logs-n8n           # Specific service
make logs-wireguard

# Restart individual service
docker compose restart <service_name>

# Rebuild after config changes
docker compose up -d --force-recreate <service_name>
```

## Updates

```bash
# Update all services
make update

# Update specific service
docker compose pull <service_name>
docker compose up -d <service_name>

# Rollback: Pin version in docker-compose.yml
# Change 'n8nio/n8n:latest' to 'n8nio/n8n:1.19.4'
nano docker-compose.yml
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

Access your monitoring dashboards:
- **Grafana**: https://grafana.${DOMAIN} (admin / GRAFANA_PASSWORD)
- **Prometheus**: https://prometheus.${DOMAIN}
- **Alertmanager**: https://alerts.${DOMAIN}

```bash
# Quick resource check
docker stats
df -h
free -h

# View logs
docker compose logs -f <service_name>
docker compose logs --tail=100 --since 1h <service_name>
```

## Maintenance

### Cleanup

```bash
# Clean Docker (removes unused images/containers)
docker system prune -a

# Check Docker disk usage
docker system df

# Clean large log files
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### Database Maintenance

```bash
# Compact n8n SQLite database
docker exec n8n sqlite3 /home/node/.n8n/database.sqlite "VACUUM;"

# Check database size
docker exec n8n du -sh /home/node/.n8n/database.sqlite
```

### Prometheus Data

```bash
# Clear old Prometheus data if storage grows too large
docker compose stop prometheus
sudo rm -rf ./data/prometheus/data/*
docker compose start prometheus
```

## Configuration Changes

```bash
# Update environment variables
nano .env
docker compose up -d --force-recreate <service_name>

# Modify service configuration
nano docker-compose.yml
docker compose up -d
```

## Traefik Management

Access dashboard: https://traefik.${DOMAIN}

```bash
# View logs
docker logs traefik
tail -f data/traefik/logs/access.log

# Check active routers
curl http://localhost:8080/api/http/routers | jq

# Traefik auto-detects label changes - just restart the service
docker compose up -d <service_name>
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md#traefik-issues) for common issues.

## Performance Tuning

Add resource limits to docker-compose.yml:

```yaml
services:
  n8n:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

Then apply: `docker compose up -d --force-recreate n8n`

## Security

```bash
# Update OS
sudo apt update && sudo apt upgrade -y

# Check SSL certificate expiry
openssl x509 -in ssl/server.crt -noout -dates

# Review logs for issues
docker compose logs adguard | grep "blocked"
docker compose logs n8n | grep "authentication"
docker compose logs wireguard | grep "peer"
```

See [security-tickets/README.md](../security-tickets/README.md) for security improvements.

## Quick Diagnostics

```bash
# Check all services
docker compose ps

# Check resources
df -h && free -h

# Check network ports
ss -tlnp | grep -E ':(53|80|5678|51820)'
```

For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
