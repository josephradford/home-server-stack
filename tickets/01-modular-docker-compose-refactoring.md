# Modular Docker Compose Refactoring

## Priority: 3 (Medium)
## Estimated Time: 4-6 hours
## Phase: Architecture Improvement

## Description
Refactor the monolithic `docker-compose.yml` (450+ lines) into modular, optional service files following the existing pattern established by `docker-compose.monitoring.yml`. This improves maintainability, clarity, and makes it easier to share individual service configurations.

## Motivation
The current docker-compose.yml contains all services (core + optional), making it:
- **Difficult to maintain** - Large file with mixed concerns
- **Hard to share** - Can't easily extract "just Bookwyrm" or "just Habitica" configs
- **Unclear dependencies** - What's required vs optional isn't obvious
- **Intimidating for new users** - 450+ lines is overwhelming

The refactoring addresses lessons learned from the complex Bookwyrm setup (volume mounts, nginx, static files, initialization) by isolating that complexity into its own file.

## Acceptance Criteria
- [ ] Core services remain in base `docker-compose.yml` (~150-200 lines)
- [ ] Optional services split into separate compose files
- [ ] Makefile updated with modular service management targets
- [ ] All existing `make` commands continue to work unchanged
- [ ] Documentation updated to reflect new structure
- [ ] Migration guide for existing deployments created
- [ ] No functionality regression (all services work as before)

## Technical Implementation Details

### Files to Create/Modify

#### New Files to Create
1. `docker-compose.bookwyrm.yml` - Bookwyrm web app + nginx + PostgreSQL + Redis
2. `docker-compose.habitica.yml` - Habitica client + server + MongoDB
3. `docs/ARCHITECTURE.md` - Document the modular compose file pattern
4. `docs/BOOKWYRM_SETUP.md` - Lessons learned from Bookwyrm deployment

#### Files to Modify
1. `docker-compose.yml` - Keep only core services
2. `Makefile` - Add modular service targets and update COMPOSE variables
3. `README.md` - Update setup instructions
4. `.gitignore` - Ensure new config/ files are handled correctly

### Proposed File Structure

```
docker-compose.yml              # Core: AdGuard, n8n, Ollama, WireGuard
docker-compose.monitoring.yml   # Existing: Grafana, Prometheus, Alertmanager, etc.
docker-compose.bookwyrm.yml     # New: Bookwyrm + nginx + databases
docker-compose.habitica.yml     # New: Habitica + MongoDB
config/
  bookwyrm/
    nginx.conf                  # Bookwyrm nginx configuration
  (future service configs)
```

### Core Services (docker-compose.yml)
**Keep these essential services:**
- AdGuard Home (DNS + ad blocking)
- n8n (workflow automation)
- Ollama (LLM inference)
- WireGuard (VPN)

**Rationale:** These are the foundational services that provide core home server functionality.

### Bookwyrm Module (docker-compose.bookwyrm.yml)

```yaml
services:
  bookwyrm:
    build:
      context: ./bookwyrm
      dockerfile: Dockerfile
    container_name: bookwyrm
    # ... (full config from current docker-compose.yml)

  bookwyrm-nginx:
    image: nginx:alpine
    # ... (nginx reverse proxy)

  bookwyrm-celery:
    # ... (celery worker)

  bookwyrm-celery-beat:
    # ... (celery scheduler)

  bookwyrm-db:
    image: postgres:16-alpine
    # ... (PostgreSQL database)

  bookwyrm-redis-activity:
    # ... (Redis for activity)

  bookwyrm-redis-broker:
    # ... (Redis for Celery)

volumes:
  bookwyrm_static:

networks:
  homeserver:
    external: true  # Uses network from base compose file
```

### Habitica Module (docker-compose.habitica.yml)

```yaml
services:
  habitica-mongo:
    image: mongo:5.0
    # ... (MongoDB database)

  habitica-server:
    image: awinterstein/habitica-server
    # ... (API server)

  habitica-client:
    image: awinterstein/habitica-client
    # ... (Frontend)

networks:
  homeserver:
    external: true  # Uses network from base compose file
```

### Makefile Changes

