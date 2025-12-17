# Alert Documentation

This document provides comprehensive information about all configured alerts in the monitoring stack, including their meanings, thresholds, response procedures, and common issues.

> **Note:** This document focuses on alert-specific response procedures. For general troubleshooting (services, DNS, SSL, network), see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Alert Severity Levels

- **Critical**: Immediate attention required. Service outage or severe resource exhaustion that will cause failures.
- **Warning**: Attention needed soon. Resource pressure or degraded performance that may lead to issues if unaddressed.

## Alert Groups

### Critical Alerts

#### ServiceDown
**Severity**: Critical
**Threshold**: Service metric `up == 0` for 30 seconds
**Meaning**: A monitored service endpoint is not responding to health checks.

**Common Causes**:
- Service crashed or failed to start
- Network connectivity issues
- Firewall blocking access to service port
- Service endpoint configuration changed

**Response Procedure**:
1. Check if service container is running: `docker ps | grep <service_name>`
2. Review service logs: `docker logs <container_name>`
3. Check service health endpoint manually: `curl http://<service_ip>:<port>/health`
4. Restart service if needed: `docker compose restart <service_name>`
5. Verify service is back up in Prometheus targets page

**False Positives**:
- Temporary network glitches (resolved within 30s)
- Planned maintenance (should silence alert beforehand)

---

#### HighCPUUsage
**Severity**: Critical
**Threshold**: CPU usage above 85% for 5 minutes
**Meaning**: System-wide CPU usage is critically high and sustained.

**Common Causes**:
- Runaway process consuming CPU
- Legitimate high workload (AI model inference, data processing)
- CPU-intensive container without resource limits
- Cryptocurrency mining malware

**Response Procedure**:
1. Identify top CPU consumers: `ssh <server> "docker stats --no-stream"`
2. Check system processes: `ssh <server> "top -b -n 1"`
3. Review recent container deployments or workflow executions
4. For n8n: Check active workflow executions
5. For Ollama: Check if models are being loaded or inferences running
6. Consider adding CPU limits to containers if abuse detected
7. Scale up server resources if legitimate workload

**False Positives**:
- Ollama model loading (typically completes within 5 minutes)
- n8n workflow batch processing (check execution logs)
- System updates or backups running

---

#### HighMemoryUsage
**Severity**: Critical
**Threshold**: Memory usage above 90% for 3 minutes
**Meaning**: System memory is nearly exhausted, risk of OOM kills.

**Common Causes**:
- Memory leak in application
- Large AI models loaded in Ollama
- n8n workflow with large data sets
- Insufficient memory for current workload
- No memory limits on containers

**Response Procedure**:
1. Check memory usage: `ssh <server> "free -h"`
2. Identify memory hogs: `ssh <server> "docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'"`
3. Review Ollama loaded models: `docker exec ollama ollama ps`
4. Unload unused models: `docker exec ollama ollama rm <model_name>`
5. Check for memory leaks in n8n workflows
6. Restart problematic containers to release memory
7. Add memory limits to prevent single container exhausting system

**False Positives**:
- Large model inference in progress (Ollama can use 4-8GB temporarily)
- Large file processing in n8n (monitor workflow completion)

---

#### DiskSpaceLow
**Severity**: Critical
**Threshold**: Disk usage above 90% for 5 minutes
**Meaning**: Root filesystem is nearly full, risk of service failures.

**Common Causes**:
- Docker images and containers accumulating
- Application logs not rotated
- Large datasets stored in volumes
- Ollama models consuming space (can be 4-7GB each)
- n8n workflow execution data accumulating

**Response Procedure**:
1. Check disk usage: `ssh <server> "df -h"`
2. Identify large directories: `ssh <server> "du -sh /var/lib/docker/* | sort -h | tail -10"`
3. Clean Docker resources: `ssh <server> "docker system prune -a --volumes -f"`
4. Review and remove old Ollama models: `docker exec ollama ollama list`
5. Clean n8n execution data if needed
6. Check log file sizes: `ssh <server> "du -sh /var/log/*"`
7. Expand disk if legitimately needed

**False Positives**:
- Large model download in progress (temporary, completes within minutes)
- Backup operation in progress

---

