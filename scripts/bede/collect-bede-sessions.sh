#!/bin/bash
# collect-bede-sessions.sh
#
# Collects Bede's Claude Code session data from the persisted projects volume,
# generates AI summaries, and POSTs the result to data-ingest.
#
# Designed to run nightly via cron on the home server:
#   0 2 * * *  /path/to/home-server-stack/scripts/bede/collect-bede-sessions.sh >> /var/log/collect-bede-sessions.log 2>&1
#
# Can also be run manually:
#   make collect-bede-sessions                    # today (or yesterday if before noon)
#   make collect-bede-sessions DATE=2026-04-15    # specific date

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment
if [[ -f "$REPO_DIR/.env" ]]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

# Paths
PROJECTS_DIR="$REPO_DIR/data/bede/claude-projects"
CLAUDE_BIN="${HOME}/.claude/local/claude"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
warn() { echo "[$(date '+%H:%M:%S')] WARNING: $*" >&2; }

# Date calculation — same midday-boundary rule as daily-raw-collect.sh:
# before noon = yesterday, noon onwards = today
if [[ -n "${DATE:-}" ]]; then
    TARGET_DATE="$DATE"
else
    CURRENT_HOUR=$(date '+%H')
    if (( 10#$CURRENT_HOUR < 12 )); then
        TARGET_DATE=$(date -d "yesterday" '+%Y-%m-%d' 2>/dev/null || date -v-1d '+%Y-%m-%d')
    else
        TARGET_DATE=$(date '+%Y-%m-%d')
    fi
fi

log "Collecting Bede sessions for $TARGET_DATE"

if [[ ! -d "$PROJECTS_DIR" ]]; then
    warn "Projects directory not found: $PROJECTS_DIR"
    warn "Has Bede been started with the claude-projects volume mount?"
    exit 1
fi

if [[ ! -x "$CLAUDE_BIN" ]]; then
    warn "Claude binary not found at $CLAUDE_BIN — summaries will use fallback"
fi

# Generate the markdown report
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

if ! python3 "$SCRIPT_DIR/collect-bede-sessions.py" "$PROJECTS_DIR" "$TARGET_DATE" "$CLAUDE_BIN" > "$TMP" 2>/dev/null; then
    warn "collect-bede-sessions.py failed"
    exit 1
fi

CONTENT=$(cat "$TMP")
LINES=$(wc -l < "$TMP" | tr -d ' ')
log "Generated $LINES lines"

if [[ "$CONTENT" == *"_(no sessions)_"* ]]; then
    log "No Bede sessions found for $TARGET_DATE — skipping POST"
    exit 0
fi

# POST to data-ingest
INGEST_URL="https://data.${DOMAIN}/ingest/vault"
TOKEN="${INGEST_WRITE_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
    warn "INGEST_WRITE_TOKEN not set — cannot POST"
    exit 1
fi

PAYLOAD=$(jq -n \
    --arg date "$TARGET_DATE" \
    --arg bede "$CONTENT" \
    '{
        date: $date,
        files: {
            "bede-sessions.md": $bede
        }
    }')

HTTP_CODE=$(curl -sk -o /tmp/collect-bede-sessions.resp \
    -w '%{http_code}' \
    -X POST "$INGEST_URL" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    --connect-timeout 10 \
    --max-time 30)

if [[ "$HTTP_CODE" == "200" ]]; then
    ROWS=$(jq -r '.rows_inserted // "?"' /tmp/collect-bede-sessions.resp 2>/dev/null)
    log "POST succeeded: $ROWS row(s) inserted"
else
    warn "POST failed (HTTP $HTTP_CODE) — $(cat /tmp/collect-bede-sessions.resp 2>/dev/null)"
    exit 1
fi

log "Done."
