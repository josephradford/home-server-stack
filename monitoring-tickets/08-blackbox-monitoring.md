# Implement Blackbox Monitoring

## Priority: 3 (Medium)
## Estimated Time: 3-4 hours
## Phase: Week 3 - Enhanced Observability

## Description
Implement external endpoint monitoring using Prometheus Blackbox Exporter for health checks, SSL certificate monitoring, response time tracking, and service availability from an external perspective.

## Acceptance Criteria
- [ ] Blackbox Exporter deployed and configured
- [ ] HTTP/HTTPS endpoint monitoring for all services
- [ ] SSL certificate expiration monitoring
- [ ] DNS resolution monitoring
- [ ] Response time and availability tracking
- [ ] Custom blackbox dashboard in Grafana
- [ ] Alerts for service unavailability and certificate issues
- [ ] Multi-protocol monitoring (HTTP, HTTPS, DNS, TCP)

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.monitoring.yml` - Add Blackbox Exporter service
2. `monitoring/blackbox/blackbox.yml` - Blackbox Exporter configuration
3. `monitoring/prometheus/prometheus.yml` - Add blackbox scrape configs
4. `monitoring/prometheus/alert_rules.yml` - Add blackbox alerts
5. `monitoring/grafana/dashboards/blackbox-monitoring.json` - Blackbox dashboard

### Services to Monitor
1. **HTTP/HTTPS Endpoints**:
   - AdGuard Home admin interface (http://SERVER_IP:80)
   - AdGuard Home setup (http://SERVER_IP:3000)
   - n8n interface (https://SERVER_IP:5678)
   - Ollama API (http://SERVER_IP:11434)
   - Grafana (http://SERVER_IP:3001)
   - Prometheus (http://SERVER_IP:9090)

2. **DNS Services**:
   - AdGuard DNS resolution (SERVER_IP:53)
   - External DNS queries through AdGuard

3. **SSL Certificates**:
   - n8n HTTPS certificate
   - Any external domain certificates

### Add Blackbox Exporter to docker-compose.monitoring.yml
```yaml
  blackbox-exporter:
    image: prom/blackbox-exporter:latest
    container_name: blackbox-exporter
    restart: unless-stopped
    ports:
      - "9115:9115"
    volumes:
      - ./monitoring/blackbox:/etc/blackbox_exporter
    command:
      - '--config.file=/etc/blackbox_exporter/blackbox.yml'
    networks:
      - homeserver
```

### Blackbox Exporter Configuration (`monitoring/blackbox/blackbox.yml`)
```yaml
modules:
  # HTTP/HTTPS modules
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: []  # Defaults to 2xx
      method: GET
      follow_redirects: true
      fail_if_ssl: false
      fail_if_not_ssl: false

  http_2xx_with_auth:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: []
      method: GET
      follow_redirects: true
      basic_auth:
        username: "${N8N_USER}"
        password: "${N8N_PASSWORD}"

  https_2xx:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: []
      method: GET
      follow_redirects: true
      fail_if_ssl: false
      fail_if_not_ssl: true
      tls_config:
        insecure_skip_verify: true  # For self-signed certificates

  # SSL certificate monitoring
  ssl_cert_check:
    prober: http
    timeout: 10s
    http:
      method: GET
      follow_redirects: true
      fail_if_ssl: false
      fail_if_not_ssl: true
      tls_config:
        insecure_skip_verify: true

  # DNS monitoring
  dns_a_query:
    prober: dns
    timeout: 5s
    dns:
      query_name: "google.com"
      query_type: "A"
      valid_rcodes:
        - NOERROR
      validate_answer_rrs:
        fail_if_matches_regexp:
          - ".*127.0.0.1"
        fail_if_not_matches_regexp:
          - ".*8.8.8.8"

  dns_adguard:
    prober: dns
    timeout: 5s
    dns:
      query_name: "google.com"
      query_type: "A"
      valid_rcodes:
        - NOERROR
      preferred_ip_protocol: "ip4"

  # TCP connectivity
  tcp_connect:
    prober: tcp
    timeout: 5s
    tcp:
      preferred_ip_protocol: "ip4"

  # API health checks
  api_health:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      method: GET
      follow_redirects: false
      fail_if_body_not_matches_regexp:
        - ".*healthy.*|.*ok.*|.*running.*"

  # n8n webhook test
  n8n_webhook:
    prober: http
    timeout: 15s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200, 404]  # 404 is ok if no webhook configured
      method: GET
      follow_redirects: true
      tls_config:
        insecure_skip_verify: true

  # Ollama API test
  ollama_api:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      method: GET
      follow_redirects: false
      headers:
        Accept: "application/json"
