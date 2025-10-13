# Configure Bookwyrm with Traefik

## Priority: 3 (Medium)
## Estimated Time: 1.5-2 hours
## Phase: Week 2 - External Services

## Description
Configure Bookwyrm (running in external docker-compose wrapper) to be accessible via Traefik at bookwyrm.home.local. This requires connecting Bookwyrm to the homeserver network, adding Traefik labels, and updating Bookwyrm's domain configuration.

## Acceptance Criteria
- [ ] Bookwyrm accessible via https://bookwyrm.home.local
- [ ] Bookwyrm connected to homeserver Docker network
- [ ] Traefik labels configured for Bookwyrm services
- [ ] BOOKWYRM_DOMAIN updated to new domain
- [ ] Bookwyrm functionality verified (login, books, feeds)
- [ ] Static files and media loading correctly
- [ ] Federation features working (if applicable)
- [ ] No errors in Bookwyrm logs

## Technical Implementation Details

### Current Bookwyrm Setup
Bookwyrm runs via external docker-compose wrapper:
- Location: `external/bookwyrm-docker/`
- Accessible at: `http://SERVER_IP:8000`
- Has own docker-compose.yml
- Uses own Docker network
- Configuration in `external/bookwyrm-docker/.env`

### Challenge
Bookwyrm runs in a separate docker-compose project, so it needs to:
1. Connect to the `homeserver` Docker network
2. Have Traefik labels on the `bookwyrm` container
3. Update domain configuration

### Files to Modify
1. `external/bookwyrm-docker/.env` - Update BOOKWYRM_DOMAIN
2. `external/bookwyrm-docker/docker-compose.yml` - Add network and Traefik labels

### Step 1: Update Bookwyrm Environment (.env)

**File:** `external/bookwyrm-docker/.env`

**Current value:**
```bash
BOOKWYRM_DOMAIN=bookwyrm.local
BOOKWYRM_USE_HTTPS=false
```

**Updated value:**
```bash
BOOKWYRM_DOMAIN=bookwyrm.home.local
BOOKWYRM_USE_HTTPS=true  # Traefik provides HTTPS
```

### Step 2: Update Bookwyrm docker-compose.yml

**File:** `external/bookwyrm-docker/docker-compose.yml`

#### A. Add External Network Declaration

At the end of the file, add:
```yaml
networks:
  bookwyrm-network:
    driver: bridge
  homeserver:
    external: true  # Connect to main homeserver network
```

#### B. Update Bookwyrm Service

Find the `bookwyrm` service (usually called `web` in Bookwyrm) and update:

```yaml
  web:
    image: bookwyrm/bookwyrm:latest
    container_name: bookwyrm
    restart: unless-stopped
    ports:
      - "${SERVER_IP:-127.0.0.1}:8000:8000"  # Keep for backward compatibility
    environment:
      # ... existing environment variables ...
      - DOMAIN=${BOOKWYRM_DOMAIN}
      - USE_HTTPS=${BOOKWYRM_USE_HTTPS}
      # ... other env vars ...
    volumes:
      # ... existing volumes ...
    networks:
      - bookwyrm-network  # Existing network for DB/Redis
      - homeserver        # ADD THIS: Connect to Traefik network
    depends_on:
      # ... existing dependencies ...

    # ADD TRAEFIK LABELS:
    labels:
      - "traefik.enable=true"

      # Specify which network Traefik should use
      - "traefik.docker.network=homeserver"

      # HTTP Router (redirect to HTTPS)
      - "traefik.http.routers.bookwyrm-http.rule=Host(`bookwyrm.home.local`)"
      - "traefik.http.routers.bookwyrm-http.entrypoints=web"
      - "traefik.http.routers.bookwyrm-http.middlewares=redirect-to-https"

      # HTTPS Router
      - "traefik.http.routers.bookwyrm.rule=Host(`bookwyrm.home.local`)"
      - "traefik.http.routers.bookwyrm.entrypoints=websecure"
      - "traefik.http.routers.bookwyrm.tls=true"

      # Service configuration
      - "traefik.http.services.bookwyrm.loadbalancer.server.port=8000"

      # Middleware for HTTPS redirect
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
```

### Step 3: Ensure Other Bookwyrm Services Don't Expose to Traefik

Bookwyrm has multiple containers (postgres, redis, celery, etc). Make sure ONLY the web container has `traefik.enable=true`. For others:

```yaml
  postgres:
    # ... postgres config ...
    networks:
      - bookwyrm-network  # Only internal network, no homeserver
    labels:
      - "traefik.enable=false"  # Explicitly disable

  redis:
    # ... redis config ...
    networks:
      - bookwyrm-network
    labels:
      - "traefik.enable=false"

  celery_worker:
    # ... celery config ...
    networks:
      - bookwyrm-network
    labels:
      - "traefik.enable=false"
```

### Step 4: Migration Procedure

```bash
# 1. Navigate to Bookwyrm directory
cd external/bookwyrm-docker

# 2. Backup configuration
cp .env .env.backup
cp docker-compose.yml docker-compose.yml.backup

# 3. Update .env file
nano .env
# Set BOOKWYRM_DOMAIN=bookwyrm.home.local
# Set BOOKWYRM_USE_HTTPS=true

# 4. Update docker-compose.yml
nano docker-compose.yml
# Add homeserver network
# Add Traefik labels to web service

# 5. Stop Bookwyrm
docker compose down

# 6. Start Bookwyrm with new configuration
docker compose up -d

# 7. Check Bookwyrm logs
docker compose logs web --tail 50

# 8. Verify containers are running
docker compose ps

# 9. Check network connectivity
docker network inspect homeserver | grep bookwyrm

# 10. Return to main directory
cd ../..
```

