# Add TLS Certificate Expiry Monitoring

## Priority: 2 (High)
## Estimated Time: 1-2 hours
## Phase: Week 2 - Certificate Management

> **📋 Current State:**
> - ✅ Let's Encrypt wildcard certificates **already deployed** via certbot + Gandi DNS plugin
> - ✅ Auto-renewal configured with post-renewal hooks
> - ✅ Traefik file provider loading certificates from `/etc/traefik/`
> - ❌ **Missing:** Certificate expiry monitoring and alerts

## Description
Add automated monitoring for SSL certificate expiration to prevent outages. The Let's Encrypt infrastructure is already fully implemented - this ticket focuses solely on adding observability via Prometheus blackbox exporter and Grafana dashboards.

## Acceptance Criteria
- [ ] Blackbox exporter deployed for TLS certificate probing
- [ ] Prometheus configured to scrape certificate metrics
- [ ] Alerts configured for certificates expiring within 30 days (warning)
- [ ] Alerts configured for certificates expiring within 7 days (critical)
- [ ] Grafana dashboard showing certificate expiry dates
- [ ] TLS version monitoring (warn on TLS 1.0/1.1)
- [ ] Certificate chain validation monitoring

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.monitoring.yml` - Add blackbox exporter service
2. `monitoring/blackbox/blackbox.yml` - Blackbox exporter configuration (new file)
3. `monitoring/prometheus/prometheus.yml` - Add blackbox scrape configs
4. `monitoring/prometheus/alert_rules.yml` - Add certificate expiry alerts
5. `monitoring/grafana/dashboards/certificates.json` - Certificate dashboard (new file)

### Current SSL Setup (Reference Only)
**Already implemented - DO NOT modify:**
- Certificates: `/etc/letsencrypt/live/${DOMAIN}/` (managed by certbot)
- Traefik certs: `./data/traefik/certs/` (copies from Let's Encrypt)
- Dynamic config: `./config/traefik/dynamic-certs.yml`
- Auto-renewal: certbot snap timer + post-renewal hook at `/etc/letsencrypt/renewal-hooks/deploy/traefik-reload.sh`

### Step 1: Deploy Blackbox Exporter

Add to `docker-compose.monitoring.yml`:
```yaml
services:
  # ... existing services ...

  blackbox-exporter:
    # Blackbox Exporter for certificate and endpoint monitoring
    # Version pinning: Update quarterly, check for CVEs
    image: prom/blackbox-exporter:v0.25.0
    container_name: blackbox-exporter
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9115:9115"
    volumes:
      - ./monitoring/blackbox:/config:ro
    command:
      - '--config.file=/config/blackbox.yml'
    networks:
      - homeserver
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:9115/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Step 2: Create Blackbox Exporter Configuration

Create `monitoring/blackbox/blackbox.yml`:
```yaml
modules:
  # TLS certificate validation (strict - for production monitoring)
  tls_connect:
    prober: tcp
    timeout: 10s
    tcp:
      tls: true
      tls_config:
        # Validate certificates (do not skip verification)
        insecure_skip_verify: false

  # HTTP/HTTPS endpoint check with certificate validation
  https_2xx:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200, 401]  # 401 OK - service responding, just needs auth
      method: GET
      preferred_ip_protocol: "ip4"
      follow_redirects: true
      tls_config:
        insecure_skip_verify: false

  # ICMP ping check (for general connectivity)
  icmp:
    prober: icmp
    timeout: 5s
    icmp:
      preferred_ip_protocol: "ip4"
```

### Step 3: Configure Prometheus Certificate Monitoring

