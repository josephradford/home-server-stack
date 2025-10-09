# Troubleshooting Guide

Common issues and solutions for the Home Server Stack.

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

### Ollama

#### Issue: Models Not Downloading

**Symptoms:**
- `ollama-setup` container exits with error
- Models not appearing in `ollama list`

**Diagnosis:**
```bash
# Check ollama-setup logs
docker compose logs ollama-setup

# Check Ollama service
docker compose logs ollama

# Check disk space
df -h
```

**Solutions:**
```bash
# Ensure sufficient disk space (20-50 GB needed)
df -h ./data/ollama

# Restart download
docker compose restart ollama-setup

# Manual download
docker exec ollama ollama pull deepseek-coder:6.7b
docker exec ollama ollama pull llama3.2:3b

# Check download progress
docker exec ollama ollama ps
```

#### Issue: Ollama Out of Memory

**Symptoms:**
- Ollama crashes during inference
- Error: "failed to allocate memory"

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check Ollama memory settings
cat .env | grep OLLAMA
```

**Solutions:**
```bash
# Use smaller models
docker exec ollama ollama pull llama3.2:1b

# Reduce parallel requests
# In .env: OLLAMA_NUM_PARALLEL=1
# In .env: OLLAMA_MAX_LOADED_MODELS=1

# Add swap space
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Restart Ollama
docker compose up -d --force-recreate ollama
```

#### Issue: Ollama Slow Inference

**Symptoms:**
- Responses take minutes instead of seconds
- High CPU usage

**Diagnosis:**
```bash
# Check CPU usage
top

# Check model size
docker exec ollama ollama list
```

**Solutions:**
```bash
# Use quantized models (smaller, faster)
docker exec ollama ollama pull deepseek-coder:6.7b  # Already quantized

# Reduce concurrent requests
# In .env: OLLAMA_NUM_PARALLEL=1

# Increase timeout
# In .env: OLLAMA_LOAD_TIMEOUT=1200

# Check CPU features (AVX support helps)
lscpu | grep -i avx
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

### Habitica

#### Issue: MongoDB "Server selection timed out"

**Symptoms:**
- habitica-server fails to start or logs timeout errors
- Error: "MongooseServerSelectionError: Server selection timed out after 30000 ms"
- MongoDB logs show "REMOVED" state or "NodeNotFound" errors

**Cause:** MongoDB replica set initialized with container ID instead of resolvable hostname

**Diagnosis:**
```bash
# Check MongoDB logs for replica set errors
docker compose logs habitica-mongo | grep -i "replica\|removed\|nodenotfound"

# Check if replica set is properly configured
docker exec habitica-mongo mongosh --eval "rs.status()"
```

**Solution:**
```bash
# Stop all Habitica services
docker compose stop habitica-client habitica-server habitica-mongo

# Remove corrupted MongoDB data
rm -rf ./data/habitica/db/* ./data/habitica/dbconf/*

# Restart services (healthcheck will reinitialize replica set correctly)
docker compose up -d habitica-mongo habitica-server habitica-client

# Verify MongoDB is in PRIMARY state
docker exec habitica-mongo mongosh --eval "rs.status()"
```

**Prevention:** The docker-compose.habitica.yml healthcheck now explicitly specifies `habitica-mongo:27017` as the replica set hostname.

#### Issue: habitica-client "lookup server" DNS errors

**Symptoms:**
- habitica-client logs show: "dial tcp: lookup server on 127.0.0.11:53: server misbehaving"
- Web UI returns 502 Bad Gateway
- Caddy cannot reach habitica-server

**Cause:** habitica-client's Caddyfile expects backend at hostname `server`, but service is named `habitica-server`

**Diagnosis:**
```bash
# Check client logs for DNS errors
docker compose logs habitica-client | grep "lookup server"

# Verify network alias exists
docker inspect habitica-server | grep -A 5 "Aliases"
```

**Solution:**
This is fixed in docker-compose.habitica.yml with a network alias:
```yaml
habitica-server:
  networks:
    homeserver:
      aliases:
        - server  # Allows client to resolve 'server' hostname
```

If issue persists, restart the services:
```bash
docker compose restart habitica-server habitica-client
```

#### Issue: Habitica Web UI Not Loading

**Symptoms:**
- `http://SERVER_IP:8080` not loading
- Browser shows connection error

