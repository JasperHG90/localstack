---
verdict: pass
tree: f77e9fbca13454ebf0e53b673a35fbafa0316541
---

# Documentation review: F1-foundation-nomad-wi-jwt-trust

## Scope

Primary deliverable: `docs/workload-identity.md` (new, 283 lines). Companion
artifact: `tests/wi-vault-probe.nomad.hcl` (new, 68 lines). Harness state:
`.loop/ledger.json` (review-stage update only). The doc is the only
user-facing surface; the test job is a scratch spec run by the operator
verification.

## Method

Read the doc in full, the test job in full, and the ticket plan. Then opened
every cited source file and compared each load-bearing claim against the
actual repo content. Ran the slop-scan greps from
`.claude/rules/slop-scan-for-docs.md` against the doc. Checked every other
doc under `docs/` that mentions the same surface for contradictions.

## Findings

### 1. Cited paths — all resolve (severity: none)

Every path the doc cites is a real file in the tree:

- `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` — exists; `:60-62`
  holds `default_identity { aud = ["vault.io"] ttl = "1h" }`, matching the
  doc's chain step 1 (lines 13-17).
- `bootstrap/roles/nomad_server/tasks/main.yml` — exists; `:219-222` writes
  `jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"` and
  `default_role="nomad-workloads"`, matching doc lines 21-25.
- `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json` —
  exists; `bound_audiences: ["vault.io"]`, `user_claim: "/nomad_job_id"`,
  exactly three `claim_mappings` (`nomad_namespace`, `nomad_job_id`,
  `nomad_task`), `token_policies: ["nomad-workloads"]`. Matches doc lines
  36-41 and the fixed-claims section (lines 50-64).
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` —
  exists; exactly three `path` blocks: two `read` on
  `secret/data/<ns>/<job>/*` and bare path, one `list` on
  `secret/metadata/<ns>/*`, zero `bootstrap/*`. Matches doc lines 68-89.
- `deployments/infrastructure/acme.tf` — exists; `:87` sets
  `token_policies = ["nomad-workloads", vault_policy.acme_tls_write.name]`,
  matching the one-token rule (doc lines 109-117).
- `deployments/infrastructure/services/acme.hcl` — exists; `:73-74` has
  `vault { role = "${vault_role}" }`, matching doc line 105.
- `deployments/infrastructure/services/minio.hcl:30-40` and
  `deployments/applications/services/memex.hcl:44-60` — both carry the bare
  `vault {}` + `template { env = true }` pattern the doc describes (lines
  122-127). Verified.
- `tests/wi-vault-probe.nomad.hcl` — exists; its template reads
  `secret/data/default/wi-test/probe`, which falls under the policy's
  job-scoped `secret/data/default/wi-test/*` grant. Consistent.

No hallucinated paths, URLs, or identifiers.

### 2. Policy shape is post-F9, not stale (severity: none)

The doc states the policy is "three `path` blocks" (line 69), lists them
correctly (job-scoped `secret/data` reads, namespace-scoped
`secret/metadata` list, zero `bootstrap/*`), and explicitly records that
"F9 removed the prior `bootstrap/data/*` ... and `bootstrap/metadata/*` ...
grants" (lines 77-78). The actual template file confirms this: 21 lines,
three path blocks, a comment block recording what F9 removed, no bootstrap
grants. The threat-model section (lines 80-89) states plainly that secret
values are job-scoped but secret paths are namespace-wide (cluster-wide in
practice), which is the real post-F9 shape. Not the pre-F9 shape, not an
idealized one.

### 3. F1/M1 scope and F10 pointer are accurate (severity: none)

The doc states F1 delivers the JWKS URL only and does not deliver an OIDC
discovery document (lines 176-191). It names `F10-foundation-nomad-oidc-
issuer` as the owner of enabling `oidc_issuer`. The F10 plan exists at
`.loop/plans/F10-foundation-nomad-oidc-issuer.md` and its scope is exactly
that: "Set `server.oidc_issuer` on the Nomad server so it serves an OIDC
discovery document." The doc's claim that the discovery endpoint returns
"OIDC Discovery endpoint disabled" is consistent with the ticket's
live-verified premise. No overstatement of what F1 delivers.

### 4. JWKS URL resolves (severity: none)

The doc cites `http://192.168.2.30:4646/.well-known/jwks.json` as the
external endpoint. `docs/haproxy_reverse_proxy.md:18` confirms
`nomad.lab.orangecluster.nl` maps to `firebat (192.168.2.30)` on port
`4646`. The internal `127.0.0.1:4646` form matches the Ansible `jwks_url`
in `main.yml:220`. Both forms are correctly presented.

### 5. No contradictions with other docs (severity: none)

`docs/vault-human-auth.md` opens by stating machine identity is a separate
system (Nomad WI JWTs, `jwt-nomad` mount) and that "nothing here touches
that." It defers to the new doc's domain without overlap or contradiction.
`docs/cluster-roles.md:11` describes the service-account role as "per-
service, via `jwt-nomad` workload identity," consistent with the new doc.
`docs/notes/audit/plan-premise-sweep-2026-07.md` contains a pre-F9 policy
snapshot but explicitly supersedes it inline (lines 78-82), so it is not a
contradiction this change created or left stale. No doc the change should
have updated was left untouched.

### 6. Slop scan — clean (severity: none)

- **P0 identity leaks**: none.
- **P0 bare stubs** (TODO/FIXME/XXX/HACK): none.
- **P0 hallucinations**: all cited paths, URLs, and identifiers resolve to
  real files and endpoints.
- **Em dashes**: zero. No `--` prose substitution.
- **Tier-1 slop words**: none (no "structured", "comprehensive",
  "actionable", "seamless", "robust", "myriad", "empower", "navigate").
- **Self-narration**: none.
- **Hedging seesaw**: none.
- **Parallel "not just / not only X but also Y"**: one hit at line 75
  ("not just its own job's") is a descriptive contrast stating real
  behavior, not the parallelism construct. Not slop.
- **Participial tail**: none.
- **British spellings**: none.
- **Smart quotes**: none.
- **Semicolon splices**: all semicolons are inside fenced code blocks
  (verified with fence tracking). None in prose.
- **ASCII arrows**: three hits, all inside a fenced code block as shell
  comments showing expected command output. Excluded by the rule.
- **Line wrap**: five lines exceed 80 chars; all are inside code blocks
  (shell commands that should not wrap) or a prose line carrying a long
  backticked file path. Non-blocking.
- **Thesis-first**: the opening paragraph states the single takeaway
  (Nomad WI JWT, Vault `jwt-nomad` trust, machine identity, no static
  credentials). Clean.

### 7. Test job matches the doc (severity: none)

`tests/wi-vault-probe.nomad.hcl` carries the named `identity` stanza the
doc specifies (`name = "vault_default"`, `aud = ["vault.io"]`,
`file = true`, `change_mode = "restart"`), matching the doc's load-bearing
`name`-field guidance (lines 132-153) and the ticket's Q5 resolution. The
job's template path (`secret/data/default/wi-test/probe`) falls under the
policy's job-scoped grant. The doc's operator-verification section (lines
193-283) references the test job by name and path consistently.

## Verdict

PASS. The doc describes the post-F9 policy shape accurately, every cited
path and endpoint resolves, the F1/M1 scope split and F10 pointer are
correct, no other doc is left contradicting it, and the slop scan is clean.
No merge-blocking findings.