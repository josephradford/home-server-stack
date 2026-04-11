# Home Server Stack Makefile
# Simplifies deployment and maintenance operations

.PHONY: help setup update start stop restart logs build build-custom pull status clean purge validate env-check
.PHONY: logs-n8n logs-homepage logs-bede logs-hae
.PHONY: setup-certs test-domain-access
.PHONY: wireguard-status wireguard-install wireguard-setup wireguard-routing wireguard-test wireguard-peers wireguard-check
.PHONY: ssl-setup ssl-renew-test
.PHONY: ddns-setup ddns-update ddns-status
.PHONY: bede-start bede-stop bede-restart bede-build bede-status
.PHONY: hae-start hae-stop hae-restart hae-build hae-status

# Compose file flags
# Services are organized into logical groups:
# - docker-compose.yml: Core services (AdGuard, n8n)
# - docker-compose.network.yml: Network & Security (Traefik, Fail2ban)
# - docker-compose.monitoring.yml: Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)  
# - docker-compose.dashboard.yml: Dashboard (Homepage, Homepage API)
# - docker-compose.ai.yml: AI services (Bede, workspace-mcp)
# - docker-compose.health.yml: Health services (hae-server, hae-mongo)
#
# NOTE: WireGuard is now a system service, not Docker service
# Install with: sudo ./scripts/wireguard/install-wireguard.sh
# Check status: make wireguard-status
#
# COMPOSE_CORE: Core + Network + Monitoring (used for operations that shouldn't restart dashboard or AI)
# COMPOSE: All services including dashboard and AI (default for most operations)
COMPOSE_CORE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.ai.yml -f docker-compose.health.yml

# Default target - show help
help:
	@echo "Home Server Stack - Available Commands"
	@echo ""
	@echo "Server Prerequisites (run once on a brand new machine, requires sudo):"
	@echo "  ./scripts/system/install-docker-official.sh       - Replace snap Docker with official Docker CE"
	@echo "  ./scripts/system/setup-user-permissions.sh        - Add user to docker group (requires logout)"
	@echo "  ./scripts/system/setup-firewall.sh               - Configure UFW firewall rules"
	@echo ""
	@echo "Setup & Deployment:"
	@echo "  make setup              - First time setup (core + monitoring + dashboard)"
	@echo "  make env-check          - Verify .env file exists and is configured"
	@echo ""
	@echo "Service Management:"
	@echo "  make start              - Start all services"
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
	@echo "  make logs-bede          - Show Bede logs only"
	@echo "  make logs-hae           - Show hae-server and hae-mongo logs only"
	@echo ""
	@echo "Health Auto Export (Individual Service Management):"
	@echo "  make hae-build          - Build hae-server Docker image"
	@echo "  make hae-start          - Start health services only"
	@echo "  make hae-stop           - Stop health services only"
	@echo "  make hae-restart        - Restart health services only"
	@echo "  make hae-status         - Show health container status"
	@echo ""
	@echo "Bede AI Assistant (Individual Service Management):"
	@echo "  make bede-build         - Build Bede Docker image"
	@echo "  make bede-start         - Start Bede AI services only"
	@echo "  make bede-stop          - Stop Bede AI services only"
	@echo "  make bede-restart       - Restart Bede AI services only"
	@echo "  make bede-status        - Show Bede AI container status"
	@echo ""
	@echo "WireGuard VPN Management:"
	@echo "  make wireguard-install  - Install WireGuard packages (one-time, requires sudo)"
	@echo "  make wireguard-setup    - Create server config and start service (requires sudo)"
	@echo "  make wireguard-routing  - Set up Docker bridge forwarding for VPN clients (run after make start)"
	@echo "  make wireguard-peers    - List, view, and manage VPN peers"
	@echo "  make wireguard-test     - Test VPN routing and connectivity"
	@echo "  make wireguard-status   - Check WireGuard service status"
	@echo ""
	@echo "SSL/TLS Certificate Management:"
	@echo "  make ssl-setup          - Complete Let's Encrypt SSL setup (certbot + renewal)"
	@echo "  make ssl-renew-test     - Test certificate renewal (dry run)"
	@echo ""
	@echo "Dynamic DNS (Gandi LiveDNS):"
	@echo "  make ddns-setup     - Create vpn.DOMAIN DNS record and install 5-min cron updater"
	@echo "  make ddns-update    - Manually trigger a DDNS IP check and update"
	@echo "  make ddns-status    - Show current public IP vs Gandi DNS record"
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
	@$(COMPOSE) build --progress=plain
	@echo "✓ Build complete"

