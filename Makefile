# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build build-bookwyrm pull status clean validate env-check clone-bookwyrm migrate-bookwyrm
.PHONY: setup-all start-all stop-all restart-all update-all logs-all status-all clean-all

# Compose file flags
COMPOSE_BASE := docker compose
COMPOSE_ALL := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml

# Bookwyrm repository
BOOKWYRM_REPO := https://github.com/bookwyrm-social/bookwyrm.git
BOOKWYRM_BRANCH := production

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (base services only)"
	@echo "  make setup-all          - Setup with monitoring stack (Grafana, Prometheus, etc.)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo "  make clone-bookwyrm     - Clone Bookwyrm repository (automatic during setup)"
	@echo ""
	@echo "Service Management (Base Stack):"
	@echo "  make start              - Start base services (AdGuard, n8n, Ollama, WireGuard, Bookwyrm)"
	@echo "  make stop               - Stop base services"
	@echo "  make restart            - Restart base services"
	@echo "  make status             - Show status of base services"
	@echo ""
	@echo "Service Management (All Services):"
	@echo "  make start-all          - Start ALL services (base + monitoring)"
	@echo "  make stop-all           - Stop ALL services (base + monitoring)"
	@echo "  make restart-all        - Restart ALL services (base + monitoring)"
	@echo "  make status-all         - Show status of ALL services (base + monitoring)"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update             - Update base services (pull latest Bookwyrm, rebuild, update images)"
	@echo "  make update-all         - Update ALL services (base + monitoring)"
	@echo "  make pull               - Pull latest images (except Bookwyrm)"
	@echo "  make build              - Build all services that require building"
	@echo "  make build-bookwyrm     - Rebuild Bookwyrm images from source"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from base services"
	@echo "  make logs-all           - Show logs from ALL services (base + monitoring)"
	@echo "  make logs-bookwyrm      - Show Bookwyrm logs only"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-wireguard     - Show WireGuard logs only"
	@echo ""
	@echo "Validation & Cleanup:"
	@echo "  make validate           - Validate docker-compose configuration"
	@echo "  make clean              - Remove base containers and volumes (WARNING: destroys data)"
	@echo "  make clean-all          - Remove ALL containers and volumes (WARNING: destroys all data)"
	@echo ""

# Check that .env file exists
env-check:
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found!"; \
		echo "Run: cp .env.example .env"; \
		echo "Then edit .env with your configuration"; \
		exit 1; \
	fi
	@echo "✓ .env file exists"

# Validate docker-compose configuration
validate: env-check
	@echo "Validating docker-compose configuration..."
	@$(COMPOSE_BASE) config --quiet
	@echo "✓ Docker Compose configuration is valid"

# Clone Bookwyrm repository if not already present
clone-bookwyrm:
	@if [ ! -d "bookwyrm" ]; then \
		echo "Cloning Bookwyrm repository ($(BOOKWYRM_BRANCH) branch)..."; \
		git clone -b $(BOOKWYRM_BRANCH) $(BOOKWYRM_REPO) bookwyrm; \
		echo "✓ Bookwyrm repository cloned"; \
	else \
		echo "✓ Bookwyrm repository already exists"; \
	fi

# Build services that require building (Bookwyrm)
build: validate clone-bookwyrm
	@echo "Building services from source..."
	@$(COMPOSE_BASE) build
	@echo "✓ Build complete"

# Build Bookwyrm specifically (takes longer, done from Git)
build-bookwyrm: validate clone-bookwyrm
	@echo "Building Bookwyrm from official Git repository..."
	@echo "This will take several minutes on first run..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo "✓ Bookwyrm build complete"

# Run Bookwyrm database migrations (creates tables, applies schema changes)
migrate-bookwyrm:
	@echo "Running Bookwyrm database migrations..."
	@echo "Waiting for Bookwyrm container to be ready..."
	@sleep 5
	@docker exec bookwyrm python manage.py migrate --no-input
	@echo "✓ Bookwyrm migrations complete"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images for base services..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo "✓ Base images pulled"

# First time setup (base stack only)
setup: env-check validate clone-bookwyrm
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/5: Building Bookwyrm from source (this takes several minutes)..."
	@$(COMPOSE_BASE) build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/5: Pulling pre-built images..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/5: Starting services..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@echo "Step 4/5: Running Bookwyrm database migrations..."
	@sleep 10
	@docker exec bookwyrm python manage.py migrate --no-input
	@echo ""
	@echo "Step 5/5: Restarting Bookwyrm services..."
	@$(COMPOSE_BASE) restart bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@sleep 5
	@$(COMPOSE_BASE) ps
	@echo ""
	@echo "✓ Setup complete! Base services are running."
	@echo ""
	@echo "Access your services:"
	@echo "  - AdGuard Home: http://$$SERVER_IP:80"
	@echo "  - n8n:          https://$$SERVER_IP:5678"
	@echo "  - Bookwyrm:     http://$$SERVER_IP:8000"
	@echo "  - Ollama API:   http://$$SERVER_IP:11434"
	@echo ""
	@echo "Note: First-time container initialization may take a few minutes."
	@echo "Check logs with: make logs"

