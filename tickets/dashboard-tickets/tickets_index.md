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
1. **[ticket_01_project_structure.md](ticket_01_project_structure.md)** - Foundation setup (30 min)
   - Creates directory structure
   - Sets up .env.example
   - Initial documentation

2. **[ticket_02_homepage_dashboard.md](ticket_02_homepage_dashboard.md)** - Homepage setup (1-2 hours)
   - Homepage container
   - Configuration files
   - Integration with existing services

3. **[ticket_03_home_assistant.md](ticket_03_home_assistant.md)** - Home Assistant (1-2 hours)
   - HA container
   - Initial configuration
   - API token setup

5. **[ticket_05_backend_api.md](ticket_05_backend_api.md)** - Backend API (2-3 hours)
   - Python Flask API
   - BOM weather
   - Transport NSW
   - Traffic conditions

### Phase 2: Integration (Required)
6. **[ticket_06_integrations.md](ticket_06_integrations.md)** - Widgets (2-3 hours)
   - Transport NSW widgets
   - Traffic widgets with scheduling
   - Google Calendar

7. **[ticket_07_final_integration.md](ticket_07_final_integration.md)** - Integration & Testing (2-4 hours)
   - Master deployment script
   - Health checks
   - End-to-end testing

### Phase 3: Optional Features
9. **[ticket_09_ios_fitness.md](ticket_09_ios_fitness.md)** - iOS Features (3-4 hours) **[LOW PRIORITY]**
   - iOS Companion App
   - Location tracking
   - Apple Health data collection
   - **Do this LAST**

### Phase 4: Maintenance
10. **[ticket_10_final_docs.md](ticket_10_final_docs.md)** - Documentation (2-3 hours)
    - Maintenance procedures
    - Update scripts
    - Troubleshooting guide

### Phase 5: Future Work (Out of Scope)
11. **[ticket_11_habitica_setup.md](ticket_11_habitica_setup.md)** - Habitica Setup (2-3 hours) **[FUTURE]**
    - Self-hosted Habitica + MongoDB + Redis
    - HTTPS with Nginx
    - SSL certificates
    - **Implement later when gamification is desired**

12. **[ticket_12_habitica_integration.md](ticket_12_habitica_integration.md)** - Habitica Integration (1-2 hours) **[FUTURE]**
    - Habitica HA integration
    - Fitness automations
    - Task completion automation
    - **Requires Ticket 11 first**

## Implementation Order

### Recommended Order
```
01 → 02 → 05 → 03 → 06 → 07 → 10 → 09 (optional) → 11 → 12 (future)
```

### Why This Order?
- **01**: Foundation (must be first)
- **02 + 05**: Get basic dashboard working quickly
- **03**: Add Home Assistant
- **06**: Add integrations (transport, traffic, calendar)
- **07**: Validate everything works
- **10**: Set up maintenance
- **09**: Optional iOS features (if desired)
- **11-12**: Future work when gamification is desired

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

- **Core Setup** (Tickets 01-05): 6-8 hours
- **Integration** (Tickets 06-07): 4-7 hours
- **Maintenance** (Ticket 10): 2-3 hours
- **Optional iOS** (Ticket 09): 3-4 hours
- **Future Habitica** (Tickets 11-12): 3-5 hours (when desired)

**Total Current Scope: 12-18 hours** (without iOS)
**With iOS: 15-22 hours**
**With Future Habitica: 18-27 hours**

## Progress Tracking

### Current Scope
- [ ] Ticket 01: Project Structure
- [ ] Ticket 02: Homepage Dashboard
- [ ] Ticket 03: Home Assistant
- [ ] Ticket 05: Backend API
- [ ] Ticket 06: Transport & Traffic
- [ ] Ticket 07: Testing & Integration
- [ ] Ticket 09: iOS Features (Optional)
- [ ] Ticket 10: Maintenance

### Future Work (Out of Scope)
- [ ] Ticket 11: Habitica Setup (Future)
- [ ] Ticket 12: Habitica Integration (Future)

## Getting Help

- Each ticket has detailed acceptance criteria
- Testing commands included
- Troubleshooting tips provided
- See [TICKETS_SUMMARY.md](TICKETS_SUMMARY.md) for overview

## After Completion

### Current Scope Features
Your dashboard will provide:
- 🌤️ Weather for North Parramatta
- 🚊 Real-time transport departures
- 🚗 Traffic conditions for your commute
- 📅 Google Calendar events
- 📍 Family location tracking (with iOS app)
- 🐳 Docker container monitoring

### Future Features (Tickets 11-12)
When you implement Habitica:
- 🎮 Gamified task management
- 💪 Fitness automation (Apple Watch → Habitica)
- ⚡ Habit tracking with RPG mechanics

All accessible from one beautiful dashboard at `http://YOUR_SERVER_IP:3100`

---

**Note**:
- Tickets 01-10 are the current scope for a functional dashboard
- Tickets 11-12 are future work for adding gamification
- Tickets are designed to be implemented sequentially
- Each ticket builds on the previous ones