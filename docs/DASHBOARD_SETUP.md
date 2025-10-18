# Dashboard Setup Guide

This guide covers setting up the Homepage dashboard with Home Assistant and various integrations.

## Quick Start

1. Copy environment variables:
   ```bash
   cp .env.example .env
   nano .env  # Fill in your values
   ```

2. Get required API keys:
   - Transport NSW: https://opendata.transport.nsw.gov.au/
   - TomTom Traffic: https://developer.tomtom.com/
   - Google Calendar: Get iCal URL from calendar settings

3. Deploy services:
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d
   ```

4. Access services:
   - Homepage: http://SERVER_IP:3100
   - Home Assistant: http://SERVER_IP:8123

## Configuration

See individual tickets for detailed setup:
- Ticket 02: Homepage Dashboard
- Ticket 03: Home Assistant
- Ticket 05: Backend API
- etc.

## Transport Stop IDs

Find your stop IDs:
1. Go to https://transportnsw.info/
2. Search for your station/stop
3. Click on it
4. Copy the ID from the URL (usually 8 digits)

## Traffic Routes

Configure multiple routes with schedules:
- Routes only show during scheduled times
- Use full addresses for accuracy
- Schedule format: "Mon-Fri 07:00-09:00" or "Daily 00:00-23:59"
