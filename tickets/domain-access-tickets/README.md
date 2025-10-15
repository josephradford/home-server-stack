# Domain-Based Access Implementation

## Overview

This directory contains implementation tickets for migrating the home server stack from IP:port-based access (e.g., `192.168.1.100:8080`) to clean domain-based access (e.g., `https://habitica.home.local`).

## Goals

1. **User-Friendly Access:** Replace IP:port combinations with memorable domain names
2. **Centralized SSL/TLS:** Use Traefik for automatic HTTPS on all services
3. **Automatic Service Discovery:** Leverage Docker labels for easy service addition
4. **Professional Setup:** Clean URLs that look and feel more polished
5. **Backward Compatibility:** Maintain IP:port access during transition

## Architecture

### Components

1. **Traefik** - Reverse proxy handling routing and SSL/TLS termination
2. **AdGuard Home** - DNS server resolving `*.home.local` to SERVER_IP
3. **Docker Labels** - Service discovery and routing configuration
4. **Self-Signed Certs** - Automatic SSL certificates for local network use

### Domain Naming Convention

All services use the `.home.local` TLD with descriptive names:

- `traefik.home.local` - Traefik dashboard
- `adguard.home.local` - AdGuard Home admin interface
- `n8n.home.local` - n8n workflow automation
- `glance.home.local` - Glance dashboard
- `hortusfox.home.local` - HortusFox plant management
- `habitica.home.local` - Habitica habit tracker
- `bookwyrm.home.local` - Bookwyrm book tracking
- `ollama.home.local` - Ollama API
- `grafana.home.local` - Grafana monitoring
- `prometheus.home.local` - Prometheus metrics
- `alerts.home.local` - Alertmanager

## Implementation Tickets

### Phase 1: Foundation (Week 1)

| # | Ticket | Priority | Time | Status |
|---|--------|----------|------|--------|
| 01 | [Traefik Deployment](01-traefik-deployment.md) | Critical | 2-3h | ⬜ Pending |
| 02 | [AdGuard Port Migration](02-adguard-port-migration.md) | Critical | 1h | ⬜ Pending |
| 03 | [Initial Service Labels](03-initial-service-labels.md) | High | 1-2h | ⬜ Pending |
| 04 | [AdGuard DNS Rewrites](04-adguard-dns-rewrites.md) | Critical | 30m | ⬜ Pending |
| 05 | [Test Initial Services](05-test-initial-services.md) | High | 1h | ⬜ Pending |

**Phase 1 Goal:** Deploy Traefik, configure DNS, and validate with 3 simple services (Glance, HortusFox, Grafana).

### Phase 2: Complex Services (Week 2)

| # | Ticket | Priority | Time | Status |
|---|--------|----------|------|--------|
| 06 | [n8n Configuration](06-n8n-configuration.md) | High | 1.5-2h | ⬜ Pending |
| 07 | [Bookwyrm Configuration](07-bookwyrm-configuration.md) | Medium | 1.5-2h | ⬜ Pending |

**Phase 2 Goal:** Migrate services with special considerations (n8n has built-in SSL, Bookwyrm is external).

### Phase 3: Complete Rollout (Week 2-3)

| # | Ticket | Priority | Time | Status |
|---|--------|----------|------|--------|
| 08 | [Remaining Services](08-remaining-services.md) | Medium | 2-3h | ⬜ Pending |
| 09 | [Update Documentation](09-update-documentation.md) | High | 1.5-2h | ⬜ Pending |

**Phase 3 Goal:** Complete migration for all remaining services and update all documentation.

### Phase 4: Security Hardening (Post-Monitoring)

| # | Ticket | Priority | Time | Status |
|---|--------|----------|------|--------|
| 10 | [Remove Direct Port Access](10-remove-direct-port-access.md) | Medium | 1-2h | ⬜ Pending |

**Phase 4 Goal:** Remove legacy IP:port access after monitoring period, forcing all traffic through Traefik.

## Total Time Estimate

- **Foundation:** 6.5-8 hours
- **Complex Services:** 3-4 hours
- **Complete Rollout:** 3.5-5 hours
- **Security Hardening:** 1-2 hours
- **Total:** 14.5-19 hours

## Prerequisites

- All services currently deployed and functional
- AdGuard Home running as network DNS (already deployed)
- Docker and Docker Compose working
- SERVER_IP defined in `.env`
- Ports 80 and 443 available (will move AdGuard from port 80)

## Dependencies Between Tickets

```
01 (Traefik) ──┬──> 03 (Service Labels) ──> 05 (Testing)
               │                               │
02 (AdGuard) ──┴──> 04 (DNS Rewrites) ────────┘
                                               │
                                               ├──> 06 (n8n) ─────┐
                                               │                   │
                                               └──> 07 (Bookwyrm) ─┤
                                                                   │
                                                                   ├──> 08 (Remaining) ──> 09 (Docs)
```

**Critical Path:**
1. Deploy Traefik (01)
2. Move AdGuard to new port (02)
3. Configure DNS rewrites (04)
4. Add service labels (03)
5. Test initial services (05)
6. Complete remaining services (06-08)
7. Update documentation (09)