# Build only custom services (faster rebuild during development)
build-custom: validate
	@echo "Building custom services from source..."
	@git submodule update --init hae-server
	@$(COMPOSE) build homepage-api hae-server --progress=plain
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
	@git submodule update --init hae-server
	@$(COMPOSE) build homepage-api hae-server --progress=plain
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
		echo "Configure network devices to use $$SERVER_IP as DNS server"; \
	else \
		echo "ERROR: DOMAIN not set in .env"; \
	fi
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
	if [ -n "$$GANDIV5_PERSONAL_ACCESS_TOKEN" ] && [ -n "$$LETSENCRYPT_EMAIL" ] && [ -n "$$DOMAIN" ]; then \
		CERT_STATUS=$$(sudo certbot certificates 2>/dev/null | grep -A 5 "Certificate Name: $$DOMAIN" | grep "Expiry Date" | sed -n 's/.*VALID: \([0-9]\+\) days.*/\1/p'); \
		if [ -z "$$CERT_STATUS" ]; then \
			CERT_STATUS="0"; \
		fi; \
		if [ "$$CERT_STATUS" = "0" ]; then \
			echo "🔒 SSL Certificate Setup Available"; \
			echo ""; \
			echo "No valid certificate found for $$DOMAIN"; \
			echo "Would you like to set up Let's Encrypt SSL certificates now? (y/N)"; \
			read -r response; \
			if [ "$$response" = "y" ] || [ "$$response" = "Y" ]; then \
				$(MAKE) ssl-setup; \
			else \
				echo ""; \
				echo "Skipping SSL setup. Your services will use self-signed certificates."; \
				echo "You can set up Let's Encrypt SSL later with: make ssl-setup"; \
			fi; \
		elif [ "$$CERT_STATUS" -lt 30 ]; then \
			echo "⚠️  SSL Certificate Expiring Soon"; \
			echo ""; \
			echo "Your certificate for $$DOMAIN expires in $$CERT_STATUS days"; \
			echo "Would you like to renew it now? (y/N)"; \
			read -r response; \
			if [ "$$response" = "y" ] || [ "$$response" = "Y" ]; then \
				sudo certbot renew --force-renewal; \
				./scripts/ssl/copy-certs-to-traefik.sh; \
				$(COMPOSE_CORE) restart traefik; \
			else \
				echo ""; \
				echo "Certificate will auto-renew within 30 days."; \
			fi; \
		else \
			echo "✓ SSL Certificate Valid"; \
			echo ""; \
			echo "Certificate for $$DOMAIN is valid for $$CERT_STATUS more days"; \
		fi; \
	else \
		echo "ℹ️  Using self-signed SSL certificates (browser warnings expected)"; \
		echo ""; \
		echo "For trusted Let's Encrypt certificates, add to .env:"; \
		echo "  - DOMAIN=your-domain.com"; \
		echo "  - LETSENCRYPT_EMAIL=your-email@example.com"; \
		echo "  - GANDIV5_PERSONAL_ACCESS_TOKEN=your-gandi-token"; \
		echo ""; \
		echo "Then run: make ssl-setup"; \
	fi
	@echo ""

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
	@git submodule update --init hae-server
	@$(COMPOSE) build homepage-api hae-server --progress=plain
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
	@mkdir -p data/bede/vault
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

logs-bede:
	@$(COMPOSE) logs -f bede

logs-hae:
	@$(COMPOSE) logs -f hae-server hae-mongo

# Bede AI Assistant (docker-compose.ai.yml)
COMPOSE_AI := docker compose -f docker-compose.ai.yml

bede-build: env-check
	@echo "Building Bede images..."
	@$(COMPOSE_AI) build --progress=plain
	@echo "✓ Bede images built"

bede-start: env-check
	@echo "Starting Bede..."
	@mkdir -p data/bede/vault
	@$(COMPOSE_AI) up -d
	@echo "✓ Bede started"

bede-stop:
	@echo "Stopping Bede..."
	@$(COMPOSE_AI) down
	@echo "✓ Bede stopped"

bede-restart: env-check
	@echo "Restarting Bede..."
	@$(COMPOSE_AI) up -d
	@echo "✓ Bede restarted"

bede-status:
	@$(COMPOSE_AI) ps

# Health Auto Export services (docker-compose.health.yml)
COMPOSE_HEALTH := docker compose -f docker-compose.health.yml

hae-build: env-check
	@echo "Building hae-server image..."
	@git submodule update --init hae-server
	@$(COMPOSE_HEALTH) build --progress=plain
	@echo "✓ hae-server image built"

