# Deploy Centralized Logging with Loki

## Priority: 3 (Medium)
## Estimated Time: 4-5 hours
## Phase: Month 2 - Medium Priority Hardening

## Description
Implement Grafana Loki for centralized log aggregation with Promtail log collectors. This enables security event tracking, audit logging, and troubleshooting across all services.

## Acceptance Criteria
- [ ] Loki deployed and collecting logs from all containers
- [ ] Promtail configured for Docker log collection
- [ ] Grafana configured with Loki datasource
- [ ] Log retention policy configured (30 days)
- [ ] Security event queries created
- [ ] Authentication failure tracking enabled
- [ ] Log-based alerts configured

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.logging.yml` - Loki stack (new file)
2. `logging/loki/loki-config.yml` - Loki configuration (new file)
3. `logging/promtail/promtail-config.yml` - Promtail config (new file)
4. `monitoring/grafana/provisioning/datasources/loki.yml` - Datasource (new file)
5. `monitoring/prometheus/alert_rules.yml` - Add log-based alerts

**docker-compose.logging.yml:**
```yaml
services:
  loki:
    image: grafana/loki:2.9.3@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./logging/loki:/etc/loki
      - loki_data:/loki
    command: -config.file=/etc/loki/loki-config.yml
    networks:
      - monitoring

  promtail:
    image: grafana/promtail:2.9.3@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: promtail
    restart: unless-stopped
    volumes:
      - ./logging/promtail:/etc/promtail
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
    command: -config.file=/etc/promtail/promtail-config.yml
    networks:
      - monitoring

volumes:
  loki_data:

networks:
  monitoring:
    external: true
    name: home-server-stack_monitoring
```

**logging/loki/loki-config.yml:**
```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
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

limits_config:
  retention_period: 720h  # 30 days
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  max_query_length: 721h
  max_cache_freshness_per_query: 10m

chunk_store_config:
  max_look_back_period: 720h

table_manager:
  retention_deletes_enabled: true
  retention_period: 720h

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150
```

**logging/promtail/promtail-config.yml:**
```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker containers
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'logstream'
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: 'service'

  # System logs
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*log

  # Authentication logs (Authelia)
  - job_name: authelia
    static_configs:
      - targets:
          - localhost
        labels:
          job: authelia
          __path__: /var/lib/docker/containers/*/*-json.log
    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            timestamp: time
      - labels:
          stream:
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      - output:
          source: output
```

See full implementation in ticket for complete configuration.

## Testing Commands
```bash
# Start Loki stack
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.logging.yml up -d

# Check Loki health
curl http://localhost:3100/ready

# Query logs via API
curl -G -s "http://localhost:3100/loki/api/v1/query" --data-urlencode 'query={container="n8n"}' | jq

# View logs in Grafana
# Navigate to Explore > select Loki datasource > query: {service="n8n"}
```

## Success Metrics
- All container logs visible in Loki
- 30-day retention working
- Security event queries functional
- Grafana Explore showing logs
- Log-based alerts triggering correctly

## References
- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [Promtail Configuration](https://grafana.com/docs/loki/latest/clients/promtail/)
