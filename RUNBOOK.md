# Alert Response Runbook

This runbook provides step-by-step troubleshooting and resolution procedures for all monitoring alerts. Follow the procedures in order for fastest resolution.

## Quick Reference

| Alert Name | Severity | Typical Cause | Quick Fix | Full Procedure |
|------------|----------|---------------|-----------|----------------|
| ServiceDown | Critical | Service crashed | Restart container | [Link](#servicedown) |
| PrometheusTargetDown | Critical | Monitoring failure | Restart monitoring stack | [Link](#prometheustargetdown) |
| AdGuardDown | Critical | DNS service crashed | Restart AdGuard | [Link](#adguarddown) |
| N8nDown | Critical | Automation service crashed | Restart n8n | [Link](#n8ndown) |
| OllamaDown | Critical | AI service crashed | Restart Ollama | [Link](#ollamadown) |
| HighCPUUsage | Critical | Resource exhaustion | Identify and kill process | [Link](#highcpuusage) |
| HighMemoryUsage | Critical | Memory exhaustion | Restart heavy containers | [Link](#highmemoryusage) |
| DiskSpaceLow | Critical | Disk full | Clean Docker resources | [Link](#diskspacelow) |
| ContainerDown | Critical | Container stopped | Restart container | [Link](#containerdown) |
| ContainerHighCPU | Warning | Container overload | Review container activity | [Link](#containerhighcpu) |
| ContainerHighMemory | Warning | Container memory pressure | Increase limits or optimize | [Link](#containerhighmemory) |
| ContainerRestartLoop | Warning | Config/bug issue | Fix configuration | [Link](#containerrestartloop) |
| HighDiskIOWait | Warning | Disk bottleneck | Check disk health | [Link](#highdiskiowait) |
| HighNetworkTraffic | Warning | Network abuse/transfer | Identify source | [Link](#highnetworktraffic) |
| SystemLoadHigh | Warning | System overload | Identify bottleneck | [Link](#systemloadhigh) |

---

## Critical Alerts

### ServiceDown

**Alert**: Service endpoint not responding to health checks for 30+ seconds

#### Immediate Actions (5 minutes)

1. **Identify the affected service**:
   ```bash
   # Check which service is down from the alert
   curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="ServiceDown")'
   ```

2. **Check container status**:
   ```bash
   # For main services
   docker ps -a | grep -E "adguard|n8n|ollama"

   # For monitoring services
   docker compose -f docker-compose.monitoring.yml ps
   ```

3. **Quick restart attempt**:
   ```bash
   # For main services
   docker compose restart <service_name>

   # For monitoring services
   docker compose -f docker-compose.monitoring.yml restart <service_name>
   ```

4. **Verify service recovery**:
   ```bash
   # Wait 30 seconds, then check Prometheus targets
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health=="down")'
   ```

#### Detailed Troubleshooting (if quick restart fails)

1. **Review recent logs**:
   ```bash
   docker logs <container_name> --tail 200 --timestamps
   ```

2. **Check for common issues**:
   ```bash
   # Port conflicts
   netstat -tlnp | grep <service_port>

   # Resource limits
   docker stats <container_name> --no-stream

   # Disk space
   df -h

   # Memory available
   free -h
   ```

3. **Inspect container state**:
   ```bash
   docker inspect <container_name> | jq '.[0].State'
   ```

4. **Check container exit code**:
   - Exit code 0: Clean shutdown (likely manual)
   - Exit code 137: OOM killed (memory exhaustion)
   - Exit code 139: Segmentation fault (application bug)
   - Exit code 143: SIGTERM received (manual stop or restart)

5. **Resolution based on findings**:
   - **OOM killed**: Increase memory limits or reduce container load
   - **Port conflict**: Identify and stop conflicting process
   - **Configuration error**: Review and fix config, then restart
   - **Application bug**: Check application logs, consider rollback

#### Prevention

- Set up health checks for all services
- Configure automatic restart policies
- Monitor resource trends to prevent exhaustion
- Regular log review for warnings

---

### PrometheusTargetDown

**Alert**: Core monitoring component (Prometheus, node-exporter, cAdvisor) down for 1+ minute

**CRITICAL**: This affects all monitoring - blind to system state until resolved.

#### Immediate Actions (3 minutes)

1. **Identify which monitoring component is down**:
   ```bash
   curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health=="down") | {job: .labels.job, instance: .labels.instance}'
   ```

2. **Check monitoring stack status**:
   ```bash
   docker compose -f docker-compose.monitoring.yml ps
   ```

3. **Restart affected component**:
   ```bash
   # Specific component
   docker compose -f docker-compose.monitoring.yml restart <component>

   # Or entire monitoring stack if multiple failures
   docker compose -f docker-compose.monitoring.yml restart
   ```

4. **Verify targets are up**:
   ```bash
   # Wait 1 minute for scrapes to complete
   sleep 60
   curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health=="down")'
   ```

#### Detailed Troubleshooting

1. **Check component-specific logs**:
   ```bash
   # Prometheus
   docker logs prometheus --tail 100

   # node-exporter
   docker logs node-exporter --tail 100

   # cAdvisor
   docker logs cadvisor --tail 100
   ```

2. **Verify network connectivity**:
   ```bash
   # Test scrape endpoints
   curl http://localhost:9090/-/healthy  # Prometheus
   curl http://localhost:9100/metrics    # node-exporter
   curl http://localhost:8080/healthz    # cAdvisor
   ```

3. **Check configuration files**:
   ```bash
   # Validate Prometheus config
   docker exec prometheus promtool check config /etc/prometheus/prometheus.yml

   # Validate alert rules
   docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml
   ```

4. **Check for resource issues**:
   ```bash
   docker stats prometheus node-exporter cadvisor --no-stream
   ```

#### Resolution

- **Config syntax error**: Fix configuration and reload/restart
- **Network issue**: Check Docker network and port bindings
- **Resource exhaustion**: Increase limits or reduce retention period
- **Volume mount issue**: Verify volume paths and permissions

#### Prevention

- Always validate config before applying changes
- Monitor monitoring stack resource usage
- Set up external monitoring for the monitoring stack itself
- Regular backups of Prometheus data and configs

---

### AdGuardDown

**Alert**: AdGuard DNS service not responding for 1+ minute

**Impact**: Network DNS resolution fails for all clients using this server.

#### Immediate Actions (3 minutes)

1. **Verify alert**:
   ```bash
   curl http://localhost:3000  # Should timeout or connection refused if down
   ```

2. **Check container status**:
   ```bash
   docker ps -a | grep adguard
   ```

3. **Quick restart**:
   ```bash
   docker compose restart adguard
   ```

4. **Test DNS resolution**:
   ```bash
   dig @localhost google.com
   # Should return ANSWER section with IP addresses
   ```

#### Detailed Troubleshooting

1. **Review logs for errors**:
   ```bash
   docker logs adguard-home --tail 200 | grep -i error
   ```

2. **Check port bindings**:
   ```bash
   # DNS ports (53/tcp, 53/udp), web UI (80/tcp, 3000/tcp)
   netstat -tlnp | grep :53
   netstat -ulnp | grep :53
   netstat -tlnp | grep -E ":(80|3000)"
   ```

3. **Verify configuration files**:
   ```bash
   ls -la data/adguard/conf/
   cat data/adguard/conf/AdGuardHome.yaml | head -50
   ```

4. **Check volume permissions**:
   ```bash
   ls -la data/adguard/work/
   ls -la data/adguard/conf/
   ```

#### Common Issues and Resolutions

1. **Port 53 already in use**:
   ```bash
   # Identify process using port 53
   sudo lsof -i :53

   # Stop systemd-resolved if conflicting
   sudo systemctl stop systemd-resolved
   sudo systemctl disable systemd-resolved
   ```

2. **Configuration corruption**:
   ```bash
   # Restore from backup if available
   cp data/adguard/conf/AdGuardHome.yaml.backup data/adguard/conf/AdGuardHome.yaml
   docker compose restart adguard
   ```

3. **Disk full preventing writes**:
   ```bash
   df -h data/adguard/
   # See DiskSpaceLow procedure
   ```

#### Prevention

- Regular backups of AdGuard configuration
- Monitor query volume for unusual patterns
- Set up secondary DNS server for redundancy
- Configure upstream DNS servers for failover

---

### N8nDown

**Alert**: n8n automation service not responding for 2+ minutes

**Impact**: All automated workflows stop executing.

#### Immediate Actions (5 minutes)

1. **Check container status**:
   ```bash
   docker ps -a | grep n8n
   ```

2. **Quick restart**:
   ```bash
   docker compose restart n8n
   ```

3. **Wait for startup and test access**:
   ```bash
   sleep 30
   curl -k https://${SERVER_IP}:5678/healthz
   ```

4. **Verify workflows resume**:
   - Access n8n web UI: `https://${SERVER_IP}:5678`
   - Check active executions

#### Detailed Troubleshooting

1. **Review startup logs**:
   ```bash
   docker logs n8n --tail 200 --follow
   ```

2. **Check for common startup issues**:
   ```bash
   # Database file access
   ls -la data/n8n/database.sqlite

   # SSL certificate issues
   ls -la ssl/server.key ssl/server.crt

   # Environment variables
   docker exec n8n env | grep N8N_
   ```

3. **Check resource usage**:
   ```bash
   docker stats n8n --no-stream
   ```

4. **Verify volume mounts**:
   ```bash
   docker inspect n8n | jq '.[0].Mounts'
   ```

#### Common Issues and Resolutions

1. **Database locked**:
   ```bash
   # Check for zombie processes
   lsof data/n8n/database.sqlite

   # If locked, stop container and remove lock
   docker compose stop n8n
   rm -f data/n8n/database.sqlite-shm data/n8n/database.sqlite-wal
   docker compose start n8n
   ```

2. **SSL certificate issues**:
   ```bash
   # Verify certificate validity
   openssl x509 -in ssl/server.crt -noout -dates

   # Check certificate matches key
   openssl x509 -noout -modulus -in ssl/server.crt | openssl md5
   openssl rsa -noout -modulus -in ssl/server.key | openssl md5
   # Should match
   ```

3. **Permission issues**:
   ```bash
   # n8n runs as user 1000:1000
   sudo chown -R 1000:1000 data/n8n
   sudo chmod -R 755 data/n8n
   ```

4. **Memory exhaustion**:
   ```bash
   # Check for OOM in logs
   docker logs n8n 2>&1 | grep -i "out of memory"

   # Add memory limit if needed
   # Edit docker-compose.yml to add:
   # mem_limit: 2g
   # mem_reservation: 1g
   ```

#### Prevention

- Regular database backups (database.sqlite)
- Monitor workflow execution duration and resource usage
- Set execution timeout limits
- Review and optimize resource-intensive workflows
- Keep SSL certificates renewed

---

### OllamaDown

**Alert**: Ollama AI service not responding for 2+ minutes

**Impact**: AI-powered workflows and applications fail.

#### Immediate Actions (5 minutes)

1. **Check container status**:
   ```bash
   docker ps -a | grep ollama
   ```

2. **Quick restart**:
   ```bash
   docker compose restart ollama
   ```

3. **Test API endpoint**:
   ```bash
   sleep 10
   curl http://${SERVER_IP}:11434/api/version
   # Should return version JSON
   ```

4. **List loaded models**:
   ```bash
   docker exec ollama ollama list
   ```

#### Detailed Troubleshooting

1. **Review logs**:
   ```bash
   docker logs ollama --tail 200
   ```

2. **Check disk space** (models are 4-7GB each):
   ```bash
   du -sh data/ollama/
   df -h data/
   ```

3. **Check memory usage**:
   ```bash
   docker stats ollama --no-stream
   # Model loading can use 4-8GB memory
   ```

4. **Test model inference**:
   ```bash
   curl http://${SERVER_IP}:11434/api/generate -d '{
     "model": "llama3.2:3b",
     "prompt": "test",
     "stream": false
   }'
   ```

#### Common Issues and Resolutions

1. **Model file corruption**:
   ```bash
   # List models
   docker exec ollama ollama list

   # Remove and re-pull corrupted model
   docker exec ollama ollama rm <model_name>
   docker exec ollama ollama pull <model_name>
   ```

2. **Insufficient disk space**:
   ```bash
   # Remove unused models
   docker exec ollama ollama list
   docker exec ollama ollama rm <unused_model>
   ```

3. **Memory exhaustion during model load**:
   ```bash
   # Check parallel loading settings
   docker exec ollama env | grep OLLAMA_MAX_LOADED_MODELS

   # Reduce concurrent models in .env:
   # OLLAMA_MAX_LOADED_MODELS=1
   ```

4. **API timeout during long inference**:
   ```bash
   # Check timeout settings
   docker exec ollama env | grep OLLAMA_LOAD_TIMEOUT

   # Increase if needed in .env:
   # OLLAMA_LOAD_TIMEOUT=900
   ```

#### Prevention

- Monitor disk space trends
- Limit number of loaded models concurrently
- Set appropriate memory limits
- Regular cleanup of unused models
- Monitor inference request durations

---

### HighCPUUsage

**Alert**: System CPU usage above 85% for 5+ minutes

#### Immediate Actions (5 minutes)

1. **Identify top CPU consumers**:
   ```bash
   # Container level
   docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}" | sort -k2 -hr

   # Process level on host
   top -b -n 1 | head -20
   ```

2. **Check current CPU usage**:
   ```bash
   mpstat 1 5  # 5 samples, 1 second apart
   ```

3. **Determine if load is legitimate**:
   - Ollama: Check for active inference
   - n8n: Check for running workflows
   - System: Check for updates/backups

#### Detailed Troubleshooting

1. **For Ollama high CPU**:
   ```bash
   # Check active models and inferences
   docker exec ollama ollama ps

   # Review recent API requests
   docker logs ollama --tail 50
   ```

2. **For n8n high CPU**:
   ```bash
   # Access n8n UI and check:
   # - Active executions
   # - Workflow complexity
   # - Data volume being processed
   ```

3. **For unknown process**:
   ```bash
   # Detailed process info
   ps aux --sort=-%cpu | head -20

   # Check for malware indicators
   ps aux | grep -iE "crypto|miner|xmrig"
   ```

#### Resolution

1. **If legitimate workload**:
   - Let it complete
   - Consider resource optimization
   - Add CPU limits to prevent resource monopolization

2. **If runaway process**:
   ```bash
   # Kill specific process
   kill <PID>

   # Or restart container
   docker compose restart <service>
   ```

3. **If cryptocurrency miner detected**:
   ```bash
   # Kill process immediately
   kill -9 <PID>

   # Investigate compromise
   # - Check for unauthorized SSH access
   # - Review Docker socket exposure
   # - Scan for malware
   # - Review firewall rules
   ```

4. **Add CPU limits** (if needed):
   ```yaml
   # In docker-compose.yml
   services:
     service_name:
       cpus: '2.0'  # Limit to 2 CPU cores
   ```

#### Prevention

- Set CPU limits on containers
- Monitor CPU trends to identify patterns
- Optimize resource-intensive workflows
- Regular security audits
- Restrict SSH access

---

### HighMemoryUsage

**Alert**: System memory usage above 90% for 3+ minutes

**CRITICAL**: Risk of OOM killer terminating processes.

#### Immediate Actions (3 minutes)

1. **Check current memory state**:
   ```bash
   free -h
   ```

2. **Identify memory hogs**:
   ```bash
   docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k2 -hr
   ```

3. **Quick mitigation** (if critical):
   ```bash
   # Drop caches (safe, kernel will repopulate)
   sudo sync && sudo sysctl -w vm.drop_caches=3
   ```

#### Detailed Troubleshooting

1. **For Ollama high memory**:
   ```bash
   # Check loaded models (each uses 4-8GB)
   docker exec ollama ollama ps

   # Unload models if needed
   docker exec ollama ollama stop <model_name>
   ```

2. **Check for memory leaks**:
   ```bash
   # Monitor memory over time
   watch -n 5 'docker stats --no-stream'

   # Look for containers with steadily increasing memory
   ```

3. **Review container memory limits**:
   ```bash
   docker inspect <container> | jq '.[0].HostConfig.Memory'
   ```

#### Resolution

1. **If Ollama causing issue**:
   ```bash
   # Reduce max loaded models in .env
   OLLAMA_MAX_LOADED_MODELS=1

   # Restart Ollama
   docker compose restart ollama
   ```

2. **If memory leak detected**:
   ```bash
   # Restart affected container
   docker compose restart <service>

   # Monitor to confirm leak is resolved
   ```

3. **Add memory limits** (if needed):
   ```yaml
   # In docker-compose.yml
   services:
     service_name:
       mem_limit: 2g
       mem_reservation: 1g
   ```

4. **If system truly needs more memory**:
   - Reduce number of services
   - Add swap space (temporary)
   - Upgrade server RAM

#### Prevention

- Set memory limits on all containers
- Monitor memory trends
- Configure memory reservations
- Regular container restarts for leak-prone services
- Optimize application memory usage

---

### DiskSpaceLow

**Alert**: Root filesystem usage above 90% for 5+ minutes

#### Immediate Actions (10 minutes)

1. **Check current disk usage**:
   ```bash
   df -h /
   ```

2. **Quick cleanup - Docker resources**:
   ```bash
   # Remove unused containers, images, networks, and volumes
   docker system prune -a --volumes -f
   ```

3. **Verify space freed**:
   ```bash
   df -h /
   ```

#### Detailed Troubleshooting

1. **Identify large directories**:
   ```bash
   # Top-level directories
   sudo du -h / --max-depth=1 | sort -hr | head -20

   # Docker-specific
   sudo du -sh /var/lib/docker/*
   ```

2. **Check for specific issues**:
   ```bash
   # Large log files
   sudo du -sh /var/log/*

   # Ollama models
   du -sh data/ollama/

   # n8n database and executions
   du -sh data/n8n/

   # AdGuard logs
   du -sh data/adguard/work/
   ```

3. **List large files**:
   ```bash
   find / -type f -size +1G 2>/dev/null -exec ls -lh {} \;
   ```

#### Resolution

1. **Clean Ollama models**:
   ```bash
   # List all models
   docker exec ollama ollama list

   # Remove unused models (4-7GB each)
   docker exec ollama ollama rm <model_name>
   ```

2. **Clean Docker images and containers**:
   ```bash
   # List all images
   docker images

   # Remove specific unused images
   docker rmi <image_id>

   # Remove dangling images
   docker image prune -f
   ```

3. **Clean logs**:
   ```bash
   # Rotate Docker logs
   sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log

   # Clean AdGuard query logs (if excessive)
   docker exec adguard-home sh -c "truncate -s 0 /opt/adguardhome/work/data/querylog.json*"
   ```

4. **Clean n8n execution data**:
   ```bash
   # Access n8n UI → Settings → Log Streaming → Clear old executions
   # Or manually in database (advanced)
   ```

5. **Expand disk** (if legitimately needed):
   ```bash
   # For VM: Extend disk in hypervisor, then:
   sudo growpart /dev/sda 1
   sudo resize2fs /dev/sda1

   # Verify
   df -h /
   ```

#### Prevention

- Set up log rotation for all services
- Configure Docker log driver with size limits
- Regular cleanup schedule (weekly/monthly)
- Monitor disk usage trends
- Set up automatic cleanup scripts
- Limit Ollama model count

**Example log rotation config** (`/etc/docker/daemon.json`):
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

### ContainerDown

**Alert**: Critical container (AdGuard, n8n, Ollama) not seen for 60+ seconds

#### Immediate Actions (3 minutes)

1. **Identify which container**:
   ```bash
   curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.alertname=="ContainerDown") | .labels.name'
   ```

2. **Check container status**:
   ```bash
   docker ps -a | grep <container_name>
   ```

3. **Restart container**:
   ```bash
   docker compose restart <service_name>
   ```

4. **Verify container is running**:
   ```bash
   docker ps | grep <container_name>
   ```

#### Detailed Troubleshooting

See service-specific procedures:
- AdGuard: [AdGuardDown](#adguarddown)
- n8n: [N8nDown](#n8ndown)
- Ollama: [OllamaDown](#ollamadown)

---

## Warning Alerts

### ContainerHighCPU

**Alert**: Container CPU usage above 80% for 10+ minutes

#### Investigation (10 minutes)

1. **Identify container and verify**:
   ```bash
   docker stats <container_name> --no-stream
   ```

2. **Determine activity**:
   - **Ollama**: Check for active inference
     ```bash
     docker exec ollama ollama ps
     docker logs ollama --tail 50
     ```

   - **n8n**: Check active workflows
     - Access n8n UI
     - Review currently executing workflows
     - Check workflow complexity

   - **AdGuard**: Check query volume
     - Access AdGuard UI
     - Review query statistics
     - Look for DNS amplification attempts

3. **Assess if legitimate**:
   - Expected: AI inference, batch workflows, high DNS load
   - Concerning: Idle service with high CPU, unknown process

#### Resolution

1. **If legitimate workload**:
   - Monitor until completion
   - Consider optimization if recurring
   - Add CPU limits to prevent monopolization

2. **If concerning**:
   ```bash
   # Review container logs
   docker logs <container> --tail 200

   # Restart if needed
   docker compose restart <service>

   # Add CPU limit
   # Edit docker-compose.yml:
   #   cpus: '2.0'
   ```

---

### ContainerHighMemory

**Alert**: Container memory above 85% of limit for 10+ minutes

#### Investigation (10 minutes)

1. **Check container memory**:
   ```bash
   docker stats <container_name> --no-stream
   docker inspect <container> | jq '.[0].HostConfig.Memory'
   ```

2. **Service-specific checks**:
   - **Ollama**: Check loaded models
   - **n8n**: Check workflow data size
   - **Others**: Review application behavior

#### Resolution

1. **If limit too low**:
   ```yaml
   # Increase in docker-compose.yml
   mem_limit: 4g  # Increase appropriately
   ```

2. **If potential leak**:
   ```bash
   # Monitor over time
   watch -n 10 'docker stats <container> --no-stream'

   # If steadily increasing, restart container
   docker compose restart <service>
   ```

3. **If at capacity**:
   - Optimize application configuration
   - Reduce concurrent operations
   - Scale to larger host

---

### ContainerRestartLoop

**Alert**: Container restarted >3 times in 1 hour

**Indicates**: Persistent configuration issue or application bug

#### Investigation (15 minutes)

1. **Check restart count**:
   ```bash
   docker inspect <container> | jq '.[0].RestartCount'
   ```

2. **Review all restart logs**:
   ```bash
   docker logs <container> --since 1h
   ```

3. **Look for patterns**:
   - Same error on each restart?
   - Timing pattern (immediate crash vs delayed)?
   - Exit code pattern?

#### Resolution

1. **Configuration error**:
   ```bash
   # Review configuration files
   # Fix errors
   # Restart manually after fix
   docker compose up -d <service>
   ```

2. **Missing dependency**:
   ```bash
   # Check depends_on in docker-compose.yml
   # Ensure dependencies are healthy
   docker compose ps
   ```

3. **Resource limit too low**:
   ```bash
   # Check for OOM kills
   docker inspect <container> | jq '.[0].State.OOMKilled'

   # Increase memory limit if true
   ```

4. **Application bug**:
   - Check for known issues in application
   - Review recent changes
   - Consider rollback to previous version
   - Report bug to application maintainers

---

### HighDiskIOWait

**Alert**: Disk I/O wait >50% for 10+ minutes

#### Investigation (10 minutes)

1. **Check current I/O**:
   ```bash
   iostat -x 5 3  # 3 samples, 5 seconds apart
   ```

2. **Identify processes causing I/O**:
   ```bash
   sudo iotop -o -b -n 3
   ```

3. **Check disk health**:
   ```bash
   sudo smartctl -a /dev/sda
   ```

#### Resolution

1. **If backup/transfer in progress**:
   - Let complete
   - Schedule during off-peak hours in future

2. **If disk hardware issue**:
   - Review SMART data for failures
   - Plan disk replacement if needed
   - Consider RAID if available

3. **If application causing excessive I/O**:
   - Optimize database queries
   - Adjust logging levels
   - Consider caching layer

---

### HighNetworkTraffic

**Alert**: Network traffic >100MB/s for 10+ minutes

#### Investigation (10 minutes)

1. **Check current traffic**:
   ```bash
   iftop -i <interface>
   ```

2. **Identify source**:
   ```bash
   # Container network usage
   docker stats --no-stream

   # Active connections
   netstat -tunap | grep ESTABLISHED | head -20
   ```

3. **Determine if legitimate**:
   - Ollama model download (4-7GB, temporary)
   - Backup operation
   - Docker image pull

#### Resolution

1. **If legitimate**:
   - Allow to complete
   - Monitor completion

2. **If suspicious/attack**:
   ```bash
   # Identify attacking IPs
   netstat -tunap | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr

   # Block abusive IP
   sudo iptables -A INPUT -s <IP_ADDRESS> -j DROP

   # For DNS amplification (AdGuard)
   # Review AdGuard logs and block in AdGuard UI
   ```

3. **If compromised**:
   - Isolate affected service
   - Review access logs
   - Scan for malware
   - Restore from known-good backup

---

### SystemLoadHigh

**Alert**: 15-minute load average >2x CPU count for 10+ minutes

#### Investigation (15 minutes)

1. **Check load averages**:
   ```bash
   uptime
   # Shows 1, 5, and 15-minute load averages
   ```

2. **Identify cause** (CPU vs I/O):
   ```bash
   # CPU usage
   mpstat 1 5

   # I/O wait
   iostat -x 1 5

   # Memory pressure
   free -h && vmstat 1 5
   ```

3. **Top processes**:
   ```bash
   top -b -n 1 | head -30
   ```

#### Resolution

Based on bottleneck identified:

1. **CPU bottleneck**: See [HighCPUUsage](#highcpuusage)
2. **I/O bottleneck**: See [HighDiskIOWait](#highdiskiowait)
3. **Memory bottleneck**: See [HighMemoryUsage](#highmemoryusage)

---

## Escalation Path

### Level 1: Automated Response
- Alert fires
- Monitoring system logs alert
- Webhook notification sent

### Level 2: On-Call Response (0-30 minutes)
- Review alert in AlertManager
- Follow runbook procedure
- Attempt standard resolution

### Level 3: Extended Investigation (30-60 minutes)
- Deep dive into logs
- Check for related alerts
- Review recent changes
- Consult application documentation

### Level 4: Emergency Response (60+ minutes)
- Consider service degradation
- Implement temporary workarounds
- Plan rollback if needed
- Engage external support if applicable

---

## Post-Incident Procedures

After resolving any critical alert:

1. **Document the incident**:
   - What happened
   - Root cause
   - Resolution steps taken
   - Time to resolution

2. **Update monitoring**:
   - Adjust alert thresholds if needed
   - Add new alerts for gaps identified
   - Update documentation

3. **Prevent recurrence**:
   - Fix root cause (not just symptoms)
   - Implement automated remediation if possible
   - Schedule preventive maintenance
   - Update runbook with lessons learned

4. **Review and improve**:
   - Was alert actionable?
   - Was runbook helpful?
   - Can we detect this earlier?
   - Can we auto-remediate?

---

## Common Tools Reference

### Docker Commands
```bash
# Container status
docker ps -a

# Logs
docker logs <container> --tail 200 --follow

# Stats
docker stats --no-stream

# Restart
docker compose restart <service>

# Inspect
docker inspect <container>

# Cleanup
docker system prune -a --volumes -f
```

### Prometheus Commands
```bash
# Check alerts
curl http://localhost:9090/api/v1/alerts

# Check targets
curl http://localhost:9090/api/v1/targets

# Query metrics
curl 'http://localhost:9090/api/v1/query?query=up'

# Validate config
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### AlertManager Commands
```bash
# List alerts
curl http://localhost:9093/api/v2/alerts

# Silence alert
amtool silence add alertname="AlertName" --duration=1h --comment="Maintenance"

# List silences
amtool silence query
```

### System Commands
```bash
# CPU usage
top, htop, mpstat

# Memory usage
free -h, vmstat

# Disk usage
df -h, du -sh, iostat

# Network usage
iftop, netstat, ss

# Disk health
smartctl -a /dev/sda
```

---

## Emergency Contacts

Update this section with your team's contact information:

- **Primary On-Call**: [Name, Contact]
- **Secondary On-Call**: [Name, Contact]
- **Infrastructure Lead**: [Name, Contact]
- **Security Team**: [Name, Contact]

---

## Maintenance Windows

Document planned maintenance windows to avoid false alerts:

- **Weekly**: [Day/Time] - Routine updates
- **Monthly**: [Day/Time] - Major updates
- **Quarterly**: [Day/Time] - Infrastructure review

Remember to silence alerts during planned maintenance:
```bash
amtool silence add alertname=~ --duration=2h --comment="Planned maintenance window"
```
