# Dynamic DNS (DDNS)

If your ISP assigns a dynamic public IP, DDNS keeps a DNS hostname pointed at
your current IP. This is a prerequisite for external VPN access: the WireGuard
server runs on the UniFi Dream Router 7, and VPN clients use `vpn.DOMAIN` as its
endpoint, so it must follow your public IP when your ISP changes it.

If you have a **static public IP**, skip this entirely and use that IP as the
endpoint in the UDR7's VPN peer configs.

DDNS runs on this server as a systemd timer (independent of Docker), not on the
router because it is already set up and working with Gandi LiveDNS. The UDR7 also has
a built-in Dynamic DNS setting; if it supports your DNS provider you could use that
instead and retire this timer.

## How it works

The update script (`scripts/ddns/gandi-ddns-update.sh`) runs every 5 minutes
via a systemd timer. It:

1. Fetches your current public IP from `ifconfig.me` (falls back to `ipinfo.io`)
2. Reads the current A record for `WIREGUARD_DDNS_SUBDOMAIN.DOMAIN` from Gandi LiveDNS
3. Updates the record only if the IP has changed (TTL 300 s)

The same Gandi API token used for SSL certificates (`GANDIV5_PERSONAL_ACCESS_TOKEN`) is reused here — no extra credentials needed.

## Setup

### 1. Set environment variables

In `.env`:

```bash
# Subdomain for the A record DDNS will create and maintain
# (the name is historical; it is the VPN endpoint hostname, not a WireGuard setting)
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
- Install a systemd timer (`gandi-ddns.timer`) that runs the update script every 5 minutes

### 3. Verify

```bash
# Trigger an immediate check
make ddns-update

# Show current public IP vs what Gandi has
make ddns-status

# Tail the update log
tail -f /var/log/gandi-ddns.log
```

### 4. Use the hostname in the UDR7 VPN

In the UniFi Network app, set the WireGuard VPN server's endpoint/hostname to
`vpn.DOMAIN` (rather than a raw IP) before generating peer configs. If peers
were created with a raw IP as `Endpoint`, regenerate them and re-scan the QR code
in the WireGuard app on that device.

## Ongoing use

The timer runs silently every 5 minutes and only writes to the log when the
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
