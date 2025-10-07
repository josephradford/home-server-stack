# Deploy Reverse Proxy for n8n Path-Based Access Control

## Priority: 3 (Medium)
## Estimated Time: 2-3 hours
## Phase: Week 2-3 - Path-Based Security

> **🔒 VPN-First Strategy Note:**
> In the VPN-first model, most services are not publicly exposed. This ticket focuses on **n8n only**: allowing webhook endpoints (`/webhook/*`) to be public for external integrations while requiring VPN access for the admin UI. Traefik/Nginx will enforce path-based access control and rate limiting.

## Description
Deploy a lightweight reverse proxy (Nginx or Traefik) to enforce path-based access control for n8n. Public traffic can only access `/webhook/*` endpoints (for GitHub webhooks, etc.), while all other paths (UI, API) require VPN authentication. Includes rate limiting for DDoS protection on webhook endpoints.

## Acceptance Criteria
- [ ] Nginx or Traefik reverse proxy deployed for n8n only
- [ ] Path-based routing: `/webhook/*` public, all other paths blocked from internet
- [ ] VPN network allowlisting for non-webhook paths
- [ ] Rate limiting on webhook endpoints (prevent DDoS)
- [ ] HTTPS with Let's Encrypt for n8n webhooks (external services require valid certs)
- [ ] Access logs for webhook requests
- [ ] Request filtering for common webhook attacks
- [ ] Metrics exported to Prometheus (optional)

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Add nginx reverse proxy for n8n
2. `proxy/nginx.conf` - Nginx path-based routing configuration (new file)
3. `proxy/nginx-n8n.conf` - n8n-specific location blocks (new file)
4. `.env.example` - Add Let's Encrypt email for n8n domain
5. `docs/N8N_WEBHOOK_SECURITY.md` - Webhook security documentation (new file)

### Option 1: Nginx (Simpler for Single Service)

**Add to docker-compose.yml:**
```yaml
services:
  nginx:
    image: nginx:1.25-alpine@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: nginx-n8n-proxy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./proxy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./proxy/conf.d:/etc/nginx/conf.d:ro
      - ./ssl/letsencrypt:/etc/letsencrypt:ro
      - ./logs/nginx:/var/log/nginx
    networks:
      - frontend
    depends_on:
      - n8n
```