```makefile
# Compose file combinations
COMPOSE_BASE := docker compose
COMPOSE_MONITORING := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml
COMPOSE_BOOKWYRM := docker compose -f docker-compose.yml -f docker-compose.bookwyrm.yml
COMPOSE_HABITICA := docker compose -f docker-compose.yml -f docker-compose.habitica.yml
COMPOSE_ALL := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.bookwyrm.yml -f docker-compose.habitica.yml

# New modular targets
.PHONY: setup-bookwyrm start-bookwyrm stop-bookwyrm restart-bookwyrm logs-bookwyrm status-bookwyrm
.PHONY: setup-habitica start-habitica stop-habitica restart-habitica logs-habitica status-habitica

# Bookwyrm-specific targets
setup-bookwyrm: env-check validate clone-bookwyrm
	@echo "Setting up Bookwyrm..."
	@$(COMPOSE_BOOKWYRM) build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@$(COMPOSE_BOOKWYRM) up -d
	@$(MAKE) init-bookwyrm

start-bookwyrm:
	@$(COMPOSE_BOOKWYRM) up -d

stop-bookwyrm:
	@$(COMPOSE_BOOKWYRM) down

restart-bookwyrm:
	@$(COMPOSE_BOOKWYRM) restart

logs-bookwyrm:
	@$(COMPOSE_BOOKWYRM) logs -f bookwyrm bookwyrm-nginx

status-bookwyrm:
	@$(COMPOSE_BOOKWYRM) ps

# Habitica-specific targets
setup-habitica: env-check validate
	@echo "Setting up Habitica..."
	@$(COMPOSE_HABITICA) up -d

start-habitica:
	@$(COMPOSE_HABITICA) up -d

stop-habitica:
	@$(COMPOSE_HABITICA) down

restart-habitica:
	@$(COMPOSE_HABITICA) restart

logs-habitica:
	@$(COMPOSE_HABITICA) logs -f habitica-client habitica-server

status-habitica:
	@$(COMPOSE_HABITICA) ps

# Updated help target
help:
	@echo "Modular Service Management:"
	@echo "  make setup-bookwyrm      - Setup Bookwyrm service"
	@echo "  make start-bookwyrm      - Start Bookwyrm only"
	@echo "  make stop-bookwyrm       - Stop Bookwyrm only"
	@echo "  make logs-bookwyrm       - View Bookwyrm logs"
	@echo "  make setup-habitica      - Setup Habitica service"
	@echo "  make start-habitica      - Start Habitica only"
	@echo "  make stop-habitica       - Stop Habitica only"
	@echo "  make logs-habitica       - View Habitica logs"
```

### Network Configuration

All modular compose files use `external: true` for the `homeserver` network:

```yaml
networks:
  homeserver:
    external: true
```

This allows services in different compose files to communicate while maintaining the ability to start/stop them independently.

### Backwards Compatibility

**Preserve existing workflows:**
- `make setup-all` - Continues to deploy everything
- `make start-all` - Continues to start all services
- `make stop-all` - Continues to stop all services
- Existing `.env` variables unchanged

**New capabilities:**
- `make setup-bookwyrm` - Deploy just Bookwyrm + core
- `make start-monitoring` - Start just monitoring stack
- Mix and match: `docker compose -f docker-compose.yml -f docker-compose.bookwyrm.yml up -d`

## Migration Path for Existing Deployments

### Step 1: Stop All Services
```bash
make stop-all
```

### Step 2: Pull Latest Changes
```bash
git pull origin main
```

### Step 3: Verify Configuration
```bash
# Check all compose files are valid
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.bookwyrm.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.habitica.yml config --quiet
make validate
```

### Step 4: Restart Services
```bash
# Option 1: Start everything (same as before)
make start-all

# Option 2: Start selectively
make start              # Core only
make start-monitoring   # Add monitoring
make start-bookwyrm     # Add Bookwyrm
make start-habitica     # Add Habitica
```

### Step 5: Verify All Services Running
```bash
make status-all
```

## Benefits

### 1. Improved Maintainability
- **Smaller files** - Each compose file is ~100-150 lines instead of 450+
- **Clear separation** - Core vs optional services obvious
- **Easier debugging** - Issues isolated to specific service files
- **Simpler reviews** - PRs touch only relevant service files

### 2. Better User Experience
- **Optional services** - Choose what to deploy
- **Clearer documentation** - Each service has its own file + docs
- **Easier sharing** - "Want Bookwyrm? Use docker-compose.bookwyrm.yml"
- **Reduced confusion** - New users start with core, add services as needed

