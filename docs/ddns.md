# Dynamic DNS (DDNS)

If your ISP assigns a dynamic public IP, DDNS keeps a DNS hostname pointed at
your current IP. This is a prerequisite for external WireGuard access — without
it, `WIREGUARD_SERVERURL` breaks whenever your IP changes.

If you have a **static public IP**, skip this entirely and set
`WIREGUARD_SERVERURL` to that IP directly.

## How it works

The update script (`scripts/ddns/gandi-ddns-update.sh`) runs every 5 minutes
via cron. It:

1. Fetches your current public IP from `ifconfig.me` (falls back to `ipinfo.io`)
2. Reads the current A record for `WIREGUARD_DDNS_SUBDOMAIN.DOMAIN` from Gandi LiveDNS
3. Updates the record only if the IP has changed (TTL 300 s)

The same Gandi API token used for SSL certificates (`GANDIV5_PERSONAL_ACCESS_TOKEN`) is reused here — no extra credentials needed.

## Setup

### 1. Set environment variables

In `.env`:

```bash
# Hostname VPN clients connect to — set this to the subdomain DDNS manages
WIREGUARD_SERVERURL=vpn.your-domain.com

# Subdomain for the A record DDNS will create and maintain
WIREGUARD_DDNS_SUBDOMAIN=vpn
```

`WIREGUARD_DDNS_SUBDOMAIN=vpn` creates the record `vpn.DOMAIN → <your public IP>`.

### 2. Run one-time setup

```bash
sudo make ddns-setup
```

This will:
- Fetch your current public IP
- Create the A record in Gandi LiveDNS
- Create `/var/log/gandi-ddns.log` with correct ownership
- Configure daily log rotation under `/etc/logrotate.d/gandi-ddns`
- Install a cron entry for your user that runs the update script every 5 minutes

### 3. Verify

```bash
# Trigger an immediate check
make ddns-update

# Show current public IP vs what Gandi has
make ddns-status

# Tail the cron log
tail -f /var/log/gandi-ddns.log
```

### 4. Regenerate WireGuard peer configs

If you already had WireGuard peers configured with a raw IP as `Endpoint`, you
need to regenerate their configs so they use the hostname instead:

```bash
sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>
```

Re-scan the QR code in the WireGuard app on that device.

## Ongoing use

The cron job runs silently every 5 minutes and only writes to the log when the
IP changes (or on error). Normal operation produces no output.

```bash
make ddns-status   # Check current IP vs DNS record
make ddns-update   # Trigger a manual update check
tail /var/log/gandi-ddns.log  # View update history
```

## Key files

| What | Where |
|------|-------|
| Update script | `scripts/ddns/gandi-ddns-update.sh` |
| Setup script | `scripts/ddns/setup-gandi-ddns.sh` |
| Update log | `/var/log/gandi-ddns.log` |
| Log rotation config | `/etc/logrotate.d/gandi-ddns` |

## Why not part of `make setup`?

DDNS setup is intentionally separate:

- **Optional** — not needed if your ISP gives you a static IP
- **Requires `sudo`** — setup writes to `/var/log/` and `/etc/logrotate.d/`
- **One-time** — unlike `make setup`, it shouldn't re-run on every deploy
