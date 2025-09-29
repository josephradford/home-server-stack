# Monitoring Stack Performance Optimization

## Priority: 4 (Low)
## Estimated Time: 3-4 hours
## Phase: Week 4 - Optimization & Documentation

## Description
Optimize the monitoring stack performance by tuning retention policies, fine-tuning alert thresholds, optimizing dashboard queries, and implementing efficient storage strategies to ensure sustainable long-term operation.

## Acceptance Criteria
- [ ] Optimized retention policies for metrics and logs
- [ ] Tuned alert thresholds to reduce false positives
- [ ] Optimized dashboard query performance
- [ ] Implemented efficient storage compression
- [ ] Configured resource limits for monitoring services
- [ ] Automated cleanup processes for old data
- [ ] Performance monitoring for the monitoring stack itself
- [ ] Documented optimization best practices

## Technical Implementation Details

### Files to Create/Modify
1. `monitoring/prometheus/prometheus.yml` - Optimize scraping and retention
2. `monitoring/loki/loki.yml` - Optimize log retention and compression
3. `monitoring/grafana/dashboards/monitoring-performance.json` - Monitor the monitoring stack
4. `docker-compose.monitoring.yml` - Add resource limits and optimizations
5. `scripts/monitoring-maintenance.sh` - Automated maintenance script
6. `monitoring/config/retention-policies.yml` - Centralized retention configuration

### Prometheus Optimizations

#### Updated Prometheus Configuration (`monitoring/prometheus/prometheus.yml`)
```yaml
global:
  scrape_interval: 30s          # Increased from 15s to reduce load
  evaluation_interval: 30s      # Increased from 15s
  external_labels:
    monitor: 'homeserver'
    environment: 'production'

# Storage optimizations
storage:
  tsdb:
    retention.time: 30d         # Keep 30 days of data
    retention.size: 50GB        # Limit storage to 50GB
    min_block_duration: 2h      # Optimize block size
    max_block_duration: 25h     # Optimize block size
    wal_compression: true       # Enable WAL compression

rule_files:
  - "alert_rules.yml"
  - "recording_rules.yml"      # Add recording rules for efficiency

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Optimized scrape intervals by service importance
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 60s        # Less frequent for self-monitoring

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 30s        # Standard interval for system metrics

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
    scrape_interval: 30s

  # High-frequency monitoring for critical services
  - job_name: 'adguard-exporter'
    static_configs:
      - targets: ['adguard-exporter:9617']
    scrape_interval: 30s

  - job_name: 'n8n-exporter'
    static_configs:
      - targets: ['n8n-exporter:9618']
    scrape_interval: 45s        # Slightly less frequent

  - job_name: 'ollama-exporter'
    static_configs:
      - targets: ['ollama-exporter:9619']
    scrape_interval: 60s        # Less frequent for AI metrics

  # Blackbox monitoring optimized
  - job_name: 'blackbox'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - http://adguard:80
        - http://prometheus:9090
        - http://grafana:3000
        - http://ollama:11434
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
    scrape_interval: 60s        # Reduced frequency for endpoint checks

# Recording rules for optimization
recording_rules:
  - name: node_recording_rules
    interval: 30s
    rules:
      - record: homeserver:node_cpu_utilization
        expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

      - record: homeserver:node_memory_utilization
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

      - record: homeserver:node_disk_utilization
        expr: 100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)

  - name: container_recording_rules
    interval: 30s
    rules:
      - record: homeserver:container_cpu_usage
        expr: rate(container_cpu_usage_seconds_total{name=~".+"}[5m]) * 100

      - record: homeserver:container_memory_usage
        expr: container_memory_usage_bytes{name=~".+"}
```

#### Recording Rules (`monitoring/prometheus/recording_rules.yml`)
```yaml
groups:
  - name: efficiency_rules
    interval: 30s
    rules:
      # Pre-calculate commonly used metrics
      - record: homeserver:service_availability
        expr: avg_over_time(up[5m])
        labels:
          metric_type: "availability"

      - record: homeserver:error_rate_5m
        expr: |
          (
            sum(rate(prometheus_notifications_total{instance="alertmanager:9093"}[5m])) by (instance)
            /
            sum(rate(prometheus_notifications_total[5m])) by (instance)
          )

      - record: homeserver:disk_usage_trend
        expr: |
          predict_linear(
            homeserver:node_disk_utilization[1h],
            24 * 3600
          )

      # Dashboard optimization rules
      - record: dashboard:response_time_p95
        expr: histogram_quantile(0.95, rate(prometheus_http_request_duration_seconds_bucket[5m]))

      - record: dashboard:query_rate
        expr: rate(prometheus_engine_queries_total[5m])
```

