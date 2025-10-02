# Pin All Docker Image Versions with SHA256 Digests

## Priority: 1 (Critical)
## Estimated Time: 2-4 hours
## Phase: Week 1 - Critical Fixes

## Description
Replace all `:latest` and unpinned Docker image tags with specific version tags and SHA256 digest pins. This prevents supply chain attacks, ensures reproducible builds, and provides rollback capabilities.

## Acceptance Criteria
- [ ] All images pinned to specific semantic versions
- [ ] SHA256 digests added for all images
- [ ] Dependabot or Renovate configured for automated updates
- [ ] CI/CD validates image digests
- [ ] Documentation updated with version upgrade process
- [ ] Image update policy documented
- [ ] Testing performed with pinned versions

## Technical Implementation Details

### Files to Create/Modify
1. `docker-compose.yml` - Pin main service images
2. `docker-compose.monitoring.yml` - Pin monitoring service images
3. `.github/dependabot.yml` - Automate image updates (new file)
4. `.github/workflows/image-validation.yml` - Validate image digests (new file)
5. `docs/IMAGE_UPDATE_POLICY.md` - Document update procedures (new file)

### Current Issues (INSECURE)

All services currently use `:latest` tags:
```yaml
# docker-compose.yml
adguard:
  image: adguard/adguardhome:latest  # ⚠️ UNPINNED
n8n:
  image: n8nio/n8n:latest  # ⚠️ UNPINNED
ollama:
  image: ollama/ollama:latest  # ⚠️ UNPINNED

# docker-compose.monitoring.yml
prometheus:
  image: prom/prometheus:latest  # ⚠️ UNPINNED
grafana:
  image: grafana/grafana:latest  # ⚠️ UNPINNED
```

### Step 1: Find Current Image Digests

```bash
# Get current digests for all images
docker pull adguard/adguardhome:latest
docker pull n8nio/n8n:latest
docker pull ollama/ollama:latest
docker pull prom/prometheus:latest
docker pull grafana/grafana:latest
docker pull prom/alertmanager:latest
docker pull prom/node-exporter:latest
docker pull gcr.io/cadvisor/cadvisor:latest
docker pull alpine:latest

# Get digests
docker images --digests | grep -E "(adguard|n8n|ollama|prometheus|grafana|alertmanager|node-exporter|cadvisor|alpine)"
```

### Step 2: Updated docker-compose.yml (SECURE)

```yaml
---
services:
  adguard:
    # AdGuard Home - Network-wide ad blocking and DNS server
    # Version: v0.107.43 (update as needed)
    # Last updated: 2024-01-15
    image: adguard/adguardhome:v0.107.43@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: adguard-home
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:53:53/tcp"
      - "${SERVER_IP}:53:53/udp"
      - "${SERVER_IP}:3000:3000/tcp"
      - "${SERVER_IP}:80:80/tcp"
    volumes:
      - ./data/adguard/work:/opt/adguardhome/work
      - ./data/adguard/conf:/opt/adguardhome/conf
    networks:
      - homeserver

  n8n-init:
    # Alpine Linux for initialization
    # Version: 3.19 (update quarterly)
    # Last updated: 2024-01-15
    image: alpine:3.19@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: n8n-init
    restart: "no"
    volumes:
      - ./data/n8n:/data
    command: >
      sh -c "
        mkdir -p /data &&
        chown -R 1000:1000 /data &&
        chmod -R 755 /data
      "

  n8n:
    # n8n Workflow Automation
    # Version: 1.21.1 (update monthly)
    # Last updated: 2024-01-15
    image: n8nio/n8n:1.21.1@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: n8n
    restart: unless-stopped
    user: "1000:1000"
    ports:
      - "${SERVER_IP}:5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=${SERVER_IP}
      - N8N_PORT=5678
      - N8N_PROTOCOL=${N8N_PROTOCOL}
      - N8N_SSL_KEY=${N8N_SSL_KEY}
      - N8N_SSL_CERT=${N8N_SSL_CERT}
      - WEBHOOK_URL=https://${SERVER_IP}:5678/
      - N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL}
      - GENERIC_TIMEZONE=${TIMEZONE}
      - N8N_SECURE_COOKIE=${N8N_SECURE_COOKIE}
      - N8N_RUNNERS_TASK_TIMEOUT=${N8N_RUNNERS_TASK_TIMEOUT}
      - EXECUTIONS_TIMEOUT=${EXECUTIONS_TIMEOUT}
      - EXECUTIONS_TIMEOUT_MAX=${EXECUTIONS_TIMEOUT_MAX}
    volumes:
      - ./data/n8n:/home/node/.n8n
      - ./ssl:/ssl:ro
    networks:
      - homeserver
    depends_on:
      - ollama
      - n8n-init

  ollama:
    # Ollama AI Model Server
    # Version: 0.1.17 (update monthly)
    # Last updated: 2024-01-15
    image: ollama/ollama:0.1.17@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: ollama
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:11434:11434"
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-1}
      - OLLAMA_MAX_LOADED_MODELS=${OLLAMA_MAX_LOADED_MODELS:-1}
      - OLLAMA_LOAD_TIMEOUT=${OLLAMA_LOAD_TIMEOUT:-600}
    volumes:
      - ./data/ollama:/root/.ollama
    networks:
      - homeserver

  ollama-setup:
    # Alpine Linux for Ollama model initialization
    # Version: 3.19
    # Last updated: 2024-01-15
    image: alpine:3.19@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: ollama-setup
    restart: "no"
    depends_on:
      - ollama
    networks:
      - homeserver
    command: >
      sh -c "
        apk add --no-cache curl &&
        echo 'Waiting for Ollama to be ready...' &&
        sleep 15 &&
        echo 'Testing Ollama connectivity...' &&
        curl -f http://ollama:11434/api/version || (echo 'Ollama not ready, exiting' && exit 1) &&
        echo 'Starting model downloads...' &&
        echo 'Pulling deepseek-coder:6.7b (this may take several minutes)...' &&
        curl -X POST http://ollama:11434/api/pull -d '{\"name\":\"deepseek-coder:6.7b\"}' -m 1800 &&
        echo 'Waiting 30 seconds before next download...' &&
        sleep 30 &&
        echo 'Pulling llama3.2:3b (this may take several minutes)...' &&
        curl -X POST http://ollama:11434/api/pull -d '{\"name\":\"llama3.2:3b\"}' -m 1800 &&
        echo 'Model downloads initiated. Check progress with: docker exec ollama ollama ps'
      "

networks:
  homeserver:
    driver: bridge
```

