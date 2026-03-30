#!/bin/bash
# gandi-ddns-update.sh
# Checks current public IP against Gandi LiveDNS A record and updates if changed.
# Run every 5 minutes via cron (installed by setup-gandi-ddns.sh).

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# Validate required variables
for var in DOMAIN GANDIV5_PERSONAL_ACCESS_TOKEN WIREGUARD_DDNS_SUBDOMAIN; do
    if [ -z "${!var}" ]; then
        log "ERROR: $var not set in $ENV_FILE"
        exit 1
    fi
done

GANDI_API="https://api.gandi.net/v5/livedns"
AUTH_HEADER="Authorization: Bearer $GANDIV5_PERSONAL_ACCESS_TOKEN"

# Fetch current public IP with fallback.
# The `|| true` at the end prevents set -e from exiting on curl failure —
# the regex check below handles the empty/invalid result explicitly.
get_public_ip() {
    local ip
    ip=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null) \
        || ip=$(curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null) \
        || true

    # Validate IPv4 format
    if [[ ! "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
        log "ERROR: Could not fetch a valid public IP (got: '${ip:-empty}')"
        exit 1
    fi
    echo "$ip"
}

CURRENT_IP=$(get_public_ip)
log "Public IP: $CURRENT_IP"

# Fetch current A record from Gandi.
# Response body is written to a temp file; only the HTTP status code is captured
# in the variable. This avoids line-splitting issues with multi-line JSON bodies.
RECORD_URL="$GANDI_API/domains/$DOMAIN/records/$WIREGUARD_DDNS_SUBDOMAIN/A"

HTTP_STATUS=$(curl -s -o /tmp/gandi-ddns-response.json -w "%{http_code}" \
    -H "$AUTH_HEADER" \
    "$RECORD_URL")

case "$HTTP_STATUS" in
    200)
        GANDI_IP=$(jq -r '.rrset_values[0]' /tmp/gandi-ddns-response.json)
        log "Gandi record: $GANDI_IP"
        ;;
    404)
        log "No existing record found — will create"
        GANDI_IP=""
        ;;
    *)
        log "ERROR: Gandi GET returned HTTP $HTTP_STATUS"
        jq . /tmp/gandi-ddns-response.json 2>/dev/null || cat /tmp/gandi-ddns-response.json
        exit 1
        ;;
esac

# Skip update if IP unchanged
if [ "$CURRENT_IP" = "$GANDI_IP" ]; then
    log "IP unchanged ($CURRENT_IP), skipping"
    exit 0
fi

# Update Gandi record
log "Updating $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP"

HTTP_STATUS=$(curl -s -o /tmp/gandi-ddns-response.json -w "%{http_code}" \
    -X PUT \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_values\": [\"$CURRENT_IP\"], \"rrset_ttl\": 300}" \
    "$RECORD_URL")

case "$HTTP_STATUS" in
    201|204)
        log "Updated $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP"
        ;;
    *)
        log "ERROR: Gandi PUT returned HTTP $HTTP_STATUS"
        jq . /tmp/gandi-ddns-response.json 2>/dev/null || cat /tmp/gandi-ddns-response.json
        exit 1
        ;;
esac
