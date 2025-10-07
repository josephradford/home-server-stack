# Configure Centralized Authentication and MFA (Optional)

## Priority: 4 (Low - Optional)
## Estimated Time: 6-8 hours
## Phase: Month 3+ - Nice-to-Have Enhancement

> **🔒 VPN-First Strategy Note:**
> In the VPN-first model, **WireGuard provides the primary authentication layer**. This ticket is now **optional** and provides defense-in-depth by adding a second authentication layer within the VPN. Only implement this if you want SSO convenience or additional security after VPN authentication.

## Description
**OPTIONAL:** Implement centralized authentication with Multi-Factor Authentication (MFA) using Authelia or OAuth2 Proxy for services accessed via VPN. This provides SSO convenience and an additional authentication layer, but is not critical since VPN already authenticates users.

## Acceptance Criteria (Optional - Only if Implementing)
- [ ] Authelia or OAuth2 Proxy deployed for VPN-accessible services
- [ ] MFA enabled (TOTP or WebAuthn) as second factor after VPN
- [ ] SSO (Single Sign-On) for internal services (Grafana, n8n UI, etc.)
- [ ] Failed login attempts tracked and alerted
- [ ] Session management configured
- [ ] Account lockout policies implemented

**Note:** VPN authentication is the primary security boundary. This adds SSO convenience and defense-in-depth.

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.auth.yml` - Authentication services (new file)
2. `auth/authelia/configuration.yml` - Authelia config (new file)
3. `auth/authelia/users_database.yml` - User database (new file)
4. `proxy/dynamic-config.yml` - Update with auth middleware
5. `.env.example` - Add authentication variables

### Option 1: Authelia (Recommended - Full Featured)

**docker-compose.auth.yml:**
```yaml
services:
  authelia:
    image: authelia/authelia:4.37@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: authelia
    restart: unless-stopped
    environment:
      - TZ=${TIMEZONE}
      - AUTHELIA_JWT_SECRET_FILE=/secrets/JWT_SECRET
      - AUTHELIA_SESSION_SECRET_FILE=/secrets/SESSION_SECRET
      - AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE=/secrets/STORAGE_ENCRYPTION_KEY
    volumes:
      - ./auth/authelia:/config
      - ./auth/secrets:/secrets:ro
    networks:
      - frontend
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.authelia.rule=Host(`auth.${DOMAIN}`)"
      - "traefik.http.routers.authelia.entrypoints=websecure"
      - "traefik.http.services.authelia.loadbalancer.server.port=9091"
      - "traefik.http.middlewares.authelia.forwardauth.address=http://authelia:9091/api/verify?rd=https://auth.${DOMAIN}"
      - "traefik.http.middlewares.authelia.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.authelia.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email"

  redis:
    image: redis:7-alpine@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: authelia-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - frontend

volumes:
  redis_data:

networks:
  frontend:
    external: true
    name: home-server-stack_frontend
```

**auth/authelia/configuration.yml:**
```yaml
---
theme: dark
default_redirection_url: https://home.${DOMAIN}

server:
  host: 0.0.0.0
  port: 9091
  path: ""
  read_buffer_size: 4096
  write_buffer_size: 4096
  enable_pprof: false
  enable_expvars: false

log:
  level: info
  format: text

totp:
  disable: false
  issuer: HomeServer
  algorithm: sha1
  digits: 6
  period: 30
  skew: 1
  secret_size: 32

webauthn:
  disable: false
  display_name: HomeServer
  attestation_conveyance_preference: indirect
  user_verification: preferred
  timeout: 60s

ntp:
  address: "time.cloudflare.com:123"
  version: 4
  max_desync: 3s
  disable_startup_check: false

authentication_backend:
  password_reset:
    disable: false
  refresh_interval: 5m
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2id
      iterations: 3
      salt_length: 16
      parallelism: 4
      memory: 64

