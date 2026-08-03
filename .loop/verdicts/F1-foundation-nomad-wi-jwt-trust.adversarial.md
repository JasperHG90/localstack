---
verdict: pass
tree: f77e9fbca13454ebf0e53b673a35fbafa0316541
---

# Adversarial review: F1-foundation-nomad-wi-jwt-trust

## Deterministic floor

`loopctl verify-eval-substance F1-foundation-nomad-wi-jwt-trust` returned
`valid`. No mechanical eval defect (grep scorer, stale depends_on, dropped
field check). Proceeded to the semantic pass.

`loopctl verify` returned `ok`. The shared tree fingerprint
`f77e9fbca13454ebf0e53b673a35fbafa0316541` is a tree object; both ticket
files (`docs/workload-identity.md`,
`tests/wi-vault-probe.nomad.hcl`) have identical blob hashes in that tree
and in the working index. Every other file differing between that tree and
the current index is inside `.loop/` (175 files, all harness state). Zero
non-`.loop/` files differ.

## Premise soundness

Every factual claim in `docs/workload-identity.md` was cross-checked
against the live files. All confirmed.

- Policy described as three `path` blocks post-F9. Confirmed:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  lines 1-11 hold two `secret/data` read grants (wildcard + bare path) and
  one `secret/metadata/<namespace>/*` list grant. Lines 13-21 are a comment
  recording what F9 removed. No `bootstrap/*` grant survives.
- Role binds `vault.io`, maps exactly three claims
  (`nomad_namespace`, `nomad_job_id`, `nomad_task`), `token_policies` is
  `["nomad-workloads"]`. Confirmed:
  `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`
  lines 3, 6-10, 12.
- `nomad.hcl.j2` sets `vault { default_identity { aud = ["vault.io"] ttl = "1h" } }`.
  Confirmed at lines 55-64.
- JWKS config `jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"` with
  `jwt_supported_algs="RS256,EdDSA"` and `default_role="nomad-workloads"`.
  Confirmed: `bootstrap/roles/nomad_server/tasks/main.yml` lines 216-226.
- External JWKS URL `http://192.168.2.30:4646/.well-known/jwks.json`.
  Confirmed: `docs/haproxy_reverse_proxy.md:18` lists Nomad at
  `192.168.2.30:4646`.
- `acme.tf:87` sets `token_policies` to BOTH `nomad-workloads` and the
  dedicated `acme-tls-write` policy. Confirmed:
  `deployments/infrastructure/acme.tf` line 87.
- `acme.hcl:73-75` selects the role with `vault { role = "${vault_role}" }`.
  Confirmed: `deployments/infrastructure/services/acme.hcl` lines 73-75.
- OIDC discovery endpoint disabled; JWKS works. The doc states this and
  points to `F10-foundation-nomad-oidc-issuer` as the owner. Consistent
  with the ticket's requirement 5 and Q7 closure.
- Threat model states secret values are job-scoped, secret paths are
  namespace-wide (cluster-wide in practice since nearly every job runs in
  `default`). Matches the surviving `secret/metadata/<namespace>/*` list
  grant at policy lines 9-11.

No stale pre-F9 shape found anywhere in the doc. No false claims.

## Scope discipline

The diff touches exactly two ticket files, both new:

- `docs/workload-identity.md` (283 lines)
- `tests/wi-vault-probe.nomad.hcl` (68 lines)

No changes to `bootstrap/`, `deployments/`, or any policy, role, audience,
or trust config. `git diff HEAD -- bootstrap/ deployments/` returned empty.
The only other changed file is `.loop/ledger.json` (harness state, not
ticket content). Confirmed by diffing the target tree against the current
index: all 175 differing files are inside `.loop/`.

## Test job correctness

`tests/wi-vault-probe.nomad.hcl` lines 39-44 carry the named identity
stanza:

```
identity {
  name        = "vault_default"
  aud         = ["vault.io"]
  file        = true
  change_mode = "restart"
}
```

Named, not bare. Matches the ticket's Q5 resolution exactly. The probe
path `secret/data/default/wi-test/probe` (job `wi-test` in the `default`
namespace) falls under the existing `secret/data/<namespace>/<job_id>/*`
grant at policy lines 1-2. No policy widening needed. `nomad fmt -check`
passes (exit 0). No hardcoded credentials: the job reads from Vault through
its `template` block and prints the WI JWT to stdout.

## Convention accuracy

- One-token rule: stated at doc lines 109-117, correctly explains that
  naming a role REPLACES `nomad-workloads`, so a job needing both must list
  both policies. Consistent with `acme.tf:87`.
- Audience-per-verifier: stated at doc lines 155-166, correctly says `aud`
  identifies the verifier not the client job, per-job distinction comes
  from `nomad_job_id`. Consistent with the ticket's Q2 resolution.
- File-vs-env: stated at doc lines 168-174, correctly says env is the
  default for Vault-templated secrets, file for raw-JWT consumers.
- F10 owns OIDC discovery: stated at doc lines 176-191, correctly says F1
  delivers JWKS only, discovery is disabled, F10 owns enabling it.

## Repo rule compliance

- Plain language: zero em-dashes, zero double-dashes, no tier-1 slop
  terms, no British spellings, no identity leaks, no stubs/TODOs.
- Surgical changes: only two new files, no refactoring of existing code.
- Secrets only in Vault: no hardcoded credentials in the test job.
- HCL formatted: `nomad fmt -check` passes.
- All pre-commit gates green (`just pre_commit`): check-json, check-ast,
  check-merge-conflict, check-yaml, debug-statements, detect-private-key,
  end-of-file-fixer, nomad-fmt, terraform-fmt, terraform-validate, ruff
  lint, ruff format, mypy strict, pytest. 14/14 passed.

## Hallucination check

Every cited file path in the doc resolves to a real file: `nomad.hcl.j2`,
`vault_nomad_workloads.hcl.j2`, `vault_role_nomad_workloads.json`,
`tasks/main.yml`, `acme.tf`, `acme.hcl`. The JWKS URL
`http://192.168.2.30:4646/.well-known/jwks.json` is real and confirmed
against `docs/haproxy_reverse_proxy.md:18`. No fabricated paths, URLs, or
identifiers.

## Findings

### Non-blocking (low confidence, style only)

1. **Semicolon splices in prose** (severity: low, does not block merge).
   Six semicolons join independent clauses in prose outside code blocks:
   doc lines 81, 137, 150, 158, 186, 197-198. The slop scanner flags these
   as low confidence and says to surface, not auto-rewrite. They read
   naturally in each case and none create ambiguity. Examples:
   - line 81: `would ship a false claim; the doc records`
   - line 150: `Do not add it here; M1 owns its own.`
   These are surface-polish items, not correctness defects. The doc is
   clean on every P0 and structural layer.

## Verdict

PASS. No blocking findings. The doc describes the post-F9 policy and trust
chain accurately, the test job is correct and scoped, the diff is surgical
and additive-only, all gates are green, and the tree fingerprint binds
cleanly.