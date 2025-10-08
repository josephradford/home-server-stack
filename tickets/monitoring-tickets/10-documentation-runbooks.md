# Create Documentation and Runbooks

## Priority: 4 (Low)
## Estimated Time: 4-5 hours
## Phase: Week 4 - Optimization & Documentation

## Description
Create comprehensive documentation, operational runbooks, troubleshooting guides, and backup/recovery procedures for the complete monitoring infrastructure to ensure sustainable operations and knowledge transfer.

## Acceptance Criteria
- [ ] Complete monitoring architecture documentation
- [ ] Alert response runbooks for all critical alerts
- [ ] Troubleshooting guides for common issues
- [ ] Backup and recovery procedures
- [ ] Performance tuning guide
- [ ] Onboarding documentation for new team members
- [ ] Maintenance schedules and procedures
- [ ] Security considerations and compliance documentation

## Technical Implementation Details

### Files to Create
1. `docs/monitoring/README.md` - Main monitoring documentation
2. `docs/monitoring/architecture.md` - System architecture overview
3. `docs/monitoring/runbooks/` - Directory for operational runbooks
4. `docs/monitoring/troubleshooting.md` - Common issues and solutions
5. `docs/monitoring/backup-recovery.md` - Backup and disaster recovery
6. `docs/monitoring/performance-tuning.md` - Optimization guidelines
7. `docs/monitoring/security.md` - Security best practices
8. `scripts/backup-monitoring.sh` - Automated backup script

### Main Monitoring Documentation (`docs/monitoring/README.md`)
```markdown
# Home Server Monitoring Stack

## Overview
This document provides comprehensive information about the monitoring infrastructure for the home server stack, including AdGuard Home, n8n, and Ollama services.

## Quick Start
```bash
# Start monitoring stack
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Access interfaces
# Grafana: http://SERVER_IP:3001 (admin/GRAFANA_PASSWORD)
# Prometheus: http://SERVER_IP:9090
# AlertManager: http://SERVER_IP:9093

# View service status
docker compose ps
```

## Architecture
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **Loki**: Log aggregation and analysis
- **AlertManager**: Alert routing and notifications
- **Blackbox Exporter**: External endpoint monitoring
- **Custom Exporters**: Service-specific metrics (AdGuard, n8n, Ollama)

## Service URLs
| Service | URL | Purpose |
|---------|-----|---------|
| Grafana | http://SERVER_IP:3001 | Dashboards and visualization |
| Prometheus | http://SERVER_IP:9090 | Metrics and queries |
| AlertManager | http://SERVER_IP:9093 | Alert management |
| Loki | http://SERVER_IP:3100 | Log queries |

## Key Dashboards
- **System Overview**: Overall infrastructure health
- **Container Health**: Docker container monitoring
- **AdGuard Home**: DNS and filtering statistics
- **n8n Workflows**: Automation monitoring
- **Ollama AI**: AI model performance
- **Logs Overview**: Centralized log analysis

## Alert Categories
- **Critical**: Service down, resource exhaustion
- **Warning**: Performance degradation, high usage
- **Info**: Maintenance events, configuration changes

## Documentation Structure
- [Architecture Overview](architecture.md)
- [Runbooks](runbooks/)
- [Troubleshooting Guide](troubleshooting.md)
- [Backup & Recovery](backup-recovery.md)
- [Performance Tuning](performance-tuning.md)
- [Security Considerations](security.md)

## Support
For issues with the monitoring stack, check the troubleshooting guide or create an issue in the repository.
```

