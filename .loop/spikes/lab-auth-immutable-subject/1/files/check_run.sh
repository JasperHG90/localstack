#!/usr/bin/env bash
# Judge a reach-probe run in JasperHG90/lab-auth-probe for lab-auth-immutable-subject risk 1.
# usage: check_run.sh RUN_ID   exits 0 only when the with-env job saw an immutable sub,
# picked the new credential and joined, and the no-env job did not join.
set -u
run=$1 repo=JasperHG90/lab-auth-probe
log=$(gh run view "$run" --repo "$repo" --log) || exit 3
echo "run $run head $(gh run view "$run" --repo "$repo" --json headSha --jq .headSha)"
gh run view "$run" --repo "$repo" --json jobs --jq '.jobs[] | "\(.name): \(.conclusion); " + ([.steps[] | "\(.name)=\(.conclusion)"] | join(", "))'
for j in with-env no-env; do
  echo "--- $j credential pick and join output"
  grep "^$j" <<<"$log" | cut -f3- | cut -c30- | grep -E "^(SUB|SUB_FORMAT|CLIENT)=|tailscale up|attempt|exchange|Unauthorized|Connected|Successfully|JOINED" | grep -v '^+' | head -10
done
joined() { gh run view "$run" --repo "$repo" --json jobs --jq ".jobs[] | select(.name==\"$1\") | .steps[] | select(.name==\"Run ./.github/actions/join\") | .conclusion" | grep -qx success; }
joined with-env && w=yes || w=no; joined no-env && n=yes || n=no
grep "^with-env" <<<"$log" | grep -q "SUB_FORMAT=immutable" && f=immutable || f=other
echo "with-env sub format: $f (want immutable); with-env joined: $w (want yes); no-env joined: $n (want no)"
echo "--- reach table (informational)"
grep "^with-env" <<<"$log" | cut -f3- | sed -n '/RESULT TABLE/,/OVERALL=/p' | cut -c30- | grep -v '^+\|echo\|printf'
[ $f = immutable ] && [ $w = yes ] && [ $n = no ]
