#!/bin/sh
# Hermes cron job registration script.
#
# Cron management in Hermes uses slash commands (/cron add) within a session,
# NOT CLI subcommands. This script sends cron registration commands via the
# gateway's OpenAI-compatible chat API on port 8642.
#
# Run AFTER the gateway is healthy:
#   curl -sf http://127.0.0.1:8642/health && sh register-cron.sh
#
# Cron jobs persist in $HERMES_HOME/cron/ — only run once on initial deploy
# or when schedules change.

set -e

GATEWAY="http://127.0.0.1:8642"
: "${TELEGRAM_HOME_CHANNEL:?TELEGRAM_HOME_CHANNEL must be set}"
: "${DIGEST_EMAIL:?DIGEST_EMAIL must be set}"
TELEGRAM="telegram:${TELEGRAM_HOME_CHANNEL}"

send_cron() {
  local cmd="$1"
  echo "Registering: $cmd"
  curl -sf -X POST "$GATEWAY/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"default\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$cmd\"}],
      \"max_tokens\": 200
    }" > /dev/null 2>&1 || echo "  WARN: failed"
  sleep 2
}

echo "hermes: registering cron jobs via gateway API..."

send_cron '/cron add "0 8 * * *" "Scrape all target engineering blogs for new articles published in the last 3 days. Save new articles verbatim to OpenViking, one resource per article." --skill blog-scraper --name "daily-blog-scrape"'

send_cron '/cron add "0 8 * * 1" "Send a weekly digest email of what was captured to ${DIGEST_EMAIL}. Search OpenViking for the past week of material and group it by theme. One line per item. Subject: Weekly Digest." --deliver email:${DIGEST_EMAIL} --name "weekly-digest"'

send_cron '/cron add "0 10 * * *" "Search OpenViking for recent insights (last 48 hours) and open GitHub issues or PRs for applicable improvements to target repositories." --skill insight-linker --name "insight-linker-daily"'

send_cron '/cron add "0 0 * * *" "Run the daily-reflect skill for today. Persistence is mandatory." --skill daily-reflect --deliver '"$TELEGRAM"' --name "Daily reflect"'

echo "hermes: cron registration complete"
echo ""
echo "Verify with: send '/cron list' via the dashboard or Telegram"
