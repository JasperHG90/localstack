---
type: verdict
title: 'Verdict: okf-reconcile reviewer round 1'
description: 'reviewer verdict for round 1 of okf-reconcile: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-19T18:45:52+00:00'
slug: okf-reconcile
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The reconcile holds up. I re-ran the stamp and it is green: both gates and
rows r1 to r5 and r7 to r10 pass. On r6, all ten enforced invariants name
tests that exist and pass, and I1 to I11 all appear in the Depicts section of
`architecture/deployment-layers.md`. On r11, the concepts I sampled match the
code, R10 to R12 are recorded accurately against the git history, and each
drafted value cites a decision or practice. Two findings, neither blocking:
some boilerplate Evidence lines name the wrong `.loop/` folder (f1), and one
sentence in minio.md calls a dropped ticket a stub (f2).

## Checked

- Gates: `loopctl gate stamp` from the worktree printed
  `stamp green: 86dc1dc2...`. It passed `just pre_commit`,
  `uv run --directory cli pytest` and rows r1, r2, r3, r4, r5, r7, r8, r9
  and r10.
- r6: I ran the 13 test ids the manifesto names with
  `uv run pytest` (64 passed, parametrized). I read `test_backup_coverage.py`:
  it parses the jobspec and `storage.tf`, and its self-checks keep it from
  passing on empty input. I11 is `planned` and names a real plan
  (`.loop/plans/backup-durable-buckets.md`). The Depicts section lists I1 to
  I11 and is the last section of the page, as `diagrams-stay-current.md`
  requires. The manifesto follows `manifesto-invariants.md`: each line has
  its status, enforced lines name tests, and Values says it is a draft for
  the operator.
- r11, R10 to R12: I checked them against `git show a7aa595` (R12 dropped on
  the operator's call, ledger `dropped: true`), the plans at `48f52e2`, and
  `64c656e` and `84b69a1`. minio.md, memex.md and container-registry.md tell
  it correctly. `storage.tf` has `tempo_wi`, `loki_wi` and `registry_wi`, and
  `aud = ["minio"]` is set in loki.hcl, tempo.hcl and registry.hcl only.
- r11, spot-checks against code (17 concepts): openviking-service (the
  /health and /ready split, 60m grace, restart and update blocks, no
  `memory_max`, the alerts at `for: 50m` and `10m`), hermes (`memory_max`
  removed), devcontainer (volumes, `UV_CACHE_DIR`/`PREK_HOME`, the mc alias
  from GitHub, `just setup` chaining), firebat and nomad-oidc-discovery
  (`nomad_oidc_config_url`, `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD`),
  vault-login-mfa (the `jwt-lab` mount, `AUTH_MODE = "vault-oidc"`,
  `MFARequired` and `validate_mfa`, seven OIDC clients, `fd5134d`),
  vault-secrets-engines (the `vault_nomad_access_token.manage` data source,
  Redis ufw allowing only .46), ufw-rules practice (`timestamp()` trigger
  added in `fef7eee`, applications root keyed on rules), gcs-backups (the
  loop gates in config.toml, which buckets backup-durable-buckets covers),
  openviking-vision-models (`gemini/gemini-3.5-flash-lite`, `66bed3c`),
  openviking-dashboard (`ov-postgres-v0.6.0`, `ov-ext-v0.7.1`),
  placement/summary (five nodes, firebat the only amd64), ADR 0005's
  correction (`secrets.tf:77-97`).
- Repointed sources: I listed every source the diff adds that is not a plain
  strip of a `git:SHA:` prefix. Each points at a file that owns the claim:
  `.pre-commit-config.yaml` for the openviking config hook,
  `nomad_server/tasks/main.yml` for the Nomad developer policy,
  `assets/openviking-dashboard-mockup.html`, and `nats.hcl` for ADR 0004's
  node-address URL. The `.claude/rules/docs-layout.md` source is one of the
  four rule files git tracks. I found no basename mismatch.
- Decisions: r8 passes. 0001 gains one appended line, 0014 a Correction
  section with `status: deprecated`, and the others gain only front-matter
  sources and appended Correction or Evidence sections. r10 passes: no
  `verified` entry was added.
- Summary against `okf-bundle.md`: about 457 words, cites concepts inline
  rather than one bullet per decision, links every section, and holds no
  template text.
- Indexes: the root index now counts 15 decisions, which matches the folder.

## Findings

- **f1** (docs, not blocking): the Evidence template line "(its plan and
  verdicts are in `.loop/archive/` in git history before `5b2ed1b`)" is false
  for backup-swap-memex-for-openviking, D10, G1, G3,
  gcs-backups-doc-to-runbook, M1, OV1, OV2, OV3, R13, R2, R8, R9 and U7.
  `git ls-tree -r 5b2ed1b^ .loop/archive/` has none of them. Their files are
  `.loop/plans/SLUG.md`, `.loop/evals/SLUG.md` and
  `.loop/reflections/SLUG.md` at `48f52e2`. The affected files are
  observability-pipeline, openviking-service, minio, gcs-backups, postgres,
  nats, localstack-cli, container-registry and bifrost. tailscale-subnet-router
  already has the right form. The plan says provenance survives as prose, so
  the prose should lead a reader to the file. The fix is plain: reword those
  lines, then check them with the same `git ls-tree` loop.
- **f2** (nit, not blocking): `components/minio.md` ends the R10 to R12
  paragraph with "All three were still stubs in the loop ledger when
  `5b2ed1b` reset the loop". R12 was marked dropped, not left a stub. Say
  "R10 and R11 were still stubs, and R12 dropped, when ...".

## Notes

Many dropped `docs/` sources were replaced with the code that owns the claim,
not with the page the doc moved to. That fits kmctl's purpose better and the
docs tickets come next, so I raise no finding on it.
