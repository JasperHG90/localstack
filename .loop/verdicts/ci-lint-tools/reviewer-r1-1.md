---
type: verdict
title: 'Verdict: ci-lint-tools reviewer round 1'
description: 'reviewer verdict for round 1 of ci-lint-tools: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T11:37:53+00:00'
slug: ci-lint-tools
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The lint job now installs Terraform 1.16.5 and Nomad 2.0.4 (checksum-verified) and creates an empty `.ssh/id_rsa` before prek runs. I found nothing left that would keep the job red on ubuntu-latest, and the test covers r1's fails_when. Pass.

## Checked

- Gate stamp, run by me from the worktree: pre_commit pass, cli_tests pass, r1 pass, r2 pass, stamp green 652bc602122fd791777aee8482c88e77997db1e618a87b7bc44d53e41e1399d6.
- Every `language: system` hook in `.pre-commit-config.yaml`: nomad-fmt and terraform-fmt need binaries on PATH, which they now get. terraform-validate runs `scripts/tf_validate.sh`, which does `init -backend=false` on a fresh runner. No `.terraform.lock.hcl` is tracked, so no platform-specific hash pins can break init on amd64. Every provider source is a registry address. The ruff, mypy and openviking hooks run through uv, which setup-uv provides. prek fetches Go for the golang hook itself.
- `.ssh/id_rsa`: both roots read `${path.root}/../../.ssh/id_rsa`, which resolves to the repo-root `.ssh/`, and the step creates the file there. detect-private-key does not see the empty key, because `.ssh` is gitignored and `--all-files` only covers tracked files.
- Checksum step: the default `bash -e` shell has no pipefail, but `sha256sum -c -` is the last command in the pipe, so a mismatch fails the step. If grep matches nothing, `sha256sum -c` exits non-zero ("no properly formatted checksum lines"), which also fails the step. The zip name is a unique substring in the SUMS file. Both curls use `-f`.
- setup-terraform's default wrapper passes `-chdir` and exit codes through, so tf_validate.sh is fine with it.
- r1 test: it asserts the pinned terraform_version, the Nomad zip and SUMS names after env substitution (which catches another pinned version), the presence of `sha256sum -c`, and that all three steps come before prek. Moving any step after prek, dropping one, or changing either version makes it fail.
- Consistency: no doc in `docs/`, `.okf/` or `README.md` describes the lint job's steps. The comments in the workflow are accurate.

## Findings

None.

## Notes

The r1 test matches strings, so a step written as `sha256sum -c - || true`, or one that touched `.ssh/id_rsa` in some way other than creating it, would still pass. I am not asking for a change: an edit like that would be a deliberate sabotage, not a likely regression. r3 is the live check after the push.
