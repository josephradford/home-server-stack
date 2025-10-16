# Dashboard Implementation Tickets

## Quick Start

Work through tickets in order:

```bash
# Start with Ticket 01
claude-code implement tickets/01-project-structure.md

# Then continue in sequence...
```

## Ticket List

### Phase 1: Core Infrastructure (Required)
1. **[01-project-structure.md](01-project-structure.md)** - Foundation setup (30 min)
   - Creates directory structure
   - Sets up .env.example
   - Initial documentation

2. **[02-homepage-dashboard.md](02-homepage-dashboard.md)** - Homepage setup (1-2 hours)
   - Homepage container
   - Configuration files
   - Integration with existing services

3. **[03-home-assistant.md](03-home-assistant.md)** - Home Assistant (1-2 hours)
   - HA container
   - Initial configuration
   - API token setup

4. **[04-habitica.md](04-habitica.md)** - Self-hosted Habitica (2-3 hours)
   - Habitica + MongoDB + Redis
   - HTTPS with Nginx
   - SSL certificates

5. **[05-backend-api.md](05-backend-api.md)** - Backend API (2-3 hours)
   - Python Flask API
   - BOM weather
   - Transport NSW
   - Traffic conditions

### Phase 2: Integration (Required)
6. **[06-transport-traffic.md](06-transport-traffic.md)** - Widgets (2-3 hours)
   - Transport NSW widgets
   - Traffic widgets with scheduling
   - Google Calendar

7. **[07-testing.md](07-testing.md)** - Integration & Testing (2-4 hours)
   - Master deployment script
   - Health checks
   - End-to-end testing

8. **[08-habitica-integration.md](08-habitica-integration.md)** - Habitica ↔ HA (1-2 hours)
   - Habitica HA integration
   - Sample automations
   - Stat widgets

### Phase 3: Optional Features
9. **[09-ios-fitness.md](09-ios-fitness.md)** - iOS Features (3-4 hours) **[LOW PRIORITY]**
   - iOS Companion App
   - Location tracking
   - Apple Health fitness automation
   - **Do this LAST**

### Phase 4: Maintenance
10. **[10-maintenance.md](10-maintenance.md)** - Documentation (2-3 hours)
    - Maintenance procedures
    - Update scripts
    - Troubleshooting guide

## Implementation Order

### Recommended Order
```
01 → 02 → 05 → 03 → 04 → 06 → 08 → 07 → 10 → 09 (optional)
```

### Why This Order?
- **01**: Foundation (must be first)
- **02 + 05**: Get basic dashboard working quickly
- **03 + 04**: Add automation platforms
- **06**: Connect everything together
- **08**: Habitica integration
- **07**: Validate everything works
- **10**: Set up maintenance
- **09**: Optional iOS features (if desired)

## Before You Start

### Required Information
- [ ] Server IP address
- [ ] Transport NSW API key (free from opendata.transport.nsw.gov.au)
- [ ] Google Calendar iCal URL
- [ ] TomTom API key (optional, for traffic)

### Optional Information (can add later)
- [ ] Transport stop IDs
- [ ] Traffic route addresses
- [ ] iOS devices for location/fitness

## Estimated Time

- **Core Setup** (Tickets 01-05): 8-11 hours
- **Integration** (Tickets 06-08): 5-8 hours  
- **Testing** (Ticket 07): 2-4 hours
- **Maintenance** (Ticket 10): 2-3 hours
- **Optional iOS** (Ticket 09): 3-4 hours

**Total: 17-26 hours** (without iOS)  
**With iOS: 20-30 hours**

## Progress Tracking

- [ ] Ticket 01: Project Structure
- [ ] Ticket 02: Homepage Dashboard
- [ ] Ticket 03: Home Assistant
- [ ] Ticket 04: Self-Hosted Habitica
- [ ] Ticket 05: Backend API
- [ ] Ticket 06: Transport & Traffic
- [ ] Ticket 07: Testing & Integration
- [ ] Ticket 08: Habitica Integration
- [ ] Ticket 09: iOS Features (Optional)
- [ ] Ticket 10: Maintenance

## Getting Help

- Each ticket has detailed acceptance criteria
- Testing commands included
- Troubleshooting tips provided
- See [TICKETS_SUMMARY.md](TICKETS_SUMMARY.md) for overview

## After Completion

Your dashboard will provide:
- 🌤️ Weather for North Parramatta
- 🚊 Real-time transport departures
- 🚗 Traffic conditions for your commute
- 📅 Google Calendar events
- 📍 Family location tracking
- 🎮 Gamified task management (Habitica)
- 💪 Fitness automation (Apple Watch → Habitica)
- 🐳 Docker container monitoring

All accessible from one beautiful dashboard at `http://YOUR_SERVER_IP:3100`

---

**Note**: Tickets are designed to be implemented by Claude Code sequentially. Each ticket builds on the previous ones.