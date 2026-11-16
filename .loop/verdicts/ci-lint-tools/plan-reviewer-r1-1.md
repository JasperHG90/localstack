---
type: verdict
title: 'Verdict: ci-lint-tools plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ci-lint-tools: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:30:03+00:00'
slug: ci-lint-tools
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan fixes the first failing hook but not the next one. I ran the full
prek suite on a fresh clone with nomad 2.0.4 and terraform 1.16.5 on PATH.
Every hook passed except terraform-validate, which fails because both roots
read a gitignored SSH key with file(). This needs a plan revision, not a
rethink. With an empty placeholder .ssh/id_rsa, both roots validate cleanly.

## Checked

- Run 43826973355 lint log: prek stops at nomad-fmt before any other hook
  reports, so nothing after it had been tested in CI.
- Cloned HEAD into the scratchpad (no .terraform, no lock files, no .ssh) and
  ran `uvx prek@0.5.5 run --all-files`. Passed: pre-commit-hooks, nomad-fmt,
  terraform-fmt, ruff, ruff-format, mypy (cli/src, cli/tests, scripts),
  openviking-config, ov-sync-consumer-go (prek fetched Go 1.27.4 itself).
  Failed: terraform-validate, on the file() call at
  deployments/infrastructure/services.tf:499. Running applications by hand
  fails the same way at deployments/applications/services.tf:262.
- With a placeholder .ssh/id_rsa touched in the clone, scripts/tf_validate.sh
  prints Success for both roots (infrastructure with deprecation warnings
  only).
- Providers: `.terraform.lock.hcl` and `.terraform` are gitignored
  (deployments/.gitignore), so the darwin/arm64 hash question does not apply.
  CI inits from scratch. Every provider (including AirHelp-OSP/bifrost and
  cyrilgdn/postgresql) comes from the public registry, and fresh init worked.
- No hook calls docker.

## Findings

- p1: terraform-validate fails on a clean checkout because of
  file(".../.ssh/id_rsa") in both roots. Installing the tools alone leaves
  the ci run red, so the plan's outcome and r3 cannot be met as scoped.

## Notes

The local run was on linux_arm64, and CI runs on amd64. The Go toolchain and
provider downloads are per-platform, but nothing suggests amd64 differs. Since
no lock file is committed, CI resolves the newest provider that fits each
constraint (for example aws ~> 6.0). That can drift from local, but it does
not break validate today.
