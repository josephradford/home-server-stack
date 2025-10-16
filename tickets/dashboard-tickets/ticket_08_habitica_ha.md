# Ticket 08: Habitica Integration with Home Assistant

## Objective
Integrate self-hosted Habitica with Home Assistant for task automation and stat tracking.

## Tasks

### 1. Configure Habitica Integration in Home Assistant

After obtaining Habitica API credentials, add to Home Assistant UI:

Create `docs/HABITICA_HA_INTEGRATION.md`:

```markdown
# Habitica Home Assistant Integration

## Prerequisites

1. Habitica instance running (see Ticket 04)
2. Habitica account created
3. Home Assistant running (see Ticket 03)
4. Habitica API credentials obtained

## Get Habitica API Credentials

1. Login to Habitica at https://SERVER_IP (or http://SERVER_IP:3000)
2. Click Settings (gear icon) → API
3. Copy your:
   - **User ID**: `abc123de-f456-7890-ghij-klmn12345678`
   - **API Token**: `def456gh-i789-0123-jklm-nopq45678901`

## Add Integration to Home Assistant

### Method 1: UI Configuration (Recommended)

1. Open Home Assistant at http://SERVER_IP:8123
2. Go to **Settings** → **Devices & Services**
3. Click **+ Add Integration**
4. Search for "Habitica"
5. Select **"Login to other instances"**
6. Enter:
   - **URL**: `http://habitica:3000` (or your HABITICA_BASE_URL)
   - **User ID**: Your Habitica User ID
   - **API Token**: Your Habitica API Token
   - **Verify SSL**: Uncheck (for self-signed certificates)
7. Click **Submit**

### Method 2: Configuration.yaml

Add to `data/homeassistant/configuration.yaml`:

```yaml
habitica:
  api_user: !secret habitica_user_id
  api_key: !secret habitica_api_token
  url: http://habitica:3000
```

Add to `data/homeassistant/secrets.yaml`:

```yaml
habitica_user_id: abc123de-f456-7890-ghij-klmn12345678
habitica_api_token: def456gh-i789-0123-jklm-nopq45678901
```

Restart Home Assistant:
```bash
docker restart homeassistant
```

## Verify Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Find "Habitica" - should show as "Configured"
3. Click on it to see available entities
4. Go to **Developer Tools** → **States**
5. Search for "habitica" - you should see entities like:
   - `sensor.habitica_USERNAME_level`
   - `sensor.habitica_USERNAME_health`
   - `sensor.habitica_USERNAME_experience`
   - `sensor.habitica_USERNAME_gold`

## Available Entities

### Character Stats
- `sensor.habitica_USERNAME_display_name` - Character name
- `sensor.habitica_USERNAME_level` - Current level
- `sensor.habitica_USERNAME_class` - Character class (Warrior, Rogue, Healer, Mage)
- `sensor.habitica_USERNAME_health` - HP
- `sensor.habitica_USERNAME_health_max` - Max HP
- `sensor.habitica_USERNAME_experience` - Current XP
- `sensor.habitica_USERNAME_experience_max` - XP to next level
- `sensor.habitica_USERNAME_mana` - MP (level 10+)
- `sensor.habitica_USERNAME_mana_max` - Max MP
- `sensor.habitica_USERNAME_gold` - Gold

### Quest Info (if in party)
- `sensor.habitica_USERNAME_quest` - Current quest name
- `sensor.habitica_USERNAME_quest_boss_health` - Boss HP remaining
- `sensor.habitica_USERNAME_member_count` - Party members

### Switches
- `switch.habitica_USERNAME_rest_in_the_inn` - Pause damage from dailies

### To-Do Lists
- `todo.habitica_USERNAME_todos` - Your to-do list
- `todo.habitica_USERNAME_dailies` - Your dailies list

### Calendars
- `calendar.habitica_USERNAME_todo_calendar` - To-dos with due dates
- `calendar.habitica_USERNAME_dailies_calendar` - Dailies schedule

## Update Homepage with Habitica Stats

After integration is working, update `.env`:

```bash
# Add Habitica credentials (from above)
HABITICA_USER_ID=abc123de-f456-7890-ghij-klmn12345678
HABITICA_API_TOKEN=def456gh-i789-0123-jklm-nopq45678901
```

Restart Homepage:
```bash
docker compose -f docker-compose.dashboard.yml restart homepage
```

The Habitica widgets in Homepage should now display your character stats!

## Troubleshooting

### Integration fails to add
- **Error: "Invalid credentials"**
  - Verify User ID and API Token are correct
  - Check for extra spaces when copying
  
- **Error: "Cannot connect"**
  - Verify Habitica is running: `docker ps | grep habitica`
  - Check URL is correct: `http://habitica:3000`
  - Try using IP instead: `http://SERVER_IP:3000`

- **SSL Certificate Error**
  - Uncheck "Verify SSL" in integration config
  - Or configure proper SSL certificate (see Ticket 04)

