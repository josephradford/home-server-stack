# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build build-bookwyrm pull status clean validate env-check

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup           - First time setup (builds Bookwyrm, pulls other images, starts services)"
	@echo "  make setup-monitoring - Setup with optional monitoring stack"
	@echo "  make env-check       - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management:"
	@echo "  make start           - Start all services"
	@echo "  make stop            - Stop all services"
	@echo "  make restart         - Restart all services"
	@echo "  make status          - Show status of all services"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update          - Update all services (rebuild Bookwyrm, pull latest images)"
	@echo "  make pull            - Pull latest images (except Bookwyrm)"
	@echo "  make build           - Build all services that require building"
	@echo "  make build-bookwyrm  - Rebuild Bookwyrm images from source"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs            - Show logs from all services (press Ctrl+C to exit)"
	@echo "  make logs-bookwyrm   - Show Bookwyrm logs only"
	@echo "  make logs-n8n        - Show n8n logs only"
	@echo "  make logs-wireguard  - Show WireGuard logs only"
	@echo ""
	@echo "Validation & Cleanup:"
	@echo "  make validate        - Validate docker-compose configuration"
	@echo "  make clean           - Remove all containers and volumes (WARNING: destroys data)"
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
	@docker compose config --quiet
	@echo "✓ Docker Compose configuration is valid"

# Build services that require building (Bookwyrm)
build: validate
	@echo "Building services from source..."
	@docker compose build
	@echo "✓ Build complete"

# Build Bookwyrm specifically (takes longer, done from Git)
build-bookwyrm: validate
	@echo "Building Bookwyrm from official Git repository..."
	@echo "This will take several minutes on first run..."
	@docker compose build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo "✓ Bookwyrm build complete"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images..."
	@docker compose pull --ignore-pull-failures
	@echo "✓ Images pulled"

# First time setup
setup: env-check validate
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/4: Building Bookwyrm from source (this takes several minutes)..."
	@docker compose build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/4: Pulling pre-built images..."
	@docker compose pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/4: Starting services..."
	@docker compose up -d
	@echo ""
	@echo "Step 4/4: Waiting for services to be ready..."
	@sleep 10
	@docker compose ps
	@echo ""
	@echo "✓ Setup complete! Services are running."
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
	@docker compose build bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/4: Pulling pre-built images..."
	@docker compose pull --ignore-pull-failures
	@docker compose -f docker-compose.yml -f docker-compose.monitoring.yml pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/4: Starting services with monitoring..."
	@docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
	@echo ""
	@echo "Step 4/4: Waiting for services to be ready..."
	@sleep 10
	@docker compose ps
	@echo ""
	@echo "✓ Setup complete! Services are running with monitoring."
	@echo ""
	@echo "Access your services:"
	@echo "  - Grafana:      http://$$SERVER_IP:3001"
	@echo "  - Prometheus:   http://$$SERVER_IP:9090"
	@echo "  - Alertmanager: http://$$SERVER_IP:9093"

# Update all services
update: env-check validate
	@echo "Updating all services..."
	@echo ""
	@echo "Step 1/3: Rebuilding Bookwyrm from latest production branch..."
	@docker compose build --no-cache bookwyrm bookwyrm-celery bookwyrm-celery-beat
	@echo ""
	@echo "Step 2/3: Pulling latest images for other services..."
	@docker compose pull --ignore-pull-failures
	@echo ""
	@echo "Step 3/3: Restarting services with new images..."
	@docker compose up -d
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Start services
start: env-check
	@echo "Starting services..."
	@docker compose up -d
	@echo "✓ Services started"

# Stop services
stop:
	@echo "Stopping services..."
	@docker compose down
	@echo "✓ Services stopped"

# Restart services
restart: env-check
	@echo "Restarting services..."
	@docker compose restart
	@echo "✓ Services restarted"

# Show service status
status:
	@docker compose ps

# View logs from all services
logs:
	@docker compose logs -f

# View logs from specific services
logs-bookwyrm:
	@docker compose logs -f bookwyrm bookwyrm-celery bookwyrm-celery-beat

logs-n8n:
	@docker compose logs -f n8n

logs-wireguard:
	@docker compose logs -f wireguard

logs-ollama:
	@docker compose logs -f ollama

# Clean up everything (WARNING: destroys data)
clean:
	@echo "WARNING: This will remove all containers and volumes, destroying all data!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing containers..."
	@docker compose down -v
	@echo "✓ Cleanup complete"