## Implementation Strategy

### Parallel vs Sequential

**Can be done in parallel:**
- Ticket 01 (Traefik) and Ticket 02 (AdGuard port move)
- Ticket 06 (n8n) and Ticket 07 (Bookwyrm) after ticket 05 is complete

**Must be sequential:**
- Tickets 03-05 require tickets 01, 02, 04 to be complete
- Ticket 09 should be last (after all services configured)

### Backward Compatibility

Throughout implementation:
- **Keep existing port mappings** - Services remain accessible via IP:port
- **Add domain access** - New access method alongside old
- **Gradual transition** - Users can switch at their own pace
- **Documentation shows both** - Legacy and new methods documented

### Rollback Strategy

Each ticket includes a rollback plan. If major issues occur:
1. Services remain accessible via IP:port (no downtime)
2. Can remove Traefik labels to disable domain routing
3. Can stop Traefik entirely without affecting services
4. Can revert DNS changes in AdGuard Home

## Success Criteria

### Technical Metrics
- ✅ All services accessible via `https://*.home.local`
- ✅ All services maintain IP:port access (backward compatibility)
- ✅ DNS resolution working for all domains
- ✅ HTTPS working with self-signed certificates
- ✅ No service downtime during migration
- ✅ No errors in Traefik or service logs

### User Experience Metrics
- ✅ Users can access services by easy-to-remember names
- ✅ HTTPS locks appear in browser (even with warnings)
- ✅ Services load at comparable speeds
- ✅ All service functionality intact
- ✅ Clear documentation for both access methods

### Operational Metrics
- ✅ Easy to add new services (just add labels)
- ✅ Centralized monitoring via Traefik dashboard
- ✅ Access logs captured by Traefik
- ✅ SSL certificates managed automatically

## Post-Implementation

After all tickets complete:

### Monitoring Period (1-2 weeks)
- Monitor Traefik logs for errors
- Track service availability
- Gather user feedback
- Document any issues encountered

### Optimization Phase
- Consider removing direct port mappings (if stable)
- Add authentication middleware for unprotected services
- Implement rate limiting if needed
- Consider Let's Encrypt for valid certificates (if services exposed publicly)

### Future Enhancements
- Implement mkcert for locally-trusted certificates (no browser warnings)
- Add OAuth2 proxy for centralized authentication
- Implement fail2ban for brute force protection
- Add geo-blocking if services exposed to internet
- Configure monitoring alerts for Traefik health

## Related Documentation

- **[SETUP.md](../../docs/SETUP.md)** - Initial server setup guide
- **[CONFIGURATION.md](../../docs/CONFIGURATION.md)** - Service configuration details
- **[OPERATIONS.md](../../docs/OPERATIONS.md)** - Day-to-day operations
- **[TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[ARCHITECTURE.md](../../docs/ARCHITECTURE.md)** - System architecture overview

## Security Considerations

### Local Network Only
- Domain access works only on local network (via AdGuard DNS)
- SSL certificates are self-signed (suitable for local use)
- No external DNS required
- Services not exposed to internet (unless configured)

### VPN Integration
- WireGuard VPN already deployed in stack
- VPN clients can use domain names (if AdGuard set as DNS)
- Remote access remains secure through VPN

### Certificate Trust
- Self-signed certificates cause browser warnings (expected)
- Trust warnings can be bypassed (safe on local network)
- For trusted certificates, use mkcert (see ticket 01 notes)

### Best Practices
- Keep Traefik updated for security patches
- Limit Traefik dashboard access (basic auth configured)
- Monitor access logs for suspicious activity
- Use WireGuard VPN for remote access (not port forwarding)

## Questions & Answers

**Q: Why .home.local instead of .local?**
A: The `.home` subdomain avoids conflicts with mDNS/Bonjour `.local` domains while remaining clearly local-only.

**Q: Why self-signed certificates?**
A: For local network use, self-signed certs are simpler and don't require DNS validation. They're safe within your network.

**Q: Can I use Let's Encrypt instead?**
A: Yes, but requires DNS challenge (since services are local-only). See Traefik configuration docs.

**Q: What if I add a new service later?**
A: Just add Traefik labels to the service's docker-compose entry. The wildcard DNS rewrite handles the domain automatically.

**Q: Can I use a different domain instead of .home.local?**
A: Yes! Update the DNS rewrites in AdGuard and the Traefik labels. Avoid public TLDs to prevent DNS conflicts.

**Q: Will this work from mobile devices?**
A: Yes, if mobile devices use AdGuard Home as DNS. Configure via DHCP or manually in WiFi settings.

## Notes

- Implementation can be paused between tickets without issues
- Services remain functional throughout entire process
- No data loss or service interruption expected
- Each ticket is independently testable
- Rollback is straightforward at any point

## Support

- **Issues:** Report problems in main repository issues
- **Questions:** See TROUBLESHOOTING.md or open a discussion
- **Updates:** Check ticket status in this README

---

**Status Legend:**
- ⬜ Pending
- 🟦 In Progress
- ✅ Complete
- ❌ Blocked

**Last Updated:** 2025-01-13
