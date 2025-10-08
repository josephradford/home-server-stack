# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build pull status clean validate env-check
.PHONY: setup-all start-all stop-all restart-all update-all logs-all status-all clean-all
.PHONY: bookwyrm-setup bookwyrm-start bookwyrm-stop bookwyrm-restart bookwyrm-status bookwyrm-logs bookwyrm-update bookwyrm-init

# Compose file flags
COMPOSE_BASE := docker compose
COMPOSE_ALL := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml

# Bookwyrm wrapper project location
BOOKWYRM_DIR := external/bookwyrm-docker

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (base services only)"
	@echo "  make setup-all          - Setup with monitoring stack (Grafana, Prometheus, etc.)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management (Base Stack):"
	@echo "  make start              - Start base services (AdGuard, n8n, Ollama, WireGuard, Habitica)"
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
	@echo "  make update             - Update base services (pull latest images)"
	@echo "  make update-all         - Update ALL services (base + monitoring)"
	@echo "  make pull               - Pull latest images"
	@echo "  make build              - Build all services that require building"
	@echo ""
	@echo "Bookwyrm (External Wrapper):"
	@echo "  make bookwyrm-setup     - Setup Bookwyrm (clone wrapper if needed)"
	@echo "  make bookwyrm-start     - Start Bookwyrm services"
	@echo "  make bookwyrm-stop      - Stop Bookwyrm services"
	@echo "  make bookwyrm-restart   - Restart Bookwyrm services"
	@echo "  make bookwyrm-status    - Show Bookwyrm status"
	@echo "  make bookwyrm-logs      - Show Bookwyrm logs"
	@echo "  make bookwyrm-update    - Update Bookwyrm to latest version"
	@echo "  make bookwyrm-init      - Re-run Bookwyrm initialization"
	@echo "  See docs/BOOKWYRM.md for detailed integration guide"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from base services"
	@echo "  make logs-all           - Show logs from ALL services (base + monitoring)"
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

# Build services that require building
build: validate
	@echo "Building services from source..."
	@$(COMPOSE_BASE) build
	@echo "✓ Build complete"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images for base services..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo "✓ Base images pulled"

# First time setup (base stack only)
setup: env-check validate
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/2: Pulling pre-built images..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Starting services..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		$(MAKE) bookwyrm-start; \
		echo ""; \
	fi
	@$(COMPOSE_BASE) ps
	@echo ""
	@echo "✓ Setup complete! Base services are running."
	@echo ""
	@echo "Access your services:"
	@echo "  - AdGuard Home: http://$$SERVER_IP:80"
	@echo "  - n8n:          https://$$SERVER_IP:5678"
	@echo "  - Ollama API:   http://$$SERVER_IP:11434"
	@echo "  - Habitica:     http://$$SERVER_IP:8080"
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "  - Bookwyrm:     http://$$SERVER_IP:8000"; \
	fi
	@echo ""
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "To add Bookwyrm, run: make bookwyrm-setup"; \
		echo ""; \
	fi
	@echo "Note: First-time container initialization may take a few minutes."
	@echo "Check logs with: make logs"

# Setup with ALL services (base + monitoring)
setup-all: env-check validate
	@echo "Starting setup with ALL services (base + monitoring)..."
	@echo ""
	@echo "Step 1/2: Pulling pre-built images..."
	@$(COMPOSE_ALL) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Starting all services..."
	@$(COMPOSE_ALL) up -d
	@echo ""
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		$(MAKE) bookwyrm-start; \
		echo ""; \
	fi
	@$(COMPOSE_ALL) ps
	@echo ""
	@echo "✓ Setup complete! All services are running (base + monitoring)."
	@echo ""
	@echo "Access your services:"
	@echo "  - Grafana:      http://$$SERVER_IP:3001"
	@echo "  - Prometheus:   http://$$SERVER_IP:9090"
	@echo "  - Alertmanager: http://$$SERVER_IP:9093"
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "  - Bookwyrm:     http://$$SERVER_IP:8000"; \
	fi
	@echo ""
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "To add Bookwyrm, run: make bookwyrm-setup"; \
		echo ""; \
	fi
	@echo "Note: Use 'make start-all', 'make stop-all', etc. to manage all services."

