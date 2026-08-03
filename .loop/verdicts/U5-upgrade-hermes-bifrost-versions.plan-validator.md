---
verdict: pass
plan: 5c31e1a834ead79319a8651538267d25de32cc036a47cb7461978bc82f80e175
---

# Plan-validator review — U5-upgrade-hermes-bifrost-versions

Re-run. Prior verdict bound the stale fingerprint `1572c7e9...`; the
current plan hash is `5c31e1a8...`, confirmed by `sha256sum` of the plan
file at `.loop/plans/U5-upgrade-hermes-bifrost-versions.md`.

## Deterministic floor

`loopctl verify-plan U5-upgrade-hermes-bifrost-versions` -> `valid`.

## Premise verdict

**SOUND.** Every load-bearing assumption was re-checked against the repo
and re-probed against the live registries during this review (2026-08-03).
The plan's core claim — that a live probe is the only way to derive the
correct `hermes_version` label because the calver base tag and the bundled
pip semver do not publish a 1:1 map — is confirmed by independent
reproduction, not by trusting the plan's own restatement.

## Per-assumption findings

- **P1 — current base pin is `nousresearch/hermes-agent:v2026.7.1`.**
  HOLDS. `deployments/applications/services/hermes/Dockerfile:9` reads
  `FROM nousresearch/hermes-agent:v2026.7.1`.

- **P2 — current labels are `hermes_version = "0.12.0-memex-v1.0.1"` and
  `bifrost_version = "1.6.2"`.** HOLDS.
  `deployments/applications/services.tf:124` reads
  `hermes_version = "0.12.0-memex-v1.0.1"`;
  `deployments/applications/services.tf:188` reads
  `bifrost_version = "1.6.2"`.

- **P3 — newer versioned base tags exist above the pin.** HOLDS. Probed
  `v2026.7.20`, `v2026.7.30`, and `latest` on `linux/arm64`; all pull and
  run.

- **P4 — PyPI listing vs operator note.** The plan itself marks this
  UNCERTAIN and defers to the probe (P6), which is the correct posture. The
  plan does not rest on P4; it is listed only to motivate the probe
  requirement. No load-bearing weight on this one.

- **P5 — calver tag and bundled pip semver move in lockstep for the probed
  tags.** HOLDS. Reproduced independently during this review:
  `v2026.7.1` -> `Hermes Agent v0.18.0 (2026.7.1)`;
  `v2026.7.20` -> `Hermes Agent v0.19.0 (2026.7.20)`;
  `v2026.7.30` -> `Hermes Agent v0.19.1 (2026.7.30)`;
  `latest` -> `Hermes Agent v0.19.1 (2026.7.30)` (identical to
  `v2026.7.30`).

- **P6 — probe results: `v2026.7.30` bundles `0.19.1`; `v1.6.7` exists.**
  HOLDS. Re-probed during this review (2026-08-03) by running
  `docker run --rm --platform=linux/arm64 --entrypoint /bin/sh
  nousresearch/hermes-agent:<tag> -c 'hermes --version'` for each tag.
  Output matches the plan's recorded results verbatim.
  `docker manifest inspect docker.io/maximhq/bifrost:v1.6.7` confirms the
  Bifrost tag exists; `latest` also exists. The operator's trigger note
  ("0.19.1") matches the probe exactly.

## Most dangerous assumption

**P6 — that `v2026.7.30` bundles `hermes-agent 0.19.1` and is identical to
`latest`.** If wrong, the new `hermes_version` label
(`"0.19.1-memex-v1.0.1"`) would be miscategorized from the moment it
ships, reproducing the exact label drift the ticket was opened to fix (the
current label claims `0.12.0` while the pin actually bundles `0.18.0`).
This one was re-probed live during this review and confirmed, so it holds.

## Contract hygiene

- **Real code surface with resolved anchors.** Every cited `path:line`
  resolves to the thing claimed, confirmed by direct read:
  `Dockerfile:9`, `services.tf:124`, `services.tf:188`,
  `bifrost.hcl:40`, `justfile:36-44`, `hermes.hcl:218-331`,
  `hermes.hcl:379-384`, `services.tf:260-283`, `services.tf:181`,
  `secrets.tf:90-98`.

- **Discovered, not assumed, gates.** `.pre-commit-config.yaml` confirms
  `nomad-fmt` (nomad fmt -recursive), `terraform-fmt`
  (terraform fmt -check -recursive), `terraform-validate`
  (scripts/tf_validate.sh, per root). The plan's gate list matches. The
  `terraform plan -var-file=./vars/prod.tfvars` invocation matches the
  `justfile` `apply` recipe (which uses `-var-file=./vars/prod.tfvars`).
  No automated test suite for Terraform/HCL is claimed, consistent with
  the repo: the `cli/`-only pytest/ruff/mypy hooks do not touch these
  files.

- **Explicit non-goals.** Stated and scoped: Memex wheel bump, native
  secrets adoption, running `rebuild_hermes`/`apply` (operator-run),
  digest pins. Each is justified.

- **Tests homed in the code surface.** The eval marker
  `.loop/evals/U5-upgrade-hermes-bifrost-versions.md` exists with 5 rows,
  all deterministic, 100% threshold, each row tied to a concrete
  file:line or command.

- **Forks surfaced.** Open question 2 (dated tag vs floating `latest`) is
  raised with a recommendation (pin the dated tag), not silently decided.

## Required fixes

None. The plan is ready to leave PLANNING.