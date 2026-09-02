---
verdict: pass
tree: d0da4bd6a9c388d2b18e2d70f897559d8faf45d1
---

# Documentation freshness — M1-minio-poc-service-account, cycle 3 (final)

No scope-binding lines: this briefing carried a tree fingerprint but no
64-hex scope digest, and the rule is to write only the digest I was given.
The verdict therefore falls back to the whole-tree binding, which is
stricter.

Reviewed paths (the full diff against HEAD): `docs/workload-identity.md`,
`deployments/infrastructure/services/minio.hcl`,
`deployments/infrastructure/services.tf`, `justfile`,
`.loop/plans/M1-minio-poc-service-account.md`,
`.loop/evals/M1-minio-poc-service-account.md`, `.loop/ledger.json`.

## Verdict

Pass. Every documented surface this change touches was updated in step, and
the three cycle-2 required fixes are genuinely fixed rather than reworded. I
re-opened each anchor, re-derived the MinIO behavior claims from upstream
source at the pinned release rather than trusting the hand-off note, and
found no new contradiction. Five findings remain, all advisory: none of them
would lead a reader to do the wrong thing, and none blocks the commit.

## Cycle-2 required fixes, re-attacked

**Fix 1 (D8, was medium) — closed.** The audience rule and its exception now
sit together. `docs/workload-identity.md:219` = "The last two rows share a
verifier, which the rule above forbids. They are" and `:220` = "the
documented exception, not a precedent: MinIO refuses more than one", with
the registry rows naming their targets at `:216-217` (`:217` = "| `minio-poc2` |
MinIO STS, `POC2` target | M1, replace in the human ticket |"). A reader who
stops at the rule no longer sees a table that silently breaks it. See D13
for the one precision point I split out.

**Fix 2 (D7, was minor) — closed.** `grep MINIO_ENDPOINT` over `docs/` and
`deployments/` returns nothing. The curl at `:322` and the `mc` example at
`:331` both use `http://<minio>:9000`, matching the recorded eval rows.

**Fix 3 (D9, was minor) — closed, and the security claim is accurate, not
reassuring.** `deployments/infrastructure/services/minio.hcl:93` =
`MINIO_IDENTITY_OPENID_ROLE_POLICY_POC2="poc2-intentionally-undefined"`, and
`docs/workload-identity.md:338` = "Its `role_policy` names
`poc2-intentionally-undefined`, a policy that does". No policy of that name
is defined anywhere in the tree (`minio_iam_policy` resources exist only at
`deployments/applications/modules/bucket/main.tf:11,29`, emitting
`<name>_read_write` / `<name>_read_only`), so `memex_read_write` survives
only as the historical clause at `minio.hcl:78`. I verified the mechanism
in the pinned release rather than accepting it: in
`cmd/sts-handlers.go` the role-policy branch resolves the ARN's policy and
returns `ErrSTSInvalidParameterValue` when `CurrentPolicies(p) == ""`,
before the `SetTempUser` call that would mint anything. `internal/config/
identity/openid/openid.go:337-339` ("RolePolicy is validated by IAM System
during its initialization") confirms load time does not check existence. So
`docs/workload-identity.md:342` = "audience. Pointing at nothing costs
nothing at startup and fails per" is literally true in both halves.

**Fix 4 (prerequisites failure mode) — correct.** `cmd/sts-handlers.go`
claim-mode branch: `policyName = globalIAMSys.CurrentPolicies(policies)`,
then `else if policyName == ""` writes the error and returns, ahead of any
credential generation. The doc's substance at `:312-316` is right; only the
quoted string is loose, see D12.

## Findings (all advisory, none blocking)

**D12 — minor. The quoted error string is not what MinIO emits.**
`docs/workload-identity.md:314` = "   credential is minted, with `None of
the given policies are defined`. It". The real message interpolates the
policy name in the middle: `None of the given policies (`m1-poc`) are
defined, credentials will not be generated`. An operator grepping alloc logs
for the doc's literal gets no hit. Two-word fix if you want it; the claim it
supports is verified correct.

**D13 — nit. The exception's stated cause is stronger than the code.**
`:220-223` says MinIO's one-claim-mode rule forces the second target to
carry its own client id. `openid.go` keys a role-policy provider by
`base64url(sha1(client_id))` and a claim-mode provider by `DummyRoleARN`,
and rejects only a second `DummyRoleARN` (`errSingleProvider`); nothing
rejects two targets sharing a client id. The distinct client id is a sound
disambiguation choice, not a MinIO requirement. The rule the paragraph
exists to state is unaffected.

**D14 — nit. "two IdPs" at `:337`** = "id, and proves MinIO can hold two
IdPs at once for the human-access work." Both targets point at one issuer.
The same sentence already says "on the same discovery document under a
different client id", so the doc self-corrects in place, and the eval marker
uses the same phrasing.

**D6 — nit, carried. Two semicolon splices on diff-added lines.**
`:207` = "  (for example `minio` for MinIO STS). M1 has since added that
one; see" and `:241` = "and nothing more. Its scope was JWKS only; it did
not deliver an OIDC". Both join independent clauses. Low confidence per the
repo rule, and `.pre-commit-config.yaml` has no markdown hook, so nothing
enforces it.

**D10 — nit, partly carried. Ragged wrap moved.** The "sits beside" spatial
copula is gone (`:335` now reads "is configured"). `:350` = "WHOLE OIDC
config load, every provider, if any" is 46 columns mid-paragraph. Cosmetic.

**D5 — advisory, carried.** Step 2 at `:312` = "2. A `minio_iam_policy`
exists whose `name` is exactly the job id, scoped to" still does not name
the file, while `minio.hcl:49-50` names `storage.tf`.

## Absence claims (settled findings the diff does not touch)

- D1 — no change in scope, still holds: no present-tense claim that MinIO
  reads Nomad's bare JWKS survives; `openid.go:218` lists `jwks_url` as a
  deprecated key, as the doc says.
- D2 — no change in scope, still holds: `:275` =
  `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD=https://nomad.lab.orangecluster.nl/.well-known/openid-configuration`
  equals `deployments/infrastructure/services.tf:388` after substitution,
  which equals `bootstrap/playbooks/configure_hashistack_server.yml:45` plus
  the well-known path.
- D3 — no change in scope, still holds: registry row and claim-mode
  ownership both present.
- D4 — no change in scope, still holds: no capability claim about Nomad JWTs
  contradicts the fixed-claims section.
- D11 — no change in scope, still holds: `docs/vault-human-auth.md:462` is
  not falsified, because the human target must use `role_policy` while NOMAD
  holds the single claim-mode slot. The replace-do-not-add instruction lives
  at `docs/workload-identity.md:344` = "wires Vault in should REPLACE it
  rather than add a third target." and `minio.hcl:81`, which is the right
  home for it.

## Checks that came back clean

- Doc and `minio.hcl`'s comment agree on all eight behavior claims they both
  make, in both directions.
- Every MinIO behavior claim re-derived from `RELEASE.2025-09-07T16-13-09Z`
  sources: deprecated `jwks_url`, `aud` checked in both modes, one claim-mode
  provider, whole-config abort on one bad discovery document, role policy
  unchecked at load, missing policy fails before minting, target name not
  case-folded, 1h default expiry.
- Every backticked identifier, path, env var and command in the changed
  regions resolves in this tree.
- Slop scan over all 109 added doc lines: no em dash, no ` -- `, no smart
  quote, no tier-1 slop, no self-narration, no British spelling, no tier-5
  spatial copula, significance cluster, throat-clear, three-fragment burst,
  participial tail or emphasis crutch. The only over-80 line is inside a
  fence.
- No other repo doc is stale. `README.md:53,58` still describes copying both
  `prod.tfvars.example` files by hand, which stays true beside the new
  `justfile:47`; no doc documents the `worktree_setup` recipe body.
- The gate was not re-run (out of scope here); `.loop/stamp.json` records
  `just pre_commit` exit 0 against this same fingerprint.
