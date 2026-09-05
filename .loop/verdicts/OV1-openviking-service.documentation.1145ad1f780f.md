---
verdict: pass-with-required-fixes
tree: 4312c61eb2458e521ea19f417b950eadbf5f6501
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY. This cycle's briefing gave a tree
fingerprint but no 64-hex scope digest, and named no verdict_binding_inputs.
The floor is not mine to choose and I must never write a digest I computed for
a set I chose, so bound_paths / scope / citations are omitted and this verdict
falls back to the whole-tree binding, which is stricter. Every anchor cited
below carries its verbatim line inline instead. Same condition cycles 1 and 2
recorded.

For the record, the artifact reviewed was the working tree against c5cba06:
modified .pre-commit-config.yaml, deployments/applications/secrets.tf,
deployments/applications/services.tf, deployments/applications/storage.tf,
deployments/infrastructure/oidc.tf, deployments/infrastructure/secrets.tf,
deployments/infrastructure/services.tf,
deployments/infrastructure/services/haproxy.hcl,
docs/haproxy_reverse_proxy.md, docs/workload-identity.md,
scripts/check_oauth2_proxy_guard.py; added
deployments/applications/services/openviking.hcl,
deployments/applications/services/openviking/ (Dockerfile.openviking,
justfile, README.md),
deployments/infrastructure/services/oauth2-proxy-openviking.hcl,
docs/openviking.md, scripts/check_openviking_config.py.
-->

# Documentation review, cycle 3 (review cap)

**Verdict: pass-with-required-fixes. Two required fixes, both in markdown,
both one line.** Neither is cosmetic. The first is a runbook command that
prints a pass while measuring nothing; the second is an enumeration that was
exact before this diff and is short by one name after it.

All four fixes the briefing named are real. DOC-15's rewrap preserved meaning
exactly. The rewritten "Verifying a deployment" section is clean on all three
slop layers and every path, identifier and version in it resolves. One command
in it does not run as documented, and that is the blocking finding.

---

## REQUIRED before this commits

### DOC-19 (high) — the foreign-audience check sends no token and prints a pass

`docs/openviking.md:102-107`:

    docs/openviking.md:102 = # a token minted for another client is refused. Also on the node, and for the
    docs/openviking.md:103 = # same reason: a curl carrying a bearer token but no proxy session cookie is
    docs/openviking.md:104 = # redirected to Vault by the proxy and never reaches OpenViking
    docs/openviking.md:105 = $ ssh radxa@192.168.2.50 curl -s -o /dev/null -w '%{http_code}' \
    docs/openviking.md:106 =     -H "Authorization: Bearer <token minted for another client>" \
    docs/openviking.md:107 =     http://127.0.0.1:1933/api/v1/collections   # expect 401

`ssh` joins its command arguments with spaces and hands the resulting string to
a shell on the remote host. The local quotes are consumed by the local shell,
so the remote `curl` never sees them. Reproduced with a stand-in that performs
exactly that join-and-reparse, the remote command line is:

    curl -s -o /dev/null -w %{http_code} -H Authorization: Bearer eyJ... http://127.0.0.1:1933/api/v1/collections

and `curl` receives eight-plus separate arguments where the doc intends four.
`-H Authorization:` is a header with an empty value, which is curl's documented
way to REMOVE a header. `Bearer` and the token become two extra URLs.

Measured, not reasoned. Against a local header-echo server with curl 8.5.0:

- correctly quoted: server logged `Authorization: 'Bearer eyJfaketoken'`,
  terminal printed `401`.
- as `docs/openviking.md:105-107` writes it: server logged
  `Authorization: None`, terminal printed `000`, `000`, then the third
  transfer's body and `401`.

So the request carries no Authorization header at all. The `401` an operator
sees at the end of that output is the plain unauthenticated 401, which the
service returns whether or not it would reject a foreign audience. The comment
at `:102` says this line shows "a token minted for another client is refused".
It shows nothing of the kind, and it looks like it does.

Why this is required rather than advisory: `.loop/evals/OV1-openviking-service.md:39`
resolves R15's runtime half as a LABELLED PROXY and states in its Expected cell
that the proxy does NOT measure "whether a token carrying a foreign audience is
refused". `.loop/plans/OV1-openviking-service.md:776` then makes
`docs/openviking.md` carrying "the runbook that checks the rest by hand" the
substitute for that measurement. This is the one line standing in for it, and a
check that reports the expected code while testing nothing is worse than an
absent check.

Fix: quote the remote command. Verified through the same reproduction that

    $ ssh radxa@192.168.2.50 'curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer <token minted for another client>" \
        http://127.0.0.1:1933/api/v1/collections'   # expect 401

delivers `argv[7] = [Authorization: Bearer <token minted for another client>]`
as one argument. The sibling `ssh` line needs no change:

    docs/openviking.md:97 = $ ssh radxa@192.168.2.50 curl -s http://127.0.0.1:1933/ready

survives the re-parse intact (`argv = [-s] [http://127.0.0.1:1933/ready]`).

