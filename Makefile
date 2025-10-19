# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build pull status clean purge validate env-check
.PHONY: logs-n8n logs-wireguard logs-homepage
.PHONY: adguard-setup setup-certs test-domain-access traefik-password
.PHONY: ssl-setup ssl-copy-certs ssl-configure-traefik ssl-setup-renewal ssl-renew-test
.PHONY: dashboard-setup dashboard-start dashboard-stop dashboard-restart dashboard-logs dashboard-status

# Compose file flags
# COMPOSE_CORE: Base services + monitoring only
# COMPOSE: All services including dashboard (default for most operations)
# COMPOSE_DASHBOARD: Dashboard only (for dashboard-specific operations)
COMPOSE_CORE := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml
COMPOSE_DASHBOARD := docker compose -f docker-compose.dashboard.yml
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (core + monitoring + dashboard)"
	@echo "  make env-check          - Verify .env file exists and is configured"
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
	@echo "  make adguard-setup      - Configure DNS rewrites for domain-based access"
	@echo "  make traefik-password   - Generate Traefik dashboard password from .env"
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
	@echo "Step 1/6: Setting up Traefik dashboard password..."
	@./scripts/setup-traefik-password.sh
	@echo ""
	@echo "Step 2/6: Setting up SSL certificate storage..."
	@$(MAKE) setup-certs
	@echo ""
	@echo "Step 3/6: Setting up Homepage dashboard config..."
	@mkdir -p data/homepage/config
	@if [ ! -f "data/homepage/config/settings.yaml" ]; then \
		echo "⚠️  Warning: Homepage config files not found in data/homepage/config/"; \
		echo "Dashboard will not start correctly without configuration files."; \
		echo "See tickets/dashboard-tickets/ticket_02_homepage_dashboard.md for setup."; \
	else \
		echo "✓ Homepage configuration found"; \
	fi
	@echo ""
	@echo "Step 4/6: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 5/6: Starting services (Docker Compose will create networks)..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 6/6: Configuring AdGuard DNS rewrites..."
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
		echo "    - Traefik Dashboard: https://traefik.$$DOMAIN"; \
		echo "    - AdGuard Home:      https://adguard.$$DOMAIN"; \
		echo "    - n8n:               https://n8n.$$DOMAIN"; \
		echo "    - Grafana:           https://grafana.$$DOMAIN"; \
		echo "    - Prometheus:        https://prometheus.$$DOMAIN"; \
		echo "    - Alertmanager:      https://alerts.$$DOMAIN"; \
		echo ""; \
		echo "  Via IP address:"; \
		echo "    - Homepage Dashboard: http://$$SERVER_IP:3100"; \
	else \
		echo "  ERROR: DOMAIN not set in .env file"; \
		echo "  Please set DOMAIN=your-domain.com in .env"; \
		echo ""; \
		echo "  Via IP address:"; \
		echo "    - Homepage Dashboard: http://$$SERVER_IP:3100"; \
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
	@echo "  - WireGuard VPN configs"
	@echo "  - All monitoring data (Grafana, Prometheus)"
	@echo "  - Homepage dashboard configuration"
	@echo "  - Let's Encrypt SSL certificates and renewal hooks"
	@echo "  - Traefik configuration files"
	@echo ""
	@echo "💡 RECOMMENDATION: Back up your data before proceeding!"
	@echo "   tar -czf backup-$$(date +%Y%m%d-%H%M%S).tar.gz ./data/ ./config/"
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
	@echo "Removing Traefik configuration..."
	@rm -rf ./config/
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
	@./scripts/setup-traefik-password.sh
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
	@echo "Step 1/2: Creating config directory and verifying files..."
	@mkdir -p data/homepage/config
	@if [ ! -f "data/homepage/config/settings.yaml" ]; then \
		echo "✗ Configuration files not found!"; \
		echo ""; \
		echo "Homepage config files should be in data/homepage/config/:"; \
		echo "  - settings.yaml"; \
		echo "  - widgets.yaml"; \
		echo "  - docker.yaml"; \
		echo "  - bookmarks.yaml"; \
		echo "  - services.yaml"; \
		echo ""; \
		echo "These files should have been created during Ticket 02 implementation."; \
		exit 1; \
	fi
	@echo "✓ Configuration files found"
	@echo ""
	@echo "Step 2/2: Starting Homepage dashboard (Docker Compose will create network)..."
	@$(COMPOSE_DASHBOARD) up -d
	@echo ""
	@echo "✓ Homepage Dashboard setup complete!"
	@echo ""
	@set -a; . ./.env; set +a; \
	echo "Access your dashboard at: http://$$SERVER_IP:3100"
	@echo ""
	@echo "Check logs with: make dashboard-logs"

# Start Homepage dashboard
dashboard-start: env-check
	@echo "Starting Homepage dashboard..."
	@$(COMPOSE_DASHBOARD) up -d
	@echo "✓ Homepage dashboard started"
	@set -a; . ./.env; set +a; \
	echo "Access at: http://$$SERVER_IP:3100"

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
