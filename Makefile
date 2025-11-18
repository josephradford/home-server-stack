# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build pull status clean purge validate env-check
.PHONY: logs-n8n logs-wireguard logs-homepage logs-homeassistant logs-actualbudget
.PHONY: adguard-setup homeassistant-setup wireguard-routing-setup setup-certs test-domain-access traefik-password
.PHONY: ssl-setup ssl-copy-certs ssl-configure-traefik ssl-setup-renewal ssl-renew-test
.PHONY: dashboard-setup dashboard-start dashboard-stop dashboard-restart dashboard-logs dashboard-status
.PHONY: local-setup local-start local-stop local-restart local-logs local-status local-clean deploy

# Compose file flags
# Services are organized into logical groups:
# - docker-compose.yml: Core services (AdGuard, n8n, Home Assistant, Actual Budget)
# - docker-compose.network.yml: Network & Security (Traefik, Wireguard, Fail2ban)
# - docker-compose.monitoring.yml: Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)
# - docker-compose.dashboard.yml: Dashboard (Homepage, Homepage API)
#
# COMPOSE_CORE: Core + Network + Monitoring (everything except dashboard)
# COMPOSE_DASHBOARD: Dashboard only (for dashboard-specific operations)
# COMPOSE: All services (default for most operations)
# COMPOSE_LOCAL: All services with local development overrides
COMPOSE_CORE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml
COMPOSE_DASHBOARD := docker compose -f docker-compose.dashboard.yml
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml
COMPOSE_LOCAL := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.local.yml --env-file .env.local

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (core + monitoring + dashboard)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo "  make deploy             - Deploy to remote server via SSH"
	@echo ""
	@echo "Local Development (Mac/Docker Desktop):"
	@echo "  make local-setup        - First time local setup (no SSL/DNS)"
	@echo "  make local-start        - Start services locally"
	@echo "  make local-stop         - Stop local services"
	@echo "  make local-restart      - Restart local services"
	@echo "  make local-logs         - View local service logs"
	@echo "  make local-status       - Show local service status"
	@echo "  make local-clean        - Remove local containers"
	@echo ""
	@echo "Service Management:"
	@echo "  make start              - Start all services (core + monitoring + dashboard)"
	@echo "  make stop               - Stop all services"
	@echo "  make restart            - Restart all services"
	@echo "  make status             - Show status of all services"
	@echo ""
	@echo "Updates & Maintenance:"
	@echo "  make update             - Update all services (pull latest images)"
	@echo "  make pull               - Pull latest images"
	@echo "  make build              - Build all services that require building"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from all services"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-homeassistant - Show Home Assistant logs only"
	@echo "  make logs-actualbudget  - Show Actual Budget logs only"
	@echo "  make logs-wireguard     - Show WireGuard logs only"
	@echo "  make logs-homepage      - Show Homepage logs only"
	@echo ""
	@echo "Dashboard Management:"
	@echo "  make dashboard-setup    - Setup and start Homepage dashboard"
	@echo "  make dashboard-start    - Start Homepage dashboard"
	@echo "  make dashboard-stop     - Stop Homepage dashboard"
	@echo "  make dashboard-restart  - Restart Homepage dashboard"
	@echo "  make dashboard-logs     - Show Homepage dashboard logs"
	@echo "  make dashboard-status   - Show Homepage dashboard status"
	@echo ""
	@echo "Service Configuration:"
	@echo "  make adguard-setup            - Configure DNS rewrites for domain-based access"
	@echo "  make homeassistant-setup      - Setup Home Assistant configuration files"
	@echo "  make wireguard-routing-setup  - Setup iptables routing for WireGuard VPN"
	@echo "  make traefik-password         - Generate Traefik dashboard password from .env"
	@echo ""
	@echo "SSL/TLS Certificate Management:"
	@echo "  make ssl-setup          - Complete Let's Encrypt SSL setup (certbot + renewal)"
	@echo "  make ssl-copy-certs     - Copy Let's Encrypt certs to Traefik"
	@echo "  make ssl-configure-traefik - Configure Traefik file provider for certs"
	@echo "  make ssl-setup-renewal  - Setup automatic certificate renewal"
	@echo "  make ssl-renew-test     - Test certificate renewal (dry run)"
	@echo ""
	@echo "Testing & Validation:"
	@echo "  make test-domain-access - Test domain-based access for all services"
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
	@echo "Step 1/8: Setting up Traefik dashboard password..."
	@ENV_FILE=.env ./scripts/setup-traefik-password.sh
	@echo ""
	@echo "Step 2/8: Setting up SSL certificate storage..."
	@$(MAKE) setup-certs
	@echo ""
	@echo "Step 3/8: Setting up Homepage dashboard config..."
	@ENV_FILE=.env FORCE_OVERWRITE=true ./scripts/configure-homepage.sh
	@echo ""
	@echo "Step 4/8: Setting up Home Assistant config..."
	@ENV_FILE=.env ./scripts/setup-homeassistant.sh
	@echo ""
	@echo "Step 5/8: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 6/8: Starting services (Docker Compose will create networks)..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 7/9: Fixing data directory permissions..."
	@echo "Containers create directories as root, fixing ownership for user access..."
	@if [ -d "data" ]; then \
		sudo chown -R $(shell id -u):$(shell getent group docker | cut -d: -f3) data/ && \
		echo "✓ Data directory permissions fixed"; \
	fi
	@echo ""
	@echo "Step 8/9: Setting up WireGuard VPN routing..."
	@./scripts/setup-wireguard-routing.sh
	@echo ""
	@echo "Step 9/9: Configuring AdGuard DNS rewrites..."
	@$(MAKE) adguard-setup
	@echo ""
	@$(COMPOSE) ps
	@echo ""
	@echo "✓ Setup complete! Services are running."
	@echo ""
	@echo "Access your services:"
	@set -a; . ./.env; set +a; \
	if [ -n "$$DOMAIN" ]; then \
		echo "  Via domain names:"; \
		echo "    - Homepage Dashboard: https://homepage.$$DOMAIN"; \
		echo "    - Traefik Dashboard:  https://traefik.$$DOMAIN"; \
		echo "    - AdGuard Home:       https://adguard.$$DOMAIN"; \
		echo "    - n8n:                https://n8n.$$DOMAIN"; \
		echo "    - Home Assistant:     https://home.$$DOMAIN"; \
		echo "    - Actual Budget:      https://actual.$$DOMAIN"; \
		echo "    - Grafana:            https://grafana.$$DOMAIN"; \
		echo "    - Prometheus:         https://prometheus.$$DOMAIN"; \
		echo "    - Alertmanager:       https://alerts.$$DOMAIN"; \
	else \
		echo "  ERROR: DOMAIN not set in .env file"; \
		echo "  Please set DOMAIN=your-domain.com in .env"; \
	fi
	@echo ""
	@echo "Note: First-time container initialization may take a few minutes."
	@echo "Check logs with: make logs"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@set -a; . ./.env; set +a; \
	if [ -n "$$GANDIV5_PERSONAL_ACCESS_TOKEN" ] && [ -n "$$ACME_EMAIL" ] && [ -n "$$DOMAIN" ]; then \
		echo "🔒 SSL Certificate Setup Available"; \
		echo ""; \
		echo "Your .env file is configured for Let's Encrypt SSL certificates."; \
		echo "Would you like to set up trusted SSL certificates now? (y/N)"; \
		read -r response; \
		if [ "$$response" = "y" ] || [ "$$response" = "Y" ]; then \
			$(MAKE) ssl-setup; \
		else \
			echo ""; \
			echo "Skipping SSL setup. Your services will use self-signed certificates."; \
			echo "You can set up Let's Encrypt SSL later with: make ssl-setup"; \
			echo "See docs/CONFIGURATION.md#ssl-certificate-setup for details."; \
		fi; \
	else \
		echo "ℹ️  Using self-signed SSL certificates (browser warnings expected)"; \
		echo ""; \
		echo "For trusted Let's Encrypt certificates, add to .env:"; \
		echo "  - DOMAIN=your-domain.com"; \
		echo "  - ACME_EMAIL=your-email@example.com"; \
		echo "  - GANDIV5_PERSONAL_ACCESS_TOKEN=your-gandi-token"; \
		echo ""; \
		echo "Then run: make ssl-setup"; \
		echo "See docs/CONFIGURATION.md#ssl-certificate-setup for details."; \
	fi
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

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
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Start all services
start: env-check
	@echo "Starting all services..."
	@$(COMPOSE) up -d
	@echo "✓ All services started"

