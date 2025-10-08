# Implement Log Aggregation with Loki

## Priority: 3 (Medium)
## Estimated Time: 4-5 hours
## Phase: Week 3 - Enhanced Observability

## Description
Implement centralized log aggregation using Grafana Loki and Promtail for collecting, storing, and analyzing logs from all services. This provides centralized log management, log-based alerting, and correlation with metrics.

## Acceptance Criteria
- [ ] Loki deployed and running for log storage
- [ ] Promtail agents collecting logs from all containers
- [ ] Logs from all services visible in Grafana
- [ ] Log-based alerting rules configured
- [ ] Log retention policies implemented
- [ ] Structured logging with proper labels
- [ ] Log search and filtering capabilities
- [ ] Integration with existing Grafana dashboards

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.monitoring.yml` - Add Loki and Promtail services
2. `monitoring/loki/loki.yml` - Loki configuration
3. `monitoring/promtail/promtail.yml` - Promtail configuration
4. `monitoring/grafana/provisioning/datasources/loki.yml` - Loki datasource
5. `monitoring/grafana/dashboards/logs-overview.json` - Log analysis dashboard
6. `monitoring/prometheus/alert_rules.yml` - Add log-based alerts

### Services to Add to docker-compose.monitoring.yml
```yaml
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
    networks:
      - homeserver

  promtail:
    image: grafana/promtail:latest
    container_name: promtail
    restart: unless-stopped
    volumes:
      - ./monitoring/promtail:/etc/promtail
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: -config.file=/etc/promtail/promtail.yml
    networks:
      - homeserver
    depends_on:
      - loki

volumes:
  loki_data:
```

### Loki Configuration (`monitoring/loki/loki.yml`)
```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 1h       # Any chunk not receiving new logs in this time will be flushed
  max_chunk_age: 1h           # All chunks will be flushed when they hit this age
  chunk_target_size: 1048576  # Loki will attempt to build chunks up to 1.5MB
  chunk_retain_period: 30s    # Must be greater than index read cache TTL if using an index cache
  max_transfer_retries: 0     # Chunk transfers disabled

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    cache_ttl: 24h
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

compactor:
  working_directory: /loki/boltdb-shipper-compactor
  shared_store: filesystem

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h  # 1 week
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
  max_query_length: 720h           # 30 days
  max_query_parallelism: 32
  max_streams_per_user: 10000
  max_line_size: 256KB

chunk_store_config:
  max_look_back_period: 168h  # 1 week

table_manager:
  retention_deletes_enabled: true
  retention_period: 168h      # 1 week

ruler:
  storage:
    type: local
    local:
      directory: /loki/rules
  rule_path: /loki/rules
  alertmanager_url: http://alertmanager:9093
  ring:
    kvstore:
      store: inmemory
  enable_api: true
```

### Promtail Configuration (`monitoring/promtail/promtail.yml`)
```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker container logs
  - job_name: docker
    static_configs:
      - targets:
          - localhost
        labels:
          job: docker
          host: homeserver
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            attrs:
      - json:
          expressions:
            tag:
          source: attrs
      - regex:
          expression: (?P<container_name>(?:[^|]*/|/)(?P<container_name_only>[^_]+))
          source: tag
      - timestamp:
          format: RFC3339Nano
          source: time
      - labels:
          stream:
          container_name:
          container_name_only:
      - output:
          source: output

  # System logs
  - job_name: syslog
    static_configs:
      - targets:
          - localhost
        labels:
          job: syslog
          host: homeserver
          __path__: /var/log/syslog

    pipeline_stages:
      - regex:
          expression: '^(?P<timestamp>\S+\s+\d+\s+\d+:\d+:\d+)\s+(?P<hostname>\S+)\s+(?P<service>\S+)(?:\[(?P<pid>\d+)\])?\:\s*(?P<message>.*)$'
      - labels:
          hostname:
          service:
          pid:
      - timestamp:
          format: Jan _2 15:04:05
          source: timestamp

  # AdGuard Home logs
  - job_name: adguard
    static_configs:
      - targets:
          - localhost
        labels:
          job: adguard
          service: adguard
          __path__: /var/lib/docker/containers/*adguard*/*log

    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
            time: time
      - timestamp:
          format: RFC3339Nano
          source: time
      - regex:
          expression: '^(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<level>\w+):\s*(?P<message>.*)$'
          source: log
      - labels:
          level:
      - output:
          source: log

  # n8n logs
  - job_name: n8n
    static_configs:
      - targets:
          - localhost
        labels:
          job: n8n
          service: n8n
          __path__: /var/lib/docker/containers/*n8n*/*log

    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
            time: time
      - timestamp:
          format: RFC3339Nano
          source: time
      - json:
          expressions:
            level: level
            message: message
            timestamp: timestamp
          source: log
      - labels:
          level:
      - timestamp:
          format: "2006-01-02T15:04:05.000Z"
          source: timestamp
      - output:
          source: message

  # Ollama logs
  - job_name: ollama
    static_configs:
      - targets:
          - localhost
        labels:
          job: ollama
          service: ollama
          __path__: /var/lib/docker/containers/*ollama*/*log

    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
            time: time
      - timestamp:
          format: RFC3339Nano
          source: time
      - regex:
          expression: '^(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+(?P<level>\w+):\s*(?P<message>.*)$'
          source: log
      - labels:
          level:
      - output:
          source: log

  # Monitoring services logs
  - job_name: monitoring
    static_configs:
      - targets:
          - localhost
        labels:
          job: monitoring
          __path__: /var/lib/docker/containers/*{prometheus,grafana,alertmanager,loki,promtail}*/*log

    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
            time: time
            attrs: attrs
      - json:
          expressions:
            tag: tag
          source: attrs
      - regex:
          expression: (?P<container_name>(?:[^|]*/|/)(?P<service>[^_]+))
          source: tag
      - timestamp:
          format: RFC3339Nano
          source: time
      - labels:
          service:
          stream:
      - output:
          source: log