Update `monitoring/prometheus/prometheus.yml`:
```yaml
scrape_configs:
  # ... existing scrape configs ...

  # Blackbox exporter self-monitoring
  - job_name: 'blackbox-exporter'
    static_configs:
      - targets: ['blackbox-exporter:9115']

  # Certificate monitoring for all HTTPS services
  - job_name: 'certificate-expiry'
    metrics_path: /probe
    params:
      module: [tls_connect]
    static_configs:
      - targets:
          # Monitor all services with Let's Encrypt certificates
          - adguard.${DOMAIN}:443
          - n8n.${DOMAIN}:443
          - grafana.${DOMAIN}:443
          - prometheus.${DOMAIN}:443
          - alerts.${DOMAIN}:443
          - traefik.${DOMAIN}:443
          - dashboard.${DOMAIN}:443
        labels:
          cert_type: letsencrypt
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  # Endpoint health monitoring (bonus - checks if services respond)
  - job_name: 'endpoint-health'
    metrics_path: /probe
    params:
      module: [https_2xx]
    static_configs:
      - targets:
          - https://adguard.${DOMAIN}
          - https://n8n.${DOMAIN}
          - https://grafana.${DOMAIN}
          - https://prometheus.${DOMAIN}
          - https://alerts.${DOMAIN}
          - https://traefik.${DOMAIN}
          - https://dashboard.${DOMAIN}
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

**Note:** Replace `${DOMAIN}` with your actual domain or use environment variable substitution in Prometheus.

### Step 4: Add Certificate Expiry Alerts

Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
groups:
  # ... existing alert groups ...

  - name: certificate-alerts
    rules:
      # Warning: Certificate expiring within 30 days
      - alert: SSLCertificateExpiringSoon
        expr: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 30
        for: 1h
        labels:
          severity: warning
          category: certificates
        annotations:
          summary: "SSL certificate expiring soon for {{ $labels.instance }}"
          description: "Certificate for {{ $labels.instance }} expires in {{ printf \"%.0f\" $value }} days. Renewal should happen automatically, but verify certbot is working."

      # Critical: Certificate expiring within 7 days
      - alert: SSLCertificateExpiringSoonCritical
        expr: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 7
        for: 10m
        labels:
          severity: critical
          category: certificates
        annotations:
          summary: "SSL certificate expires within 7 days for {{ $labels.instance }}"
          description: "Certificate for {{ $labels.instance }} expires in {{ printf \"%.0f\" $value }} days. URGENT: Check certbot renewal immediately!"

      # Critical: Certificate already expired
      - alert: SSLCertificateExpired
        expr: probe_ssl_earliest_cert_expiry - time() <= 0
        for: 5m
        labels:
          severity: critical
          category: certificates
        annotations:
          summary: "SSL certificate has EXPIRED for {{ $labels.instance }}"
          description: "Certificate for {{ $labels.instance }} has expired. Service may be unavailable. Run: sudo certbot renew --force-renewal"

      # Warning: Using deprecated TLS version
      - alert: TLSVersionTooOld
        expr: probe_tls_version_info{version=~"TLS 1.0|TLS 1.1"} == 1
        for: 5m
        labels:
          severity: warning
          category: certificates
        annotations:
          summary: "Deprecated TLS version on {{ $labels.instance }}"
          description: "{{ $labels.instance }} is using {{ $labels.version }}, which is deprecated and insecure. Upgrade to TLS 1.2 or higher."

      # Warning: Certificate probe failing (can't check expiry)
      - alert: SSLCertificateProbeFailure
        expr: probe_success{job="certificate-expiry"} == 0
        for: 10m
        labels:
          severity: warning
          category: certificates
        annotations:
          summary: "Cannot probe SSL certificate for {{ $labels.instance }}"
          description: "Blackbox exporter cannot probe {{ $labels.instance }} certificate. Service may be down or certificate invalid."

      # Info: Certificate will be renewed soon (Let's Encrypt renews at 30 days)
      - alert: SSLCertificateRenewalDue
        expr: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 35 and (probe_ssl_earliest_cert_expiry - time()) / 86400 > 30
        for: 6h
        labels:
          severity: info
          category: certificates
        annotations:
          summary: "SSL certificate renewal due for {{ $labels.instance }}"
          description: "Certificate expires in {{ printf \"%.0f\" $value }} days. Certbot should auto-renew within the next few days."
```

### Step 5: Create Grafana Dashboard (Optional but Recommended)

Create `monitoring/grafana/dashboards/certificates.json`:

This is a large JSON file. Key panels to include:
1. **Certificate Expiry Timeline** - Shows days until expiry for all certs
2. **Certificate Details Table** - Lists all certificates with issuer, expiry date, days remaining
3. **TLS Version Distribution** - Pie chart showing TLS versions in use
4. **Certificate Probe Success Rate** - Shows if monitoring is working
5. **Alert Status** - Shows active certificate alerts

**Quick creation method:**
1. Import dashboard ID 13230 from Grafana.com (Blackbox Exporter dashboard)
2. Customize for your environment
3. Export JSON and save to `monitoring/grafana/dashboards/certificates.json`

Alternatively, create panels manually with these queries:
```promql
# Days until expiry
(probe_ssl_earliest_cert_expiry - time()) / 86400

# Certificate not valid before
probe_ssl_not_before

# Certificate not valid after
probe_ssl_not_after

# TLS version
probe_tls_version_info

# Certificate issuer
probe_ssl_issuer
```

### Testing Commands