access_control:
  default_policy: deny
  rules:
    # Authelia portal
    - domain: auth.${DOMAIN}
      policy: bypass

    # Admin services - require 2FA
    - domain:
        - adguard.${DOMAIN}
        - grafana.${DOMAIN}
        - traefik.${DOMAIN}
      policy: two_factor
      subject:
        - ["group:admins"]

    # n8n - require authentication but allow API access
    - domain: n8n.${DOMAIN}
      policy: two_factor
      resources:
        - "^/webhook/.*$"
      policy: bypass  # Allow webhooks without auth

    # Monitoring - local network only with 1FA
    - domain:
        - prometheus.${DOMAIN}
        - alertmanager.${DOMAIN}
      policy: one_factor
      networks:
        - 192.168.0.0/16

session:
  name: authelia_session
  domain: ${DOMAIN}
  same_site: lax
  secret: file:///secrets/SESSION_SECRET
  expiration: 1h
  inactivity: 15m
  remember_me_duration: 1M

  redis:
    host: redis
    port: 6379
    password: ${REDIS_PASSWORD}
    database_index: 0
    maximum_active_connections: 8
    minimum_idle_connections: 0

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  encryption_key: file:///secrets/STORAGE_ENCRYPTION_KEY
  local:
    path: /config/db.sqlite3

notifier:
  disable_startup_check: false
  filesystem:
    filename: /config/notification.txt
  # Alternative: SMTP notifications
  # smtp:
  #   username: ${SMTP_USERNAME}
  #   password: ${SMTP_PASSWORD}
  #   host: smtp.gmail.com
  #   port: 587
  #   sender: authelia@${DOMAIN}
```

**auth/authelia/users_database.yml:**
```yaml
---
users:
  admin:
    displayname: "Administrator"
    password: "$argon2id$v=19$m=65536,t=3,p=4$REPLACE_WITH_HASHED_PASSWORD"
    email: admin@${DOMAIN}
    groups:
      - admins
      - dev

  user:
    displayname: "Regular User"
    password: "$argon2id$v=19$m=65536,t=3,p=4$REPLACE_WITH_HASHED_PASSWORD"
    email: user@${DOMAIN}
    groups:
      - users
```

### Generate Secrets

**scripts/generate-auth-secrets.sh:**
```bash
#!/bin/bash
# Generate Authelia secrets

set -e

mkdir -p auth/secrets

echo "Generating Authelia secrets..."

# Generate JWT secret (32 bytes)
tr -cd '[:alnum:]' < /dev/urandom | fold -w64 | head -n1 > auth/secrets/JWT_SECRET

# Generate session secret (32 bytes)
tr -cd '[:alnum:]' < /dev/urandom | fold -w64 | head -n1 > auth/secrets/SESSION_SECRET

# Generate storage encryption key (64 bytes)
tr -cd '[:alnum:]' < /dev/urandom | fold -w128 | head -n1 > auth/secrets/STORAGE_ENCRYPTION_KEY

