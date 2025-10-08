# Add Resource Limits and Security Profiles

## Priority: 3 (Medium)
## Estimated Time: 3-4 hours
## Phase: Month 2 - Medium Priority Hardening

## Description
Implement CPU/memory limits, health checks, and security profiles (seccomp, AppArmor) for all containers to prevent resource exhaustion and limit attack surface.

## Acceptance Criteria
- [ ] Resource limits defined for all services
- [ ] Health checks configured
- [ ] Seccomp profiles applied
- [ ] Read-only root filesystems where possible
- [ ] no-new-privileges enabled
- [ ] Drop unnecessary capabilities

## Technical Implementation Details

**Example docker-compose.yml updates:**
```yaml
services:
  n8n:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    security_opt:
      - no-new-privileges:true
      - seccomp=./security/seccomp/n8n-profile.json
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  adguard:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
      - NET_ADMIN
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost/"]
      interval: 30s

  grafana:
    read_only: true
    tmpfs:
      - /tmp
      - /var/lib/grafana/plugins:mode=1777
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    security_opt:
      - no-new-privileges:true
```

**Security profile example (security/seccomp/default-profile.json):**
```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86", "SCMP_ARCH_X32"],
  "syscalls": [
    {"names": ["read", "write", "open", "close", "stat"], "action": "SCMP_ACT_ALLOW"},
    {"names": ["socket", "bind", "connect", "listen"], "action": "SCMP_ACT_ALLOW"},
    {"names": ["execve", "fork", "clone"], "action": "SCMP_ACT_ALLOW"}
  ]
}
```

## Testing Commands
```bash
# Verify resource limits
docker stats

# Check health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Test resource constraints
docker exec n8n cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# Verify seccomp profile
docker inspect n8n | jq '.[0].HostConfig.SecurityOpt'
```

## Success Metrics
- All containers have resource limits
- Health checks passing
- No resource exhaustion incidents
- Security profiles active

## References
- [Docker Resource Constraints](https://docs.docker.com/config/containers/resource_constraints/)
- [Seccomp Profiles](https://docs.docker.com/engine/security/seccomp/)
