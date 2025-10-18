# Add Core Monitoring Stack (Foundation)

## Priority: 1 (Critical)
## Estimated Time: 4-6 hours
## Phase: Week 1 - Foundation

## Description
Implement the core monitoring infrastructure using Prometheus, Grafana, AlertManager, Node Exporter, and cAdvisor. This provides the foundation for all subsequent monitoring capabilities.

## Acceptance Criteria
- [x] Monitoring services added to docker-compose configuration
- [x] Prometheus collecting metrics from all containers
- [x] Grafana accessible with pre-configured dashboards
- [x] AlertManager configured for basic alerting
- [x] Node Exporter providing host metrics
- [x] cAdvisor providing container metrics
- [x] Data persistence configured for all monitoring services
- [x] Services accessible via defined ports

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.monitoring.yml` - New monitoring services
2. `monitoring/prometheus/prometheus.yml` - Prometheus configuration
3. `monitoring/grafana/provisioning/` - Grafana dashboards and datasources
4. `monitoring/alertmanager/alertmanager.yml` - Alert routing configuration
5. `.env` - Add monitoring-related environment variables

### Docker Compose Services to Add
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
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - homeserver

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:3001:3000"  # Using 3001 to avoid conflict with AdGuard
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    networks:
      - homeserver

  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9093:9093"
    volumes:
      - ./monitoring/alertmanager:/etc/alertmanager
    networks:
      - homeserver

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - homeserver

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    networks:
      - homeserver

volumes:
  prometheus_data:
  grafana_data:
```

### Environment Variables to Add
Add to `.env`:
```
# Monitoring Configuration
GRAFANA_PASSWORD=your_secure_grafana_password
```

### Prometheus Configuration (`monitoring/prometheus/prometheus.yml`)
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'adguard'
    static_configs:
      - targets: ['adguard:3000']
    metrics_path: '/control/stats'

  - job_name: 'n8n'
    static_configs:
      - targets: ['n8n:5678']
    scheme: https
    tls_config:
      insecure_skip_verify: true

  - job_name: 'ollama'
    static_configs:
      - targets: ['ollama:11434']
```

### Testing Commands
```bash
# Start monitoring stack
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# Verify services are running
docker ps | grep -E "(prometheus|grafana|alertmanager|node-exporter|cadvisor)"

# Check Prometheus targets
curl http://SERVER_IP:9090/api/v1/targets

# Access interfaces
# Grafana: http://SERVER_IP:3001 (admin/GRAFANA_PASSWORD)
# Prometheus: http://SERVER_IP:9090
# AlertManager: http://SERVER_IP:9093
```

## Success Metrics
- All monitoring containers running and healthy
- Prometheus showing all targets as "UP"
- Grafana accessible with admin login
- Basic system metrics visible in Grafana
- No port conflicts with existing services

## Dependencies
- Existing docker-compose.yml infrastructure
- Available disk space (50GB+ recommended)
- Ports 3001, 8080, 9090, 9093, 9100 available

## Risk Considerations
- AdGuard Home port conflict (moved Grafana to 3001)
- Resource usage increase (2-3GB RAM)
- Network security (monitoring ports exposed)

## Rollback Plan
```bash
# Stop monitoring services
docker compose -f docker-compose.monitoring.yml down

# Remove monitoring volumes if needed
docker volume rm home-server-stack_prometheus_data home-server-stack_grafana_data
```