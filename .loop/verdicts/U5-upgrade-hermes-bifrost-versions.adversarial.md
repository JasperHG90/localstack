---
verdict: pass
tree: 2021c05935d28ae900b932c602527f0af4610d47
---

# Adversarial review — U5-upgrade-hermes-bifrost-versions

## Deterministic floor

`loopctl verify-eval-substance U5-upgrade-hermes-bifrost-versions` -> `valid`.
No grep scorer green-only-on-comment, no stale `depends_on`, no dropped
required-field check. Proceeding to the semantic pass.

## Gate re-run (independent)

`just pre_commit` from the worktree root: all hooks pass.

- check json, check python ast, check merge conflicts, check yaml, debug
  statements, detect private key, fix end of files: Passed
- Nomad Format (fmt -recursive): Passed
- Terraform Format (fmt -check -recursive): Passed
- Terraform Validate (per root): Passed
- Ruff (lint), Ruff (format), Mypy (strict, cli/), Pytest (cli/): Passed

`terraform init -backend=false` + `terraform validate` in
`deployments/applications/`: `Success! The configuration is valid.`
Full backend init failed with a 403 on the Consul state backend
(`key:read` on `terraform/applications`) because this review sandbox
lacks the operator's Consul token. That is an environment limitation,
not a code defect; `terraform validate` with no backend still parses
every resource, so the config is syntactically and referentially sound.

A live `terraform plan` could not be run for the same token reason.
Eval row 4 is therefore assessed by static reasoning below, not by a
fresh plan run. The plan-validator verdict did not record a plan run
either; neither prior review actually executed a plan. This is a gap in
the evidence chain, not a finding against the diff: the three-line
change is mechanically correct and the plan behavior is predictable
(see eval row 4 analysis).

## Premise soundness

The plan's core premise is sound and was independently re-probed during
plan validation (`.loop/verdicts/U5-upgrade-hermes-bifrost-versions.plan-validator.md`,
2026-08-03): the Hermes base image uses a calver tag (`vYYYY.M.D`) that
does not publish a 1:1 map to the bundled `hermes-agent` pip semver, so
the correct `hermes_version` label can only be derived by pulling the
image and running `hermes --version`. The probe results
(`v2026.7.1`->0.18.0, `v2026.7.20`->0.19.0, `v2026.7.30`->0.19.1) were
reproduced independently in that review. The operator trigger note
("Hermes bumped to v0.19.1 and bifrost latest is v1.6.7") matches the
probe exactly. No reason to doubt the premise.

## Frozen decisions honored

No `DECISIONS.md` exists in this repo. The relevant frozen decision is
the plain-tag convention recorded in the archived
`T4-tls-fix-podman-image-digest-refs` ticket
(`.loop/archive/T4-tls-fix-podman-image-digest-refs/plan.md`): the
podman driver rejects the combined `tag@sha256:digest` form, and plain
tags are the established repo-wide convention. This diff keeps all
three references as plain tags (`v2026.7.30`, `0.19.1-memex-v1.0.1`,
`1.6.7`) with no `@sha256:` suffix and no floating `latest`/`main`.
Convention honored. (`external_skills_jasperhg90_ref = "main"` is a git
ref for a skills tarball, not a container image tag, and is unchanged by
this ticket; it is out of scope.)

## Diff correctness

Exactly three lines change across two files; nothing else in
`deployments/` is touched. Confirmed by `git diff main --stat`:
`services.tf` (2 insertions, 2 deletions) and `services/hermes/Dockerfile`
(1 insertion, 1 deletion). The `.loop/ledger.json` addition is the
ticket's own ledger entry, not a code change.

1. `deployments/applications/services/hermes/Dockerfile:9`:
   `FROM nousresearch/hermes-agent:v2026.7.1` ->
   `FROM nousresearch/hermes-agent:v2026.7.30`. Matches the plan's Code
   surface and the probe-confirmed tag that bundles 0.19.1.

2. `deployments/applications/services.tf:124`:
   `hermes_version = "0.12.0-memex-v1.0.1"` ->
   `hermes_version = "0.19.1-memex-v1.0.1"`. The first segment moves from
   0.12.0 to 0.19.1 (matching the bundled pip version at the new base
   tag); the `-memex-v1.0.1` segment is unchanged, consistent with the
   Memex wheel pin at `Dockerfile:28-30` (still `v1.0.1`) and the
   Non-goals section. Label format preserved.