### Architecture Documentation (`docs/monitoring/architecture.md`)
```markdown
# Monitoring Architecture

## System Overview
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AdGuard Home  │    │       n8n       │    │     Ollama      │
│     :80,:53     │    │     :5678       │    │     :11434      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐             │
         └──────────────▶│   Prometheus    │◀────────────┘
                        │     :9090       │
                        └─────────────────┘
                                 │
         ┌─────────────────┬─────┴─────┬─────────────────┐
         ▼                 ▼           ▼                 ▼
┌─────────────────┐┌─────────────────┐┌─────────────────┐┌─────────────────┐
│    Grafana      ││  AlertManager   ││      Loki       ││ Blackbox Export │
│     :3001       ││     :9093       ││     :3100       ││     :9115       │
└─────────────────┘└─────────────────┘└─────────────────┘└─────────────────┘
         │                 │                       ▲
         │                 │              ┌─────────────────┐
         │                 │              │    Promtail     │
         │                 │              │     :9080       │
         │                 │              └─────────────────┘
         │                 │                       │
         ▼                 ▼                       │
┌─────────────────┐┌─────────────────┐             │
│    Dashboards   ││  Notifications  │             │
│   & Queries     ││   (Slack/Email) │             │
└─────────────────┘└─────────────────┘             │
                                                   │
                                          ┌─────────────────┐
                                          │   Docker Logs   │
                                          │  & System Logs  │
                                          └─────────────────┘
```

## Component Details

### Prometheus (Metrics)
- **Role**: Central metrics collection and storage
- **Data Sources**: Node Exporter, cAdvisor, Custom Exporters
- **Retention**: 30 days, 50GB limit
- **Queries**: PromQL for analysis and alerting

### Grafana (Visualization)
- **Role**: Dashboard and visualization platform
- **Data Sources**: Prometheus, Loki
- **Authentication**: Admin user with basic auth
- **Dashboards**: Pre-configured for all services

### Loki (Logs)
- **Role**: Log aggregation and storage
- **Data Sources**: Docker logs, system logs via Promtail
- **Retention**: 3 days
- **Queries**: LogQL for log analysis

### AlertManager (Notifications)
- **Role**: Alert routing and notification management
- **Receivers**: Slack, Email
- **Features**: Grouping, inhibition, silencing

## Data Flow
1. **Metrics**: Services → Exporters → Prometheus → Grafana
2. **Logs**: Services → Docker → Promtail → Loki → Grafana
3. **Alerts**: Prometheus → AlertManager → Notifications

## Network Architecture
- All services run in `homeserver` Docker network
- External access through configured ports
- Internal communication via container names

## Storage
- **Prometheus**: Time-series database with compression
- **Grafana**: SQLite for dashboards and users
- **Loki**: BoltDB for indexes, filesystem for chunks

## Security
- Basic authentication for web interfaces
- Internal network isolation
- SSL/TLS for external endpoints
- No external exposure of sensitive metrics
```

### Alert Response Runbooks

#### Critical Service Down Runbook (`docs/monitoring/runbooks/service-down.md`)
```markdown
# Service Down Alert Response

## Alert: ServiceDown / EndpointDown

### Immediate Actions (0-5 minutes)
1. **Verify Alert Legitimacy**
   ```bash
   # Check service status
   docker compose ps

   # Check specific service
   docker logs <service_name> --tail 20
   ```

2. **Quick Assessment**
   - Is this a planned maintenance?
   - Are multiple services affected?
   - Is the host system responsive?

### Investigation Steps (5-15 minutes)
1. **Check Container Status**
   ```bash
   # View container status
   docker ps -a | grep <service>

   # Check resource usage
   docker stats --no-stream
   ```

2. **Review Logs**
   ```bash
   # Service logs
   docker logs <service> --since 30m

   # System logs
   journalctl -u docker --since "30 minutes ago"
   ```

3. **Check System Resources**
   ```bash
   # CPU and memory
   top

   # Disk space
   df -h

   # Network connectivity
   ping 8.8.8.8
   ```

### Resolution Steps
1. **Container Restart**
   ```bash
   # Restart specific service
   docker compose restart <service>

   # Restart entire stack if needed
   docker compose down && docker compose up -d
   ```

2. **Resource Issues**
   ```bash
   # Free up disk space
   docker system prune -f

   # Clear logs if needed
   sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
   ```

3. **Configuration Issues**
   ```bash
   # Validate configuration
   docker compose config

   # Check environment variables
   docker compose config | grep -A5 -B5 <service>
   ```

### Post-Resolution
1. **Verify Service Health**
   - Check all dashboards
   - Verify alerts have cleared
   - Test service functionality

2. **Document Incident**
   - Root cause analysis
   - Timeline of events
   - Preventive measures

### Escalation
If service cannot be restored within 30 minutes:
1. Consider system reboot
2. Check hardware issues
3. Contact infrastructure team
```

#### High Resource Usage Runbook (`docs/monitoring/runbooks/high-resource-usage.md`)
```markdown
# High Resource Usage Alert Response

