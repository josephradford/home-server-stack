# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build pull status clean purge validate env-check ssl-check regenerate-ssl
.PHONY: logs-n8n logs-wireguard logs-ollama logs-habitica logs-hortusfox logs-glance
.PHONY: bookwyrm-setup bookwyrm-start bookwyrm-stop bookwyrm-restart bookwyrm-status bookwyrm-logs bookwyrm-update bookwyrm-init
.PHONY: glance-setup adguard-setup

# Compose file flags - always include monitoring and habitica
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.habitica.yml

# Bookwyrm wrapper project location
BOOKWYRM_DIR := external/bookwyrm-docker

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (all services + monitoring + Bookwyrm)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management:"
	@echo "  make start              - Start all services (base + monitoring + Bookwyrm)"
	@echo "  make stop               - Stop all services"
	@echo "  make restart            - Restart all services"
	@echo "  make status             - Show status of all services"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update             - Update all services (pull latest images)"
	@echo "  make pull               - Pull latest images"
	@echo "  make build              - Build all services that require building"
	@echo ""
	@echo "Bookwyrm Management:"
	@echo "  make bookwyrm-setup     - Setup Bookwyrm wrapper (auto-run during setup)"
	@echo "  make bookwyrm-start     - Start Bookwyrm services (auto-run during start)"
	@echo "  make bookwyrm-stop      - Stop Bookwyrm services (auto-run during stop)"
	@echo "  make bookwyrm-restart   - Restart Bookwyrm services"
	@echo "  make bookwyrm-status    - Show Bookwyrm status"
	@echo "  make bookwyrm-logs      - Show Bookwyrm logs"
	@echo "  make bookwyrm-update    - Update Bookwyrm (auto-run during update)"
	@echo "  make bookwyrm-init      - Re-run Bookwyrm initialization"
	@echo "  See docs/BOOKWYRM.md for integration details"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from all services"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-wireguard     - Show WireGuard logs only"
	@echo "  make logs-habitica      - Show Habitica logs only"
	@echo "  make logs-hortusfox     - Show HortusFox logs only"
	@echo "  make logs-glance        - Show Glance logs only"
	@echo ""
	@echo "Service Configuration:"
	@echo "  make glance-setup       - Create default Glance configuration"
	@echo "  make adguard-setup      - Configure DNS rewrites for domain-based access"
	@echo ""
	@echo "SSL Certificates:"
	@echo "  make regenerate-ssl     - Regenerate SSL certificates (optional)"
	@echo "  make regenerate-ssl DOMAIN=example.com - Regenerate with custom domain"
	@echo ""
	@echo "Validation & Cleanup:"
	@echo "  make validate           - Validate docker-compose configuration"
	@echo "  make clean              - Remove all containers and volumes (preserves ./data/)"
	@echo "  make purge              - Remove containers, volumes, AND ./data/ (WARNING: destroys ALL data)"
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

# Generate SSL certificates if they don't exist
ssl-check:
	@if [ ! -f ssl/server.key ] || [ ! -f ssl/server.crt ]; then \
		echo "Generating SSL certificates for n8n..."; \
		cd ssl && ./generate-cert.sh localhost 365; \
		echo "✓ SSL certificates generated"; \
	else \
		echo "✓ SSL certificates exist"; \
	fi

