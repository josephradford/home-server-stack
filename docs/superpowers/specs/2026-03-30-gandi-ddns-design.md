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
- **`scripts/ddns/setup-gandi-ddns.sh`** — one-time setup: creates the DNS A record, installs the cron entry, configures log rotation

No new dependencies beyond `jq` (for JSON parsing). All other tools (`curl`, `crontab`) are standard on Ubuntu.

---

## Files

```
scripts/ddns/
  gandi-ddns-update.sh
  setup-gandi-ddns.sh
/etc/logrotate.d/gandi-ddns     (written by setup-gandi-ddns.sh)
/var/log/gandi-ddns.log         (created by setup-gandi-ddns.sh)
```

---

## Environment Variables

Added to `.env.example` in the WireGuard section:

| Variable | Example | Purpose |
|---|---|---|
| `WIREGUARD_DDNS_SUBDOMAIN` | `vpn` | Subdomain to manage (resolves to `vpn.DOMAIN`) |
| `WIREGUARD_SERVERURL` | `vpn.example.com` | Updated to reference the DDNS hostname instead of a raw IP |

Existing variables reused: `DOMAIN`, `GANDIV5_PERSONAL_ACCESS_TOKEN`.

---

## Gandi LiveDNS API

**GET current record:**
```
GET https://api.gandi.net/v5/livedns/domains/{DOMAIN}/records/{SUBDOMAIN}/A
Authorization: Bearer {GANDIV5_PERSONAL_ACCESS_TOKEN}
```
Response body:
```json
{
  "rrset_values": ["1.2.3.4"],
  "rrset_ttl": 300
}
```
Parse current IP with: `jq -r '.rrset_values[0]'`
A 404 response means the record does not yet exist — treat as "always needs updating" and proceed to PUT.

**PUT updated record:**
```
PUT https://api.gandi.net/v5/livedns/domains/{DOMAIN}/records/{SUBDOMAIN}/A
Authorization: Bearer {GANDIV5_PERSONAL_ACCESS_TOKEN}
Content-Type: application/json
Body: {"rrset_values": ["<public-ip>"], "rrset_ttl": 300}
```

**TTL note:** 300s TTL matches the cron interval. In the worst case (resolver just cached the old record and cron fires immediately after an IP change), total propagation delay before all resolvers see the new IP is up to 10 minutes (5 min TTL drain + 5 min until next cron run). This is acceptable for a WireGuard use case — the client will reconnect on the next handshake attempt.

---

## `gandi-ddns-update.sh` Logic

1. Load `.env` — validate `DOMAIN`, `GANDIV5_PERSONAL_ACCESS_TOKEN`, `WIREGUARD_DDNS_SUBDOMAIN`
2. Fetch current public IP:
   - Try `curl -sf --max-time 5 ifconfig.me`
   - Fallback: `curl -sf --max-time 5 ipinfo.io/ip`
   - Validate response matches IPv4 pattern (`^[0-9]{1,3}(\.[0-9]{1,3}){3}$`)
   - If both fail or return invalid response: log error and `exit 1` — do **not** touch DNS
3. GET current A record from Gandi API:
   - HTTP 200: parse `rrset_values[0]` with `jq`
   - HTTP 404: record does not exist — skip comparison, proceed to PUT
   - Any other status: log error and `exit 1`
4. If current IP matches Gandi record → log "IP unchanged (1.2.3.4), skipping" and `exit 0`
5. PUT new IP to Gandi API with `Content-Type: application/json`
   - On success (HTTP 201/204): log "Updated vpn.DOMAIN → 1.2.3.4"
   - On failure: log error with HTTP status and `exit 1`
6. All log lines prefixed with `[YYYY-MM-DD HH:MM:SS]`

---

## `setup-gandi-ddns.sh` Logic

1. Load `.env` — validate `DOMAIN`, `GANDIV5_PERSONAL_ACCESS_TOKEN`, `WIREGUARD_DDNS_SUBDOMAIN`
2. Check `jq` is installed — if not, print install instructions and exit
3. Fetch and validate current public IP (same logic as update script)
4. PUT initial A record to Gandi LiveDNS (`vpn.DOMAIN → current public IP`)
5. Create log file owned by the invoking user (requires sudo to write to `/var/log/`):
   ```bash
   sudo touch /var/log/gandi-ddns.log
   sudo chown "${SUDO_USER:-$(whoami)}": /var/log/gandi-ddns.log
   sudo chmod 644 /var/log/gandi-ddns.log
   ```
   `$SUDO_USER` is set by sudo to the original unprivileged user, ensuring the cron job (which runs as that user) can append to the file.
6. Write logrotate config to `/etc/logrotate.d/gandi-ddns` (requires sudo):
   ```
   /var/log/gandi-ddns.log {
       daily
       rotate 7
       compress
       missingok
       notifempty
   }
   ```
7. Install user crontab entry (idempotent):
   ```bash
   SCRIPT_PATH="$(realpath scripts/ddns/gandi-ddns-update.sh)"
   (crontab -l 2>/dev/null | grep -v "gandi-ddns-update.sh"; \
    echo "*/5 * * * * $SCRIPT_PATH >> /var/log/gandi-ddns.log 2>&1") | crontab -
   ```
   Deduplication key: `gandi-ddns-update.sh` (matches on script filename, handles repo path changes cleanly by removing any previous entry before adding the new one)
8. Print summary and next steps

---

## Makefile Targets

| Target | Description |
|---|---|
| `ddns-setup` | Runs `setup-gandi-ddns.sh` — creates DNS record, installs cron, configures log rotation |
| `ddns-update` | Manually triggers `gandi-ddns-update.sh` — useful for testing |
| `ddns-status` | Read-only: prints current public IP and current Gandi A record value side-by-side |

**`ddns-status` implementation:** Inline Makefile shell — fetches public IP via `curl ifconfig.me` and fetches the Gandi A record via GET, parses with `jq`. No script file needed for this simple read-only display.

---

## Integration with WireGuard Workflow

`make wireguard-setup` completion output will be updated to mention DDNS as an optional next step for users with dynamic IPs:

```
Optional: If your public IP is dynamic, set up automatic DNS updates:
  1. Set WIREGUARD_DDNS_SUBDOMAIN=vpn in .env
  2. Run: make ddns-setup
  3. Update WIREGUARD_SERVERURL=vpn.DOMAIN in .env
```

`ddns-setup` is **not** called by `make setup` because:
- WireGuard itself is not part of `make setup` (it's a separate system-level workflow)
- Users with static IPs don't need it

---

## Security

`vpn.DOMAIN` is published in public DNS. This reveals that a VPN endpoint exists at that address, but WireGuard's stealth handshake mitigates the risk — it silently drops all packets from unknown peers without responding. Anyone scanning the port finds nothing to interact with. The cryptographic handshake is the security boundary, not hostname obscurity.

---

## Next Steps for Existing Peers

After running `ddns-setup`, any existing WireGuard peers must have their configs regenerated to use the new hostname endpoint. This will be noted in the `setup-gandi-ddns.sh` completion output:

```
Action required: regenerate configs for existing WireGuard peers:
  sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>
```
