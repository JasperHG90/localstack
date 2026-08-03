---
verdict: pass-with-required-fixes
plan: c7a37832836d45b5aabc0810fd7d7fb2b6f323b1b0ddce5bcdb80d14e095f9a1
---

# Premise verdict: SOUND

This is a fresh, from-scratch adversarial pass against the CURRENT plan file
and CURRENT live/repo state, not a re-read of the prior verdict's
conclusions. Every one of the eight items the two prior rounds found and the
plan claims to have fixed was independently re-attacked against primary
sources (live cluster probes, actual file line numbers, MinIO's own upstream
Go source at the pinned release tag), exactly as if this plan had never been
reviewed. All eight hold. The overwritten prior verdict on this file (Round
2, `verdict: fail`, premise PARTIALLY SOUND) found six defects (P6-P11
below, in that verdict's numbering); all six are now genuinely fixed, not
just claimed fixed.

## Deterministic floor

`loopctl verify-plan M1-minio-poc-service-account` (re-run fresh this pass,
backgrounded, output captured):

    valid: warn: ambiguous file basename 'services.tf' (matches several
    files); warn: ambiguous file basename 'services.tf' (matches several
    files); warn: ambiguous file basename 'services.tf' (matches several
    files)

Clean: only the harmless ambiguous-basename warning, no errors. Proceeded to
the deep pass.

## Per-assumption findings (the plan's own P1-P5, plus two I added)

- **P1 — Nomad now serves a real, concrete OIDC discovery document (F10
  applied). HOLDS.** `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42`
  (`oidc_issuer = "{{ nomad_oidc_issuer }}"`) and
  `bootstrap/playbooks/configure_hashistack_server.yml:45`
  (`nomad_oidc_issuer: "https://nomad.lab.orangecluster.nl"`) both confirmed
  verbatim. Live probe, run fresh this pass: `curl -sk
  https://nomad.lab.orangecluster.nl/.well-known/openid-configuration` →
  HTTP 200, `"issuer":"https://nomad.lab.orangecluster.nl"`,
  `"jwks_uri":"https://nomad.lab.orangecluster.nl/.well-known/jwks.json"`.

- **P2 — MinIO's deployed release accepts only `config_url`, never
  `jwks_url`. HOLDS, confirmed against primary source, not just a live
  probe.** Fetched `internal/config/identity/openid/openid.go` at tag
  `RELEASE.2025-09-07T16-13-09Z` (the exact pin at `minio.hcl:66`) from
  GitHub. Lines 67-69: `// Removed params` / `JwksURL = "jwks_url"` /
  `ClaimPrefix = "claim_prefix"`. `LookupConfig` builds `deprecatedKeys :=
  []string{JwksURL}` and deletes any `jwks_url` key from every target's KVS
  before validating. Independently re-confirmed live against
  `192.168.2.29:9000` with the Vault-held root creds
  (`secret/default/minio/localstack`): `mc admin config get <alias>
  identity_openid` lists `config_url`, `client_id`, `claim_name`,
  `role_policy`, etc., and no `jwks_url` key anywhere.

- **P3 — The consumer job's `identity` block must be NAMED, with `file =
  true`, to land a JWT on disk. HOLDS.** `docs/workload-identity.md:132-153`
  re-read verbatim: "An **unnamed** `identity {}` configures the task's
  default Nomad-API identity, not the Vault one. It does not retarget
  Vault, it does not write a JWT to disk... Only the named form lands a JWT
  on disk." R2's block (`name = "minio"`, `aud = ["minio"]`, `file = true`,
  `change_mode = "restart"`) matches this doc's own worked pattern
  (substituting the MinIO audience for the doc's `vault.io` example),
  consistent with the doc's own guidance on adding a distinct audience per
  new verifying-service class (lines 155-164).

- **P4 — The deployed MinIO release still supports OIDC/STS. HOLDS,
  re-verified live today, independent of the plan's cited 2026-07-26
  probe.** `mc admin config get <alias>` lists `identity_openid enable
  OpenID SSO support` in the config subsystem. An unauthenticated
  `AssumeRoleWithWebIdentity` POST (`curl -X POST
  "http://192.168.2.29:9000/?Action=AssumeRoleWithWebIdentity&WebIdentityToken=junk&RoleArn=arn:minio:iam:::role/dummy-internal&Version=2011-06-15"`)
  returns `InvalidParameterValue: ... RoleARN ... is not defined` — a live,
  role-aware handler, not a 404/removed-feature response.

- **P5 — F1, F10, and A1 are all `done`. HOLDS.** `.loop/ledger.json`:
  `F1-foundation-nomad-wi-jwt-trust` → `done`,
  `F10-foundation-nomad-oidc-issuer` → `done`,
  `A1-audit-plan-premise-sweep` → `done`. M1 itself is `blocked`
  (`unresolved-design-fork`, pointing at the prior version of this verdict
  file), which is exactly the state this review decides whether to lift.

- **P6 (added; this is the prior verdict's P6, "provider name case").
  HOLDS — genuinely fixed.** Fetched `internal/config/config.go` at the
  same tag. `getEnvVarName` builds the env var as `EnvPrefix +
  ToUpper(subSys) + Default + ToUpper(param) + Default + target` — `target`
  is appended **verbatim, never upper-cased**. `GetAvailableTargets`
  recovers the target name via `strings.TrimPrefix(k, envVarPrefix)` against
  the literal env var string found via `env.List(...)`, again with no
  case-folding anywhere in the round trip. `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD`
  therefore names the target `NOMAD`, exactly as R1, the code surface,
  subticket 2, and E1 now all assert. This was the single most dangerous
  "how does MinIO actually behave" claim in the plan and it is now both
  correctly stated everywhere in the plan text AND confirmed against
  primary source, not just plausible.

- **P7 (added; the prior verdict's P7, "multi-IdP placeholder abort").
  HOLDS — genuinely fixed.** Same `openid.go`: the `for _, cfgName := range
  openIDTargets` loop calls `parseDiscoveryDoc`, and on error `return c,
  err` immediately — the whole `LookupConfig` call returns, discarding every
  target processed in this call, confirming a parse failure on any one
  target genuinely aborts the entire config load (the plan's risk claim is
  accurate, not exaggerated). E7, subticket 6, the eval file's last row, and
  a dedicated risk-assessment bullet now all require the second target to
  point at a real, reachable discovery document, never a placeholder.
  Separately: the loop's own duplicate check is on `ClientID`
  (`seenClientIDs.Contains(p.ClientID)`), not on URL, so pointing two
  targets at the SAME discovery URL under different `client_id` values (the
  plan's chosen fix) hits no duplicate-URL error — this is the mechanism
  MinIO expects for multi-target config, not a workaround.

## Formerly-broken items re-verified as now fixed (prior verdict's P8-P11)

- **Worktree precondition (prior P8). Fixed and confirmed.** Section 8 now
  states: "Precondition if run in a fresh git worktree... Run `just
  worktree_setup <path>` (`justfile:40-42`) first." Re-checked live:
  `deployments/infrastructure/services.tf:290` does call
  `file("${path.root}/../../.ssh/id_rsa")` inside the `firewall_rules`
  provisioner, evaluated statically by `terraform validate`; `justfile:41-43`
  (one line off from the plan's cited `40-42`, see below) is exactly the
  `worktree_setup path:` recipe that symlinks `.ssh` and copies
  `prod.tfvars`. The precondition is real and now documented.

- **Q3-vs-subticket-4 contradiction (prior P9). Fixed and confirmed.** R5,
  the code-surface item, subticket 4, and Q3 itself now all say
  `storage.tf`-local, consistently, with the shared
  `deployments/applications/modules/bucket/` module left untouched. Read
  `deployments/applications/modules/bucket/outputs.tf`: 0 bytes — the
  module exports nothing, confirming the plan's claim that
  `minio_s3_bucket.bucket` genuinely is not addressable from `storage.tf`,
  so the plain-string bucket-name scoping in R5 is the only workable
  approach, not a stylistic pick. No remaining contradiction anywhere in the
  plan text.

- **Q5 dead branch (prior P10). Fixed and confirmed.** Fetched
  `internal/config/identity/openid/jwt.go`'s `Validate` and its caller in
  `cmd/sts-handlers.go:448`
  (`globalIAMSys.OpenIDConfig.Validate(r.Context(), roleArn, token,
  accessToken, ...)`) — called unconditionally, **before** the
  `if isRolePolicyProvider` branch (line 467) that splits role-policy from
  claim mode. `Validate` checks `aud` (falling back to `azp`) against
  `pCfg.ClientID` in every mode. Q5 now states this as resolved with no
  conditional branch, matching the source exactly.

- **Drifted `services.tf` anchors (prior P11). Fixed and confirmed at their
  current, correct positions.**
  `deployments/infrastructure/services.tf:306-311` is genuinely the `minio`
  job's `templatefile(...)` call with `minio_secret` — read directly, lines
  305-311 are `### Minio` / `resource "nomad_job" "minio" { jobspec =
  templatefile(...) { minio_secret = ... } }`, matching the plan's citation
  exactly (not 301-305 as the prior verdict found stale).
  `deployments/applications/services.tf:159-179` is genuinely the `memex`
  job (`resource "nomad_job" "memex"` opens at line 159, closes at 179 with
  its `depends_on`) — matches exactly (not 147-163). Both anchors now
  resolve to the resources the plan claims.

## New findings this pass (not in either prior round)

Checked specifically for dangling cross-references or new drift the two fix
rounds might have introduced, per the brief.

1. **`depends_on` front matter omits `F10-foundation-nomad-oidc-issuer`.**
   The plan's own P5 and Q1 treat F10 as a hard prerequisite ("F1 delivers
   JWKS only and does NOT enable discovery; F10 is the owner... Once F10 is
   `done`, M1's `config_url` is this concrete value"), and the create-ticket
   contract states `depends_on` "names tickets that must reach `done`
   before this one may be picked up... so name only real prerequisites"
   (`skills/create-ticket/SKILL.md:68-73`). F10 is a real prerequisite by
   the plan's own account, yet `depends_on = ["F1-foundation-nomad-wi-jwt-trust",
   "A1-audit-plan-premise-sweep"]` never lists it. F10 is `done` today so
   this has no live blocking effect, but the front matter is inconsistent
   with the plan's own stated dependency structure.

2. **Eval marker drift.** `.loop/evals/M1-minio-poc-service-account.md:8`,
   the Definition-of-Done prose, still reads "...with the `nomad` OIDC
   provider coexisting with a second named IdP..." (lowercase), while every
   scored table row in the same file (row 1, row 7) and the plan text
   throughout correctly say `NOMAD`. This is the exact class of drift the
   second fix round closed everywhere else, missed in this one summary
   sentence. Harmless to the scored checks themselves (the table rows are
   already correct), but a real, easily-found leftover.

Neither finding touches a load-bearing assumption or a scored eval row; both
are one-line, mechanical fixes.

## Minor citation drift (not a required fix, noted for completeness)

`justfile` line citations are off by one in two places: `worktree_setup` is
cited as `justfile:40-42` but the recipe (comment, `worktree_setup path:`,
both body lines) actually spans `justfile:40-43`; `just pre_commit` is
cited as "line 17-18" but the comment is line 17, `pre_commit:` is line 18,
and the actual command (`pre-commit run --all-files`) is line 19. Neither
changes the substance of the precondition or the gate command; not required
to fix.

## Most dangerous assumption

**P6 (uppercase target-name derivation).** If MinIO folded case anywhere in
the env-var-to-target-name round trip, every downstream claim (R1, the code
surface, subticket 2, E1, and the eval marker) would name the wrong provider
and E1 would fail on a correctly-implemented ticket. Read the actual
`config.go` at the pinned release tag directly: no case-folding exists in
`getEnvVarName` or `GetAvailableTargets`. This is now the most solidly
source-confirmed premise in the plan, not its weakest link — the fix from
the second round holds under direct scrutiny of MinIO's own code, not just
a live `mc admin config get` snapshot.

## Contract hygiene

- Non-goals remain explicit (human path, existing-consumer migration,
  Zitadel, production rollout, F1 changes) — clean.
- Tests are homed: the eval file exists (`require_eval` satisfied) and each
  E1-E7 row maps to a ticket eval row; all seven rows present and internally
  consistent except the one prose drift noted above.
- Open Questions (Q1-Q6) carry recommendations; Q3 and Q5 are explicitly
  marked resolved and are consistent with the rest of the plan (the prior
  contradiction on Q3 and the dead branch on Q5 are both gone).
- Gates section names the real repo gate (`just pre_commit`,
  `.pre-commit-config.yaml` hooks confirmed at `:16-21`/`:22-27`/`:28-33`,
  `scripts/tf_validate.sh` confirmed to validate all three named roots
  offline) and now states the worktree precondition.

## Verdict rationale

Premise: **SOUND.** All five of the plan's own stated premises hold under
independent re-verification, and the two implicit assumptions most load-
bearing to the "how does MinIO actually behave" claims (case-sensitive
target naming; the all-or-nothing config-load abort) both hold against
MinIO's own upstream source at the exact pinned release tag — not merely
against the plan's paraphrase of an earlier probe. All six defects the prior
(Round 2) verdict found are genuinely fixed, independently reconfirmed here,
not just claimed fixed. Code-surface anchors for both `services.tf` files,
`minio.hcl`, `storage.tf`, `modules/bucket/main.tf`, and
`docs/workload-identity.md` all resolve to what the plan claims. Two small,
mechanical contract-hygiene items remain (a missing `depends_on` entry; one
stale lowercase reference in the eval marker's summary prose) plus two
harmless one-line-off `justfile` citations. None of these touch the
premise or any scored eval row.

**Gate verdict: `pass-with-required-fixes`.** Required fixes before
implementation:
1. Add `F10-foundation-nomad-oidc-issuer` to the plan's `depends_on` front
   matter, matching the hard prerequisite the plan's own P5/Q1 already
   describe.
2. Fix `.loop/evals/M1-minio-poc-service-account.md:8` to say `NOMAD`
   instead of `nomad`, matching every scored row in the same file.

## Method note

All cluster interaction this pass was read-only: unauthenticated/read-only
`curl` GETs against Nomad's public discovery endpoint, a Vault KV2 read of
the MinIO root credentials already referenced by the plan's own Context
section, `mc admin config get` (read-only) against the live MinIO server
with those credentials, an unauthenticated `curl` POST against MinIO's STS
endpoint with a junk token and a non-existent role ARN, plus outbound
`curl` reads of MinIO's own public GitHub source at the exact pinned
release tag. No `vault write`, no `nomad job run/stop`, no `terraform
apply`, no mutating git command.