# Update base services
update: env-check validate
	@echo "Updating base services..."
	@echo ""
	@echo "Step 1/2: Pulling latest images..."
	@$(COMPOSE_BASE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Restarting services with new images..."
	@$(COMPOSE_BASE) up -d
	@echo ""
	@$(MAKE) bookwyrm-update
	@echo ""
	@echo "✓ Update complete! Base services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Update ALL services (base + monitoring)
update-all: env-check validate
	@echo "Updating ALL services (base + monitoring)..."
	@echo ""
	@echo "Step 1/2: Pulling latest images for all services..."
	@$(COMPOSE_ALL) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Restarting all services with new images..."
	@$(COMPOSE_ALL) up -d
	@echo ""
	@$(MAKE) bookwyrm-update
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status-all"

# Start base services
start: env-check
	@echo "Starting base services..."
	@$(COMPOSE_BASE) up -d
	@$(MAKE) bookwyrm-start
	@echo "✓ Base services started"

# Start ALL services (base + monitoring)
start-all: env-check
	@echo "Starting ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) up -d
	@$(MAKE) bookwyrm-start
	@echo "✓ All services started"

# Stop base services
stop:
	@echo "Stopping base services..."
	@$(COMPOSE_BASE) down
	@$(MAKE) bookwyrm-stop
	@echo "✓ Base services stopped"

# Stop ALL services (base + monitoring)
stop-all:
	@echo "Stopping ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) down
	@$(MAKE) bookwyrm-stop
	@echo "✓ All services stopped"

# Restart base services
restart: env-check
	@echo "Restarting base services..."
	@$(COMPOSE_BASE) restart
	@$(MAKE) bookwyrm-restart
	@echo "✓ Base services restarted"

# Restart ALL services (base + monitoring)
restart-all: env-check
	@echo "Restarting ALL services (base + monitoring)..."
	@$(COMPOSE_ALL) restart
	@$(MAKE) bookwyrm-restart
	@echo "✓ All services restarted"

# Show base service status
status:
	@$(COMPOSE_BASE) ps
	@echo ""
	@$(MAKE) bookwyrm-status

# Show ALL service status (base + monitoring)
status-all:
	@$(COMPOSE_ALL) ps
	@echo ""
	@$(MAKE) bookwyrm-status

# View logs from base services
logs:
	@$(COMPOSE_BASE) logs -f

# View logs from ALL services (base + monitoring)
logs-all:
	@$(COMPOSE_ALL) logs -f

# View logs from specific services
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

# Bookwyrm wrapper integration targets
# These commands delegate to the external bookwyrm-docker wrapper project

bookwyrm-setup:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Cloning bookwyrm-docker wrapper..."; \
		mkdir -p external; \
		cd external && git clone https://github.com/josephradford/bookwyrm-docker.git; \
		echo "✓ Bookwyrm wrapper cloned"; \
		echo ""; \
		echo "Next steps:"; \
		echo "1. cd $(BOOKWYRM_DIR)"; \
		echo "2. cp .env.example .env"; \
		echo "3. Edit .env with your configuration"; \
		echo "4. Run: make bookwyrm-setup (again to deploy)"; \
		exit 0; \
	fi
	@echo "Setting up Bookwyrm via wrapper..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) setup
	@echo ""
	@echo "✓ Bookwyrm setup complete!"
	@echo "See docs/BOOKWYRM.md for integration details"

bookwyrm-start:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Starting Bookwyrm..."; \
		cd $(BOOKWYRM_DIR) && $(MAKE) start; \
	fi

bookwyrm-stop:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Stopping Bookwyrm..."; \
		cd $(BOOKWYRM_DIR) && $(MAKE) stop; \
	fi

bookwyrm-restart:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Restarting Bookwyrm..."; \
		cd $(BOOKWYRM_DIR) && $(MAKE) restart; \
	fi

bookwyrm-status:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		cd $(BOOKWYRM_DIR) && $(MAKE) status; \
	else \
		echo "Bookwyrm not installed (run: make bookwyrm-setup)"; \
	fi

bookwyrm-logs:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		cd $(BOOKWYRM_DIR) && $(MAKE) logs; \
	else \
		echo "ERROR: Bookwyrm wrapper not found at $(BOOKWYRM_DIR)"; \
		echo "Run: make bookwyrm-setup"; \
		exit 1; \
	fi

bookwyrm-update:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Updating Bookwyrm..."; \
		cd $(BOOKWYRM_DIR) && $(MAKE) update; \
	fi

bookwyrm-init:
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Re-running Bookwyrm initialization..."; \
		cd $(BOOKWYRM_DIR) && $(MAKE) init; \
	else \
		echo "ERROR: Bookwyrm wrapper not found at $(BOOKWYRM_DIR)"; \
		echo "Run: make bookwyrm-setup"; \
		exit 1; \
	fi
