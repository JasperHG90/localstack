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

# Write nomad config — used by the nomad skill for API access.
cat > /data/nomad.env <<CONF
NOMAD_ADDR=${NOMAD_ADDR:-http://192.168.2.30:4646}
NOMAD_TOKEN=${NOMAD_TOKEN}
CONSUL_ADDR=${CONSUL_ADDR:-http://192.168.2.30:8500}
CONF

# Skills — install from staging dir to avoid self-clobber
# (skill install copies to $OPENFANG_HOME/skills/ which is /data/skills/)
for d in /tmp/skills/*/; do
    [ -d "$d" ] && openfang skill install "$d" 2>/dev/null || true
done

# Agents — kill ALL existing, then spawn only what's in /data/workspaces
for agent_id in $(openfang agent list 2>/dev/null | awk 'NR>1 {print $1}'); do
    [ -n "$agent_id" ] && openfang agent kill "$agent_id" 2>/dev/null || true
done
for f in /data/workspaces/*/agent.toml; do
    [ -f "$f" ] && openfang agent spawn "$f" || true
done

# Hands — deactivate running instance, upsert config, activate fresh
for d in /tmp/hands/*/; do
    if [ -d "$d" ] && [ -f "$d/HAND.toml" ]; then
        hand_id=`basename "$d"`
        # Kill running instance if any
        instance_id=`curl -s "http://127.0.0.1:50051/api/hands/active" \
            | jq -r ".instances[] | select(.hand_id == \"$hand_id\") | .instance_id" 2>/dev/null` || true
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
        echo "Hand $hand_id: activated"
    fi
done

# Wait for hand agents to register
attempts=0
watchdog_id=""
while [ $attempts -lt 10 ]; do
    watchdog_id=$(openfang agent list 2>/dev/null | grep "cluster-watchdog-hand" | awk '{print $1}' | head -1)
    [ -n "$watchdog_id" ] && break
    attempts=$((attempts + 1))
    sleep 1
done

if [ -n "$watchdog_id" ]; then
    echo "Watchdog agent registered: $watchdog_id"
else
    echo "WARNING: cluster-watchdog-hand not found after 10s"
fi

# Push secrets to OpenFang credential vault
if [ -n "$NOMAD_TOKEN" ] && [ -n "$watchdog_id" ]; then
    curl -sf -X PUT "http://127.0.0.1:50051/api/memory/agents/${watchdog_id}/kv/NOMAD_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"value\": \"$NOMAD_TOKEN\"}" 2>/dev/null || true
    echo "NOMAD_TOKEN pushed to vault for $watchdog_id"
elif [ -z "$NOMAD_TOKEN" ]; then
    echo "WARNING: NOMAD_TOKEN not set, skipping vault push"
fi

# Cron jobs — sync from schedules.json (delete + recreate to pick up new agent IDs)
if [ -f /tmp/schedules.json ] && command -v jq >/dev/null 2>&1; then
    # Delete existing cron jobs that we manage
    openfang cron list 2>/dev/null | jq -c '.jobs[]' 2>/dev/null \
        | while read -r job; do
            jid=$(echo "$job" | jq -r .id)
            jname=$(echo "$job" | jq -r .name)
            if jq -e --arg n "$jname" '.[] | select(.name == $n)' /tmp/schedules.json >/dev/null 2>&1; then
                openfang cron delete "$jid" 2>/dev/null || true
                echo "Cron $jname: deleted stale entry"
            fi
        done
    # Recreate with current agent IDs
    jq -c '.[]' /tmp/schedules.json | while read -r s; do
        name=$(echo "$s" | jq -r .name)
        agent_name=$(echo "$s" | jq -r .agent_name)
        agent_id=$(openfang agent list 2>/dev/null | grep "$agent_name" | awk '{print $1}' | head -1)
        if [ -n "$agent_id" ]; then
            cron=$(echo "$s" | jq -r .cron)
            prompt=$(echo "$s" | jq -r '.prompt // "Run your default task"')
            openfang cron create "$agent_id" "$cron" "$prompt" --name "$name" 2>&1 || true
        else
            echo "WARNING: Cron $name: agent '$agent_name' not found, skipping"
        fi
    done
fi

# Workflows
for f in /data/workflows/*.json; do
    [ -f "$f" ] && openfang workflow create "$f" 2>/dev/null || true
done