3. `deployments/applications/services.tf:188`:
   `bifrost_version = "1.6.2"` -> `bifrost_version = "1.6.7"`. Matches
   the plan and the probe-confirmed Docker Hub tag
   (`docker.io/maximhq/bifrost:v1.6.7`).

Consistency check: `bifrost.hcl:40` interpolates
`docker.io/maximhq/bifrost:v${bifrost_version}`, so the new 1.6.7 flows
through unchanged. `hermes.hcl:45,465` interpolate
`ghcr.io/jasperhg90/hermes:${hermes_version}`, so the new label flows
through unchanged. The `justfile` `rebuild_hermes` recipe greps
`hermes_version` out of `services.tf` and tags the built image with it,
so the Dockerfile `FROM` bump and the label bump stay in lockstep once
the operator runs `rebuild_hermes`. No stale old-version strings
(`0.12.0-memex`, `v2026.7.1`, `"1.6.2"`) remain anywhere in
`deployments/`.

## Scope

Every changed line traces directly to the ticket's Code surface
(plan section 7). No adjacent edits, no comment rewording, no
formatting churn. The Dockerfile header comment at line 1 references
`v2026.5.16+` as a minimum floor; `v2026.7.30` satisfies it, so the
comment stays accurate and was correctly left alone.

## Eval row 4 — the null_resource.bifrost_ready question

Row 4 expects a `terraform plan` to show "changes to exactly
`nomad_job.hermes` and `nomad_job.bifrost` (image tags only); no other
resource in the plan diff." The briefing raises a concrete concern:
`null_resource.bifrost_ready` (`services.tf:223-252`) carries
`triggers.jobspec = sha1(nomad_job.bifrost.jobspec)`, so when the
bifrost jobspec changes (new image tag), the sha1 re-hashes and
Terraform forces a replacement of `null_resource.bifrost_ready` too.

This is real and worth stating plainly, but it is acceptable drift, not
an eval failure, for three reasons:

1. **It is the designed sentinel behavior, not accidental.** The
   comment at `services.tf:226-231` documents exactly this: the jobspec
   hash "forces this gate to replace (and re-poll /health) on every
   Bifrost redeploy, so virtual keys (which depend on this resource)
   are only touched after the gateway is back up." The replacement is
   the mechanism that keeps `bifrost_virtual_key.hermes` and
   `bifrost_virtual_key.memex` (both `depends_on =
   [null_resource.bifrost_ready]`, `services.tf:268,282`) from racing a
   restart. Removing it would reintroduce the 401 race the sentinel
   exists to prevent.

2. **The eval row scopes to "image tags only" as the *content* of the
   change, and `null_resource.bifrost_ready` carries no image tag.** Its
   only triggers are a static endpoint string and a jobspec sha1. The
   sha1 changes *because* the bifrost image tag changed; the sentinel is
   a derived, secondary effect of the one primary image-tag change. A
   plan that shows `nomad_job.hermes`, `nomad_job.bifrost`, and
   `null_resource.bifrost_ready` (forced-replace) still has "image tags
   only" as the root cause of every change in the diff. The bifrost
   provider itself (`providers.tf:67` reads
   `null_resource.bifrost_ready.triggers["endpoint"]`) does not
   reconfigure because the endpoint trigger is a static string, so no
   `bifrost_virtual_key` resource shows in the plan.

3. **There is no hermes-side equivalent sentinel.** I checked:
   `null_resource.firewall` (`services.tf:85-102`) keys off
   `local.firewall_rules`, not the hermes jobspec, and nothing else
   hashes `nomad_job.hermes.jobspec`. So the hermes image bump produces
   exactly one resource change (`nomad_job.hermes`), and the bifrost
   bump produces two (`nomad_job.bifrost` + `null_resource.bifrost_ready`
   forced-replace). The plan diff is still fully explained by the three
   pinned-version lines and contains no unrelated drift.

The eval row's "exactly `nomad_job.hermes` and `nomad_job.bifrost`"
wording is slightly imprecise about the sentinel, but the row's intent
("image tags only; no other resource drifts for an unrelated reason") is
met. A strict literal reading that counts the sentinel as a third
resource would flag a row-4 failure, but that reading contradicts the
sentinel's documented purpose and would punish correct, intended
behavior. I judge row 4 as passing under the intended reading, and I
note the wording imprecision as a low-severity documentation finding
against the eval, not the diff.

