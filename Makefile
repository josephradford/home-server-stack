# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build pull status clean validate env-check
.PHONY: bookwyrm-setup bookwyrm-start bookwyrm-stop bookwyrm-restart bookwyrm-status bookwyrm-logs bookwyrm-update bookwyrm-init

# Compose file flags - always include monitoring
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml

# Bookwyrm wrapper project location
BOOKWYRM_DIR := external/bookwyrm-docker

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (all services + monitoring)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management:"
	@echo "  make start              - Start all services (base + monitoring + Bookwyrm if present)"
	@echo "  make stop               - Stop all services"
	@echo "  make restart            - Restart all services"
	@echo "  make status             - Show status of all services"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update             - Update all services (pull latest images)"
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
	@echo "  make logs               - Show logs from all services"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-wireguard     - Show WireGuard logs only"
	@echo ""
	@echo "Validation & Cleanup:"
	@echo "  make validate           - Validate docker-compose configuration"
	@echo "  make clean              - Remove all containers and volumes (WARNING: destroys data)"
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
	@$(COMPOSE) config --quiet
	@echo "✓ Docker Compose configuration is valid"

# Build services that require building
build: validate
	@echo "Building services from source..."
	@$(COMPOSE) build
	@echo "✓ Build complete"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo "✓ Images pulled"

# First time setup
setup: env-check validate
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/2: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Starting services..."
	@$(COMPOSE) up -d
	@echo ""
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		$(MAKE) bookwyrm-start; \
		echo ""; \
	fi
	@$(COMPOSE) ps
	@echo ""
	@echo "✓ Setup complete! All services are running."
	@echo ""
	@echo "Access your services:"
	@echo "  - AdGuard Home: http://$$SERVER_IP:80"
	@echo "  - n8n:          https://$$SERVER_IP:5678"
	@echo "  - Ollama API:   http://$$SERVER_IP:11434"
	@echo "  - Habitica:     http://$$SERVER_IP:8080"
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
	@echo "Note: First-time container initialization may take a few minutes."
	@echo "Check logs with: make logs"

# Update all services
update: env-check validate
	@echo "Updating all services..."
	@echo ""
	@echo "Step 1/2: Pulling latest images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/2: Restarting services with new images..."
	@$(COMPOSE) up -d
	@echo ""
	@$(MAKE) bookwyrm-update
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Start all services
start: env-check
	@echo "Starting all services..."
	@$(COMPOSE) up -d
	@$(MAKE) bookwyrm-start
	@echo "✓ All services started"

# Stop all services
stop:
	@echo "Stopping all services..."
	@$(COMPOSE) down
	@$(MAKE) bookwyrm-stop
	@echo "✓ All services stopped"

# Restart all services
restart: env-check
	@echo "Restarting all services..."
	@$(COMPOSE) restart
	@$(MAKE) bookwyrm-restart
	@echo "✓ All services restarted"

# Show service status
status:
	@$(COMPOSE) ps
	@echo ""
	@$(MAKE) bookwyrm-status

# View logs from all services
logs:
	@$(COMPOSE) logs -f

# View logs from specific services
logs-n8n:
	@$(COMPOSE) logs -f n8n

logs-wireguard:
	@$(COMPOSE) logs -f wireguard

logs-ollama:
	@$(COMPOSE) logs -f ollama

# Clean up all services (WARNING: destroys data)
clean:
	@echo "WARNING: This will remove all containers and volumes, destroying all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing all containers..."
	@$(COMPOSE) down -v
	@echo "✓ Cleanup complete"

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