### Entities not showing
- Wait 1-2 minutes for initial sync
- Restart Home Assistant: `docker restart homeassistant`
- Check HA logs: `docker logs homeassistant | grep habitica`

### Stats not updating
- Check Habitica is accessible from HA:
  ```bash
  docker exec homeassistant curl http://habitica:3000
  ```
- Verify network connectivity
- Check for API rate limits (30 requests/minute max)

## Update Environment Variables

After successful integration, update `.env` file:

```bash
# Habitica API Credentials (add these)
HABITICA_USER_ID=your_user_id_here
HABITICA_API_TOKEN=your_api_token_here
```

Then restart Homepage to display stats:
```bash
docker compose -f docker-compose.dashboard.yml restart homepage
```
```

### 2. Create Sample Habitica Automations

Create `data/homeassistant/automations/habitica.yaml`:

```yaml
# Sample Habitica Automations
# Copy these to your automations.yaml or create separate file

# ============================================================================
# EXAMPLE: Complete Daily Task When Workout Detected
# ============================================================================
- id: habitica_workout_complete
  alias: "Habitica: Complete Workout Daily"
  description: "Mark workout daily complete when Apple Health workout detected"
  trigger:
    - platform: webhook
      webhook_id: health_workout
  condition:
    - condition: template
      value_template: "{{ trigger.json.workouts | length > 0 }}"
  action:
    - service: habitica.api_call
      data:
        name: score_task
        args:
          task_id: "your-workout-daily-task-id"  # Replace with your task ID
          direction: "up"
    - service: notify.persistent_notification
      data:
        title: "💪 Workout Logged!"
        message: "Your Habitica workout daily has been completed. +XP!"

# ============================================================================
# EXAMPLE: Low Health Warning
# ============================================================================
- id: habitica_low_health_warning
  alias: "Habitica: Low Health Warning"
  description: "Send notification when HP drops below 20"
  trigger:
    - platform: numeric_state
      entity_id: sensor.habitica_USERNAME_health  # Replace USERNAME
      below: 20
  action:
    - service: notify.mobile_app_your_phone  # Replace with your device
      data:
        title: "⚠️ Low Health in Habitica!"
        message: "Your HP is {{ states('sensor.habitica_USERNAME_health') }}. Complete some tasks!"
        data:
          url: /lovelace/habitica

# ============================================================================
# EXAMPLE: Level Up Celebration
# ============================================================================
- id: habitica_level_up
  alias: "Habitica: Level Up Celebration"
  description: "Flash lights when you level up"
  trigger:
    - platform: state
      entity_id: sensor.habitica_USERNAME_level  # Replace USERNAME
  condition:
    - condition: template
      value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: "🎉 Level Up!"
        message: "You reached level {{ states('sensor.habitica_USERNAME_level') }}!"
    # Optional: Flash lights if you have smart bulbs
    # - service: light.turn_on
    #   target:
    #     entity_id: light.living_room
    #   data:
    #     flash: long

# ============================================================================
# EXAMPLE: Daily Task Reminder
# ============================================================================
- id: habitica_daily_reminder
  alias: "Habitica: Daily Task Reminder"
  description: "Remind to complete dailies at 8 PM"
  trigger:
    - platform: time
      at: "20:00:00"
  condition:
    - condition: template
      value_template: "{{ states('todo.habitica_USERNAME_dailies') | int > 0 }}"
  action:
    - service: notify.mobile_app_your_phone
      data:
        title: "📋 Habitica Reminder"
        message: "You have {{ states('todo.habitica_USERNAME_dailies') }} dailies left to complete today!"

# ============================================================================
# EXAMPLE: Create To-Do When Dishwasher Finishes
# ============================================================================
- id: habitica_dishwasher_todo
  alias: "Habitica: Create Dishwasher To-Do"
  description: "Create to-do when dishwasher cycle completes"
  trigger:
    - platform: state
      entity_id: sensor.dishwasher_status  # Replace with your sensor
      to: "complete"
  action:
    - service: habitica.api_call
      data:
        name: add_task
        args:
          type: "todo"
          text: "Empty the dishwasher"
          notes: "Dishes are clean and ready to put away"

# ============================================================================
# NOTE: To use these automations
# ============================================================================
# 1. Replace USERNAME with your Habitica username (lowercase)
# 2. Replace task_id with your actual task IDs (get from Habitica API)
# 3. Replace sensor names with your actual device entities
# 4. Uncomment sections you want to use
# 5. Restart Home Assistant after editing
```

### 3. Create Task ID Helper Script

Create `scripts/get-habitica-tasks.sh`:

```bash
#!/bin/bash
# Helper script to get Habitica task IDs

source .env

if [ -z "$HABITICA_USER_ID" ] || [ -z "$HABITICA_API_TOKEN" ]; then
    echo "❌ Habitica credentials not set in .env"
    exit 1
fi

