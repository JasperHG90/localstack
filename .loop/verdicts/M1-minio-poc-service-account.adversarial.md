---
verdict: pass
tree: d0da4bd6a9c388d2b18e2d70f897559d8faf45d1
---

# Adversarial review, cycle 3 (final) — M1-minio-poc-service-account

Both cycle-2 blocking findings are fixed on the evidence, not on the
hand-off summary. Three advisories remain; none of them blocks a commit.

## Scope binding

No scope digest was supplied in this briefing, and `.loop/config.json`
declares no `verdict_binding_inputs`. Rather than write a digest I computed
for a set I chose myself, this verdict omits `bound_paths` / `scope` /
`citations` and falls back to the whole-tree binding, which is stricter.

I recomputed the tree fingerprint independently, in a throwaway index
outside the repo (`git add -A .`, `git rm -r --cached .loop`, re-add
`.loop/config.json`, `git write-tree`, per `stamp.py:226-300`). It is
`d0da4bd6a9c388d2b18e2d70f897559d8faf45d1`, exactly the fingerprint I was
briefed with. The tree I reviewed is the tree this verdict authorizes.

## Deterministic floor

`loopctl verify-eval-substance M1-minio-poc-service-account` returns
`valid`: no hard-fail, and no advisory either. No comment-only grep scorer,
no stale `depends_on`, no amendment that dropped a still-required check, no
empty `Fails-when`, no positional row citation, no plan-drift, no
`assessed-statically-not-executed` row. Proceeded to the semantic pass.

## Gate, re-run independently

`just pre_commit` from the worktree root: exit 0, all 18 hooks pass,
including `Nomad Format`, `Terraform Format` and `Terraform Validate (per
root)`. The cycle-2 trust stamp was keyed on `9307c88f...`, which is not
this cycle's fingerprint, so I re-ran rather than trusted it, and rewrote
`.loop/scratch/M1-minio-poc-service-account.adversarial/trust-stamp.json`
against `d0da4bd6...`.

## Method note on the MinIO evidence

Every claim below rests on the source of the exact pinned image,
`docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`
(`deployments/infrastructure/services/minio.hcl:123`). I re-fetched
`cmd/sts-handlers.go`, `cmd/iam.go`, `cmd/iam-store.go`,
`internal/config/identity/openid/openid.go`,
`internal/config/identity/openid/jwt.go` and `internal/config/config.go`
from that tag this cycle and sha1-matched them against the copies read in
cycle 2 (for example `sts-handlers.go` =
`04f398c7f84975b0b38f2b2960315e25e1b8545b`), so no finding leans on a
possibly-drifted local copy. Line numbers below are into those files.

---

## F1 — POC2's standing s3:* grant. RESOLVED (was blocking)

**Fix under review:** `deployments/infrastructure/services/minio.hcl:93` =
`MINIO_IDENTITY_OPENID_ROLE_POLICY_POC2="poc2-intentionally-undefined"`.

I attacked "a dangling policy name is inert" on four fronts. All four are
closed.

**1. It does not fail at load, and it does not get created.**
`iam.go:369-376` builds `rolesMap` with a bare `maps.Copy` from
`OpenIDConfig.GetRoleInfo()` and from the AuthN plugin, with no existence
check. Worth flagging for the next reader: upstream's own comment at
`openid.go:338-339` says "RolePolicy is validated by IAM System during its
initialization", and that comment is **stale** — no such validation exists
on this release. The repo comment at `minio.hcl:75-76` is right and
upstream's is wrong. Live confirmation: MinIO restarted and both targets
came back enabled (`mc idp openid ls` shows `NOMAD` with an empty RoleARN
and `POC2` at `arn:minio:iam:::role/mUb-r9Uvk5J8VRzv_DJhP17Dy0M`).
`iam-store.go:1588-1626` `MergePolicies` only *reads* missing names via
`loadPolicyDoc`; nothing anywhere creates a policy from a `role_policy`
value.

**2. It fails closed per request, before anything is minted.** With
`RoleArn` set to POC2's ARN, `sts-handlers.go:467-470` leaves `policyName`
empty, so the block at `553-569` re-resolves `p =
"poc2-intentionally-undefined"`, finds `globalIAMSys.CurrentPolicies(p) ==
""` at line 563, and returns `ErrSTSInvalidParameterValue` at line 566.
That is **before** `SetTempUser` at line 583, so the credential struct built
at line 515 is never registered in IAM and never reaches the caller.

