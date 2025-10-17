# Troubleshooting Guide

Common issues and solutions for the Home Server Stack.

## Alert Reference

Quick lookup for Prometheus/Alertmanager alerts. When an alert fires, find it below for immediate resolution steps.

| Alert Name | Severity | Quick Fix | Details |
|------------|----------|-----------|---------|
| **ServiceDown** | Critical | `docker compose restart <service>` | [↓](#servicedown-alert) |
| **AdGuardDown** | Critical | `docker compose restart adguard` | [↓](#adguarddown-alert) |
| **N8nDown** | Critical | `docker compose restart n8n` | [↓](#n8ndown-alert) |
| **WireGuardDown** | Critical | `docker compose restart wireguard` | [↓](#wireguarddown-alert) |
| **HighCPUUsage** | Critical | Identify process with `docker stats` | [↓](#highcpuusage-alert) |
| **HighMemoryUsage** | Critical | Restart heavy containers | [↓](#highmemoryusage-alert) |
| **DiskSpaceLow** | Critical | `docker system prune -a` | [↓](#diskspacelow-alert) |
| **ContainerDown** | Critical | `docker compose restart <service>` | See service-specific sections |
| **ContainerHighCPU** | Warning | Check container logs | [↓](#performance-issues) |
| **ContainerHighMemory** | Warning | Review memory limits | [↓](#performance-issues) |
| **HighDiskIOWait** | Warning | Check with `iostat -x 5 3` | [↓](#slow-disk-io) |
| **SystemLoadHigh** | Warning | Identify bottleneck (CPU/Memory/I/O) | [↓](#performance-issues) |

### Critical Alert Procedures

#### ServiceDown Alert
**Trigger:** Service endpoint not responding for 30+ seconds

```bash
# 1. Identify which service
docker compose ps

# 2. Restart the service
docker compose restart <service_name>

# 3. Check logs if restart fails
docker logs <container_name> --tail 100
```

#### AdGuardDown Alert
**Trigger:** AdGuard DNS not responding for 1+ minute
**Impact:** Network DNS resolution fails for all clients

```bash
# Quick fix
docker compose restart adguard

# Test DNS after restart
dig @localhost google.com

# If failing: Check port 53 conflict
sudo lsof -i :53
```

See [AdGuard Home](#adguard-home) section for detailed troubleshooting.

#### N8nDown Alert
**Trigger:** n8n not responding for 2+ minutes
**Impact:** All automated workflows stop

```bash
# Quick fix
docker compose restart n8n

# Wait for startup, then test
sleep 30
curl -k https://localhost:5678/healthz

# If failing: Check SSL certificates and database
ls -la ssl/server.* data/n8n/database.sqlite
```

See [n8n](#n8n) section for detailed troubleshooting.

#### WireGuardDown Alert
**Trigger:** WireGuard VPN not responding for 2+ minutes
**Impact:** Remote VPN access unavailable

```bash
# Quick fix
docker compose restart wireguard

# Check logs
docker logs wireguard --tail 50

# Verify container is healthy
docker ps | grep wireguard
```

See [WireGuard](#wireguard) section for detailed troubleshooting.

#### HighCPUUsage Alert
**Trigger:** System CPU >85% for 5+ minutes

```bash
# Identify top consumers
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}" | sort -k2 -hr

# Check for runaway processes
top -b -n 1 | head -20

# Restart heavy container if needed
docker compose restart <service>
```

#### HighMemoryUsage Alert
**Trigger:** System memory >90% for 3+ minutes
**Warning:** Risk of OOM killer

```bash
# Check memory state
free -h

# Identify memory hogs
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k2 -hr

# Quick mitigation (drops caches)
sudo sync && sudo sysctl -w vm.drop_caches=3

# Restart heavy containers
docker compose restart <service>
```

#### DiskSpaceLow Alert
**Trigger:** Root filesystem >90% for 5+ minutes

```bash
# Quick cleanup
docker system prune -a --volumes -f

# Check space freed
df -h /

# If still low, identify large directories
sudo du -h / --max-depth=1 | sort -hr | head -10

# Clean Docker logs if needed
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

---

## General Diagnostics

### Quick Health Check

```bash
# Check all services status
docker compose ps

# Check for errors in logs
docker compose logs | grep -i error

# Check Docker daemon
sudo systemctl status docker

# Check system resources
df -h  # Disk space
free -h  # Memory
uptime  # System load
```

## Service-Specific Issues

### AdGuard Home

#### Issue: Port 53 Already in Use

**Symptoms:**
- AdGuard fails to start
- Error: "address already in use"

**Cause:** systemd-resolved or another DNS service using port 53

**Solution:**
```bash
# Check what's using port 53
sudo netstat -tlnp | grep :53

# Option 1: Disable systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl stop systemd-resolved

# Remove symlink and create resolv.conf
sudo rm /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Option 2: Change AdGuard port in docker-compose.yml
# Edit: "53:53" -> "5353:53"

# Restart AdGuard
docker compose up -d adguard
```

#### Issue: Cannot Access Web Interface

**Symptoms:**
- `http://SERVER_IP:80` not loading
- Browser shows "Connection refused"

**Diagnosis:**
```bash
# Check if container is running
docker compose ps adguard

# Check logs
docker compose logs adguard

# Check port binding
sudo netstat -tlnp | grep :80
```

**Solutions:**
```bash
# Restart AdGuard
docker compose restart adguard

# Check firewall
sudo ufw status
sudo ufw allow 80/tcp

# Access via container IP
docker inspect adguard | grep IPAddress
curl http://<CONTAINER_IP>:3000
```

### n8n

#### Issue: SSL Certificate Warnings

**Symptoms:**
- Browser shows "Your connection is not private"
- "NET::ERR_CERT_AUTHORITY_INVALID"

**This is Expected:** Self-signed certificates trigger warnings.

**Solutions:**
```bash
# Option 1: Accept the warning (development)
# Click "Advanced" -> "Proceed to site (unsafe)"

# Option 2: Install Let's Encrypt (production)
# See: security-tickets/04-tls-certificate-monitoring.md

# Option 3: Disable HTTPS (not recommended)
# Edit .env: N8N_PROTOCOL=http
# Remove SSL mount from docker-compose.yml
docker compose up -d --force-recreate n8n
```

#### Issue: Cannot Login to n8n

**Symptoms:**
- "Invalid credentials" error
- Repeated login failures

**Diagnosis:**
```bash
# Check credentials in .env
cat .env | grep N8N

# Check n8n logs
docker compose logs n8n | tail -50
```

**Solutions:**
```bash
# Reset password in .env
nano .env
# Update N8N_PASSWORD

# Recreate n8n container
docker compose up -d --force-recreate n8n

# Clear browser cache/cookies
# Try incognito/private browsing mode
```

#### Issue: n8n Workflows Not Executing

**Symptoms:**
- Workflows don't trigger
- Webhooks not responding

**Diagnosis:**
```bash
# Check n8n is running
docker compose ps n8n

# Check workflow execution logs
docker compose logs n8n | grep "Workflow"

# Test webhook endpoint
curl -X POST https://SERVER_IP:5678/webhook/test
```

**Solutions:**
```bash
# Check n8n base URL
cat .env | grep N8N_EDITOR_BASE_URL

# Restart n8n
docker compose restart n8n

# Check for execution timeout
# In .env: EXECUTIONS_TIMEOUT=1800

# Review n8n execution log
docker exec n8n cat /home/node/.n8n/n8n.log
```

### WireGuard

#### Issue: Cannot Connect to VPN

**Symptoms:**
- WireGuard client shows "Handshake failed"
- Cannot reach internal services via VPN

**Diagnosis:**
```bash
# Check WireGuard container
docker compose ps wireguard

# Check logs
docker compose logs wireguard

# Check if port is open
sudo netstat -ulnp | grep 51820
```

**Solutions:**
```bash
# Restart WireGuard
docker compose restart wireguard

# Check router port forwarding
# Ensure UDP port 51820 is forwarded to SERVER_IP

# Regenerate peer config
docker compose down wireguard
sudo rm -rf ./data/wireguard/*
docker compose up -d wireguard

# Get new config
docker exec wireguard cat /config/peer1/peer1.conf
```

#### Issue: VPN Connected but Cannot Access Services

**Symptoms:**
- WireGuard shows "Connected"
- Cannot ping internal IPs

**Diagnosis:**
```bash
# Check allowed IPs in client config
# Should include: 192.168.1.0/24,10.13.13.0/24

# Check routing
ip route show

# Test from VPN client
ping 192.168.1.100
```

**Solutions:**
```bash
# Update WireGuard environment
# In .env: WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24

# Recreate WireGuard
docker compose up -d --force-recreate wireguard

# Check DNS (should be AdGuard IP)
# In .env: PEERDNS=192.168.1.100

# Test DNS from VPN client
nslookup google.com
```

## Docker Issues

### Issue: "Cannot connect to Docker daemon"

**Symptoms:**
- All docker commands fail
- Error: "Cannot connect to the Docker daemon"

**Solution:**
```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker on boot
sudo systemctl enable docker

# Check status
sudo systemctl status docker

# If still failing, reinstall
sudo apt remove docker docker-engine docker.io containerd runc
sudo apt update
sudo apt install -y docker.io docker-compose
```

### Issue: Docker Disk Space

**Symptoms:**
- "no space left on device"
- Containers failing to start

**Diagnosis:**
```bash
# Check disk usage
df -h
docker system df
```

**Solutions:**
```bash
# Clean up Docker
docker system prune -a

# Remove old images
docker image prune -a

# Remove unused volumes (⚠️ be careful!)
docker volume ls
docker volume rm <volume_name>

# Check large log files
du -sh /var/lib/docker/containers/*/*-json.log

# Add log rotation to docker-compose.yml
# See OPERATIONS.md
```

### Issue: Container Crashes on Start

**Symptoms:**
- Container exits immediately
- Status shows "Exited (1)"

**Diagnosis:**
```bash
# Check logs
docker compose logs <service>

# Check container exit code
docker compose ps <service>

# Try running manually
docker run -it <image> /bin/sh
```

**Solutions:**
```bash
# Check for port conflicts
sudo netstat -tlnp | grep <port>

# Check permissions
ls -la ./data/<service>/

# Recreate container
docker compose rm -f <service>
docker compose up -d <service>

# Check resource limits
docker stats
```

## Network Issues

### Issue: Cannot Access Services from Network

**Symptoms:**
- Services work on server, not from other devices
- Connection timeout from LAN

**Diagnosis:**
```bash
# Check if service is listening on 0.0.0.0
sudo netstat -tlnp | grep <port>

# Check firewall
sudo ufw status

# Test from server
curl http://localhost:<port>
```

**Solutions:**
```bash
# Open firewall ports
sudo ufw allow 80/tcp
sudo ufw allow 5678/tcp
sudo ufw allow 51820/udp

# Check SERVER_IP is correct in .env
cat .env | grep SERVER_IP

# Ensure SERVER_IP binding in docker-compose.yml
# Ports should be: "${SERVER_IP}:80:80"

# Restart services
docker compose up -d
```

### Issue: DNS Resolution Not Working

**Symptoms:**
- Devices using AdGuard cannot resolve domains
- "DNS_PROBE_FINISHED_NXDOMAIN"

**Diagnosis:**
```bash
# Test AdGuard DNS
nslookup google.com SERVER_IP

# Check AdGuard logs
docker compose logs adguard | grep -i error

# Check upstream DNS
docker exec adguard cat /opt/adguardhome/conf/AdGuardHome.yaml | grep upstream
```

**Solutions:**
```bash
# Access AdGuard UI: http://SERVER_IP:80
# Go to Settings > DNS settings
# Add upstream servers: 8.8.8.8, 1.1.1.1

# Restart AdGuard
docker compose restart adguard

# Test DNS from client
nslookup google.com SERVER_IP
```

## Performance Issues

### Issue: High CPU Usage

**Diagnosis:**
```bash
# Check container CPU usage
docker stats

# Check which service
top
```

**Solutions:**
```bash
# Add CPU limits in docker-compose.yml
# See OPERATIONS.md

# Stop unused services
docker compose stop <service>
```

### Issue: High Memory Usage

**Diagnosis:**
```bash
# Check memory
free -h

# Check container memory
docker stats

# Check largest memory users
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k 2 -h
```

**Solutions:**
```bash
# Add memory limits
# See OPERATIONS.md

# Add swap
sudo fallocate -l 8G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Issue: Slow Disk I/O

**Diagnosis:**
```bash
# Check disk I/O
iotop

# Check disk usage
df -h
du -sh ./data/*
```

**Solutions:**
```bash
# Use SSD instead of HDD
# Move ./data to faster storage

# Clean up old data
docker system prune -a

# Configure log rotation
# See OPERATIONS.md

# Check for disk errors
sudo dmesg | grep -i error
```

## Domain Access Issues

### DNS Not Resolving

**Symptom:** `nslookup servicename.home.local` fails or returns wrong IP

**Solutions:**
```bash
# 1. Verify AdGuard DNS rewrites
cat data/adguard/conf/AdGuardHome.yaml | grep -A 5 rewrites

# 2. Verify client DNS settings
# Check your device is using SERVER_IP as DNS

# 3. Flush DNS cache on client
# Windows: ipconfig /flushdns
# macOS: sudo dscacheutil -flushcache
# Linux: sudo systemd-resolve --flush-caches

# 4. Test DNS directly
dig @SERVER_IP servicename.home.local +short
# Should return: SERVER_IP
```

### SSL Certificate Issues

**Symptom:** Browser blocks access, can't proceed past certificate warning

**Solutions:**

**Chrome "NET::ERR_CERT_INVALID" (can't proceed):**
- Type: `thisisunsafe` (no spaces) while on the error page
- Or use Firefox/Safari which allow easier bypassing

**Add certificate exception:**
1. Click certificate error details
2. Export certificate
3. Add to system trust store (advanced users only)

**Use mkcert for trusted local certificates (recommended for heavy use):**
```bash
# Install mkcert
# macOS: brew install mkcert
# Linux: apt install mkcert / yum install mkcert

# Create local CA
mkcert -install

# Generate certificates
mkcert -cert-file ssl/server.crt -key-file ssl/server.key "*.home.local" localhost 127.0.0.1

# Configure Traefik to use these certificates (see CONFIGURATION.md)
```

### Service Not Accessible via Domain

**Symptom:** `https://servicename.home.local` returns 404 or 502

**Solutions:**
```bash
# 1. Check service is running
docker ps | grep servicename

# 2. Check Traefik discovered the service
docker logs traefik | grep servicename

# 3. Verify Traefik labels
docker inspect servicename | grep -A 20 Labels

# 4. Check service port matches label
docker port servicename

# 5. Test direct container access
docker exec traefik wget -qO- http://servicename:PORT

# 6. Check Traefik routers
curl http://localhost:8080/api/http/routers | jq
```

## Traefik Issues

### 502 Bad Gateway

**Symptom:** Service returns 502 Bad Gateway error

**Causes & Solutions:**

1. **Service not running:**
   ```bash
   docker ps | grep servicename
   docker compose up -d servicename
   ```

2. **Wrong port in Traefik label:**
   ```bash
   # Check service's internal port
   docker port servicename

   # Verify label matches
   docker inspect servicename | grep "loadbalancer.server.port"
   ```

3. **Service not on same network:**
   ```bash
   # Check service is on homeserver network
   docker inspect servicename | grep -A 10 Networks
   ```

4. **Service not ready:**
   ```bash
   # Check health check
   docker inspect servicename | grep -A 10 Health

   # Give service more time to start
   docker logs servicename
   ```

### Traefik Not Discovering Service

**Symptom:** Service doesn't appear in Traefik dashboard

**Solutions:**
```bash
# 1. Verify traefik.enable=true label
docker inspect servicename | grep "traefik.enable"

# 2. Verify service on homeserver network
docker inspect servicename | grep -A 10 Networks

# 3. Restart service to trigger discovery
docker compose up -d servicename

# 4. Check Traefik logs for errors
docker logs traefik | grep -i error

# 5. Verify Docker socket mounted
docker inspect traefik | grep docker.sock
```

### Redirect Loop

**Symptom:** Browser shows "Too many redirects" error

**Solutions:**
```bash
# Check for conflicting redirect configurations
# Remove duplicate redirect middleware
# Ensure service doesn't force its own HTTPS redirect

# Check Traefik labels for duplicate redirects
docker inspect servicename | grep redirect
```

## Common Error Messages

### "bind: address already in use"

**Meaning:** Another service is using the required port

**Solution:**
```bash
# Find what's using the port
sudo netstat -tlnp | grep :<port>

# Stop conflicting service or change port in docker-compose.yml
```

### "failed to register layer"

**Meaning:** Docker storage driver issue

**Solution:**
```bash
docker system prune -a
sudo systemctl restart docker
docker compose pull
docker compose up -d
```

### "OCI runtime create failed"

**Meaning:** Docker container runtime error

**Solution:**
```bash
# Check Docker version
docker --version

# Update Docker
sudo apt update && sudo apt install docker.io

# Restart Docker
sudo systemctl restart docker
```

## Getting Help

### Collect Diagnostic Information

```bash
# System info
uname -a
cat /etc/os-release

# Docker info
docker --version
docker compose version
docker info

# Service status
docker compose ps
docker compose logs --tail=100

# Resource usage
free -h
df -h
docker stats --no-stream
```

### Report an Issue

1. Check [Known Issues](KNOWN_ISSUES.md)
2. Search [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
3. Create new issue with:
   - Description of problem
   - Steps to reproduce
   - Output from diagnostic commands above
   - Relevant log snippets

## Additional Resources

- [Operations Guide](OPERATIONS.md) - Service management
- [Setup Guide](SETUP.md) - Installation help
- [Requirements](REQUIREMENTS.md) - System requirements
- [Known Issues](KNOWN_ISSUES.md) - Known bugs
