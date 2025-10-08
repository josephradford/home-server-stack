# Implement Compliance Scanning

## Priority: 4 (Low - Enhancement)
## Estimated Time: 3-4 hours
## Phase: Month 3 - Ongoing Security

## Description
Implement automated compliance scanning using Docker Bench Security and CIS benchmarks to ensure containers and configurations meet security standards.

## Acceptance Criteria
- [ ] Docker Bench Security running weekly
- [ ] CIS Docker Benchmark results tracked
- [ ] Compliance score monitored over time
- [ ] Failed checks documented and remediated
- [ ] Compliance reports generated
- [ ] CI/CD compliance checks added

## Technical Implementation Details

**scripts/compliance-scan.sh:**
```bash
#!/bin/bash
# Docker CIS Benchmark compliance scanning

set -e

echo "🔍 Running Docker Bench Security..."

# Run Docker Bench Security
docker run --rm --net host --pid host --userns host --cap-add audit_control \
  -v /etc:/etc:ro \
  -v /usr/bin/containerd:/usr/bin/containerd:ro \
  -v /usr/bin/runc:/usr/bin/runc:ro \
  -v /usr/lib/systemd:/usr/lib/systemd:ro \
  -v /var/lib:/var/lib:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  --label docker_bench_security \
  docker/docker-bench-security

# Parse results
echo "Generating compliance report..."

# Export to JSON for tracking
docker run --rm --net host --pid host --userns host --cap-add audit_control \
  -v /etc:/etc:ro \
  -v /var/lib:/var/lib:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v $(pwd)/compliance:/usr/share/docker-bench-security/results \
  docker/docker-bench-security -l /usr/share/docker-bench-security/results/bench-$(date +%Y%m%d).json

echo "✅ Compliance scan complete. Results in compliance/"
```

**.github/workflows/compliance-check.yml:**
```yaml
name: Compliance Scanning

on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday
  workflow_dispatch:

jobs:
  docker-bench:
    runs-on: ubuntu-latest
    steps:
      - name: Run Docker Bench Security
        run: |
          docker run --rm --net host --pid host --userns host \
            -v /var/run/docker.sock:/var/run/docker.sock \
            docker/docker-bench-security | tee bench-results.txt

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: compliance-results
          path: bench-results.txt

      - name: Check for failures
        run: |
          if grep -q "FAIL" bench-results.txt; then
            echo "::warning::Compliance issues found"
          fi
```

**Remediation tracking (compliance/remediation.md):**
```markdown
# CIS Docker Benchmark Remediation

## Section 1: Host Configuration

### 1.1.1 Ensure a separate partition for containers has been created
- Status: ⚠️ WARNING
- Action: Consider separate partition for /var/lib/docker
- Priority: Low

### 1.2.1 Ensure the container host has been hardened
- Status: ✅ PASS
- Notes: Using Ubuntu Server with minimal services

## Section 4: Container Images and Build Files

### 4.1 Ensure a user for the container has been created
- Status: ✅ PASS (n8n, most services)
- Status: ⚠️ WARN (AdGuard, Ollama run as root)
- Action: Investigate rootless mode for AdGuard/Ollama

## Section 5: Container Runtime

### 5.12 Ensure the container's root filesystem is mounted as read-only
- Status: ⚠️ WARNING
- Action: Add read_only: true to Grafana, Prometheus
- Priority: Medium
```

## Testing Commands
```bash
# Run compliance scan
chmod +x scripts/compliance-scan.sh
./scripts/compliance-scan.sh

# View results
cat compliance/bench-$(date +%Y%m%d).json | jq '.tests[].results[] | select(.status=="FAIL")'

# Compare scores over time
# Parse JSON and track metrics in Prometheus
```

## Success Metrics
- Weekly compliance scans automated
- Compliance score improving over time
- All FAIL items documented
- High-priority issues remediated

## References
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Docker Bench Security](https://github.com/docker/docker-bench-security)
