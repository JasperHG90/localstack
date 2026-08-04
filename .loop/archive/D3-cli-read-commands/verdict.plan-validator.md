---
verdict: pass
plan: 3e4e4bb9eb2cb270e63b0418bd5b814e8586baedfafc829b0ff5df402eb81094
---

# D3-cli-read-commands — plan premise review (second pass)

Plan reviewed: `.loop/plans/D3-cli-read-commands.md`
sha256 `3e4e4bb9eb2cb270e63b0418bd5b814e8586baedfafc829b0ff5df402eb81094`.
Pass id: `plan-validator`. Repo root: `/home/vscode/workspace`.

This is the second review pass after two required fixes were applied:
the pickup-order note in requirement 2 and the rewritten Q1 option (b)
rationale. The first review returned `pass`; this pass re-falsifies the
premises against the live cluster (probed 2026-08-03, read-only GETs
only) and the merged tree, and verifies the two fixes are consistent
with the ledger and D4's current plan.

## Deterministic floor

`loopctl verify-plan D3-cli-read-commands` returned exit 0, `valid`,
with warnings only (no hard-fail):

- "symbol 'developer' cited at developer_group.tf:78-80 is off those
  lines"
- "symbol 'developer' cited at developer_group.tf:110-112 is off those
  lines"
- "31/33 Context/Requirements claims carry no path:line anchor"

The two symbol warnings are heuristic false-positives. The cited line
ranges do contain the grants the plan claims:
`developer_group.tf:78-80` is the `path "sys/policies/acl/*"` block
(line 79 carries `read`); `:110-112` is the `path
"secret/metadata/default/*"` block. The verifier's heuristic looks for
the `developer` resource declaration, which starts at `:15`, not the
cited path-block content. The anchors resolve. The coverage warning is
informational; section 7 carries the resolved code-surface anchors the
contract requires.

## Premise verdict: SOUND

The plan's load-bearing premises hold against the live cluster and the
merged tree. No premise breaks. The two fixes applied since the first
review are consistent with the ledger and with D4's current plan text.

## Per-assumption findings (live cluster probed 2026-08-03)

- **P1 (haproxy routes live in the Nomad API, not the repo).** HOLDS.
  Live `GET /v1/job/haproxy` returns `TaskGroups[].Tasks[].Templates[]`;
  the `local/haproxy.cfg` entry's `EmbeddedTmpl` is 2327 bytes and
  carries all ten `acl is_<n> hdr(host) -i <host>` lines verbatim
  (probed). The repo file `deployments/infrastructure/services/haproxy.hcl`
  is a `templatefile` input wired at
  `deployments/infrastructure/services.tf:318-323`, with
  `openfang_password` interpolated at `:322`. Not a parseable jobspec.

- **P2 (three-way join has no shared key; 10/19/25 counts).** HOLDS.
  Live: 10 routed hostnames parsed from the haproxy `EmbeddedTmpl`; 19
  Nomad jobs via `GET /v1/jobs` (including `talat-shim` and
  `talat-consumer`, both confirmed); 25 Consul services via
  `GET /v1/catalog/services` (no token). `vault`, `nomad` and `consul`
  routes back onto no Nomad job; `s3` backs onto no job and no Consul
  service. Confirmed end-to-end with a management token this pass.

- **P3 (haproxy jobspec carries a live password).** HOLDS. The live
  `EmbeddedTmpl` contains the `insecure-password` line (probed). The
  interpolation is at `deployments/infrastructure/services.tf:322`.

- **P4 (every Vault reference is a static literal).** HOLDS on the
  evidence cited. The regex mechanism is sound for literal
  `{{ with secret "..." }}` references; requirement 6's unknown state
  and test 14 guard the computed-reference case the plan hedges against.
  Not all 19 jobs were re-probed individually in this pass, but the
  live `nomad-workloads` policy and the haproxy template both behaved
  as the plan describes. The plan states this as a probe result and
  degrades visibly via the unknown state if it breaks.

- **P5 (brokered Consul token sees 2 of 25 services).** HOLDS on the
  policy file. `bootstrap/playbooks/enable_consul_secrets.yml:39-58`
  grants `service "minio"` read and `service "postgres-db"` read with
  no `service_prefix` (confirmed verbatim). The devcontainer's
  `CONSUL_TOKEN` is the bootstrap master token (sees all 25), so the
  2-of-25 filter was not directly reproduced in this pass; the ACL
  policy file is the authority and it supports the claim. Anonymous
  `GET /v1/catalog/services` returns 200 with all 25 (probed),
  matching the plan.

