#!/usr/bin/env bash
# r2 for seaweedfs-cutover-registry: old images serve unchanged, a new push
# lands on SeaweedFS, and MinIO's registry bucket stays fixed.
set -euo pipefail
D="$(dirname "$0")"
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
export REG_PASS="$(vault kv get -field=password secret/default/registry/auth)"
C=/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.sh
echo "## before switch (07:40 UTC, on MinIO)"; python3 -I -c "import json; d=json.load(open('$D/before.json')); print(len(d), 'tags')"
echo "## after switch: every tag by tag and by digest, layers by HEAD through the presigned redirect"
python3 -I "$D/snapshot.py" "$D/after.json" --verify "$D/before.json"
echo "## counts before push"; $C registry | tail -1
echo "## push a new image, read it back, delete it"
STAMP="$(date -u +%s)" python3 -I "$D/push_check.py" --delete
echo "## counts after push"; $C registry | tail -1
