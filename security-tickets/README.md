# Security Implementation Tickets

This directory contains security improvement tickets for the Home Server Stack project. Each ticket follows the same format as the monitoring tickets and includes detailed implementation guidance.

> **🔒 VPN-First Hybrid Security Strategy**
>
> This roadmap implements a **VPN-first approach** where WireGuard VPN is the primary security boundary. Most services are only accessible via VPN, with the exception of n8n webhook endpoints which must be publicly accessible for external integrations (GitHub webhooks, etc.).
>
> **Public Exposure (Internet-Accessible):**
> - WireGuard VPN (port 51820/udp) - Primary entry point
> - n8n webhooks only (`/webhook/*` paths) - For external integrations
>
> **VPN-Required (Private):**
> - All admin interfaces (Grafana, Prometheus, AdGuard, n8n UI)
> - All internal services (Ollama, monitoring stack)
>
> This approach dramatically reduces attack surface while maintaining functionality for external webhooks.

## Implementation Roadmap (Revised for VPN-First)

### Phase 1: Week 1-2 (Critical - VPN Foundation)
**Establish VPN as primary security boundary**

1. ✅ [Fix Privileged Container (cAdvisor)](01-fix-privileged-cadvisor.md) - 2-3 hours
2. ✅ [Implement Secret Scanning Pre-Commit Hooks](02-secret-scanning-pre-commit-hooks.md) - 2-3 hours
3. ✅ [Pin All Docker Image Versions](03-pin-docker-image-versions.md) - 2-4 hours
4. **🆕 [WireGuard VPN Hardening](17-wireguard-hardening.md) - 3-4 hours** ⭐ **HIGHEST PRIORITY**

**Total Phase 1**: 9-13 hours

### Phase 2: Week 2-3 (High Priority - Hybrid Exposure)
**Configure selective exposure for n8n webhooks**

5. ⬜ [Implement Network Segmentation](05-network-segmentation.md) - 3-4 hours
   - *Updated for VPN-first hybrid model*
6. ⬜ [n8n Path-Based Access Control (Reverse Proxy)](06-reverse-proxy-rate-limiting.md) - 2-3 hours
   - *Simplified for n8n-only; webhooks public, UI requires VPN*
