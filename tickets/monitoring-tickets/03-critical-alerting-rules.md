# Implement Critical Alerting Rules

## Priority: 1 (Critical)
## Estimated Time: 2-3 hours
## Phase: Week 1 - Foundation

## Description
Configure critical alerting rules in Prometheus for service down detection, resource exhaustion, and infrastructure failures. Set up AlertManager for routing notifications to appropriate channels.

## Acceptance Criteria
- [x] Service down alerts for all containers (using Prometheus `up{}` metric)
- [x] Resource exhaustion alerts (CPU, memory, disk)
- [ ] SSL certificate expiration alerts (deferred to blackbox monitoring - ticket #08)
- [x] Service monitoring alerts (AdGuard, n8n, Ollama via Prometheus targets)
- [x] AlertManager configured with notification channels (webhook + email templates)
- [x] Alert rules tested and firing correctly
- [x] Proper alert severity levels and labels
- [x] Alert suppression and grouping configured

**Note:** SSL certificate monitoring and advanced endpoint probing require Blackbox Exporter, which will be implemented in a separate ticket (monitoring-tickets/08-blackbox-monitoring.md).

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
      - alert: PrometheusTargetDown
        expr: up{job=~"prometheus|node-exporter|cadvisor"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Monitoring target {{ $labels.job }} is down"
          description: "{{ $labels.job }} monitoring target on {{ $labels.instance }} has been down for more than 1 minute"

      - alert: AdGuardDown
        expr: up{job="adguard"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "AdGuard DNS service is down"
          description: "AdGuard service is not responding for more than 1 minute"

      - alert: N8nDown
        expr: up{job="n8n"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "n8n automation service is down"
          description: "n8n service is not responding for more than 2 minutes"

      - alert: OllamaDown
        expr: up{job="ollama"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Ollama AI service is down"
          description: "Ollama API is not responding for more than 2 minutes"

  - name: resource-alerts
    rules:
      - alert: HighDiskIOWait
        expr: rate(node_disk_io_time_seconds_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High disk I/O wait time"
          description: "Disk I/O wait time is high on {{ $labels.instance }} for more than 10 minutes"

      - alert: HighNetworkTraffic
        expr: rate(node_network_receive_bytes_total{device!~"lo|docker.*"}[5m]) > 100000000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High network traffic detected"
          description: "Network interface {{ $labels.device }} on {{ $labels.instance }} is receiving high traffic for more than 10 minutes"

      - alert: SystemLoadHigh
        expr: node_load15 / count(node_cpu_seconds_total{mode="idle"}) without (cpu, mode) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "System load is high"
          description: "15-minute load average on {{ $labels.instance }} is above 2x CPU count for more than 10 minutes"
```

### AlertManager Configuration (`monitoring/alertmanager/alertmanager.yml`)
```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@homeserver.local'
  smtp_require_tls: false

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
    webhook_configs:
      - url: 'http://127.0.0.1:5001/'
        send_resolved: true

  - name: 'critical-alerts'
    webhook_configs:
      - url: 'http://127.0.0.1:5001/'
        send_resolved: true
    # Email notifications can be configured by uncommenting:
    # email_configs:
    #   - to: 'admin@your-domain.com'
    #     headers:
    #       Subject: '🚨 CRITICAL Alert: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    #     html: |
    #       <html>
    #       <body>
    #         <h2 style="color: #d9534f;">🚨 Critical Alert</h2>
    #         {{ range .Alerts }}
    #         <div style="border-left: 4px solid #d9534f; padding-left: 10px; margin: 10px 0;">
    #           <p><strong>Alert:</strong> {{ .Annotations.summary }}</p>
    #           <p><strong>Description:</strong> {{ .Annotations.description }}</p>
    #           <p><strong>Severity:</strong> {{ .Labels.severity }}</p>
    #           <p><strong>Time:</strong> {{ .StartsAt }}</p>
    #         </div>
    #         {{ end }}
    #       </body>
    #       </html>

  - name: 'warning-alerts'
    webhook_configs:
      - url: 'http://127.0.0.1:5001/'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

### Environment Variables to Add
Add to `.env.example`:
```bash
# AlertManager Configuration
WEBHOOK_URL=http://127.0.0.1:5001/
ALERT_EMAIL_FROM=alerts@homeserver.local
ALERT_EMAIL_USER=alerts@your-domain.com
ALERT_EMAIL_PASS=your_email_app_password
ALERT_EMAIL_TO=admin@your-domain.com

# Optional integrations (Slack, PagerDuty, etc.) can be configured in alertmanager.yml
```

**Note:** Webhook integration is configured by default for local testing. For production use, configure email or integrate with external services like Slack, PagerDuty, or OpsGenie by updating `alertmanager.yml`.

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
   ```bash
   docker compose stop adguard
   # Wait 1-2 minutes and check alerts
   curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="AdGuardDown")'
   ```

2. **High CPU**: Use stress testing to trigger CPU alerts
   ```bash
   # Install stress-ng if needed: apt-get install stress-ng
   stress-ng --cpu 8 --timeout 360s
   # Monitor alerts during test
   ```

3. **High Memory**: Create memory pressure to test memory alerts
   ```bash
   stress-ng --vm 2 --vm-bytes 90% --timeout 300s
   ```

4. **Disk Space**: Create large files to test disk space alerts
   ```bash
   fallocate -l 10G /tmp/testfile
   # Remove after testing: rm /tmp/testfile
   ```

5. **Container Restart**: Trigger restart loop detection
   ```bash
   # Restart container multiple times in 1 hour
   for i in {1..4}; do docker compose restart adguard; sleep 600; done
   ```

### Notification Channel Setup
1. **Webhook Integration** (Default):
   - Webhook receiver running on http://127.0.0.1:5001/
   - Can be replaced with custom webhook endpoint
   - Alerts sent in JSON format

2. **Email Notifications** (Optional):
   - Uncomment email_configs in alertmanager.yml
   - Configure SMTP settings in global section
   - Test email delivery for critical alerts
   - Set up distribution lists if needed

3. **Third-party Integrations** (Optional):
   - Slack: Add slack_configs with webhook URL
   - PagerDuty: Add pagerduty_configs with service key
   - OpsGenie: Add opsgenie_configs with API key
   - See AlertManager documentation for full integration list

## Success Metrics
- All alert rules validate without syntax errors
- Test alerts fire correctly within expected timeframes
- Notifications delivered to configured channels
- No false positive alerts during normal operation
- Alert suppression and grouping working correctly

## Dependencies
- ✅ Completed: "Add Core Monitoring Stack (Foundation)"
- ✅ Prometheus running and collecting metrics
- ✅ AlertManager container running
- ⚠️ Access to notification channels (webhook default, email/Slack optional)

**Note:** Advanced monitoring features like blackbox probing and SSL certificate checks will be added in ticket #08 (Blackbox Monitoring).

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