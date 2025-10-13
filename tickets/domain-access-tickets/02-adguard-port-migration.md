# Move AdGuard Home to Alternate Port

## Priority: 1 (Critical - Blocker for Traefik)
## Estimated Time: 1 hour
## Phase: Week 1 - Foundation

## Description
Move AdGuard Home from port 80 to an alternate port (8888) to free up port 80 for Traefik reverse proxy. AdGuard will then be accessed via Traefik at adguard.home.local instead of direct port access.

## Acceptance Criteria
- [ ] AdGuard Home moved from port 80 to port 8888
- [ ] AdGuard container restarted and healthy
- [ ] AdGuard admin interface accessible at SERVER_IP:8888
- [ ] DNS functionality (port 53) unaffected
- [ ] No service interruption for DNS resolution
- [ ] Port 80 freed for Traefik usage

## Technical Implementation Details

### Files to Modify
1. `docker-compose.yml` - Update AdGuard port mapping

### Current Configuration
```yaml
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard-home
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:53:53/tcp"
      - "${SERVER_IP}:53:53/udp"
      - "${SERVER_IP}:3000:3000/tcp"
      - "${SERVER_IP}:80:80/tcp"        # <- Change this
    volumes:
      - ./data/adguard/work:/opt/adguardhome/work
      - ./data/adguard/conf:/opt/adguardhome/conf
    networks:
      - homeserver
```

### New Configuration
```yaml
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard-home
    restart: unless-stopped
    ports:
      - "${SERVER_IP}:53:53/tcp"
      - "${SERVER_IP}:53:53/udp"
      - "${SERVER_IP}:3000:3000/tcp"
      - "${SERVER_IP}:8888:80/tcp"      # <- Changed to 8888
    volumes:
      - ./data/adguard/work:/opt/adguardhome/work
      - ./data/adguard/conf:/opt/adguardhome/conf
    networks:
      - homeserver
```

### Migration Steps
```bash
# 1. Edit docker-compose.yml to change port mapping
nano docker-compose.yml

# 2. Restart AdGuard container
docker compose up -d adguard

# 3. Verify AdGuard is running on new port
curl http://${SERVER_IP}:8888

# 4. Test DNS still works
nslookup google.com ${SERVER_IP}

# 5. Verify port 80 is now free
sudo netstat -tlnp | grep :80
# OR
sudo lsof -i :80
```

### Testing Commands
```bash
# Check AdGuard container status
docker ps | grep adguard

# Test admin interface on new port
curl -I http://192.168.1.100:8888

# Verify DNS still working
dig @192.168.1.100 google.com

# Confirm port 80 is free
nc -zv 192.168.1.100 80  # Should fail/refuse connection

# Check AdGuard logs for any errors
docker logs adguard-home | tail -20
```

## Success Metrics
- AdGuard admin interface accessible at http://SERVER_IP:8888
- DNS queries on port 53 continue working normally
- Port 80 is free for Traefik
- No errors in AdGuard logs
- Existing DNS filters and settings preserved

## Dependencies
- None - this can be done independently
- Should be completed BEFORE deploying Traefik

## Risk Considerations
- **Brief DNS interruption** during container restart (~5-10 seconds)
- Bookmarks/scripts using port 80 will need updating
- Consider doing during low-usage time
- **IMPORTANT:** DNS clients will not be affected as port 53 is unchanged

## Rollback Plan
```bash
# If issues occur, revert the port change
# Edit docker-compose.yml back to port 80
nano docker-compose.yml

# Restart AdGuard
docker compose up -d adguard

# Verify
curl http://${SERVER_IP}:80
```

## Next Steps
After completion:
- Complete ticket 01 (Traefik deployment) if not done
- Proceed to ticket 03 (Add Traefik labels to AdGuard)
- Update any bookmarks or scripts referencing AdGuard on port 80

## Notes
- Port 8888 chosen to avoid common port conflicts
- Alternative ports: 8080 (might conflict with cAdvisor or other services), 8888, 9999
- After Traefik setup, AdGuard will be accessed via adguard.home.local
- This migration can be done independently of other changes
- No configuration inside AdGuard needs to change
