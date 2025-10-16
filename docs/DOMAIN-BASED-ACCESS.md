# Domain-Based Access Testing

This document describes how to test and verify domain-based access for services in the home server stack.

**Note:** This project now uses real domains with Let's Encrypt SSL certificates. Configure your domain in `.env` by setting `DOMAIN`, `ACME_EMAIL`, and `GANDIV5_API_KEY`. Throughout this document, replace references to `.home.local` with your actual domain (e.g., `example.com`).

## Overview

Domain-based access allows you to access services using memorable domain names (e.g., `glance.example.com`) instead of IP addresses and ports (e.g., `192.168.1.100:8282`). This is accomplished through:

1. **Traefik**: Reverse proxy that routes requests based on domain names with Let's Encrypt SSL
2. **Let's Encrypt**: Automatic SSL certificate generation using Gandi DNS-01 challenge
3. **Gandi DNS**: DNS provider for domain management and ACME challenge

## Configured Services

The following services are configured for domain-based access (replace `DOMAIN` with your configured domain):

| Service | Domain | Direct Access (IP:Port) | Notes |
|---------|--------|------------------------|-------|
| Glance Dashboard | `https://glance.DOMAIN` | N/A (Traefik only) | - |
| HortusFox | `https://hortusfox.DOMAIN` | N/A (Traefik only) | - |
| Grafana | `https://grafana.DOMAIN` | N/A (Traefik only) | - |
| n8n Workflow Automation | `https://n8n.DOMAIN` | N/A (Traefik only) | - |
| AdGuard Home | `https://adguard.DOMAIN` | `http://SERVER_IP:8888` | Emergency access |
| Ollama AI API | `https://ollama.DOMAIN` | `http://SERVER_IP:11434` | Direct API access |
| Habitica Habit Tracker | `https://habitica.DOMAIN` | `http://SERVER_IP:8080` | Legacy access |
| Prometheus Monitoring | `https://prometheus.DOMAIN` | `http://SERVER_IP:9090` | Metrics scraping |
| Alertmanager | `https://alerts.DOMAIN` | `http://SERVER_IP:9093` | Alert management |
| Traefik Dashboard | `https://traefik.DOMAIN` | N/A (domain-only) | - |

## Prerequisites

Before testing domain-based access, ensure:

1. **AdGuard DNS is configured**: Run `make adguard-setup` to configure DNS rewrites
2. **All services are running**: Run `make status` to verify
3. **Router DNS configuration**: Configure your router's DHCP settings to provide your server IP (e.g., `192.168.1.100`) as the primary DNS server. This automatically configures all devices on your network.

## Running Tests

### Automated Testing

Run the automated test suite to verify all domain-based access functionality:

```bash
make test-domain-access
```

This test script verifies:
- ✅ DNS resolution for `*.home.local` domains
- ✅ HTTP to HTTPS redirect functionality
- ✅ HTTPS endpoint accessibility
- ✅ Traefik routing configuration
- ✅ Service availability

### Manual Testing

#### 1. Test DNS Resolution

From the server:
```bash
# Test local DNS resolution
dig @192.168.1.100 glance.home.local +short

# Expected output: 192.168.1.100
```

From a client device (configured to use AdGuard DNS):
```bash
# Should resolve to server IP
dig glance.home.local +short

# Or use nslookup
nslookup glance.home.local
```

#### 2. Test HTTP Redirect

The HTTP endpoint should redirect to HTTPS:
```bash
# Test redirect (should return 301/302/308)
curl -I -H "Host: glance.home.local" http://192.168.1.100

# Expected: HTTP/1.1 301 Moved Permanently
# Location: https://glance.home.local/
```

#### 3. Test HTTPS Access

Access via HTTPS (allow self-signed cert):
```bash
# Test HTTPS endpoint (should return 200)
curl -I -k https://glance.home.local

# Expected: HTTP/2 200
```

#### 4. Test in Browser

1. Open browser on a client device configured to use AdGuard DNS
2. Navigate to `https://glance.home.local`
3. Accept the self-signed certificate warning
4. Verify the service loads correctly

### Expected Browser Behavior

When accessing `https://glance.home.local` in a browser:

1. **Certificate Warning**: You'll see a warning about an untrusted certificate
   - This is expected with self-signed certificates
   - Click "Advanced" and "Proceed to site" (wording varies by browser)
   - To avoid warnings, install the server certificate in your browser's trusted store

2. **Service Loads**: After accepting the certificate, the service should load normally

3. **Future Visits**: Most browsers will remember your exception for the certificate

## Troubleshooting

### DNS Not Resolving

**Symptom**: `dig @192.168.1.100 glance.home.local` returns no results

**Solutions**:
1. Verify AdGuard is running: `docker ps | grep adguard`
2. Check AdGuard logs: `docker logs adguard-home`
3. Re-run DNS setup: `make adguard-setup`
4. Verify DNS service: `nc -zv 192.168.1.100 53`

### HTTP Redirect Not Working

**Symptom**: HTTP requests don't redirect to HTTPS

**Solutions**:
1. Verify Traefik is running: `docker ps | grep traefik`
2. Check Traefik logs: `docker logs traefik`
3. Verify Traefik configuration: `docker inspect traefik`
4. Check for port conflicts: `lsof -i :80 -i :443`

### HTTPS Not Accessible

**Symptom**: HTTPS requests fail or timeout

