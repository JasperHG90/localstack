---
verdict: pass
tree: eb35aca72cef9675632137d49838c5d3d5b30a76
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY, for the fourth cycle running. This
briefing again carried a tree fingerprint but no 64-hex scope digest, and named
no verdict_binding_inputs. The floor is not mine to choose and I must never
write a digest I computed for a set I chose, so bound_paths / scope / citations
are omitted and this verdict falls back to the whole-tree binding, which is
stricter. Every anchor cited below carries its verbatim line inline instead.

For the record, the artifact reviewed was the working tree against c5cba06.
Modified: .pre-commit-config.yaml, deployments/applications/secrets.tf,
deployments/applications/services.tf, deployments/applications/storage.tf,
deployments/infrastructure/oidc.tf, deployments/infrastructure/secrets.tf,
deployments/infrastructure/services.tf,
deployments/infrastructure/services/haproxy.hcl,
docs/haproxy_reverse_proxy.md, docs/vault-human-auth.md,
docs/workload-identity.md, scripts/check_oauth2_proxy_guard.py.
Added: deployments/applications/services/openviking.hcl,
deployments/applications/services/openviking/Dockerfile.openviking,
deployments/applications/services/openviking/README.md,
deployments/applications/services/openviking/justfile,
deployments/infrastructure/services/oauth2-proxy-openviking.hcl,
docs/openviking.md, scripts/check_openviking_config.py.
-->

# Documentation pass, cycle 4: PASS

Every documented surface this change touches is updated in step. Both required
findings from cycle 3 are fixed, and I re-measured rather than took the fix on
report. Nothing must change before commit. Two advisories stay advisory.

The cycle-4 delta is exactly four files, confirmed by mtime rather than by the
briefing's word: `docs/openviking.md`, `docs/vault-human-auth.md`,
`deployments/infrastructure/services.tf`, and
`deployments/applications/services/openviking/Dockerfile.openviking` all carry
20:01:01; every other changed file is 19:42 or earlier. No unreported edit rode
along.

## DOC-19 (was high, required) — CLOSED, measured

The foreign-audience check is now one single-quoted remote command:

    docs/openviking.md:109 = $ ssh radxa@192.168.2.50 'curl -s -o /dev/null -w "%{http_code}" \
    docs/openviking.md:110 =     -H "Authorization: Bearer <token minted for another client>" \
    docs/openviking.md:111 =     http://127.0.0.1:1933/api/v1/collections'   # expect 401

I re-ran the reproduction against bash 5.2.21, curl 8.5.0, and a local
header-echo server, driving it through a stand-in that reproduces ssh's argv
space-join and hands the joined string to `/bin/bash -c`. Four things checked
out:

