# Ticket 11: Remove Direct Port Access for Habitica and Bookwyrm

**Priority:** Low
**Estimated Time:** 30 minutes
**Category:** Security & Cleanup
**Status:** ⬜ Pending
**Dependencies:** Habitica and Bookwyrm fully stable with domain-based access
**Blocked By:** Habitica Traefik routing issues resolved

## Overview

Complete the port access removal process by removing direct IP:port bindings from Habitica and Bookwyrm services. These services were intentionally excluded from Ticket 10 due to:
- Habitica: Active Traefik routing issues preventing domain-based access
- Bookwyrm: External wrapper project requiring separate testing

## Current Situation

After Ticket 10 completion, these services still have direct port bindings:

| Service | Current Port Binding | Reason for Retention |
|---------|---------------------|---------------------|
| Habitica client | `${SERVER_IP}:8080:80` | Traefik routing not working reliably |
| Habitica server | `${SERVER_IP}:3002:3000` | Backend for habitica-client |
| Bookwyrm | `${SERVER_IP}:8000:8000` | External wrapper project, needs separate validation |

## Prerequisites

Before implementing this ticket:

### Habitica Prerequisites
- [ ] Resolve habitica.home.local browser hanging issue
- [ ] Verify Traefik can route to habitica-client container
- [ ] Test that habitica-server healthcheck passes consistently
- [ ] Confirm domain-based access works reliably for 1 week
- [ ] Document any Habitica-specific Traefik configuration requirements

### Bookwyrm Prerequisites
- [ ] Verify bookwyrm.home.local works via Traefik
- [ ] Test Bookwyrm functionality (login, book search, posting)
- [ ] Confirm external wrapper project compatibility with port removal
- [ ] Update bookwyrm-docker wrapper if needed
- [ ] Document any Bookwyrm-specific configuration

## Implementation Steps

### Step 1: Update docker-compose.habitica.yml

**habitica-client service:**
```yaml
habitica-client:
  image: awinterstein/habitica-client:${HABITICA_VERSION:-latest}
  container_name: habitica-client
  restart: unless-stopped
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:8080:80"

  # ADD: expose section
  expose:
    - 80

  environment:
    - TZ=${TIMEZONE}
  networks:
    - homeserver
  depends_on:
    habitica-server:
      condition: service_healthy
  labels:
    # ... existing Traefik labels ...
```

**habitica-server service:**
```yaml
habitica-server:
  image: awinterstein/habitica-server:${HABITICA_VERSION:-latest}
  container_name: habitica-server
  restart: unless-stopped
  # REMOVE: ports section
  # ports:
  #   - "${SERVER_IP}:3002:3000"

  # ADD: expose section
  expose:
    - 3000

  environment:
    # ... existing environment variables ...
```

### Step 2: Update Bookwyrm Configuration

Update the Bookwyrm wrapper's docker-compose.override.yml to remove port bindings:

```yaml
# In external/bookwyrm-docker/docker-compose.override.yml
services:
  web:
    # REMOVE: ports section
    # ports:
    #   - "${SERVER_IP}:8000:8000"

    # ADD: expose section
    expose:
      - 8000

    labels:
      # ... existing Traefik labels ...
```

### Step 3: Update Documentation

**README.md:**
```markdown
# Remove these lines from "Direct IP Access" section:
# - Habitica: `http://SERVER_IP:8080` (Legacy access)
# - Bookwyrm: `http://SERVER_IP:8000` (Legacy access)
```

**docs/DOMAIN-BASED-ACCESS.md:**
```markdown
# Update table entries:
| Habitica Habit Tracker | `https://habitica.home.local` | N/A (Traefik only) | - |
| Bookwyrm Book Tracking | `https://bookwyrm.home.local` | N/A (Traefik only) | - |
```

**Makefile:**
```makefile
# In bookwyrm-setup target, update message:
@echo "✓ Bookwyrm setup complete!"
@echo "  - Accessible at: https://bookwyrm.home.local"
# REMOVE: @echo "  - Also available at: http://$$SERVER_IP:8000 (backward compatibility)"
```

### Step 4: Update .env.example Comments

```bash
# Habitica Configuration - Gamified habit and task tracker
# Accessible via https://habitica.home.local (Traefik handles SSL)
# REMOVE: "Accessible via http://SERVER_IP:8080"

# Bookwyrm Configuration - Social reading and book tracking
# Accessible via https://bookwyrm.home.local (Traefik handles SSL)
# REMOVE: "Accessible via VPN at http://SERVER_IP:8000"
```

## Testing Checklist

### Habitica Testing
- [ ] habitica-client and habitica-server start successfully
- [ ] `curl http://192.168.1.101:8080` returns connection refused
- [ ] `curl http://192.168.1.101:3002` returns connection refused
- [ ] `curl -k https://habitica.home.local` returns 200 OK
- [ ] Browser can load https://habitica.home.local
- [ ] Can log in to Habitica via domain
- [ ] Can create and complete tasks
- [ ] No errors in Traefik logs for habitica routes
- [ ] Both containers remain healthy for 24 hours

### Bookwyrm Testing
- [ ] All Bookwyrm services start successfully
- [ ] `curl http://192.168.1.101:8000` returns connection refused
- [ ] `curl -k https://bookwyrm.home.local` returns 200 OK
- [ ] Browser can load https://bookwyrm.home.local
- [ ] Can log in to Bookwyrm via domain
- [ ] Can search and add books
- [ ] Can post status updates
- [ ] Federation works correctly (if enabled)
- [ ] No errors in Traefik logs for bookwyrm routes
- [ ] All containers remain healthy for 24 hours

## Rollback Plan

If issues occur with either service:

**Habitica rollback:**
```bash
# Restore port bindings in docker-compose.habitica.yml
git checkout HEAD^ -- docker-compose.habitica.yml
docker compose -f docker-compose.habitica.yml up -d
```

**Bookwyrm rollback:**
```bash
# Restore port bindings in wrapper
cd external/bookwyrm-docker
git checkout HEAD^ -- docker-compose.override.yml
make restart
```

## Success Criteria

- ✅ Habitica accessible only via https://habitica.home.local
- ✅ Bookwyrm accessible only via https://bookwyrm.home.local
- ✅ Direct IP:port access returns "connection refused" for both services
- ✅ No service downtime during migration
- ✅ No errors in service or Traefik logs
- ✅ All functionality works correctly via domain names
- ✅ Documentation updated to reflect domain-only access

## Security Impact

Once complete, this ticket will:
- ✅ Ensure ALL user-facing services enforce HTTPS via Traefik
- ✅ Eliminate final HTTP access bypasses
- ✅ Complete the domain-based access security model
- ✅ Centralize all traffic through single monitored entry point

## Notes

- **Do not implement until prerequisites are met**
- Habitica Traefik routing issues must be resolved first (see conversation logs)
- Test thoroughly before removing port bindings
- Consider a longer monitoring period (1-2 weeks) due to previous issues
- Bookwyrm is an external wrapper - coordinate changes carefully

## Related Issues

- Habitica healthcheck issues (resolved in previous commits)
- Habitica domain access hanging in browser (unresolved - blocker for this ticket)
- Bookwyrm Traefik integration (implemented but needs validation)

## Related Tickets

- **Ticket 10:** Remove Direct Port Access (completed - foundation)
- **Ticket 03:** Initial Service Labels (Traefik configuration)
- **Ticket 09:** Update Documentation (docs update template)

---

**Created:** 2025-10-17
**Target Completion:** After Habitica and Bookwyrm domain-based access is stable and validated