**Solutions**:
1. Check Traefik is listening on 443: `nc -zv 192.168.1.100 443`
2. Verify SSL certificates exist: `ls -la ssl/`
3. Check Traefik logs for routing errors: `docker logs traefik | grep error`
4. Verify service labels: `docker inspect glance | grep traefik`

### Service Not Routing

**Symptom**: Domain resolves but shows Traefik 404

**Solutions**:
1. Verify service has Traefik labels: `docker inspect <service> | grep traefik.enable`
2. Check service is on correct network: `docker inspect <service> | grep NetworkMode`
3. Verify Traefik can see the service: `docker logs traefik | grep <service>`
4. Restart Traefik: `docker restart traefik`

### Client Can't Resolve Domains

**Symptom**: Browser says "Server not found" or similar

**Solutions**:
1. Verify router DHCP is configured to use server IP as DNS
2. Restart client device to get fresh DHCP lease with new DNS settings
3. Test DNS from client: `dig glance.home.local` (should return server IP)
4. Flush DNS cache:
   - macOS: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`
   - Windows: `ipconfig /flushdns`
   - Linux: `sudo systemd-resolve --flush-caches`
5. Try disconnecting and reconnecting to WiFi network

## How It Works

### Request Flow

1. **Browser DNS Lookup**: Client requests IP for `glance.home.local`
2. **AdGuard DNS Response**: Returns server IP (`192.168.1.100`)
3. **HTTP Request**: Browser sends HTTP request to `http://192.168.1.100` with `Host: glance.home.local`
4. **Traefik Redirect**: Traefik intercepts, returns 301 redirect to HTTPS
5. **HTTPS Request**: Browser sends HTTPS request to `https://192.168.1.100` with `Host: glance.home.local`
6. **Traefik Routing**: Traefik matches the Host header and routes to the correct container
7. **Service Response**: Container responds, Traefik forwards back to browser

### Architecture Components

```
┌─────────────┐
│   Browser   │
│  (Client)   │
└──────┬──────┘
       │ 1. DNS Query: glance.home.local?
       │
       ▼
┌─────────────┐
│   AdGuard   │
│  (DNS :53)  │
└──────┬──────┘
       │ 2. DNS Response: 192.168.1.100
       │
       ▼
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ 3. HTTP: http://192.168.1.100 (Host: glance.home.local)
       │
       ▼
┌─────────────┐
│   Traefik   │
│ (:80, :443) │
└──────┬──────┘
       │ 4. 301 Redirect → https://glance.home.local
       │
       ▼
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ 5. HTTPS: https://192.168.1.100 (Host: glance.home.local)
       │
       ▼
┌─────────────┐
│   Traefik   │
│ (:80, :443) │
└──────┬──────┘
       │ 6. Route based on Host header
       │
       ▼
┌─────────────┐
│   Glance    │
│  (:8080)    │
└─────────────┘
       │ 7. Service response
       │
       ▼
    Browser
```

## SSL Certificate Management

### Current Setup (Self-Signed)

The current setup uses self-signed SSL certificates generated during initial setup:

```bash
# Regenerate SSL certificates
make regenerate-ssl

# Or with custom domain
make regenerate-ssl DOMAIN=your-domain.com
```

### Production Setup (Let's Encrypt)

For production use with valid SSL certificates:

1. **Domain Name**: Obtain a real domain name (e.g., `homeserver.example.com`)
2. **DNS Configuration**: Point domain to your public IP
3. **Port Forwarding**: Forward ports 80 and 443 to your server
4. **Let's Encrypt**: Configure Traefik with Let's Encrypt ACME

See Traefik's [Let's Encrypt documentation](https://doc.traefik.io/traefik/https/acme/) for details.

## Security Considerations

### SSL Certificates

The project uses Let's Encrypt for valid SSL certificates:

- Automatic certificate renewal via Traefik
- DNS-01 challenge using Gandi API (supports wildcard certs)
- No browser warnings for trusted certificates

### VPN Access

For remote access, use WireGuard VPN:

1. Connect to VPN
2. VPN automatically routes home network traffic
3. Access services via your configured domain

See `docs/WIREGUARD.md` for VPN setup.

### Exposed Services Warning

⚠️ **Do NOT expose** these services directly to the internet without:
- Proper authentication
- Rate limiting
- Valid SSL certificates
- Security hardening
- Firewall rules

## Testing Checklist

Before marking domain-based access as working:

- [ ] DNS rewrites configured in AdGuard
- [ ] All services have Traefik labels in docker-compose
- [ ] Traefik is running and accessible
- [ ] Router DHCP configured to use server IP as DNS
- [ ] DNS resolution works: `dig @SERVER_IP glance.home.local`
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS endpoints accessible
- [ ] Browser can access all services via domain names
- [ ] Certificate warnings appear (expected with self-signed)
- [ ] Services load correctly after accepting certificate

## References

- [Traefik Documentation](https://doc.traefik.io/)
- [AdGuard Home DNS Rewrites](https://adguard.com/kb/general/dns-providers/)
- [Docker Networking](https://docs.docker.com/network/)

## Related Documentation

- `docs/ADGUARD.md` - AdGuard Home setup and configuration
- `docs/TRAEFIK.md` - Traefik reverse proxy configuration (if exists)
- `docs/SSL.md` - SSL certificate management (if exists)
- `README.md` - Main project documentation