- **P6 (templated policy is three-block post-F9).** HOLDS. Live
  `GET /v1/sys/policies/acl/nomad-workloads` returns exactly three
  `path` blocks: `secret/data/{ns}/{job}/*`, `secret/data/{ns}/{job}`,
  and `secret/metadata/{ns}/*` (probed). The renderer's "handle both
  shapes" rule is justified: the policy already changed block count
  once.

- **P7 (server versions 2.0.x).** HOLDS. `GET /v1/sys/health` returned
  a 2.x-shaped payload (`sealed: false`, `initialized: true`) and works
  with no token (probed). Consistent with the cited handoff and prior
  reviews.

- **P8 (userpass is live).** HOLDS.
  `deployments/infrastructure/auth_userpass.tf:13-15` creates the
  backend; `:28-36` writes the operator user with `token_policies = []`
  (verified verbatim); `:48-53` binds the identity alias. D2 is `done`
  in the ledger and settled login on userpass.

- **P9 (developer token holds the Vault read grants via F11).** HOLDS.
  `developer_group.tf:78-80` grants `sys/policies/acl/*` read (line 79
  carries `read`). `:110-112` grants `secret/metadata/default/*` read.
  `:158-163` binds `developer` to the operator entity via the
  `developer` group. F11 is `done` in `.loop/ledger.json`. The grants
  arrive on the human token in `identity_policies`, not `policies`
  (comment at `:154-157`). This is the F7 to F11 / manage substitution
  the replan settled, and it is accurate.

- **P10 (deploy lacks list-jobs; manage role exists; D2 brokers only
  deploy).** HOLDS. `nomad_deploy_role.tf:13-30` grants `submit-job`,
  `read-job` and five `host-volume-*` capabilities, with no `list-jobs`
  and no node read (comment at `:1-5` states the omission is
  deliberate). `developer_group.tf:140-142` grants `nomad/creds/manage`
  read. `nomad_oidc.tf:74-78` defines the `manage` role with
  `type = "management"`. D2's `cli/src/localstack_cli/auth/broker.py:25`
  brokers only `nomad/creds/deploy`. The relayed requirement to D2 is
  stated as a precondition, not a `depends_on` edge, which is correct
  since D2 is `done` in the ledger.

- **P11 (management token is full Nomad access, a privilege widening).**
  HOLDS. `nomad_oidc.tf:74-78` `type = "management"` mints a token that
  bypasses all Nomad ACLs. The plan states the widening honestly in
  three places: Context `:101-108`, Q1 `:898-910`, Risk `:836-841`. It
  does not hide that the CLI's Nomad token can submit jobs, not just
  read. The operator's acceptance over a narrow `nomad_read_role.tf` is
  recorded.

- **P12 (api/ purity contract achievable).** HOLDS. `status` needs
  concurrent `httpx` GETs; `service --open` needs stdlib `webbrowser`
  from `commands/`; `--json` serializes dataclasses. Nothing in the
  four commands forces typer or rich below the render layer.

- **P13 (Consul token replaces the default rather than merging).**
  Grounded in `bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`
  (cited, not re-probed this pass). Consistent with P5's ACL policy.
  HOLDS.

## Most dangerous assumption

**P10/P11: that brokering `nomad/creds/manage` is the accepted path and
D2 will relay it.** This is a relayed follow-up to a done ticket (D2),
not a `depends_on` edge. If D2 never brokers `manage`, `status` and
`service` ship partial Nomad data (Vault panel works, Nomad `/v1/jobs`
403s, Consul filtered). The plan does not over-claim: it states the
precondition (Preconditions `:83-108`), the widening (Q1, Risk), and the
partial-ship fallback (Q2 options, recommendation (a)). The Vault-read
commands (`vault grants`, `secret <service>`) work fully via F11 today,
so the ticket is not blocked from being built or tested. Sound.

## Fixes applied since the first review (verified)

- **Pickup-order note (requirement 2, `:401-406`).** Consistent with
  the ledger: D4 priority 42, D3 priority 20, both `planning`, neither
  depends on the other. D4's plan at `:303-310` and `:702-706` (P11)
  confirms D4 creates `cli/src/localstack_cli/api/` under D3's contract
  and D3 adds its own functions later. The contract is the same either
  way. The `api/` directory does not yet exist on `main` (neither ticket
  has landed: `cli/src/localstack_cli/api/` is absent, only `auth/` and
  `commands/` are present), so the note is a forward statement about
  pickup order, not a claim about current tree state. Accurate.