# Stop all services
stop:
	@echo "Stopping all services..."
	@$(COMPOSE) down
	@echo "✓ All services stopped"

# Restart all services
restart: env-check
	@echo "Restarting all services..."
	@$(COMPOSE) restart
	@echo "✓ All services restarted"

# Show service status
status:
	@$(COMPOSE) ps

# View logs from all services
logs:
	@$(COMPOSE) logs -f

# View logs from specific services
logs-n8n:
	@$(COMPOSE) logs -f n8n

logs-homeassistant:
	@$(COMPOSE) logs -f homeassistant

logs-actualbudget:
	@$(COMPOSE) logs -f actualbudget

logs-wireguard:
	@$(COMPOSE) logs -f wireguard

logs-homepage:
	@$(COMPOSE_DASHBOARD) logs -f homepage

# Clean up all services (preserves ./data/)
clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@echo "Note: ./data/ directories will be preserved"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "Stopping and removing all containers..."
	@$(COMPOSE) down -v
	@echo "✓ Cleanup complete (./data/ preserved)"

# Purge everything including data (WARNING: destroys ALL data)
purge:
	@echo "⚠️  WARNING: This will DELETE EVERYTHING including all data in ./data/!"
	@echo "This includes:"
	@echo "  - All Docker containers and volumes"
	@echo "  - All Docker images (requires re-download on next setup)"
	@echo "  - AdGuard configuration and logs"
	@echo "  - n8n workflows and database"
	@echo "  - Home Assistant configuration and database"
	@echo "  - Actual Budget financial data and budgets"
	@echo "  - WireGuard VPN configs"
	@echo "  - All monitoring data (Grafana, Prometheus)"
	@echo "  - Homepage dashboard configuration"
	@echo "  - Let's Encrypt SSL certificates and renewal hooks"
	@echo "  - Generated Traefik SSL configuration (dynamic-certs.yml)"
	@echo ""
	@echo "💡 RECOMMENDATION: Back up your data before proceeding!"
	@echo "   tar -czf backup-$$(date +%Y%m%d-%H%M%S).tar.gz ./data/ .env"
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
	@echo "Removing all data directories..."
	@rm -rf ./data/
	@echo "Removing generated Traefik configuration..."
	@rm -rf ./config/traefik/
	@echo "Removing Let's Encrypt certificates and configuration..."
	@sudo rm -rf /etc/letsencrypt/
	@echo "Removing SSL renewal hook..."
	@sudo rm -f /var/log/certbot-traefik-reload.log
	@echo "Removing all Docker images..."
	@docker image prune -af
	@echo "✓ Purge complete - ALL DATA DELETED"

