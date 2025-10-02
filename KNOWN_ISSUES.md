# Known Issues

## Disk Usage Showing 0% in Grafana

**Status:** Unresolved
**Affects:** System Overview Dashboard - Disk Usage panel
**Severity:** Low (cosmetic, doesn't affect actual system)

### Description
The Disk Usage gauge in the System Overview dashboard consistently shows 0% even though the system has actual disk usage (~21% on a 98GB filesystem).

### Root Cause
Node-exporter running in a Docker container is reading filesystem metrics from the container's overlay filesystem view rather than the host's actual root filesystem. The metrics show:
- Container view: 8.32 GB total, 8.32 GB available (0% used)
- Actual host: 98 GB total, ~74 GB available (~21% used)

### Attempted Fixes
Multiple configurations were attempted:
- `pid: host` - Insufficient
- `network_mode: host` - Broke Prometheus scraping
- `privileged: true` with `/:/host:ro` mount - Still saw container filesystem
- Various `--path.rootfs` configurations - Did not resolve the issue

### Workaround
Check actual disk usage via SSH:
```bash
ssh user@server "df -h /"
```

Or via cAdvisor metrics (if available):
```
container_fs_usage_bytes / container_fs_limit_bytes
```

### Potential Future Solutions
1. Run node-exporter directly on the host (not containerized)
2. Use a different exporter specifically for filesystem metrics
3. Create custom exporter script that runs on host and exposes metrics
4. Wait for upstream node-exporter Docker compatibility improvements

### References
- Related issue: https://github.com/prometheus/node_exporter/issues/
- Docker filesystem isolation: https://docs.docker.com/storage/storagedriver/

---
*Last updated: 2025-10-02*
