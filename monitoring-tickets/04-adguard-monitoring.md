# Implement AdGuard Home Monitoring

## Priority: 2 (High)
## Estimated Time: 3-4 hours
## Phase: Week 2 - Service-Specific Monitoring

## Description
Implement comprehensive monitoring for AdGuard Home including DNS query metrics, blocked requests tracking, performance monitoring, and custom dashboard creation.

## Acceptance Criteria
- [ ] AdGuard Home metrics exported to Prometheus
- [ ] DNS query rate and response time monitoring
- [ ] Blocked requests and filtering effectiveness tracking
- [ ] Custom AdGuard dashboard in Grafana
- [ ] Alerts for DNS service failures and performance issues
- [ ] Query log analysis capabilities
- [ ] Client-based metrics and filtering statistics

## Technical Implementation Details

### Files to Create/Modify
1. `monitoring/exporters/adguard-exporter.py` - Custom metrics exporter
2. `monitoring/grafana/dashboards/adguard-home.json` - AdGuard-specific dashboard
3. `monitoring/prometheus/prometheus.yml` - Add AdGuard scrape config
4. `monitoring/prometheus/alert_rules.yml` - Add AdGuard-specific alerts
5. `docker-compose.monitoring.yml` - Add AdGuard exporter service

### AdGuard Metrics to Monitor
1. **DNS Performance**:
   - Total DNS queries per second
   - Average response time
   - Query type distribution (A, AAAA, PTR, etc.)
   - Upstream server response times

2. **Filtering Statistics**:
   - Blocked requests count and percentage
   - Allowed requests count
   - Top blocked domains
   - Filtering rule effectiveness

3. **Client Analytics**:
   - Queries per client
   - Top clients by query volume
   - Client geographic distribution
   - Blocked requests per client

4. **System Health**:
   - AdGuard service uptime
   - Configuration reload success
   - Log file sizes and rotation
   - Memory usage by AdGuard process

### Custom AdGuard Exporter (`monitoring/exporters/adguard-exporter.py`)
```python
#!/usr/bin/env python3
"""
AdGuard Home Prometheus Exporter
Exports metrics from AdGuard Home API to Prometheus format
"""

import time
import requests
import json
from prometheus_client import start_http_server, Gauge, Counter, Histogram
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AdGuard Home configuration
ADGUARD_URL = os.getenv('ADGUARD_URL', 'http://adguard:3000')
ADGUARD_USER = os.getenv('ADGUARD_USER', 'admin')
ADGUARD_PASS = os.getenv('ADGUARD_PASS', 'admin')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', '9617'))

# Prometheus metrics
dns_queries_total = Counter('adguard_dns_queries_total', 'Total DNS queries', ['type', 'client'])
dns_queries_blocked = Counter('adguard_dns_queries_blocked_total', 'Total blocked DNS queries', ['client'])
dns_query_duration = Histogram('adguard_dns_query_duration_seconds', 'DNS query duration')
adguard_filtering_enabled = Gauge('adguard_filtering_enabled', 'Filtering status (1=enabled, 0=disabled)')
adguard_clients_count = Gauge('adguard_clients_count', 'Number of active clients')
adguard_rules_count = Gauge('adguard_rules_count', 'Number of filtering rules')
adguard_uptime_seconds = Gauge('adguard_uptime_seconds', 'AdGuard uptime in seconds')

class AdGuardExporter:
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (ADGUARD_USER, ADGUARD_PASS)

    def collect_stats(self):
        """Collect statistics from AdGuard Home API"""
        try:
            # Get general stats
            stats_response = self.session.get(f'{ADGUARD_URL}/control/stats')
            stats_data = stats_response.json()

            # Update metrics
            adguard_filtering_enabled.set(1 if stats_data.get('protection_enabled') else 0)

            # Get query log for detailed analysis
            log_response = self.session.get(f'{ADGUARD_URL}/control/querylog')
            log_data = log_response.json()

            # Process query log data
            self.process_query_log(log_data.get('data', []))

            # Get status information
            status_response = self.session.get(f'{ADGUARD_URL}/control/status')
            status_data = status_response.json()

            # Update system metrics
            if 'version' in status_data:
                logger.info(f"AdGuard version: {status_data['version']}")

        except Exception as e:
            logger.error(f"Error collecting AdGuard stats: {e}")

    def process_query_log(self, queries):
        """Process query log data and update metrics"""
        for query in queries:
            client = query.get('client', 'unknown')
            query_type = query.get('type', 'unknown')
            blocked = query.get('reason', '') in ['FilteredBlackList', 'FilteredBlockedService']

            # Update counters
            dns_queries_total.labels(type=query_type, client=client).inc()
            if blocked:
                dns_queries_blocked.labels(client=client).inc()

    def run(self):
        """Main exporter loop"""
        logger.info(f"Starting AdGuard exporter on port {EXPORTER_PORT}")
        start_http_server(EXPORTER_PORT)

        while True:
            try:
                self.collect_stats()
                time.sleep(30)  # Collect every 30 seconds
            except KeyboardInterrupt:
                logger.info("Exporter stopped")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait longer on error

if __name__ == '__main__':
    exporter = AdGuardExporter()
    exporter.run()
```

