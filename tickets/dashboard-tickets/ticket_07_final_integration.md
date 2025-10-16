# Ticket 07: Complete Integration & Testing

## Objective
Integrate all services, perform end-to-end testing, and create deployment documentation.

## Tasks

### 1. Create Master Deployment Script

Create `scripts/deploy-dashboard.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying Complete Dashboard Stack"
echo "======================================"
echo ""

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo "Copy .env.example to .env and configure it first"
    exit 1
fi

# Source environment
source .env

# Validate required variables
REQUIRED_VARS=(
    "SERVER_IP"
    "TRANSPORTNSW_API_KEY"
    "HABITICA_SESSION_SECRET"
    "HABITICA_ADMIN_EMAIL"
    "HABITICA_ADMIN_PASSWORD"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required variable $var not set in .env"
        exit 1
    fi
done

echo "✅ Environment variables validated"
echo ""

# Create network if needed
if ! docker network inspect home-server &>/dev/null; then
    echo "📡 Creating Docker network..."
    docker network create home-server
fi

# Create all data directories
echo "📁 Creating data directories..."
mkdir -p data/{homepage/config,homeassistant,habitica/{mongo,redis,uploads},homepage-api}
mkdir -p ssl/habitica

echo "✅ Directories created"
echo ""

# Generate Habitica SSL certificate
if [ ! -f ssl/habitica/habitica.crt ]; then
    echo "🔒 Generating Habitica SSL certificate..."
    cd ssl
    ./generate-habitica-cert.sh ${HABITICA_BASE_URL:-habitica.local}
    cd ..
fi

# Build custom images
echo "🔨 Building custom images..."
docker compose -f docker-compose.dashboard.yml build homepage-api

# Deploy services in order
echo ""
echo "🚀 Deploying services..."
echo ""

# Start databases first
echo "1️⃣  Starting databases..."
docker compose -f docker-compose.dashboard.yml up -d habitica-mongo habitica-redis
sleep 10

# Start Habitica
echo "2️⃣  Starting Habitica..."
docker compose -f docker-compose.dashboard.yml up -d habitica habitica-nginx
sleep 20

# Start Home Assistant
echo "3️⃣  Starting Home Assistant..."
docker compose -f docker-compose.dashboard.yml up -d homeassistant
sleep 30

# Start Backend API
echo "4️⃣  Starting Backend API..."
docker compose -f docker-compose.dashboard.yml up -d homepage-api
sleep 10

# Start Homepage
echo "5️⃣  Starting Homepage..."
docker compose -f docker-compose.dashboard.yml up -d homepage

echo ""
echo "✅ All services deployed!"
echo ""
echo "📊 Service Status:"
docker compose -f docker-compose.dashboard.yml ps
echo ""

# Display access information
echo "🌐 Access Information:"
echo "───────────────────────────────────────────"
echo "Homepage Dashboard:    http://${SERVER_IP}:3100"
echo "Home Assistant:        http://${SERVER_IP}:8123"
echo "Habitica:              https://${SERVER_IP} (or http://${SERVER_IP}:3000)"
echo "Backend API:           http://${SERVER_IP}:5000/api/health"
echo ""

echo "📋 Next Steps:"
echo "───────────────────────────────────────────"
echo "1. Complete Home Assistant setup at http://${SERVER_IP}:8123"
echo "2. Generate HA API token and add to .env"
echo "3. Create Habitica account at https://${SERVER_IP}"
echo "4. Get Habitica API credentials and add to .env"
echo "5. Install Home Assistant iOS app"
echo "6. Configure transport stop IDs in .env"
echo "7. Configure traffic routes in .env"
echo ""
echo "See docs/DASHBOARD_SETUP.md for detailed instructions"
echo ""
echo "🎉 Deployment complete!"
```

Make executable:
```bash
chmod +x scripts/deploy-dashboard.sh
```

### 2. Create Health Check Script

Create `scripts/health-check.sh`:

```bash
#!/bin/bash

echo "🏥 Dashboard Health Check"
echo "========================"
echo ""

source .env

# Check each service
check_service() {
    local name=$1
    local url=$2
    local expected=$3
    
    echo -n "Checking $name... "
    
    if response=$(curl -s -f -m 5 "$url" 2>/dev/null); then
        if [ -z "$expected" ] || echo "$response" | grep -q "$expected"; then
            echo "✅ OK"
            return 0
        else
            echo "⚠️  Unexpected response"
            return 1
        fi
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Container checks
echo "📦 Container Status:"
docker compose -f docker-compose.dashboard.yml ps --format "table {{.Name}}\t{{.Status}}"
echo ""

# Service checks
echo "🔍 Service Health Checks:"
check_service "Homepage" "http://localhost:3100" "DOCTYPE"
check_service "Home Assistant" "http://localhost:8123" ""
check_service "Habitica (HTTP)" "http://localhost:3000" ""
check_service "Backend API" "http://localhost:5000/api/health" "healthy"
echo ""

# API endpoint checks
echo "🔌 API Endpoint Checks:"
check_service "BOM Weather" "http://localhost:5000/api/bom/weather" "temp"

if [ -n "$TRANSPORTNSW_API_KEY" ]; then
    check_service "Transport NSW API" "http://localhost:5000/api/health" "transport_nsw.*configured"
else
    echo "⚠️  Transport NSW: Not configured"
fi

if [ -n "$TOMTOM_API_KEY" ]; then
    check_service "TomTom API" "http://localhost:5000/api/health" "tomtom.*configured"
else
    echo "⚠️  TomTom Traffic: Not configured"
fi

if [ -n "$HOMEASSISTANT_TOKEN" ]; then
    check_service "Home Assistant Token" "http://localhost:5000/api/health" "home_assistant.*configured"
else
    echo "⚠️  Home Assistant: Token not configured"
fi

echo ""
echo "📊 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo ""

# Check disk space
echo "💾 Disk Usage:"
du -sh data/* 2>/dev/null | sort -h
echo ""

echo "Health check complete!"
```

Make executable:
```bash
chmod +x scripts/health-check.sh
```

### 3. Create Testing Documentation

Create `docs/TESTING.md`:

```markdown
# Testing Guide

## Pre-Deployment Testing

### 1. Environment Configuration
```bash
# Validate .env file
./scripts/validate-env.sh

# Check all required variables are set
grep -v '^#' .env | grep -v '^$'
```

### 2. Docker Network
```bash
# Verify network exists
docker network inspect home-server

# If not, create it
docker network create home-server
```

## Deployment Testing

### 1. Deploy All Services
```bash
./scripts/deploy-dashboard.sh
```

Expected output: All services start without errors

### 2. Wait for Initialization
- Habitica: 2-3 minutes
- Home Assistant: 1-2 minutes
- Other services: 10-30 seconds

### 3. Run Health Check
```bash
./scripts/health-check.sh
```

All checks should pass ✅

## Component Testing

### Homepage Dashboard
```bash
# Access dashboard
curl http://localhost:3100

# Should return HTML with DOCTYPE
# Open in browser: http://SERVER_IP:3100
# Verify: All existing services visible (AdGuard, n8n, Ollama, Grafana)
```

### Home Assistant
```bash
# Check if running
curl http://localhost:8123

# Open in browser: http://SERVER_IP:8123
# Complete onboarding wizard
# Generate API token
# Add token to .env
```

### Habitica
```bash
# Check HTTP
curl http://localhost:3000

# Check HTTPS (will have cert warning)
curl -k https://localhost:443

# Open in browser: https://SERVER_IP
# Accept certificate warning
# Create account
# Get API credentials from Settings > API
```

### Backend API
```bash
# Health check
curl http://localhost:5000/api/health | jq

# Should show all services configured/not configured

# Test BOM weather
curl http://localhost:5000/api/bom/weather | jq

# Should return current weather for Parramatta
```

### Transport NSW (requires API key)
```bash
# Test with your stop ID
curl http://localhost:5000/api/transport/departures/10101323 | jq

# Should return departure times
# If error: check API key in .env
```

### Traffic (requires TomTom API key)
```bash
# Test route
curl "http://localhost:5000/api/traffic/route?origin=North+Parramatta&destination=Sydney+CBD" | jq

# Should return travel time and traffic status
```

## Integration Testing

### 1. Homepage → Backend API
- Open Homepage at http://SERVER_IP:3100
- Check "Transport & Commute" section
- Verify weather widget shows data
- Verify transport times (if configured)

### 2. Homepage → Home Assistant
- After HA token configured
- Check "Family & Location" section
- Should show HA version

### 3. Homepage → Habitica
- After Habitica API configured
- Check "Habitica RPG" section
- Should show character stats

### 4. Docker Integration
- Homepage should show all running containers
- Container status indicators should be accurate
- Click container names should show details

## End-to-End Testing Checklist

- [ ] All containers running (`docker ps`)
- [ ] Homepage accessible
- [ ] Home Assistant accessible and configured
- [ ] Habitica accessible and account created
- [ ] API health check passes
- [ ] Weather data displaying
- [ ] Transport times showing (if configured)
- [ ] Traffic data showing (if configured)
- [ ] Calendar showing (if configured)
- [ ] Docker containers visible in Homepage
- [ ] No errors in any logs

## Log Checking

```bash
# Check all logs
docker compose -f docker-compose.dashboard.yml logs

# Check specific service
docker logs homepage
docker logs homeassistant
docker logs habitica
docker logs homepage-api

# Follow logs in real-time
docker logs -f homepage-api
```

## Performance Testing

### Resource Usage
```bash
# Check container resources
docker stats