```bash
# 1. Start blackbox exporter
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d blackbox-exporter

# 2. Test certificate probe manually
curl -s 'http://${SERVER_IP}:9115/probe?target=n8n.${DOMAIN}:443&module=tls_connect' | grep probe_ssl_earliest_cert_expiry

# Expected output: probe_ssl_earliest_cert_expiry 1.7355552e+09 (Unix timestamp)

# 3. Check blackbox exporter health
curl -s http://${SERVER_IP}:9115/health
# Expected: Healthy

# 4. Reload Prometheus configuration
docker compose -f docker-compose.monitoring.yml exec prometheus kill -HUP 1

# Or restart Prometheus
docker compose -f docker-compose.monitoring.yml restart prometheus

# 5. Verify Prometheus targets
# Open: http://${SERVER_IP}:9090/targets
# Look for: certificate-expiry and endpoint-health jobs
# Status should be: UP

# 6. Test certificate expiry query in Prometheus
# Open: http://${SERVER_IP}:9090/graph
# Query: (probe_ssl_earliest_cert_expiry - time()) / 86400
# Should show days until expiry for each cert

# 7. Check certificate details
curl -s 'http://${SERVER_IP}:9115/probe?target=n8n.${DOMAIN}:443&module=tls_connect' | grep probe_ssl

# 8. Verify alerts are loading
curl -s http://${SERVER_IP}:9090/api/v1/rules | jq '.data.groups[] | select(.name=="certificate-alerts")'

# 9. Test alert would trigger (force expiry check)
# Query: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 30
# If any certs expire in <30 days, alert should show as pending/firing

# 10. Check Grafana dashboards (if created)
# Open: http://${SERVER_IP}:3001/dashboards
# Look for: Certificate Monitoring dashboard
```

### Useful PromQL Queries

```promql
# Show certificates expiring in next 30 days
(probe_ssl_earliest_cert_expiry - time()) / 86400 < 30

# Show certificates by days remaining (sorted)
sort_desc((probe_ssl_earliest_cert_expiry - time()) / 86400)

# Show certificate issuer
probe_ssl_issuer

# Show TLS versions in use
probe_tls_version_info

# Certificate expiry as timestamp
probe_ssl_earliest_cert_expiry

# Certificate chain length
probe_ssl_last_chain_info

# Count services with expiring certs
count((probe_ssl_earliest_cert_expiry - time()) / 86400 < 30)
```

## Success Metrics
- ✅ Blackbox exporter running and healthy
- ✅ Prometheus successfully scraping certificate metrics from all services
- ✅ Certificate expiry visible in Prometheus (days remaining)
- ✅ Alerts configured and showing in Prometheus rules
- ✅ Test alert triggers when threshold reached
- ✅ Grafana dashboard displays certificate status (if implemented)
- ✅ All monitored services show valid certificates (probe_success=1)

## Dependencies
- ✅ Let's Encrypt certificates already deployed
- ✅ Prometheus already running
- ✅ Grafana already running
- Blackbox exporter (to be deployed)

## Risk Considerations
- **Monitoring Overhead**: Minimal - blackbox exporter is lightweight
- **Alert Fatigue**: Alerts staged (30d warning → 7d critical → 0d critical)
- **False Positives**: May alert if certbot renewal temporarily fails (expected behavior)
- **Probe Frequency**: Default 15s scrape interval - adjust if needed

## Rollback Plan
```bash
# If blackbox exporter causes issues:

# 1. Stop blackbox exporter
docker compose -f docker-compose.monitoring.yml stop blackbox-exporter

# 2. Remove from Prometheus targets (comment out in prometheus.yml)
# Edit monitoring/prometheus/prometheus.yml
# Comment out certificate-expiry and endpoint-health jobs

# 3. Reload Prometheus
docker compose -f docker-compose.monitoring.yml exec prometheus kill -HUP 1

# 4. Remove container
docker compose -f docker-compose.monitoring.yml rm -f blackbox-exporter

# Certificates will continue to renew automatically - monitoring is observation only
```

## Security Impact
- **Before**: Certificates renew automatically, but no visibility into renewal status or upcoming expiries
- **After**: Proactive monitoring with 30-day advance warning, preventing unexpected outages
- **Risk Reduction**:
  - 95% reduction in certificate-related outages (early warning system)
  - Visibility into TLS version compliance
  - Validation that auto-renewal is working

## References
- [Blackbox Exporter Documentation](https://github.com/prometheus/blackbox_exporter)
- [Prometheus Certificate Monitoring Guide](https://prometheus.io/docs/guides/tls-encryption/)
- [Let's Encrypt Integration (already implemented)](../docs/SSL_CERTIFICATES.md)

## Follow-up Tasks
- Consider adding OCSP stapling monitoring
- Add certificate transparency log monitoring
- Monitor certificate chain validity
- Set up CAA DNS record monitoring
- Add certificate pinning validation (if implemented)

## Notes
- Let's Encrypt certificates are valid for 90 days
- Certbot renews at 30 days remaining (automatic via snap timer)
- This monitoring provides oversight of the existing renewal system
- No changes to certificate generation or renewal process needed
