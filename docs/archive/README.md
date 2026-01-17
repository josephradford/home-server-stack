# Archived Documentation

This directory contains legacy documentation from the initial development phase of the home-server-stack project.

## Purpose

These files are preserved for **historical reference** and contain valuable detailed information about:
- Initial architecture decisions and implementations
- Step-by-step setup procedures from early versions
- Troubleshooting solutions for legacy configurations
- Detailed service-specific documentation

## Why Archived?

The documentation in this folder was created during active development and captures point-in-time implementation details. As the project matured:

1. **Simpler structure**: Main documentation consolidated into `CLAUDE.md` and `README.md`
2. **Better visualization**: New `docs/ARCHITECTURE.md` uses Mermaid diagrams instead of ASCII art
3. **Reduced maintenance**: Fewer files to keep synchronized with code changes
4. **Preserved history**: These docs remain available for reference without cluttering the main docs directory

## Current Documentation

For current setup and usage instructions, see:
- **[README.md](../../README.md)** - Quick start and overview
- **[CLAUDE.md](../../CLAUDE.md)** - Complete project instructions and architecture
- **[docs/ARCHITECTURE.md](../ARCHITECTURE.md)** - Visual architecture diagrams
- **[SERVICES.md](../../SERVICES.md)** - Service catalog

## Using Archived Docs

These files are **read-only** historical references. If you find information here that's missing from current docs:
1. Check if it's already covered in `CLAUDE.md` or `README.md`
2. If not, consider opening an issue to add it to current documentation
3. Don't directly update these archived files

## Files in Archive

| File | Original Purpose | Current Equivalent |
|------|-----------------|-------------------|
| ALERTS.md | Alert definitions and response procedures | See `CLAUDE.md` Monitoring section |
| ARCHITECTURE.md | Original ASCII architecture diagrams | **docs/ARCHITECTURE.md** (Mermaid diagrams) |
| BACKEND_API.md | Homepage API documentation | See `CLAUDE.md` Homepage API section |
| CONFIGURATION.md | Service configuration details | See `CLAUDE.md` Service-Specific Notes |
| DASHBOARD_SETUP.md | Dashboard setup guide | See `CLAUDE.md` Homepage Dashboard section |
| DOMAIN-BASED-ACCESS.md | Domain routing documentation | See `CLAUDE.md` Domain-Based Routing |
| HOME_ASSISTANT_SETUP.md | Home Assistant integration | See `CLAUDE.md` Home Assistant section |
| KNOWN_ISSUES.md | Known issues tracker | See GitHub Issues |
| MONITORING_DEPLOYMENT.md | Monitoring setup | See `CLAUDE.md` Monitoring Stack |
| OPERATIONS.md | Day-to-day operations | See `CLAUDE.md` Common Development Commands |
| REMOTE_ACCESS.md | VPN and remote access | See `CLAUDE.md` WireGuard VPN Management |
| REQUIREMENTS.md | System requirements | See `README.md` and `CLAUDE.md` |
| SECURITY-OPERATIONS.md | Security procedures | See `CLAUDE.md` Security Architecture |
| SETUP.md | Setup instructions | See `README.md` Quick Start |
| TROUBLESHOOTING.md | Troubleshooting guide | See `CLAUDE.md` Common Issues |
| WIREGUARD_SECURITY.md | WireGuard security | See `CLAUDE.md` WireGuard section |

---

**Note:** These docs were archived on 2025-12-12 and reflect the project state at that time. For the most current information, always refer to the main documentation.