### Loki Optimizations

#### Updated Loki Configuration (`monitoring/loki/loki.yml`)
```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  log_level: warn              # Reduce log verbosity

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s

  # Optimized chunk settings
  chunk_idle_period: 30m       # Reduced from 1h
  max_chunk_age: 2h           # Increased from 1h
  chunk_target_size: 1572864  # 1.5MB optimized size
  chunk_retain_period: 30s
  max_transfer_retries: 0

# Optimized storage configuration
storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    cache_ttl: 24h
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

# Enhanced compaction
compactor:
  working_directory: /loki/boltdb-shipper-compactor
  shared_store: filesystem
  compaction_interval: 10m     # More frequent compaction
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

# Stricter limits for performance
limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 24h    # Reduced from 168h
  ingestion_rate_mb: 8               # Reduced from 16
  ingestion_burst_size_mb: 16        # Reduced from 32
  max_query_length: 168h             # Reduced from 720h
  max_query_parallelism: 16          # Reduced from 32
  max_streams_per_user: 5000         # Reduced from 10000
  max_line_size: 128KB               # Reduced from 256KB
  max_entries_limit_per_query: 5000
  max_query_series: 500

# Optimized retention
chunk_store_config:
  max_look_back_period: 24h          # Reduced from 168h

table_manager:
  retention_deletes_enabled: true
  retention_period: 72h              # Reduced from 168h (3 days)

# Query optimization
query_range:
  align_queries_with_step: true
  cache_results: true
  max_retries: 5

querier:
  max_concurrent: 4                  # Limit concurrent queries
```

### Resource Limits and Optimizations

#### Updated docker-compose.monitoring.yml with Resource Limits
```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--storage.tsdb.retention.size=50GB'
      - '--storage.tsdb.wal-compression'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
      - '--query.max-concurrency=4'
      - '--query.max-samples=50000000'
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1.0"
        reservations:
          memory: 1G
          cpus: "0.5"
    networks:
      - homeserver

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_ANALYTICS_REPORTING_ENABLED=false
      - GF_ANALYTICS_CHECK_FOR_UPDATES=false
      - GF_LOG_LEVEL=warn
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "0.5"
        reservations:
          memory: 512M
          cpus: "0.25"
    networks:
      - homeserver

  loki:
    image: grafana/loki:latest
    container_name: loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki:/etc/loki
      - loki_data:/loki
    command: -config.file=/etc/loki/loki.yml
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "0.5"
        reservations:
          memory: 512M
          cpus: "0.25"
    networks:
      - homeserver

  # Additional monitoring services with resource limits...
```

### Performance Monitoring Dashboard

#### Monitoring Stack Performance Dashboard
Create `monitoring/grafana/dashboards/monitoring-performance.json` with panels:

1. **Resource Usage**:
   - Prometheus memory usage
   - Grafana response times
   - Loki ingestion rates
   - Disk usage by service

2. **Query Performance**:
   - Prometheus query duration
   - Dashboard load times
   - Most expensive queries
   - Query concurrency

3. **Storage Efficiency**:
   - Storage growth rate
   - Compression ratios
   - Retention effectiveness
   - Disk I/O patterns

4. **Alert Performance**:
   - Alert evaluation time
   - False positive rates
   - Alert delivery times
   - Rule efficiency

### Automated Maintenance Script

