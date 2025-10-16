# Ticket 10: Final Documentation & Maintenance

## Objective
Create comprehensive maintenance documentation, update procedures, and troubleshooting guides for long-term operation.

## Tasks

### 1. Create Maintenance Guide

Create `docs/MAINTENANCE.md`:

```markdown
# Dashboard Maintenance Guide

## Regular Maintenance Tasks

### Daily
- Monitor container health: `docker ps`
- Check Homepage is accessible

### Weekly
- Review logs for errors: `./scripts/health-check.sh`
- Check disk usage: `du -sh data/*`

### Monthly
- Backup configuration and databases: `./scripts/backup-dashboard.sh`
- Update containers: `./scripts/update-dashboard.sh`
- Review and rotate logs

### Quarterly
- Review and clean old data
- Update API keys if expired
- Test disaster recovery

## Backup Procedures

### Manual Backup
```bash
./scripts/backup-dashboard.sh
```

Creates timestamped backup in `./backups/`

### Automated Backup (Recommended)

Add to crontab:
```bash
# Backup every Sunday at 2 AM
0 2 * * 0 cd /path/to/home-server-stack && ./scripts/backup-dashboard.sh
```

### What Gets Backed Up
- Homepage configuration files
- Home Assistant configuration and database
- Habitica MongoDB database
- Environment variables (.env)

### What's NOT Backed Up
- Docker images (can be re-pulled)
- Temporary files
- Logs (optional to include)

## Update Procedures

### Update All Services
```bash
./scripts/update-dashboard.sh
```

### Update Individual Service
```bash
# Pull latest image
docker compose -f docker-compose.dashboard.yml pull SERVICE_NAME

# Recreate container
docker compose -f docker-compose.dashboard.yml up -d SERVICE_NAME
```

### Update Backend API
```bash
# Rebuild after code changes
docker compose -f docker-compose.dashboard.yml build homepage-api
docker compose -f docker-compose.dashboard.yml up -d homepage-api
```

## Log Management

### View Logs
```bash
# All services
docker compose -f docker-compose.dashboard.yml logs

# Specific service
docker logs homepage
docker logs homeassistant
docker logs habitica
docker logs homepage-api

# Follow logs (real-time)
docker logs -f homepage-api

# Last 100 lines
docker logs --tail 100 habitica
```

### Rotate Logs
```bash
# Docker handles log rotation automatically
# Configure in /etc/docker/daemon.json:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Clear Old Logs
```bash
# Truncate logs for a container
truncate -s 0 $(docker inspect --format='{{.LogPath}}' homepage)
```

## Database Maintenance

### Habitica MongoDB

**Check Database Size:**
```bash
docker exec habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD --eval "db.stats()"
```

**Compact Database:**
```bash
docker exec habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD habitica --eval "db.runCommand({compact: 'users'})"
```

**Export Database:**
```bash
docker exec habitica-mongo mongodump \
  --username=$HABITICA_MONGO_USER \
  --password=$HABITICA_MONGO_PASSWORD \
  --out=/data/backup
  
docker cp habitica-mongo:/data/backup ./backups/habitica-mongo-$(date +%Y%m%d)
```

### Home Assistant Database

**Check Size:**
```bash
du -h data/homeassistant/home-assistant_v2.db
```

**Purge Old Data:**
```yaml
# In configuration.yaml
recorder:
  purge_keep_days: 30
  commit_interval: 30
```

Then restart HA: `docker restart homeassistant`

**Manual Purge:**
```bash
# In Home Assistant
# Developer Tools → Services
# Service: recorder.purge
# Service Data: { "keep_days": 30, "repack": true }
```

## Monitoring

### Resource Usage
```bash
# Current usage
docker stats --no-stream

# Continuous monitoring
docker stats
```

### Disk Space
```bash
# Check available space
df -h

# Check data directory sizes
du -sh data/*

# Find large files
find data/ -type f -size +100M -exec ls -lh {} \;
```

### Container Health
```bash
# Health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Restart unhealthy containers
docker compose -f docker-compose.dashboard.yml restart SERVICE_NAME
```

## Security Maintenance

### Update SSL Certificates

**Self-Signed (Annual):**
```bash
cd ssl
./generate-habitica-cert.sh habitica.yourdomain.local
docker restart habitica-nginx
```

**Let's Encrypt (Automatic):**
```bash
# If using certbot with auto-renewal
sudo certbot renew --dry-run
```

### Rotate API Keys

When API keys need rotation:

1. Generate new key from provider
2. Update `.env` file
3. Restart affected services:
   ```bash
   docker compose -f docker-compose.dashboard.yml restart homepage homepage-api
   ```

### Review Access Logs

```bash
# Homepage API access
docker logs homepage-api | grep "GET\|POST"

# Home Assistant access
docker exec homeassistant cat /config/home-assistant.log | grep "Login"
```

## Performance Optimization

### Clear Caches

**Home Assistant:**
```bash
# Remove .storage cache (careful!)
docker exec homeassistant rm -rf /config/.storage/.cloud
docker restart homeassistant
```

**Docker:**
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Clean everything (careful!)
docker system prune -a --volumes
```

### Optimize Databases

**MongoDB:**
```bash
docker exec habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD habitica --eval "db.runCommand({reIndex: 'users'})"
```

**Home Assistant:**
```bash
# Use MariaDB/PostgreSQL instead of SQLite for better performance
# See Home Assistant documentation
```

## Disaster Recovery

### Restore from Backup

1. **Stop all services:**
   ```bash
   docker compose -f docker-compose.dashboard.yml down
   ```

2. **Extract backup:**
   ```bash
   tar -xzf backups/dashboard-TIMESTAMP.tar.gz -C ./
   ```

3. **Restore configurations:**
   ```bash
   cp -r backups/dashboard-TIMESTAMP/homepage-config/* data/homepage/config/
   cp -r backups/dashboard-TIMESTAMP/homeassistant/* data/homeassistant/
   ```

4. **Restore Habitica database:**
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d habitica-mongo
   sleep 10
   
   docker exec habitica-mongo mongorestore \
     --username=$HABITICA_MONGO_USER \
     --password=$HABITICA_MONGO_PASSWORD \
     backups/dashboard-TIMESTAMP/habitica-db
   ```

5. **Start services:**
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d
   ```

### Test Recovery Procedure

Periodically test your backups:
```bash
# Create test environment
mkdir -p /tmp/recovery-test
cd /tmp/recovery-test

# Extract backup
tar -xzf ~/home-server-stack/backups/dashboard-LATEST.tar.gz

# Verify files
ls -la

# Cleanup
cd ~
rm -rf /tmp/recovery-test
```

## Troubleshooting Common Issues

### Container Won't Start

1. Check logs: `docker logs CONTAINER_NAME`
2. Check port conflicts: `sudo netstat -tlnp | grep PORT`
3. Check disk space: `df -h`
4. Remove and recreate: `docker compose -f docker-compose.dashboard.yml up -d --force-recreate CONTAINER_NAME`

### High Resource Usage

1. Identify culprit: `docker stats`
2. Check logs for errors
3. Restart container: `docker restart CONTAINER_NAME`
4. Consider resource limits in docker-compose

### Database Corruption

**Habitica MongoDB:**
```bash
docker exec habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD habitica --eval "db.repairDatabase()"
```

**Home Assistant SQLite:**
```bash
docker exec homeassistant sqlite3 /config/home-assistant_v2.db "PRAGMA integrity_check;"
```

### Network Issues

1. Check network exists: `docker network inspect home-server`
2. Recreate network:
   ```bash
   docker compose -f docker-compose.dashboard.yml down
   docker network rm home-server
   docker network create home-server
   docker compose -f docker-compose.dashboard.yml up -d
   ```

## Monitoring Alerts

### Set Up Basic Monitoring

Create cron job for health checks:
```bash
# Check every 5 minutes, alert on failure
*/5 * * * * /path/to/home-server-stack/scripts/health-check.sh || echo "Dashboard health check failed" | mail -s "Alert" your@email.com
```

### Integration with External Monitoring

- **Uptime Kuma**: Self-hosted monitoring
- **Healthchecks.io**: Dead man's switch
- **Grafana**: Already installed, create dashboards

## Support & Resources

### Documentation
- Homepage: https://gethomepage.dev/
- Home Assistant: https://home-assistant.io/
- Habitica: https://habitica.fandom.com/

### Community
- Home Assistant Community: https://community.home-assistant.io/
- r/selfhosted: https://reddit.com/r/selfhosted
- Your GitHub repo issues

### Getting Help

When asking for help, provide:
1. Container logs: `docker logs CONTAINER_NAME`
2. Health check output: `./scripts/health-check.sh`
3. Docker version: `docker --version`
4. OS information: `uname -a`
5. Steps to reproduce the issue
```