## Alert: HighCPUUsage / HighMemoryUsage / DiskSpaceLow

### Immediate Assessment (0-2 minutes)
1. **Check Current Usage**
   ```bash
   # Overall system resources
   htop

   # Container resources
   docker stats --no-stream
   ```

2. **Identify Top Consumers**
   ```bash
   # CPU usage by process
   ps aux --sort=-%cpu | head -10

   # Memory usage by process
   ps aux --sort=-%mem | head -10

   # Disk usage by directory
   du -sh /* | sort -hr | head -10
   ```

### Investigation Steps (2-10 minutes)
1. **Analyze Trends**
   - Check Grafana for usage patterns
   - Look for sudden spikes or gradual increases
   - Correlate with service activity

2. **Service-Specific Checks**
   ```bash
   # Ollama model usage
   docker exec ollama ollama ps

   # n8n active workflows
   docker logs n8n | grep -i "workflow"

   # AdGuard query volume
   docker logs adguard | grep -i "queries"
   ```

### Resolution Actions
1. **CPU Issues**
   ```bash
   # Identify CPU-intensive processes
   top -o %CPU

   # Reduce Ollama concurrency if needed
   docker exec ollama ollama stop <model>

   # Restart CPU-intensive service
   docker compose restart <service>
   ```

2. **Memory Issues**
   ```bash
   # Clear system cache
   sync && echo 3 > /proc/sys/vm/drop_caches

   # Restart memory-intensive services
   docker compose restart ollama

   # Check for memory leaks in logs
   docker logs <service> | grep -i "memory\|oom"
   ```

3. **Disk Space Issues**
   ```bash
   # Clean Docker resources
   docker system prune -af --volumes

   # Clear old logs
   find /var/log -name "*.log" -mtime +7 -delete

   # Clean monitoring data if needed
   docker exec prometheus rm -rf /prometheus/wal/*
   ```

### Prevention Measures
1. **Set Resource Limits**
   - Update docker-compose with memory limits
   - Configure CPU limits for services

2. **Monitoring Improvements**
   - Set up predictive alerting
   - Monitor growth trends

3. **Maintenance Scheduling**
   - Regular cleanup schedules
   - Automated resource management
```

### Troubleshooting Guide (`docs/monitoring/troubleshooting.md`)
```markdown
# Monitoring Stack Troubleshooting

## Common Issues and Solutions

### 1. Grafana Dashboard Not Loading
**Symptoms**: Dashboard shows "No data" or loading errors

**Possible Causes**:
- Prometheus data source not configured
- Network connectivity issues
- Query timeout

**Solutions**:
```bash
# Check Prometheus connectivity
curl http://localhost:9090/api/v1/query?query=up

# Test Grafana data source
docker logs grafana | grep -i "error\|fail"

# Restart Grafana
docker compose restart grafana
```

### 2. Prometheus Not Scraping Targets
**Symptoms**: Targets show as "DOWN" in Prometheus

**Solutions**:
```bash
# Check target status
curl http://localhost:9090/api/v1/targets

# Verify network connectivity
docker exec prometheus nc -zv <target_host> <target_port>

# Check configuration
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### 3. Alerts Not Firing
**Symptoms**: Expected alerts not triggering

**Solutions**:
```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Validate alert syntax
docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml

# Check AlertManager
curl http://localhost:9093/api/v1/alerts
```

### 4. High Memory Usage by Monitoring Stack
**Symptoms**: Monitoring containers consuming excessive memory

**Solutions**:
```bash
# Check container memory usage
docker stats --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Reduce Prometheus retention
# Edit prometheus.yml: --storage.tsdb.retention.time=15d

# Optimize Grafana
# Add to grafana environment: GF_ANALYTICS_REPORTING_ENABLED=false
```

### 5. Loki Log Ingestion Issues
**Symptoms**: Logs not appearing in Grafana

**Solutions**:
```bash
# Check Promtail status
docker logs promtail | grep -i "error"

# Test Loki connectivity
curl http://localhost:3100/ready

