# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build build-bookwyrm pull status clean validate env-check
.PHONY: setup-monitoring start-monitoring stop-monitoring restart-monitoring update-monitoring logs-monitoring status-monitoring

# Compose file flags
COMPOSE_BASE := docker compose
COMPOSE_MONITORING := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (builds Bookwyrm, pulls images, starts services)"
	@echo "  make setup-monitoring   - Setup with optional monitoring stack (Grafana, Prometheus)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management (Base Stack):"
	@echo "  make start              - Start base services (AdGuard, n8n, Ollama, WireGuard, Bookwyrm)"
	@echo "  make stop               - Stop base services"
	@echo "  make restart            - Restart base services"
	@echo "  make status             - Show status of base services"
	@echo ""
	@echo "Service Management (With Monitoring):"
	@echo "  make start-monitoring   - Start all services including monitoring"
	@echo "  make stop-monitoring    - Stop all services including monitoring"
	@echo "  make restart-monitoring - Restart all services including monitoring"
	@echo "  make status-monitoring  - Show status of all services including monitoring"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update             - Update base services (rebuild Bookwyrm, pull latest images)"
	@echo "  make update-monitoring  - Update all services including monitoring"
	@echo "  make pull               - Pull latest images (except Bookwyrm)"
	@echo "  make build              - Build all services that require building"
	@echo "  make build-bookwyrm     - Rebuild Bookwyrm images from source"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from base services"
	@echo "  make logs-monitoring    - Show logs from all services including monitoring"
	@echo "  make logs-bookwyrm      - Show Bookwyrm logs only"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-wireguard     - Show WireGuard logs only"
	@echo ""
	@echo "Validation & Cleanup:"
	@echo "  make validate           - Validate docker-compose configuration"
	@echo "  make clean              - Remove base containers and volumes (WARNING: destroys data)"
	@echo "  make clean-monitoring   - Remove all containers and volumes including monitoring"
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

# Build services that require building (Bookwyrm)
build: validate
	@echo "Building services from source..."
	@$(COMPOSE_BASE) build
	@echo "✓ Build complete"

# Build Bookwyrm specifically (takes longer, done from Git)
build-bookwyrm: validate
	@echo "Building Bookwyrm from official Git repository..."
	@echo "This will take several minutes on first run..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo "✓ Bookwyrm build complete"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images for base services..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo "✓ Base images pulled"

# First time setup (base stack only)
setup: env-check validate
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/4: Building Bookwyrm from source (this takes several minutes)..."
	@$(COMPOSE_BASE) build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/4: Pulling pre-built images..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/4: Starting services..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@echo "Step 4/4: Waiting for services to be ready..."
	@sleep 10
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

# Setup with monitoring stack
setup-monitoring: env-check validate
	@echo "Starting setup with monitoring stack..."
	@echo ""
	@echo "Step 1/4: Building Bookwyrm from source..."
	@$(COMPOSE_BASE) build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/4: Pulling pre-built images..."
	@$(COMPOSE_MONITORING) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/4: Starting services with monitoring..."
	@$(COMPOSE_MONITORING) up -d
	@echo ""
	@echo "Step 4/4: Waiting for services to be ready..."
	@sleep 10
	@$(COMPOSE_MONITORING) ps
	@echo ""
	@echo "✓ Setup complete! Services are running with monitoring."
	@echo ""
	@echo "Access your services:"
	@echo "  - Grafana:      http://$$SERVER_IP:3001"
	@echo "  - Prometheus:   http://$$SERVER_IP:9090"
	@echo "  - Alertmanager: http://$$SERVER_IP:9093"
	@echo ""
	@echo "Note: Use 'make start-monitoring', 'make stop-monitoring', etc. to manage all services."

# Update base services
update: env-check validate
	@echo "Updating base services..."
	@echo ""
	@echo "Step 1/3: Rebuilding Bookwyrm from latest production branch..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/3: Pulling latest images for other services..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/3: Restarting services with new images..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@echo "✓ Update complete! Base services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Update all services including monitoring
update-monitoring: env-check validate
	@echo "Updating all services including monitoring..."
	@echo ""
	@echo "Step 1/3: Rebuilding Bookwyrm from latest production branch..."
	@$(COMPOSE_BASE) build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/3: Pulling latest images for all services..."
	@$(COMPOSE_MONITORING) pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/3: Restarting all services with new images..."
	@$(COMPOSE_MONITORING) up -d
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status-monitoring"

# Start base services
start: env-check
	@echo "Starting base services..."
	@$(COMPOSE_BASE) up -d
	@echo "✓ Base services started"

# Start all services including monitoring
start-monitoring: env-check
	@echo "Starting all services including monitoring..."
	@$(COMPOSE_MONITORING) up -d
	@echo "✓ All services started (including monitoring)"

# Stop base services
stop:
	@echo "Stopping base services..."
	@$(COMPOSE_BASE) down
	@echo "✓ Base services stopped"

# Stop all services including monitoring
stop-monitoring:
	@echo "Stopping all services including monitoring..."
	@$(COMPOSE_MONITORING) down
	@echo "✓ All services stopped (including monitoring)"

# Restart base services
restart: env-check
	@echo "Restarting base services..."
	@$(COMPOSE_BASE) restart
	@echo "✓ Base services restarted"

# Restart all services including monitoring
restart-monitoring: env-check
	@echo "Restarting all services including monitoring..."
	@$(COMPOSE_MONITORING) restart
	@echo "✓ All services restarted (including monitoring)"

# Show base service status
status:
	@$(COMPOSE_BASE) ps

# Show all service status including monitoring
status-monitoring:
	@$(COMPOSE_MONITORING) ps

# View logs from base services
logs:
	@$(COMPOSE_BASE) logs -f

# View logs from all services including monitoring
logs-monitoring:
	@$(COMPOSE_MONITORING) logs -f

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

# Clean up everything including monitoring (WARNING: destroys data)
clean-monitoring:
	@echo "WARNING: This will remove ALL containers and volumes including monitoring, destroying all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing all containers..."
	@$(COMPOSE_MONITORING) down -v
	@echo "✓ Complete cleanup finished"
