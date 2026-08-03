eval: U5-upgrade-hermes-bifrost-versions

Hermes and Bifrost track a current upstream release: three version pins
bumped, nothing else touched, `just pre_commit` and a `terraform plan`
show exactly those three lines and no drift.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Hermes base image pin bumped | `git diff` of `deployments/applications/services/hermes/Dockerfile` | Line 9's `FROM` changes from `nousresearch/hermes-agent:v2026.7.1` to `nousresearch/hermes-agent:v2026.7.30`, no other line in the file changes | Deterministic (diff match) | 100% |
| Hermes custom image label bumped | `git diff` of `deployments/applications/services.tf` line 124 | `hermes_version` changes from `"0.12.0-memex-v1.0.1"` to `"0.19.1-memex-v1.0.1"` | Deterministic (string match) | 100% |
| Bifrost version pin bumped | `git diff` of `deployments/applications/services.tf` line 188 | `bifrost_version` changes from `"1.6.2"` to `"1.6.7"` | Deterministic (string match) | 100% |
| No drift outside the three pins | `terraform plan -var-file=./vars/prod.tfvars` from `deployments/applications/` after the edit | Plan shows changes to exactly `nomad_job.hermes` and `nomad_job.bifrost` (image tags only); no other resource in the plan diff | Deterministic (terraform plan output) | 100% |
| Plain-tag convention preserved (guardrail) | The three new pin values | None of the three carries a `@sha256:` digest suffix or a floating tag (`latest`/`main`) | Deterministic (regex: no `@sha256`, no bare `latest`/`main`) | 100% |

signed-off-by: jasperginn@gmail.com 2026-08-03