#### Create `scripts/monitoring-maintenance.sh`
```bash
#!/bin/bash

# Monitoring Stack Maintenance Script
# Automated cleanup and optimization tasks

set -e

LOG_FILE="/var/log/monitoring-maintenance.log"
PROMETHEUS_URL="http://localhost:9090"
GRAFANA_URL="http://localhost:3001"
LOKI_URL="http://localhost:3100"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check service health
check_service_health() {
    local service_name="$1"
    local health_url="$2"

    if curl -f -s "$health_url" > /dev/null; then
        log "✅ $service_name is healthy"
        return 0
    else
        log "❌ $service_name health check failed"
        return 1
    fi
}

# Function to cleanup old metrics
cleanup_prometheus() {
    log "Starting Prometheus cleanup..."

    # Trigger compaction
    curl -X POST "$PROMETHEUS_URL/api/v1/admin/tsdb/snapshot"

    # Clean tombstones
    curl -X POST "$PROMETHEUS_URL/api/v1/admin/tsdb/clean_tombstones"

    log "Prometheus cleanup completed"
}

# Function to optimize Loki
optimize_loki() {
    log "Starting Loki optimization..."

    # Trigger compactor
    curl -X POST "$LOKI_URL/loki/api/v1/push" || true

    # Check Loki status
    check_service_health "Loki" "$LOKI_URL/ready"

    log "Loki optimization completed"
}

# Function to cleanup Grafana
cleanup_grafana() {
    log "Starting Grafana cleanup..."

    # Cleanup old sessions (if accessible)
    # Note: This would require Grafana API access

    check_service_health "Grafana" "$GRAFANA_URL/api/health"

    log "Grafana cleanup completed"
}

# Function to check disk usage
check_disk_usage() {
    log "Checking disk usage..."

    local prometheus_size=$(du -sh /var/lib/docker/volumes/*prometheus_data*/_data 2>/dev/null | cut -f1)
    local grafana_size=$(du -sh /var/lib/docker/volumes/*grafana_data*/_data 2>/dev/null | cut -f1)
    local loki_size=$(du -sh /var/lib/docker/volumes/*loki_data*/_data 2>/dev/null | cut -f1)

    log "📊 Storage usage:"
    log "   Prometheus: ${prometheus_size:-N/A}"
    log "   Grafana: ${grafana_size:-N/A}"
    log "   Loki: ${loki_size:-N/A}"

    # Check if any volume is getting too large (>40GB)
    if [[ $(du -s /var/lib/docker/volumes/*prometheus_data*/_data 2>/dev/null | cut -f1) -gt 41943040 ]]; then
        log "⚠️  Prometheus storage is approaching limits"
    fi
}

# Function to backup critical configs
backup_configs() {
    local backup_dir="/opt/monitoring-backups/$(date +%Y%m%d)"
    mkdir -p "$backup_dir"

    log "Creating configuration backup..."

    # Backup configurations
    cp -r ./monitoring "$backup_dir/" 2>/dev/null || true
    cp docker-compose.monitoring.yml "$backup_dir/" 2>/dev/null || true

    # Keep only last 7 days of backups
    find /opt/monitoring-backups -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

    log "Configuration backup completed"
}

# Main execution
main() {
    log "🚀 Starting monitoring maintenance..."

    # Health checks
    check_service_health "Prometheus" "$PROMETHEUS_URL/-/healthy"
    check_service_health "Grafana" "$GRAFANA_URL/api/health"
    check_service_health "Loki" "$LOKI_URL/ready"

    # Maintenance tasks
    check_disk_usage
    backup_configs
    cleanup_prometheus
    optimize_loki
    cleanup_grafana

    log "✅ Monitoring maintenance completed successfully"
}

# Run maintenance
main "$@"
```

### Alert Threshold Optimization

#### Optimized Alert Rules
```yaml
groups:
  - name: optimized-critical-alerts
    rules:
      # More intelligent CPU alerting
      - alert: HighCPUUsage
        expr: homeserver:node_cpu_utilization > 85
        for: 10m                    # Increased from 5m to reduce noise
        labels:
          severity: critical
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is {{ $value }}% for more than 10 minutes"

      # Smarter memory alerting with trend analysis
      - alert: HighMemoryUsage
        expr: homeserver:node_memory_utilization > 90 and homeserver:disk_usage_trend > 95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage with concerning trend"
          description: "Memory usage is {{ $value }}% and trending upward"

      # Contextual service alerts
      - alert: ServiceDown
        expr: homeserver:service_availability < 0.99
        for: 2m                     # Increased to reduce flapping
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.instance }} availability degraded"
          description: "Service availability is {{ $value | humanizePercentage }} over 5 minutes"
```

### Performance Testing Commands
```bash
# Test Prometheus query performance
curl -g "http://localhost:9090/api/v1/query?query=up&time=$(date +%s)"

# Benchmark dashboard loading
time curl -s "http://localhost:3001/api/dashboards/uid/system-overview" > /dev/null

# Check Loki ingestion rate
curl -s "http://localhost:3100/metrics" | grep loki_ingester_chunks_created_total

# Monitor resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Run maintenance script
chmod +x scripts/monitoring-maintenance.sh
./scripts/monitoring-maintenance.sh
```

## Success Metrics
- Reduced false positive alerts by 50%
- Dashboard load times under 3 seconds
- Storage growth rate under 1GB/week
- Query response times under 1 second
- Memory usage under 4GB total for monitoring stack

## Dependencies
- Completed: All previous monitoring tickets
- Sufficient disk space for optimization
- Access to container resource management
- Backup storage for configurations

## Risk Considerations
- Over-optimization reducing monitoring effectiveness
- Storage constraints affecting data retention
- Resource limits impacting monitoring accuracy
- False positive reduction missing real issues

## Documentation to Update
- Add performance tuning guide to README.md
- Document maintenance procedures
- Include resource planning guidelines
- Add troubleshooting performance issues section