1. **The local shell now yields ONE argv element.** `printf '%q'` on the ssh
   argv shows a single element holding the whole remote command, with the
   backslash-newlines preserved as literal bytes (`od -c` shows `\` `\n` at
   both continuation points). The old unquoted form yielded nine.
2. **The remote shell folds the continuations and curl gets the header
   whole.** The remote receives `argv[5]=-H` and
   `argv[6]='Authorization: Bearer TOKENFOROTHERCLIENT'` as one entry. The
   header-echo server logged `AUTH='Bearer TOKENFOROTHERCLIENT'` and the
   terminal printed a bare `401`, which is what `# expect 401` promises. The
   command genuinely tests what it claims.
3. **The comment's account of the failure mode is accurate.** Running the old
   unquoted form through the same rig gives `argv[6]='Authorization:'`,
   `argv[7]='Bearer'`, `argv[8]='TOKEN'`; the server logged `AUTH=None` and the
   terminal printed `000000401`. So both claims hold verbatim:

    docs/openviking.md:105 = # The remote command is ONE quoted string: ssh joins its argv with spaces and
    docs/openviking.md:106 = # hands the result to a shell, so unquoted here the remote curl would see
    docs/openviking.md:107 = # `-H Authorization:`, which is how curl REMOVES a header, and would report
    docs/openviking.md:108 = # the plain unauthenticated 401 while sending no token at all

4. **Two details the fix could have gotten wrong, and did not.** The literal
   placeholder `<token minted for another client>` parses as one argv entry:
   the angle brackets sit inside the *remote* double quotes, so no redirection
   fires. And the trailing `# expect 401` sits outside the single quotes, so it
   stays a local comment and is never sent to the remote. My end-to-end run
   confirmed the remote received the curl command alone.

## DOC-9 (was medium, required) — CLOSED

    docs/vault-human-auth.md:42 = | `oidc.tf` | The OIDC signing key, the shared `groups` and `email` scopes, the provider, one throwaway smoke-test client, and the consumer clients added since (nomad, memex, oauth2-proxy, grafana, openviking) |

Ground truth re-measured this cycle, not carried from cycle 3: `oidc.tf` holds
six `vault_identity_oidc_client` resources (`smoke`:160, `nomad`:222,
`memex`:384, `oauth2_proxy`:425, `openviking`:462, `grafana`:500). The row
describes smoke separately and then names the five non-smoke consumers. Exact
again.

    deployments/infrastructure/oidc.tf:462 = resource "vault_identity_oidc_client" "openviking" {

## DOC-17 (advisory) — CLOSED, the twins agree

    deployments/infrastructure/services.tf:217 = ### OpenViking's workspace and RAGFS's local scratch.
    deployments/applications/services/openviking.hcl:32 =     ### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live

The "its OAuth SQLite db" clause is gone from the Terraform half, so the pair no
longer disagrees with each other or with `docs/openviking.md`'s statement that
OpenViking's own OAuth 2.1 implementation is off.

## DOC-23 (new, informational) — the Dockerfile `--no-deps` comment

    Dockerfile.openviking:36 = # whose whole purpose is a reproducible pin. ov_postgres needs openviking and
    Dockerfile.openviking:37 = # pydantic, which the base image carries, plus psycopg and psycopg_pool, which
    Dockerfile.openviking:38 = # RUN #2 supplies. Do not strip `pool` from RUN #2 as redundant: the adapter

Internally consistent, which is all this tree can check: RUN #2 at :46-48 is
`psycopg[binary,pool]==3.2.3`, which is exactly what supplies `psycopg` and
`psycopg_pool`, so the attribution names the right block and the "do not strip
pool" warning points at the right RUN. The cross-reference at :33 resolves too:
`Dockerfile.embark:32-33` is the `--no-deps` paragraph. A build comment is not a
reader-facing documented surface, so this was never required. Recorded because
the delta touched it.

## Wrapping, re-checked after the fence changed again

The four added comment lines pushed nothing over 80. `docs/openviking.md` holds
**zero** lines over 80 characters. `docs/haproxy_reverse_proxy.md` still holds
zero. `docs/workload-identity.md`'s over-80 set is byte-identical to HEAD's,
shifted by the three added lines (49, 65, 70, 281, 501, 537).
`docs/vault-human-auth.md`'s over-80 set is the same six lines as HEAD's; line
42 grew 199 to 211 characters, but it is a markdown table row and every row in
that table is over 80 already. Not a regression and not wrappable.

## Slop scan, re-run in full over the re-edited `docs/openviking.md` (1080 words)

Layer 0: no identity leaks, no `TODO`/`FIXME`/`XXX`/`HACK`, every cited path
resolves (`scripts/check_openviking_config.py`, `scripts/bifrost_smoke.py`,
`scripts/embark_rerank.py`,
`deployments/applications/services/openviking/README.md`). The one command that
failed Layer 0 last cycle is DOC-19, now closed on measurement. Layer 1: 6/6.
Layer 2: 0 over-80, 0 em dashes, 0 ` -- `, 0 smart quotes, 0 semicolon splices,
0 tier-1 slop, 0 self-narration, 0 negative parallelism, 0 spatial copula, 0
participial tails, 0 British spellings, 0 throat-clearing, 0 emphasis crutch, 0
prose arrows. Layer 3: no unearned quality claims. The new comment block also
ends without a terminal period, matching every sibling block in the fence
(DOC-18 stays consistent).

## Advisories — follow-ups, not commit blockers

- **DOC-20 (low).** `docs/openviking.md:111` names `/api/v1/collections` and
  nothing in this repo produces that route; the only OpenViking paths with a
  producer here are `/ready` and `/health`. Unverifiable from this tree rather
  than provably wrong, and under `auth_mode oidc` a wrong path would 401 too,
  so the check cannot catch its own typo. Worth confirming against upstream
  once, on the node, the first time an operator runs the runbook.
- **DOC-22 (low, cosmetic).** `docs/haproxy_reverse_proxy.md:35` is a
  33-character line mid-paragraph, left by the earlier rewrite.

    docs/haproxy_reverse_proxy.md:35 = `grafana` reaches that same Vault

  Neighbors run 75-78. Nothing is over 80 and no sentence is wrong; re-flowing
  would churn six lines to fix one. Leave it.

## Re-attach record

All 19 untouched settled findings carry a cycle-4 absence claim in
`.loop/scratch/OV1-openviking-service.documentation/findings.json`. DOC-14 and
DOC-18 were re-opened and re-run rather than asserted, because the fence they
cover changed again this cycle.
