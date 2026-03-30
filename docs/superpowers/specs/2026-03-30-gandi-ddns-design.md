# Gandi LiveDNS Dynamic DNS — Design Spec

**Date:** 2026-03-30
**Branch:** `docs/restructure-env-example`
**Status:** Approved

---

## Problem

WireGuard peer configs contain a static `Endpoint` hostname. Most home ISPs assign dynamic public IPs, so this hostname must be kept current. Previously handled by No-IP with router-based DDNS. This spec replaces that with a self-hosted solution using the Gandi LiveDNS API — reusing the existing `GANDIV5_PERSONAL_ACCESS_TOKEN` already in `.env`.

---

## Approach

Two bash scripts following existing repo conventions, wired up via Makefile targets and a user-space cron job:

- **`scripts/ddns/gandi-ddns-update.sh`** — lightweight update script run by cron every 5 minutes
- **`scripts/ddns/setup-gandi-ddns.sh`** — one-time setup: creates the DNS A record and installs the cron entry

No new dependencies. Both scripts use only `curl`, which is already used throughout the repo.

---

## Files

```
scripts/ddns/
  gandi-ddns-update.sh
  setup-gandi-ddns.sh
```

Log file: `/var/log/gandi-ddns.log`

---

## Environment Variables

Added to `.env.example` in the WireGuard section:

| Variable | Example | Purpose |
|---|---|---|
| `WIREGUARD_DDNS_SUBDOMAIN` | `vpn` | Subdomain to manage (resolves to `vpn.DOMAIN`) |
| `WIREGUARD_SERVERURL` | `vpn.example.com` | Updated to reference the DDNS hostname instead of a raw IP |

Existing variables reused: `DOMAIN`, `GANDIV5_PERSONAL_ACCESS_TOKEN`.

---

## `gandi-ddns-update.sh` Logic

1. Load `.env` — validate `DOMAIN`, `GANDIV5_PERSONAL_ACCESS_TOKEN`, `WIREGUARD_DDNS_SUBDOMAIN`
2. Fetch current public IP via `curl ifconfig.me` with fallback to `ipinfo.io/ip`
3. GET current A record value from Gandi LiveDNS API
4. If IP unchanged → log "IP unchanged, skipping" and exit 0
5. If changed → PUT new IP to Gandi API
6. Log result with timestamp to `/var/log/gandi-ddns.log`
7. Exit non-zero on any API or network failure

**Gandi API endpoint:**
```
PUT https://api.gandi.net/v5/livedns/domains/{DOMAIN}/records/{SUBDOMAIN}/A
Authorization: Bearer {GANDIV5_PERSONAL_ACCESS_TOKEN}
Body: {"rrset_values": ["<public-ip>"], "rrset_ttl": 300}
```

TTL set to 300s (5 minutes) to match the cron interval — ensures DNS catches up quickly after an IP change.

---

## `setup-gandi-ddns.sh` Logic

1. Load `.env` — validate required variables
2. Fetch current public IP
3. PUT the initial A record to Gandi LiveDNS (`vpn.DOMAIN → current public IP`)
4. Install cron entry (idempotent — checks for existing entry before adding):
   ```
   */5 * * * * /path/to/scripts/ddns/gandi-ddns-update.sh >> /var/log/gandi-ddns.log 2>&1
   ```
5. Create `/var/log/gandi-ddns.log` with correct permissions (`sudo touch` + `chmod 644`)
6. Print summary and next steps

---

## Makefile Targets

| Target | Description |
|---|---|
| `ddns-setup` | Runs `setup-gandi-ddns.sh` — creates DNS record and installs cron |
| `ddns-update` | Manually triggers `gandi-ddns-update.sh` — useful for testing |
| `ddns-status` | Prints current public IP alongside current Gandi A record value |

---

## Integration with WireGuard Workflow

`make wireguard-setup` completion output will be updated to mention DDNS as an optional next step for users with dynamic IPs:

```
Optional: If your public IP is dynamic, set up automatic DNS updates:
  make ddns-setup
```

`ddns-setup` is **not** called by `make setup` because:
- WireGuard itself is not part of `make setup` (it's a separate system-level workflow)
- Users with static IPs don't need it

---

## Security

`vpn.DOMAIN` is published in public DNS. This reveals that a VPN endpoint exists at that address, but WireGuard's stealth handshake mitigates the risk — it silently drops all packets from unknown peers without responding. Anyone scanning the port finds nothing to interact with. The cryptographic handshake is the security boundary, not hostname obscurity.

---

## Next Steps for Existing Peers

After running `ddns-setup`, any existing WireGuard peers must have their configs regenerated to use the new hostname endpoint:

```bash
# Remove old peer and re-add to get updated Endpoint line
sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>
```

This will be noted in the `setup-gandi-ddns.sh` completion output.
