# Monitoring Stack Deployment Guide

## Overview
Foundation monitoring stack implemented with Prometheus, Grafana, AlertManager, Node Exporter, and cAdvisor.

## Pre-deployment Setup

1. **Copy environment variables:**
   ```bash
   cp .env.example .env
   ```

2. **Configure environment variables in `.env`:**
   - Set `SERVER_IP` to your server's IP address
   - Set `GRAFANA_PASSWORD` to a secure password

## Deployment Commands

1. **Start the monitoring stack:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
   ```

2. **Verify services are running:**
   ```bash
   docker ps | grep -E "(prometheus|grafana|alertmanager|node-exporter|cadvisor)"
   ```

3. **Check Prometheus targets:**
   ```bash
   curl http://SERVER_IP:9090/api/v1/targets
   ```

## Access URLs
- **Grafana:** http://SERVER_IP:3001 (admin/GRAFANA_PASSWORD)
- **Prometheus:** http://SERVER_IP:9090
- **AlertManager:** http://SERVER_IP:9093
- **cAdvisor:** http://SERVER_IP:8080
- **Node Exporter:** http://SERVER_IP:9100

## Pre-configured Dashboards
- Node Exporter Full (System metrics)
- Docker Container Monitoring (Container metrics)

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