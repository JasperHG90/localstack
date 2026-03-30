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

# Hands — deactivate running instance, upsert config, activate fresh
for d in /tmp/hands/*/; do
    if [ -d "$d" ] && [ -f "$d/HAND.toml" ]; then
        hand_id=`basename "$d"`
        # Kill running instance if any
        instance_id=`curl -s "http://127.0.0.1:50051/api/hands/active" \
            | jq -r ".[] | select(.hand_id == \"$hand_id\") | .id" 2>/dev/null` || true
        if [ -n "$instance_id" ]; then
            curl -s -X DELETE "http://127.0.0.1:50051/api/hands/instances/$instance_id" > /dev/null 2>&1 || true
            echo "Hand $hand_id: deactivated instance $instance_id"
        fi
        # Upsert config
        toml_content=`cat "$d/HAND.toml"`
        skill_content=""
        [ -f "$d/SKILL.md" ] && skill_content=`cat "$d/SKILL.md"`
        curl -s -X POST "http://127.0.0.1:50051/api/hands/upsert" \
            -H "Content-Type: application/json" \
            -d "$(jq -n --arg t "$toml_content" --arg s "$skill_content" \
                '{toml_content: $t, skill_content: $s}')" > /dev/null 2>&1 || true
        # Activate fresh instance
        openfang hand activate "$hand_id" 2>/dev/null || true
    fi
done

# Push secrets to OpenFang credential vault
if [ -n "$NOMAD_TOKEN" ]; then
    watchdog_id=$(openfang agent list 2>/dev/null \
        | grep "cluster-watchdog-hand" | awk '{print $1}' | head -1)
    if [ -n "$watchdog_id" ]; then
        curl -sf -X PUT "http://127.0.0.1:50051/api/memory/agents/${watchdog_id}/kv/NOMAD_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"value\": \"$NOMAD_TOKEN\"}" 2>/dev/null || true
    fi
fi

# Schedules — upsert from schedules.json
if [ -f /tmp/schedules.json ] && command -v jq >/dev/null 2>&1; then
    # Get existing schedule names to avoid duplicates
    existing=$(curl -s "http://127.0.0.1:50051/api/schedules" \
        | jq -r '.schedules[].name' 2>/dev/null) || true
    jq -c '.[]' /tmp/schedules.json | while read -r s; do
        name=$(echo "$s" | jq -r .name)
        if echo "$existing" | grep -qx "$name"; then
            echo "Schedule $name: already exists, skipping"
        else
            agent_name=$(echo "$s" | jq -r .agent_name)
            agent_id=$(openfang agent list 2>/dev/null | grep "$agent_name" | awk '{print $1}' | head -1)
            if [ -n "$agent_id" ]; then
                cron=$(echo "$s" | jq -r .cron)
                desc=$(echo "$s" | jq -r .description)
                curl -s -X POST "http://127.0.0.1:50051/api/schedules" \
                    -H "Content-Type: application/json" \
                    -d "$(jq -n --arg n "$name" --arg a "$agent_id" --arg c "$cron" --arg d "$desc" \
                        '{name: $n, agent_id: $a, cron: $c, description: $d, enabled: true}')" \
                    > /dev/null 2>&1 || true
                echo "Schedule $name: created for agent $agent_name"
            fi
        fi
    done
fi

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
