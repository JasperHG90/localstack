#!/usr/bin/env bash
# r3 for seaweedfs-cutover-openviking: readiness, tree and hashes against the
# step 0 baseline, and a new write landing on SeaweedFS while MinIO stays fixed.
set -euo pipefail
D="$(dirname "$0")"
cd /home/vscode/workspace
eval "$(uv run localstack env)" 2>/dev/null
export OV_TOKEN="$(vault read -field=token identity/oidc/token/openviking)"
echo "## readiness"; curl -s -m 20 https://openviking-api.lab.orangecluster.nl/ready; echo
echo "## before (step 0 baseline, 06:40 UTC)"; head -1 "$D/before/summary.txt"
mkdir -p "$D/after"
echo "## after"; python3 -I "$D/snapshot.py" "$D/after" "$D/before/sample.txt" | head -1
echo "## listing diff (empty means identical)"; diff "$D/before/listing.txt" "$D/after/listing.txt" && echo "(identical)"
echo "## hash diff (empty means identical)"; diff "$D/before/hashes.txt" "$D/after/hashes.txt" && echo "(identical)"
echo "## new write"
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.sh openviking | tail -1
python3 -I "$D/write_check.py" make
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.sh openviking | tail -1
python3 -I "$D/write_check.py" remove
