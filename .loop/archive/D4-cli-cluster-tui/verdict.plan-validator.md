---
verdict: pass
plan: 3edec314fa81042572f037c20a4c06a139e5e28b5124dd7d17f562161ac70c3f
---

# Plan review: D4-cli-cluster-tui (pass 4, plan-validator)

Plan reviewed: `/home/vscode/workspace/.loop/plans/D4-cli-cluster-tui.md`
Fingerprint: `3edec314fa81042572f037c20a4c06a139e5e28b5124dd7d17f562161ac70c3f`.
`loopctl verify-plan D4-cli-cluster-tui` returned `valid`.
Live cluster probed during this review (read-only GETs, 2026-08-03).

## Premise verdict: SOUND

All premises P1-P13 hold against the live cluster and the repo. The RF1
fix (httpx runtime dep) and the four stale-anchor hygiene fixes from
pass 3 all landed correctly. All prior fixes from passes 1-3 still
hold. No new required fixes surface.

## RF1 fix (httpx runtime dep): confirmed applied

- `cli/pyproject.toml:7-9` lists only `click`, `rich`, `typer` as
  runtime deps. httpx is NOT a CLI dependency today.
- `cli/src/localstack_cli/auth/vault.py:9-10` imports `urllib.error`
  and `urllib.request` (stdlib), confirming D1 built on urllib.
- `requirements.txt:3` carries `httpx`, but that file serves the
  non-CLI scripts, not this package.
- Requirement 11 (`plan:311-321`) now correctly states httpx must be
  added via `uv add httpx` (runtime) and `respx` via `uv add --dev
  respx`, and no longer claims httpx is already the CLI's HTTP client.
- Section 7 modified-pyproject line (`plan:392-396`) lists `uv add
  httpx` alongside `textual`.

## Stale-anchor hygiene fixes: confirmed applied

- `justfile:33-34` is `unseal_vault` (resolves; cited at `plan:120`,
  `plan:239`).
- `justfile:41-42` is `worktree_setup` (resolves; cited at `plan:422`).
- `.loop/ledger.json:892` is D4 `"priority": 42` (resolves; cited at
  `plan:714`).
- `.loop/ledger.json:842` is D3 `"priority": 20` (resolves; cited at
  `plan:715`).

## Per-assumption findings

### P1 (HOLDS) — JobSummary counters are cumulative

`GET /v1/jobs` live key set: carries `JobSummary` but no
`GroupCountSum`. Eight healthy service jobs carry `Failed > 0` while
`Running=1` and `Status=running`:

```
grafana     Failed=7   haproxy    Failed=11  loki       Failed=8
memex       Failed=31  minio      Failed=3   phoenix    Failed=15
postgres    Failed=6   prometheus Failed=4
```

The exact counter values drift upward over time (grafana was `Failed=4`
on 2026-07-31, is `7` today), but the plan's claim is structural
(cumulative, not current state), not about exact values. Evidence:
`GET /v1/jobs` live, 200 with token.

### P2 (HOLDS) — /v1/jobs/statuses returns current state

`GET /v1/jobs/statuses` returns 200 with token, 403 without. 19 jobs.
Key set verified: `Allocs ChildStatuses Datacenters GroupCountSum ID
IsPack LatestDeployment ModifyIndex Name Namespace NodePool ParentID
Priority Status Stop SubmitTime Type Version`. No `JobSummary` key,
matching the plan's strongest-protection claim (`plan:432-438`).
Pagination confirmed: `?per_page=5` sets `X-Nomad-Nexttoken: 225790`.

### P3 (HOLDS) — Periodic parents: Allocs null

Periodic parents `acme`, `backup-minio`, `backup-postgres` each return
`Allocs: None` (JSON null), `ChildStatuses: []`, `GroupCountSum: 1`,
`Status: running`, `Stop: False`. The null-vs-empty distinction the
plan builds on is real. Evidence: live probe output.

### P4 (HOLDS) — GroupCountSum per-node for system jobs

`node-exporter` and `promtail` (system type) both report
`GroupCountSum: 1` with 5 running allocs. Evidence: live probe.

### P5 (HOLDS) — Tokenless Consul reads via tokens.default

Consul tokenless `GET /v1/health/state/any` is 200 with 41 checks, 0
critical. Same call with a bogus token is 403. Tokenless
`GET /v1/acl/tokens` is 403. Config anchor
`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-33` shows
`default_policy = "deny"` at `:27` and `tokens.default` set to the
agent token at `:29-32`. The three-probe separation is confirmed.

