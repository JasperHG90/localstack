---
verdict: fail
---

# Plan review — D4-cli-cluster-tui (pass `plan-validator`)

Plan reviewed: `.loop/plans/D4-cli-cluster-tui.md`
sha256 computed locally: `4cac00a7857d6e2410ea9eee92b6c358493a89fd4101ecb918e4adcd2a681535`

**Briefing gap, recorded:** the briefing did not supply the plan fingerprint.
No `plan:` line is written regardless, because this is a `fail` and a failing
verdict must never carry an authorizing hash. The hash above is for the
operator's record only. It authorizes nothing.

Live cluster probed during this review (read-only GETs, 2026-07-31).

## Premise verdict: BROKEN

The plan's headline question is "is my job running", and its answer is
`GET /v1/jobs` plus `JobSummary`. Measured on the live cluster today, that
data source cannot answer it. `JobSummary.Summary.<group>.Failed` and `.Lost`
are **cumulative lifetime allocation counters, not current state**. Eight of
the fourteen healthy `service` jobs carry `Failed > 0` right now, two carry
`Lost > 0`, and every one of them is `Status: running` with its full desired
allocation count running. The plan's own health rule (§8 test table, "a job
with `Failed > 0` is unhealthy") therefore reds 8 healthy jobs. Add the 3
periodic/system jobs the plan already caught and **11 of 19 jobs render as
broken on a fully healthy cluster**. The plan calls exactly this outcome
"worse than no panel because a developer stops trusting it" (`plan:317`) and
then bakes it into requirement 1, requirement 2's cut justification, and the
parametrized test table. Separately, `/v1/jobs` carries no desired count at
all, so requirement 1's "running/desired" is not computable from the one call
the plan budgets for it.

Layered on that: Q3's resolution assumes D3 lands first, but the harness
priority ordering picks D4 first; Q2's resolution parks this ticket's Nomad
read role in a `blocked` ticket with a BROKEN premise and no `depends_on`
edge; and §7 Code surface and §10 Subtickets still describe the
pre-resolution plan, instructing the implementer to build the exact file the
resolutions forbid.

## Per assumption

### P1 — Q1: D1 and D2 are registered, the `depends_on` edge stands. HOLDS

`.loop/ledger.json` carries `D1-cli-package-skeleton` (`planning`) and
`D2-cli-login-broker-tokens` (`planning`, deps `[D1, F2]`). D4's ledger
`dependencies` is `["D2-cli-login-broker-tokens"]`, matching front-matter
`plan:3`. The Q1 resolution at `plan:450-452` is accurate.

### P2 — Q2: parking the Nomad read role in F7 leaves D4 implementable. BREAKS

Three sub-claims, checked separately.

The handoff itself is real. `F7-foundation-deployer-vault-oidc-login.md:554-580`
carries the section "F7 also owns the human read roles (added 2026-07-31)"
naming `D4-cli-cluster-tui` Q2 and specifying `list-jobs`, `read-job`, node
read, plus a `vault_nomad_secret_role`. The reasoning also checks out: D2's
Terraform guardrail is real (`D2-cli-login-broker-tokens.md:168`), and the
`developer` policy warning is corroborated at `F7:576-578`. So far, HOLDS.

The dependency is unmet and invisible to the ledger. F7 is `stage: blocked`,
`blocker.code: unresolved-design-fork`, reason "plan review BROKEN/fail". Its
verdict file opens `verdict: fail` with "Premise verdict: BROKEN". D4's
`dependencies` list does not contain F7. The loop's `PLANNING -> READY` gate
and the `advance implementing` gate both read `dependencies`, so neither can
see this edge. D4 will be handed to an implementer while the token it needs
does not exist and cannot currently be built.

The eval can no longer catch the consequence. Row 7 of
`.loop/evals/D4-cli-cluster-tui.md:34` was re-pointed to "Score it from a
fixture, not from whichever token happens to be live at implementation time".
Verified live: `GET /v1/jobs` and `GET /v1/nodes` both return **403**
tokenless, and `nomad_deploy_role.tf:17-29` grants only `submit-job`,
`read-job` and `host-volume-*`. So the shipped panel's two headline widgets
say "denied" while every eval row scores 100%. That is Q2's own option (c),
the one it rejected as "not worth shipping" (`plan:383-384`), arrived at by a
different route. It is the same defect shape the F7 verdict flagged there: an
eval row certifying a broken result green.

### P3 — Q3: D3 lands first, so D4 imports `cli/localstack/api/`. BREAKS

