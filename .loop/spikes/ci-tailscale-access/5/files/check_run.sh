#!/usr/bin/env bash
# Read a reach-probe run in JasperHG90/localstack (branch spike/lab-auth-reach) and judge risk 1 (reach) or 2 (join).
# usage: check_run.sh RUN_ID reach|join   exits 0 only when the risk does not hold.
set -u
run=$1 mode=$2 repo=JasperHG90/localstack
log=$(gh run view "$run" --repo "$repo" --log) || exit 3
echo "run $run head $(gh run view "$run" --repo "$repo" --json headSha --jq .headSha)"
gh run view "$run" --repo "$repo" --json jobs --jq '.jobs[] | "\(.name): \(.conclusion); " + ([.steps[] | "\(.name)=\(.conclusion)"] | join(", "))'
echo "localstack OIDC sub setting: $(gh api repos/$repo/actions/oidc/customization/sub)"
for j in with-env no-env; do
  echo "--- $j join output"
  grep "^$j" <<<"$log" | cut -f3- | cut -c30- | grep -E "tailscale up|attempt|exchange|Connected|Successfully|JOINED|logged out" | head -8
done
joined() { grep "^$1" <<<"$log" | grep -q "Run JasperHG90/localstack/.github/actions/join@spike/lab-auth-reach" && gh run view "$run" --repo "$repo" --json jobs --jq ".jobs[] | select(.name==\"$1\") | .steps[] | select(.name==\"Run JasperHG90/localstack/.github/actions/join@spike/lab-auth-reach\") | .conclusion" | grep -qx success; }
if [ "$mode" = join ]; then
  joined with-env && w=yes || w=no; joined no-env && n=yes || n=no
  echo "with-env joined: $w (want yes); no-env joined: $n (want no)"
  [ $w = yes ] && [ $n = no ]
else
  echo "--- reach table"
  grep "^with-env" <<<"$log" | cut -f3- | sed -n '/RESULT TABLE/,/OVERALL=/p' | cut -c30-
  grep -q "OVERALL=PASS" <<<"$log" || { echo "no PASS table: reach checks did not run or failed"; exit 1; }
fi
