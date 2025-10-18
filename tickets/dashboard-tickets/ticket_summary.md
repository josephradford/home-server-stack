# Dashboard Implementation - Tickets Summary

## Overview

This document provides a high-level overview of all tickets for implementing the Homepage Dashboard with Home Assistant and various integrations.

**Note**: Self-hosted Habitica integration has been moved to future work (see Future Features section).

## Ticket Order & Dependencies

```
Ticket 01 (Foundation)
    ↓
Ticket 02 (Homepage) ──→ Ticket 05 (Backend API)
    ↓                           ↓
Ticket 03 (Home Assistant) ←────┘
    ↓
Ticket 06 (Integrations: Transport, Calendar, Traffic)
    ↓
Ticket 07 (Testing & Integration)
    ↓
Ticket 09 (iOS & Fitness) [LOW PRIORITY]
    ↓
Ticket 10 (Maintenance & Docs)

Future Features (Not in Current Scope):
    Ticket 11 (Self-Hosted Habitica)
    Ticket 12 (Habitica ↔ Home Assistant)
```

## Tickets List

### Core Infrastructure

#### [Ticket 01: Project Structure](ticket_01_project_structure)
- **Estimated Time**: 30 minutes
- **Priority**: CRITICAL - Must be first
- **Deliverables**:
  - Directory structure
  - .env.example with all variables
  - Initial documentation
  - README updates

#### [Ticket 02: Homepage Dashboard](ticket_02_homepage_dashboard)
- **Estimated Time**: 1-2 hours
- **Priority**: HIGH
- **Deliverables**:
  - Homepage container configuration
  - YAML config files (settings, widgets, docker, bookmarks)
  - Setup script
  - Integration with existing services

#### [Ticket 03: Home Assistant](ticket_03_home_assistant)
- **Estimated Time**: 1-2 hours
- **Priority**: HIGH
- **Deliverables**:
  - Home Assistant container
  - Initial configuration
  - Zone setup
  - API token generation
  - Documentation

#### ~~[Ticket 04: Self-Hosted Habitica](ticket_04_habitica)~~ → **MOVED TO TICKET 11 (FUTURE WORK)**
- **Status**: OUT OF SCOPE - Moved to future features
- See Ticket 11 in Future Features section below

#### [Ticket 05: Backend API Service](ticket_05_backend_api)
- **Estimated Time**: 2-3 hours
- **Priority**: HIGH
- **Deliverables**:
  - Python Flask API
  - BOM weather endpoint
  - Transport NSW endpoint
  - Traffic endpoint (TomTom)
  - Home Assistant helpers
  - Dockerfile and deployment

### Integration Layer

#### [Ticket 06: Transport, Calendar & Traffic](ticket_06_integrations)
- **Estimated Time**: 2-3 hours
- **Priority**: MEDIUM
- **Deliverables**:
  - Transport NSW widgets (configurable stops)
  - Google Calendar integration
  - Traffic widgets with scheduling
  - Route scheduler script
  - Configuration documentation

#### [Ticket 07: Complete Integration & Testing](ticket_07_final_integration)
- **Estimated Time**: 2-4 hours
- **Priority**: HIGH
- **Deliverables**:
  - Master deployment script
  - Health check script
  - Backup script
  - Comprehensive testing guide
  - Integration validation

#### ~~[Ticket 08: Habitica ↔ Home Assistant](ticket_08_habitica_ha)~~ → **MOVED TO TICKET 12 (FUTURE WORK)**
- **Status**: OUT OF SCOPE - Moved to future features
- See Ticket 12 in Future Features section below

### Optional Features

#### [Ticket 09: iOS & Fitness Automation](ticket_09_ios_fitness)
- **Estimated Time**: 3-4 hours
- **Priority**: LOW - Complete last
- **Deliverables**:
  - iOS Companion App setup guide
  - Location tracking configuration
  - Device tracking (AirPods, etc.)
  - Health Auto Export setup
  - Person widgets for Homepage
- **Note**: Fitness → Habitica automations moved to future work (requires Tickets 11-12)

### Maintenance

#### [Ticket 10: Documentation & Maintenance](ticket_10_final_docs)
- **Estimated Time**: 2-3 hours
- **Priority**: MEDIUM
- **Deliverables**:
  - Maintenance guide
  - Update procedures
  - Troubleshooting guide
  - Deployment checklist
  - Long-term operation docs

### Future Features

