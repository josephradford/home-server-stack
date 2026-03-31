# WireGuard VPN

WireGuard provides secure remote access to the home network. It runs as a system service (`wg-quick@wg0`), not a Docker container — this ensures VPN access stays up even when the Docker stack is restarted or updated.

## How it all fits together

Setup has two distinct phases: a one-time server setup, and ongoing peer (client device) management.

### One-time setup

Run these once when setting up a new server:

```bash
# 1. Install the WireGuard apt package
make wireguard-install

# 2. Generate server keys, write /etc/wireguard/wg0.conf,
#    and enable + start the wg-quick@wg0 systemd service
make wireguard-setup

# 3. Start the Docker stack (must come before wireguard-routing)
make start

# 4. Add iptables rules so VPN clients can reach Docker containers and the LAN.
#    Must run AFTER make start — it inspects the live Docker bridge network.
make wireguard-routing
```

### Adding client devices (peers)

Run once per device you want to connect:

```bash
sudo ./scripts/wireguard/wireguard-add-peer.sh <name>

# Examples:
sudo ./scripts/wireguard/wireguard-add-peer.sh laptop
sudo ./scripts/wireguard/wireguard-add-peer.sh phone
```

This generates a key pair for the device, adds a `[Peer]` block to `/etc/wireguard/wg0.conf`, and saves the client config and QR code to `data/wireguard/peers/<name>/`. Scan the QR code in the WireGuard app to connect.

> There is no `make` target for this because it requires a peer name argument.

## Ongoing use

```bash
# Check service is running and enabled
make wireguard-status

# List peers and view connection status
make wireguard-peers

# Test routing, iptables rules, and handshakes
make wireguard-test

# View live connection details
sudo wg show

# Systemd service management
sudo systemctl status wg-quick@wg0
sudo systemctl restart wg-quick@wg0
```

## Key file locations

| What | Where |
|------|-------|
| Server config | `/etc/wireguard/wg0.conf` |
| Client configs + QR codes | `data/wireguard/peers/<name>/` |
| Allowed IPs (split tunnel) | `WIREGUARD_ALLOWEDIPS` in `.env` |

## External access and DDNS

For VPN clients connecting from outside your home network, WireGuard needs a
stable hostname or IP via `WIREGUARD_SERVERURL` in `.env`, plus a port forward
on your router (UDP `WIREGUARD_PORT` → `SERVER_IP`).

If your ISP assigns a dynamic public IP, set up DDNS first — see
[docs/ddns.md](ddns.md).

## Split tunneling

WireGuard is configured for split tunneling by default — only traffic destined for the home network and VPN subnet is routed through the VPN:

```
WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24
```

Do **not** use `0.0.0.0/0` unless you want all internet traffic routed through your home server.
