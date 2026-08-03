---
verdict: pass
plan: 066eb183640ed961e2c425d66d3a93288cad16910282d0c00e235af80d431371
---

# Premise verdict: SOUND

This is the first plan-validator pass ever run against this ticket. `loopctl
verify-plan F1-foundation-nomad-wi-jwt-trust` reports `valid` (deterministic
floor clean). I then re-derived and live-probed every load-bearing claim
against the actual repo and the actual cluster (`VAULT_ADDR`/`NOMAD_ADDR`/
tokens were reachable in this session) rather than trusting the plan's own
narration of its re-verification.

## Per-assumption findings (P1-P8, plan's own list)

- **P1 - Nomad->Vault trust chain runs in Ansible.** HOLDS.
  `bootstrap/roles/nomad_server/tasks/main.yml:207-214` enables `jwt-nomad`;
  `:216-226` configures `jwks_url` + `default_role="nomad-workloads"`. Read
  directly, matches verbatim. Live: `vault auth list -format=json` shows
  `jwt-nomad/` with accessor `auth_jwt_649fd6cc`.

- **P2 - The shared policy is 3 `path` blocks, 21 lines, matching the live
  cluster exactly.** HOLDS, live-confirmed. `wc -l
  bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` = 21.
  `vault policy read nomad-workloads` (run live) returns exactly the three
  `path` blocks the plan quotes, byte-for-byte, including the accessor
  `auth_jwt_649fd6cc` matching the auth list above.

- **P3 - Bootstrap mount untouched but unreachable via this policy.** HOLDS.
  `vault secrets list` (live) shows `bootstrap/` mounted. F9's own archived
  eval (`.loop/archive/F9-foundation-scope-nomad-workloads-policy/eval.md`,
  row 1 of the table, "The bootstrap write grant is gone") is exactly the
  citation the plan makes, and it asserts 403 on both read and write with a
  non-root `nomad-workloads` token — matches P3's claim precisely.