#### [Ticket 11: Self-Hosted Habitica](ticket_11_habitica)
- **Estimated Time**: 2-3 hours
- **Priority**: FUTURE WORK
- **Status**: Not in current implementation scope
- **Planned Deliverables**:
  - Habitica + MongoDB + Redis
  - HTTPS with Nginx reverse proxy
  - SSL certificate generation
  - Setup script
  - Backup procedures

#### [Ticket 12: Habitica ↔ Home Assistant](ticket_12_habitica_ha)
- **Estimated Time**: 1-2 hours
- **Priority**: FUTURE WORK
- **Status**: Not in current implementation scope
- **Dependencies**: Requires Ticket 11 completion
- **Planned Deliverables**:
  - Habitica HA integration
  - Sample automations
  - Task ID helper script
  - Homepage widgets for Habitica stats
  - Integration documentation

## Total Estimated Time

### Current Scope (Tickets 01-10, excluding Habitica)
- **Core Setup** (Tickets 01-03, 05): 6-8 hours
- **Integration** (Ticket 06): 2-3 hours
- **Testing** (Ticket 07): 2-4 hours
- **Optional iOS** (Ticket 09): 3-4 hours
- **Documentation** (Ticket 10): 2-3 hours

**Total: 15-22 hours** (excluding iOS features: 12-18 hours)

### Future Work (Not in Current Scope)
- **Habitica Setup** (Ticket 11): 2-3 hours
- **Habitica Integration** (Ticket 12): 1-2 hours

**Future Total: 3-5 hours** (if implemented later)

## Quick Start Order

### Minimal Viable Dashboard (Day 1)
1. Ticket 01 - Structure
2. Ticket 02 - Homepage
3. Ticket 05 - Backend API
4. Basic testing

**Result**: Dashboard with weather, existing services

### Full Integration (Day 2-3)
5. Ticket 03 - Home Assistant
6. Ticket 06 - Transport & Traffic
7. Ticket 07 - Testing

**Result**: Complete dashboard with all current-scope features

### Optional Add-ons (Later)
8. Ticket 09 - iOS features (if desired)
9. Ticket 10 - Maintenance setup

### Future Features (If Desired)
10. Ticket 11 - Self-Hosted Habitica (future work)
11. Ticket 12 - Habitica ↔ Home Assistant integration (future work)

## Key Configuration Points

### Required Before Starting
- [ ] Transport NSW API key
- [ ] Server IP address
- [ ] Google Calendar iCal URL
- [ ] TomTom API key (optional)

### Required During Setup
- [ ] Home Assistant API token (after HA setup)
- [ ] Transport stop IDs
- [ ] Traffic route addresses

### Optional for Future Features
- [ ] Habitica API credentials (if implementing Ticket 11/12 later)

### Optional for Full Features
- [ ] iOS devices for location tracking
- [ ] Apple Watch for fitness tracking
- [ ] Health Auto Export app ($3.99)

## Success Criteria

### After Core Tickets (01-03, 05)
- ✅ Homepage accessible
- ✅ Weather displaying
- ✅ Existing services visible
- ✅ Home Assistant running
- ✅ API healthy

### After Integration (06-07)
- ✅ Transport times showing
- ✅ Traffic conditions displaying
- ✅ Calendar events visible
- ✅ All widgets functional
- ✅ Integration tests passing

### After Optional iOS Features (09)
- ✅ Location tracking working
- ✅ Family devices tracked
- ✅ Complete dashboard experience

### Future Work (Tickets 11-12, if implemented)
- ✅ Habitica accessible
- ✅ Habitica stats in Homepage
- ✅ Fitness automations active (requires iOS + Habitica)

## Important Notes

### Service Dependencies
- Homepage depends on: Backend API, Home Assistant
- Traffic widgets depend on: Backend API, TomTom key
- Transport widgets depend on: Backend API, Transport NSW key
- iOS features depend on: Home Assistant, iOS devices

### Future Feature Dependencies
- Habitica widgets depend on: Habitica (Ticket 11), Home Assistant integration (Ticket 12)
- Fitness automations depend on: iOS features (Ticket 09), Habitica integration (Ticket 12)

### Configuration Files
All configuration is centralized in:
- `.env` - All secrets and API keys
- `data/homepage/config/*.yaml` - Homepage configuration
- `data/homeassistant/configuration.yaml` - HA configuration
- `docker-compose.dashboard.yml` - Service definitions

### Ports Used
- 3100 - Homepage Dashboard
- 8123 - Home Assistant
- 5000 - Backend API

### Future Feature Ports (Tickets 11-12)
- 3000 - Habitica (HTTP direct)
- 443 - Habitica (HTTPS via Nginx)