```

### Prometheus Scrape Configuration
Add to `monitoring/prometheus/prometheus.yml`:
```yaml
  # Blackbox exporter scrape config
  - job_name: 'blackbox'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - http://adguard:80
        - http://adguard:3000
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

  # HTTPS endpoints
  - job_name: 'blackbox-https'
    metrics_path: /probe
    params:
      module: [https_2xx]
    static_configs:
      - targets:
        - https://n8n:5678
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  # SSL certificate monitoring
  - job_name: 'blackbox-ssl'
    metrics_path: /probe
    params:
      module: [ssl_cert_check]
    static_configs:
      - targets:
        - https://n8n:5678
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  # DNS monitoring
  - job_name: 'blackbox-dns'
    metrics_path: /probe
    params:
      module: [dns_adguard]
    static_configs:
      - targets:
        - adguard:53
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  # External connectivity tests
  - job_name: 'blackbox-external'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - http://httpbin.org/status/200
        - https://www.google.com
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  # API health checks
  - job_name: 'blackbox-api-health'
    metrics_path: /probe
    params:
      module: [api_health]
    static_configs:
      - targets:
        - http://ollama:11434/api/version
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### Blackbox Alert Rules
Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
  - name: blackbox-alerts
    rules:
      - alert: BlackboxProbeDown
        expr: up{job=~"blackbox.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Blackbox exporter is down"
          description: "Blackbox exporter probe is not responding"

      - alert: EndpointDown
        expr: probe_success == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Endpoint {{ $labels.instance }} is down"
          description: "Endpoint {{ $labels.instance }} has been down for more than 2 minutes"

      - alert: EndpointSlowResponse
        expr: probe_duration_seconds > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Endpoint {{ $labels.instance }} slow response"
          description: "Endpoint {{ $labels.instance }} response time is {{ $value }}s"

      - alert: SSLCertificateExpiringSoon
        expr: probe_ssl_earliest_cert_expiry - time() < 7 * 24 * 3600
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "SSL certificate expiring soon for {{ $labels.instance }}"
          description: "SSL certificate for {{ $labels.instance }} expires in {{ $value | humanizeDuration }}"

      - alert: SSLCertificateExpired
        expr: probe_ssl_earliest_cert_expiry - time() < 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "SSL certificate expired for {{ $labels.instance }}"
          description: "SSL certificate for {{ $labels.instance }} has expired"

      - alert: HTTPStatusCodeAlert
        expr: probe_http_status_code != 200
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "HTTP status code error for {{ $labels.instance }}"
          description: "{{ $labels.instance }} returned status code {{ $value }}"

      - alert: DNSResolutionFailed
        expr: probe_success{job="blackbox-dns"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "DNS resolution failed"
          description: "DNS resolution through AdGuard failed for test query"

      - alert: ExternalConnectivityLost
        expr: probe_success{job="blackbox-external"} == 0
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "External connectivity lost"
          description: "Cannot reach external endpoints: {{ $labels.instance }}"

      - alert: HighResponseTime
        expr: avg_over_time(probe_duration_seconds[5m]) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High response time for {{ $labels.instance }}"
          description: "Average response time is {{ $value }}s over last 5 minutes"
```

### Grafana Dashboard Panels
Key panels for blackbox monitoring dashboard:

1. **Service Availability Overview**:
   - Service uptime percentage (last 24h)
   - Current service status (up/down)
   - Service availability heatmap
   - Uptime SLA tracking

2. **Response Time Analysis**:
   - Response time trends by service
   - Response time percentiles
   - Slowest endpoints table
   - Response time distribution

3. **SSL Certificate Monitoring**:
   - Certificate expiration dates
   - Days until expiration
   - Certificate validity status
   - Certificate details table

4. **Network Connectivity**:
   - DNS resolution success rate
   - External connectivity status
   - Network latency trends
   - Connection timeout tracking

5. **Error Analysis**:
   - HTTP status code distribution
   - Failed probe details
   - Error rate trends
   - Failure reason categorization

### Environment Variables for Configuration
Update `.env` to include:
```bash
# Blackbox monitoring targets
BLACKBOX_EXTERNAL_TARGETS=http://httpbin.org/status/200,https://www.google.com
BLACKBOX_INTERNAL_TARGETS=http://adguard:80,http://grafana:3000
```

### Testing Commands
```bash
# Test blackbox exporter
curl http://SERVER_IP:9115/metrics

# Test specific probes
curl "http://SERVER_IP:9115/probe?target=http://adguard:80&module=http_2xx"
curl "http://SERVER_IP:9115/probe?target=https://n8n:5678&module=https_2xx"
curl "http://SERVER_IP:9115/probe?target=adguard:53&module=dns_adguard"

# Check SSL certificate info
curl "http://SERVER_IP:9115/probe?target=https://n8n:5678&module=ssl_cert_check" | grep probe_ssl

# View all probe results
curl http://SERVER_IP:9090/api/v1/query?query=probe_success

# Test DNS resolution
dig @SERVER_IP google.com

# Manual endpoint testing
curl -v http://SERVER_IP:80
curl -k -v https://SERVER_IP:5678
```

### Monitoring Coverage Matrix
| Service | HTTP | HTTPS | SSL | DNS | API |
|---------|------|-------|-----|-----|-----|
| AdGuard Home | ✓ | - | - | ✓ | - |
| n8n | - | ✓ | ✓ | - | - |
| Ollama | ✓ | - | - | - | ✓ |
| Grafana | ✓ | - | - | - | - |
| Prometheus | ✓ | - | - | - | ✓ |

### Advanced Monitoring Scenarios
1. **Multi-step Checks**: Chain HTTP requests for complex workflows
2. **Geographic Monitoring**: Monitor from multiple locations (if available)
3. **Performance Budgets**: Set response time thresholds per service
4. **Dependency Mapping**: Track service dependency health

## Success Metrics
- Blackbox Exporter running and accessible
- All defined endpoints being monitored
- SSL certificate monitoring working
- DNS resolution tests passing
- Alerts firing for simulated failures

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- Network connectivity to all monitored services
- SSL certificates configured for HTTPS services
- DNS resolution working through AdGuard

## Risk Considerations
- False positives from network issues
- Certificate renewal timing
- Monitoring overhead on services
- External dependency on test endpoints

## Troubleshooting Common Issues
1. **SSL Verification Failures**: Check certificate configuration
2. **DNS Resolution Errors**: Verify AdGuard Home configuration
3. **Timeout Issues**: Adjust timeout values in blackbox config
4. **Authentication Failures**: Check credentials in configuration

## Documentation to Update
- Add blackbox monitoring section to README.md
- Document SSL certificate management
- Include network troubleshooting guide
- Add uptime SLA tracking procedures