- **P4 - OIDC discovery disabled, JWKS is not.** HOLDS, live-confirmed.
  `curl $NOMAD_ADDR/.well-known/openid-configuration` -> "OIDC Discovery
  endpoint disabled" (live, this session). `curl
  $NOMAD_ADDR/.well-known/jwks.json` -> 3 keys (live, this session).

- **P5 - F10 now owns `oidc_issuer`, not F1.** HOLDS.
  `.loop/plans/F10-foundation-nomad-oidc-issuer.md` exists and its summary
  and title are exactly "Set server.oidc_issuer... so Nomad serves an OIDC
  discovery document." One inaccuracy: the plan and its Q7-closure note both
  say F10 is "stage `planning`" at time of writing; the live ledger
  (`.loop/ledger.json`) shows F10 at stage `ready`, not `planning`. This is
  stale narration, not a broken premise — "ready" is further along than
  "planning" and still means "not yet implemented," which is the only fact
  P5 actually leans on. Noted but does not sink the plan.

- **P6 - Fixed-claims constraint holds on Nomad 2.0.4 despite `extra_claims`
  now parsing.** HOLDS, live-confirmed by direct probe. I POSTed a job HCL
  with `identity { extra_claims = ["job_id", "task"] }` to
  `$NOMAD_ADDR/v1/jobs/parse` (Canonicalize=true): it parses cleanly and
  `ExtraClaims` appears in the canonicalized `Identities[0]`. Separately,
  `auth/jwt-nomad/role/nomad-workloads` (`vault read`, live) shows
  `claim_mappings` = exactly `nomad_job_id`, `nomad_namespace`, `nomad_task`
  - nothing from `extra_claims` is mapped, so the conclusion (no per-job
  custom scoping through Vault) stands exactly as the plan states.

- **P7 - Identity stanza must be NAMED `vault_default`, not bare.** HOLDS,
  live-confirmed by direct probe, both directions. A named
  `identity { name = "vault_default" ... }` job parses to
  `"Identity": null, "Identities": [{"Name": "vault_default", ...}]`. An
  unnamed `identity { aud = [...] file = true }` job parses to
  `"Identity": {"Name": "", "File": true, ...}, "Identities": []`. This is
  exactly the distinction the plan's Q5 resolution and eval 7 depend on.

- **P8 - One task = one Vault token; naming a role REPLACES
  `nomad-workloads`.** HOLDS. `deployments/infrastructure/acme.tf:87`
  (`grep -n` confirmed) reads
  `token_policies = ["nomad-workloads", vault_policy.acme_tls_write.name]`
  exactly as cited. Live: `vault list auth/jwt-nomad/role` returns
  `["acme", "nomad-workloads"]`, consistent with T3 already applied.

## Most dangerous assumption

P2 (the narrowed 3-block policy shape). Everything downstream -
requirement 1's doc content, the fixed-claims writeup, every eval from 1
through 9, and the "namespace-wide list is the surviving gap" threat-model
line - is a direct function of this shape being described correctly. It is
the one claim a stale re-plan would get wrong first, and it is the one I
live-verified byte-for-byte against `vault policy read nomad-workloads`. It
holds.

## Code-surface spot audit (beyond the P1-P8 set)

I independently re-opened every `path:line` anchor the plan cites as
"corrected 2026-08-02" rather than trusting the correction was accurate, and
all resolved exactly as claimed:
`nomad.hcl.j2:55-64` (vault/default_identity block), `:34-36` (acl block),
`justfile:10-11` (format), `:18-19` (pre_commit), `:41-43` (worktree_setup,
confirmed via direct read - `41: worktree_setup path:`, `42: ln -sfn...`,
`43: cp ...`), `secrets.tf:17,39,54,76` (all four `name = "default/..."`
lines, confirmed via `grep -n`), `deployments/applications/services.tf:128`
(`memex_auth_secret` line, confirmed), `deployments/infrastructure/
services.tf:298,306` (postgres/minio `nomad_job` resources, confirmed),
`services.tf:290` (the gitignored `id_rsa` `file()` call, confirmed),
`acme.tf:41-90` (confirmed exact resource-block bounds via `grep -n`),
`acme.hcl:73-75` (`vault { role = "${vault_role}" }`, confirmed),
`docs/haproxy_reverse_proxy.md:18` and `docs/monitoring.md:211,220`
(confirmed both support the 192.168.2.30:4646 claim), and
`.pre-commit-config.yaml:1,12,16-21,22-27,28-33` (exclude line, detect-
private-key, nomad-fmt, terraform-fmt, terraform-validate hook bounds, all
confirmed via direct read). I found no drift the plan missed.

`rescue-ssh.nomad.hcl` exists at repo root (Q4's cited pattern). No `tests/`
directory yet exists - consistent with the plan's own required-artifacts
list (it is new).

## Confirmed gap: the eval marker file, not fixed by this pass

`.loop/evals/F1-foundation-nomad-wi-jwt-trust.md` still asserts the pre-F9
policy shape. I read it directly and confirmed: its Definition of Done names
the `bootstrap/data/*` write grant as part of what the doc must describe,
and row 8 ("The doc records the real blast radius...") expects
`vault kv get -mount=bootstrap github` to **succeed** - the exact opposite
of what P3 (live-confirmed, 403) and this plan's eval 9 now assert. The plan
itself surfaces this honestly (Tests & validation gates callout, and item 7
of the Re-plan corrections section) and states it is out of this driver's
scoped task. I confirm the gap is real and current, not stale narration:
**this eval marker must be re-authored against the narrowed policy (at
minimum, flip row 8's expectation to 403 and drop the `bootstrap/data/*`
line from the Definition of Done) before implementation starts**, or the
loop's own eval will fail a correct implementation of this plan. This is a
required pre-implementation action item, separate from and not blocking
this plan document's own fingerprint.

## Contract hygiene

Clean. Non-goals are explicit and current (section 5, including the
corrected "do not narrow it further" and the live-reprobed `extra_claims`
non-goal). Tests are homed (`tests/wi-vault-probe.nomad.hcl` named with its
full identity stanza). Forks are surfaced with recommendations and resolved
in "Resolved forks," Q7 is closed with a pointer to F10 rather than silently
decided. The document carries the required `# Ticket:` title line, numbered
`## 1.`-`## 11.` headings, and the `## Premises / assumptions` section with
anchored probes for each P1-P8, satisfying the newly-enforced
`loopctl verify-plan` structural check (which reports `valid`).

## Conclusion

SOUND premise, clean contract -> **pass**. The one outstanding item (the
stale eval marker) is a required action for the operator before
implementation, not a defect in the plan document itself, and the plan
already discloses it rather than hiding it.