# Regenerate SSL certificates (optional - use custom domain)
# Usage: make regenerate-ssl DOMAIN=your-domain.com
regenerate-ssl:
	@echo "Regenerating SSL certificates..."
	@cd ssl && ./generate-cert.sh $(if $(DOMAIN),$(DOMAIN),localhost) 365
	@echo "✓ SSL certificates regenerated"
	@echo ""
	@echo "Note: Restart n8n for changes to take effect: make restart

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
setup: env-check ssl-check validate
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/5: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/5: Starting services..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 3/5: Configuring AdGuard DNS rewrites..."
	@$(MAKE) adguard-setup
	@echo ""
	@echo "Step 4/5: Setting up Glance dashboard..."
	@$(MAKE) glance-setup
	@echo ""
	@echo "Step 5/5: Setting up Bookwyrm..."
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Cloning bookwyrm-docker wrapper..."; \
		mkdir -p external; \
		cd external && git clone https://github.com/josephradford/bookwyrm-docker.git; \
		echo "✓ Bookwyrm wrapper cloned"; \
		echo ""; \
		echo "⚠️  Bookwyrm requires configuration:"; \
		echo "1. cd $(BOOKWYRM_DIR)"; \
		echo "2. cp .env.example .env"; \
		echo "3. Edit .env with your configuration"; \
		echo "4. Run: make bookwyrm-setup"; \
	elif [ ! -f "$(BOOKWYRM_DIR)/.env" ]; then \
		echo "⚠️  Bookwyrm not configured yet:"; \
		echo "1. cd $(BOOKWYRM_DIR)"; \
		echo "2. cp .env.example .env"; \
		echo "3. Edit .env with your configuration"; \
		echo "4. Run: make bookwyrm-setup"; \
	else \
		$(MAKE) bookwyrm-setup; \
	fi
	@echo ""
	@$(COMPOSE) ps
	@echo ""
	@echo "✓ Setup complete! Services are running."
	@echo ""
	@echo "Access your services:"
	@echo "  - AdGuard Home: http://$$SERVER_IP:80"
	@echo "  - n8n:          https://$$SERVER_IP:5678"
	@echo "  - Ollama API:   http://$$SERVER_IP:11434"
	@echo "  - Habitica:     http://$$SERVER_IP:8080"
	@echo "  - HortusFox:    http://$$SERVER_IP:8181"
	@echo "  - Glance:       http://$$SERVER_IP:8282"
	@echo "  - Grafana:      http://$$SERVER_IP:3001"
	@echo "  - Prometheus:   http://$$SERVER_IP:9090"
	@echo "  - Alertmanager: http://$$SERVER_IP:9093"
	@if [ -d "$(BOOKWYRM_DIR)" ] && [ -f "$(BOOKWYRM_DIR)/.env" ]; then \
		echo "  - Bookwyrm:     http://$$SERVER_IP:8000"; \
	fi
	@echo ""
	@if [ ! -d "$(BOOKWYRM_DIR)" ] || [ ! -f "$(BOOKWYRM_DIR)/.env" ]; then \
		echo "⚠️  To complete setup, configure and start Bookwyrm (see above)"; \
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
	@$(MAKE) bookwyrm-stop
	@$(COMPOSE) down
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

logs-habitica:
	@$(COMPOSE) logs -f habitica-client habitica-server habitica-mongo

logs-hortusfox:
	@$(COMPOSE) logs -f hortusfox hortusfox-db

logs-glance:
	@$(COMPOSE) logs -f glance

# Clean up all services (preserves ./data/)
clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@echo "Note: ./data/ directories will be preserved"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing all containers..."
	@$(COMPOSE) down -v
	@$(MAKE) bookwyrm-stop
	@echo "✓ Cleanup complete (./data/ preserved)"

# Purge everything including data (WARNING: destroys ALL data)
purge:
	@echo "⚠️  WARNING: This will DELETE EVERYTHING including all data in ./data/!"
	@echo "This includes:"
	@echo "  - All Docker containers and volumes"
	@echo "  - All Docker images (requires re-download on next setup)"
	@echo "  - AdGuard configuration and logs"
	@echo "  - n8n workflows and database"
	@echo "  - Ollama AI models"
	@echo "  - WireGuard VPN configs"
	@echo "  - Habitica database"
	@echo "  - HortusFox database and images"
	@echo "  - Bookwyrm data"
	@echo "  - All monitoring data (Grafana, Prometheus)"
	@echo ""
	@echo "💡 RECOMMENDATION: Back up your data before proceeding!"
	@echo "   tar -czf backup-$$(date +%Y%m%d-%H%M%S).tar.gz ./data/"
	@echo ""
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo ""
	@echo "⚠️  FINAL WARNING: This action CANNOT be undone!"
	@echo "Type 'DELETE' (in capitals) to confirm permanent deletion:"
	@read final_confirm; \
	if [ "$$final_confirm" != "DELETE" ]; then \
		echo "Purge cancelled - confirmation did not match"; \
		exit 1; \
	fi
	@echo "Stopping and removing all containers..."
	@$(COMPOSE) down -v
	@$(MAKE) bookwyrm-stop || true
	@echo "Removing all data directories..."
	@rm -rf ./data/
	@echo "Removing Bookwyrm data..."
	@if [ -d "$(BOOKWYRM_DIR)" ]; then \
		cd $(BOOKWYRM_DIR) && $(MAKE) clean || true; \
	fi
	@echo "Removing all Docker images..."
	@docker image prune -af
	@echo "✓ Purge complete - ALL DATA DELETED"

# Bookwyrm wrapper integration targets
# These commands delegate to the external bookwyrm-docker wrapper project
# Bookwyrm is a mandatory part of the stack

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
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@echo "Starting Bookwyrm..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) start

bookwyrm-stop:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@echo "Stopping Bookwyrm..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) stop

bookwyrm-restart:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@echo "Restarting Bookwyrm..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) restart

bookwyrm-status:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "Bookwyrm: Not installed (run: make setup)"; \
	else \
		cd $(BOOKWYRM_DIR) && $(MAKE) status; \
	fi

bookwyrm-logs:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@cd $(BOOKWYRM_DIR) && $(MAKE) logs