- **Q1 option (b) rationale (`:914-916`).** The stale claim that "D4
  already claims `nomad_read_role.tf` as its own deliverable (D4:565)"
  is gone. The new rationale says D4 rejected the same option for the
  same reason: the `manage` grant already exists on the `developer`
  policy, so a parallel read policy duplicates ownership for no benefit.
  D4's current Q2 at `:600-601` says exactly this: option (b) "is
  rejected — it duplicates ownership and the operator accepted the
  management token's wider scope." The two plans are now consistent.

## Management-token privilege widening (honesty check)

The plan states the widening in three places, each plain rather than
hedged:

- Context `:101-108`: "A Nomad management token is full Nomad access,
  not read-only. Brokering it to a read-only CLI is a privilege
  widening the operator accepted over the rejected alternative."
- Q1 `:898-910`: "A management token bypasses all Nomad ACLs, so it can
  list jobs, read jobs, read nodes, and do anything else in Nomad."
- Risk `:836-841`: "Brokering a Nomad management token widens
  privilege. A management token bypasses all Nomad ACLs, so the CLI's
  Nomad token can submit jobs, not just read."

The rejected alternative (a narrow `nomad_read_role.tf`) is named, and
the reason for rejection (the grant already exists, no new policy
needed) is given. The plan does not hide the widening. Honest.

## Contract hygiene

- **Real code surface with resolved anchors.** Every `path:line` in
  section 7 resolves to the thing the plan claims:
  `auth_userpass.tf:28-36` (operator user, `token_policies = []`),
  `developer_group.tf:78-80` (`sys/policies/acl/*` read),
  `:110-112` (`secret/metadata/default/*` read),
  `:140-142` (`nomad/creds/manage` read), `:158-163` (group binding),
  `nomad_deploy_role.tf:13-30` (deploy capabilities),
  `nomad_oidc.tf:74-78` (`manage` role, `type = "management"`),
  `services.tf:318-323` (haproxy jobspec interpolation). All opened and
  confirmed verbatim. The `verify-plan` symbol warnings are
  false-positives from a matcher that expects the resource header at
  line 15, not the path block content.

- **Discovered, not assumed, gates.** `just pre_commit`
  (`justfile:18-19`) is the gate. D1 landed ruff, ruff-format, mypy
  (strict) and pytest hooks scoped to `^cli/`
  (`.pre-commit-config.yaml:37-72`), all present on `main`. The
  `cluster` marker and `addopts = "-m 'not cluster'"` are in
  `cli/pyproject.toml:31-34`. The plan's gate references match the
  repo.

- **Explicit non-goals.** Section 5 lists ten non-goals, including no
  mirror of native CLIs, no auth handling, no writes, no policy
  changes, no TUI, no Consul KV browsing. Clear.

- **Tests homed in the code surface.** Every named test file appears
  in section 7's test list, mirroring the source tree under
  `cli/tests/`. The live-cluster tests carry the `cluster` marker and
  are excluded from the default run via D1's `addopts`.

- **Forks surfaced.** Q1-Q7 carry recommendations; Q1 and Q4 are
  resolved, Q2 is an operator fork with a recommendation, Q3 is a
  relayed finding. The management-token widening is surfaced as a
  trade-off, not silently decided.

The "31/33 claims carry no path:line anchor" warning refers to prose
probe claims in Context/Requirements that cite live behavior rather
than file anchors. The create-ticket contract requires resolved
anchors for the code surface, which section 7 carries. The probe
claims are evidence the author gathered, not contract anchors, and the
live cluster re-probe in this review confirmed the load-bearing ones.

## Notes on what I could not settle

- I did not mint `nomad/creds/deploy`, `nomad/creds/manage` or
  `consul/creds/deploy`, since minting creates a Vault lease and this
  review is read-only. The Nomad 403 claims rest on policy text plus
  the live probes (the env's `NOMAD_TOKEN` is a management token and
  sees all 19 jobs and 5 nodes), not an end-to-end brokered-token
  measurement. The plan's claims about the brokered `deploy` token's
  scope are consistent with `nomad_deploy_role.tf:13-30` and Nomad's
  documented `list-jobs` requirement for `/v1/jobs`.
- P4's "zero computed `secret (...)` calls across 19 jobs" is taken on
  the plan's stated probe, not re-measured across all 19 this pass. The
  guardrail (requirement 6, test 14) makes the failure visible, so a
  false P4 does not produce a silently wrong command.

No required premise fixes. The plan is ready to leave PLANNING.