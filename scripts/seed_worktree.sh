#!/usr/bin/env bash
# Give a linked git worktree the gitignored files `just pre_commit` needs:
# terraform validate reads the SSH key and both prod.tfvars. A loop ticket's
# worktree, and the temporary one `loopctl ticket land` stamps, start without
# them. The key is linked so a rotation reaches every worktree. The tfvars are
# copied so a stray write in a worktree cannot reach the primary's.
# Does nothing in the primary checkout, and never replaces an existing file.
set -euo pipefail

primary=$(git worktree list --porcelain | sed -n '1s/^worktree //p')
here=$(git rev-parse --show-toplevel)
[ "$primary" = "$here" ] && exit 0

if [ ! -e "$here/.ssh" ] && [ -e "$primary/.ssh" ]; then
  ln -s "$primary/.ssh" "$here/.ssh"
fi
for f in deployments/infrastructure/vars/prod.tfvars deployments/applications/vars/prod.tfvars; do
  if [ ! -e "$here/$f" ] && [ -e "$primary/$f" ]; then
    cp "$primary/$f" "$here/$f"
  fi
done
