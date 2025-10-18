# Ticket 09: iOS Integration & Fitness Automation

**Priority: LOW** - Complete after all other tickets

## Objective
Configure Home Assistant iOS Companion App for location tracking, device tracking, and Apple Health fitness data export.

## Note
This ticket currently only covers location/device tracking and fitness data collection. Fitness automation (auto-completing tasks) will be added in future Habitica tickets (11 & 12).

## Prerequisites
- Home Assistant fully configured (Ticket 03)
- iPhone/iPad with iOS 16+ or iPadOS 16+
- Apple Watch (optional, for fitness tracking)

## Tasks

### 1. Install Home Assistant Companion App

**On each iOS device:**

1. Download "Home Assistant" from App Store (free)
2. Open the app
3. It should auto-discover your Home Assistant instance
4. Or manually enter: `http://SERVER_IP:8123`
5. Login with your Home Assistant account
6. Grant permissions when prompted:
   - ✅ **Location**: "Always" (for family tracking)
   - ✅ **Precise Location**: Enable
   - ✅ **Notifications**: Allow
   - ✅ **Motion & Fitness**: Allow (for activity sensors)

### 2. Configure Location Tracking

**In the iOS App:**

1. Open app → Settings (gear icon)
2. Tap "Companion App"
3. Enable "Location Sensors":
   - ✅ Location
   - ✅ Zone
   - ✅ Activity
   - ✅ Geocoded Location

4. Configure update frequency:
   - Tap "Location" → "Update Interval"
   - Recommended: "Significant Location Change" (battery friendly)
   - Or: "Every 5 minutes" (more accurate, more battery)

5. Enable background updates:
   - iOS Settings → Home Assistant
   - Enable "Background App Refresh"

**In Home Assistant:**

1. Go to Settings → People
2. Add each family member
3. Assign device trackers:
   - Click person → Add device tracker
   - Select: `device_tracker.PHONE_NAME`

### 3. Configure Device Tracking (AirPods, iPads, etc.)

**In iOS App:**

1. Settings → Companion App → "Device Sensors"
2. Enable sensors for devices you want to track:
   - ✅ Battery Level
   - ✅ Battery State
   - ✅ Connectivity (WiFi, Cellular)

**iCloud Device Tracking:**

Home Assistant iOS app tracks Find My devices automatically:
- AirPods (when connected or last known location)
- iPads
- Apple Watches
- Other iCloud devices

These appear as entities: `device_tracker.airpods_pro`, etc.

### 4. Install Health Auto Export App

**For Apple Health → Habitica automation:**

1. Download "Health Auto Export" from App Store ($3.99 one-time)
2. Open app
3. Grant Health app permissions:
   - ✅ Workouts
   - ✅ Steps
   - ✅ Active Energy
   - ✅ Any other metrics you want

### 5. Configure Health Auto Export

**Create Automation:**

1. Open Health Auto Export
2. Tap "Automations" tab
3. Tap "New Automation"
4. Configure:
   - **Name**: "Home Assistant Fitness"
   - **Destination**: Custom (JSON)
   - **Enable**: ON

5. Set URL:
   ```
   http://YOUR_SERVER_IP:8123/api/webhook/apple_health
   ```

6. Add Headers:
   - Key: `Authorization`
   - Value: `Bearer YOUR_HA_TOKEN`

7. Configure Data:
   - **Include Workouts**: ON
   - **Data Type**: Health Metrics
   - **Sync Cadence**: 30 minutes
   - **Notify on Update**: ON (for debugging)

8. Add Widget to Home Screen:
   - Long press home screen → Add Widget
   - Search "Health Auto Export"
   - Add "Automations" widget
   - Select your automation

### 6. Create Home Assistant Webhook Handler

Add to `data/homeassistant/configuration.yaml`:

```yaml
# Webhook for Apple Health data
automation apple_health:
  - alias: "Process Apple Health Data"
    trigger:
      - platform: webhook
        webhook_id: apple_health
    action:
      - service: python_script.process_health_data
        data:
          data: "{{ trigger.json }}"
```

### 7. Create Python Script for Health Data Processing

Create `data/homeassistant/python_scripts/process_health_data.py`:

```python
"""
Process Apple Health data and update Habitica
"""

# Get workout data from webhook
health_data = data.get('data', {})
workouts = health_data.get('workouts', [])

# Log received data
logger.info(f"Received {len(workouts)} workouts from Apple Health")

# Check if there are any workouts
if not workouts:
    logger.info("No workouts in this update")
else:
    for workout in workouts:
        workout_type = workout.get('type', 'Unknown')
        duration_minutes = workout.get('duration', 0) / 60
        
        logger.info(f"Workout detected: {workout_type} for {duration_minutes:.0f} minutes")
        
        # Fire event for automation to handle
        hass.bus.fire('apple_health_workout', {
            'type': workout_type,
            'duration_minutes': duration_minutes,
            'calories': workout.get('activeEnergy', 0),
            'date': workout.get('start')
        })
```