### DOC-9 (medium, OVERTURNED from cycle 2's not-required) — the OIDC client list was exact and this diff makes it short

    docs/vault-human-auth.md:42 = | `oidc.tf` | The OIDC signing key, the shared `groups` and `email` scopes, the provider, one throwaway smoke-test client, and the consumer clients added since (nomad, memex, oauth2-proxy, grafana) |

Cycle 2 closed this as not-required on the reasoning that the counts there were
already unmaintained. I measured it this cycle and half of that reasoning is
wrong. At HEAD, `deployments/infrastructure/oidc.tf` held exactly five
`vault_identity_oidc_client` resources: `smoke`, `nomad`, `memex`,
`oauth2_proxy`, `grafana`. The row names the smoke client separately and then
the four others by name. It was COMPLETE and exact.

This diff adds the fifth consumer:

    deployments/infrastructure/oidc.tf:462 = resource "vault_identity_oidc_client" "openviking" {

and leaves the row naming four of five. A reader consulting "What Terraform
creates" to learn which clients exist is now wrong, and the diff's own new
comment sends them there:

    deployments/infrastructure/oidc.tf:455 = ### (docs/vault-human-auth.md:288-292) - the built-in "allow_all" assignment,

Fix: add `openviking` to the parenthetical. One word. The precedent is in the
same file, where the grafana client's arrival is already reflected in that list.

**The other half of the old DOC-9 claim stays not-required.**
`docs/vault-human-auth.md:291` and `docs/cluster-roles.md:172` both say "Four
of the six known consumers" declare flat access. Measured at HEAD, only TWO
clients declared `assignments = ["allow_all"]` (`oauth2_proxy`, `grafana`), so
that sentence already did not track the resource count before this ticket. Not
this ticket's to fix, and not required here.

---

## Confirmed fixed

- **DOC-15 — fixed, and the meaning survived.** `docs/haproxy_reverse_proxy.md`
  now holds ZERO lines over 80 characters. HEAD held exactly one, the 91-char
  predecessor of the edited sentence, so the pre-existing offender is gone too.
  I checked the rewrap the way it has to be checked, at word level rather than
  line level: diffing the paragraph's words HEAD vs now returns only the
  intended widening (`dash` and `registry-ui` becomes three names, `4180 and
  4181` becomes three ports, `both` becomes `all`) plus the two new sentences.
  No HEAD sentence was dropped, reordered or altered.

      docs/haproxy_reverse_proxy.md:26 = | `openviking.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4182 |
      docs/haproxy_reverse_proxy.md:30 = HAProxy no longer gates it. `dash`, `registry-ui` and `openviking` each sit

  The new claim is true: `oauth2-proxy-openviking.hcl:75` sets
  `OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER="true"` and neither sibling jobspec
  sets it, so "differs from the other two" is exact.

- **DOC-16 — fixed, and the twins agree again.**

      deployments/applications/storage.tf:35 =     # creation (datalake and mlflow-artifacts have none).
      docs/workload-identity.md:272 = keys for buckets no job consumes. `openviking` is no longer one of those: its

- **DOC-18 — fixed by restructure.** Every comment block in the fence now ends
  without a terminal period. The period at `:112` is a sentence separator
  inside a two-sentence block, matching `:94`'s own internal break:

      docs/openviking.md:94 = # the service is up and its backends opened. Checked ON the node: the edge

- **The loopback rewrite is correct, and better than what the adversarial pass
  asked for.** A14 suggested pointing the line at `http://192.168.2.50:1933`.
  The implementer used `ssh` plus `127.0.0.1`, which works because
  `openviking.hcl:70` sets `network_mode = "host"` and `:153` binds
  `"host": "0.0.0.0"`, and which is necessary because
  `deployments/applications/services.tf:160` admits only `192.168.2.50` to port
  1933. The stated reason is accurate too: the proxy carries no auth exemption
  (that absence is what `scripts/check_oauth2_proxy_guard.py` now enforces over
  the new jobspec), and it sets no `SKIP_JWT_BEARER_TOKENS`, so a bearer token
  with no session cookie is redirected rather than passed through.

## Slop layers, re-run in full on the changed section and the whole file

`docs/openviking.md`, 1026 words.

- **Layer 0.** Zero identity leaks, zero `TODO`/`FIXME`/`XXX`/`HACK`. Every
  cited path resolves: `scripts/check_openviking_config.py`,
  `scripts/bifrost_smoke.py`, `scripts/embark_rerank.py`,
  `deployments/applications/services/openviking/README.md`. Every identifier
  resolves: `data "vault_identity_oidc_client_creds" "openviking"`
  (`services.tf:45`), the deliberate absence of a `minio_iam_policy` named
  `openviking`, `U7-upgrade-bifrost-2x` (the plan file exists), dimension 768
  (`openviking.hcl:136`), port 1933, port 4182
  (`oauth2-proxy-openviking.hcl:49`). The unbackticked "1.6.11" boundary is
  supported by U7's measured P4, not invented. Ran
  `check_openviking_config.py` and its `--self-test`: both exit 0. The one
  Layer 0 failure is DOC-19.
- **Layer 1.** 6/6. Thesis at `:3-5`; the section's own thesis at `:90` ("It
  does **not** measure anything about a running service") lands before the
  fence and earns it.
- **Layer 2.** 0 lines over 80, 0 em dashes, 0 ` -- `, 0 smart quotes, 0
  semicolon splices, 0 tier-1 slop, 0 self-narration, 0 hedging seesaw, 0
  "not just"/"not only", 0 participial tails, 0 British spellings, 0 spatial
  copula, 0 significance cluster, 0 throat-clearing, 0 emphasis crutch, 0
  performative honesty, 0 prior-art marker, 0 prose arrows, 0 negative or
  contrastive parallelism.
- **Layer 3.** No unearned quality claims.

Same layers on the other two edited docs. `docs/haproxy_reverse_proxy.md`: 0
over-80, 2 em dashes in 847 words (within budget, both pre-existing).
`docs/workload-identity.md`: 6 over-80 lines, a byte-identical set to HEAD's
and all in pre-existing command fences; the four added lines are all under 80.

## Advisory, for a follow-up rather than this commit

- **DOC-17 is half fixed, and the half-fix left a contradiction.**

      deployments/applications/services/openviking.hcl:32 =     ### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live
      deployments/infrastructure/services.tf:217 = ### OpenViking's workspace, its OAuth SQLite db and RAGFS's local scratch.

  The clause was cut from one twin and left in the other, and
  `docs/openviking.md:36` ("OpenViking's own OAuth 2.1 implementation is
  **off**") sides with the version that cut it. Still advisory, because both
  surfaces are Terraform comments rather than docs a reader follows and
  severity belongs to the adversarial pass that raised the question. But the
  judgment call it was waiting on has now been made, so the fix is unambiguous
  and is one clause.

- **`/api/v1/collections` has no producer in this repo.** `docs/openviking.md:107`
  names it; the only openviking routes with a producer here are `/ready`
  (`openviking.hcl:60`) and `/health` (ticket P18). Unverifiable from this tree
  rather than provably wrong, and worth noting that under `auth_mode: "oidc"` a
  wrong path would 401 too, so this check cannot catch its own typo. Survives
  the DOC-19 fix.

- **`docs/haproxy_reverse_proxy.md:35` is a 33-character ragged line
  mid-paragraph**, left over from where the old wrap broke. Not a rule
  violation: 80 is a maximum, not a fill target. Purely aesthetic.

## Settled findings the diff did not touch

- DOC-1 — no change in scope, still holds. The content fix at `:26` and
  `:30-34` is intact; its wrap regression is now closed as DOC-15.
- DOC-2 — no change in scope, still holds. Re-opened `workload-identity.md:272-275`;
  unchanged and still true against `secrets.tf:254` and `openviking.hcl:110-112`.
- DOC-3 — no change in scope, still holds. `embark_rerank.py` exists and the
  `bifrost_smoke.py` disclaimer survives the rewrite at `:112-114`.
- DOC-4 — no change in scope, still holds. `docs/openviking.md:19` resolves.
- DOC-5 — no change in scope, still holds. Re-ran the checker and its
  `--self-test` this cycle; both exit 0.
- DOC-6 — no change in scope, still holds. Service `README.md:7` names exactly
  the two `RUN` blocks at `Dockerfile.openviking:39-47`; zero repo-wide matches
  for `openviking[auth]`. Its one over-80 line is a table row, unwrappable.
  All five recipes its fence names (`show`, `build`, `verify`, `push`,
  `release`) exist in the justfile beside it, and both paths it cites
  (`bootstrap/playbooks/configure_podman.yml`,
  `deployments/applications/services/embark/Dockerfile.embark`) resolve.
- DOC-7 — no change in scope, still holds. `:100` uses the root path.
- DOC-8 — no change in scope, still holds. Zero semicolon splices.
- DOC-10 — no change in scope, still holds. Re-opened `registry-ui.md:28-30`:
  the antecedent is dash's and registry-ui's jobspecs, over which the guard
  does still run.
- DOC-11 — no change in scope, still holds. `README.md:62` is a parenthetical
  category list that already omits several hooks.
- DOC-12 — no change in scope, still holds. Re-opened `dns.md:14` and `:21` and
  `tls-certificates.md:3-4`: `openviking.lab` is a flat label under the `*.lab`
  wildcard, and `dns.md:21` says adding a service needs no DNS change.
- DOC-13 — no change in scope, still holds. No tile was scoped; the fix would
  be `tiles.json`, not docs.
- DOC-21 (new, closed not-required) — the fence covers three of the four
  behaviors the eval's R15 row lists as unmeasured. "Persists a collection into
  the `openviking` schema" has no step, but the ticket's own statement of the
  runbook obligation at `.loop/plans/OV1-openviking-service.md:776` names three
  items, and the fence covers all three. Not owed.

## What clears once the two lines land

Nothing else in this diff touches a documented surface that went unupdated. The
new hostname, port, proxy, bucket, OIDC client, firewall rule, host volume,
pre-commit hooks and derived image all have their describing doc updated in the
same change, and the new page itself is accurate everywhere I could measure it.
