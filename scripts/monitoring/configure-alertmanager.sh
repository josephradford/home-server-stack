#!/bin/bash
set -e

# Generate the real Alertmanager config from the tracked template.
# Alertmanager does not substitute ${VAR} placeholders in its own config file,
# so this script does it on the host via envsubst before the container starts.
# Always regenerates — there is no user-editable state in this file to
# preserve (unlike Homepage's dashboard config), so it's safe to re-run on
# every `make setup` / `make start` / `make update` and pick up .env changes.

echo "📧 Configuring Alertmanager"
echo "==========================="

TEMPLATE="monitoring/alertmanager/alertmanager.yml.example"
TARGET="monitoring/alertmanager/alertmanager.yml"

if [ ! -f "$TEMPLATE" ]; then
    echo "❌ Error: Template not found: $TEMPLATE"
    exit 1
fi

if [ ! -f .env ]; then
    echo "❌ Error: .env not found. Run 'make setup' first."
    exit 1
fi

if ! command -v envsubst >/dev/null 2>&1; then
    echo "❌ Error: envsubst not found (part of gettext-base)."
    echo "   Install it with: sudo apt-get install -y gettext-base"
    exit 1
fi

# Only substitute the variables this template actually uses — envsubst with
# no argument would also try to expand unrelated $-signs (e.g. inside Go
# template syntax like {{ .Labels.severity }}, which envsubst leaves alone
# since it only touches $VAR / ${VAR} forms, but naming the vars explicitly
# keeps this from ever surprising us if the template grows).
VARS='${ALERT_SMTP_HOST} ${ALERT_SMTP_PORT} ${ALERT_SMTP_USERNAME} ${ALERT_SMTP_PASSWORD} ${ALERT_EMAIL_FROM} ${ALERT_EMAIL_TO}'

set -a
# shellcheck disable=SC1091
source .env
set +a

envsubst "$VARS" < "$TEMPLATE" > "$TARGET"

echo "✅ Wrote $TARGET"
