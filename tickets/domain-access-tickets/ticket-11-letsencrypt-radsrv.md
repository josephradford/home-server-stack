# Ticket 11: Configure Let's Encrypt SSL with Gandi for example.com

**Priority:** High
**Estimated Time:** 2 hours
**Category:** Security & Infrastructure
**Status:** ⬜ Pending
**Dependencies:** Tickets 01-08 complete, working domain-based access

## Overview

Configure Let's Encrypt SSL certificates using DNS-01 challenge with your registered domain `example.com` from Gandi. This provides trusted certificates for all services while maintaining a secure architecture where only webhook endpoints are publicly accessible.

## Problem Statement

**Current Situation:**
- Services use self-signed certificates from Traefik
- Browser certificate warnings on every visit
- n8n exposed directly on port 5678 (bypassing Traefik)
- No separation between public webhooks and private admin interfaces

**Goal:**
- Trusted SSL certificates for all services
- Secure architecture with minimal public exposure
- Webhook functionality maintained for n8n and future services
- VPN-only access for administrative interfaces

## Architecture Overview

```
Public Internet Access:
├── webhook.example.com → Traefik → n8n (webhook paths only)
└── [YOUR_IP]:51820 → WireGuard VPN

VPN/Local Access Only:
├── n8n.home.example.com → Full n8n interface
├── hortusfox.home.example.com → HortusFox
├── grafana.home.example.com → Grafana
└── *.home.example.com → All other services
```

## Prerequisites

### ✅ Already Completed
- Domain registered: `example.com` (from Gandi)
- WireGuard VPN configured and working
- Traefik proxy installed

### 📋 Still Needed
- Gandi API key (Production v5)
- DNS configuration at Gandi
- Migration of n8n from port 5678 to Traefik

## Implementation Steps

### Step 1: Generate Gandi API Key