### Testing Commands

```bash
# Test DNS resolution
nslookup bookwyrm.home.local
# Expected: resolves to SERVER_IP

# Test HTTP redirect
curl -I http://bookwyrm.home.local
# Expected: 301/302 redirect to https://bookwyrm.home.local

# Test HTTPS access
curl -Ik https://bookwyrm.home.local
# Expected: 200 OK, HTML content

# Test static files
curl -Ik https://bookwyrm.home.local/static/css/bookwyrm.css
# Expected: 200 OK

# Test media files (if any exist)
curl -Ik https://bookwyrm.home.local/images/
# Expected: 200 OK or 404 (if no images yet)

# Check Traefik discovered Bookwyrm
docker logs traefik | grep bookwyrm

# Check Bookwyrm logs
cd external/bookwyrm-docker
docker compose logs web | grep -i error
```

### Testing Checklist

#### Basic Access Tests
- [ ] DNS resolves bookwyrm.home.local to SERVER_IP
- [ ] HTTP redirects to HTTPS
- [ ] HTTPS loads with self-signed cert
- [ ] Bookwyrm homepage loads
- [ ] Backward compatibility: http://SERVER_IP:8000 still works

#### Functionality Tests
- [ ] Login page accessible
- [ ] Can login with existing account
- [ ] Can create new account (if registration open)
- [ ] User dashboard loads
- [ ] Book search works
- [ ] Can view book details
- [ ] Can add book to shelf
- [ ] Can post status/review
- [ ] Activity feed displays

#### Static and Media Files
- [ ] CSS files load correctly (check browser dev tools)
- [ ] JavaScript files load
- [ ] Book cover images display
- [ ] User profile images display
- [ ] No 404 errors for static assets

#### Database and Services
- [ ] PostgreSQL connection working (no DB errors)
- [ ] Redis connection working (cache/sessions)
- [ ] Celery workers processing tasks (check celery logs)
- [ ] Background jobs executing (book imports, etc.)

#### Federation Tests (if applicable)
- [ ] Can search remote instances
- [ ] Can follow remote users
- [ ] Can see federated content
- [ ] WebFinger working (if tested)

### Bookwyrm-Specific Considerations

#### Domain Change Impact
Bookwyrm uses the domain for federation (ActivityPub). Changing the domain may affect:
- **Existing federation relationships** - Remote instances may need to re-follow
- **ActivityPub identifiers** - Will use new domain
- **Shared links** - Old bookmarks will break

#### Database Migration
If changing domain from existing installation:
```bash
# Bookwyrm may need database update for domain change
cd external/bookwyrm-docker

# Run migrations
docker compose run --rm web python manage.py migrate

# Update site settings
docker compose run --rm web python manage.py shell
# In shell:
# from bookwyrm.models import SiteSettings
# site = SiteSettings.objects.get()
# site.domain = 'bookwyrm.home.local'
# site.save()
```

#### Static Files
Ensure static files are accessible:
```bash
# Collect static files
cd external/bookwyrm-docker
docker compose run --rm web python manage.py collectstatic --noinput
```

## Success Metrics
- Bookwyrm accessible via https://bookwyrm.home.local
- All functionality working (login, search, shelves, feeds)
- Static files and media loading correctly
- No errors in Bookwyrm, PostgreSQL, or Redis logs
- Database and cache connections stable
- Background workers processing tasks

## Common Issues and Solutions

### Issue: Static files not loading (404 errors)
**Solution:**
```bash
cd external/bookwyrm-docker
docker compose run --rm web python manage.py collectstatic --noinput
docker compose restart web
```

### Issue: "Invalid HTTP_HOST header"
**Solution:**
```bash
# Update ALLOWED_HOSTS in Bookwyrm settings
# Edit .env to ensure BOOKWYRM_DOMAIN is correct
# Restart: docker compose restart web
```

### Issue: Database connection errors
**Solution:**
```bash
# Verify postgres is on bookwyrm-network
docker network inspect bookwyrm-network | grep postgres

# Check postgres logs
docker compose logs postgres --tail 50

# Verify database credentials in .env
```

### Issue: Federation broken after domain change
**Solution:**
```bash
# This is expected when changing domains
# Remote instances will need to re-discover your instance
# Update site settings to new domain (see above)
# Consider this a fresh start for federation
```

## Dependencies
- Ticket 01: Traefik deployment completed
- Ticket 04: DNS rewrites configured
- Ticket 06: n8n configuration completed (learning from similar service)
- Bookwyrm already deployed via make bookwyrm-setup

## Risk Considerations
- **Domain change affects federation** - Existing ActivityPub connections may break
- **Database migration needed** if changing from existing domain
- Bookwyrm has multiple containers - ensure only web is exposed to Traefik
- Static files must be properly served
- More complex than other services due to federation

## Rollback Plan
```bash
# Restore original configuration
cd external/bookwyrm-docker
cp .env.backup .env
cp docker-compose.yml.backup docker-compose.yml

# Restart Bookwyrm
docker compose down
docker compose up -d

# Verify
curl http://192.168.1.100:8000
```

## Next Steps
After completion:
- Update any bookmarked URLs to new domain
- Notify federated contacts of domain change (if applicable)
- Re-follow remote instances if needed
- Proceed to ticket 08 (Configure remaining services)

## Notes
- Bookwyrm uses ActivityPub for federation - domain is important
- Consider domain change carefully if instance is federated
- For new installations, domain change is straightforward
- For existing installations with federation, coordinate domain change
- Keep port 8000 exposed initially for backward compatibility
- External network connection is key for Traefik to discover Bookwyrm
