# Home Assistant Configuration Templates

This directory contains template configuration files for Home Assistant that are copied to `data/homeassistant/` during setup.

## Files

- **configuration.yaml** - Main Home Assistant configuration with:
  - Trusted proxies configured for Traefik (Docker and local networks)
  - Zone definitions (Home, Work)
  - Recorder settings (30-day retention)
  - TTS and automation includes

- **secrets.yaml.example** - Template for sensitive values
  - Copy to `data/homeassistant/secrets.yaml` and fill in your values

- **automations.yaml** - Empty file for Home Assistant UI to populate
- **scripts.yaml** - Empty file for Home Assistant UI to populate
- **scenes.yaml** - Empty file for Home Assistant UI to populate

## Setup

These templates are automatically copied during first-time setup:

```bash
make setup  # Includes Home Assistant configuration
```

Or manually:

```bash
make homeassistant-setup  # Copy templates only
```

## Customization

To customize the configuration:

1. Edit templates in this directory (`config/homeassistant-template/`)
2. Run `make homeassistant-setup` to copy updated templates
3. Restart Home Assistant: `docker restart homeassistant`

**Note**: Changes to `data/homeassistant/` are NOT tracked in git (gitignored for runtime data).

## Important: Trusted Proxies

The `configuration.yaml` includes critical trusted proxy configuration:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - ::1
    - 172.16.0.0/12  # Docker bridge networks
    - 192.168.0.0/16  # Local network range
```

**Without this**, accessing Home Assistant via Traefik (`https://home.DOMAIN`) will return **400 Bad Request**.

This configuration is automatically included when using `make setup` or `make homeassistant-setup`.