# Verify log paths
docker exec promtail ls -la /var/lib/docker/containers/
```

## Performance Optimization

### Query Optimization
- Use recording rules for complex calculations
- Limit time ranges in dashboards
- Use appropriate step intervals

### Storage Optimization
- Regular cleanup of old data
- Optimize retention policies
- Use compression where available

### Resource Management
- Set appropriate resource limits
- Monitor resource usage trends
- Scale resources based on load

## Maintenance Tasks

### Daily
- Check service health
- Review critical alerts
- Monitor resource usage

### Weekly
- Review dashboard performance
- Clean up old data
- Update documentation

### Monthly
- Performance optimization review
- Security updates
- Backup verification
```

### Backup and Recovery Procedures (`docs/monitoring/backup-recovery.md`)
```markdown
# Backup and Recovery Procedures

## Backup Strategy

### What to Backup
1. **Configuration Files**
   - All files in `monitoring/` directory
   - `docker-compose.monitoring.yml`
   - Environment files

2. **Critical Data**
   - Grafana dashboards and datasources
   - Prometheus configuration and rules
   - AlertManager configuration

3. **Historical Data** (Optional)
   - Prometheus metrics data
   - Grafana database

### Automated Backup Script

Create `scripts/backup-monitoring.sh`:
```bash
#!/bin/bash

BACKUP_DIR="/opt/monitoring-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/monitoring_backup_$DATE"

# Create backup directory
mkdir -p "$BACKUP_PATH"

echo "Starting monitoring backup..."

# Backup configurations
cp -r monitoring/ "$BACKUP_PATH/"
cp docker-compose.monitoring.yml "$BACKUP_PATH/"
cp .env "$BACKUP_PATH/env.example"

# Backup Grafana data
docker exec grafana grafana-cli admin export-dashboard > "$BACKUP_PATH/grafana_dashboards.json"

# Backup Prometheus config
docker exec prometheus cat /etc/prometheus/prometheus.yml > "$BACKUP_PATH/prometheus.yml"

# Create archive
tar -czf "$BACKUP_PATH.tar.gz" -C "$BACKUP_DIR" "monitoring_backup_$DATE"
rm -rf "$BACKUP_PATH"

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "monitoring_backup_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_PATH.tar.gz"
```

### Recovery Procedures

#### Complete System Recovery
```bash
# 1. Stop all monitoring services
docker compose -f docker-compose.monitoring.yml down