hae-start: env-check
	@echo "Starting health services..."
	@git submodule update --init hae-server
	@$(COMPOSE_HEALTH) up -d
	@echo "✓ Health services started"

hae-stop:
	@echo "Stopping health services..."
	@$(COMPOSE_HEALTH) down
	@echo "✓ Health services stopped"

hae-restart: env-check
	@echo "Restarting health services..."
	@$(COMPOSE_HEALTH) up -d
	@echo "✓ Health services restarted"

hae-status:
	@$(COMPOSE_HEALTH) ps

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
	@echo "Next steps:"
	@echo "  1. Start Docker services:  make start"
	@echo "  2. Set up VPN routing:     make wireguard-routing  (run after make start)"
	@echo "  3. Add VPN peers:          sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>"
	@echo ""
	@echo "Optional — if your public IP is dynamic:"
	@echo "  Set WIREGUARD_DDNS_SUBDOMAIN=vpn in .env, then:"
	@echo "  4. Set up automatic DNS:   make ddns-setup"

# Set up iptables rules for VPN clients to access Docker services and LAN
# Must be run after 'make start' so Docker networks exist for accurate subnet detection
wireguard-routing:
	@echo "Setting up WireGuard routing for Docker bridge access..."
	@echo ""
	@echo "This configures iptables DOCKER-USER rules so VPN clients can reach"
	@echo "services running in Docker containers and the local network."
	@echo ""
	@echo "Note: Run this after 'make start' so Docker networks exist."
	@echo ""
	@sudo ./scripts/wireguard/setup-wireguard-routing.sh

# Manage VPN peers (list, view stats, remove)
wireguard-peers:
	@./scripts/wireguard/wireguard-peer-management.sh

# Test WireGuard routing and connectivity
wireguard-test:
	@echo "Testing WireGuard routing and connectivity..."
	@echo ""
	@./scripts/wireguard/test-wireguard-routing.sh

ddns-setup:
	@echo "Setting up Gandi LiveDNS dynamic DNS..."
	@echo ""
	@sudo ./scripts/ddns/setup-gandi-ddns.sh

ddns-update:
	@echo "Running Gandi DDNS update check..."
	@./scripts/ddns/gandi-ddns-update.sh

ddns-status:
	@set -a; . ./.env; set +a; \
	CURRENT_IP=$$(curl -sf --max-time 5 ifconfig.me 2>/dev/null \
	    || curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null \
	    || echo "unavailable"); \
	HTTP_STATUS=$$(curl -s -o /tmp/gandi-ddns-status.json -w "%{http_code}" \
	    -H "Authorization: Bearer $$GANDIV5_PERSONAL_ACCESS_TOKEN" \
	    "https://api.gandi.net/v5/livedns/domains/$$DOMAIN/records/$$WIREGUARD_DDNS_SUBDOMAIN/A"); \
	if [ "$$HTTP_STATUS" = "200" ]; then \
	    GANDI_IP=$$(jq -r '.rrset_values[0]' /tmp/gandi-ddns-status.json); \
	else \
	    GANDI_IP="(no record found)"; \
	fi; \
	echo "DDNS Status"; \
	echo "  Current public IP:  $$CURRENT_IP"; \
	echo "  Gandi DNS record:   $$GANDI_IP ($$WIREGUARD_DDNS_SUBDOMAIN.$$DOMAIN)"; \
	if [ "$$CURRENT_IP" = "$$GANDI_IP" ]; then \
	    echo "  Status: in sync"; \
	else \
	    echo "  Status: out of sync — run: make ddns-update"; \
	fi

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
	@echo "  - LETSENCRYPT_EMAIL must be set in .env"
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
		echo ""; \
		echo "Certificate info:"; \
		echo "  - Expires: 90 days from now"; \
		echo "  - Auto-renewal: 30 days before expiry"; \
		echo "  - Test renewal after 2-4 hours: sudo certbot renew --dry-run"; \
	fi
	@echo ""
	@echo "Certificates will auto-renew every 90 days."
	@echo "Check renewal logs: sudo tail -f /var/log/certbot-traefik-reload.log"

# Test certificate renewal (dry run)
ssl-renew-test:
	@echo "Testing certificate renewal (dry run)..."
	@echo "This will simulate renewal without actually renewing certificates."
	@echo ""
	@echo "Note: Wait 2-4 hours after initial setup for DNS caches to clear."
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo ""
	@sudo certbot renew --dry-run