#### ContainerDown
**Severity**: Critical
**Threshold**: Container not seen by cAdvisor for 60 seconds
**Meaning**: A critical service container (AdGuard, n8n, Ollama) has stopped.

**Common Causes**:
- Container crashed due to application error
- Out of memory kill (OOM)
- Docker daemon restart
- Manual stop during maintenance
- Resource limits exceeded

**Response Procedure**:
1. Check container status: `docker ps -a | grep <container_name>`
2. Review container exit reason: `docker inspect <container_name> | grep -A 5 State`
3. Check container logs: `docker logs --tail 100 <container_name>`
4. Restart container: `docker compose restart <service_name>`
5. Monitor for repeated failures (indicates deeper issue)

**False Positives**:
- Intentional restart during maintenance
- Docker daemon updates

---

#### ContainerHighCPU
**Severity**: Warning
**Threshold**: Container CPU usage above 80% for 10 minutes
**Meaning**: A specific container is using excessive CPU resources.

**Common Causes**:
- Ollama: Model inference or loading
- n8n: Complex workflow execution
- AdGuard: Heavy DNS query load
- Application bug or inefficiency

**Response Procedure**:
1. Identify container and current activity
2. For Ollama: Check running models and inferences
3. For n8n: Review active workflow executions
4. For AdGuard: Check query volume in dashboard
5. Review container logs for errors or anomalies
6. Consider adding CPU limits if abuse continues
7. Optimize application if legitimate but inefficient

**False Positives**:
- Expected high CPU during AI inference (Ollama)
- Batch workflow processing (n8n)
- High DNS query volume during legitimate traffic spikes

---

#### ContainerHighMemory
**Severity**: Warning
**Threshold**: Container memory above 85% of limit for 10 minutes
**Meaning**: A container is approaching its memory limit.

**Common Causes**:
- Large AI model loaded in Ollama
- Memory leak in application
- Large dataset processing in n8n
- Insufficient memory limit configured

**Response Procedure**:
1. Check container memory limit and usage: `docker stats <container_name>`
2. Review what the container is currently doing
3. For Ollama: Check loaded models size
4. For n8n: Review workflow data size
5. Increase memory limit if legitimately needed
6. Investigate and fix memory leaks if detected

**False Positives**:
- Normal operation for large model inference
- Temporary spike during data processing

---

#### ContainerRestartLoop
**Severity**: Warning
**Threshold**: Container restarted more than 3 times in 1 hour
**Meaning**: A container is repeatedly crashing and restarting.

**Common Causes**:
- Application crash on startup due to misconfiguration
- Missing required environment variables
- Volume mount issues
- Insufficient resources causing OOM kills
- Database connection failures
- Network dependency issues

**Response Procedure**:
1. Check restart count: `docker ps -a | grep <container_name>`
2. Review recent logs: `docker logs --tail 200 <container_name>`
3. Check container configuration: `docker inspect <container_name>`
4. Verify environment variables are set correctly
5. Check volume mounts are accessible
6. Review resource limits (may be too low)
7. Check dependencies are available
8. Fix configuration and restart manually

**False Positives**:
- Manual restarts during troubleshooting (if within 1 hour window)

---

### Service-Specific Alerts

#### PrometheusTargetDown
**Severity**: Critical
**Threshold**: Monitoring target down for 1 minute
**Meaning**: A core monitoring component (Prometheus, node-exporter, cAdvisor) is not responding.

**Common Causes**:
- Monitoring container stopped or crashed
- Network configuration changed
- Port binding conflict
- Docker network issues

**Response Procedure**:
1. Check monitoring stack status: `docker compose -f docker-compose.monitoring.yml ps`
2. Review logs: `docker logs <monitoring_container>`
3. Verify port bindings: `netstat -tlnp | grep <port>`
4. Restart monitoring stack if needed
5. **CRITICAL**: This affects all monitoring - resolve immediately

**False Positives**:
- Intentional restart during monitoring stack updates

---

#### AdGuardDown
**Severity**: Critical
**Threshold**: AdGuard service down for 1 minute
**Meaning**: DNS and ad-blocking service is not responding.

**Impact**: Network clients using this DNS server will fail to resolve domains.

