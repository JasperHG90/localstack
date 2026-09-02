---
verdict: pass
tree: cae4315c2e5f8c12e00b2bb73ab17a32c62f3380
---

# Adversarial review, cycle 4 (final) — G1-grafana-native-oidc-login

Verdict: **pass**. The three cycle-3 fixes are correct, the claims I was
asked to re-derive hold on their own evidence rather than on my prior
report, the gate is green, rows 6/8/9 pass, and all six eval amendments
are intact. Two low findings the author declared and left stand; I record
them as follow-ups and do not gate on them.

## Scope binding

The three scope-binding lines are **deliberately omitted**. My briefing
carried the tree fingerprint but no 64-hex scope digest and no
`verdict_binding_inputs`, and fabricating one for a path set I computed
myself is forbidden. This verdict therefore falls back to the whole-tree
binding, which is stricter. The reviewed path set, for the record:

    .loop/evals/G1-grafana-native-oidc-login.md
    .loop/ledger.json
    deployments/infrastructure/auth_userpass.tf
    deployments/infrastructure/nomad_oidc.tf
    deployments/infrastructure/oidc.tf
    deployments/infrastructure/secrets.tf
    deployments/infrastructure/services.tf
    deployments/infrastructure/services/grafana.hcl
    deployments/infrastructure/services/oauth2-proxy.hcl
    deployments/infrastructure/variables.tf
    docs/dash-landing-page.md
    docs/haproxy_reverse_proxy.md
    docs/monitoring.md
    docs/postgres-vault-dynamic-creds-spike.md
    docs/vault-human-auth.md

## Deterministic floor

`loopctl verify-eval-substance G1-grafana-native-oidc-login` returns
**valid**, one advisory, no hard fail:

    warn: row '`terraform plan` is additive-only' is annotated
    verdict: assessed-statically-not-executed

An advisory is not a fail. This one the check can only echo from the
author, and it is the operator's to clear by running `terraform plan`
against the live cluster. No plan-drift advisory, so the marker's `plan:`
fingerprint still matches the plan.

## Gate

Re-ran it myself. The prior trust stamp was keyed to fingerprint
`08292f6a…`, which is not this tree, so a re-run was mandatory rather
than optional.

    just pre_commit   →   exit 0, all 18 hooks Passed
    (Terraform Validate, Terraform Format, Nomad Format, detect private key,
     Ruff x4, Mypy x2, Pytest x2, …)

Trust stamp rewritten to `cae4315c…` at
`.loop/scratch/G1-grafana-native-oidc-login.adversarial/trust-stamp.json`.

## The delta is exactly the three declared edits

`ls --time-style=full-iso` puts `nomad_oidc.tf`, `oidc.tf` and
`docs/postgres-vault-dynamic-creds-spike.md` in one write batch at
23:47:52 and every other reviewed file at 23:34 or earlier. No fourth
edit slipped in.

### Edit 1 — `docs/postgres-vault-dynamic-creds-spike.md:35` (G1-ADV-13, RESOLVED)

`docs/postgres-vault-dynamic-creds-spike.md:35 = - the admin role, `deployments/infrastructure/secrets.tf:98-112``

Correct. `secrets.tf:98 = resource "vault_kv_secret_v2" "postgres_root_credentials" {`
and `:112` is its closing brace. I re-checked the premise instead of
taking it from my own cycle-3 note: `git show HEAD:…/secrets.tf` puts
that same block at 74-88, so the cite is restored to the resource it has
always named. Swept every `<file>:<line>` reference in the tree outside
`.loop/archive/`: no other cite into a file this diff shifts went stale.

### Edit 2 — `deployments/infrastructure/oidc.tf:72-77` (G1-ADV-10 / DOC-G1-16, RESOLVED)

`oidc.tf:74 = ### without this scope. Most consumers can: memex and the Nomad client both`

You asked me to check you had not garbled my report. You had not. I
re-derived all three claims from source:

- **memex speaks OIDC with no proxy.** `docs/vault-human-auth.md:375-381`
  ("A service that verifies the token ITSELF must read the id_token…"),
  and `memex_oidc.tf:70` gives memex its own client and its own key. No
  proxy anywhere in its path.
- **memex logs people in on `groups` alone.**
  `docs/memex-oidc-verification.md:246 =   scopes: ["openid", "groups"]`.
  The same doc at :325-327 records a login *succeeding* with `["openid"]`
  only, which is stronger than the comment claims.
- **The Nomad client, likewise.** `nomad_oidc.tf:136-152` is a native
  `nomad_acl_auth_method`, no proxy, and
  `nomad_oidc.tf:151 =     oidc_scopes      = [vault_identity_oidc_scope.groups.name]`.
- **R4/Phoenix is the other consumer that needs email.**
  `.loop/ledger.json:357` and
  `.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:651` both record the
  hard requirement. I grepped every other plan and eval for a second one
  and found none, so "the other" is exact, not loose.

### Edit 3 — `deployments/infrastructure/nomad_oidc.tf:159-162` (DOC-G1-14, RESOLVED)

`nomad_oidc.tf:160 =     # this provider does not advertise `profile`, so mapping it`

Confirmed. `vault_identity_oidc_provider.lab` sets
`scopes_supported = [groups, email]` (`oidc.tf:122-125`). `profile` is
absent, `preferred_username` is a `profile`-scope claim, so mapping it
would still bind an always-empty value. The weakened premise is true and
the unchanged conclusion still follows from it.