### 2. Create Update Script

Create `scripts/update-dashboard.sh`:

```bash
#!/bin/bash
set -e

echo "🔄 Updating Dashboard Services"
echo "=============================="
echo ""

# Create backup first
echo "📦 Creating backup before update..."
./scripts/backup-dashboard.sh

# Pull latest images
echo ""
echo "⬇️  Pulling latest images..."
docker compose -f docker-compose.dashboard.yml pull

# Rebuild custom images
echo ""
echo "🔨 Rebuilding custom images..."
docker compose -f docker-compose.dashboard.yml build homepage-api

# Recreate containers with new images
echo ""
echo "🔄 Recreating containers..."
docker compose -f docker-compose.dashboard.yml up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 30

# Run health check
echo ""
echo "🏥 Running health check..."
./scripts/health-check.sh

echo ""
echo "✅ Update complete!"
echo ""
echo "📋 Updated services:"
docker compose -f docker-compose.dashboard.yml images
```

Make executable:
```bash
chmod +x scripts/update-dashboard.sh
```

### 3. Create Troubleshooting Guide

Create `docs/TROUBLESHOOTING.md`:

```markdown
# Troubleshooting Guide

## Quick Diagnostics

Run this first:
```bash
./scripts/health-check.sh
```

## Common Issues

### Homepage not accessible

**Symptoms:** Cannot load http://SERVER_IP:3100

**Solutions:**
1. Check container is running:
   ```bash
   docker ps | grep homepage
   ```

2. Check logs:
   ```bash
   docker logs homepage
   ```

3. Check port binding:
   ```bash
   sudo netstat -tlnp | grep 3100
   ```

4. Restart container:
   ```bash
   docker restart homepage
   ```

### Home Assistant not responding

**Symptoms:** http://SERVER_IP:8123 not loading

**Solutions:**
1. Check container:
   ```bash
   docker ps | grep homeassistant
   ```

2. Check logs for errors:
   ```bash
   docker logs homeassistant | tail -50
   ```

3. Check configuration:
   ```bash
   docker exec homeassistant hass --script check_config
   ```

4. Restart:
   ```bash
   docker restart homeassistant
   ```

### Habitica not accessible

**Symptoms:** HTTPS or HTTP not working

**Solutions:**
1. Check all Habitica containers:
   ```bash
   docker ps | grep habitica
   ```

2. Check MongoDB:
   ```bash
   docker logs habitica-mongo
   ```

3. Check Nginx logs:
   ```bash
   docker logs habitica-nginx
   ```

4. Test direct HTTP access:
   ```bash
   curl http://localhost:3000
   ```

5. Restart all:
   ```bash
   docker compose -f docker-compose.dashboard.yml restart habitica habitica-mongo habitica-redis habitica-nginx
   ```

### Backend API errors

**Symptoms:** Widgets showing errors, API returning 500

**Solutions:**
1. Check logs:
   ```bash
   docker logs homepage-api
   ```

2. Test health endpoint:
   ```bash
   curl http://localhost:5000/api/health
   ```

3. Check API keys in .env

4. Restart:
   ```bash
   docker restart homepage-api
   ```

### Transport NSW not showing data

**Symptoms:** Transport widgets empty or error

**Solutions:**
1. Verify API key:
   ```bash
   curl http://localhost:5000/api/health | jq '.services.transport_nsw'
   ```

2. Test stop ID manually:
   ```bash
   curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID
   ```

3. Check stop ID is correct (8 digits)

4. Verify API key in .env is correct

### Traffic not showing

**Symptoms:** Traffic widgets empty

**Solutions:**
1. Check TomTom API key:
   ```bash
   curl http://localhost:5000/api/health | jq '.services.tomtom'
   ```

2. Test geocoding:
   ```bash
   curl "http://localhost:5000/api/traffic/route?origin=North+Parramatta&destination=Sydney"
   ```

3. Verify addresses are complete

4. Check route schedule (route may be outside scheduled time)

### Habitica stats not showing in Homepage

**Symptoms:** Habitica widgets empty in Homepage

**Solutions:**
1. Verify HA token in .env

2. Check Habitica integration in HA:
   - Settings → Devices & Services → Habitica

3. Check entity names:
   - Developer Tools → States → search "habitica"

4. Update services.yaml with correct entity names

5. Restart Homepage:
   ```bash
   docker restart homepage
   ```

### Location tracking not working

**Symptoms:** Person entities show "unknown" or don't update

**Solutions:**
1. Check iOS app permissions:
   - Settings → Home Assistant → Location → Always
   - Enable Precise Location

2. Check HA companion app settings:
   - App → Settings → Companion App → Location

3. Enable Background App Refresh

4. Check person configuration in HA:
   - Settings → People

5. Verify device tracker entities exist:
   - Developer Tools → States → search "device_tracker"

### Fitness automation not working

**Symptoms:** Workouts not completing Habitica tasks

**Solutions:**
1. Check Health Auto Export:
   - Open app → Activity Log
   - Verify syncs are happening

2. Check webhook URL is correct

3. Test webhook manually (see Ticket 09)

4. Check HA logs:
   ```bash
   docker logs homeassistant | grep workout
   ```

5. Verify task IDs in automations are correct

### High CPU/Memory usage

**Symptoms:** Server slow, high resource usage

**Solutions:**
1. Identify culprit:
   ```bash
   docker stats
   ```

2. Check logs for errors/loops

3. Restart high-usage container

4. Consider adding resource limits:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1.0'
         memory: 512M
   ```