### P6 (HOLDS) — Vault seal-status tokenless, Nomad 403 tokenless

Vault `GET /v1/sys/seal-status` is 200 tokenless (sealed: false, type:
shamir). Nomad `/v1/jobs/statuses` and `/v1/nodes` are both 403
tokenless. ACL on at
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:45-47`.

### P7 (HOLDS) — deploy role lacks list-jobs/node; manage needed

`nomad_deploy_role.tf:1-12` comment states "no list-jobs ... no node /
agent / operator access"; `:17-29` grants only `submit-job`,
`read-job`, `host-volume-*`. The `manage` Vault role at
`deployments/infrastructure/nomad_oidc.tf:74-78` is
`type = "management"`. The developer policy grants `nomad/creds/manage`
read at `deployments/infrastructure/developer_group.tf:140`. D2 today
brokers only `nomad/creds/deploy` and `consul/creds/deploy`
(`cli/src/localstack_cli/auth/broker.py:25-26`). The relay-to-D2
precondition is real and honestly recorded as a privilege widening.

### P8 (HOLDS) — N4 closes LAN ports, edge survives

N4 plan at `.loop/plans/N4-netsec-edge-only-service-access.md:418`
narrows LAN ports; `:465` states "the only route to Nomad's API becomes
haproxy". N4 priority 50 > D4 priority 42 (`.loop/ledger.json:892`).
The edge survives: port 443 open to both LAN and tailnet
(`deployments/infrastructure/services.tf:189-190`).

### P9 (HOLDS) — HTTPS edge routes the three services

haproxy routes `vault.`, `nomad.` and `consul.lab.orangecluster.nl`
(`deployments/infrastructure/services/haproxy.hcl:98-107`). Probed live
over TLS: vault edge 200, consul edge 200, both with valid
certificates (no `-k`).

### P10 (HOLDS) — Cluster versions

Vault 2.0.3 and Consul 2.0.2 confirmed live via `/v1/sys/seal-status`
version field and `/v1/agent/self` config. Nomad 2.0.4 recorded in
`U1-upgrade-pin-hashistack-versions/plan.md:72-74` (agent/self needs a
token I did not mint; the plan's version claim is consistent with the
U1 record and the 2026-07-31 incident log at `nomad.hcl.j2:18-22`).

### P11 (HOLDS) — D4 picked before D3

`.loop/ledger.json:892` carries D4 priority 42; `:842` carries D3
priority 20. Pickup order puts D4 first. Both anchors resolve.

### P12 (HOLDS) — D1 establishes cli/src/localstack_cli/

D1 archive plan at `:167-191` establishes `cli/src/localstack_cli/` as
the package root. `cli/src/localstack_cli/config.py` exists and reads
`VAULT_ADDR`, `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`, erroring on missing, as
the plan's requirement 8 depends on.

### P13 (HOLDS) — Repo gates

`.pre-commit-config.yaml:37-72` carries ruff, ruff-format, mypy
(strict, `--config-file cli/pyproject.toml`) and pytest hooks scoped
to `^cli/`. `.loop/config.json` gates on `just pre_commit`;
`justfile:18-19` runs `pre-commit run --all-files`. No CI for these
gates (`.github/workflows/` holds only agent runners).

## Most dangerous assumption

P1/P2 together: that `/v1/jobs` counters are cumulative while
`/v1/jobs/statuses` carries current state. If this were wrong, the
panel's entire health model collapses. It is not wrong: the live key
sets and counter values confirm it directly, and the structural
absence of `JobSummary` from `/v1/jobs/statuses` is the strongest
protection against reading the wrong counters.

## Contract hygiene

- Real code surface with resolved anchors: all cited `path:line`
  anchors resolve to the claimed content. The stale anchors from pass
  3 are fixed.
- Discovered gates: `just pre_commit` and `uv run --project cli pytest`
  match the repo's actual gate configuration.
- Explicit non-goals: section 5 (`plan:210-234`) is thorough and
  bounded.
- Tests homed in the code surface: every test file listed in section 7
  with its path under `cli/tests/`.
- Forks surfaced: all open questions resolved in `## Forks resolved,
  2026-07-31` (`plan:746-825`) with the operator's decisions recorded.
  Q2, Q3, Q5, Q6 overturned with reasons.

## Verdict

pass. The premise is SOUND, the contract is clean, and all fixes from
prior passes hold.