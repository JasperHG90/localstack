#!/usr/bin/env bash
# r2 for minio-volume-destroy: volume, host directory and Vault keys gone, plan clean.
set -uo pipefail
cd /home/vscode/workspace.worktrees/minio-volume-destroy
eval "$(uv run localstack env)" 2>/dev/null
echo "## nomad host volumes named minio_data"
nomad volume status -type host 2>&1 | grep -c minio_data
echo "## host directory on orangepi4a"
ssh -i /home/vscode/workspace/.ssh/id_rsa -o BatchMode=yes -o ConnectTimeout=10 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR orangepi@192.168.2.29 \
  'sudo test -e /opt/nomad/data/host_volumes/cb07eebf-a72a-28f7-a223-a106d1ccbe2b && echo present || echo gone'
echo "## vault: MinIO key paths"
printf 'default/minio: '; vault kv list secret/default/minio 2>&1 | head -1
for j in loki tempo registry openviking memex mlflow; do
  printf 'default/%s/minio: ' "$j"; vault kv metadata get "secret/default/$j/minio" >/dev/null 2>&1 && echo present || echo gone
done
echo "## infrastructure plan"
terraform -chdir=deployments/infrastructure plan -var-file=./vars/prod.tfvars -input=false -no-color 2>&1 \
  | grep -E '^Plan:|No changes|^  # [a-z]' | sed 's/^  # //' | sed -E 's/\["[a-z_0-9]+"\] must be replaced/[...] must be replaced/' | sort | uniq -c
