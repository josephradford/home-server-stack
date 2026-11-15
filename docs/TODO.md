# TODO

Known follow-ups that aren't tied to a feature in progress.

## Fix the boot race that leaves AdGuard (and others) broken after a power loss

**Seen:** 2026-11-15. After a hard power loss (server down ~10 days), Docker
started the containers a few seconds into boot, before the host network was
fully up.

- `adguard-home` showed `Up` but had **no published ports**: nothing listened on
  `SERVER_IP:53`, and every upstream logged `network is unreachable`. LAN DNS
  was down until it was recreated (`docker compose up -d --force-recreate adguard`).
- `prometheus` was left `Exited (255)` despite `restart: unless-stopped`; it
  needed a manual `docker start prometheus`.
- The other containers recovered on their own.

Because `SERVER_IP:53` is bound to a specific address, AdGuard is the one most
sensitive to the address not existing yet. If it is down, DNS (and so the
internet) is down for the whole LAN.

**Ideas to evaluate**
- Make `docker.service` wait for the network, e.g. a systemd drop-in with
  `After=network-online.target` and `Wants=network-online.target`
  (check `systemd-networkd-wait-online` / `NetworkManager-wait-online` is enabled).
- A boot-time check (systemd unit or timer) that runs `make status` / probes
  `dig @SERVER_IP` and recreates AdGuard if it isn't answering.
- A Docker healthcheck on AdGuard that does a real DNS lookup, so `Up` means it
  is serving, plus an autoheal-style restart.
- Re-enable or rework the `AdGuardDNSFailing` alert (disabled in #264) so a
  silent DNS outage pages someone.
- Script the fix into the setup scripts under `scripts/system/` so a rebuilt
  server gets it too.

**Done when:** a hard power cycle brings the server back with DNS answering on
`SERVER_IP:53` and no manual steps. Test by rebooting and running
`dig @SERVER_IP google.com` shortly after boot.
