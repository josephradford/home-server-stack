# Home Assistant Setup Guide

## Overview

Home Assistant provides location tracking and home automation capabilities for the home server stack. It enables:
- Family location tracking via iOS/Android Companion App
- iCloud device tracking (AirPods, iPads, etc.)
- Home automation and scenes
- Integration with other services via automations

## Initial Setup

### 1. Setup Configuration (Included in `make setup`)

Home Assistant configuration is automatically set up during first-time deployment:

```bash
make setup  # Includes Home Assistant configuration setup
```

Or if you need to reset/update the configuration:

```bash
make homeassistant-setup  # Copies templates from config/homeassistant-template/
```

This automatically:
- Creates `data/homeassistant/` directory
- Copies `configuration.yaml` with correct trusted proxies for Traefik
- Copies `secrets.yaml.example` template
- Creates empty automation files

### 2. Start Home Assistant

```bash
make start
```

Home Assistant will start along with other services. First startup takes 60-120 seconds as it initializes the database and configuration.

### 3. Monitor Startup

Watch the logs to ensure successful startup:

```bash
docker logs -f homeassistant
```

Wait for the message: **"Home Assistant is running"** or **"Home Assistant initialized"**

### 4. Access Home Assistant

Open your browser and navigate to:
- Direct access: `http://SERVER_IP:8123`
- Via Traefik (requires VPN or local network): `https://home.DOMAIN`

### 5. Complete Onboarding Wizard

On first access, you'll be guided through the onboarding wizard:

1. **Create admin account**
   - Choose a username (e.g., `admin`)
   - Set a strong password
   - Note: This is separate from other service passwords

2. **Set location**
   - Name your home (e.g., "Home")
   - Set location to your address or nearby landmark
   - Example: North Parramatta, NSW
   - This enables location-based automations and weather

3. **Set timezone**
   - Should auto-detect based on location
   - Verify it matches your `TIMEZONE` env var

4. **Skip device discovery**
   - You can skip automatic device discovery for now
   - Devices will be added manually later

5. **Analytics**
   - Choose whether to share analytics with Home Assistant
   - This is optional and up to your preference

## Generate API Token for Homepage Dashboard

The Homepage dashboard needs a token to display Home Assistant information.

### Steps:

1. Click on your **profile** (bottom left, shows your username)

2. Scroll down to the **"Long-Lived Access Tokens"** section

3. Click **"Create Token"**

4. Give it a descriptive name: `Homepage Dashboard`

5. **Copy the token immediately** - it won't be shown again!

6. Add the token to your `.env` file:
   ```bash
   HOMEASSISTANT_TOKEN=your_token_here
   ```

7. Restart Homepage to apply the change:
   ```bash
   make restart
   ```

8. Verify the widget appears on the Homepage dashboard at `https://homepage.DOMAIN`

## Initial Configuration

### Copy Secrets Template

If you plan to use custom zones (like work location):

```bash
cd data/homeassistant
cp secrets.yaml.example secrets.yaml
```

Edit `secrets.yaml` with your actual coordinates:
```yaml
work_latitude: -33.8688
work_longitude: 151.2093
```

### Edit Zones (Optional)

The default configuration includes two zones:
- **Home**: Set to approximate Sydney coordinates (-33.8000, 151.0000)
- **Work**: Uses coordinates from `secrets.yaml`

To customize, edit `data/homeassistant/configuration.yaml`:

```yaml
zone:
  - name: Home
    latitude: -33.8000  # Your home latitude
    longitude: 151.0000  # Your home longitude
    radius: 100
    icon: mdi:home

  - name: Work
    latitude: !secret work_latitude
    longitude: !secret work_longitude
    radius: 200
    icon: mdi:office-building
```

After editing, restart Home Assistant:
```bash
docker restart homeassistant
```

## iOS Companion App Setup

Location tracking requires the Home Assistant Companion App on iOS devices.

**See Ticket 09 for detailed iOS app configuration** including:
- App installation and setup
- Location tracking permissions
- Device tracking (AirPods, iPads, etc.)
- Sensor configuration
- Apple Health fitness data export

Quick start:
1. Install "Home Assistant" from the App Store
2. Open the app and scan the QR code from Settings → Companion App
3. Grant location permissions (Always Allow for best tracking)
4. Person entities will automatically appear in Home Assistant

## Accessing Home Assistant

### Local Network Access
- Direct: `http://192.168.1.100:8123` (replace with your SERVER_IP)
- Via Traefik: `https://home.example.com` (replace with your DOMAIN)

### Remote Access
Remote access requires VPN connection (WireGuard). Home Assistant is **not exposed publicly** for security.

1. Connect to WireGuard VPN
2. Access via domain: `https://home.DOMAIN`
3. Or direct IP: `http://SERVER_IP:8123`

## Configuration Files

### Configuration Structure

```
data/homeassistant/
├── configuration.yaml      # Main configuration
├── secrets.yaml           # Sensitive values (gitignored)
├── secrets.yaml.example   # Template for secrets
├── automations.yaml       # Automations (managed via UI)
├── scripts.yaml          # Scripts (managed via UI)
└── scenes.yaml           # Scenes (managed via UI)
```

### Key Configuration Settings

**HTTP Configuration** (in `configuration.yaml`):
- Trusts Traefik proxy headers for correct client IPs
- **CRITICAL**: Must trust Docker network (172.16.0.0/12) and local network (192.168.0.0/16)
- Without this, accessing via domain (Traefik) will return 400 Bad Request
- Required for proper logging and security