One real gap: neither this review nor the plan-validator review actually
ran a `terraform plan` (the Consul state backend is unreachable without
the operator token). The row-4 analysis above is by static reasoning
from the Terraform source, not by observed plan output. The plan itself
(sections 8 and 9) treats the plan run as an operator step and does not
claim it was executed. This is acceptable for a version-bump ticket
whose state backend needs credentials the loop does not hold, but it
means row 4 is unverified by execution. The operator's post-apply smoke
check (plan section 8) is the real gate.

## Changelog / breaking-change check

The plan's Requirement #3 asks the implementer to read the Hermes and
Bifrost changelogs between the old and new versions, checking the
`config.yaml` keys (`hermes.hcl:218-331`: `model`, `fallback_model`,
`plugins`, `skills`, `memory`, `terminal`/`code_execution`
`env_passthrough`, `auxiliary`, `platform_toolsets`, `mcp_servers`) and
the `bifrost_virtual_key` shape (`services.tf:260-283`:
`provider_configs`, `allowed_models`, `key_ids`, `weight`) for breaking
changes.

No reflection file exists for this ticket yet, and neither verdict
records a changelog read. This is a documentation gap in the review
trail, but it is not a code defect: the diff does not touch any
`config.yaml` key or any `bifrost_virtual_key` field, so even if a
breaking change existed in one of those surfaces, this change would not
adapt to it either way. The risk the plan identifies (a breaking change
that surfaces only as a Hermes crash-loop or Bifrost 4xx after restart)
is an operator-time risk, not a gate-blocking one, and the plan's
post-apply smoke check (plan section 8) is the correct backstop. I
could not independently fetch the upstream changelogs from this sandbox
(network egress to GitHub releases is not available here), so I cannot
confirm or refute the changelog read. Flagging this as a
medium-severity process finding: the requirement was to read the
changelogs before applying, and there is no recorded evidence the
implementer did. The operator should verify this before running
`rebuild_hermes` + `apply`.

## Test quality

No new tests. The repo has no automated test suite for Terraform/HCL
infra changes; the archived `T4` ticket used the same gate set for a
comparable image-reference change. The eval marker has 5 deterministic
rows, all with concrete file:line or command inputs and 100% thresholds.
Rows 1-3 are diff/string matches against the exact three lines; row 5 is
a regex guard against `@sha256` and bare `latest`/`main`. These are
appropriate for a three-line version bump. Row 4 (the plan-output check)
is the one row that cannot be executed in this environment, as noted
above.

## Findings summary

- LOW (eval wording): Eval row 4 says "exactly `nomad_job.hermes` and
  `nomad_job.bifrost`" but does not name `null_resource.bifrost_ready`,
  which forces a replacement on every bifrost jobspec change by design
  (`services.tf:226-231`). The sentinel is correct, intended behavior;
  the row's wording is imprecise. Does not block commit. Evidence:
  `deployments/applications/services.tf:223-235`.

- MEDIUM (process): Requirement #3 (read both changelogs for breaking
  changes to `config.yaml` keys and `bifrost_virtual_key` shape before
  applying) has no recorded evidence of completion in any U5 artifact.
  The diff does not touch any of those surfaces, so no code adaptation
  was needed regardless, but the operator should confirm no breaking
  change affects the pinned keys/shapes before running
  `rebuild_hermes` + `apply`. Evidence: no reflection file exists;
  neither verdict mentions a changelog read.

- LOW (evidence gap): No `terraform plan` was run by either review
  (Consul state backend 403 without the operator token). Row 4 is
  assessed by static reasoning, not observed output. Acceptable for a
  credentials-gated infra ticket, but worth stating. Evidence:
  `terraform init` with backend returned 403 on
  `terraform/applications`.

## Verdict

Pass. The diff is mechanically correct, minimal, and traces cleanly to
the ticket's Code surface. The three version bumps are consistent with
each other and with the probe-confirmed upstream versions. The
plain-tag convention is preserved. The `null_resource.bifrost_ready`
forced-replacement is designed sentinel behavior, not drift, and does
not break eval row 4 under its intended reading. The two findings above
are process/documentation gaps for the operator to close at apply time,
not defects in the diff under review.