HABITICA_URL=${HABITICA_BASE_URL:-http://localhost:3000}

echo "🎮 Fetching your Habitica tasks..."
echo ""

# Get all tasks
response=$(curl -s \
    -H "x-api-user: $HABITICA_USER_ID" \
    -H "x-api-key: $HABITICA_API_TOKEN" \
    -H "x-client: $(uuidgen)" \
    "$HABITICA_URL/api/v3/tasks/user")

echo "📋 DAILIES:"
echo "$response" | jq -r '.data[] | select(.type=="daily") | "  \(.text) - ID: \(.id)"'

echo ""
echo "✅ TO-DOS:"
echo "$response" | jq -r '.data[] | select(.type=="todo") | "  \(.text) - ID: \(.id)"'

echo ""
echo "💪 HABITS:"
echo "$response" | jq -r '.data[] | select(.type=="habit") | "  \(.text) - ID: \(.id)"'

echo ""
echo "Copy the task IDs to use in Home Assistant automations"
```

Make executable:
```bash
chmod +x scripts/get-habitica-tasks.sh
```

### 4. Update Homepage services.yaml

Verify the Habitica section in `data/homepage/config/services.yaml` has correct entity names:

```yaml
- Habitica RPG:
    - Character Stats:
        icon: mdi-shield-account
        href: {{HOMEPAGE_VAR_HABITICA_URL}}
        description: Your RPG character
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: sensor.habitica_USERNAME_level  # Replace USERNAME with yours
              label: Level
              field: state
            - state: sensor.habitica_USERNAME_health  # Replace USERNAME
              label: HP
              field: state
            - state: sensor.habitica_USERNAME_experience  # Replace USERNAME
              label: XP
              field: state
            - state: sensor.habitica_USERNAME_gold  # Replace USERNAME
              label: Gold
              field: state

    - Resources:
        icon: mdi-treasure-chest
        description: Character resources
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: sensor.habitica_USERNAME_mana  # Replace USERNAME
              label: Mana
              field: state
            - state: sensor.habitica_USERNAME_class  # Replace USERNAME
              label: Class
              field: state

    - Open Habitica:
        icon: habitica.png
        href: {{HOMEPAGE_VAR_HABITICA_URL}}
        description: Go to Habitica
```

**Note:** Replace `USERNAME` with your actual Habitica username (lowercase, no spaces).

### 5. Create Habitica Dashboard Card for Home Assistant

Create `data/homeassistant/lovelace/habitica_card.yaml`:

```yaml
# Add this to your Lovelace dashboard
# Edit dashboard → Add card → Manual card

type: vertical-stack
title: Habitica Character
cards:
  - type: entities
    entities:
      - entity: sensor.habitica_USERNAME_display_name
        name: Character
      - entity: sensor.habitica_USERNAME_level
        name: Level
      - entity: sensor.habitica_USERNAME_class
        name: Class

  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.habitica_USERNAME_health
        name: Health
        min: 0
        max: 50
        severity:
          green: 30
          yellow: 20
          red: 0

      - type: gauge
        entity: sensor.habitica_USERNAME_experience
        name: Experience
        min: 0
        max: 100

  - type: entities
    entities:
      - entity: sensor.habitica_USERNAME_gold
        name: Gold
      - entity: sensor.habitica_USERNAME_mana
        name: Mana
      - entity: switch.habitica_USERNAME_rest_in_the_inn
        name: Rest in Inn

  - type: todo-list
    entity: todo.habitica_USERNAME_dailies
    title: Today's Dailies
```

## Acceptance Criteria
- [ ] Habitica integration added to Home Assistant
- [ ] All Habitica entities visible in HA
- [ ] Character stats displaying correctly
- [ ] To-do lists accessible in HA
- [ ] Sample automations documented
- [ ] Task ID helper script created
- [ ] Homepage Habitica widgets showing data
- [ ] Documentation created
- [ ] Dashboard card example provided
- [ ] Integration survives restarts

## Testing
```bash
# Get Habitica API credentials
# (From Habitica UI: Settings → API)

# Add integration to Home Assistant
# (Via UI: Settings → Devices & Services → Add Integration → Habitica)

# Verify entities exist
# Go to Developer Tools → States
# Search for "habitica"

# Get task IDs
./scripts/get-habitica-tasks.sh

# Test automation (create a test daily/todo in Habitica first)
# In HA: Developer Tools → Services
# Service: habitica.api_call
# Service Data:
# name: score_task
# args:
#   task_id: "your-task-id"
#   direction: "up"

# Check Homepage
# Visit http://SERVER_IP:3100
# Verify Habitica stats display in dashboard
```

## Dependencies
- Ticket 03: Home Assistant setup
- Ticket 04: Habitica self-hosted
- Habitica account created
- Home Assistant API token obtained

## Notes
- Integration requires Habitica API credentials from Settings → API
- Entity names include username (lowercase)
- Rate limit: 30 requests per minute
- To-do lists and calendars available in HA 2024.10+
- Fitness automations configured in Ticket 09
- Replace all USERNAME placeholders with actual username
- Task IDs required for automation (use helper script)
- Integration survives container restarts
- Self-signed SSL certificates require "Verify SSL: off"