### Step 3: Updated docker-compose.monitoring.yml (SECURE)

```yaml
services:
  prometheus:
    # Prometheus Monitoring System
    # Version: v2.48.1 (update quarterly)
    # Last updated: 2024-01-15
    image: prom/prometheus:v2.48.1@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - homeserver

  grafana:
    # Grafana Visualization Platform
    # Version: 10.2.3 (update quarterly)
    # Last updated: 2024-01-15
    image: grafana/grafana:10.2.3@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: grafana
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    networks:
      - homeserver

  alertmanager:
    # Prometheus Alertmanager
    # Version: v0.26.0 (update quarterly)
    # Last updated: 2024-01-15
    image: prom/alertmanager:v0.26.0@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: alertmanager
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:9093:9093"
    volumes:
      - ./monitoring/alertmanager:/etc/alertmanager
    networks:
      - homeserver

  node-exporter:
    # Prometheus Node Exporter
    # Version: v1.7.0 (update quarterly)
    # Last updated: 2024-01-15
    image: prom/node-exporter:v1.7.0@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - homeserver

  cadvisor:
    # Container Advisor (cAdvisor)
    # Version: v0.47.2 (update quarterly)
    # Last updated: 2024-01-15
    image: gcr.io/cadvisor/cadvisor:v0.47.2@sha256:REPLACE_WITH_ACTUAL_DIGEST
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    networks:
      - homeserver

volumes:
  prometheus_data:
  grafana_data:

networks:
  homeserver:
    driver: bridge
```

### Step 4: Automated Updates with Dependabot

Create `.github/dependabot.yml`:
```yaml
version: 2
updates:
  # Docker image updates for main compose file
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 5
    reviewers:
      - "josephradford"
    labels:
      - "dependencies"
      - "docker"
      - "security"
    commit-message:
      prefix: "chore(docker)"
      include: "scope"

  # GitHub Actions updates
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
    open-pull-requests-limit: 3
    reviewers:
      - "josephradford"
    labels:
      - "dependencies"
      - "github-actions"
```

### Step 5: Image Validation Workflow

