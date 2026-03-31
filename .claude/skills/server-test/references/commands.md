# Server Diagnostic Commands

All commands run via SSH: `ssh ${SERVER_USER}@${SERVER_HOST} "cd ~/home-server-stack && <command>"`

## Logs

```bash
# Specific service (last 50 lines)
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml logs --tail=50 <service>
# All services (last 30 lines)
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml logs --tail=30
```

## Service state

```bash
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml ps
docker ps -a  # shows exit codes and restart counts
```

## WireGuard (system service, not Docker)

```bash
systemctl is-active wg-quick@wg0
sudo wg show
```

## SSL certificates

```bash
ls -la ~/home-server-stack/data/traefik/certs/
sudo certbot certificates 2>/dev/null | grep -A5 "Certificate Name"
```

## Disk / system

```bash
df -h ~
free -h
```

## Restart a container

```bash
docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml restart <service>
```

## Re-apply config changes

```bash
make start  # idempotent — safe to re-run
```
