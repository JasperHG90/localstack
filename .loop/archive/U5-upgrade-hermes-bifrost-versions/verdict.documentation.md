---
verdict: pass
tree: 2021c05935d28ae900b932c602527f0af4610d47
---

## Documentation-freshness review: U5-upgrade-hermes-bifrost-versions

The change bumps three internal version pins:
- `deployments/applications/services/hermes/Dockerfile:9`: `FROM nousresearch/hermes-agent:v2026.7.1` -> `v2026.7.30`
- `deployments/applications/services.tf:124`: `hermes_version` `"0.12.0-memex-v1.0.1"` -> `"0.19.1-memex-v1.0.1"`
- `deployments/applications/services.tf:188`: `bifrost_version` `"1.6.2"` -> `"1.6.7"`

These are config values interpolated into container image tags at build/apply
time (`hermes.hcl:45,465` and `bifrost.hcl:40`). They are not a public API, a
CLI flag, a documented config schema key, or a user-facing command.

### Documented-surface check

I searched every markdown file in the repo (excluding `.loop/` and vendored
trees) and every Terraform/HCL/Dockerfile for the old version strings
(`0.12.0-memex`, `1.6.2`, `v2026.7.1`, `v2026.7.30`, `0.19.1`, `1.6.7`):

- No README, runbook, `docs/` page, or SKILL.md states any of these version
  numbers. Hermes and Bifrost are referenced in docs only by role
  (`docs/workload-identity.md`, `docs/haproxy_reverse_proxy.md`,
  `docs/nats.md`, `docs/vault-human-auth.md`, `README.md`, `AGENTS.md`), never
  by pinned version.
- The Dockerfile header comment at line 1 says `v2026.5.16+` (a minimum-floor
  note, not the exact pin). `v2026.7.30` satisfies that floor, so the comment
  stays accurate.
- `deployments/applications/services/hermes/SOUL.md` and the skills under
  `hermes/skills/` describe agent behavior, not image versions.

No documented behavior changed. No doc needs updating. Pass.