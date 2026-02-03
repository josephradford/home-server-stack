# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build build-custom pull status clean purge validate env-check
.PHONY: logs-n8n logs-homepage
.PHONY: openclaw-install openclaw-status openclaw-logs setup-certs test-domain-access
.PHONY: wireguard-status wireguard-install wireguard-setup wireguard-check
.PHONY: ssl-setup ssl-renew-test

# Compose file flags
# Services are organized into logical groups:
# - docker-compose.yml: Core services (AdGuard, n8n)
# - docker-compose.network.yml: Network & Security (Traefik, Fail2ban)
# - docker-compose.monitoring.yml: Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)
# - docker-compose.dashboard.yml: Dashboard (Homepage, Homepage API)
#
# NOTE: WireGuard is now a system service, not Docker service
# Install with: sudo ./scripts/wireguard/install-wireguard.sh
# Check status: make wireguard-status
#
# COMPOSE_CORE: Core + Network + Monitoring (used for operations that shouldn't restart dashboard)
# COMPOSE: All services including dashboard (default for most operations)
COMPOSE_CORE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml

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
	@echo "  make build-custom       - Build only custom services (faster for development)"
	@echo ""
	@echo "Logs & Debugging:"
	@echo "  make logs               - Show logs from all services"
	@echo "  make logs-n8n           - Show n8n logs only"
	@echo "  make logs-homepage      - Show Homepage logs only"
	@echo "OpenClaw AI Assistant (Native Install):"
	@echo "  make openclaw-install         - Install OpenClaw natively on the server"
	@echo "  make openclaw-status          - Check OpenClaw service status"
	@echo "  make openclaw-logs            - View OpenClaw gateway logs"
	@echo ""
	@echo "WireGuard VPN Management:"
	@echo "  make wireguard-install        - Install WireGuard packages (one-time, requires sudo)"
	@echo "  make wireguard-setup          - Create config and start service (requires sudo)"
	@echo "  make wireguard-status         - Check WireGuard service status"
	@echo ""
	@echo "SSL/TLS Certificate Management:"
	@echo "  make ssl-setup          - Complete Let's Encrypt SSL setup (certbot + renewal)"
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

# Build only custom services (faster rebuild during development)
build-custom: validate
	@echo "Building custom services from source..."
	@$(COMPOSE) build homepage-api
	@echo "✓ Custom services built"

# Pull latest images for services using pre-built images
pull: validate
	@echo "Pulling latest Docker images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo "✓ Images pulled"

# First time setup
setup: env-check validate wireguard-check
	@echo "Starting first-time setup..."
	@echo ""
	@echo "Step 1/8: Setting up Traefik dashboard password..."
	@./scripts/traefik/setup-traefik-password.sh
	@echo ""
	@echo "Step 2/8: Setting up SSL certificate storage..."
	@$(MAKE) setup-certs
	@echo ""
	@echo "Step 3/8: Setting up Homepage dashboard config..."
	@./scripts/homepage/configure-homepage.sh
	@echo ""
	@echo "Step 4/8: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 5/8: Building custom services from source..."
	@$(COMPOSE) build homepage-api
	@echo ""
	@echo "Step 6/8: Starting services (Docker Compose will create networks)..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 7/8: Fixing data directory permissions..."
	@echo "Containers create directories as root, fixing ownership for user access..."
	@if [ -d "data" ]; then \
		sudo chown -R $(shell id -u):$(shell getent group docker | cut -d: -f3) data/ && \
		echo "✓ Data directory permissions fixed"; \
	fi
	@echo ""
	@echo "Step 8/8: Configuring AdGuard DNS rewrites..."
	@./scripts/adguard/setup-adguard-dns.sh
	@$(COMPOSE_CORE) restart adguard
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

