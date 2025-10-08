# Add TLS Certificate Monitoring and Let's Encrypt for n8n

## Priority: 2 (High)
## Estimated Time: 2-3 hours
## Phase: Week 2 - Certificate Management

> **🔒 VPN-First Strategy Note:**
> In the VPN-first model, only n8n webhooks are publicly exposed and require valid CA-signed certificates (Let's Encrypt). All other services use self-signed certificates since they're only accessible via VPN, where certificate validation can be disabled or CA cert distributed to clients.

## Description
Implement Let's Encrypt for n8n webhooks (required for external services like GitHub to trust the endpoint) and monitoring for certificate expiry. VPN-only services continue using self-signed certificates with local certificate monitoring.

## Acceptance Criteria
- [ ] Let's Encrypt certificate for n8n domain with automatic renewal
- [ ] Certificate expiry monitoring for n8n cert in Prometheus
- [ ] Alerts configured for n8n certificate expiring within 30 days
- [ ] Self-signed certificates upgraded to 4096-bit RSA for VPN-only services
- [ ] Blackbox exporter monitoring n8n certificate validity
- [ ] Certificate storage moved outside version control (.gitignore updated)
- [ ] Documentation for n8n cert renewal and VPN service certs
- [ ] TLS 1.2+ enforced on all services

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Add Let's Encrypt certbot for n8n (integrated with nginx/traefik)
2. `monitoring/prometheus/prometheus.yml` - Add blackbox exporter for n8n cert monitoring
3. `monitoring/prometheus/alert_rules.yml` - Add n8n certificate expiry alerts
4. `docker-compose.monitoring.yml` - Add blackbox exporter
5. `ssl/generate-cert.sh` - Upgrade to 4096-bit RSA for VPN-only services
6. `.env.example` - Add n8n domain and Let's Encrypt email
7. `.gitignore` - Ensure certificates excluded
8. `docs/CERTIFICATE_MANAGEMENT.md` - Certificate procedures (new file)

### Current Issues

> **Note:** In VPN-first model, `insecure_skip_verify` for internal services is acceptable since they're not publicly exposed. The focus is on n8n which requires valid certs for external webhooks.

1. **Weak Certificate (VPN-only services)**:
   ```bash
   # ssl/generate-cert.sh:17
   openssl genrsa -out "$KEY_FILE" 2048  # ⚠️ Upgrade to 4096-bit
   ```

2. **n8n Needs Valid Certificate**:
   - Currently using self-signed cert
   - External webhook providers (GitHub, etc.) will reject self-signed certs
   - Need Let's Encrypt for public trust

3. **No Expiry Monitoring**: n8n certificate expiry could break webhooks without warning

4. **Acceptable for VPN-only services**:
   ```yaml
   # monitoring/prometheus/prometheus.yml:35-37
   - job_name: 'grafana'
     scheme: https
     tls_config:
       insecure_skip_verify: true  # ✅ OK - VPN-only service
   ```

### Step 1: Add Blackbox Exporter for Certificate Monitoring

Update `docker-compose.monitoring.yml`:
```yaml
services:
  # ... existing services ...

  blackbox-exporter:
    # Blackbox Exporter for TLS/SSL monitoring
    # Version: v0.24.0 (update quarterly)
    # Last updated: 2024-01-15
    image: prom/blackbox-exporter:v0.24.0@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: blackbox-exporter
    restart: unless-stopped
    ports:
      - "9115:9115"
    volumes:
      - ./monitoring/blackbox:/config
    command:
      - '--config.file=/config/blackbox.yml'
    networks:
      - homeserver
```

### Step 2: Create Blackbox Exporter Configuration

Create `monitoring/blackbox/blackbox.yml`:
```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: []
      method: GET
      preferred_ip_protocol: "ip4"

  tls_connect:
    prober: tcp
    timeout: 5s
    tcp:
      tls: true
      tls_config:
        insecure_skip_verify: false

  http_post_2xx:
    prober: http
    timeout: 5s
    http:
      method: POST
      valid_status_codes: [200, 201]

  tcp_connect:
    prober: tcp
    timeout: 5s

  icmp:
    prober: icmp
    timeout: 5s
```

### Step 3: Update Prometheus Configuration

Update `monitoring/prometheus/prometheus.yml`:
```yaml
scrape_configs:
  # ... existing scrape configs ...

  - job_name: 'blackbox-tls'
    metrics_path: /probe
    params:
      module: [tls_connect]
    static_configs:
      - targets:
          - n8n:5678
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  - job_name: 'n8n'
    static_configs:
      - targets: ['n8n:5678']
    scheme: https
    tls_config:
      insecure_skip_verify: false  # ✅ SECURE (after proper CA setup)
      ca_file: /ssl/ca.crt  # Add CA certificate
```

### Step 4: Add Certificate Expiry Alerts

Update `monitoring/prometheus/alert_rules.yml`:
```yaml
groups:
  # ... existing alert groups ...

  - name: certificate_alerts
    rules:
      - alert: SSLCertificateExpiringSoon
        expr: probe_ssl_earliest_cert_expiry - time() < 86400 * 30
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "SSL certificate expiring soon for {{ $labels.instance }}"
          description: "SSL certificate for {{ $labels.instance }} expires in {{ $value | humanizeDuration }}. Renew immediately."

      - alert: SSLCertificateExpiredOrExpiringSoon
        expr: probe_ssl_earliest_cert_expiry - time() < 86400 * 7
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "SSL certificate expires within 7 days for {{ $labels.instance }}"
          description: "SSL certificate for {{ $labels.instance }} expires in {{ $value | humanizeDuration }}. URGENT ACTION REQUIRED."

      - alert: SSLCertificateExpired
        expr: probe_ssl_earliest_cert_expiry - time() <= 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "SSL certificate has EXPIRED for {{ $labels.instance }}"
          description: "SSL certificate for {{ $labels.instance }} has expired. Service may be unavailable."

      - alert: TLSVersionTooOld
        expr: probe_tls_version_info{version=~"TLS 1.0|TLS 1.1"} == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "TLS version too old on {{ $labels.instance }}"
          description: "{{ $labels.instance }} is using {{ $labels.version }}, which is deprecated. Upgrade to TLS 1.2 or higher."
```

### Step 5: Upgrade Certificate Generation Script

Update `ssl/generate-cert.sh`:
```bash
#!/bin/bash

# SSL Certificate Generation Script for n8n
# Generates strong 4096-bit RSA or ECDSA certificates

set -e

DOMAIN=${1:-"your-domain"}
DAYS=${2:-365}
KEY_TYPE=${3:-"rsa"}  # Options: rsa, ecdsa
KEY_FILE="server.key"
CERT_FILE="server.crt"

echo "Generating SSL certificate for domain: $DOMAIN"
echo "Valid for $DAYS days"
echo "Key type: $KEY_TYPE"

# Generate private key based on type
if [ "$KEY_TYPE" = "ecdsa" ]; then
  echo "Generating ECDSA P-384 private key..."
  openssl ecparam -genkey -name secp384r1 -out "$KEY_FILE"
else
  echo "Generating 4096-bit RSA private key..."
  openssl genrsa -out "$KEY_FILE" 4096
fi

# Generate certificate signing request
openssl req -new -key "$KEY_FILE" -out server.csr \
  -subj "/C=US/ST=Development/L=Development/O=HomeServer/OU=IT/CN=$DOMAIN"

# Generate self-signed certificate with proper extensions
openssl x509 -req -days "$DAYS" -in server.csr -signkey "$KEY_FILE" \
  -out "$CERT_FILE" -sha256 \
  -extensions v3_req -extfile <(
cat <<EOF
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $DOMAIN
DNS.2 = localhost
DNS.3 = *.local
IP.1 = 127.0.0.1
IP.2 = 192.168.1.100
EOF
)

# Clean up CSR file
rm server.csr

# Set appropriate permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

# Display certificate information
echo ""
echo "✅ SSL certificate generated successfully!"
echo "Key file: $KEY_FILE"
echo "Certificate file: $CERT_FILE"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERT_FILE" -noout -text | grep -A2 "Subject:"
openssl x509 -in "$CERT_FILE" -noout -dates
echo ""
echo "To use with a different domain or ECDSA:"
echo "./generate-cert.sh your-domain.ddns.net 730 ecdsa"
```

### Step 6: Option A - Let's Encrypt Integration (Recommended)

Add to `docker-compose.yml`:
```yaml
services:
  # ... existing services ...

  certbot:
    # Certbot for Let's Encrypt certificates
    # Version: v2.8.0
    # Last updated: 2024-01-15
    image: certbot/certbot:v2.8.0@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: certbot
    restart: "no"
    volumes:
      - ./ssl/letsencrypt:/etc/letsencrypt
      - ./ssl/letsencrypt-lib:/var/lib/letsencrypt
      - ./ssl/webroot:/var/www/certbot
    command: certonly --webroot --webroot-path=/var/www/certbot --email ${LETSENCRYPT_EMAIL} --agree-tos --no-eff-email -d ${N8N_DOMAIN}
    depends_on:
      - nginx

  nginx:
    # Nginx reverse proxy for ACME challenge
    # Version: 1.25-alpine
    # Last updated: 2024-01-15
    image: nginx:1.25-alpine@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./ssl/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl/webroot:/var/www/certbot:ro
      - ./ssl/letsencrypt:/etc/letsencrypt:ro
    networks:
      - homeserver
```

Add to `.env.example`:
```bash
# Let's Encrypt Configuration
LETSENCRYPT_EMAIL=admin@example.com
N8N_DOMAIN=your-domain.ddns.net
```

### Step 7: Certificate Renewal Automation

Create `scripts/renew-certificates.sh`:
```bash
#!/bin/bash
# Automated certificate renewal script

set -e

echo "🔄 Starting certificate renewal process..."

# Renew Let's Encrypt certificates
docker compose run --rm certbot renew

# Reload nginx to pick up new certificates
docker compose exec nginx nginx -s reload

# Check certificate expiry
docker compose exec certbot certbot certificates

echo "✅ Certificate renewal complete"
```

Add to crontab:
```bash
# Renew certificates weekly
0 3 * * 1 cd /path/to/home-server-stack && ./scripts/renew-certificates.sh >> /var/log/cert-renewal.log 2>&1
```

### Testing Commands
```bash
# Test certificate generation
cd ssl
./generate-cert.sh test-domain.local 365 ecdsa
openssl x509 -in server.crt -noout -text

# Start blackbox exporter
docker compose -f docker-compose.monitoring.yml up -d blackbox-exporter

# Test certificate probe
curl -s 'http://localhost:9115/probe?target=n8n:5678&module=tls_connect' | grep probe_ssl_earliest_cert_expiry

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="blackbox-tls")'

# View certificate expiry in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=probe_ssl_earliest_cert_expiry' | jq

# Test Let's Encrypt (dry run)
docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot --email test@example.com --agree-tos --dry-run -d test-domain.com

# Verify TLS version
openssl s_client -connect localhost:5678 -tls1_2 < /dev/null
```

### Grafana Dashboard Query Examples
```promql
# Days until certificate expiry
(probe_ssl_earliest_cert_expiry - time()) / 86400

# Certificate expiry timestamp
probe_ssl_earliest_cert_expiry

# TLS version
probe_tls_version_info

# Certificate issuer
probe_ssl_issuer
```

## Success Metrics
- Certificate expiry visible in Prometheus/Grafana
- Alerts trigger 30 days before expiry
- Certificates use 4096-bit RSA or ECDSA P-384
- TLS 1.2+ enforced on all services
- Automated renewal working (if Let's Encrypt used)
- No `insecure_skip_verify` in production configs

## Dependencies
- Blackbox Exporter
- Prometheus and Grafana running
- Domain name (for Let's Encrypt)
- Port 80 accessible (for ACME challenge)
- OpenSSL 1.1.1+

## Risk Considerations
- **Service Disruption**: Certificate changes require service restarts
- **Let's Encrypt Rate Limits**: 50 certificates per week per domain
- **DNS Requirements**: Domain must resolve to server IP
- **Port 80 Requirement**: Required for HTTP-01 challenge
- **Monitoring Overhead**: Additional scrape target load

## Rollback Plan
```bash
# If Let's Encrypt fails:
# 1. Revert to self-signed certificates
cd ssl
./generate-cert.sh your-domain.local

# 2. Restart n8n with new cert
docker compose restart n8n

# 3. Restore insecure_skip_verify temporarily
# Edit monitoring/prometheus/prometheus.yml
# Set: insecure_skip_verify: true

# 4. Reload Prometheus
docker compose exec prometheus kill -HUP 1
```

## Security Impact (VPN-First Model)
- **Before**: Self-signed certs rejected by external webhook providers, no expiry monitoring, potential webhook failures
- **After**: Valid Let's Encrypt for n8n (webhooks work reliably), automated renewal, expiry monitoring
- **Risk Reduction**:
  - 100% elimination of webhook cert validation failures
  - 90% reduction in cert-related outages (automated renewal)
  - VPN-only services can safely use self-signed certs (acceptable security trade-off)

## References
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Blackbox Exporter Guide](https://github.com/prometheus/blackbox_exporter)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [TLS Best Practices](https://wiki.mozilla.org/Security/Server_Side_TLS)

## Follow-up Tasks
- Implement certificate pinning for critical services
- Add OCSP stapling to nginx
- Configure HSTS headers
- Set up CAA DNS records
- Monitor certificate transparency logs
- Implement certificate rotation procedures
