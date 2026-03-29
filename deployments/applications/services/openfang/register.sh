#!/bin/sh
set -e

# Write memex config — shared by all agents in this container.
cat > /data/memex.env <<CONF
MEMEX_SERVER_URL=${MEMEX_SERVER_URL}
MEMEX_API_KEY=${MEMEX_API_KEY}
MEMEX_S3_ENDPOINT=${MEMEX_S3_ENDPOINT}
MEMEX_S3_BUCKET=${MEMEX_S3_BUCKET}
MEMEX_S3_REGION=${MEMEX_S3_REGION}
MEMEX_S3_ACCESS_KEY=${MEMEX_S3_ACCESS_KEY}
MEMEX_S3_SECRET_KEY=${MEMEX_S3_SECRET_KEY}
CONF

# Skills — install from staging dir to avoid self-clobber
# (skill install copies to $OPENFANG_HOME/skills/ which is /data/skills/)
for d in /tmp/skills/*/; do
    [ -d "$d" ] && openfang skill install "$d" 2>/dev/null || true
done

# Agents — stop existing before re-spawning
for f in /data/workspaces/*/agent.toml; do
    if [ -f "$f" ]; then
        name=$(grep '^name' "$f" | head -1 | sed 's/.*= *"\(.*\)"/\1/')
        agent_id=$(openfang agent list 2>/dev/null | grep "$name" | awk '{print $1}' | head -1)
        [ -n "$agent_id" ] && openfang agent kill "$agent_id" 2>/dev/null || true
        openfang agent spawn "$f" || true
    fi
done

# Hands — install from staging dir
for d in /tmp/hands/*/; do
    [ -d "$d" ] && openfang hand install "$d" 2>/dev/null || true
done

# Workflows
for f in /data/workflows/*.json; do
    [ -f "$f" ] && openfang workflow create "$f" 2>/dev/null || true
done

# Triggers (requires jq)
if [ -f /data/triggers.json ] && command -v jq >/dev/null 2>&1; then
    jq -c '.[]' /data/triggers.json | while read -r t; do
        name=$(echo "$t" | jq -r .agent_name)
        pattern=$(echo "$t" | jq -r .pattern)
        prompt=$(echo "$t" | jq -r .prompt)
        max_fires=$(echo "$t" | jq -r .max_fires)
        agent_id=$(openfang agent list 2>/dev/null | grep "$name" | awk '{print $1}' | head -1)
        [ -n "$agent_id" ] && openfang trigger create "$agent_id" "$pattern" \
            --prompt "$prompt" --max-fires "$max_fires" 2>/dev/null || true
    done
fi