# Check WireGuard is running (required for all Docker operations)
wireguard-check:
	@if ! systemctl is-active --quiet wg-quick@wg0; then \
		echo "❌ ERROR: WireGuard VPN is not running!"; \
		echo ""; \
		echo "WireGuard must be running before starting Docker services."; \
		echo "This ensures your remote VPN access survives Docker restarts."; \
		echo ""; \
		echo "To set up WireGuard:"; \
		echo ""; \
		echo "1. Install WireGuard (one-time):"; \
		echo "   make wireguard-install"; \
		echo ""; \
		echo "2. Create server configuration:"; \
		echo "   sudo ./scripts/wireguard/setup-wireguard-server.sh"; \
		echo ""; \
		echo "3. Enable and start the service:"; \
		echo "   sudo systemctl enable --now wg-quick@wg0"; \
		echo ""; \
		echo "4. Verify it's running:"; \
		echo "   make wireguard-status"; \
		echo ""; \
		exit 1; \
	fi

# Update all services
update: env-check validate wireguard-check
	@echo "Updating all services..."
	@echo ""
	@echo "Step 1/3: Pulling latest images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 2/3: Building custom services from source..."
	@$(COMPOSE) build homepage-api
	@echo ""
	@echo "Step 3/3: Restarting services with new images..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "✓ Update complete! All services restarted with latest versions."
	@echo ""
	@echo "Check status with: make status"

# Start all services
start: env-check wireguard-check
	@echo "Starting all services..."
	@$(COMPOSE) up -d
	@echo "✓ All services started"

# Stop all services
stop:
	@echo "Stopping all services..."
	@$(COMPOSE) down
	@echo "✓ All services stopped"

# Restart all services
restart: env-check wireguard-check
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