1. **Log into Gandi account** at [gandi.net](https://gandi.net)
2. **Navigate to**: Account Settings → Security
3. **Find**: "Production API Key" section
4. **Generate key**:
   - Click "Generate API key" (or "Regenerate" if exists)
   - **Copy immediately** - won't be shown again
   - Store securely in password manager

### Step 2: Configure DNS at Gandi

Create the following DNS records in Gandi's dashboard:

```
# For webhook access (points to your real IP)
Type: A
Name: webhook
Value: [YOUR_REAL_PUBLIC_IP]
TTL: 300

# For SSL certificates (dummy IP - never actually accessed)
Type: A  
Name: *.home
Value: 127.0.0.1
TTL: 300
```

**Verify propagation:**
```bash
# Should return your real IP
dig webhook.example.com

# Should return 127.0.0.1
dig test.home.example.com
```

### Step 3: Configure Local DNS (AdGuard)

Add DNS rewrites in AdGuard Home:

```
# Local access to all services
*.home.example.com → 192.168.1.101

# Also keep existing for backward compatibility
*.home.local → 192.168.1.101
```

### Step 4: Update Environment Variables

**File:** `.env`

```bash
# Domain Configuration
HOME_DOMAIN=home.example.com
PUBLIC_DOMAIN=example.com

# Let's Encrypt Configuration
ACME_EMAIL=your-email@example.com

# Gandi API Key (Production API v5)
GANDIV5_API_KEY=your_gandi_api_key_here

# Network Configuration
SERVER_IP=192.168.1.101
```

**File:** `.env.example`

```bash
# Domain Configuration
HOME_DOMAIN=home.example.com    # Internal services domain
PUBLIC_DOMAIN=example.com       # Public webhook domain

# Let's Encrypt SSL Certificates
ACME_EMAIL=admin@example.com

# Gandi API Key (from Account Settings → Security)
GANDIV5_API_KEY=your_gandi_production_api_key

# Network Configuration
SERVER_IP=192.168.1.101
```

### Step 5: Update Traefik Configuration

**File:** `docker-compose.yml`

```yaml
traefik:
  image: traefik:v3.0
  container_name: traefik
  restart: unless-stopped
  command:
    # API and Dashboard
    - "--api.dashboard=true"
    - "--api.insecure=false"

    # Docker provider
    - "--providers.docker=true"
    - "--providers.docker.exposedbydefault=false"

    # Entrypoints
    - "--entrypoints.web.address=:80"
    - "--entrypoints.websecure.address=:443"

    # HTTP to HTTPS redirect
    - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
    - "--entrypoints.web.http.redirections.entrypoint.scheme=https"

    # TLS
    - "--entrypoints.websecure.http.tls=true"

    # Let's Encrypt Certificate Resolver with Gandi
    - "--certificatesresolvers.letsencrypt.acme.dnschallenge=true"
    - "--certificatesresolvers.letsencrypt.acme.dnschallenge.provider=gandiv5"
    - "--certificatesresolvers.letsencrypt.acme.dnschallenge.resolvers=1.1.1.1:53,8.8.8.8:53"
    - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
    - "--certificatesresolvers.letsencrypt.acme.storage=/certs/acme.json"
    # FOR TESTING ONLY - Uncomment to use staging:
    # - "--certificatesresolvers.letsencrypt.acme.caserver=https://acme-staging-v02.api.letsencrypt.org/directory"

    # Wildcard Certificate Configuration
    - "--certificatesresolvers.letsencrypt.acme.dnschallenge.delaybeforecheck=30"
    
    # Logging
    - "--log.level=INFO"
    - "--accesslog=true"
    - "--accesslog.filepath=/var/log/traefik/access.log"

  ports:
    - "${SERVER_IP}:80:80"
    - "${SERVER_IP}:443:443"
    # Remove port 5678 - n8n will go through Traefik

  environment:
    # Gandi API credentials
    - GANDIV5_API_KEY=${GANDIV5_API_KEY}

  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - ./data/traefik/certs:/certs
    - ./data/traefik/logs:/var/log/traefik

  networks:
    - homeserver

  labels:
    # Enable Traefik
    - "traefik.enable=true"

    # Dashboard (VPN/local only)
    - "traefik.http.routers.dashboard.rule=Host(`traefik.${HOME_DOMAIN}`)"
    - "traefik.http.routers.dashboard.entrypoints=websecure"
    - "traefik.http.routers.dashboard.tls=true"
    - "traefik.http.routers.dashboard.tls.certresolver=letsencrypt"
    - "traefik.http.routers.dashboard.service=api@internal"
    
    # Request wildcard certificate for all services
    - "traefik.http.routers.dashboard.tls.domains[0].main=${HOME_DOMAIN}"
    - "traefik.http.routers.dashboard.tls.domains[0].sans=*.${HOME_DOMAIN}"
    - "traefik.http.routers.dashboard.tls.domains[1].main=${PUBLIC_DOMAIN}"
    - "traefik.http.routers.dashboard.tls.domains[1].sans=*.${PUBLIC_DOMAIN}"

    # Dashboard auth
    - "traefik.http.middlewares.dashboard-auth.basicauth.users=admin:$$2y$$10$$..."
    - "traefik.http.routers.dashboard.middlewares=dashboard-auth"

  healthcheck:
    test: ["CMD", "traefik", "healthcheck", "--ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Step 6: Update Service Labels for SSL

For each internal service, add the cert resolver. Example:

**HortusFox:**
```yaml
hortusfox:
  # ... existing config ...
  labels:
    - "traefik.enable=true"
    
    # Router for HTTPS
    - "traefik.http.routers.hortusfox.rule=Host(`hortusfox.${HOME_DOMAIN}`)"
    - "traefik.http.routers.hortusfox.entrypoints=websecure"
    - "traefik.http.routers.hortusfox.tls=true"
    - "traefik.http.routers.hortusfox.tls.certresolver=letsencrypt"  # Add this
    
    # Service
    - "traefik.http.services.hortusfox.loadbalancer.server.port=80"
```

Apply same pattern to: Grafana, AdGuard, Ollama, Habitica, Prometheus, Alertmanager, Glance

**Note:** n8n configuration is special - see Ticket 13 for webhook setup.

### Step 7: Create Certificate Storage

```bash
# On the server
mkdir -p data/traefik/certs
touch data/traefik/certs/acme.json
chmod 600 data/traefik/certs/acme.json
```

### Step 8: Test with Staging Certificates

1. **Enable staging** (uncomment the staging line in Traefik command)

2. **Deploy:**
```bash
docker compose down
docker compose up -d traefik
```

3. **Monitor logs:**
```bash
docker logs traefik -f | grep -i acme
```

4. **Look for:**
- "Starting DNS-01 challenge"
- "Validations succeeded"
- "Server responded with a certificate"

5. **Test access:**
```bash
curl -k https://traefik.home.example.com
# Should work but show staging certificate warning
```

### Step 9: Deploy Production Certificates

1. **Disable staging** (comment out the staging line)

2. **Clear staging certs:**
```bash
rm data/traefik/certs/acme.json
touch data/traefik/certs/acme.json
chmod 600 data/traefik/certs/acme.json
```

3. **Deploy all services:**
```bash
docker compose up -d
```

4. **Verify certificates:**
   - Visit `https://hortusfox.home.example.com` (through VPN or locally)
   - Should show trusted Let's Encrypt certificate
   - No browser warnings

## Testing Checklist

### DNS Configuration
- [ ] `webhook.example.com` resolves to your real IP
- [ ] `*.home.example.com` resolves to 127.0.0.1 (public DNS)
- [ ] `*.home.example.com` resolves to 192.168.1.101 (AdGuard)

### Certificate Generation
- [ ] Staging certificates generate successfully
- [ ] Production certificates generate successfully
- [ ] Wildcard certificates cover all subdomains

### Service Access (Local/VPN)
- [ ] All services accessible via `https://*.home.example.com`
- [ ] No certificate warnings
- [ ] Favicons display and save properly

### Public Access
- [ ] `webhook.example.com` not yet configured (see Ticket 13)
- [ ] No services accessible from internet except WireGuard

## Troubleshooting

### "Invalid API Key"
```bash
# Test Gandi API key
curl -H "Authorization: Apikey YOUR_KEY" \
     https://api.gandi.net/v5/livedns/domains

# Should list your domains
```

### "DNS Challenge Failed"
- Check Gandi API key is Production v5 (not XML-RPC)
- Verify DNS propagation: `dig TXT _acme-challenge.home.example.com`
- Check Traefik can reach Gandi: `docker logs traefik | grep gandi`

### "Too Many Certificates"
- Let's Encrypt rate limit: 50/week per domain
- Wait 7 days or use staging for testing
- Use wildcard to minimize certificate count

## Security Notes

- ✅ Public DNS for `*.home.example.com` points to 127.0.0.1 (not your real IP)
- ✅ Only `webhook.example.com` points to real IP (for future webhook use)
- ✅ All admin interfaces require VPN or local access
- ✅ Certificates auto-renew every 60-90 days

## Success Criteria

- ✅ All services have trusted SSL certificates
- ✅ Wildcard certificates working for both domains
- ✅ No services exposed to internet (except future webhooks)
- ✅ Certificate auto-renewal configured
- ✅ Clean separation between public and private domains

## Next Steps

- **Ticket 12:** Implement Security Hardening (firewall rules, fail2ban, monitoring)
- **Ticket 13:** Configure n8n Webhook Architecture (migrate from port 5678)

---

**Created:** 2025-01-15
**Estimated Cost:** ~$15-20/year (domain registration only)