---
type: handoff
title: "Passwordless Postgres ticket planning"
description: "postgres-dynamic-credentials is planned and lints clean; risk 1 awaits operator accept and risk 2 is blocked on a working Postgres admin login."
tags: [handoff]
generated:
  by: process:kmctl/0.14.0
  at: 2026-11-19T07:48:24Z
stale_after: 2026-12-03T07:48:24Z
handoff_key: "5b5de334-808c-4b22-977c-aa8f1886ca6d"
---

# Passwordless Postgres ticket planning

## Summary

The operator asked to loop the rollout of passwordless Postgres. ADR 0005
chose Vault's database secrets engine (Path A) in August and the S2 spike
proved it, but it never shipped: every app role still gets a
`random_password` (`deployments/applications/database.tf:56`) written to KV.

The ask was routed to the loop (judgement
`j-20261119T054828+0000-0a32d3ea`) and registered as ticket
`postgres-dynamic-credentials`. It is the first slice of a larger rollout:
stand up a `postgres` mount in Vault, authenticating as a dedicated
`vault-dbengine-admin` role, and move Bifrost onto a per-lease user. Running
jobs on a static Postgres password go from 2 to 1 (openviking stays).

Operator decisions, 2026-11-19:

- The engine, its admin role and the per-job policies and JWT roles live in
  the applications root, an exception to `.okf/architecture/deployment-layers.md`.
  The reason: only that root has the `postgresql` provider, and the
  write-only chain must write the role and the Vault connection in one apply.
  Rejected: every Vault object in infrastructure with the password passed
  through KV, which splits the chain across two roots. The build writes it
  as ADR 0032 (O5).
- Bifrost converts first. It has one template, and its startup migrations
  test ADR 0005's untested failure mode 4.
- After cutover the static `bifrost` role becomes `NOLOGIN` and its human KV
  copy is removed. Break-glass access is the root `localstack` login.

## Where it stands

- Plan written and `loopctl plan lint` is clean apart from the open risks.
- Risk 3, the write-only chain on today's provider pins: settled.
  `spike:postgres-dynamic-credentials/3` applied the whole chain in one apply
  with 0 copies of the password in state. `spike:postgres-dynamic-credentials/2`
  found no colliding leftovers except the stale KV entry
  `secret/default/postgres/vault-dbengine-admin`. The plan now deletes it.
  Not covered: the Consul backend and `ADMIN OPTION` grants.
- Risk 1: decided by the operator, but not yet recorded. It needs
  `loopctl plan accept`, which only the operator may run, in their own terminal.
- Risk 2, failure mode 4: not run. `PGPASSWORD` in the dev shell is stale
  (`FATAL: password authentication failed for user "localstack"`), and the
  auto-mode classifier blocked the spike agent from searching for the
  password. Nothing scratch was created.
- Not started: eval rows (template at
  `.loop/evals/postgres-dynamic-credentials/rows.json`), plan review, build.
- Uncommitted on `main`: the kmctl v0.14.0 upgrade (`apm.yml`,
  `apm.lock.yaml`, `justfile`, `.copier-answers.yml`, the updated
  `.agents/skills/*`, the new `decision-gaps` skill) and this handoff.

## Next steps

1. Operator runs, in their own terminal:
   `loopctl plan accept postgres-dynamic-credentials --risk 1 --reason "Operator chose the applications-root exception: the write-only chain needs the postgresql provider and the Vault connection in one apply"`.
2. Unblock risk 2. Either the operator supplies a working `localstack`
   password in the environment, or explicitly allows reading
   `secret/default/postgres/localstack` from Vault for the spike. Then
   dispatch `spike-runner` on risk 2 with the same hard limits as before:
   scratch objects prefixed `spike_r2`, Bifrost 2.3.1 in a local container,
   full teardown. If it shows Bifrost's driver resets the role, the plan
   changes.
3. `loopctl plan lint postgres-dynamic-credentials`, then the
   `create-eval` skill. Grants g6 and g7 allow eval-sign. g7 runs until
   2026-11-20 05:51 UTC.
4. The `plan-review` skill, then `implement-ticket`.
5. Register follow-up stubs: openviking, memex with its db-migrate prestart,
   the root consumers (exporter, backup-postgres, applications provider; old
   R8), what to do with phoenix and the ducklake roles, and human
   credentials from the engine (old S1).
6. Separately: `.claude/settings.json` (gitignored) holds a plaintext Nomad
   token in many allowlist entries. Operator was told to rotate it and remove
   those entries.

## Key references

- Plan: `.loop/plans/postgres-dynamic-credentials/README.md`
- Spikes: `.loop/spikes/postgres-dynamic-credentials/` (1 discarded, 2 and 3)
- [ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md),
  [ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)
- [S2 runbook and measurements](/proposals/postgres-dynamic-credentials.md)
- [Write-only credential chains](/practices/terraform-write-only-credentials.md)
- Pattern to copy: the Redis engine in `deployments/infrastructure/database.tf`
- Old blocked R3 ticket and its verdict: `git show 48f52e2:.loop/ledger.json`