### 3. Organizational Benefits
- **Service ownership** - Each file can have a maintainer
- **Isolated testing** - Test Bookwyrm changes without touching core
- **Flexible deployment** - Different environments use different combinations
- **Better Git history** - Changes scoped to specific services

### 4. Captures Complexity
The Bookwyrm setup revealed significant complexity:
- Volume mount shadowing issues
- Static file compilation requirements
- nginx reverse proxy configuration
- Multi-step initialization (migrate, initdb, compile_themes, collectstatic)

Isolating this in `docker-compose.bookwyrm.yml` + `docs/BOOKWYRM_SETUP.md` prevents that complexity from overwhelming the main configuration.

## Risks and Mitigations

### Risk 1: Breaking Existing Deployments
**Mitigation:**
- Preserve `make setup-all` and `make start-all` commands
- Extensive testing before merge
- Clear migration documentation
- Version the change (breaking change if needed)

### Risk 2: Network Complexity
**Mitigation:**
- Use `external: true` for shared network
- Document network architecture in `docs/ARCHITECTURE.md`
- Test inter-service communication

### Risk 3: Confusing New Users
**Mitigation:**
- Update README with clear "Quick Start" (use setup-all)
- Document modular approach in ARCHITECTURE.md
- Provide examples for common scenarios

### Risk 4: Makefile Complexity
**Mitigation:**
- Keep variable names consistent (COMPOSE_*)
- Group related targets in comments
- Test all targets before merge

## Testing Plan

### 1. Fresh Deployment Test
```bash
# Clone repo
git clone <repo>
cd home-server-stack

# Setup base only
make setup

# Verify core services
make status

# Add Bookwyrm
make setup-bookwyrm

# Verify Bookwyrm working (http://SERVER_IP:8000)
# Add monitoring
make start-monitoring

# Verify Grafana (http://SERVER_IP:3001)
```

### 2. Full Stack Test
```bash
make setup-all
make status-all
# Verify all services accessible
```

### 3. Selective Stop/Start
```bash
make stop-bookwyrm
make status-all  # Verify only Bookwyrm stopped
make start-bookwyrm
make status-all  # Verify Bookwyrm restarted
```

### 4. Migration Test
```bash
# From existing deployment
make stop-all
git pull
make validate
make start-all
make status-all  # Verify all services running
```

## Documentation Updates

### docs/ARCHITECTURE.md (New)
```markdown
# Home Server Stack Architecture

## Modular Compose Files

This stack uses Docker Compose's multi-file feature to organize services:

- `docker-compose.yml` - Core services (required)
- `docker-compose.monitoring.yml` - Observability stack (optional)
- `docker-compose.bookwyrm.yml` - Book tracking platform (optional)
- `docker-compose.habitica.yml` - Habit tracker (optional)

### Quick Start

Deploy everything:
make setup-all

Deploy selectively:
make setup              # Core only
make setup-bookwyrm     # Core + Bookwyrm
make setup-monitoring   # Add monitoring to existing deployment

### Service Communication

All services share the `homeserver` network created by the base compose file.
Optional services use `external: true` to connect to this network.
```

### docs/BOOKWYRM_SETUP.md (New)
Document all the lessons learned:
- Volume mount shadowing issue
- Static file compilation requirements
- nginx configuration
- Initialization sequence
- Common troubleshooting

### README.md Updates
- Add "Modular Architecture" section
- Update Quick Start to mention optional services
- Link to ARCHITECTURE.md for details

## Follow-up Tasks

After this refactoring:
1. Create similar modules for any future services
2. Consider adding `make enable-<service>` / `make disable-<service>` commands
3. Explore per-service .env files for better secret management
4. Document service dependency graph
5. Add validation that checks for required services when starting optional ones

## Success Metrics

- [ ] Core docker-compose.yml under 200 lines
- [ ] All modular compose files under 150 lines each
- [ ] All existing make commands work unchanged
- [ ] Documentation updated and complete
- [ ] Successful migration test on production server
- [ ] No service functionality regression

## References

- Docker Compose multiple file documentation: https://docs.docker.com/compose/extends/
- Existing pattern: `docker-compose.monitoring.yml` in this repo
- Inspiration: Bookwyrm's official multi-container setup
