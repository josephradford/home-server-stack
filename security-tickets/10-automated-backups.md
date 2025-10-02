# Implement Automated Encrypted Backups

## Priority: 3 (Medium)
## Estimated Time: 4-6 hours
## Phase: Month 2 - Medium Priority Hardening

## Description
Implement automated encrypted backups using Restic with off-site storage. Follow the 3-2-1 backup rule: 3 copies, 2 different media types, 1 off-site.

## Acceptance Criteria
- [ ] Restic backup container deployed
- [ ] Daily automated backups configured
- [ ] Backups encrypted with strong passphrase
- [ ] Off-site backup target configured (S3/B2/etc)
- [ ] Backup monitoring and alerts
- [ ] Restoration tested and documented
- [ ] Backup retention policy (7 daily, 4 weekly, 12 monthly)

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.backup.yml` - Backup service (new file)
2. `backup/restic-backup.sh` - Backup script (new file)
3. `backup/restic-restore.sh` - Restore script (new file)
4. `.env.example` - Add backup configuration
5. `docs/BACKUP_RESTORE.md` - Procedures (new file)

**docker-compose.backup.yml:**
```yaml
services:
  restic:
    image: restic/restic:0.16.2@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: restic-backup
    restart: "no"  # Run via cron
    environment:
      - RESTIC_REPOSITORY=${BACKUP_REPOSITORY}
      - RESTIC_PASSWORD_FILE=/run/secrets/restic_password
      - AWS_ACCESS_KEY_ID=${BACKUP_ACCESS_KEY}
      - AWS_SECRET_ACCESS_KEY=${BACKUP_SECRET_KEY}
      - BACKUP_RETENTION_DAYS=7
      - BACKUP_RETENTION_WEEKS=4
      - BACKUP_RETENTION_MONTHS=12
    volumes:
      - ./data:/data:ro
      - ./backup:/backup
      - ./backup/restic-password:/run/secrets/restic_password:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - backend
    command: backup /data
```

**backup/restic-backup.sh:**
```bash
#!/bin/bash
# Automated backup script using Restic

set -e

BACKUP_NAME="home-server-$(date +%Y%m%d-%H%M%S)"
RESTIC_REPOSITORY="${BACKUP_REPOSITORY:-s3:s3.amazonaws.com/your-bucket/restic}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-/backup/restic-password}"

echo "🔐 Starting encrypted backup: $BACKUP_NAME"

# Initialize repository if it doesn't exist
restic snapshots > /dev/null 2>&1 || restic init

# Pre-backup: Stop containers for consistency (optional)
# docker compose stop n8n ollama

# Backup data directories
restic backup \
  --tag automated \
  --tag daily \
  --host homeserver \
  /data/adguard \
  /data/n8n \
  /data/ollama \
  /data/grafana \
  /data/prometheus

# Backup configurations
restic backup \
  --tag config \
  --exclude='*.log' \
  --exclude='*.tmp' \
  /opt/home-server-stack/docker-compose*.yml \
  /opt/home-server-stack/.env \
  /opt/home-server-stack/monitoring \
  /opt/home-server-stack/ssl

# Post-backup: Restart containers
# docker compose start n8n ollama

# Apply retention policy
restic forget \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 12 \
  --keep-yearly 3 \
  --prune

# Verify backup integrity (weekly only)
if [ "$(date +%u)" -eq 1 ]; then
  echo "Running weekly backup verification..."
  restic check --read-data-subset=10%
fi

# Show backup stats
restic stats

echo "✅ Backup completed successfully!"

# Send notification (optional)
curl -X POST ${HEALTHCHECK_URL} || true
```

## Testing Commands
```bash
# Initialize backup repository
export RESTIC_REPOSITORY="s3:s3.amazonaws.com/your-bucket"
export RESTIC_PASSWORD="your-strong-passphrase"
restic init

# Run manual backup
./backup/restic-backup.sh

# List snapshots
restic snapshots

# Restore specific file
restic restore latest --target /tmp/restore --include /data/n8n/workflows.json

# Test restoration
./backup/restic-restore.sh --snapshot latest --target /tmp/restore-test
```

See full implementation in ticket for complete configuration.

## Success Metrics
- Daily backups completing successfully
- Backups encrypted and stored off-site
- Restoration tested and working
- Backup size and duration monitored
- Alerts on backup failures

## References
- [Restic Documentation](https://restic.readthedocs.io/)
- [3-2-1 Backup Rule](https://www.backblaze.com/blog/the-3-2-1-backup-strategy/)