bookwyrm-update:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@echo "Updating Bookwyrm..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) update

bookwyrm-init:
	@if [ ! -d "$(BOOKWYRM_DIR)" ]; then \
		echo "ERROR: Bookwyrm wrapper not found. Run: make setup"; \
		exit 1; \
	fi
	@echo "Re-running Bookwyrm initialization..."
	@cd $(BOOKWYRM_DIR) && $(MAKE) init

# Glance dashboard setup
glance-setup:
	@echo "Setting up Glance dashboard..."
	@mkdir -p data/glance
	@if [ -d "data/glance/glance.yml" ]; then \
		echo "ERROR: data/glance/glance.yml exists as a directory!"; \
		echo "Removing directory..."; \
		rm -rf data/glance/glance.yml; \
	fi
	@if [ -f "data/glance/glance.yml" ]; then \
		echo "⚠️  Warning: data/glance/glance.yml already exists"; \
		echo "Backup existing config? (y/n)"; \
		read backup; \
		if [ "$$backup" = "y" ]; then \
			cp data/glance/glance.yml data/glance/glance.yml.backup.$$(date +%Y%m%d-%H%M%S); \
			echo "✓ Backup created"; \
		fi; \
	fi
	@echo "Creating default Glance configuration..."
	@echo 'pages:' > data/glance/glance.yml
	@echo '  - name: Home Server' >> data/glance/glance.yml
	@echo '    columns:' >> data/glance/glance.yml
	@echo '      - size: small' >> data/glance/glance.yml
	@echo '        widgets:' >> data/glance/glance.yml
	@echo '          - type: docker-containers' >> data/glance/glance.yml
	@echo '            sock-path: /var/run/docker.sock' >> data/glance/glance.yml
	@echo '            running-only: true' >> data/glance/glance.yml
	@echo '            format-container-names: true' >> data/glance/glance.yml
	@echo '            hide-by-default: false' >> data/glance/glance.yml
	@echo '' >> data/glance/glance.yml
	@echo '      - size: full' >> data/glance/glance.yml
	@echo '        widgets:' >> data/glance/glance.yml
	@echo '          - type: calendar' >> data/glance/glance.yml
	@echo '' >> data/glance/glance.yml
	@echo '          - type: bookmarks' >> data/glance/glance.yml
	@echo '            groups:' >> data/glance/glance.yml
	@echo '              - title: Core Services' >> data/glance/glance.yml
	@echo '                links:' >> data/glance/glance.yml
	@echo '                  - title: AdGuard Home' >> data/glance/glance.yml
	@echo '                    url: http://$$SERVER_IP:80' >> data/glance/glance.yml
	@echo '                  - title: n8n' >> data/glance/glance.yml
	@echo '                    url: https://$$SERVER_IP:5678' >> data/glance/glance.yml
	@echo '                  - title: Grafana' >> data/glance/glance.yml
	@echo '                    url: http://$$SERVER_IP:3001' >> data/glance/glance.yml
	@echo '              - title: Apps' >> data/glance/glance.yml
	@echo '                links:' >> data/glance/glance.yml
	@echo '                  - title: Habitica' >> data/glance/glance.yml
	@echo '                    url: http://$$SERVER_IP:8080' >> data/glance/glance.yml
	@echo '                  - title: Bookwyrm' >> data/glance/glance.yml
	@echo '                    url: http://$$SERVER_IP:8000' >> data/glance/glance.yml
	@echo '                  - title: HortusFox' >> data/glance/glance.yml
	@echo '                    url: http://$$SERVER_IP:8181' >> data/glance/glance.yml
	@echo "✓ Created data/glance/glance.yml"
	@echo ""
	@echo "Starting Glance service..."
	@$(COMPOSE) up -d glance
	@echo ""
	@echo "✓ Glance setup complete!"
	@echo "Access at: http://$$SERVER_IP:8282"
	@echo ""
	@echo "To customize your dashboard, edit: data/glance/glance.yml"
	@echo "Then restart: docker compose restart glance"

# AdGuard Home DNS rewrites setup
adguard-setup: env-check
	@echo "Setting up AdGuard DNS rewrites for domain-based access..."
	@./scripts/setup-adguard-dns.sh
	@echo ""
	@echo "Restarting AdGuard to apply configuration..."
	@$(COMPOSE) restart adguard
	@echo ""
	@echo "✓ AdGuard DNS setup complete!"
	@echo ""
	@echo "Testing DNS resolution..."
	@sleep 3
	@echo "Testing: glance.home.local"
	@dig @127.0.0.1 glance.home.local +short || true
	@echo ""
	@echo "All *.home.local domains should now resolve to $$SERVER_IP"
	@echo "Configure network devices to use $$SERVER_IP as DNS server"