# 2. Restore configuration files
tar -xzf monitoring_backup_YYYYMMDD_HHMMSS.tar.gz
cp -r monitoring_backup_YYYYMMDD_HHMMSS/* ./

# 3. Restart services
docker compose -f docker-compose.monitoring.yml up -d

# 4. Verify services
docker compose ps
curl http://localhost:9090/-/healthy
curl http://localhost:3001/api/health
```

#### Selective Recovery

**Grafana Dashboards**:
```bash
# Import dashboard via API
curl -X POST http://admin:password@localhost:3001/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @dashboard.json
```

**Prometheus Configuration**:
```bash
# Copy configuration
docker cp prometheus.yml prometheus:/etc/prometheus/

# Reload configuration
curl -X POST http://localhost:9090/-/reload
```

### Disaster Recovery Plan

#### RTO/RPO Targets
- **Recovery Time Objective (RTO)**: 30 minutes
- **Recovery Point Objective (RPO)**: 1 hour

#### Recovery Steps
1. **Assessment** (5 minutes)
   - Determine scope of failure
   - Identify recoverable components

2. **Infrastructure Recovery** (15 minutes)
   - Restore Docker environment
   - Recover configuration files

3. **Service Recovery** (10 minutes)
   - Start monitoring services
   - Verify connectivity

4. **Validation** (5 minutes)
   - Test all dashboards
   - Verify alerting

### Testing Recovery
```bash
# Test backup script
./scripts/backup-monitoring.sh

# Test restore (in test environment)
# 1. Copy current config
cp -r monitoring monitoring.backup

# 2. Restore from backup
tar -xzf monitoring_backup_test.tar.gz
cp -r monitoring_backup_test/monitoring ./

# 3. Test services
docker compose -f docker-compose.monitoring.yml up -d

# 4. Restore original
rm -rf monitoring
mv monitoring.backup monitoring
```
```

### Performance Tuning Guide (`docs/monitoring/performance-tuning.md`)
```markdown
# Performance Tuning Guide

## Prometheus Optimization

### Query Performance
```yaml
# Prometheus configuration optimizations
global:
  scrape_interval: 30s          # Increase from 15s
  evaluation_interval: 30s      # Increase from 15s

# Storage optimizations
storage:
  tsdb:
    retention.time: 30d         # Reduce from 90d
    retention.size: 50GB        # Set size limit
    wal_compression: true       # Enable compression
```

### Recording Rules
Create pre-calculated metrics for expensive queries:
```yaml
groups:
  - name: performance_rules
    interval: 30s
    rules:
      - record: homeserver:cpu_usage
        expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

## Grafana Optimization

### Dashboard Performance
- Use template variables to reduce query load
- Implement appropriate time ranges
- Use recording rules for complex calculations
- Limit concurrent panel queries

### Configuration Optimizations
```ini
# grafana.ini optimizations
[database]
wal = true

[dashboards]
min_refresh_interval = 5s

[panels]
disable_sanitize_html = false
```

## Loki Optimization

### Ingestion Performance
```yaml
# Optimized limits
limits_config:
  ingestion_rate_mb: 8
  ingestion_burst_size_mb: 16
  max_query_parallelism: 16
```

### Query Performance
- Use specific time ranges
- Filter by labels early
- Avoid regex when possible
- Use `|=` instead of `|~` for exact matches

## Resource Management

### Container Limits
```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: "1.0"
    reservations:
      memory: 1G
      cpus: "0.5"
```

### Host Optimizations
```bash
# Increase file descriptors
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize kernel parameters
echo "vm.max_map_count=262144" >> /etc/sysctl.conf
sysctl -p
```

## Monitoring the Monitoring

### Key Metrics to Track
- Prometheus query duration
- Grafana response times
- Loki ingestion rate
- Memory usage by service
- Disk I/O patterns

### Performance Alerts
```yaml
- alert: MonitoringStackSlowQueries
  expr: histogram_quantile(0.99, rate(prometheus_engine_query_duration_seconds_bucket[5m])) > 5
  for: 5m
  annotations:
    summary: "Slow Prometheus queries detected"
```
```

### Security Guide (`docs/monitoring/security.md`)
```markdown
# Security Considerations

## Access Control

### Authentication
- Grafana: Basic authentication with strong passwords
- Prometheus: Network-level access control
- AlertManager: No authentication (internal network only)

### Network Security
```yaml
# Docker network isolation
networks:
  homeserver:
    driver: bridge
    internal: false  # Set to true for full isolation
```

## Data Security

### Sensitive Information
- Never expose credentials in dashboards
- Use environment variables for secrets
- Implement log filtering for sensitive data

### Encryption
- Use HTTPS for external access
- Encrypt backup files
- Secure notification channels

## Compliance

### Data Retention
- Define retention policies
- Implement automated cleanup
- Document data handling procedures

### Audit Logging
- Monitor access to monitoring interfaces
- Log configuration changes
- Track alert acknowledgments

## Security Monitoring

### Security Alerts
```yaml
- alert: UnauthorizedAccess
  expr: increase(grafana_api_login_failures_total[5m]) > 5
  annotations:
    summary: "Multiple failed login attempts detected"

- alert: ConfigurationChanged
  expr: increase(prometheus_config_last_reload_successful[1m]) > 0
  annotations:
    summary: "Prometheus configuration was reloaded"
```

### Best Practices
1. Regular security updates
2. Minimal privilege access
3. Network segmentation
4. Encrypted communications
5. Regular security audits
```

## Success Metrics
- Complete documentation coverage for all monitoring components
- Runbooks for all critical alerts
- Mean time to resolution under 15 minutes for documented issues
- Backup and recovery procedures tested successfully
- All team members can use documentation to operate the system

## Dependencies
- Completed: All monitoring implementation tickets
- Access to create documentation structure
- Testing environment for validating procedures

## Risk Considerations
- Outdated documentation becoming misleading
- Runbooks not matching actual system behavior
- Recovery procedures not tested regularly
- Security practices not followed consistently

## Maintenance Plan
- Review documentation quarterly
- Test recovery procedures monthly
- Update runbooks after incidents
- Security review annually