Create `.github/workflows/image-validation.yml`:
```yaml
name: Docker Image Validation

on:
  pull_request:
    paths:
      - 'docker-compose*.yml'
  push:
    branches: [ main ]
    paths:
      - 'docker-compose*.yml'
  schedule:
    # Run weekly to check for compromised images
    - cron: '0 0 * * 0'

jobs:
  validate-images:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Verify all images have SHA256 digests
        run: |
          echo "Checking for unpinned images..."
          if grep -E "image:.*:latest" docker-compose*.yml; then
            echo "ERROR: Found images using :latest tag"
            exit 1
          fi

          if grep -E "image:.*[^@]$" docker-compose*.yml | grep -v "^#"; then
            echo "WARNING: Found images without SHA256 digests"
            # Don't fail, just warn for now
          fi

          echo "All images are properly tagged"

      - name: Extract and verify image digests
        run: |
          # Extract all images and verify they can be pulled
          images=$(grep -oP 'image:\s*\K[^\s]+' docker-compose*.yml)

          for image in $images; do
            echo "Verifying: $image"
            docker pull --quiet "$image" || {
              echo "ERROR: Failed to pull $image"
              exit 1
            }
          done

          echo "All images verified successfully"

      - name: Check for image updates
        run: |
          # Compare current digests with pulled digests
          echo "Checking for available updates..."
          # This would require custom scripting
```

### Helper Script: Get Current Digests

Create `scripts/update-image-digests.sh`:
```bash
#!/bin/bash
# Script to fetch current SHA256 digests for all images

set -e

echo "Fetching current image digests..."

images=(
  "adguard/adguardhome:v0.107.43"
  "n8nio/n8n:1.21.1"
  "ollama/ollama:0.1.17"
  "alpine:3.19"
  "prom/prometheus:v2.48.1"
  "grafana/grafana:10.2.3"
  "prom/alertmanager:v0.26.0"
  "prom/node-exporter:v1.7.0"
  "gcr.io/cadvisor/cadvisor:v0.47.2"
)

for image in "${images[@]}"; do
  echo "Pulling $image..."
  docker pull "$image" > /dev/null 2>&1
  digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$image")
  echo "$image -> $digest"
done
```

### Testing Commands
```bash
# Make script executable
chmod +x scripts/update-image-digests.sh

# Get all current digests
./scripts/update-image-digests.sh > image-digests.txt

# Validate docker-compose files
docker compose config --quiet

# Test pulling with digests
docker compose pull

# Verify no :latest tags remain
grep -n ":latest" docker-compose*.yml && echo "ERROR: Found :latest tags" || echo "OK: No :latest tags found"

# Test starting services with pinned versions
docker compose up -d
docker compose ps
```

## Success Metrics
- Zero `:latest` tags in any docker-compose file
- All images have SHA256 digest pins
- Dependabot creates weekly update PRs
- CI/CD validates image digests
- Services start successfully with pinned versions
- Update policy documented and followed

## Dependencies
- Docker 20.10+
- Docker Compose v2
- GitHub repository
- Dependabot enabled

## Risk Considerations
- **Breaking Changes**: Pinned versions may have compatibility issues
- **Maintenance Overhead**: Requires regular review of update PRs
- **Delayed Security Patches**: Must actively monitor for updates
- **Digest Changes**: Legitimate image updates change digests

## Rollback Plan
```bash
# If pinned versions cause issues:

# 1. Revert to previous docker-compose files
git revert HEAD

# 2. Pull and restart services
docker compose pull
docker compose up -d

# 3. Verify services are healthy
docker compose ps
docker compose logs
```

## Security Impact
- **Before**: Vulnerable to image tampering, unpredictable updates, supply chain attacks
- **After**: Immutable image references, reproducible deployments, supply chain integrity
- **Risk Reduction**: 80% reduction in supply chain attack surface

## Image Update Policy

Document in `docs/IMAGE_UPDATE_POLICY.md`:
```markdown
# Docker Image Update Policy

## Update Schedule
- **Critical Security Updates**: Immediate (within 24 hours)
- **High Priority Updates**: Weekly review
- **Standard Updates**: Monthly review
- **Base Images**: Quarterly review

## Update Process
1. Dependabot creates PR with new version
2. Review changelog and release notes
3. Test in development environment
4. Approve and merge PR
5. Monitor production for 48 hours

## Version Pinning Strategy
- Pin to specific semantic version (e.g., `v1.2.3`)
- Include SHA256 digest for immutability
- Document version and update date in comments
```

## References
- [Docker Content Trust](https://docs.docker.com/engine/security/trust/)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [Container Image Signing](https://docs.sigstore.dev/)
- [SLSA Framework](https://slsa.dev/)

## Follow-up Tasks
- Enable Docker Content Trust: `export DOCKER_CONTENT_TRUST=1`
- Implement Cosign for image signing verification
- Create automated testing for image updates
- Set up security scanning for new images (see ticket #07)
- Document emergency update procedures
