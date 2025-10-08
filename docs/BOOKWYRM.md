# Bookwyrm Integration Guide

This home server stack uses the standalone [bookwyrm-docker](https://github.com/josephradford/bookwyrm-docker) wrapper project for deploying Bookwyrm. Bookwyrm is a **mandatory component** of the stack and is automatically deployed during setup.

## Why Use the Wrapper?

The bookwyrm-docker wrapper project:
- ✅ Handles all Bookwyrm deployment complexity (nginx, static files, initialization)
- ✅ Is production-ready and well-documented
- ✅ Can be used standalone or integrated into other stacks
- ✅ Is maintained separately, benefiting the broader Bookwyrm community
- ✅ Reduces the size of this repository's docker-compose.yml

## Automatic Deployment

Bookwyrm is automatically deployed when you run `make setup`. The wrapper is cloned to `external/bookwyrm-docker/` and integrated with the main stack.

**First-time setup flow:**
1. Run `make setup` - wrapper is cloned automatically
2. Setup pauses and prompts you to configure Bookwyrm `.env`
3. Configure `external/bookwyrm-docker/.env` (see below)
4. Run `make setup` again - Bookwyrm deploys automatically

## Manual Configuration

### 1. Navigate to Wrapper Directory

```bash
cd external/bookwyrm-docker
```

### 2. Configure Bookwyrm

```bash
cp .env.example .env
nano .env  # Edit configuration
```

**Minimal required configuration in `.env`:**
```bash
# Domain
BOOKWYRM_DOMAIN=bookwyrm.local

# Security (generate with: openssl rand -base64 45)
BOOKWYRM_SECRET_KEY=your_very_long_secret_key_here

# Database password (generate with: openssl rand -base64 32)
BOOKWYRM_DB_PASSWORD=your_secure_password

# Redis passwords
BOOKWYRM_REDIS_ACTIVITY_PASSWORD=your_redis_activity_password
BOOKWYRM_REDIS_BROKER_PASSWORD=your_redis_broker_password

# Network
BOOKWYRM_PORT=8000
BOOKWYRM_CSRF_TRUSTED_ORIGINS=http://192.168.1.100:8000,http://bookwyrm.local
```

**Optional: Use your main home-server-stack .env**

To avoid maintaining two `.env` files, you can symlink or copy Bookwyrm variables from the main `.env`:

```bash
# Create symlink (changes to main .env affect Bookwyrm)
ln -s ../../.env .env

# Or copy relevant sections (independent configuration)
grep "^BOOKWYRM_" ../../.env >> .env
grep "^TIMEZONE=" ../../.env >> .env
```

### 3. Deploy Bookwyrm

From the home-server-stack root directory:

```bash
make bookwyrm-setup
```

Or manually from the external/bookwyrm-docker directory:

```bash
cd external/bookwyrm-docker
make setup
```

### 4. Verify Deployment

```bash
# Check services are running
cd external/bookwyrm-docker
docker compose ps

# Access Bookwyrm
open http://192.168.1.100:8000
```

## Integration with Home Server Stack

### Network Integration

The Bookwyrm wrapper uses its own `bookwyrm` network by default. To integrate with the home server stack's `homeserver` network, you have two options:

**Option A: Keep Separate Networks (Recommended)**

Bookwyrm runs in isolation with its own network. Access via port 8000 like other services.

**Pros:**
- Isolated from other services
- Follows wrapper's default configuration
- No additional setup needed

**Cons:**
- Not part of the homeserver network
- Cannot use internal DNS between services

**Option B: Connect to Homeserver Network**

Override Bookwyrm's network to use `homeserver`:

```bash
# In external/bookwyrm-docker/, create docker-compose.override.yml
cat > docker-compose.override.yml <<EOF
services:
  bookwyrm:
    networks:
      - homeserver
  bookwyrm-nginx:
    networks:
      - homeserver
  bookwyrm-db:
    networks:
      - homeserver
  bookwyrm-redis-activity:
    networks:
      - homeserver
  bookwyrm-redis-broker:
    networks:
      - homeserver
  bookwyrm-celery:
    networks:
      - homeserver
  bookwyrm-celery-beat:
    networks:
      - homeserver

networks:
  homeserver:
    external: true
EOF
```

**Pros:**
- Integrated with other services
- Can use internal DNS (e.g., `bookwyrm:8000` from n8n)
- Visible to monitoring stack

**Cons:**
- Requires override file
- More complex setup

### Monitoring Integration

If using the homeserver network (Option B above), Prometheus can scrape Bookwyrm metrics.

Add to `monitoring/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'bookwyrm'
    static_configs:
      - targets: ['bookwyrm-nginx:80']
```

### Backup Integration

Bookwyrm data is stored in `external/bookwyrm-docker/data/`:

```
external/bookwyrm-docker/data/
├── pgdata/          # PostgreSQL database (critical!)
├── redis-activity/  # Redis persistence
├── redis-broker/    # Redis persistence
└── images/          # User-uploaded book covers
```

**Backup strategy:**

```bash
# Manual backup
cd external/bookwyrm-docker
tar czf ~/backups/bookwyrm-$(date +%Y%m%d).tar.gz data/

# Database backup (recommended for migrations)
docker exec bookwyrm-db pg_dump -U bookwyrm bookwyrm > ~/backups/bookwyrm-db-$(date +%Y%m%d).sql
```

## Management Commands

All Bookwyrm management is done through the wrapper's Makefile:

```bash
cd external/bookwyrm-docker

# Service management
make start           # Start Bookwyrm
make stop            # Stop Bookwyrm
make restart         # Restart Bookwyrm
make status          # Show container status

# Maintenance
make update          # Update to latest Bookwyrm version
make logs            # View all logs
make logs-web        # View web server logs only
make logs-nginx      # View nginx logs only

# Initialization (if needed)
make init            # Re-run database migrations and static collection
```

## Home Server Stack Makefile Integration

For convenience, bookwyrm commands can be run from the home-server-stack root:

```bash
# From home-server-stack root
make bookwyrm-setup     # Initial setup
make bookwyrm-start     # Start Bookwyrm
make bookwyrm-stop      # Stop Bookwyrm
make bookwyrm-logs      # View logs
make bookwyrm-status    # Check status
```

These commands are wrappers that execute the bookwyrm-docker Makefile.

## Troubleshooting

### Bookwyrm Wrapper Not Cloned

**Error:** `external/bookwyrm-docker does not exist`

**Solution:**
```bash
mkdir -p external
cd external
git clone https://github.com/josephradford/bookwyrm-docker.git
```

### Port Conflict (Port 8000 in Use)

**Error:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:** Change port in `external/bookwyrm-docker/.env`:
```bash
BOOKWYRM_PORT=8001
```

### Static Files Not Loading

**Error:** Website shows plain text without CSS

**Solution:** Re-run initialization:
```bash
cd external/bookwyrm-docker
make init
```

### Database Connection Issues

**Error:** `password authentication failed`

**Solution:** Reset database:
```bash
cd external/bookwyrm-docker
docker compose down
rm -rf data/pgdata
make setup
```

### Complete Troubleshooting Guide

See the wrapper's documentation:
- [external/bookwyrm-docker/README.md](../external/bookwyrm-docker/README.md)
- [external/bookwyrm-docker/docs/TROUBLESHOOTING.md](../external/bookwyrm-docker/docs/TROUBLESHOOTING.md)

## Updating the Wrapper

To update the bookwyrm-docker wrapper project:

```bash
cd external/bookwyrm-docker
git pull origin main
make update  # Pulls latest Bookwyrm and rebuilds
```

## Removing Bookwyrm

To completely remove Bookwyrm:

```bash
cd external/bookwyrm-docker
make clean  # Stops containers and removes volumes (destroys data!)
cd ../..
rm -rf external/bookwyrm-docker  # Remove wrapper
```

## Alternative: Using Bookwyrm Wrapper Standalone

The bookwyrm-docker wrapper can also be used completely independently:

```bash
# Clone anywhere
git clone https://github.com/josephradford/bookwyrm-docker.git
cd bookwyrm-docker

# Configure
cp .env.example .env
nano .env

# Deploy
make setup

# Access at http://localhost:8000
```

This is useful for:
- Testing Bookwyrm on a development machine
- Deploying Bookwyrm on a different server
- Sharing the wrapper with others who want Bookwyrm

## Benefits of This Approach

**Separation of Concerns:**
- Home server stack focuses on core services (AdGuard, n8n, Ollama, WireGuard)
- Bookwyrm complexity isolated in standalone project
- Each can be maintained and updated independently

**Reusability:**
- Bookwyrm wrapper benefits the broader community
- Can be used in any Docker environment
- Well-documented for standalone use

**Maintainability:**
- Smaller docker-compose.yml in main repo
- Bookwyrm updates don't require changes to main stack
- Clear ownership and documentation

**Flexibility:**
- Easy to add/remove Bookwyrm from your stack
- Can deploy multiple Bookwyrm instances
- Network integration is optional

## See Also

- [bookwyrm-docker Repository](https://github.com/josephradford/bookwyrm-docker)
- [Official Bookwyrm](https://joinbookwyrm.com/)
- [Bookwyrm Documentation](https://docs.joinbookwyrm.com/)
- [Home Server Stack README](../README.md)
