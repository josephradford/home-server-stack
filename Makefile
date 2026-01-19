# AWS Deployment Makefile
# Simplified commands for deploying to AWS EC2

.PHONY: help setup start stop restart logs status clean validate

COMPOSE := docker compose -f docker-compose.yml

help:
	@echo "AWS Deployment Commands:"
	@echo "  make setup      - First-time setup (installs Docker, configures services)"
	@echo "  make start      - Start all services"
	@echo "  make stop       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs from all services"
	@echo "  make status     - Show service status"
	@echo "  make clean      - Stop and remove containers"
	@echo "  make validate   - Validate docker-compose configuration"
	@echo ""
	@echo "Monitoring:"
	@echo "  make cloudwatch-setup  - Install CloudWatch agent (AWS monitoring)"

# Validate compose file
validate:
	@echo "Validating docker-compose.yml..."
	@$(COMPOSE) config --quiet && echo "✓ Configuration valid" || (echo "✗ Configuration invalid" && exit 1)

# First-time setup
setup: validate
	@echo "=== AWS Deployment Setup ==="
	@echo ""
	@echo "Step 1/5: Checking environment file..."
	@if [ ! -f .env ]; then \
		echo "ERROR: .env file not found!"; \
		echo "Copy .env.example to .env and configure:"; \
		echo "  cp .env.example .env"; \
		echo "  nano .env"; \
		exit 1; \
	fi
	@echo "✓ Environment file exists"
	@echo ""
	@echo "Step 2/5: Generating Traefik dashboard password..."
	@if [ -z "$$(grep '^TRAEFIK_DASHBOARD_USERS=' .env | cut -d'=' -f2)" ]; then \
		PASS=$$(grep '^TRAEFIK_PASSWORD=' .env | cut -d'=' -f2); \
		HASH=$$(htpasswd -nb admin "$$PASS"); \
		sed -i.bak "s|^TRAEFIK_DASHBOARD_USERS=.*|TRAEFIK_DASHBOARD_USERS=$$HASH|" .env; \
		echo "✓ Traefik password configured"; \
	else \
		echo "✓ Traefik password already configured"; \
	fi
	@echo ""
	@echo "Step 3/5: Creating data directories..."
	@mkdir -p data/{traefik/{letsencrypt,logs},n8n,actualbudget,mealie,homepage/{config},homepage-api}
	@echo "✓ Directories created"
	@echo ""
	@echo "Step 4/5: Building custom services..."
	@$(COMPOSE) build homepage-api
	@echo ""
	@echo "Step 5/5: Starting services..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Services will be available at:"
	@echo "  - Homepage:     https://$$(grep '^DOMAIN=' .env | cut -d'=' -f2)"
	@echo "  - n8n:          https://n8n.$$(grep '^DOMAIN=' .env | cut -d'=' -f2)"
	@echo "  - Mealie:       https://mealie.$$(grep '^DOMAIN=' .env | cut -d'=' -f2)"
	@echo "  - Actual:       https://actual.$$(grep '^DOMAIN=' .env | cut -d'=' -f2)"
	@echo "  - Traefik:      https://traefik.$$(grep '^DOMAIN=' .env | cut -d'=' -f2)"
	@echo ""
	@echo "Note: Let's Encrypt SSL certificates will be generated automatically on first access"

# Start services
start: validate
	@echo "Starting all services..."
	@$(COMPOSE) up -d
	@echo "✓ Services started"

# Stop services
stop:
	@echo "Stopping all services..."
	@$(COMPOSE) down
	@echo "✓ Services stopped"

# Restart services
restart:
	@echo "Restarting all services..."
	@$(COMPOSE) restart
	@echo "✓ Services restarted"

# View logs
logs:
	@$(COMPOSE) logs -f

# Show service status
status:
	@$(COMPOSE) ps

# Clean up
clean:
	@echo "Stopping and removing containers..."
	@$(COMPOSE) down -v
	@echo "✓ Cleanup complete (data/ preserved)"

# Install CloudWatch agent for AWS monitoring
cloudwatch-setup:
	@echo "Installing CloudWatch agent..."
	@echo "Follow AWS documentation:"
	@echo "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-on-EC2-Instance.html"
	@echo ""
	@echo "Quick install:"
	@echo "1. Attach IAM role with CloudWatchAgentServerPolicy"
	@echo "2. Run: wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb"
	@echo "3. Run: sudo dpkg -i amazon-cloudwatch-agent.deb"
	@echo "4. Configure: sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard"