`nomad_oidc.tf` sits outside the plan's section 7 code surface
(plan:205-221 names `services.tf`, `grafana.hcl` and `docs/monitoring.md`),
same class as `docs/vault-human-auth.md` and `docs/haproxy_reverse_proxy.md`.
Named, not faulted: the file is touched only because this diff falsified a
claim in it, and the repo's surgical-changes rule requires cleaning up your
own mess.

## Rows 6, 8, 9 re-scored

| Row | Result |
|---|---|
| 6 — Guardrail: both copies of the root URL changed | **pass**. `grep -n '192\.168\.2\.47:3000'` over `grafana.hcl` and `services.tf` returns zero. Both sibling cites exact: `GF_SERVER_ROOT_URL` at `grafana.hcl:74`, `grafana_external_url` at `services.tf:449`. |
| 8 — The client id reached the provider's allowlist | **pass**. `vault_identity_oidc_client.grafana.client_id` is at `oidc.tf:105` inside `local.oidc_provider_client_ids`; Terraform Validate passed in my gate re-run. |
| 9 — Guardrail: no client secret landed in a `.tf` file | **pass**. `grep -rnE 'hvo_secret_[A-Za-z0-9]{8,}' deployments/` returns zero. The bare pattern still returns the two prose mentions (`secrets.tf:73`, `:209`), which is exactly why the narrowing was counter-signed. |

## Amendments intact (the check that caught a real regression once)

Six `amended-by:` lines at `.loop/evals/…:32, 34, 36, 38, 40, 42`, and
the footer at `:43` reads `<!-- amendments: 6 (last: 2026-09-02 by
JasperHG90) -->`. Nothing dropped, count honest.

## New attack this cycle, and it survived

I attacked the one thing no gate exercises and no prior cycle had
proved: a job template reading a **new** KV2 path can 403 at start if the
Vault policy is per-secret. It is not.

`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`
grants read on `secret/data/<nomad_namespace>/<nomad_job_id>/*`, so
`default/grafana/oidc` (`secrets.tf:78`) falls under the same prefix as
the already-read `default/grafana/admin` and `default/grafana/telegram`.
`grafana.hcl:29` is a bare `vault {}`, so the job lands on that default
role. No policy change is needed and none is missing.

Two supporting checks: `grafana.hcl:121 =         env         = true`, so
the two `GF_AUTH_GENERIC_OAUTH_CLIENT_*` values become process env rather
than a file nothing reads; and `services.tf:431` wires
`grafana_oidc_secret` from `vault_kv_secret_v2.grafana_oidc_client.path`,
the same attribute the working `grafana_secret` uses one line above.

## Follow-ups — recorded, not gating

None of these should hold a commit. All are low, all are pre-existing in
substance, and the review-cycle cap is spent.

1. **MINOR — `oidc.tf:4` and `:7-10` contradict the file's own contents.**
   `oidc.tf:4 = ### scopes, the provider itself, and ONE throwaway smoke-test client that proves`
   and `oidc.tf:7 = ### Consumer clients (dash/L1, mlflow/R1, phoenix/R4, the MinIO tiers/M2) are`
   ("…NOT created here"). But `oidc.tf:192` already defined
   `vault_identity_oidc_client.oauth2_proxy` at HEAD, and `:232` now adds
   grafana. **You asked whether I disagree: mildly, yes.** Line 4 was
   already edited in this diff (`scope` → `scopes`), so the header was in
   the blast radius and a one-word fix was in reach. But the header was
   false before this ticket, `docs/vault-human-auth.md:42` was corrected
   here to name both consumer clients so the canonical surface is right,
   and the header's operative instruction (">>> APPEND YOUR CLIENT HERE
   <<<" for the provider list) is still correct. Not worth a cycle.

2. **LOW — the `What Terraform creates` table is now internally
   inconsistent.**
   `docs/vault-human-auth.md:43 = | `secrets.tf` | Two KV2 writes: the operator password, and the smoke client's credentials |`
   while row 42 directly above it *was* updated to name oauth2-proxy and
   grafana. `secrets.tf` held `oauth2_proxy_oidc_client` (`:210`) at HEAD
   and `grafana_oidc_client` (`:76`) now, so the undercount predates the
   ticket; the oddity is that the fix stopped one row short. Agreed as
   left, recorded so it is not lost.

3. **INFORMATIONAL — `oidc.tf:178 = ### the documented procedure (docs/vault-human-auth.md:282-290) — the built-in`**
   cites branch 3 as 282-290, straddling branches 2 and 3, where the new
   G1 block at `:215` cites the exact 288-292. Pre-existing and unshifted
   by this diff, so not chargeable here.

4. **INFORMATIONAL — row 10's `Expected` names three creates where the
   diff makes four** (`vault_identity_oidc_scope.email` is the fourth).
   Row verdict unaffected: its `Fails-when` is destroy/replace only.

5. **OPERATOR ACTION — the `assessed-statically-not-executed` advisory on
   row 10 stands.** Only a real `terraform plan` clears it, which takes the
   Consul state lock and is not safe unattended. `loopctl eval-rebind`
   refuses inside this worktree by design, so I cannot clear it either.

## Ledger

Appended 17 cycle-4 entries (`G1-ADV-13`, `-10`, `-15` … `-19` plus one
absence claim per untouched settled finding) to
`.loop/scratch/G1-grafana-native-oidc-login.adversarial/findings.json`.
