# Ticket 13: Configure n8n Webhook Architecture

**Priority:** High
**Estimated Time:** 3 hours (includes migration and testing)
**Category:** Security & Architecture
**Status:** ⬜ Pending
**Dependencies:** Tickets 11 and 12 complete

## Overview

Migrate n8n from direct port exposure (5678) to Traefik-managed routing with strict separation between public webhook endpoints and private admin interface. This enables secure webhook reception while keeping administrative access VPN-only.

## Current vs Target Architecture

### Current (Insecure)
```
Internet → Router → Port 5678 → n8n (FULL ACCESS)
                                   ├── /webhook/* (needed)
                                   ├── /rest/* (OAuth, needed)
                                   └── /* (admin UI, EXPOSED!)
```

### Target (Secure)
```
Internet → Router → Port 443 → Traefik
                                 ├── webhook.example.com/webhook/* → n8n (✅)
                                 ├── webhook.example.com/rest/oauth2-credential/* → n8n (✅)
                                 └── webhook.example.com/* → 404 (❌ blocked)

VPN/Local → n8n.home.example.com → n8n (FULL ACCESS ✅)
```

## Pre-Migration Checklist

### Before You Start
- [ ] Backup n8n data: `cp -r data/n8n data/n8n.backup`
- [ ] Document current webhook URLs in use
- [ ] Note OAuth redirect URIs configured in external services
- [ ] Have VPN access ready for testing
- [ ] Schedule maintenance window (15-30 minutes)

## Implementation Steps

### Step 1: Update n8n Configuration

**File:** `docker-compose.yml`

```yaml
n8n:
  image: n8nio/n8n:latest
  container_name: n8n
  restart: unless-stopped
  environment:
    - N8N_HOST=n8n.home.example.com
    - N8N_PORT=5678
    - N8N_PROTOCOL=https
    - WEBHOOK_URL=https://webhook.example.com
    - N8N_EDITOR_BASE_URL=https://n8n.home.example.com
    - VUE_APP_URL_BASE_API=https://n8n.home.example.com
    - N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
    - N8N_BASIC_AUTH_ACTIVE=true
    - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER}
    - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD}
    - GENERIC_TIMEZONE=${TZ}
    - TZ=${TZ}
  volumes:
    - ./data/n8n:/home/node/.n8n
  networks:
    - homeserver
  # REMOVE the ports section - no direct exposure
  # ports:
  #   - "${SERVER_IP}:5678:5678"  # DELETE THIS
  labels:
    - "traefik.enable=true"
    
    # PUBLIC: Webhook endpoint (internet accessible)
    - "traefik.http.routers.n8n-webhook.rule=Host(`webhook.${PUBLIC_DOMAIN}`) && (PathPrefix(`/webhook`) || PathPrefix(`/rest/oauth2-credential/callback`))"
    - "traefik.http.routers.n8n-webhook.entrypoints=websecure"
    - "traefik.http.routers.n8n-webhook.tls=true"
    - "traefik.http.routers.n8n-webhook.tls.certresolver=letsencrypt"
    - "traefik.http.routers.n8n-webhook.middlewares=webhook-secure"
    - "traefik.http.routers.n8n-webhook.priority=100"
    
    # PRIVATE: Admin interface (VPN/local only)
    - "traefik.http.routers.n8n-admin.rule=Host(`n8n.${HOME_DOMAIN}`)"
    - "traefik.http.routers.n8n-admin.entrypoints=websecure"
    - "traefik.http.routers.n8n-admin.tls=true"
    - "traefik.http.routers.n8n-admin.tls.certresolver=letsencrypt"
    - "traefik.http.routers.n8n-admin.middlewares=admin-secure"
    - "traefik.http.routers.n8n-admin.priority=90"
    
    # Service definition
    - "traefik.http.services.n8n.loadbalancer.server.port=5678"
    
    # Health check
    - "traefik.http.services.n8n.loadbalancer.healthcheck.path=/healthz"
    - "traefik.http.services.n8n.loadbalancer.healthcheck.interval=30s"