**Response Procedure**:
1. Check container status: `docker ps | grep adguard`
2. Review logs: `docker logs adguard-home --tail 100`
3. Verify port bindings (53/tcp, 53/udp, 80/tcp, 3000/tcp)
4. Check configuration files: `ls -la data/adguard/conf/`
5. Restart service: `docker compose restart adguard`
6. Verify DNS resolution: `dig @<server_ip> google.com`

**False Positives**:
- Configuration updates requiring restart

---

#### N8nDown
**Severity**: Critical
**Threshold**: n8n service down for 2 minutes
**Meaning**: Workflow automation service is not responding.

**Impact**: All automated workflows will stop executing.

**Response Procedure**:
1. Check container status: `docker ps | grep n8n`
2. Review logs: `docker logs n8n --tail 100`
3. Check database file: `ls -la data/n8n/database.sqlite`
4. Verify SSL certificates if using HTTPS: `ls -la ssl/`
5. Check environment variables in .env file
6. Restart service: `docker compose restart n8n`
7. Verify web interface accessible: `https://<server_ip>:5678`

**False Positives**:
- Intentional restart for configuration changes

---

#### OllamaDown
**Severity**: Critical
**Threshold**: Ollama service down for 2 minutes
**Meaning**: AI model inference API is not responding.

**Impact**: AI-powered workflows and integrations will fail.

**Response Procedure**:
1. Check container status: `docker ps | grep ollama`
2. Review logs: `docker logs ollama --tail 100`
3. Check model storage: `du -sh data/ollama/`
4. Verify API endpoint: `curl http://<server_ip>:11434/api/version`
5. Restart service: `docker compose restart ollama`
6. Reload models if needed: `docker exec ollama ollama pull <model_name>`

**False Positives**:
- Model management operations causing brief unavailability

---

### Resource Alerts

#### HighDiskIOWait
**Severity**: Warning
**Threshold**: Disk I/O wait time > 0.5 for 10 minutes
**Meaning**: System is spending significant time waiting for disk operations.

**Common Causes**:
- Disk hardware issues or failure
- Heavy database writes
- Large file operations
- Insufficient IOPS for workload
- Disk nearly full causing slow operations

**Response Procedure**:
1. Check disk I/O: `ssh <server> "iostat -x 5 3"`
2. Identify processes with high I/O: `ssh <server> "iotop -o -b -n 3"`
3. Check disk health: `ssh <server> "smartctl -a /dev/sda"`
4. Review disk space: `df -h`
5. Check for large ongoing operations (backups, logs)
6. Consider I/O optimization or hardware upgrade if persistent

**False Positives**:
- Backup operations in progress
- Large model file downloads (Ollama)
- Database maintenance operations

---

#### HighNetworkTraffic
**Severity**: Warning
**Threshold**: Network traffic exceeds 100MB/s for 10 minutes
**Meaning**: Unusually high network traffic detected.

**Common Causes**:
- Large file transfers (model downloads)
- DDoS attack or abuse
- Data synchronization or backup
- Container image pulls
- Video streaming or large downloads

**Response Procedure**:
1. Monitor network traffic: `ssh <server> "iftop -i <interface>"`
2. Check container network usage: `docker stats`
3. Review active connections: `ssh <server> "netstat -tunap | grep ESTABLISHED"`
4. For AdGuard: Check for DNS amplification attempts
5. Review firewall logs for suspicious activity
6. Block abusive IPs if attack detected

**False Positives**:
- Legitimate large file downloads (Ollama models 4-7GB)
- Docker image pulls during updates
- Backup operations

---

#### SystemLoadHigh
**Severity**: Warning
**Threshold**: 15-minute load average above 2x CPU count for 10 minutes
**Meaning**: System load is consistently high, indicating resource contention.

**Common Causes**:
- Too many active processes
- I/O bottleneck causing process queuing
- CPU-bound workload exceeding capacity
- Memory pressure causing swapping
- Runaway processes

**Response Procedure**:
1. Check load averages: `ssh <server> "uptime"`
2. Review running processes: `ssh <server> "top -b -n 1"`
3. Check I/O wait: `ssh <server> "iostat"`
4. Review memory usage: `ssh <server> "free -h"`
5. Identify bottleneck (CPU, I/O, memory)
6. Address specific resource constraint
7. Consider workload optimization or hardware scaling

**False Positives**:
- Batch processing jobs (n8n workflows)
- AI model inference workloads (Ollama)
- Legitimate high load during peak usage

