# Implement Critical Alerting Rules

## Priority: 1 (Critical)
## Estimated Time: 2-3 hours
## Phase: Week 1 - Foundation

## Description
Configure critical alerting rules in Prometheus for service down detection, resource exhaustion, and infrastructure failures. Set up AlertManager for routing notifications to appropriate channels.

## Acceptance Criteria
- [ ] Service down alerts for all containers
- [ ] Resource exhaustion alerts (CPU, memory, disk)
- [ ] SSL certificate expiration alerts
- [ ] DNS service failure alerts
- [ ] AlertManager configured with notification channels
- [ ] Alert rules tested and firing correctly
- [ ] Proper alert severity levels and labels
- [ ] Alert suppression and grouping configured

## Technical Implementation Details

### Files to Create/Modify
1. `monitoring/prometheus/alert_rules.yml` - Prometheus alerting rules
2. `monitoring/alertmanager/alertmanager.yml` - AlertManager configuration
3. `monitoring/alertmanager/templates/` - Custom alert templates
4. `.env` - Add notification webhook URLs and credentials

### Alert Rules Configuration (`monitoring/prometheus/alert_rules.yml`)
```yaml
groups:
  - name: critical-alerts
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "Service {{ $labels.job }} has been down for more than 30 seconds"

      - alert: HighCPUUsage
        expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is above 85% for more than 5 minutes (current value: {{ $value }}%)"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is above 90% for more than 3 minutes (current value: {{ $value }}%)"

      - alert: DiskSpaceLow
        expr: 100 - ((node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100) > 90
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space critically low"
          description: "Disk space usage is above 90% for more than 5 minutes (current value: {{ $value }}%)"

      - alert: ContainerDown
        expr: container_last_seen{name=~"adguard|n8n|ollama"} < (time() - 60)
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.name }} is down"
          description: "Container {{ $labels.name }} has not been seen for more than 1 minute"

      - alert: ContainerHighCPU
        expr: rate(container_cpu_usage_seconds_total{name=~".+"}[5m]) * 100 > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} high CPU usage"
          description: "Container {{ $labels.name }} CPU usage is above 80% for more than 10 minutes"

      - alert: ContainerHighMemory
        expr: (container_memory_usage_bytes{name=~".+"} / container_spec_memory_limit_bytes{name=~".+"}) * 100 > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} high memory usage"
          description: "Container {{ $labels.name }} memory usage is above 85% for more than 10 minutes"

      - alert: ContainerRestartLoop
        expr: increase(container_start_time_seconds{name=~".+"}[1h]) > 3
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} restarting frequently"
          description: "Container {{ $labels.name }} has restarted {{ $value }} times in the last hour"

  - name: service-specific-alerts
    rules:
      - alert: AdGuardDNSDown
        expr: probe_success{job="blackbox", instance="SERVER_IP:53"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AdGuard DNS service is down"
          description: "DNS resolution through AdGuard is failing"

      - alert: N8nWebhookDown
        expr: probe_success{job="blackbox", instance="https://SERVER_IP:5678"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "n8n service is unreachable"
          description: "n8n webhook endpoint is not responding"

      - alert: OllamaAPIDown
        expr: probe_success{job="blackbox", instance="SERVER_IP:11434"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Ollama API is down"
          description: "Ollama API endpoint is not responding"

  - name: ssl-certificate-alerts
    rules:
      - alert: SSLCertificateExpiring
        expr: probe_ssl_earliest_cert_expiry{job="blackbox"} - time() < 7 * 24 * 3600
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "SSL certificate expiring soon"
          description: "SSL certificate for {{ $labels.instance }} expires in less than 7 days"

      - alert: SSLCertificateExpired
        expr: probe_ssl_earliest_cert_expiry{job="blackbox"} - time() < 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "SSL certificate expired"
          description: "SSL certificate for {{ $labels.instance }} has expired"
```

### AlertManager Configuration (`monitoring/alertmanager/alertmanager.yml`)
```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@your-domain.com'
  smtp_auth_username: '${ALERT_EMAIL_USER}'
  smtp_auth_password: '${ALERT_EMAIL_PASS}'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 10s
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: 'warning-alerts'
      repeat_interval: 30m

receivers:
  - name: 'default-receiver'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#monitoring'
        title: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'critical-alerts'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#alerts-critical'
        title: '🚨 CRITICAL: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        send_resolved: true
    email_configs:
      - to: '${ALERT_EMAIL_TO}'
        subject: '🚨 CRITICAL Alert: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Severity: {{ .Labels.severity }}
          Time: {{ .StartsAt }}
          {{ end }}

  - name: 'warning-alerts'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#monitoring'
        title: '⚠️  WARNING: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

### Environment Variables to Add
Add to `.env`:
```bash
# AlertManager Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
ALERT_EMAIL_USER=alerts@your-domain.com
ALERT_EMAIL_PASS=your_email_app_password
ALERT_EMAIL_TO=admin@your-domain.com

# Optional: PagerDuty Integration
PAGERDUTY_INTEGRATION_KEY=your_pagerduty_integration_key
```

### Testing Commands
```bash
# Validate alert rules syntax
docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml

# Check AlertManager configuration
docker exec alertmanager amtool config check /etc/alertmanager/alertmanager.yml

# View active alerts
curl http://SERVER_IP:9090/api/v1/alerts

# View AlertManager status
curl http://SERVER_IP:9093/api/v1/status

# Test alert firing (temporary high CPU)
stress-ng --cpu 8 --timeout 60s

# Send test alert to AlertManager
curl -XPOST http://SERVER_IP:9093/api/v1/alerts -H "Content-Type: application/json" -d '[{
  "labels": {
    "alertname": "TestAlert",
    "severity": "warning"
  },
  "annotations": {
    "summary": "Test alert",
    "description": "This is a test alert"
  },
  "startsAt": "2024-01-01T00:00:00Z"
}]'
```

### Alert Testing Scenarios
1. **Service Down**: Stop a container and verify alert fires
2. **High CPU**: Use stress testing to trigger CPU alerts
3. **High Memory**: Create memory pressure to test memory alerts
4. **Disk Space**: Create large files to test disk space alerts
5. **SSL Certificate**: Test with expired certificate

### Notification Channel Setup
1. **Slack Integration**:
   - Create Slack app with incoming webhook
   - Configure webhook URL in environment variables
   - Test notification delivery

2. **Email Notifications**:
   - Configure SMTP settings for email provider
   - Test email delivery for critical alerts
   - Set up distribution lists if needed

## Success Metrics
- All alert rules validate without syntax errors
- Test alerts fire correctly within expected timeframes
- Notifications delivered to configured channels
- No false positive alerts during normal operation
- Alert suppression and grouping working correctly

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- Prometheus running and collecting metrics
- AlertManager container running
- Access to notification channels (Slack, email)

## Risk Considerations
- Alert fatigue from too many notifications
- False positives during legitimate high usage
- Notification delivery failures
- Alert rule syntax errors breaking Prometheus

## Rollback Plan
```bash
# Disable alerting rules
docker exec prometheus mv /etc/prometheus/alert_rules.yml /etc/prometheus/alert_rules.yml.disabled
docker exec prometheus kill -HUP 1

# Stop AlertManager
docker compose stop alertmanager
```

## Documentation to Update
- Add alert descriptions to README.md
- Document notification channel setup
- Include alert response procedures
- Add troubleshooting guide for alerts