**Recorder** (in `configuration.yaml`):
- Purges data older than 30 days
- Keeps database size manageable
- Adjust `purge_keep_days` if you need longer history

**Zones** (in `configuration.yaml`):
- Defines geographic zones for location-based automations
- Triggers when person enters/leaves zone

## Troubleshooting

### 400 Bad Request when accessing via domain (https://home.DOMAIN)

**Symptom**: Direct access (`http://SERVER_IP:8123`) works, but domain access returns 400 Bad Request.

**Cause**: Home Assistant isn't trusting the Traefik reverse proxy network.

**This should NOT happen** if you used `make setup` or `make homeassistant-setup`, as the configuration template includes the correct trusted proxies.

**If it still happens**:

1. Verify the configuration was copied correctly:
   ```bash
   grep -A 5 "trusted_proxies" data/homeassistant/configuration.yaml
   ```

   Should show:
   ```yaml
   trusted_proxies:
     - 127.0.0.1
     - ::1
     - 172.16.0.0/12  # Docker bridge networks
     - 192.168.0.0/16  # Local network range
   ```

2. If the configuration is missing these proxies, re-run setup:
   ```bash
   make homeassistant-setup
   docker restart homeassistant
   ```

3. Verify fix:
   ```bash
   curl -I https://home.DOMAIN  # Should return 200 OK
   ```

### Cannot access Home Assistant

**Check container status:**
```bash
docker ps | grep homeassistant
```

Should show: `Up X minutes (healthy)`

**Check logs:**
```bash
docker logs homeassistant
```

Look for errors or warnings.

**Verify port is open:**
```bash
curl http://SERVER_IP:8123
```

Should return HTML (Home Assistant login page).

### Homepage widget not showing

1. **Verify token is set:**
   ```bash
   grep HOMEASSISTANT_TOKEN .env
   ```

2. **Check Homepage logs:**
   ```bash
   docker logs homepage
   ```

3. **Verify token is valid:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://SERVER_IP:8123/api/
   ```

   Should return: `{"message": "API running."}`

4. **Regenerate token if needed:**
   - Go to Profile → Long-Lived Access Tokens
   - Delete old token
   - Create new token
   - Update `.env` and restart Homepage

### Home Assistant won't start

**Check disk space:**
```bash
df -h
```

Home Assistant database can grow large over time.

**Check permissions:**
```bash
ls -la data/homeassistant/
```

Directory should be writable by the container user.

**Reset configuration (nuclear option):**
```bash
docker stop homeassistant
mv data/homeassistant data/homeassistant.backup
mkdir data/homeassistant
# Copy back configuration files but not the database
cp data/homeassistant.backup/configuration.yaml data/homeassistant/
cp data/homeassistant.backup/secrets.yaml data/homeassistant/
touch data/homeassistant/{automations,scripts,scenes}.yaml
docker start homeassistant
```

### Network mode issues

The stack uses **bridge networking** (not host mode) for better integration with Traefik and other services.

**Implications:**
- ✅ Works seamlessly with Traefik reverse proxy
- ✅ Proper SSL termination
- ✅ Consistent with other stack services
- ⚠️ Some device discovery features may be limited (mDNS, SSDP)
- ⚠️ Manual device configuration may be needed for some integrations

**If you need host mode for specific integrations:**
1. Edit `docker-compose.yml`
2. Change `networks: - homeserver` to `network_mode: host`
3. Remove port mappings (not needed in host mode)
4. Restart: `docker restart homeassistant`

Note: This will require accessing via IP only, not domain name through Traefik.

### Database growing too large

**Check database size:**
```bash
du -sh data/homeassistant/home-assistant_v2.db
```

**Reduce retention period:**

Edit `data/homeassistant/configuration.yaml`:
```yaml
recorder:
  purge_keep_days: 7  # Reduce from 30 to 7 days
  commit_interval: 30
```

Restart Home Assistant:
```bash
docker restart homeassistant
```

**Exclude entities from recorder:**

Add to `configuration.yaml`:
```yaml
recorder:
  purge_keep_days: 30
  commit_interval: 30
  exclude:
    entities:
      - sensor.time
      - sensor.date
    entity_globs:
      - sensor.weather_*
```

### iOS App not connecting

1. **Verify Home Assistant is accessible:**
   ```bash
   curl http://SERVER_IP:8123
   ```

2. **Check firewall allows port 8123:**
   ```bash
   sudo ufw status | grep 8123
   ```

   If not open (and you're on local network):
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 8123
   ```

3. **Try manual connection:**
   - Open app → Add Server
   - Enter: `http://SERVER_IP:8123`
   - Enter username and password

4. **Check app permissions:**
   - Settings → Privacy & Security → Location Services
   - Find "Home Assistant"
   - Set to "Always" for best tracking

## Next Steps

1. **Install iOS Companion App** - See Ticket 09 for detailed setup
2. **Configure Person Tracking** - After iOS app setup, person entities will appear
3. **Set up Automations** - Use the UI to create location-based automations
4. **Integrate with n8n** - Create workflows triggered by Home Assistant events
5. **Add Device Tracking** - Track AirPods, iPads, and other devices (Ticket 09)

## Reference

- [Home Assistant Documentation](https://www.home-assistant.io/docs/)
- [Companion App Documentation](https://companion.home-assistant.io/)
- [Zones Documentation](https://www.home-assistant.io/integrations/zone/)
- [Recorder Documentation](https://www.home-assistant.io/integrations/recorder/)
