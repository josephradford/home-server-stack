# Create Basic Monitoring Dashboards

## Priority: 1 (Critical)
## Estimated Time: 3-4 hours
## Phase: Week 1 - Foundation

## Description
Create essential Grafana dashboards for system overview, container health, and resource utilization monitoring. These dashboards provide immediate visibility into infrastructure health.

## Acceptance Criteria
- [x] System overview dashboard showing CPU, memory, disk, network
- [x] Container health dashboard showing all service status
- [x] Resource utilization dashboard with historical trends
- [x] Dashboards automatically provisioned on Grafana startup
- [x] All panels showing data from Prometheus
- [x] Responsive design for mobile/tablet viewing
- [x] Proper time range selectors and refresh intervals

## Technical Implementation Details

### Files to Create
1. `monitoring/grafana/provisioning/dashboards/dashboard.yml` - Dashboard provider config
2. `monitoring/grafana/provisioning/datasources/prometheus.yml` - Prometheus datasource
3. `monitoring/grafana/dashboards/system-overview.json` - System overview dashboard
4. `monitoring/grafana/dashboards/container-health.json` - Container monitoring dashboard
5. `monitoring/grafana/dashboards/resource-utilization.json` - Resource trends dashboard

### Grafana Provisioning Structure
```
monitoring/grafana/
├── provisioning/
│   ├── dashboards/
│   │   └── dashboard.yml
│   ├── datasources/
│   │   └── prometheus.yml
│   └── notifiers/
└── dashboards/
    ├── system-overview.json
    ├── container-health.json
    └── resource-utilization.json
```

### Datasource Configuration (`monitoring/grafana/provisioning/datasources/prometheus.yml`)
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

### Dashboard Provider Config (`monitoring/grafana/provisioning/dashboards/dashboard.yml`)
```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

### System Overview Dashboard Key Panels
1. **CPU Usage** - `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)`
2. **Memory Usage** - `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100`
3. **Disk Usage** - `100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100)`
4. **Network I/O** - `rate(node_network_receive_bytes_total[5m])` and `rate(node_network_transmit_bytes_total[5m])`
5. **Load Average** - `node_load1`, `node_load5`, `node_load15`
6. **Uptime** - `time() - node_boot_time_seconds`

### Container Health Dashboard Key Panels
1. **Container Status** - `container_last_seen{name=~".+"}`
2. **Container CPU Usage** - `rate(container_cpu_usage_seconds_total{name=~".+"}[5m]) * 100`
3. **Container Memory Usage** - `container_memory_usage_bytes{name=~".+"}`
4. **Container Network I/O** - `rate(container_network_receive_bytes_total{name=~".+"}[5m])`
5. **Container Restart Count** - `increase(container_start_time_seconds{name=~".+"}[1h])`
6. **Docker Containers Up** - `count(container_last_seen{name=~".+"})`

### Resource Utilization Dashboard Key Panels
1. **CPU Usage Over Time** - Time series of CPU usage by core
2. **Memory Usage Trends** - Historical memory consumption patterns
3. **Disk I/O Trends** - Read/write operations over time
4. **Network Traffic Patterns** - Bandwidth utilization trends
5. **Container Resource Allocation** - Resource usage by container
6. **Top Resource Consumers** - Tables showing highest resource usage

### Dashboard Features to Include
- **Time Range Selector**: Last 1h, 6h, 12h, 24h, 7d
- **Refresh Intervals**: 5s, 30s, 1m, 5m, 15m
- **Responsive Design**: Mobile-friendly layouts
- **Color Coding**: Green/Yellow/Red thresholds
- **Tooltips**: Explanatory text for each metric
- **Drill-down**: Links between related dashboards

### Alert Thresholds to Visualize
- CPU > 70% (Yellow), > 85% (Red)
- Memory > 80% (Yellow), > 90% (Red)
- Disk > 80% (Yellow), > 90% (Red)
- Container Down (Red)

### Testing Commands
```bash
# Verify Grafana is running
curl http://SERVER_IP:3001/api/health

# Check dashboard provisioning
docker exec grafana ls -la /etc/grafana/provisioning/dashboards/

# Check datasource connection
curl -u admin:GRAFANA_PASSWORD http://SERVER_IP:3001/api/datasources

# Verify dashboard import
curl -u admin:GRAFANA_PASSWORD http://SERVER_IP:3001/api/search
```

### Dashboard URLs (after implementation)
- System Overview: `http://SERVER_IP:3001/d/system-overview`
- Container Health: `http://SERVER_IP:3001/d/container-health`
- Resource Utilization: `http://SERVER_IP:3001/d/resource-utilization`

## Success Metrics
- All dashboards load without errors
- All panels display data from Prometheus
- Responsive design works on mobile devices
- Proper time range and refresh functionality
- Color-coded thresholds display correctly

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- Prometheus collecting metrics successfully
- Grafana container running and accessible
- Node Exporter and cAdvisor providing data

## Risk Considerations
- Large dashboards may impact Grafana performance
- Complex queries could slow down dashboard loading
- Mobile responsiveness may require iteration

## Documentation to Update
- Add dashboard URLs to README.md
- Document dashboard navigation
- Include screenshot examples
- Add troubleshooting section for common issues