**Diagnosis:**
```bash
# Check all Habitica containers
docker compose ps | grep habitica

# Check client logs
docker compose logs habitica-client

# Check server health
docker compose exec habitica-server wget -q -O- http://localhost:3000/api/v3/status
```

**Solutions:**
```bash
# Restart services in dependency order
docker compose restart habitica-mongo habitica-server habitica-client

# Check MongoDB is running and healthy
docker compose ps habitica-mongo

# Verify network connectivity
docker compose exec habitica-client ping -c 3 server
```

### HortusFox

#### Issue: "Unknown character set" Database Error

**Symptoms:**
- Error: `SQLSTATE[HY000] [2019] Unknown character set`
- Application fails to initialize database
- Error in `/var/www/html/vendor/danielbrendel/asatru-php-framework/src/database.php`

**Cause:** Missing `DB_CHARSET` environment variable in docker-compose.yml

**Diagnosis:**
```bash
# Check HortusFox logs for charset error
docker compose logs hortusfox | grep -i "charset\|character set"

# Check environment variables
docker compose exec hortusfox env | grep DB_CHARSET
```

**Solution:**
This is fixed in docker-compose.yml with:
```yaml
hortusfox:
  environment:
    - DB_CHARSET=utf8mb4
```

If issue persists:
```bash
# Recreate containers with updated config
docker compose up -d --force-recreate hortusfox

# If database is corrupted, reset it
docker compose stop hortusfox hortusfox-db
rm -rf ./data/hortusfox/db/*
docker compose up -d hortusfox-db hortusfox
```

#### Issue: Cannot Login to HortusFox

**Symptoms:**
- Login fails with incorrect credentials
- Admin account not created

**Diagnosis:**
```bash
# Check admin credentials in .env
cat .env | grep HORTUSFOX_ADMIN

# Check HortusFox logs for initialization
docker compose logs hortusfox | grep -i "admin\|user"
```

**Solutions:**
```bash
# Verify credentials in .env
nano .env
# Update HORTUSFOX_ADMIN_EMAIL and HORTUSFOX_ADMIN_PASSWORD

# Recreate container to reset admin account
docker compose up -d --force-recreate hortusfox

# If database already exists, admin won't be recreated
# Option: Reset database (⚠️ deletes all data)
docker compose stop hortusfox hortusfox-db
rm -rf ./data/hortusfox/db/*
docker compose up -d hortusfox-db hortusfox
```

#### Issue: HortusFox Web UI Not Loading

**Symptoms:**
- `http://SERVER_IP:8181` not loading
- Browser shows connection error or 502 Bad Gateway

**Diagnosis:**
```bash
# Check both containers
docker compose ps | grep hortusfox

# Check HortusFox logs
docker compose logs hortusfox

# Check MariaDB health
docker compose logs hortusfox-db
```

**Solutions:**
```bash
# Restart services in dependency order
docker compose restart hortusfox-db hortusfox

# Verify MariaDB is healthy
docker compose exec hortusfox-db healthcheck.sh --connect

# Check network connectivity
docker compose exec hortusfox ping -c 3 hortusfox-db

# Test database connection
docker compose exec hortusfox-db mysql -u hortusfox -p${HORTUSFOX_DB_PASSWORD} -e "SHOW DATABASES;"
```

#### Issue: Images Not Uploading

**Symptoms:**
- Plant images fail to upload
- Permission denied errors in logs

**Diagnosis:**
```bash
# Check volume permissions
ls -la ./data/hortusfox/images/

# Check logs for permission errors
docker compose logs hortusfox | grep -i "permission\|denied"

# Check disk space
df -h ./data/hortusfox/
```

**Solutions:**
```bash
# Fix permissions
sudo chown -R 82:82 ./data/hortusfox/images/
sudo chmod -R 755 ./data/hortusfox/images/

# Ensure sufficient disk space
du -sh ./data/hortusfox/*

# Restart HortusFox
docker compose restart hortusfox
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
sudo ufw allow 11434/tcp
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
# Limit Ollama parallel requests
# In .env: OLLAMA_NUM_PARALLEL=1

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
# Use smaller AI models
docker exec ollama ollama pull llama3.2:1b

# Limit loaded models
# In .env: OLLAMA_MAX_LOADED_MODELS=1

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
- [RUNBOOK.md](RUNBOOK.md) - Alert troubleshooting