**3. There is no claim-mode side door.** The unrecognized-ARN fallback at
`sts-handlers.go:419-438` only fires when `GetRolePolicy` errors; POC2's ARN
is in `rolesMap`, so it never fires. A request with no `RoleArn` resolves
through `DummyRoleARN`, which is the `NOMAD` provider
(`openid.go:379-387`), whose `ClientID` is `minio`; `jwt.go:190-217`
rejects a token whose `aud`/`azp` lacks it. So a workload that declares
`aud = ["minio-poc2"]` and nothing else gets credentials from **neither**
path.

**4. Even a hypothetically-minted credential is denied at the data plane.**
`iam.go:2306-2314` maps the `roleArn` claim back to the undefined name and
`iam.go:2346-2352` rejects on the empty merge ("expected policy missing
from the JWT claim ... rejecting the request").

**Live state matches the diff**, checked read-only against
`192.168.2.29:9000`: `mc admin config get identity_openid` shows
`CONFIG_URL_NOMAD`/`CLIENT_ID_NOMAD=minio`/`CLAIM_NAME_NOMAD=nomad_job_id`
and `CONFIG_URL_POC2`/`CLIENT_ID_POC2=minio-poc2`/
`ROLE_POLICY_POC2=poc2-intentionally-undefined`. `mc admin policy ls` has
21 policies and none is `poc2-intentionally-undefined`. POC2's live RoleARN
`mUb-r9Uvk5J8VRzv_DJhP17Dy0M` equals `base64url(sha1("minio-poc2"))`
computed independently, matching the derivation at `openid.go:355-364`, so
that ARN is the one carrying the undefined policy.

**On "better or worse than deleting the target".** Better. Eval row 7
requires two coexisting targets; deleting POC2 would fail the spec. The
residual hazard is narrow and named: the target becomes a grant again only
if someone creates a policy called `poc2-intentionally-undefined`, and both
`minio.hcl:74-79` and `docs/workload-identity.md:338-339` say in writing not
to. The old value was not hypothetical — `mc admin policy info
memex_read_write` is `s3:*` on `arn:aws:s3:::memex` and `memex/*`, so the
cycle-2 severity was right and the fix removes it entirely.

A tidier variant exists (point `role_policy` at a real, deliberately empty
deny-all policy, so there is no name left to squat). I am **not** requiring
it: it would add a Terraform resource the plan's teardown subticket 7 is
meant to leave clean, and the current form is safe on the evidence above.

## F2 — the doc stated the wrong failure mode. RESOLVED (was blocking)

`docs/workload-identity.md:312-316` now reads: "Without it the exchange
itself fails, before any credential is minted ... It does not hand back a
credential that is then denied, so a job that cannot get credentials at all
is the symptom of a missing policy."

Verified against `sts-handlers.go:476-493`. In claim mode, `policyName =
globalIAMSys.CurrentPolicies(policies)` (line 479); when that is empty the
handler writes the error and returns at line 490, which precedes
`auth.GetNewCredentialsWithMetadata` at line 515. So "the exchange fails
before any credential is minted" is exactly right, and the old
"succeeds-then-denies" reading is gone. Confirmed.

## Everything else I checked

- **Claim-mode convention, proven from the surviving artifacts.** Decoding
  both STS session tokens: `sts1` carries `roleArn =
  arn:minio:iam:::role/MHR2BeH2-q1dHO2yx5U9Mf-tP9Q`, which equals
  `base64url(sha1("minio"))`, so phase one ran through `NOMAD` in
  role-policy mode. `sts2` carries no `roleArn` and `nomad_job_id=m1-poc`,
  which by `sts-handlers.go:487-491` was impossible unless a policy named
  `m1-poc` existed at that instant. Both share `jti`/`iat`/`exp`, so both
  phases ran against one identity, in order. That independently proves the
  policy-name-equals-job-id convention (plan R4) without the deleted job.
- **Eval row 5** (model + rubric, 4/5): **4/5, passes.** The two-phase
  sequence is proven as above. The two read legs (`mc ls sts/memex` exit 0,
  `mc ls sts/loki` `AccessDenied`) remain operator-report only and are not
  re-runnable now the job is gone. That is the one point off.
- **Eval row 7** (model + rubric, 4/5): **5/5, passes.** Two named targets
  coexist on the same real discovery document under distinct client ids,
  and the document is live (`curl` returns `issuer` plus `jwks_uri`). The
  targets both loading is itself the proof that `NOMAD` still works, since
  `LookupConfig` is all-or-nothing (`openid.go:294-298` returns on any
  `parseDiscoveryDoc` error).
- **Teardown is real.** No `m1-poc` anywhere under `deployments/`, no
  `minio_iam_policy` in `storage.tf`, no `m1-poc` policy on the live server.
- **`services.tf:382-388`** cites
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` as the source of
  truth for the issuer. Verified: that file line 42 is `oidc_issuer = "{{
  nomad_oidc_issuer }}"` and
  `bootstrap/playbooks/configure_hashistack_server.yml:45` sets it to
  `https://nomad.lab.orangecluster.nl`. The URL in the diff matches.