### Database errors

**Symptoms:** "Database locked" or corruption errors

**Solutions:**
1. **Home Assistant:**
   ```bash
   docker exec homeassistant sqlite3 /config/home-assistant_v2.db "PRAGMA integrity_check;"
   ```

2. **Habitica MongoDB:**
   ```bash
   docker exec habitica-mongo mongosh -u $HABITICA_MONGO_USER -p $HABITICA_MONGO_PASSWORD habitica --eval "db.repairDatabase()"
   ```

3. Restore from backup if corrupted

### Disk space issues

**Symptoms:** Containers failing, "No space left on device"

**Solutions:**
1. Check disk space:
   ```bash
   df -h
   ```

2. Clean Docker:
   ```bash
   docker system prune -a
   ```

3. Remove old logs:
   ```bash
   find data/ -name "*.log" -mtime +30 -delete
   ```

4. Purge HA database:
   - Developer Tools → Services
   - Service: recorder.purge
   - keep_days: 30

## Getting More Help

If issues persist:

1. Check all logs:
   ```bash
   docker compose -f docker-compose.dashboard.yml logs > debug.log
   ```

2. Run full health check:
   ```bash
   ./scripts/health-check.sh > health-report.txt
   ```

3. Create GitHub issue with:
   - Problem description
   - Steps to reproduce
   - Log files
   - Health check output
   - Docker/OS versions
