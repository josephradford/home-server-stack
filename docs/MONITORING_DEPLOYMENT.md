# Monitoring Stack Deployment Guide

## Overview
Foundation monitoring stack implemented with Prometheus, Grafana, AlertManager, Node Exporter, and cAdvisor. The monitoring stack is automatically deployed as part of the standard setup.

## Deployment

The monitoring stack is automatically deployed when you run:

```bash
make setup
```

This deploys all services including:
- Core services (AdGuard, n8n, Ollama, WireGuard, Habitica)
- Monitoring stack (Grafana, Prometheus, Alertmanager, Node Exporter, cAdvisor)
- Bookwyrm wrapper (cloned, requires separate configuration)

**Note:** The monitoring stack is always included - there is no "base only" deployment option.

## Verification

1. **Verify all services are running:**
   ```bash
   make status
   ```

2. **Check Prometheus targets:**
   ```bash
   curl http://SERVER_IP:9090/api/v1/targets
   ```

3. **View monitoring logs:**
   ```bash
   docker logs grafana
   docker logs prometheus
   docker logs alertmanager
   ```

## Access URLs
- **Grafana:** http://SERVER_IP:3001 (admin/GRAFANA_PASSWORD)
- **Prometheus:** http://SERVER_IP:9090
- **AlertManager:** http://SERVER_IP:9093
- **cAdvisor:** http://SERVER_IP:8080
- **Node Exporter:** http://SERVER_IP:9100

## Pre-configured Dashboards
- System Overview (CPU, memory, disk, network)
- Container Health (Docker container status and resources)
- Resource Utilization (Historical trends and top consumers)
- Node Exporter Full (System metrics)
- Docker Container Monitoring (Container metrics)

## Troubleshooting

### Grafana Not Starting - "data source not found" Error

If Grafana fails to start with the error `Datasource provisioning error: data source not found`, the Grafana database may have corrupted state. To fix:

```bash
# Stop all services
make stop

# Remove the Grafana volume to reset its database
docker volume rm home-server-stack_grafana_data

# Start services again - Grafana will re-provision from scratch
make start

# Verify Grafana is running
docker logs grafana
```

**Note:** This will reset Grafana's database (users, manual dashboard changes, etc.), but all provisioned dashboards and datasources will be recreated automatically from the configuration files.

### Dashboards Not Showing Data

If dashboards load but show no data:
1. Verify Prometheus is scraping targets: http://SERVER_IP:9090/targets
2. Check that all exporters are running: `docker ps | grep -E "(node-exporter|cadvisor)"`
3. Verify the Prometheus datasource in Grafana: Configuration → Data sources → Prometheus → Test

## Alert Rules
- Instance Down (5 minute threshold)
- High CPU Usage (>80% for 10 minutes)
- High Memory Usage (>85% for 10 minutes)
- Disk Space Low (>90% for 5 minutes)

## Rollback Instructions
```bash
# Stop monitoring services
docker compose -f docker-compose.monitoring.yml down

# Remove monitoring volumes if needed
docker volume rm home-server-stack_prometheus_data home-server-stack_grafana_data
```

## Network Configuration
All services use the existing `homeserver` network for inter-service communication.

## Data Persistence
- Prometheus data: `prometheus_data` volume
- Grafana data: `grafana_data` volume
- Configuration files: Host bind mounts to `./monitoring/` directory