`plan:466-470` states "D3 owns the fetch layer; this ticket imports it" and
treats D4-first as a remote contingency ("If pickup order **ever** puts this
ticket first"). It is not a contingency, it is the default.

`loop_harness/ledger.py:112` documents `priority` as "soft ordering
preference (higher = sooner)", and `loop_harness/deps.py:197` and `:266` sort
by `-priority`. D4's priority is **42**; D3's is **20**. Both depend only on
D2 and neither depends on the other, so the graph leaves the order free and
priority decides. The harness picks **D4 before D3**.

The rest of the Q3 claim HOLDS: `.loop/evals/D3-cli-read-commands.md:40` does
score the reuse contract by grepping `cli/localstack/api/` for typer and rich
imports, exactly as `plan:466-468` says.

Consequence: the implementer will reach `cli/localstack/api/` and find
nothing, with §7 of this plan pointing at the forbidden `cluster_api.py` and
no anchor into D3's contract. The escape hatch at `plan:469-470` is one
sentence at the end of the plan, contradicted by §7 and §10.

### P4 — the package path in §7 Code surface. BREAKS

Three-way disagreement across the tickets that share this package:

- D1, the ticket that decides the layout: `cli/src/localstack_cli/`
  (`D1-cli-package-skeleton.md:168`, `:170`, `:173`, `:213`).
- D3 and D4's own eval marker: `cli/localstack/api/`
  (`D3-cli-read-commands.md:254`, eval rows at `.loop/evals/D4-cli-cluster-tui.md:29`,
  `:36`, `:40`).
- D4's §7: `cli/src/localstack/tui/cluster.py` (`plan:203-219`).

The plan body hedges this ("D1's actual package name wins", `plan:198-200`),
which is the right posture. The **eval marker does not hedge**, and that is
the checkable defect. Under D1's actual layout, three eval rows pass
vacuously because a grep over a path that does not exist returns no match and
"no match" is the expected result: row 2 (`grep -rn "deployments/"
cli/localstack/`), row 11 (`grep -rniE "userpass|auth/token|session\.json|
VAULT_TOKEN" cli/localstack/tui*`) and row 13 (token values). Row 8's
`ls cli/localstack/` errors rather than failing informatively.

### P5 — `JobSummary` answers job health; `Failed > 0` means unhealthy. BREAKS

**This is the most dangerous assumption.** Probed live 2026-07-31 against
`GET /v1/jobs`, every job below `Status: running` with its desired count
running:

    grafana      service  running  Running=1  Failed=4   Lost=0  Complete=11
    haproxy      service  running  Running=1  Failed=8   Lost=0  Complete=28
    loki         service  running  Running=1  Failed=5   Lost=0  Complete=1
    memex        service  running  Running=1  Failed=31  Lost=0  Complete=35
    minio        service  running  Running=1  Failed=3   Lost=2  Complete=10
    phoenix      service  running  Running=1  Failed=15  Lost=2  Complete=10
    postgres     service  running  Running=1  Failed=6   Lost=0  Complete=6
    prometheus   service  running  Running=1  Failed=4   Lost=0  Complete=8

`GroupCountSum` for `grafana` is 1 and `/v1/job/grafana` reports
`TaskGroups[0].Count = 1`, so 1 running is full health. These counters count
every allocation the job has ever had in that state, across restarts and
redeploys. They are not current state.

Three places in the plan depend on the false reading:

- `plan:145` — requirement 1 names "running/desired plus failed/lost from
  `JobSummary`" as the job health answer.
- `plan:282` — the parametrized test asserts "a job with `Failed > 0` is
  unhealthy". That test would pass and the panel would still be wrong.
- `plan:149-152` — requirement 2 cuts the "recent failed allocations" panel
  because "`JobSummary.Failed`/`Lost` on the job row already answers it". A
  lifetime counter cannot answer "did something fail recently". The cut may
  still be right, but this justification for it is false.

The eval cannot fail on this. Row 3
(`.loop/evals/D4-cli-cluster-tui.md:30`) fixtures a periodic parent, a system
job, and a service job at 2 of 3 desired. No row exercises a healthy service
job carrying a non-zero cumulative `Failed`, which is 8 of the 14 service
jobs on the real cluster.

### P6 — `GET /v1/jobs` returns everything the job widget needs in one call. BREAKS

`plan:41-43` claims that call yields `JobSummary.Summary.<group>.{Running,
Failed,Lost,Queued,Starting}` plus `Type`, `Periodic`, `Status`. All of that
is present and verified. What is **absent** is any desired count. The full
key set of a `/v1/jobs` element, probed live:

    CreateIndex Datacenters ID JobModifyIndex JobSummary ModifyIndex
    Multiregion Name Namespace NodePool ParameterizedJob ParentID Periodic
    Priority Status StatusDescription Stop SubmitTime Type

So requirement 1's "running/desired" needs a per-job `/v1/job/<id>` read, 14
extra calls every refresh, which also falsifies Q4's "four small calls every
5 seconds against a five-node cluster is negligible" (`plan:472-473`).

**Constructive fix, verified live:** `GET /v1/jobs/statuses` returns 200 and
carries, in one call, `GroupCountSum` (the desired count), an `Allocs` array
of the job's **current** allocations with `ClientStatus` and
`DeploymentStatus.Healthy`, `ChildStatuses` for periodic parents, and
`LatestDeployment.Status`. That is current state rather than lifetime
counters, and it fixes P5 and P6 together in a single request.

### P7 — periodic parents report `Running: 0` while healthy. HOLDS

Probed live: `acme` returns `Children: {Dead: 10, Pending: 0, Running: 0}`
and `Summary.acme.Running == 0`, with `Status: running`, `Periodic: true`.
`backup-minio` and `backup-postgres` behave the same
(`Children.Dead` 119 and similar). Requirement 4's type-branching rule
(`plan:155-157`) is correct and well motivated. Note that
`Summary`'s key is the **task group** name, not the job name: `backup-minio`
keys on `backup`. The plan writes `Summary.<group>` and gets this right.

### P8 — the cluster inventory claims. HOLDS, re-verified today

All of `plan:39-81` re-probed live 2026-07-31: **19 jobs** (14 `service`, 3
`batch`, 2 `system`); `acme`, `backup-minio`, `backup-postgres` periodic;
`node-exporter`, `promtail` system; `talat-shim` and `talat-consumer` both
live and both absent from `deployments/` (confirmed, `grep -rl talat` finds
nothing); **5 nodes** all `ready`/`eligible`/`Drain: false` (`firebat`,
`orangepi4a`, `radxa-dragon-q6a`, `ubuntu`, `jetson-orin-nano`); **24
allocations, all `ClientStatus: running`**. The `talat-*` trap and
requirement 3 are well founded.

### P9 — Q7: tokenless Consul reads work only via `tokens.default`. HOLDS

Strongly evidenced. Config confirmed: `consul.hcl.j2:27` is
`default_policy = "deny"`, `:29-32` is the `tokens` block, and `:31` sets
`default` to the same value as `agent`. Three probes separate the mechanism
from a mere "Consul is open":

- tokenless `GET /v1/health/state/any` returns **200 with 41 checks, 0
  critical** (matching `plan:75-76` exactly).
- the same call with an explicit all-zeros token returns **403**, so it is
  not that Consul ignores ACLs.
- tokenless `GET /v1/acl/tokens` returns **403**, so the default identity is
  the agent policy, not management.

That is precisely the "the agent authenticates tokenless HTTP calls as
itself" claim at `plan:77-78`, and the resolution's plan to comment the
dependency and degrade to "denied" if it tightens (`plan:483-486`) is sound.
`/v1/agent/members` returns 5 members, matching `plan:73`.

### P10 — Vault tokenless, Nomad token-required. HOLDS

Probed: `GET /v1/sys/seal-status` returns **200** with no auth header
(`{"sealed": false, "t": 3, "n": 5}`, shamir 3-of-5 as claimed at
`plan:63`). `GET /v1/jobs` and `GET /v1/nodes` return **403** tokenless. ACL
enabled confirmed in `nomad.hcl.j2` (see P14 for the anchor). The "one panel
that always renders" design at `plan:67-69` is correct.

### P11 — Q4's refresh contract is achievable in Textual workers. HOLDS on mechanism, with two caveats

Probed by installing the library: textual **8.2.8** exposes `App.set_interval`
and `App.run_worker`, and the `@work` decorator takes `group`, `exclusive`
and `thread`. `httpx.Timeout(2.0)` is per-request. So four `@work(group=...,
exclusive=True)` workers driven by `set_interval(5, ...)`, each with a 2s
httpx timeout, is a straightforward build. `pytest-textual-snapshot` and
`respx` both resolve too, so requirement 10 HOLDS.

Caveat one, an eval defect: row 7
(`.loop/evals/D4-cli-cluster-tui.md:35`) fixtures Nomad answering in 5
seconds against a 2-second timeout and expects the widget to keep "its last
known value, visibly marked stale". From a cold start there is no last known
value, because the very first fetch also times out at 2s. As written the row
cannot pass. The fixture must serve one fast response before going slow, or
the expected state must include a distinct "no data yet" render.

Caveat two: the "negligible load" argument holds only if the job widget is
one call. See P6.

### P12 — Q5/Q6 addressing: on-LAN only, defaulting to 192.168.2.30. HOLDS today, BREAKS on N4

The claim is accurate today. `configure_network.yml:13-25` admits 8500, 8300,
8301, 8600, 8200, 8201, 4646, 4647, 4648 and `20000:32000` from
`192.168.0.0/16`, and `:10-11` gives `100.64.0.0/10` port 22 alone.
`services.tf:338` does hardcode `192.168.2.30:8500` as Q6 claims.

But `N4-netsec-edge-only-service-access` is `planning` with **priority 50**,
above D4's 42, so the harness schedules it **first**. Its code surface
(`N4:191-192`) narrows `from_ip` for 4646, 8200 and 8500 away from
`192.168.0.0/16`, and its own risk section says "After the change, the only
route to Nomad's API is haproxy" (`N4:214-215`) and "Terraform runs from the
devcontainer, which is on the LAN and therefore loses direct access"
(`N4:222-223`). After N4, D4's panel reaches nothing from any developer
machine, on-LAN or off, unless it goes through the HTTPS edge. Q5's "scope
this ticket to on-LAN use" and Q6's "fall back to the `192.168.2.30`
defaults" are both reasoned from a firewall state a higher-priority sibling
plans to remove. Neither ticket references the other.

The rest of Q6 HOLDS: `localstack config` is a real D2 command
(`D2-cli-login-broker-tokens.md:759-763`), so reading it rather than
inventing a format is right.

### P13 — cluster versions Nomad 1.11.3 and Vault 1.21.4. BREAKS, low severity

Live today: Vault **2.0.3** (build 2026-06-17), Nomad **2.0.4**, Consul
**2.0.2**. `plan:62` says "Build 1.11.3" and `plan:63` says "v1.21.4".
`U1-upgrade-pin-hashistack-versions.md:72-74` records installed 1.21.4-1 /
1.11.3-1 / 1.22.6-1 with candidates 2.0.3-1 / 2.0.4-1 / 2.0.2-1, so the whole
stack crossed a major version between the plan's measurement date and today.
`nomad.hcl.j2:18-22` records an unattended-upgrades restart on 2026-07-31,
which is the likely cause and is also U1's whole premise.

Low severity for D4 only because I re-verified every payload shape the plan
depends on against the live 2.x cluster (P7, P8, P9, P10) and they all hold.
The version strings are stale, not load-bearing. Worth correcting so the next
reader does not trust the date stamp on the other measurements.

### P14 — `nomad.hcl.j2` anchors. BREAKS

Three anchors do not resolve to what the plan says:

| Plan claim | Actual |
| --- | --- |
| `nomad.hcl.j2:11-14` server block (`plan:58`, `plan:142`) | lines 11-14 are an `advertise` comment; the `server` block is **29-32** |
| `nomad.hcl.j2:20-30` client block (`plan:58`) | `client` block is **38-48** |
| `nomad.hcl.j2:16-18` ACL on (`plan:72`) | `acl` block is **34-36** |

Cause is commit `c744b92` ("pin nomad advertise addresses"), which inserted a
17-line comment and `advertise` block above the server stanza. Confirmed by
`git show c744b92^`, where `server {` sat at line 11 exactly as the plan
says. The underlying facts (`bootstrap_expect = 1`, ACL enabled, server is
also a client) are all still true, so this is anchor drift, not a false
claim.

### P15 — repo gates, rule anchors, dependency claims. HOLDS

Every other anchor resolved. `.loop/config.json` `gates` is `["just
pre_commit"]`. `justfile:18-19` runs `pre-commit run --all-files`;
`justfile:22-23` is `unseal_vault`; `justfile:30-32` is `worktree_setup`;
`scripts/unseal_vault.sh` is 13 lines. `.pre-commit-config.yaml` is 33 lines
with `detect-private-key` at `:12` and no ruff or mypy hook, as claimed.
`.github/workflows/` holds only `claude-ollama.yaml` and
`hermes-interactive.yaml`. `requirements.txt:3` is `httpx`. `docs/monitoring.md:12-15`
and `:48-56` say exactly what `plan:103-107` claims.
`nomad_deploy_role.tf:1-12`, `:17-29` and `:32-41` all resolve.
`haproxy.hcl:5-9` is the `firebat` constraint. `services.tf:338` is the
hardcoded Consul address. `python-testing.md:6-10`, `:26-32`, `:89`,
`:112-117` and `uv-installer.md:6-8` all resolve.

## Most dangerous assumption

**P5.** If `JobSummary.Failed`/`Lost` are current state, the plan works. They
are not; they are lifetime counters, and 8 of 14 healthy service jobs carry
non-zero values right now. Get this wrong and the panel reds a majority of a
healthy cluster on day one, which by the plan's own words (`plan:317`) makes
it worse than shipping nothing. It is the most dangerous because it is the
one failure no eval row can catch and no reviewer sees without querying the
live API, since the fixtures are authored from the same false model.

## Required fixes

1. **Replace the job data source.** Drop `/v1/jobs` + `JobSummary` counters
   as the health input. Use `GET /v1/jobs/statuses`, which returns
   `GroupCountSum` (desired), `Allocs[].ClientStatus` and
   `DeploymentStatus.Healthy` (current), `ChildStatuses` (periodic), and
   `LatestDeployment.Status`, all in one call. Rewrite requirement 1
   (`plan:145`), requirement 4 (`plan:155-157`) and the test table
   (`plan:282`). Delete "a job with `Failed > 0` is unhealthy".
2. **Re-justify or re-open requirement 2's cut** (`plan:149-152`). Lifetime
   `Failed`/`Lost` do not answer "did something fail recently". Keep the cut
   if you want, on a different reason.
3. **Add an eval row that can fail on P5.** Fixture a healthy `service` job
   at full desired count carrying `Failed: 31` and `Lost: 2`, taken from live
   `memex` and `phoenix`, and require it to render healthy.
4. **Settle the F7 dependency out loud.** Either add
   `F7-foundation-deployer-vault-oidc-login` to `depends_on` (and accept that
   D4 waits on a `blocked` ticket), or state plainly in §5 and §9 that D4
   ships with 403 in both headline widgets until F7 lands, and add an eval
   row that fails on that state. Do not leave the edge as prose in a
   resolution note the ledger cannot read.
5. **Invert the Q3 ordering assumption.** Priority 42 beats D3's 20, so D4 is
   picked first. Rewrite `plan:466-470` to make D4-building-`api/` the
   primary path, and anchor it to D3's actual contract
   (`D3-cli-read-commands.md:193-194`, `:254-265`) so the implementer knows
   what shape to build.
6. **Rewrite §7 Code surface and §10 Subtickets to match the resolutions.**
   Today they still instruct the implementer to create `cluster_api.py`
   (`plan:209-211`, subtickets 3 and 5 at `plan:337-340`), which eval row 8
   fails on; to add the conditional `nomad_read_role.tf` (`plan:231-235`,
   `plan:253-255`) that Q2 moved to F7; and to "register the `status`
   subcommand" (`plan:226`, `plan:346`), a name that now belongs to D3. Also
   drop the stale subticket 1 ("Settle Q1-Q3 with the operator") and the Q2
   references at `plan:19`, `plan:130` and `plan:302`.
7. **Fix the package path, in the eval marker especially.** D1 establishes
   `cli/src/localstack_cli/`; D3 and this eval assume `cli/localstack/`; §7
   says `cli/src/localstack/`. Pick one and make D1 the source of truth. The
   plan body's hedge is fine; the eval's hard-coded greps are not, because
   three rows pass vacuously against a path that does not exist.
8. **Fix eval row 7's cold start.** Serve one fast response before the slow
   one, or add "no data yet" as a distinct expected render. As written no
   implementation can satisfy "keeps its last known value".
9. **Note the N4 interaction.** N4 has higher priority and removes direct LAN
   access to 4646, 8200 and 8500 (`N4:191-192`, `N4:214-215`). Q5 and Q6 were
   both reasoned from the pre-N4 firewall. Decide whether D4 addresses the
   HTTPS edge, and say so.
10. **Repoint the `nomad.hcl.j2` anchors** to 29-32 (server), 34-36 (acl) and
    38-48 (client), and correct the version claims at `plan:62-63` to Nomad
    2.0.4, Vault 2.0.3, Consul 2.0.2.