```

### 4. Create Final Checklist

Create `docs/DEPLOYMENT_CHECKLIST.md`:

```markdown
# Deployment Checklist

Use this checklist to ensure complete deployment.

## Pre-Deployment

- [ ] Server meets minimum requirements (8GB RAM, 500GB storage)
- [ ] Docker and Docker Compose installed
- [ ] Static IP configured for server
- [ ] All API keys obtained:
  - [ ] Transport NSW API key
  - [ ] TomTom API key (optional)
  - [ ] Google Calendar iCal URL
- [ ] `.env` file created from `.env.example`
- [ ] All `.env` variables configured

## Core Deployment (Tickets 01-05)

- [ ] **Ticket 01**: Directory structure created
- [ ] **Ticket 02**: Homepage deployed and accessible
- [ ] **Ticket 03**: Home Assistant deployed and configured
- [ ] **Ticket 04**: Habitica deployed with HTTPS
- [ ] **Ticket 05**: Backend API deployed and healthy

## Integration (Tickets 06-08)

- [ ] **Ticket 06**: Transport widgets configured
- [ ] **Ticket 06**: Calendar widget showing events
- [ ] **Ticket 06**: Traffic widgets configured
- [ ] **Ticket 07**: All services integrated and tested
- [ ] **Ticket 08**: Habitica connected to Home Assistant
- [ ] **Ticket 08**: Habitica stats showing in Homepage