**Create proxy/nginx.conf:**
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;

    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=webhook_limit:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=1r/s;

    # Connection limiting
    limit_conn_zone $binary_remote_addr zone=addr:10m;
    limit_conn addr 10;

    # Include server configs
    include /etc/nginx/conf.d/*.conf;
}
```

**Create proxy/conf.d/n8n.conf:**
```nginx
upstream n8n_backend {
    server n8n:5678;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name n8n.yourdomain.com;

    # Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server for n8n
server {
    listen 443 ssl http2;
    server_name n8n.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # PUBLIC: Webhook endpoints - accessible from internet
    location /webhook/ {
        # Strict rate limiting for webhooks
        limit_req zone=webhook_limit burst=20 nodelay;

        # Webhook-specific logging
        access_log /var/log/nginx/n8n-webhooks.log main;

        # Proxy to n8n
        proxy_pass https://n8n_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for webhooks
        proxy_connect_timeout 10s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # Security: Block suspicious patterns
        if ($request_method !~ ^(POST|GET|PUT)$ ) {
            return 405;
        }
    }

    # PRIVATE: Admin UI and API - VPN/Local network only
    location / {
        # Only allow VPN and local network
        allow 10.13.13.0/24;     # WireGuard VPN subnet
        allow 192.168.0.0/16;    # Local network
        deny all;

        # Less strict rate limiting for admin access
        limit_req zone=general_limit burst=10 nodelay;

        # Proxy to n8n
        proxy_pass https://n8n_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for n8n UI)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Longer timeouts for admin UI
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Block access to sensitive paths
    location ~ /\. {
        deny all;
    }
}
```

**Setup Let's Encrypt:**
```bash
# Add certbot to docker-compose.yml
services:
  certbot:
    image: certbot/certbot:latest
    container_name: certbot
    volumes:
      - ./ssl/letsencrypt:/etc/letsencrypt
      - ./ssl/certbot-webroot:/var/www/certbot
    command: certonly --webroot --webroot-path=/var/www/certbot --email ${LETSENCRYPT_EMAIL} --agree-tos --no-eff-email -d n8n.yourdomain.com
```

### Option 2: Traefik (More Features, More Complex)

**docker-compose.proxy.yml:**
```yaml
services:
  traefik:
    image: traefik:v2.11@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    ports:
      - "80:80"
      - "443:443"
      - "${SERVER_IP}:8080:8080"  # Dashboard (local only)
    environment:
      - CF_API_EMAIL=${CLOUDFLARE_EMAIL}
      - CF_API_KEY=${CLOUDFLARE_API_KEY}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./proxy/traefik.yml:/traefik.yml:ro
      - ./proxy/dynamic-config.yml:/dynamic-config.yml:ro
      - ./proxy/acme.json:/acme.json
      - ./logs/traefik:/logs
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.${DOMAIN}`)"
      - "traefik.http.routers.dashboard.service=api@internal"
      - "traefik.http.routers.dashboard.middlewares=auth"
      - "traefik.http.middlewares.auth.basicauth.users=${TRAEFIK_DASHBOARD_AUTH}"
    networks:
      - frontend
      - monitoring

networks:
  frontend:
    external: true
    name: home-server-stack_frontend
  monitoring:
    external: true
    name: home-server-stack_monitoring
```

**proxy/traefik.yml:**
```yaml
# Traefik Static Configuration

api:
  dashboard: true
  insecure: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https

  websecure:
    address: ":443"
    http:
      tls:
        certResolver: letsencrypt
      middlewares:
        - security-headers@file
        - rate-limit@file

# Let's Encrypt configuration
certificatesResolvers:
  letsencrypt:
    acme:
      email: ${LETSENCRYPT_EMAIL}
      storage: /acme.json
      httpChallenge:
        entryPoint: web
      # For DNS challenge (better for wildcards):
      # dnsChallenge:
      #   provider: cloudflare
      #   delayBeforeCheck: 0

# Prometheus metrics
metrics:
  prometheus:
    buckets:
      - 0.1
      - 0.3
      - 1.0
      - 3.0
      - 5.0
    addEntryPointsLabels: true
    addServicesLabels: true

# Access logs
accessLog:
  filePath: "/logs/access.log"
  format: json
  fields:
    headers:
      defaultMode: keep

# Provider configuration
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: frontend
  file:
    filename: /dynamic-config.yml
    watch: true

# Global log level
log:
  level: INFO
  filePath: "/logs/traefik.log"
```

**proxy/dynamic-config.yml:**
```yaml
# Traefik Dynamic Configuration

http:
  middlewares:
    # Security headers
    security-headers:
      headers:
        frameDeny: true
        sslRedirect: true
        browserXssFilter: true
        contentTypeNosniff: true
        stsIncludeSubdomains: true
        stsPreload: true
        stsSeconds: 31536000
        customFrameOptionsValue: "SAMEORIGIN"
        customResponseHeaders:
          X-Robots-Tag: "none,noarchive,nosnippet,notranslate,noimageindex"
          server: ""
          X-Powered-By: ""

    # Rate limiting - general
    rate-limit:
      rateLimit:
        average: 100
        period: 1s
        burst: 50

    # Rate limiting - strict (for authentication endpoints)
    rate-limit-strict:
      rateLimit:
        average: 10
        period: 1m
        burst: 5

    # Rate limiting - API
    rate-limit-api:
      rateLimit:
        average: 200
        period: 1s
        burst: 100

    # IP whitelist (local network)
    local-network-only:
      ipWhiteList:
        sourceRange:
          - "192.168.0.0/16"
          - "172.16.0.0/12"
          - "10.0.0.0/8"
          - "127.0.0.1/32"

    # Compression
    compression:
      compress: {}

    # Circuit breaker
    circuit-breaker:
      circuitBreaker:
        expression: "NetworkErrorRatio() > 0.3 || ResponseCodeRatio(500, 600, 0, 600) > 0.3"

tls:
  options:
    default:
      minVersion: VersionTLS12
      cipherSuites:
        - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305
        - TLS_AES_128_GCM_SHA256
        - TLS_AES_256_GCM_SHA384
        - TLS_CHACHA20_POLY1305_SHA256
      curvePreferences:
        - CurveP521
        - CurveP384
      sniStrict: true
```

### Service Configuration with Traefik Labels

**Update docker-compose.yml services:**
```yaml
services:
  adguard:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.adguard.rule=Host(`adguard.${DOMAIN}`)"
      - "traefik.http.routers.adguard.entrypoints=websecure"
      - "traefik.http.services.adguard.loadbalancer.server.port=80"
      - "traefik.http.routers.adguard.middlewares=local-network-only@file"

  n8n:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
      - "traefik.http.services.n8n.loadbalancer.server.scheme=https"
      - "traefik.http.routers.n8n.middlewares=rate-limit-strict@file,security-headers@file"

  grafana:
    # ... existing configuration ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`grafana.${DOMAIN}`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"
      - "traefik.http.routers.grafana.middlewares=local-network-only@file"
```

### Environment Variables

Add to `.env.example`:
```bash
# Reverse Proxy Configuration
DOMAIN=your-domain.com
CLOUDFLARE_EMAIL=admin@example.com
CLOUDFLARE_API_KEY=your_cloudflare_api_key
TRAEFIK_DASHBOARD_AUTH=admin:$$apr1$$H6uskkkW$$IgXLP6ewTrSuBkTrqE8wj/
# Generate with: htpasswd -nb admin your_password
```

### Option 2: Nginx with ModSecurity (WAF)

**docker-compose.proxy.yml (Nginx variant):**
```yaml
services:
  nginx:
    image: nginx:1.25-alpine@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./proxy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./proxy/conf.d:/etc/nginx/conf.d:ro
      - ./ssl/letsencrypt:/etc/letsencrypt:ro
      - ./logs/nginx:/var/log/nginx
    networks:
      - frontend
      - monitoring
    depends_on:
      - modsecurity

  modsecurity:
    image: owasp/modsecurity-crs:nginx-alpine
    container_name: modsecurity
    restart: unless-stopped
    environment:
      - PARANOIA=1
      - ANOMALY_INBOUND=5
      - ANOMALY_OUTBOUND=4
    networks:
      - frontend
```

**proxy/nginx.conf:**
```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=strict:10m rate=5r/m;

# Connection limiting
limit_conn_zone $binary_remote_addr zone=addr:10m;

upstream n8n {
    server n8n:5678;
}

upstream grafana {
    server grafana:3000;
}

server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name n8n.yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate limiting
    limit_req zone=api burst=10 nodelay;
    limit_conn addr 10;

    location / {
        proxy_pass https://n8n;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Logging
    access_log /var/log/nginx/n8n-access.log;
    error_log /var/log/nginx/n8n-error.log;
}
```

### Testing Commands
```bash
# Create ACME storage file
touch proxy/acme.json
chmod 600 proxy/acme.json

# Generate dashboard auth
htpasswd -nb admin your_password

# Start proxy
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.proxy.yml up -d traefik

# Check Traefik dashboard
curl -u admin:password https://SERVER_IP:8080/dashboard/

# Test rate limiting
for i in {1..200}; do curl -s -o /dev/null -w "%{http_code}\n" https://n8n.yourdomain.com; done
# Should see 429 (Too Many Requests) after hitting limit

# Verify HTTPS redirect
curl -I http://n8n.yourdomain.com
# Should return 301 or 308 redirect to HTTPS

# Check SSL configuration
sslscan https://n8n.yourdomain.com
testssl.sh https://n8n.yourdomain.com

# View access logs
docker exec traefik tail -f /logs/access.log

# Test security headers
curl -I https://n8n.yourdomain.com
# Check for X-Frame-Options, HSTS, etc.

# Verify Prometheus metrics
curl http://SERVER_IP:8080/metrics
```

## Success Metrics
- All services accessible via reverse proxy
- HTTPS automatically configured with Let's Encrypt
- Rate limiting blocks excessive requests
- Security headers present on all responses
- Centralized access logs available
- Prometheus metrics exported

## Dependencies
- Domain name with DNS configured
- Ports 80/443 available
- Let's Encrypt compatible (or manual cert setup)
- Docker networks configured

## Risk Considerations
- **Single Point of Failure**: Proxy down = all services down
- **Complexity**: Additional layer to troubleshoot
- **Certificate Issues**: Let's Encrypt rate limits
- **Performance**: Added latency from proxying

## Rollback Plan
```bash
# Stop proxy and access services directly
docker compose -f docker-compose.proxy.yml down

# Access services on original ports
# n8n: https://SERVER_IP:5678
# grafana: http://SERVER_IP:3001
```

## Security Impact (VPN-First Model)
- **Before**: n8n fully exposed to internet, no path-based access control, potential abuse of admin UI
- **After**: Only webhook paths public, admin UI requires VPN, DDoS protection on webhooks, Let's Encrypt for valid certs
- **Risk Reduction**:
  - 85% reduction in n8n attack surface (only /webhook/* exposed)
  - Prevents unauthorized access to workflow editor
  - Protects against webhook DDoS attacks

## References
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [OWASP ModSecurity CRS](https://owasp.org/www-project-modsecurity-core-rule-set/)
- [Mozilla SSL Config](https://ssl-config.mozilla.org/)

## Follow-up Tasks
- Implement GeoIP blocking
- Add WAF (ModSecurity) rules
- Configure fail2ban integration
- Set up DDoS protection (Cloudflare)
- Implement API gateway patterns
