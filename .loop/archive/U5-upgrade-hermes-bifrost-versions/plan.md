---
epic = "upgrade"
depends_on = []
priority = 20
summary = "Bump the pinned Hermes base image and Bifrost binary to their current upstream releases, keeping the two independent version schemes (Hermes: calver base image containing a semver pip package; Bifrost: semver binary) straight."
---

# Ticket: U5-upgrade-hermes-bifrost-versions

## 1. Title
Bump the Hermes base image and the Bifrost version pin so both track a
current upstream release instead of one that is several releases behind.

## 2. Size / Effort
**S/M.** Two `.tf` lines and one Dockerfile `FROM` line change. Sized up
from pure S because picking the *correct* new values requires a live probe
against the registries (see Requirements #1) rather than trusting a
scrape taken at planning time.

## 3. Triggered by
Operator note: "Hermes bumped to v0.19.1 and bifrost latest is v1.6.7."

## 4. Context

Two independent version axes, easy to conflate:

- **Bifrost.** `deployments/applications/services.tf:188` sets
  `bifrost_version = "1.6.2"`, interpolated into
  `deployments/applications/services/bifrost.hcl:40` as
  `docker.io/maximhq/bifrost:v${bifrost_version}`. One knob, one number.
- **Hermes.** Two separate things share the name "Hermes version":
  - The **base image tag**, pinned in
    `deployments/applications/services/hermes/Dockerfile:9` as
    `FROM nousresearch/hermes-agent:v2026.7.1` — a **calver** tag
    (`vYYYY.M.D`) chosen by the upstream maintainer, currently several
    releases behind (checked via Docker Hub on 2026-08-03: `v2026.7.20`,
    `v2026.7.30`, and a floating `latest`/`main` exist above our pin).
  - Our own **custom label**, `hermes_version` in
    `deployments/applications/services.tf:124`, currently
    `"0.12.0-memex-v1.0.1"`. This string has no runtime meaning of its
    own — it is only the tag of our derived image
    `ghcr.io/jasperhg90/hermes:${hermes_version}`
    (`deployments/applications/justfile:36-44` `rebuild_hermes` builds
    and pushes it from the Dockerfile above). By the Dockerfile's own
    naming convention the first segment records whichever `hermes-agent`
    **pip package** semver the pinned base image happens to bundle, and
    the `-memex-vX.Y.Z` segment records the Memex wheel version installed
    in `deployments/applications/services/hermes/Dockerfile:28-30`
    (currently pinned to `v1.0.1`, unrelated to this ticket — see
    Non-goals). The pip package's own version numbers (checked via PyPI
    on 2026-08-03: latest listed there was `0.19.0`, 2026-07-20) do
    **not** necessarily line up 1:1 with the calver image tag; the label
    is only ever recomputed by whoever runs `rebuild_hermes`, and nothing
    enforces that it stays accurate.
  - There is no `hermes-agent` pip install anywhere in our Dockerfile —
    the package is baked into the upstream base image, so the only way to
    know which pip version a given base tag bundles is to pull that image
    and check it directly (see Requirements #1). Trusting a DockerHub/PyPI
    page scraped at planning time for the exact match is not good enough:
    confirmed below, the current pin (`v2026.7.1`) already bundles
    `0.18.0`, not the `0.12.0` our own label claims — the label has
    already drifted.
  - **Probe run during planning review** (`loopctl verify-plan` pass,
    `.loop/verdicts/U5-upgrade-hermes-bifrost-versions.plan-validator.md`,
    2026-08-03): pulled `nousresearch/hermes-agent` for `v2026.7.1`,
    `v2026.7.20`, `v2026.7.30`, and `latest` on `linux/arm64` and ran
    `hermes --version` in each. Results: `v2026.7.1` (our current pin) →
    `0.18.0`; `v2026.7.20` → `0.19.0`; `v2026.7.30` → `0.19.1`, and
    `v2026.7.30` is identical to `latest`. `0.19.1` matches the operator's
    trigger note exactly and does not appear on PyPI's public listing
    (P4), confirming a live probe was the only way to find it.

## 5. Non-goals / out of scope

- Bumping the Memex wheel versions in
  `deployments/applications/services/hermes/Dockerfile:28-30` (pinned
  `v1.0.1`; a newer `v1.1.0` exists upstream). Not requested; a separate
  concern from the Hermes/Bifrost bump.
- Adopting Hermes's native `secrets:` config feature — that is
  `U6-evaluate-hermes-native-secrets` (stub), a separate open design
  question, not a mechanical version bump.
- Running `just rebuild_hermes` / pushing the new image, and running
  `just apply` against the cluster. Both require credentials and cluster
  access this ticket does not assume; the operator runs them after review,
  the same way `T4-tls-fix-podman-image-digest-refs` left "re-running the
  apply" to the operator.
- Converting any of these three references to digest pins. The repo's
  established convention (recorded in the archived
  `T4-tls-fix-podman-image-digest-refs` ticket) is plain tags; that
  ticket's actual finding was narrower than "no digests" — the podman
  driver rejects the *combined* `tag@digest` form, not a digest alone —
  but plain tags are still the unbroken, established convention here and
  this ticket does not deviate from it.

## 6. Requirements & restrictions

1. **Verify by probe, not by scrape** (satisfied — see Context "Probe run
   during planning review" and P6). Planning-time DockerHub/PyPI pages
   were a starting hypothesis, not ground truth — this repo's own
   discipline for behavioral premises
   (`.claude/plugins/aim-ef9f6a17bd3105b7/loop-harness/skills/create-ticket/SKILL.md`,
   "Verify behavioral premises by probe") applies here: the version
   string is derived FROM the probe, not asserted then checked. The
   implementer does not need to re-run this probe; re-run it only if the
   apply is delayed long enough that a newer tag may have superseded
   `v2026.7.30`.
2. **Keep the label convention.** The new `hermes_version` value is
   `"0.19.1-memex-v1.0.1"` (memex segment unchanged per Non-goals),
   matching the format the Dockerfile comment at line 1-8 and the
   existing value already establish.
3. **Read both changelogs for breaking changes** before applying:
   Hermes (https://github.com/NousResearch/hermes-agent/releases,
   between `0.18.0` and `0.19.1`) and Bifrost
   (https://github.com/maximhq/bifrost/releases, between `1.6.2` and
   `1.6.7`), checking specifically against:
   - `deployments/applications/services/hermes.hcl:218-331` (`config.yaml`
     keys: `model`, `fallback_model`, `plugins`, `skills`, `memory`,
     `terminal`/`code_execution` `env_passthrough`, `auxiliary`,
     `platform_toolsets`, `mcp_servers`).
   - `deployments/applications/services.tf:260-283`
     (`bifrost_virtual_key` resources: `provider_configs`,
     `allowed_models`, `key_ids`, `weight`).
   No requirement to change any of the above unless a changelog names a
   breaking change to one of these keys/shapes.
4. Plain-tag convention only (see Non-goals) — no digest pins.

## 7. Code surface

- `deployments/applications/services/hermes/Dockerfile:9` — bump `FROM
  nousresearch/hermes-agent:v2026.7.1` to `FROM
  nousresearch/hermes-agent:v2026.7.30` (confirmed bundling `0.19.1`, see
  Requirement #1).
- `deployments/applications/services.tf:124` — bump `hermes_version =
  "0.12.0-memex-v1.0.1"` to `hermes_version = "0.19.1-memex-v1.0.1"`.
- `deployments/applications/services.tf:188` — bump `bifrost_version =
  "1.6.2"` to `"1.6.7"`.

No other file needs an edit: `deployments/applications/justfile:36-44`
reads `hermes_version` out of `deployments/applications/services.tf` at
build time, and
`deployments/applications/services/bifrost.hcl:40` interpolates
`bifrost_version` the same way — both already point at the bumped values
once the two `.tf` lines change.

## 8. Tests & validation gates

This repo has no automated test suite for Terraform/HCL infra changes
(confirmed by the archived `T4-tls-fix-podman-image-digest-refs` ticket,
which used the same gate set for a comparable image-reference change).
Gates:
- `just pre_commit` from repo root (`nomad fmt -recursive`, `terraform fmt
  -check -recursive`, `terraform validate` per `.pre-commit-config.yaml`).
- `terraform plan -var-file=./vars/prod.tfvars` from
  `deployments/applications/` (via `just apply refresh=false` is NOT
  appropriate here — that applies; use a plain `terraform plan` to
  confirm only the three expected diffs appear, nothing else drifts).
- Manual post-apply smoke check (operator-run, not part of this ticket's
  gate): Hermes gateway health check
  (`deployments/applications/services/hermes.hcl:379-384`, TCP check on
  the `gateway` port) goes healthy, and one Bifrost-routed Hermes chat
  turn completes, after the operator runs `rebuild_hermes` + `apply`.
- Eval marker: `.loop/evals/U5-upgrade-hermes-bifrost-versions.md`
  (5 rows, all deterministic, 100% threshold).

## 9. Risk assessment

- **Blast radius:** both services restart on apply (new image pull).
  Hermes downtime for the rebuild+pull+restart cycle; Bifrost briefly
  unavailable, which also stalls any in-flight Hermes/Memex call routed
  through it (per the comment at
`deployments/applications/services.tf:181`, Bifrost is a single
  point of failure for both Hermes and Memex's model calls).
- **Reversibility:** trivial — revert the three lines and re-apply.
  Old images are not deleted from the registry.
- **Likeliest failure mode:** a config.yaml or `bifrost_virtual_key`
  breaking change from Requirement #3 that isn't caught before apply and
  only surfaces as a Hermes crash-loop or Bifrost 4xx after restart.
  Mitigated by reading changelogs first and by the plan step being
  reversible.

## 10. Subtickets

None. Single-file-set change, one loop iteration.

## 11. Open questions

1. **Resolved** during planning review (P6): `v2026.7.30` bundles
   `hermes-agent 0.19.1`, matching the operator's trigger note. Pin that
   tag.
2. Should the base image tag track a specific dated release
   (`v2026.7.30`) or the floating `latest`/`main`? Recommendation: pin
   the dated release tag — floating tags reintroduce the exact "drifts
   without an apply" risk the repo already flagged for the
   Bifrost-admin-creds sync (`deployments/infrastructure/secrets.tf:90-98`),
   and the plain-tag convention throughout this repo already implies a
   fixed, named tag. `v2026.7.30` and `latest` are identical today, so
   this loses nothing at apply time.

## Premises / assumptions

- P1 (VERIFIED — source: `deployments/applications/services/hermes/Dockerfile`
  line 9): current base pin is `nousresearch/hermes-agent:v2026.7.1`.
- P2 (VERIFIED, `deployments/applications/services.tf:124-188`): current
  labels are `hermes_version = "0.12.0-memex-v1.0.1"`,
  `bifrost_version = "1.6.2"`.
- P3 (VERIFIED — source: https://hub.docker.com/r/nousresearch/hermes-agent/tags,
  checked 2026-08-03): newer versioned base tags exist above our pin
  (`v2026.7.20`, `v2026.7.30`), plus a floating `latest`/`main`.
- P4 (VERIFIED — source: https://pypi.org/project/hermes-agent/, checked
  2026-08-03): `hermes-agent` pip releases up to `0.19.0` (2026-07-20) are
  listed; the operator's stated `0.19.1` was not visible on that page at
  scrape time. UNCERTAIN whether it has since shipped or the operator
  meant the nearest listed release — Requirement #1's live probe is the
  actual source of truth for what to pin, not this scrape.
- P5 (RESOLVED, source: P6 below): whether the base image's calver tag
  and the bundled pip semver move in lockstep release-for-release — they
  do for the tags probed (`v2026.7.1`→`0.18.0`, `v2026.7.20`→`0.19.0`,
  `v2026.7.30`→`0.19.1`).
- P6 (VERIFIED — probe:
  `docker run --platform=linux/arm64 nousresearch/hermes-agent:<tag>
  hermes --version` (read-only; add cleanup of the stopped container
  afterward), run during planning review, source:
  `.loop/verdicts/U5-upgrade-hermes-bifrost-versions.plan-validator.md`,
  2026-08-03): `v2026.7.1` bundles `0.18.0`; `v2026.7.20` bundles
  `0.19.0`; `v2026.7.30` bundles `0.19.1` and is identical to `latest`.
  Also confirmed `docker.io/maximhq/bifrost:v1.6.7` exists and is the
  current `latest` release on Docker Hub.