---

## Alert Response Priorities

### Immediate Action Required (Critical)
1. **ServiceDown** - Affects monitoring and services
2. **PrometheusTargetDown** - Blind to system state
3. **AdGuardDown** - Network DNS resolution fails
4. **ContainerDown** - Service outage
5. **HighMemoryUsage** - Risk of OOM kills
6. **DiskSpaceLow** - Risk of service failures

### Investigate Soon (Warning)
1. **ContainerRestartLoop** - May escalate to outage
2. **HighCPUUsage** - May cause performance issues
3. **ContainerHighCPU/Memory** - May affect container
4. **SystemLoadHigh** - System under pressure
5. **HighDiskIOWait** - Performance degradation
6. **HighNetworkTraffic** - May indicate abuse

---

## Alert Silencing

To silence alerts during planned maintenance:

```bash
# Silence all alerts for 2 hours
amtool silence add alertname=~ --duration=2h --comment="Planned maintenance"

# Silence specific alert
amtool silence add alertname="ServiceDown" instance="server:9090" --duration=1h --comment="Service upgrade"

# List active silences
amtool silence query

# Expire a silence
amtool silence expire <silence_id>
```

---

## Testing Alerts

To verify alerts are working correctly:

```bash
# Test ServiceDown - stop a service
docker compose stop adguard
# Wait 1-2 minutes, then check: curl http://localhost:9090/api/v1/alerts
docker compose start adguard

# Test HighCPU - create CPU load
stress-ng --cpu 8 --timeout 360s

# Test HighMemory - create memory pressure
stress-ng --vm 2 --vm-bytes 90% --timeout 300s

# Test DiskSpace - create large file
fallocate -l 10G /tmp/testfile
# Clean up: rm /tmp/testfile

# Send test alert to AlertManager
curl -XPOST http://localhost:9093/api/v1/alerts -H "Content-Type: application/json" -d '[{
  "labels": {"alertname": "TestAlert", "severity": "warning"},
  "annotations": {"summary": "Test alert", "description": "This is a test"},
  "startsAt": "2024-01-01T00:00:00Z"
}]'
```

---

## Notification Channels

Alerts are routed based on severity:

- **Critical**: Webhook (http://127.0.0.1:5001/) with 5-minute repeat interval
- **Warning**: Webhook (http://127.0.0.1:5001/) with 30-minute repeat interval
- **Email**: Configured but commented out in alertmanager.yml (optional)

To enable email notifications, uncomment the email_configs section in `monitoring/alertmanager/alertmanager.yml` and configure SMTP settings.

---

## Common Issues and Solutions

### Alert Not Firing

1. Check alert rule syntax: `docker exec prometheus promtool check rules /etc/prometheus/alert_rules.yml`
2. Verify metric exists: Query metric in Prometheus UI
3. Check evaluation interval: May take up to 1 minute to evaluate
4. Review Prometheus logs: `docker logs prometheus`

### Alert Firing Constantly (False Positives)

1. Review threshold - may be too sensitive
2. Increase `for:` duration to filter transient spikes
3. Add additional label filters to exclude known cases
4. Consider alert inhibition rules

### Notifications Not Received

1. Check AlertManager status: `curl http://localhost:9093/api/v1/status`
2. Verify receiver configuration in alertmanager.yml
3. Test webhook endpoint: `curl -XPOST http://127.0.0.1:5001/`
4. Review AlertManager logs: `docker logs alertmanager`
5. Check alert routing matches severity labels

### Too Many Alerts (Alert Fatigue)

1. Review and adjust thresholds based on normal baseline
2. Increase `for:` durations to reduce noise
3. Implement better inhibition rules
4. Group related alerts
5. Consider separate warning vs critical thresholds

---

## Maintenance

### Regular Review Schedule

- **Weekly**: Review fired alerts and adjust thresholds if needed
- **Monthly**: Analyze alert patterns and optimize rules
- **Quarterly**: Full alert configuration audit

### Metrics to Track

- Alert firing frequency
- Time to resolution
- False positive rate
- Alert coverage gaps

---

## Further Reading

- [Prometheus Alerting Documentation](https://prometheus.io/docs/alerting/latest/overview/)
- [AlertManager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Best Practices for Alerting](https://prometheus.io/docs/practices/alerting/)