# AdGuard Home DNS rewrites setup
adguard-setup: env-check
	@echo "Setting up AdGuard DNS rewrites for domain-based access..."
	@./scripts/setup-adguard-dns.sh
	@echo ""
	@echo "Restarting AdGuard to apply configuration..."
	@$(COMPOSE_CORE) restart adguard
	@echo ""
	@echo "✓ AdGuard DNS setup complete!"
	@echo ""
	@echo "Testing DNS resolution..."
	@sleep 3
	@set -a; . ./.env; set +a; \
	if [ -n "$$DOMAIN" ]; then \
		echo "Testing: n8n.$$DOMAIN"; \
		dig @$$SERVER_IP n8n.$$DOMAIN +short || true; \
		echo ""; \
		echo "All *.$$DOMAIN domains should now resolve to $$SERVER_IP"; \
	else \
		echo "ERROR: DOMAIN not set in .env"; \
	fi
	@set -a; . ./.env; set +a; \
	echo "Configure network devices to use $$SERVER_IP as DNS server"

# Home Assistant configuration setup
homeassistant-setup: env-check
	@echo "Setting up Home Assistant configuration..."
	@./scripts/setup-homeassistant.sh
	@echo ""
	@echo "✓ Home Assistant configuration setup complete!"

# WireGuard VPN routing setup
wireguard-routing-setup: env-check
	@echo "Setting up WireGuard VPN routing (iptables forwarding rules)..."
	@./scripts/setup-wireguard-routing.sh

