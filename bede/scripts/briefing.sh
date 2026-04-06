#!/bin/bash
# Called by supercronic for scheduled briefings.
# Usage: briefing.sh [morning|evening|weekly]
set -e

TYPE="${1:-morning}"

# Pull latest vault state before briefing
if [ -d "/vault/.git" ]; then
    git -C /vault pull --ff-only || true
fi

case "${TYPE}" in
    morning)
        PROMPT="Generate my morning briefing. Check my calendar for today's events, summarise any unread emails, and note anything I should be aware of today."
        ;;
    evening)
        PROMPT="Generate my evening briefing. Summarise today's calendar events and help me prepare for tomorrow's schedule."
        ;;
    weekly)
        PROMPT="Generate my weekly review. Summarise the past week from my calendar and help me prepare for the week ahead."
        ;;
    *)
        PROMPT="${*}"
        ;;
esac

MCP_ARGS=()
if [ -n "${MCP_CONFIG_PATH}" ] && [ -f "${MCP_CONFIG_PATH}" ]; then
    MCP_ARGS=(--mcp-config "${MCP_CONFIG_PATH}")
fi

OUTPUT=$(claude -p "${PROMPT}" --dangerously-skip-permissions --output-format json "${MCP_ARGS[@]}" < /dev/null 2>&1)

# Extract result from JSONL output
RESULT=$(echo "${OUTPUT}" | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        if obj.get('type') == 'result':
            print(obj.get('result', '').strip())
    except json.JSONDecodeError:
        pass
" 2>/dev/null)

if [ -z "${RESULT}" ]; then
    exit 0
fi

# Send to Telegram (outbound only — no polling needed for scheduled messages)
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${ALLOWED_USER_ID}" \
    --data-urlencode "text=${RESULT}" \
    -d "parse_mode=Markdown" \
    > /dev/null
