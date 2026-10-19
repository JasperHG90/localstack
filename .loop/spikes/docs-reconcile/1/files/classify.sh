#!/usr/bin/env bash
# docs-reconcile risk 3: how many pages under docs/{how-to,reference,explanation}
# are mainly repo-worker content (plan, audit, build history, handoff,
# decision record) and so belong in .okf/?
#
# Part 1 is mechanical: per-page counts of build-history markers and of
# ticket-code tokens (F9, G2, M1 ...). Part 2 is the reader's verdict on every
# page part 1 flags, recorded below with the line that is the evidence; the
# script fails if any evidence line is no longer in the page.
# Exit 0 when at most 3 pages ("a handful") are verdict MOVE, else 1.
set -u
markers='\.loop/|\bticket\b|\bspike\b|\bwe (decided|chose|considered)\b|\bthe plan\b|\bbuild plan\b|\bhandoff\b|\bdecision record\b|\.okf/(decisions|proposals|prototypes|practices)|\b20[0-9]{2}-[0-9]{2}-[0-9]{2}\b|\bproposal\b|\bused to\b|\blanded\b|\bas of\b|\bsince [A-Z][0-9]|\bfollow-up\b|\btime of writing\b'
# Standalone letter+digit tokens, minus ones that are not ticket ids here.
codes='\b[A-Z][0-9]{1,2}[a-z]?\b'
notcodes='^(S3|H1|H2|L4|L7|E2)$'

files=$(find docs/how-to docs/reference docs/explanation -name '*.md' ! -name README.md | sort)
total=$(echo "$files" | wc -l)
echo "pages: $total"
echo "--- markers  codes  words  page (only pages with any hit) ---"
for f in $files; do
  m=$(grep -ciE "$markers" "$f")
  c=$(grep -oE "$codes" "$f" | grep -vcE "$notcodes")
  w=$(wc -w < "$f")
  [ $((m + c)) -gt 0 ] && printf '%7d %6d %6d  %s\n' "$m" "$c" "$w" "$f"
done | sort -k1,1nr -k2,2nr

# verdict|page|fixed-string evidence line
# MOVE    = mainly repo-worker content, belongs in .okf/
# RESIDUE = user page with build-history lines to edit out in place
# KEEP    = marker hit is user content (a log string, a dated measurement)
verdicts='RESIDUE|docs/how-to/verify-memex-oidc.md|G5 — the scaffold edit landed where it should, and only there.
RESIDUE|docs/how-to/verify-memex-oidc.md|`MEMEX_API_KEY` in `hermes.hcl` at both sites. Removal is a follow-up.
RESIDUE|docs/explanation/workload-identity.md|M1 landed this. A Nomad job can now read its bucket with no static S3 key: it
RESIDUE|docs/explanation/workload-identity.md|| `minio-poc2` | MinIO STS, `POC2` target | M1, replace in the human ticket |
RESIDUE|docs/explanation/workload-identity.md|and is applied by Ansible. As of F9 (2026-07-30) it is three `path` blocks:
RESIDUE|docs/reference/vault-human-auth.md|What G2 changed is the route: reaching it used to require someone handing you a
RESIDUE|docs/reference/cli-login.md|Removing the injected token entirely is F8'"'"'s job, not this CLI'"'"'s.
RESIDUE|docs/reference/cli-login.md|The `userpass` backend and the `operator` entity come from F2. The policy that
RESIDUE|docs/how-to/add-a-vault-oidc-client.md|`vault_identity_group`, because it reuses F11'"'"'s existing `developer` group
RESIDUE|docs/how-to/revoke-a-lost-or-stolen-session.md|**`localstack logout` ships with `D2` and is the way to do this.** It revokes
RESIDUE|docs/explanation/cluster-roles.md|If you want a real boundary, that is a different design and a different ticket.
RESIDUE|docs/how-to/narrow-the-monitoring-firewall-rules.md|the time of writing (2026-07-26) that includes the dnsmasq removal, which is
RESIDUE|docs/reference/dash.md|`dash` sits entirely behind oauth2-proxy (L1), gated on a completed Vault
RESIDUE|docs/reference/tls-certificates.md|staging until the idempotency gate was cleared on 2026-07-26: the job ran
RESIDUE|docs/reference/cluster-roles.md|Whether a level is per-app or per-resource is the consumer ticket'"'"'s call.
KEEP|docs/reference/dns.md|`.okf/proposals/postgres-nats-cdc-bridge.md` advertise
KEEP|docs/explanation/openviking-identity.md|provisioner that used to POST to the Admin API is gone rather than replaced.
KEEP|docs/reference/openviking.md|Two it used to assert are gone. Under `oidc` the plugin never consults'

echo "--- verdicts ---"
bad=0
while IFS='|' read -r v f line; do
  n=$(grep -nF -- "$line" "$f" | cut -d: -f1 | head -1)
  if [ -z "$n" ]; then echo "STALE evidence: $f: $line"; bad=1; continue; fi
  echo "$v $f:$n  $line"
done <<< "$verdicts"
[ $bad -eq 0 ] || { echo "evidence no longer matches"; exit 2; }

move=$(echo "$verdicts" | grep -c '^MOVE|' || true)
residue=$(echo "$verdicts" | grep '^RESIDUE|' | cut -d'|' -f2 | sort -u | wc -l)
echo "MOVE pages: $move of $total"
echo "RESIDUE pages (edit in place): $residue"
[ "$move" -le 3 ]