# Expected usage:
# - Homepage: ~50MB RAM
# - Home Assistant: ~400MB RAM
# - Habitica: ~200MB RAM
# - MongoDB: ~100MB RAM
# - Redis: ~10MB RAM
# - Backend API: ~100MB RAM
# Total: ~1GB RAM
```

### Response Times
```bash
# Test API response times
time curl http://localhost:5000/api/bom/weather
# Should be < 2 seconds

time curl http://localhost:5000/api/transport/departures/10101323
# Should be < 3 seconds

time curl "http://localhost:5000/api/traffic/route?origin=test&destination=test"
# Should be < 5 seconds
```

## Troubleshooting Failed Tests

### Service won't start
1. Check logs: `docker logs CONTAINER_NAME`
2. Check port conflicts: `sudo netstat -tlnp | grep PORT`
3. Check .env variables
4. Try restarting: `docker compose -f docker-compose.dashboard.yml restart SERVICE_NAME`

### API returning errors
1. Check API logs: `docker logs homepage-api`
2. Verify API keys in .env
3. Test endpoints directly with curl
4. Check network connectivity: `docker exec homepage-api ping homeassistant`

### Homepage not showing widgets
1. Check Homepage logs: `docker logs homepage`
2. Verify environment variables passed to container
3. Check services.yaml syntax
4. Restart Homepage: `docker compose -f docker-compose.dashboard.yml restart homepage`

### Database connection errors
1. Check if MongoDB is running: `docker ps | grep mongo`
2. Check MongoDB logs: `docker logs habitica-mongo`
3. Verify credentials in .env match docker-compose
4. Try recreating containers

## Acceptance Criteria

All of the following must pass:
- [ ] `./scripts/deploy-dashboard.sh` completes successfully
- [ ] `./scripts/health-check.sh` reports all services healthy
- [ ] Homepage accessible and displays all sections
- [ ] Home Assistant accessible and responding
- [ ] Habitica accessible via HTTPS
- [ ] Backend API health check returns "healthy"
- [ ] BOM weather API returns current weather data
- [ ] All containers show "Up" status
- [ ] No critical errors in any service logs
- [ ] Resource usage within expected ranges
```

### 4. Update Main README

Add testing section to main `README.md`:

```markdown
## Testing

After deployment, run health checks:

```bash
./scripts/health-check.sh
```

See [Testing Guide](docs/TESTING.md) for comprehensive testing procedures.
```

### 5. Create Backup Script

Create `scripts/backup-dashboard.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups/dashboard-$(date +%Y%m%d-%H%M%S)"

echo "💾 Creating dashboard backup..."
echo "Backup location: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"

# Backup configurations
echo "📋 Backing up configurations..."
cp -r data/homepage/config "$BACKUP_DIR/homepage-config"
cp -r data/homeassistant "$BACKUP_DIR/homeassistant"
cp .env "$BACKUP_DIR/env.backup"

# Backup Habitica database
echo "🎮 Backing up Habitica database..."
docker exec habitica-mongo mongodump \
  --username=$HABITICA_MONGO_USER \
  --password=$HABITICA_MONGO_PASSWORD \
  --out=/data/backup

docker cp habitica-mongo:/data/backup "$BACKUP_DIR/habitica-db"

# Create backup archive
echo "📦 Creating archive..."
tar -czf "$BACKUP_DIR.tar.gz" -C ./backups "$(basename $BACKUP_DIR)"

# Cleanup temp backup directory
rm -rf "$BACKUP_DIR"

echo "✅ Backup complete: $BACKUP_DIR.tar.gz"
echo "Size: $(du -h "$BACKUP_DIR.tar.gz" | cut -f1)"
```

Make executable:
```bash
chmod +x scripts/backup-dashboard.sh
```

## Acceptance Criteria
- [ ] Master deployment script created and working
- [ ] Health check script created and passing
- [ ] Testing documentation comprehensive
- [ ] Backup script created
- [ ] All services deploy successfully
- [ ] Health checks pass for all services
- [ ] Integration between services working
- [ ] Documentation updated
- [ ] No errors in deployment
- [ ] Resource usage acceptable

## Testing
```bash
# Clean deployment
docker compose -f docker-compose.dashboard.yml down -v
./scripts/deploy-dashboard.sh

# Run health checks
./scripts/health-check.sh

# Test backup
./scripts/backup-dashboard.sh

# Verify all functionality
# Follow TESTING.md checklist
```

## Dependencies
- All previous tickets (01-06) completed
- .env fully configured
- All API keys obtained

## Notes
- Deployment script handles service order
- Health check validates all components
- Backup includes configs and databases
- Testing guide covers all scenarios
- Scripts have proper error handling
- Resource usage monitored
- Logs easily accessible