# Setup SSL certificate storage (for certbot-generated certs)
setup-certs:
	@echo "Setting up SSL certificate storage..."
	@mkdir -p data/traefik/certs
	@mkdir -p config/traefik
	@echo "✓ Certificate storage configured"

# Test domain-based access for all services
test-domain-access: env-check
	@echo "Testing domain-based access..."
	@./scripts/test-domain-access.sh

# Setup Traefik dashboard password
traefik-password: env-check
	@echo "Setting up Traefik dashboard password..."
	@ENV_FILE=.env ./scripts/setup-traefik-password.sh
	@echo ""
	@echo "Restarting Traefik to apply new password..."
	@$(COMPOSE_CORE) stop traefik
	@$(COMPOSE_CORE) rm -f traefik
	@$(COMPOSE_CORE) up -d traefik
	@echo "✓ Traefik password updated and service restarted"

# Let's Encrypt SSL Certificate Setup with certbot
# Note: Uses certbot instead of Traefik's built-in ACME due to compatibility issues
# with Gandi API v5 in Traefik's Lego library (v4.21.0)
ssl-setup: env-check
	@echo "==================================================="
	@echo "Let's Encrypt SSL Setup with certbot + Gandi DNS"
	@echo "==================================================="
	@echo ""
	@echo "This will:"
	@echo "  1. Install certbot and Gandi DNS plugin"
	@echo "  2. Generate wildcard certificate for *.DOMAIN and DOMAIN"
	@echo "  3. Copy certificates to Traefik directory"
	@echo "  4. Configure Traefik to use file provider"
	@echo "  5. Setup automatic certificate renewal"
	@echo ""
	@echo "Prerequisites:"
	@echo "  - DOMAIN must be set in .env"
	@echo "  - ACME_EMAIL must be set in .env"
	@echo "  - GANDIV5_PERSONAL_ACCESS_TOKEN must be set in .env"
	@echo "  - Domain must be hosted on Gandi"
	@echo ""
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo ""
	@echo "Step 1/5: Installing certbot and generating certificate..."
	@./scripts/setup-certbot-gandi.sh
	@echo ""
	@echo "Step 2/5: Copying certificates to Traefik..."
	@./scripts/copy-certs-to-traefik.sh
	@echo ""
	@echo "Step 3/5: Configuring Traefik file provider..."
	@./scripts/configure-traefik-file-provider.sh
	@echo ""
	@echo "Step 4/5: Recreating Traefik container with new configuration..."
	@$(COMPOSE_CORE) stop traefik
	@$(COMPOSE_CORE) rm -f traefik
	@$(COMPOSE_CORE) up -d traefik
	@sleep 5
	@echo ""
	@echo "Step 5/5: Setting up automatic renewal..."
	@./scripts/setup-cert-renewal.sh
	@echo ""
	@echo "==================================================="
	@echo "✓ SSL Setup Complete!"
	@echo "==================================================="
	@echo ""
	@echo "Your services are now secured with Let's Encrypt SSL certificates!"
	@echo ""
	@set -a; . ./.env; set +a; \
	if [ -n "$$DOMAIN" ]; then \
		echo "Test your certificates:"; \
		echo "  https://n8n.$$DOMAIN"; \
		echo "  https://home.$$DOMAIN"; \
		echo "  https://actual.$$DOMAIN"; \
		echo "  https://grafana.$$DOMAIN"; \
		echo "  https://traefik.$$DOMAIN"; \
	fi
	@echo ""
	@echo "Certificates will auto-renew every 90 days."
	@echo "Check renewal logs: sudo tail -f /var/log/certbot-traefik-reload.log"