7. ⬜ [Let's Encrypt for n8n Webhooks](04-tls-certificate-monitoring.md) - 2-3 hours
   - *Focused on n8n only; VPN services use self-signed certs*
8. ⬜ [Add Image Vulnerability Scanning to CI/CD](07-image-vulnerability-scanning.md) - 3-4 hours

**Total Phase 2**: 10-14 hours

### Phase 3: Month 2 (Medium Priority Hardening)
**Operational excellence and defense in depth**

9. ⬜ [Deploy Centralized Logging (Loki)](09-centralized-logging-loki.md) - 4-5 hours
10. ⬜ [Implement Automated Backups](10-automated-backups.md) - 4-6 hours
11. ⬜ [Add Resource Limits and Security Profiles](11-resource-limits-security-profiles.md) - 3-4 hours
12. ⬜ [Configure Comprehensive Alerting](12-comprehensive-alerting.md) - 3-4 hours

**Total Phase 3**: 14-19 hours

### Phase 4: Month 3+ (Optional Enhancements)
**Nice-to-have improvements - VPN already provides primary security**

13. ⬜ [Add Security Documentation](13-security-documentation.md) - 4-6 hours
14. ⬜ [Implement Compliance Scanning](14-compliance-scanning.md) - 3-4 hours
15. ⬜ [Set Up Regular Security Audits](15-regular-security-audits.md) - 2-3 hours
16. ⬜ [Create Security Training Materials](16-security-training.md) - 4-6 hours
17. ⬜ [Centralized Authentication & MFA (Optional)](08-authentication-mfa.md) - 6-8 hours
    - *Now optional - VPN provides primary auth; this adds SSO convenience*

**Total Phase 4**: 19-27 hours (optional)

## Total Estimated Time

**Critical Path (Phases 1-3)**: 33-46 hours
**With Optional Enhancements (Phase 4)**: 52-73 hours

**VPN-First Benefits:**
- 🎯 Reduced implementation time (removed full reverse proxy, simplified certs)
- 🔒 Smaller attack surface (only 2 public ports vs many)
- ✅ Simpler architecture (VPN handles auth, less middleware)
- 💰 No domain required for most services (optional for n8n webhooks)

## Priority Legend
- **Priority 1 (Critical)**: Must implement before production use
- **Priority 2 (High)**: Essential for secure production deployment
- **Priority 3 (Medium)**: Important for operational security
- **Priority 4 (Low)**: Enhancements and continuous improvement

## Security Impact Summary (VPN-First Model)

| Ticket | Security Impact | Risk Reduction | Priority |
|--------|----------------|----------------|----------|
| #17 🆕 | **WireGuard VPN - Primary security boundary** | **90% attack surface reduction** | ⭐ Critical |
| #01 | Remove privileged container access | 95% container escape prevention | Critical |
| #02 | Prevent secret leakage | 90% reduction in credential exposure | Critical |
| #03 | Prevent supply chain attacks | 80% reduction in supply chain risk | Critical |
| #05 | Network isolation (VPN-aware) | 60% reduction in lateral movement | High |
| #06 | n8n webhook path control | 85% reduction in n8n attack surface | High |
| #04 | Let's Encrypt for n8n webhooks | 100% webhook cert validation | High |
| #07 | Block vulnerable images | 80% reduction in known CVEs | High |
| #09 | Security event visibility | 50% faster incident detection | Medium |
| #10 | Data protection & recovery | 90% reduction in data loss risk | Medium |
| #11 | Resource protection | 40% reduction in DoS risk | Medium |
| #12 | Faster incident response | 60% faster response time | Medium |
| #08 | SSO/MFA (Optional) | 20% additional defense-in-depth | Optional |
| #13-16 | Process improvements | Ongoing risk reduction | Optional |

**Key Changes:**
- **#17 (WireGuard)**: Now the most critical ticket - provides 90% of security value
- **#06 (Reverse Proxy)**: Simplified to n8n-only path-based routing
- **#04 (TLS)**: Focused on n8n webhooks only; VPN services use self-signed
- **#08 (Auth/MFA)**: Downgraded to optional - VPN provides primary auth

## Quick Start (VPN-First)

1. **Start with WireGuard (Ticket #17)** - This is your primary security boundary ⭐
2. Complete Phase 1 (Critical) tickets - Container security foundations
3. Set up Phase 2 (High Priority) - Hybrid exposure for n8n webhooks
4. Test VPN access to all services before proceeding
5. Phase 3+ is optional - VPN already provides strong security

**Key Decision Point:** Do you need external webhooks (GitHub, APIs, etc.)?
- **YES**: Implement Phase 2 (n8n webhook exposure with path-based routing)
- **NO**: Skip #06 and #04, keep everything VPN-only (even simpler!)

## Dependencies (VPN-First Model)

**Critical Path:**
- #17 (WireGuard) → Must be first, establishes security boundary
- #05 (Network Segmentation) → Provides defense-in-depth if VPN compromised
- #06 (Reverse Proxy) → Only if you need n8n webhooks; requires #17 first
- #04 (TLS for n8n) → Only if you need n8n webhooks; requires #06

**Optional Dependencies:**
- #08 (Authentication) → Optional; requires #06 if implementing
- #12 (Alerting) → Depends on #04 and #09 (but #04 now simplified)
- #09 (Logging) → Independent, can implement anytime

## Testing

Each ticket includes:
- Testing commands
- Success metrics
- Rollback procedures

Always test in a development environment first!

## Getting Help

- Review the main [SECURITY.md](../SECURITY.md) for security policy
- Check [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
- Consult individual ticket references for external documentation

## Progress Tracking

Update this README as you complete tickets:
- ✅ = Completed
- ⬜ = Not started
- 🔄 = In progress
- ⚠️ = Blocked/Issues
