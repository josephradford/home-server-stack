# Fix Privileged Container (cAdvisor Security Hardening)

## Priority: 1 (Critical)
## Estimated Time: 2-3 hours
## Phase: Week 1 - Critical Fixes

## Description
Remove the `privileged: true` flag from the cAdvisor container and replace it with specific Linux capabilities. This significantly reduces the attack surface by following the principle of least privilege while maintaining full monitoring functionality.

## Acceptance Criteria
- [ ] `privileged: true` removed from cAdvisor configuration
- [ ] Specific capabilities added (`SYS_PTRACE`, `SYS_ADMIN`)
- [ ] Security options configured (`no-new-privileges`)
- [ ] Read-only root filesystem implemented where possible
- [ ] cAdvisor continues to collect all metrics successfully
- [ ] Container health check passes
- [ ] Documentation updated with security rationale

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.monitoring.yml` - Update cAdvisor service configuration
2. `SECURITY.md` - Document security hardening decisions (new file)

### Current Configuration (INSECURE)
```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:latest
  container_name: cadvisor
  restart: unless-stopped
  ports:
    - "8080:8080"
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /dev/disk/:/dev/disk:ro
  privileged: true  # ⚠️ SECURITY RISK
  devices:
    - /dev/kmsg
  networks:
    - homeserver
```

### New Hardened Configuration
```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:v0.47.2  # Pinned version (update as needed)
  container_name: cadvisor
  restart: unless-stopped
  ports:
    - "8080:8080"
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /dev/disk/:/dev/disk:ro
  cap_add:
    - SYS_PTRACE    # Required for process inspection
    - SYS_ADMIN     # Required for cgroup access
  cap_drop:
    - ALL
  security_opt:
    - no-new-privileges:true
    - apparmor=unconfined  # Required for cAdvisor to access system metrics
  devices:
    - /dev/kmsg:/dev/kmsg:r  # Read-only access
  networks:
    - homeserver
  healthcheck:
    test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:8080/healthz"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

### Alternative Minimal Capability Configuration
If the above doesn't work, try this more minimal approach:
```yaml
cadvisor:
  image: gcr.io/cadvisor/cadvisor:v0.47.2
  container_name: cadvisor
  restart: unless-stopped
  ports:
    - "8080:8080"
  volumes:
    - /:/rootfs:ro
    - /var/run:/var/run:ro
    - /sys:/sys:ro
    - /dev/disk/:/dev/disk:ro
  cap_add:
    - SYS_ADMIN
  security_opt:
    - no-new-privileges:true
  devices:
    - /dev/kmsg
  networks:
    - homeserver
```

### Testing Commands
```bash
# Stop existing monitoring stack
docker compose -f docker-compose.monitoring.yml down

# Restart with new configuration
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d cadvisor

# Check container is running
docker ps | grep cadvisor

# Verify capabilities
docker inspect cadvisor | grep -A 20 CapAdd

# Test metrics collection
curl -s http://localhost:8080/metrics | head -n 20

# Check for errors in logs
docker logs cadvisor --tail 50

# Verify Prometheus can scrape metrics
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="cadvisor")'

# Access cAdvisor UI
# http://SERVER_IP:8080/containers/
```

### Validation Steps
1. Verify cAdvisor starts without errors
2. Confirm metrics are being collected (check /metrics endpoint)
3. Ensure Prometheus successfully scrapes cAdvisor
4. Check Grafana dashboards display container metrics
5. Verify no capability-related errors in logs
6. Test that all previously available metrics are still present

## Success Metrics
- cAdvisor container runs without `privileged: true`
- All container metrics available in Prometheus
- No permission-denied errors in cAdvisor logs
- Grafana container dashboards functioning normally
- Security audit shows reduced attack surface
- Container passes health checks

## Dependencies
- Existing monitoring stack deployed
- Docker version 20.10+ (for proper capability support)
- Prometheus scraping cAdvisor metrics

## Risk Considerations
- **Metric Loss**: Some metrics might not be available if capabilities are insufficient
- **Compatibility**: Different Docker/kernel versions may require different capabilities
- **Rollback Needed**: If monitoring breaks, quick rollback to privileged mode required

## Rollback Plan
```bash
# If cAdvisor fails to start or loses metrics:

# 1. Restore original configuration
git checkout docker-compose.monitoring.yml

# 2. Restart with original settings
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d cadvisor

# 3. Verify metrics restored
curl http://localhost:8080/metrics

# 4. Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.job=="cadvisor")'
```

## Security Impact
- **Before**: Container has full root access to host system, can perform any privileged operation
- **After**: Container limited to specific capabilities required for monitoring only
- **Attack Surface Reduction**: ~95% reduction in exploitable privileges

## References
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Linux Capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)
- [cAdvisor GitHub Issues on Capabilities](https://github.com/google/cadvisor/issues)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)

## Follow-up Tasks
- Monitor cAdvisor performance for 1 week
- Document any missing metrics
- Consider AppArmor/SELinux profiles for additional hardening
- Apply same capability-based approach to other containers