# Copy Let's Encrypt certificates to Traefik directory
ssl-copy-certs: env-check
	@echo "Copying Let's Encrypt certificates to Traefik..."
	@./scripts/copy-certs-to-traefik.sh

# Configure Traefik to use file provider for certificates
ssl-configure-traefik: env-check
	@echo "Configuring Traefik file provider..."
	@./scripts/configure-traefik-file-provider.sh
	@echo ""
	@echo "Restarting Traefik to apply configuration..."
	@$(COMPOSE_CORE) stop traefik
	@$(COMPOSE_CORE) rm -f traefik
	@$(COMPOSE_CORE) up -d traefik
	@sleep 3
	@echo "✓ Traefik configured and restarted"

# Setup automatic certificate renewal
ssl-setup-renewal: env-check
	@echo "Setting up automatic certificate renewal..."
	@./scripts/setup-cert-renewal.sh

# Test certificate renewal (dry run)
ssl-renew-test:
	@echo "Testing certificate renewal (dry run)..."
	@echo "This will simulate renewal without actually renewing certificates."
	@echo ""
	@sudo certbot renew --dry-run

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dashboard Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Setup Homepage dashboard (first time)
dashboard-setup: env-check
	@echo "Setting up Homepage Dashboard..."
	@echo ""
	@echo "Step 1/3: Creating config directory..."
	@mkdir -p data/homepage/config
	@echo "✓ Config directory created"
	@echo ""
	@echo "Step 2/3: Generating Homepage configuration files..."
	@./scripts/configure-homepage.sh
	@echo ""
	@echo "Step 3/3: Starting Homepage dashboard (Docker Compose will create network)..."
	@$(COMPOSE_DASHBOARD) up -d
	@echo ""
	@echo "✓ Homepage Dashboard setup complete!"
	@echo ""
	@set -a; . ./.env; set +a; \
	echo "Access your dashboard at: https://homepage.$$DOMAIN"
	@echo ""
	@echo "Check logs with: make dashboard-logs"

# Start Homepage dashboard
dashboard-start: env-check
	@echo "Starting Homepage dashboard..."
	@$(COMPOSE_DASHBOARD) up -d
	@echo "✓ Homepage dashboard started"
	@set -a; . ./.env; set +a; \
	echo "Access at: https://homepage.$$DOMAIN"

# Stop Homepage dashboard
dashboard-stop:
	@echo "Stopping Homepage dashboard..."
	@$(COMPOSE_DASHBOARD) down
	@echo "✓ Homepage dashboard stopped"

# Restart Homepage dashboard
dashboard-restart: env-check
	@echo "Restarting Homepage dashboard..."
	@$(COMPOSE_DASHBOARD) restart
	@echo "✓ Homepage dashboard restarted"

# Show Homepage dashboard logs
dashboard-logs:
	@$(COMPOSE_DASHBOARD) logs -f homepage