```

### Loki Datasource Configuration (`monitoring/grafana/provisioning/datasources/loki.yml`)
```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
    isDefault: false
    jsonData:
      maxLines: 1000
      derivedFields:
        - datasourceUid: prometheus_uid
          matcherRegex: "traceID=(\\w+)"
          name: TraceID
          url: "$${__value.raw}"
```

### Log-Based Alert Rules
Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
  - name: log-based-alerts
    rules:
      - alert: HighErrorLogRate
        expr: |
          (
            sum(rate({job=~".+"} |~ "(?i)(error|exception|fail)" [5m])) by (service)
            /
            sum(rate({job=~".+"} [5m])) by (service)
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in logs for {{ $labels.service }}"
          description: "{{ $labels.service }} has {{ $value | humanizePercentage }} error rate in logs"

      - alert: ServiceLogErrors
        expr: |
          sum(rate({job=~".+"} |~ "(?i)(fatal|critical)" [5m])) by (service) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Critical errors in {{ $labels.service }} logs"
          description: "{{ $labels.service }} is logging critical/fatal errors"

      - alert: AdGuardDNSErrors
        expr: |
          sum(rate({service="adguard"} |~ "(?i)(dns.*error|resolve.*fail)" [5m])) > 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "DNS resolution errors in AdGuard"
          description: "AdGuard is experiencing DNS resolution errors"

      - alert: N8nWorkflowErrors
        expr: |
          sum(rate({service="n8n"} |~ "(?i)(workflow.*fail|execution.*error)" [5m])) > 0.1
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "n8n workflow execution errors"
          description: "n8n workflows are experiencing execution errors"

      - alert: OllamaModelErrors
        expr: |
          sum(rate({service="ollama"} |~ "(?i)(model.*error|load.*fail)" [5m])) > 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Ollama model loading errors"
          description: "Ollama is experiencing model loading or inference errors"

      - alert: NoLogsReceived
        expr: |
          sum(rate({job=~".+"} [10m])) by (service) == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "No logs received from {{ $labels.service }}"
          description: "{{ $labels.service }} has not sent any logs in the last 10 minutes"
```

### Grafana Logs Dashboard Panels
Key panels for logs dashboard:

1. **Log Volume Overview**:
   - Total log lines per service over time
   - Log level distribution (INFO, WARN, ERROR)
   - Top services by log volume
   - Log ingestion rate

2. **Error Analysis**:
   - Error rate percentage by service
   - Recent error logs table
   - Error pattern detection
   - Critical/fatal error alerts

3. **Service-Specific Logs**:
   - AdGuard DNS query logs and errors
   - n8n workflow execution logs
   - Ollama model inference logs
   - System and container logs

4. **Log Search Interface**:
   - Dynamic log search with filters
   - Service and time range selectors
   - Log level filtering
   - Regex pattern matching

5. **Performance Correlation**:
   - Logs correlated with metrics
   - Error spikes with resource usage
   - Log volume vs system performance
   - Alert correlation view

### Testing Commands
```bash
# Test Loki API
curl http://SERVER_IP:3100/ready

# Check Promtail status
curl http://SERVER_IP:9080/metrics

# Query logs via API
curl -G -s "http://SERVER_IP:3100/loki/api/v1/query" \
  --data-urlencode 'query={job="docker"}' \
  --data-urlencode 'limit=10'

# Test log ingestion
docker logs adguard

# Check Loki targets in Grafana
# Navigate to Grafana > Explore > Loki > Log browser

# Generate test errors for alerting
docker exec adguard logger "ERROR: Test error message for monitoring"
```

### Log Retention and Storage Configuration
- **Retention Period**: 1 week (configurable)
- **Storage Backend**: Local filesystem (can be changed to S3/GCS)
- **Compression**: Enabled for older logs
- **Index Cleanup**: Automatic via compactor

### Performance Considerations
- **Log Parsing**: Structured logging improves performance
- **Label Cardinality**: Keep labels minimal and consistent
- **Query Optimization**: Use specific time ranges and filters
- **Storage Management**: Monitor disk usage and retention

## Success Metrics
- Loki and Promtail running without errors
- All services sending logs to Loki
- Logs visible and searchable in Grafana
- Log-based alerts firing correctly
- No significant performance impact on services

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- Docker log driver compatibility
- Sufficient disk space for log storage
- Access to Docker socket for log collection

## Risk Considerations
- Log volume may impact disk space
- Promtail resource usage on host system
- Log parsing errors affecting ingestion
- Potential log sensitive data exposure

## Security Considerations
- Secure Loki API access
- Log data retention policies
- Sensitive information filtering
- Access control for log viewing

## Documentation to Update
- Add log monitoring section to README.md
- Document log search and query syntax
- Include log-based troubleshooting guides
- Add retention policy management instructions