# Set proper permissions
chmod 600 auth/secrets/*

echo "✅ Secrets generated in auth/secrets/"
echo ""
echo "Generate user passwords with:"
echo "docker run --rm authelia/authelia:latest authelia hash-password 'your-password'"
```

### Update Traefik for Protected Services

**Update service labels in docker-compose.yml:**
```yaml
services:
  grafana:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`grafana.${DOMAIN}`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.middlewares=authelia@docker"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"

  n8n:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.middlewares=authelia@docker"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
```

### Option 2: OAuth2 Proxy with Google/GitHub

**docker-compose.auth.yml (OAuth2 variant):**
```yaml
services:
  oauth2-proxy:
    image: quay.io/oauth2-proxy/oauth2-proxy:v7.5.1@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: oauth2-proxy
    restart: unless-stopped
    command:
      - --http-address=0.0.0.0:4180
      - --provider=github
      - --client-id=${OAUTH_CLIENT_ID}
      - --client-secret=${OAUTH_CLIENT_SECRET}
      - --cookie-secret=${OAUTH_COOKIE_SECRET}
      - --email-domain=*
      - --upstream=static://202
      - --cookie-secure=true
      - --cookie-domain=.${DOMAIN}
      - --whitelist-domain=.${DOMAIN}
      - --redirect-url=https://auth.${DOMAIN}/oauth2/callback
      - --set-xauthrequest=true
    networks:
      - frontend
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.oauth.rule=Host(`auth.${DOMAIN}`) || PathPrefix(`/oauth2`)"
      - "traefik.http.services.oauth.loadbalancer.server.port=4180"
```

### Monitoring Failed Logins

**Update monitoring/prometheus/alert_rules.yml:**
```yaml
groups:
  - name: authentication_alerts
    rules:
      - alert: HighFailedLoginRate
        expr: rate(authelia_authentication_failed_total[5m]) > 5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High failed login rate detected"
          description: "More than 5 failed logins per minute detected. Possible brute force attack."

      - alert: AccountLocked
        expr: authelia_regulation_banned_users_total > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "User account locked due to failed attempts"
          description: "{{ $value }} user(s) have been temporarily banned."
```

### Testing Commands
```bash
# Generate secrets
chmod +x scripts/generate-auth-secrets.sh
./scripts/generate-auth-secrets.sh

# Hash password for user database
docker run --rm authelia/authelia:latest authelia crypto hash generate argon2 --password 'YourStrongPassword123!'

# Start authentication stack
docker compose -f docker-compose.yml -f docker-compose.proxy.yml -f docker-compose.auth.yml up -d

# Test authentication portal
curl https://auth.yourdomain.com

# Test protected endpoint (should redirect to auth)
curl -L https://grafana.yourdomain.com

# Check Authelia logs
docker logs authelia

# Test TOTP generation
# 1. Access https://auth.yourdomain.com
# 2. Login with credentials
# 3. Scan QR code with authenticator app
# 4. Enter TOTP code

# Verify session cookie
curl -v -c cookies.txt https://grafana.yourdomain.com
# Should set authelia_session cookie

# Test API access (should bypass auth for webhooks)
curl -X POST https://n8n.yourdomain.com/webhook/test
```

## Success Metrics
- Authelia portal accessible and functional
- MFA enrollment working (TOTP/WebAuthn)
- All admin services require 2FA
- Failed login attempts logged and alerted
- Session timeout working correctly
- Account lockout after 3 failed attempts

## Dependencies
- Traefik reverse proxy deployed
- Domain name configured
- Redis for session storage
- Email server for notifications (optional)

## Risk Considerations
- **Lockout Risk**: Misconfiguration could lock out all users
- **Complexity**: Additional authentication layer to manage
- **Single Point of Failure**: Authelia down = all services inaccessible
- **MFA Device Loss**: Recovery process needed

## Rollback Plan
```bash
# Remove authentication middleware
# Edit Traefik labels, remove authelia middleware
docker compose up -d

# Stop Authelia
docker compose -f docker-compose.auth.yml down

# Access services directly if needed
# Update /etc/hosts to bypass Traefik temporarily
```

## Security Impact (VPN-First Model - Optional)
- **Before**: VPN authentication only, individual service logins
- **After**: VPN + centralized SSO + optional MFA, improved user experience
- **Risk Reduction**:
  - Minimal additional security (VPN already provides strong auth)
  - Primary benefit: SSO convenience, not security
  - Defense-in-depth: 20% additional protection if VPN is compromised
  - **Recommendation**: Skip unless you need SSO convenience

## References
- [Authelia Documentation](https://www.authelia.com/)
- [OAuth2 Proxy](https://oauth2-proxy.github.io/oauth2-proxy/)
- [WebAuthn Guide](https://webauthn.guide/)

## Follow-up Tasks
- Configure SMTP for email notifications
- Implement password reset workflow
- Add hardware key support (YubiKey)
- Set up OAuth/OIDC providers
- Create user management procedures