logs-homepage:
	@$(COMPOSE) logs -f homepage

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
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OpenClaw AI Assistant (Native Installation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Install OpenClaw natively on the server
openclaw-install:
	@echo "═════════════════════════════════════════════════════════════════"
	@echo "OpenClaw AI Assistant - Native Installation"
	@echo "═════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "This will install OpenClaw as a native system service (not Docker)."
	@echo ""
	@echo "Prerequisites:"
	@echo "  - Node.js 22 or higher (check with: node --version)"
	@echo "  - Anthropic API key (get from console.anthropic.com)"
	@echo "  - Telegram Bot Token (get from @BotFather)"
	@echo ""
	@echo "Installation steps:"
	@echo "  1. Check Node.js version"
	@echo "  2. Install OpenClaw using official installer"
	@echo "  3. Run onboarding wizard (interactive)"
	@echo "  4. Configure Telegram bot"
	@echo "  5. Start gateway as systemd service"
	@echo ""
	@echo "═════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Step 1: Checking Node.js version..."
	@node --version || { \
		echo ""; \
		echo "❌ Node.js not found or version too old."; \
		echo ""; \
		echo "Install Node.js 22:"; \
		echo "  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -"; \
		echo "  sudo apt-get install -y nodejs"; \
		echo ""; \
		exit 1; \
	}
	@echo ""
	@echo "Step 2: Installing OpenClaw..."
	@curl -fsSL https://openclaw.ai/install.sh | bash
	@echo ""
	@echo "Step 3: Running onboarding wizard..."
	@echo ""
	@echo "⚠️  IMPORTANT: During onboarding you'll be asked for:"
	@echo "  - AI provider: Choose Anthropic"
	@echo "  - API key: Provide your Anthropic API key"
	@echo "  - Model: Recommend claude-sonnet-4-5"
	@echo "  - Channel: Choose Telegram"
	@echo "  - Mode: LONG-POLLING (default - no webhook needed)"
	@echo "  - Bot Token: Provide your Telegram Bot Token from @BotFather"
	@echo "  - Daemon: Enable installation (--install-daemon)"
	@echo ""
	@echo "Press Enter to continue to onboarding wizard..."
	@read confirm
	@echo ""
	@openclaw onboard --install-daemon
	@echo ""
	@echo "Step 4: Starting OpenClaw gateway..."
	@openclaw gateway start
	@echo ""
	@echo "═════════════════════════════════════════════════════════════════"
	@echo "✓ OpenClaw Installation Complete!"
	@echo "═════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "OpenClaw is now running as a systemd service."
	@echo ""
	@echo "Next steps:"
	@echo "  1. Test your Telegram bot by sending it a message"
	@echo "  2. Check status: make openclaw-status"
	@echo "  3. View logs: make openclaw-logs"
	@echo ""
	@set -a; . ./.env; set +a; \
	echo "Web UI access: http://$$SERVER_IP:18789"
	@echo ""
	@echo "Useful commands:"
	@echo "  openclaw gateway status    # Check gateway status"
	@echo "  openclaw health            # Health check"
	@echo "  journalctl --user -u openclaw-gateway -f  # View logs"
	@echo ""

# Check OpenClaw service status
openclaw-status:
	@echo "Checking OpenClaw status..."
	@openclaw gateway status && openclaw health

# View OpenClaw gateway logs
openclaw-logs:
	@echo "Viewing OpenClaw logs..."
	@echo "Press Ctrl+C to stop following logs"
	@echo ""
	@journalctl --user -u openclaw-gateway -f

# WireGuard VPN Management (System Service)
wireguard-status:
	@echo "Checking WireGuard service status..."
	@systemctl is-active wg-quick@wg0 > /dev/null 2>&1 && echo "✓ WireGuard is running" || echo "✗ WireGuard is not running"
	@systemctl is-enabled wg-quick@wg0 > /dev/null 2>&1 && echo "✓ WireGuard is enabled" || echo "✗ WireGuard is not enabled"
	@echo ""
	@echo "For detailed status:"
	@echo "  sudo wg show"
	@echo "  sudo systemctl status wg-quick@wg0"

wireguard-install:
	@echo "Installing WireGuard as a system service..."
	@echo ""
	@echo "This script requires sudo. You will be prompted for your password."
	@sudo ./scripts/wireguard/install-wireguard.sh

wireguard-setup: env-check
	@echo "Setting up WireGuard VPN server..."
	@echo ""
	@echo "This script requires sudo. You will be prompted for your password."
	@echo ""
	@sudo ./scripts/wireguard/setup-wireguard-server.sh
	@echo ""
	@echo "Enabling and starting WireGuard service..."
	@sudo systemctl enable --now wg-quick@wg0
	@echo ""
	@echo "✓ WireGuard setup complete!"
	@echo ""
	@make wireguard-status
	@echo ""
	@echo "Next: Add VPN peers"
	@echo "  sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>"

# Setup SSL certificate storage (for certbot-generated certs)
setup-certs:
	@echo "Setting up SSL certificate storage..."
	@mkdir -p data/traefik/certs
	@mkdir -p config/traefik
	@echo "✓ Certificate storage configured"

# Test domain-based access for all services
test-domain-access: env-check
	@echo "Testing domain-based access..."
	@./scripts/testing/test-domain-access.sh

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
	@./scripts/ssl/setup-certbot-gandi.sh
	@echo ""
	@echo "Step 2/5: Copying certificates to Traefik..."
	@./scripts/ssl/copy-certs-to-traefik.sh
	@echo ""
	@echo "Step 3/5: Configuring Traefik file provider..."
	@./scripts/traefik/configure-traefik-file-provider.sh
	@echo ""
	@echo "Step 4/5: Recreating Traefik container with new configuration..."
	@$(COMPOSE_CORE) stop traefik
	@$(COMPOSE_CORE) rm -f traefik
	@$(COMPOSE_CORE) up -d traefik
	@sleep 5
	@echo ""
	@echo "Step 5/5: Setting up automatic renewal..."
	@./scripts/ssl/setup-cert-renewal.sh
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

# Test certificate renewal (dry run)
ssl-renew-test:
	@echo "Testing certificate renewal (dry run)..."
	@echo "This will simulate renewal without actually renewing certificates."
	@echo ""
	@sudo certbot renew --dry-run