### 8. (FUTURE) Create Habitica Fitness Automations

**NOTE:** This section is for future implementation when Habitica is added (Tickets 11 & 12).

Create `data/homeassistant/automations/habitica_fitness.yaml` (when implementing Habitica):

```yaml
# ============================================================================
# APPLE WATCH / APPLE HEALTH FITNESS AUTOMATIONS
# ============================================================================

# Complete workout daily when any workout detected
- id: habitica_workout_detected
  alias: "Habitica: Complete Workout Daily"
  description: "Mark workout daily complete when Apple Watch workout detected"
  trigger:
    - platform: event
      event_type: apple_health_workout
  action:
    - service: habitica.api_call
      data:
        name: score_task
        args:
          task_id: "your-workout-daily-id"  # Get from Habitica
          direction: "up"
    - service: notify.mobile_app_iphone
      data:
        title: "💪 Workout Logged!"
        message: >
          {{ trigger.event.data.type }} workout completed! 
          Duration: {{ trigger.event.data.duration_minutes | round(0) }} minutes
          +XP in Habitica!

# Score running habit for running workouts
- id: habitica_running_habit
  alias: "Habitica: Score Running Habit"
  description: "Score running habit when running workout detected"
  trigger:
    - platform: event
      event_type: apple_health_workout
      event_data:
        type: "Running"
  action:
    - service: habitica.api_call
      data:
        name: score_habit
        args:
          task_id: "your-running-habit-id"
          direction: "up"

# Score strength training habit
- id: habitica_strength_habit
  alias: "Habitica: Score Strength Training Habit"
  description: "Score strength habit for weight training"
  trigger:
    - platform: event
      event_type: apple_health_workout
  condition:
    - condition: template
      value_template: >
        {{ 'Strength' in trigger.event.data.type or 'Weight' in trigger.event.data.type }}
  action:
    - service: habitica.api_call
      data:
        name: score_habit
        args:
          task_id: "your-strength-habit-id"
          direction: "up"

# Complete 10k steps daily
- id: habitica_10k_steps
  alias: "Habitica: Complete 10k Steps Daily"
  description: "Mark steps daily complete when 10k steps reached"
  trigger:
    - platform: event
      event_type: apple_health_workout
  condition:
    - condition: template
      value_template: >
        {{ state_attr('sensor.iphone_steps', 'value') | int > 10000 }}
    # Only trigger once per day
    - condition: template
      value_template: >
        {{ (now() - state_attr('automation.habitica_10k_steps', 'last_triggered')).days >= 1 }}
  action:
    - service: habitica.api_call
      data:
        name: score_task
        args:
          task_id: "your-10k-steps-daily-id"
          direction: "up"
```

### 9. Create Person/Location Widgets for Homepage

Update `data/homepage/config/services.yaml`:

```yaml
- Family & Location:
    - Home Assistant:
        icon: home-assistant.png
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:8123
        description: Location & Automation Hub

    - Person 1:
        icon: mdi-account-circle
        description: Current location
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: person.person1  # Replace with actual person entity
              label: Location
              field: state
            - state: sensor.person1_iphone_battery_level
              label: Battery
              field: state
              suffix: "%"
            - state: sensor.person1_iphone_geocoded_location
              label: Address
              field: state

    - Person 2:
        icon: mdi-account-circle
        description: Current location
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: person.person2
              label: Location
              field: state
            - state: sensor.person2_iphone_battery_level
              label: Battery
              field: state
              suffix: "%"

    - Devices:
        icon: mdi-devices
        description: Family devices
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: device_tracker.airpods_pro
              label: AirPods Pro
              field: state
            - state: device_tracker.ipad
              label: iPad
              field: state

    - Family Map:
        icon: mdi-map-marker-multiple
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:8123/lovelace/map
        description: View on map
```

### 10. Create iOS Setup Documentation

Create `docs/IOS_SETUP.md`:

```markdown
# iOS Setup Guide

## Overview

This guide covers setting up iOS devices for:
- Family location tracking
- Device tracking (AirPods, iPads, etc.)
- Apple Health fitness data export
- Habitica fitness automation

## Setup Checklist

### For Each Family Member's iPhone

- [ ] Install Home Assistant Companion App
- [ ] Grant location permissions ("Always")
- [ ] Enable precise location
- [ ] Configure location sensors
- [ ] Add person in Home Assistant
- [ ] Verify location tracking works

### For Fitness Tracking (Optional)

- [ ] Purchase Health Auto Export ($3.99)
- [ ] Grant Health app permissions
- [ ] Configure automation with webhook
- [ ] Add widget to home screen
- [ ] Create Habitica workout tasks
- [ ] Configure fitness automations
- [ ] Test with a workout

## Detailed Steps

See sections 1-9 in this ticket for complete instructions.

## Troubleshooting

### Location not updating
- Check app permissions: Settings → Home Assistant → Location → Always
- Enable Background App Refresh
- Check battery settings (not in Low Power Mode)
- Restart Home Assistant iOS app

### Health data not syncing
- Check webhook URL is correct
- Verify HA token in Health Auto Export
- Add widget to home screen (required for background)
- Check Health Auto Export activity log
- Test manual sync in app

### Person showing "Away" when home
- Check Home zone radius in HA (Settings → Areas)
- Verify location permissions are "Always"
- Check GPS accuracy (Settings → Privacy → Location Services → System Services → Status Bar Icon)

### AirPods not showing
- AirPods must be connected to show live location
- Last known location persists in Home Assistant
- Rename in Settings if name conflicts with other devices

## Privacy Considerations

- Location data stays on your Home Assistant server
- No third-party tracking services
- iCloud credentials never shared with HA
- Health data transmitted directly to your server
- All data encrypted in transit (if using HTTPS)

## Battery Impact

- Location tracking: Minimal with "Significant Change" mode
- Health Export: Minimal (syncs every 30 min)
- Recommended settings for best battery:
  - Location: Significant Location Change
  - Health Sync: 30-60 minutes
  - Background App Refresh: On (but not excessive)

## Testing

1. **Location Tracking:**
   - Leave home
   - Check person entity changes to "Away"
   - Return home
   - Check entity changes to "Home"

2. **Fitness Automation:**
   - Do a 5-minute workout on Apple Watch
   - Wait for Health Export sync (up to 30 min)
   - Check Home Assistant logs for workout event
   - Verify Habitica task completed

3. **Device Tracking:**
   - Check AirPods entity in HA
   - Should show "Home" or last location
   - Battery level should be visible
```

## Acceptance Criteria
- [ ] iOS app installation instructions documented
- [ ] Location tracking configured and working
- [ ] Device tracking (AirPods, etc.) visible in HA
- [ ] Health Auto Export app configured
- [ ] Webhook handler created in HA
- [ ] Python script for health processing created
- [ ] Fitness data collection working (automations deferred to Habitica tickets)
- [ ] Person widgets added to Homepage
- [ ] Testing procedures documented
- [ ] Troubleshooting guide provided
- [ ] Privacy considerations documented

## Testing
```bash
# In Home Assistant, check for person entities
# Go to Developer Tools → States
# Search for: person.

# Check device trackers
# Search for: device_tracker.

# Test webhook (after configuring Health Auto Export)
# Send test data:
curl -X POST http://SERVER_IP:8123/api/webhook/apple_health \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "workouts": [
        {
          "type": "Running",
          "duration": 1800,
          "activeEnergy": 350,
          "start": "2025-01-15T10:00:00Z"
        }
      ]
    }
  }'

# Check HA logs for processing
docker logs homeassistant | grep -i workout

# Verify Habitica task was completed
# Check in Habitica web UI
```

## Dependencies
- Ticket 03: Home Assistant setup and configured
- iOS devices (iPhone/iPad)
- Apple Watch (optional, for fitness)
- Home Assistant API token obtained

## Notes
- **LOW PRIORITY**: Complete this ticket last, after core functionality works
- Requires physical iOS devices - cannot be tested without them
- Health Auto Export requires iOS 14+ and costs $3.99
- Location tracking works without Apple Watch
- Fitness automation requires Apple Watch or other fitness device
- Privacy-focused: all data stays on your server
- Battery impact minimal with recommended settings
- Python scripts require Home Assistant's python_script integration
- Webhook must be accessible from iOS devices (same network or VPN)
- Test incrementally: location first, then fitness
- Family members can opt in/out individually
- Each person needs their own HA user account (or share one)
- Entity names include device name (e.g., device_tracker.johns_iphone)
- Health data sync can take up to 30 minutes (not instant)
- Widget on home screen is REQUIRED for background sync
- Consider adding to Lock Screen widgets for quick access
- Fitness automation (auto-completing tasks) will be added in Habitica tickets (11 & 12)