### Resource Requirements
- **Minimum**: 8GB RAM, 500GB disk, 2 CPU cores
- **Recommended**: 16GB RAM, 1TB disk, 4 CPU cores
- **Expected Usage** (current scope): ~1GB RAM total, ~5GB disk
- **Expected Usage** (with Habitica future features): ~1.5GB RAM total, ~10GB disk

### Network Configuration
- All services use `home-server` Docker network
- Home Assistant uses `network_mode: host` for device discovery
- Services communicate by container name

## Testing Strategy

### Per-Ticket Testing
Each ticket includes:
- Acceptance criteria checklist
- Specific testing commands
- Expected results
- Troubleshooting tips

### Integration Testing (Ticket 07)
- End-to-end service connectivity
- All widgets displaying data
- No errors in any logs
- Health check passing

### User Acceptance Testing
- Dashboard accessible from all devices
- All family members can view data
- iOS apps connected (if Ticket 09 implemented)
- Future: Fitness automations working (requires Tickets 09, 11, 12)

## Risk Areas & Mitigation

### High Risk
1. **Home Assistant database growth**
   - Mitigation: Purge old data (30 days)
   - Monitoring: Check size weekly

2. **API key expiration**
   - Mitigation: Calendar reminders
   - Documentation: Rotation procedures

### Future Risk (If Implementing Habitica)
1. **Habitica MongoDB corruption** (Ticket 11)
   - Mitigation: Regular backups (Ticket 10)
   - Recovery: Restore from backup

### Medium Risk
1. **iOS app permissions**
   - Mitigation: Clear setup instructions (Ticket 09)
   - Support: Troubleshooting guide

2. **Network connectivity issues**
   - Mitigation: Health monitoring
   - Recovery: Network recreation script

### Future Medium Risk (If Implementing Habitica)
1. **SSL certificate expiration** (Habitica Nginx - Ticket 11)
   - Mitigation: Annual renewal reminder
   - Documentation: Renewal procedure

### Low Risk
1. **Widget display issues**
   - Mitigation: Validate YAML syntax
   - Recovery: Restore config from backup

2. **API rate limits**
   - Mitigation: Reasonable refresh intervals
   - Documentation: Rate limit guidelines

## Customization Points

### Easy to Customize
- Transport stops (add/remove in .env)
- Traffic routes (add/remove in .env)
- Homepage theme and colors
- Widget layouts and grouping
- Backup schedule

### Moderate Customization
- Adding new Homepage widgets
- Creating new HA automations
- Adding new API endpoints

### Moderate Customization (Future - Tickets 11-12)
- Customizing Habitica tasks (requires Ticket 11)

### Advanced Customization
- Custom backend API features
- Complex HA integrations
- Custom iOS shortcuts

### Advanced Customization (Future - Ticket 11)
- Modifying Habitica source (requires Ticket 11)

## Maintenance Schedule

### Daily
- Check dashboard accessibility
- Monitor container health

### Weekly
- Review health check output
- Check disk usage
- Review error logs

### Monthly
- Run full backup
- Update all containers
- Review and rotate logs
- Check API key validity

### Quarterly
- Test disaster recovery
- Review security settings
- Update documentation
- Clean old data

## Support Resources

### Documentation Locations
- `docs/DASHBOARD_SETUP.md` - Main setup guide
- `docs/TESTING.md` - Testing procedures
- `docs/TROUBLESHOOTING.md` - Common issues
- `docs/MAINTENANCE.md` - Long-term operation
- Each ticket has specific documentation

### Scripts
- `scripts/deploy-dashboard.sh` - Full deployment
- `scripts/health-check.sh` - System health
- `scripts/backup-dashboard.sh` - Backup creation
- `scripts/update-dashboard.sh` - Update all services

### Future Scripts (Tickets 11-12)
- `scripts/get-habitica-tasks.sh` - Get task IDs (Ticket 12)

### External Resources
- Homepage: https://gethomepage.dev/
- Home Assistant: https://www.home-assistant.io/
- Transport NSW: https://opendata.transport.nsw.gov.au/
- TomTom: https://developer.tomtom.com/

### Future Feature Resources (Tickets 11-12)
- Habitica: https://habitica.fandom.com/

## Completion Checklist

### Current Scope
Use this to track progress:

- [ ] Ticket 01: Project Structure ✓
- [ ] Ticket 02: Homepage Dashboard ✓
- [ ] Ticket 03: Home Assistant ✓
- [ ] ~~Ticket 04: Self-Hosted Habitica~~ → Moved to Ticket 11 (Future)
- [ ] Ticket 05: Backend API ✓
- [ ] Ticket 06: Transport & Traffic ✓
- [ ] Ticket 07: Integration & Testing ✓
- [ ] ~~Ticket 08: Habitica Integration~~ → Moved to Ticket 12 (Future)
- [ ] Ticket 09: iOS Features (Optional) ☐
- [ ] Ticket 10: Maintenance Docs ✓

### Future Features (Optional)
- [ ] Ticket 11: Self-Hosted Habitica ☐
- [ ] Ticket 12: Habitica ↔ HA Integration ☐

### Final Validation
- [ ] All services running
- [ ] Health check passing
- [ ] Backup created
- [ ] Documentation complete
- [ ] Family members onboarded
- [ ] Maintenance scheduled

## Next Steps After Completion

1. **Immediate** (Week 1)
   - Monitor stability
   - Fine-tune refresh intervals
   - Adjust layouts as needed

2. **Short Term** (Month 1)
   - Add more transport stops
   - Configure additional traffic routes
   - Create more HA automations
   - Optimize performance

3. **Long Term** (Ongoing)
   - Regular backups and updates
   - Monitor and adjust
   - Add new integrations
   - Consider implementing Habitica (Tickets 11-12)
   - Share learnings/contribute back

## Known Limitations

### Technical
- BOM weather uses unofficial API (may change)
- Transport NSW rate limited to 30 req/min
- Apple Health sync not instant (up to 30 min delay) - if using iOS features
- iOS location requires "Always" permission - if using iOS features

### Future Features Technical Limitations (Tickets 11-12)
- Habitica uses self-signed SSL (can upgrade to Let's Encrypt)
- Fitness automation requires iOS devices + Habitica

### Functional
- No authentication on Homepage (use VPN/firewall)
- Home Assistant requires separate login
- Traffic limited to TomTom coverage area
- Transport limited to NSW

### Future Features Functional Limitations (Tickets 11-12)
- Habitica requires separate login

### By Design
- Location tracking requires iOS Companion App (Ticket 09)
- Some widgets require specific API keys
- Self-hosted means you maintain it

## FAQ

**Q: Can I skip Home Assistant?**
A: Not recommended. You'll lose location tracking and other automation capabilities. Homepage can work without it, but Home Assistant adds significant value.

**Q: What happened to Habitica?**
A: Habitica (Tickets 04 and 08) has been moved to future work (Tickets 11 and 12). The current scope focuses on the core dashboard with Home Assistant, weather, transport, and traffic.

**Q: Can I use cloud Habitica instead of self-hosted?**
A: Yes! If you implement Ticket 11 later, you can use `https://habitica.com` instead of self-hosting. Self-hosted gives you more control and privacy.

**Q: Do I need iOS devices?**
A: No, but Ticket 09 features (location tracking) require them. The core dashboard works without iOS devices.

**Q: Can I add more family members later?**
A: Yes! Just install HA iOS app on their devices and add them as people in HA (if implementing Ticket 09).

**Q: What if I don't have an Apple Watch?**
A: The core dashboard doesn't require any Apple devices. Fitness features are optional (Tickets 09, 11, 12).

**Q: Can I customize the dashboard colors/theme?**
A: Yes! Edit `data/homepage/config/settings.yaml` - many themes and colors available.

**Q: How much does this cost?**
A: Just server electricity and optional Health Auto Export ($3.99). All other software is free/open source.

**Q: Can I access this from outside my home?**
A: Yes, but requires VPN or reverse proxy with authentication. Not covered in these tickets for security reasons.

## Success Story Template

After completion of current scope, your dashboard will:

✨ **Show you at a glance:**
- Current weather for North Parramatta
- Next train/bus departures
- Traffic conditions for your commute
- Upcoming calendar events
- All your Docker services

📍 **Keep your family connected (with Ticket 09):**
- Know when everyone arrives home
- Track lost AirPods
- See battery levels
- Geofencing automations

🏠 **Centralize your homelab:**
- Single dashboard for everything
- Monitor all services
- Quick access to all UIs
- Docker container status
- Home Assistant integration

### Future Features (Tickets 11-12, if implemented):

🎮 **Automatically gamify your life:**
- Complete Habitica tasks when you workout
- Earn XP for real-world activities
- Track habits with RPG mechanics
- Visual progress and achievements
- Your Habitica character progress on dashboard

---

**Current Scope Implementation Time**: 15-22 hours (12-18 without iOS)
**Future Features Time**: 3-5 hours (if desired)
**Maintenance**: 1-2 hours/month
**Result**: Your personal mission control center!

Good luck with the implementation!