## Optional (Ticket 09)

- [ ] **Ticket 09**: iOS app installed on family devices
- [ ] **Ticket 09**: Location tracking working
- [ ] **Ticket 09**: Health Auto Export configured
- [ ] **Ticket 09**: Fitness automation working

## Post-Deployment

- [ ] Health check passing
- [ ] Backup created
- [ ] Documentation reviewed
- [ ] Maintenance schedule planned
- [ ] All family members onboarded

## Verification

- [ ] Homepage accessible at http://SERVER_IP:3100
- [ ] Home Assistant accessible at http://SERVER_IP:8123
- [ ] Habitica accessible at https://SERVER_IP
- [ ] Weather widget showing data
- [ ] Transport times displaying (if configured)
- [ ] Traffic data showing (if configured)
- [ ] Calendar events visible
- [ ] Docker containers visible
- [ ] Habitica stats displaying
- [ ] Location tracking working (if configured)
- [ ] No errors in logs

## Success Criteria

All services running:
```bash
docker ps | grep -E "homepage|homeassistant|habitica|homepage-api"
```

Health check passing:
```bash
./scripts/health-check.sh
```

All widgets displaying data in Homepage.

## Next Steps

1. Set up automated backups (cron job)
2. Configure monitoring/alerts
3. Add more transport stops as needed
4. Add more traffic routes as needed
5. Create Habitica tasks and configure automations
6. Customize Homepage theme/layout
7. Add more family members
8. Review maintenance schedule

## Support

See troubleshooting guide if issues: `docs/TROUBLESHOOTING.md`
```

## Acceptance Criteria
- [ ] Maintenance guide created with all procedures
- [ ] Update script created and tested
- [ ] Troubleshooting guide comprehensive
- [ ] Deployment checklist created
- [ ] All scripts documented
- [ ] Backup/restore procedures tested
- [ ] Monitoring guidelines provided
- [ ] Security maintenance documented
- [ ] Performance optimization tips included
- [ ] Disaster recovery procedure documented

## Testing
```bash
# Test update script (dry run concept)
./scripts/update-dashboard.sh

# Test backup
./scripts/backup-dashboard.sh
ls -lh backups/

# Verify all documentation
ls -1 docs/

# Ensure all scripts are executable
ls -l scripts/*.sh
```

## Dependencies
- All previous tickets completed
- System fully deployed and tested

## Notes
- This ticket focuses on long-term operation
- Maintenance procedures prevent issues
- Regular backups are critical
- Update procedures minimize downtime
- Troubleshooting guide saves time
- Security maintenance protects system
- Performance tips keep system responsive
- Create calendar reminders for maintenance tasks
- Consider automation for backups and updates
- Document any customizations made to the system