- **Every factual claim in the `minio.hcl:32-82` comment block checks out.**
  `getEnvVarName` (`config.go:1157-1164`) uppercases only the subsystem and
  the param and appends the target **verbatim**, so `_NOMAD` yields `NOMAD`
  — the cited function names are real and the claim is right, and live
  `mc idp openid ls` agrees. `jwks_url` is in `deprecatedKeys`
  (`openid.go:218`). `Validate` checks `aud` unconditionally
  (`jwt.go:190-217`). `errSingleProvider` (`openid.go:148`, raised at 385)
  refuses a second claim-mode target. Nomad WI JWTs do carry
  `nomad_job_id`, per the decoded tokens.
- **Style gates the repo freezes.** One em dash in the whole doc, no
  tier-1 slop terms, no ` -- ` prose, no British spellings, no over-80
  prose lines (the three long lines are inside fenced code blocks).
- **Scope.** Every changed line traces to the ticket. `services.tf` is
  named in plan section 7; `minio.hcl` is R1 and subtickets 2/5/6;
  `docs/workload-identity.md` records the R4 convention. `.loop/*` is
  harness bookkeeping and is stripped from the fingerprint.

## Advisories (non-blocking; no fix required to commit)

- **A1 — the safety property is conditional, and unstated.** Both
  policy-existence checks sit behind `if newGlobalAuthZPluginFn() == nil`
  (`sts-handlers.go:482` and `561`). Setting `MINIO_POLICY_PLUGIN_URL`
  would skip them and mint a credential for any `aud=minio-poc2` token. It
  does not apply today: `mc admin config get policy_plugin` shows `url=`
  empty, `identity_plugin` likewise, and even then `iam.go:2346-2352`
  denies at the data plane. One clause in the `minio.hcl:70-79` comment
  would close it.
- **A2 — `docs/workload-identity.md:314` quotes a message MinIO never emits
  verbatim.** The literal is ``None of the given policies (`%s`) are
  defined, credentials will not be generated`` (`sts-handlers.go:489` and
  `565`). The doc elides the parenthetical and the tail, so an operator
  grepping the backticked phrase gets no hit. I checked this against the
  call path rather than the diff, because no gate asserts the string and it
  is the first of its kind in the repo. The substance is right; only the
  quotation is short.
- **A3 — `docs/workload-identity.md:219` cites rows by position** ("The
  last two rows share a verifier"). Naming `minio` and `minio-poc2`
  survives a future row; the positional phrasing does not. Cosmetic.

## Prior findings the diff does not touch

- `M1-A-05` — no change in scope, still holds: plan R2 at
  `.loop/plans/M1-minio-poc-service-account.md:149` still says `change_mode
  = "restart"` while `docs/workload-identity.md:298-310`, which plan P3
  names as the authority, says `noop` with a pinned `filepath` and `ttl`.
  The implementation followed the doc, which matches the standing
  convention at `docs:180-188` and the only live precedent
  (`hermes.hcl:412-419`), so the contradiction survives only in a closed
  plan whose POC job is deleted. Advisory.

## On `justfile:47` — keep it

Asked directly, so answered directly. Re-attacked and re-confirmed my
cycle-2 correction: `terraform validate` reads no tfvars and
`scripts/tf_validate.sh` passes no `-var-file`, so `just pre_commit` is
green without this line. It is still the right line to keep. It mirrors
`justfile:46` exactly for the applications root; the source is gitignored
(`.gitignore:12`, `**/vars/prod.tfvars`) and the destination directory
exists in a fresh worktree because `backend-config.hcl` and
`prod.tfvars.example` are tracked, so the copy works. What it unblocks is
`terraform plan`/`apply` against `deployments/applications` from a
worktree, which subtickets 4, 5 and 7 all required. Plan section 8 already
describes `worktree_setup` as copying `prod.tfvars`; this makes the recipe
match its own documentation. Not speculative, and one line.

## Verdict

`pass`. The two blocking findings are closed on independent evidence, the
gate is green on this exact tree, both model-scored eval rows clear their
4/5 threshold, and no changed line falls outside the ticket. The three
advisories are cheap follow-ups, not commit blockers.