# Show Homepage dashboard status
dashboard-status:
	@$(COMPOSE_DASHBOARD) ps

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Local Development (Mac/Docker Desktop)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Setup local development environment
local-setup:
	@echo "Setting up local development environment..."
	@if [ ! -f .env.local ]; then \
		echo "Creating .env.local from .env.local.example..."; \
		cp .env.local.example .env.local; \
		echo "✓ .env.local created"; \
		echo ""; \
		echo "Please edit .env.local if needed (default values should work)"; \
	else \
		echo "✓ .env.local already exists"; \
	fi
	@echo ""
	@echo "Validating local configuration..."
	@$(COMPOSE_LOCAL) config --quiet
	@echo "✓ Configuration valid"
	@echo ""
	@echo "Creating data directories..."
	@mkdir -p data/n8n data/homeassistant data/actualbudget data/grafana data/prometheus data/alertmanager data/homepage/config data/traefik
	@echo "✓ Data directories created"
	@echo ""
	@echo "Setting up Homepage configuration..."
	@ENV_FILE=.env.local FORCE_OVERWRITE=true ./scripts/configure-homepage.sh
	@echo ""
	@echo "Setting up Home Assistant configuration..."
	@ENV_FILE=.env.local ./scripts/setup-homeassistant.sh
	@echo ""
	@echo "Starting local services..."
	@$(COMPOSE_LOCAL) up -d
	@echo ""
	@echo "✓ Local development environment ready!"
	@echo ""
	@echo "Access your services:"
	@echo "  - Homepage Dashboard:  http://localhost:3000"
	@echo "  - Traefik Dashboard:   http://localhost:8080"
	@echo "  - n8n:                 http://localhost:5678"
	@echo "  - Home Assistant:      http://localhost:8123"
	@echo "  - Actual Budget:       http://localhost:5006"
	@echo "  - Grafana:             http://localhost:3001"
	@echo "  - Prometheus:          http://localhost:9090"
	@echo "  - Alertmanager:        http://localhost:9093"
	@echo ""
	@echo "Note: AdGuard, WireGuard, and Fail2ban are disabled in local mode"
	@echo ""
	@echo "Commands:"
	@echo "  - make local-logs      - View logs"
	@echo "  - make local-status    - Check service status"
	@echo "  - make local-stop      - Stop all services"

# Start local development services
local-start:
	@if [ ! -f .env.local ]; then \
		echo "ERROR: .env.local not found"; \
		echo "Run: make local-setup"; \
		exit 1; \
	fi
	@echo "Starting local development services..."
	@$(COMPOSE_LOCAL) up -d
	@echo "✓ Services started"
	@echo ""
	@echo "Access at: http://localhost:3000 (Homepage)"

# Stop local development services
local-stop:
	@echo "Stopping local development services..."
	@$(COMPOSE_LOCAL) down
	@echo "✓ Services stopped"

# Restart local development services
local-restart:
	@echo "Restarting local development services..."
	@$(COMPOSE_LOCAL) restart
	@echo "✓ Services restarted"

# View local development logs
local-logs:
	@$(COMPOSE_LOCAL) logs -f

# Show local development service status
local-status:
	@$(COMPOSE_LOCAL) ps

# Clean local development environment
local-clean:
	@echo "Removing local development containers..."
	@$(COMPOSE_LOCAL) down -v
	@echo "✓ Local containers removed"
	@echo ""
	@echo "Note: ./data/ directories preserved"
	@echo "To remove data: rm -rf ./data/"

# Deploy to remote server
deploy:
	@if [ -z "$(SERVER)" ]; then \
		echo "ERROR: SERVER variable required"; \
		echo ""; \
		echo "Usage: make deploy SERVER=user@host [BRANCH=main]"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make deploy SERVER=joe@192.168.1.100"; \
		echo "  make deploy SERVER=joe@homeserver.local BRANCH=feature/new-service"; \
		echo ""; \
		exit 1; \
	fi
	@./scripts/deploy-to-server.sh $(SERVER) $(BRANCH)
