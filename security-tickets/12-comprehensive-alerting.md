# Configure Comprehensive Security Alerting

## Priority: 3 (Medium)
## Estimated Time: 3-4 hours
## Phase: Month 2 - Medium Priority Hardening

## Description
Configure AlertManager with multiple notification channels (email, Slack, PagerDuty) for security events, including authentication failures, resource issues, and certificate expiry.

## Acceptance Criteria
- [ ] AlertManager routes configured for severity levels
- [ ] Slack/email notifications working
- [ ] Security-specific alert rules created
- [ ] Alert deduplication configured
- [ ] On-call rotation setup (optional)
- [ ] Alert documentation and runbooks

## Technical Implementation Details

**monitoring/alertmanager/alertmanager.yml:**
```yaml
global:
  resolve_timeout: 5m
  slack_api_url: ${SLACK_WEBHOOK_URL}
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@yourdomain.com'
  smtp_auth_username: ${SMTP_USERNAME}
  smtp_auth_password: ${SMTP_PASSWORD}

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      continue: true
    - match:
        severity: warning
      receiver: 'warning-alerts'
    - match_re:
        alertname: '(AuthenticationFailure|BruteForce|Unauthorized)'
      receiver: 'security-alerts'
      continue: true

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@yourdomain.com'

  - name: 'critical-alerts'
    slack_configs:
      - channel: '#alerts-critical'
        title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
    pagerduty_configs:
      - service_key: ${PAGERDUTY_SERVICE_KEY}

  - name: 'security-alerts'
    slack_configs:
      - channel: '#security-alerts'
        title: '🔐 Security Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
    email_configs:
      - to: 'security@yourdomain.com'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Additional alert rules (monitoring/prometheus/alert_rules.yml):**
```yaml
groups:
  - name: security_alerts
    rules:
      - alert: UnauthorizedAccessAttempt
        expr: rate(nginx_http_requests_total{status="401"}[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate of 401 responses"
          description: "Possible unauthorized access attempts"

      - alert: SuspiciousNetworkActivity
        expr: rate(container_network_transmit_bytes_total[1m]) > 100000000
        labels:
          severity: warning
        annotations:
          summary: "Unusual network traffic detected"

      - alert: ContainerRestart
        expr: rate(container_last_seen[5m]) > 2
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} restarting frequently"
```

## Testing Commands
```bash
# Test AlertManager config
docker exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml

# Send test alert
curl -X POST http://localhost:9093/api/v1/alerts -d '[{"labels":{"alertname":"test"}}]'

# Check alert routing
docker exec alertmanager amtool config routes test --config.file=/etc/alertmanager/alertmanager.yml

# View active alerts
curl http://localhost:9093/api/v2/alerts
```

## Success Metrics
- Alerts delivered to correct channels
- No alert spam (proper grouping)
- Critical alerts reach on-call
- Alert fatigue minimized

## References
- [AlertManager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