### Docker Service for AdGuard Exporter
Add to `docker-compose.monitoring.yml`:
```yaml
  adguard-exporter:
    build:
      context: ./monitoring/exporters
      dockerfile: Dockerfile.adguard
    container_name: adguard-exporter
    restart: unless-stopped
    environment:
      - ADGUARD_URL=http://adguard:3000
      - ADGUARD_USER=${ADGUARD_USER}
      - ADGUARD_PASS=${ADGUARD_PASS}
      - EXPORTER_PORT=9617
    ports:
      - "9617:9617"
    networks:
      - homeserver
    depends_on:
      - adguard
```

### Dockerfile for AdGuard Exporter (`monitoring/exporters/Dockerfile.adguard`)
```dockerfile
FROM python:3.11-alpine

WORKDIR /app

RUN pip install prometheus-client requests

COPY adguard-exporter.py .

EXPOSE 9617

CMD ["python", "adguard-exporter.py"]
```

### Prometheus Scrape Configuration
Add to `monitoring/prometheus/prometheus.yml`:
```yaml
  - job_name: 'adguard-exporter'
    static_configs:
      - targets: ['adguard-exporter:9617']
    scrape_interval: 30s

  - job_name: 'adguard-api'
    static_configs:
      - targets: ['adguard:3000']
    metrics_path: '/control/status'
    scrape_interval: 60s
```

### AdGuard-Specific Alert Rules
Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
  - name: adguard-alerts
    rules:
      - alert: AdGuardDown
        expr: up{job="adguard-exporter"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AdGuard Home exporter is down"
          description: "AdGuard Home monitoring is not responding"

      - alert: AdGuardFilteringDisabled
        expr: adguard_filtering_enabled == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "AdGuard filtering is disabled"
          description: "DNS filtering has been disabled in AdGuard Home"

      - alert: AdGuardHighQueryRate
        expr: rate(adguard_dns_queries_total[5m]) > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High DNS query rate detected"
          description: "DNS query rate is {{ $value }} queries per second"

      - alert: AdGuardHighBlockRate
        expr: (rate(adguard_dns_queries_blocked_total[5m]) / rate(adguard_dns_queries_total[5m])) > 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High DNS block rate detected"
          description: "{{ $value | humanizePercentage }} of DNS queries are being blocked"

      - alert: AdGuardDNSResolutionSlow
        expr: histogram_quantile(0.95, rate(adguard_dns_query_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow DNS resolution detected"
          description: "95th percentile DNS resolution time is {{ $value }}s"
```

### Grafana Dashboard Panels
Key panels for AdGuard dashboard:

1. **Overview Stats**:
   - Total queries in last 24h
   - Blocked percentage
   - Active clients count
   - Filtering rules count

2. **Query Analysis**:
   - Queries per second time series
   - Query type distribution (pie chart)
   - Top queried domains (table)
   - Response time histogram

3. **Blocking Statistics**:
   - Blocked requests over time
   - Top blocked domains (table)
   - Blocking effectiveness by rule list
   - False positive detection

4. **Client Analysis**:
   - Queries per client (bar chart)
   - Top clients by query volume
   - Client geographic distribution
   - Per-client blocking statistics

5. **Performance Metrics**:
   - DNS response time trends
   - Upstream server performance
   - AdGuard memory usage
   - Configuration reload times

### Environment Variables to Add
Add to `.env`:
```bash
# AdGuard Monitoring Configuration
ADGUARD_USER=admin
ADGUARD_PASS=your_adguard_admin_password
```

### Testing Commands
```bash
# Test AdGuard exporter
curl http://SERVER_IP:9617/metrics

# Check AdGuard API connectivity
curl -u admin:password http://SERVER_IP:3000/control/status

# Test DNS resolution
nslookup google.com SERVER_IP

# Generate test DNS traffic
for i in {1..100}; do nslookup example$i.com SERVER_IP; done

# Check Prometheus targets
curl http://SERVER_IP:9090/api/v1/targets | grep adguard
```

### AdGuard Configuration Requirements
1. Enable query log in AdGuard settings
2. Configure appropriate log retention (7-30 days)
3. Enable statistics collection
4. Set up admin credentials for API access

## Success Metrics
- AdGuard exporter running and exposing metrics
- Prometheus successfully scraping AdGuard metrics
- Grafana dashboard displaying DNS statistics
- Alerts firing for DNS service issues
- Query log analysis working correctly

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- AdGuard Home running and accessible
- Admin credentials for AdGuard API access
- Python environment for custom exporter

## Risk Considerations
- API rate limiting affecting metric collection
- Large query logs impacting performance
- False positives from blocking rule changes
- Privacy concerns with detailed query logging

## Documentation to Update
- Add AdGuard monitoring section to README.md
- Document custom exporter configuration
- Include DNS performance troubleshooting guide
- Add query log privacy considerations