# Setup with ALL services (base + monitoring)
setup-all: env-check validate clone-bookwyrm
	@echo "Starting setup with ALL services (base + monitoring)..."
	@echo ""
	@echo "Step 1/5: Building Bookwyrm from source..."
	@$(COMPOSE_BASE) build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/5: Pulling pre-built images..."
	@$(COMPOSE_ALL) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/5: Starting all services..."
	@$(COMPOSE_ALL) up -d
	@echo ""
	@echo "Step 4/5: Running Bookwyrm database migrations..."
	@sleep 10
	@docker exec bookwyrm python manage.py migrate --no-input
	@echo ""
	@echo "Step 5/5: Restarting Bookwyrm services..."
	@$(COMPOSE_ALL) restart bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@sleep 5
	@$(COMPOSE_ALL) ps
	@echo ""
	@echo "✓ Setup complete! All services are running (base + monitoring)."
	@echo ""
	@echo "Access your services:"
	@echo "  - Grafana:      http://$$SERVER_IP:3001"
	@echo "  - Prometheus:   http://$$SERVER_IP:9090"
	@echo "  - Alertmanager: http://$$SERVER_IP:9093"
	@echo ""
	@echo "Note: Use 'make start-all', 'make stop-all', etc. to manage all services."

# Update base services
update: env-check validate clone-bookwyrm
	@echo "Updating base services..."
	@echo ""
	@echo "Step 1/4: Pulling latest Bookwyrm source code..."
	@cd bookwyrm && git pull origin $(BOOKWYRM_BRANCH)
	@echo ""
	@echo "Step 2/4: Rebuilding Bookwyrm from latest production branch..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 3/4: Pulling latest images for other services..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 4/4: Restarting services with new images..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@echo "✓ Update complete! Base services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Update ALL services (base + monitoring)
update-all: env-check validate clone-bookwyrm
	@echo "Updating ALL services (base + monitoring)..."
	@echo ""
	@echo "Step 1/4: Pulling latest Bookwyrm source code..."
	@cd bookwyrm && git pull origin $(BOOKWYRM_BRANCH)
	@echo ""
	@echo "Step 2/4: Rebuilding Bookwyrm from latest production branch..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 3/4: Pulling latest images for all services..."
	@$(COMPOSE_ALL) pull --ignore-pull-failures
	@echo ""
	@echo "Step 4/4: Restarting all services with new images..."
	@$(COMPOSE_ALL) up -d
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status-all"

# Start base services
start: env-check
	@echo "Starting base services..."
	@$(COMPOSE_BASE) up -d
	@echo "✓ Base services started"

# Start ALL services (base + monitoring)
start-all: env-check
	@echo "Starting ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) up -d
	@echo "✓ All services started"

# Stop base services
stop:
	@echo "Stopping base services..."
	@$(COMPOSE_BASE) down
	@echo "✓ Base services stopped"

# Stop ALL services (base + monitoring)
stop-all:
	@echo "Stopping ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) down
	@echo "✓ All services stopped"

# Restart base services
restart: env-check
	@echo "Restarting base services..."
	@$(COMPOSE_BASE) restart
	@echo "✓ Base services restarted"

# Restart ALL services (base + monitoring)
restart-all: env-check
	@echo "Restarting ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) restart
	@echo "✓ All services restarted"

# Show base service status
status:
	@$(COMPOSE_BASE) ps

# Show ALL service status (base + monitoring)
status-all:
	@$(COMPOSE_ALL) ps

# View logs from base services
logs:
	@$(COMPOSE_BASE) logs -f

# View logs from ALL services (base + monitoring)
logs-all:
	@$(COMPOSE_ALL) logs -f

# View logs from specific services
logs-bookwyrm:
	@$(COMPOSE_BASE) logs -f bookwyrm bookwyrm-celery bookwyrm-celery-beat

logs-n8n:
	@$(COMPOSE_BASE) logs -f n8n

logs-wireguard:
	@$(COMPOSE_BASE) logs -f wireguard

logs-ollama:
	@$(COMPOSE_BASE) logs -f ollama

# Clean up base stack (WARNING: destroys data)
clean:
	@echo "WARNING: This will remove base containers and volumes, destroying all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing base containers..."
	@$(COMPOSE_BASE) down -v
	@echo "✓ Base stack cleanup complete"

# Clean up ALL services (base + monitoring) - WARNING: destroys all data
clean-all:
	@echo "WARNING: This will remove ALL containers and volumes (base + monitoring), destroying all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing all containers..."
	@$(COMPOSE_ALL) down -v
	@echo "✓ Complete cleanup finished"
