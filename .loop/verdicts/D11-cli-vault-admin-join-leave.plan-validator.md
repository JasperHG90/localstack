---
verdict: fail
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: de5bb531820574564c18a2e99944c87b54eba70f30397a944363dacae52b6d10
fix_sections: front-matter, 6, 7, 8, 9, 10, premises
citations:
  deployments/infrastructure/roles.tf:127 = resource "vault_identity_group" "admin" {
  deployments/infrastructure/roles.tf:130 =   policies                   = [vault_policy.admin.name]
  deployments/infrastructure/roles.tf:131 =   external_member_entity_ids = true
  deployments/infrastructure/roles.tf:134 =     description = "Break-glass. Join for the incident, leave after. Membership is not managed by Terraform; see docs/cluster-roles.md."
  deployments/infrastructure/developer_group.tf:7 = ### The holder can write `identity/*` and `sys/policies/acl/*`, so they can
  deployments/infrastructure/developer_group.tf:103 =     path "identity/*" {
  deployments/infrastructure/developer_group.tf:104 =       capabilities = ["create", "read", "update", "delete", "list"]
  docs/cluster-roles.md:56 = > **Leaving yourself in `admin` after an incident is invisible to every
  docs/cluster-roles.md:70 = **The list is REPLACED, not appended to.** The join and leave commands below
  docs/cluster-roles.md:77 = vault read -field=member_entity_ids -format=json identity/group/name/admin \
  docs/cluster-roles.md:82 = vault read -field=entity_id auth/token/lookup-self
  cli/src/localstack_cli/auth/vault.py:3 = Five endpoints, over `urllib`. D1 chose the stdlib and a real HTTP server in
  cli/src/localstack_cli/auth/vault.py:68 = def _request(
  cli/src/localstack_cli/auth/vault.py:114 =     return f"Vault returned HTTP {status} for {path}{detail}"
  cli/src/localstack_cli/auth/vault.py:155 = def read_creds(addr: str, token: str, path: str) -> dict[str, Any]:
  cli/src/localstack_cli/auth/vault.py:171 =     `identity_policies` instead. Reporting only `policies` tells a developer
  cli/src/localstack_cli/commands/vault.py:18 = from localstack_cli.commands._common import fail, refreshed_session, require_session, warn
  cli/src/localstack_cli/commands/vault.py:23 = app = typer.Typer(no_args_is_help=True)
  cli/src/localstack_cli/main.py:57 =         # D3's read commands. `vault` is a group because it will hold more
  cli/src/localstack_cli/main.py:59 =         "status": "localstack_cli.commands.status:app",
  cli/src/localstack_cli/main.py:62 =         "vault": "localstack_cli.commands.vault:app",
  cli/src/localstack_cli/commands/breakglass.py:10 = - No read of `VAULT_TOKEN`, `VAULT_UNSEAL_KEY_*`, `NOMAD_TOKEN`,
  cli/src/localstack_cli/commands/breakglass.py:12 = - No subprocess, no SSH, no `vault`/`nomad`/`consul`/`ansible`/`terraform`.
  cli/src/localstack_cli/commands/breakglass.py:18 = to printing the whole runbook rather than raising. The command always exits
  cli/tests/conftest.py:3 = Every test runs against a real HTTP server or a real closed port, never a
  cli/tests/fixtures/cluster.py:3 = The client code is a thin wrapper over `urllib`, so mocking the transport
  cli/tests/fixtures/cluster.py:80 = HEALTHY_ROUTES: dict[str, tuple[int, bytes]] = {
  cli/tests/fixtures/cluster.py:116 =     def requests_for(self, path: str) -> list[Request]:
  cli/tests/auth/test_vault.py:64 =     assert [item.method for item in sent] == ["POST"]
  cli/tests/commands/test_read_commands.py:524 = def test_vault_has_exactly_one_subcommand() -> None:
  cli/tests/test_read_guardrails.py:73 = def test_the_api_layer_is_read_only() -> None:
  cli/pyproject.toml:31 =     "respx>=0.23.1",
  .pre-commit-config.yaml:58 =         entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests
  .pre-commit-config.yaml:68 =         entry: uv run --project cli pytest cli/tests
  README.md:26 = | CLI | `cli/` | Python — the `localstack` cockpit. `login`, `logout`, `whoami`, `env`, `token`, `config`, `breakglass`, `deps`, `monitor`, `status`, `service`, `secret` and `vault grants` |
  docs/cli-read-commands.md:92 = ## `vault grants <job>`
---

# Plan review — D11-cli-vault-admin-join-leave

## Deterministic floor

`loopctl verify-plan D11-cli-vault-admin-join-leave` returns clean:

    valid: warn: provenance: premise Q1 measured against probe live cluster
    2026-09-03 at vault token capabilities identity/group/name/admin returned
    create, delete, list, read, update

No hard-fail, so the deep pass ran. Plan file sha256 recomputed as
`cc8230a394c712c26be4f288a0a25ff2e2a9e1739c7cb361a59d619db5a58f85`, matching
the briefed fingerprint. It is omitted from the header above because this is
a `fail`.

## Premise verdict

**BROKEN.**

The ticket's shape is right and its motivation is real. Two of its six stated
premises are false against the live cluster as of 2026-09-03T07:53Z, and one
premise the author never wrote down (that respx can mock the client this plan
extends) is false against the repo. One of the false ones, P6, is the author's
own flagged UNCERTAIN, and it settles against the plan: R5 as written would
ship a warning that is not true.

Scratch created at
`.loop/scratch/D11-cli-vault-admin-join-leave.plan-validator/`.

## Per-assumption findings

### P1 — HOLDS, but on grounds the plan never states

`deployments/infrastructure/developer_group.tf:103`
> path "identity/*" {

`deployments/infrastructure/developer_group.tf:104`
> capabilities = ["create", "read", "update", "delete", "list"]

Probe re-run live, 2026-09-03T07:53Z:

    identity/group/name/admin -> create, delete, list, read, update
    identity/entity/id/351f302a-ada1-0e79-15d3-e22a4be2e3e4 -> create, delete, list, patch, read, sudo, update
    sys/seal -> create, delete, list, patch, read, sudo, update

The five capabilities the plan measured are exactly the five in
`developer_group.tf:104`, and they are NOT the seven the `admin` policy's
`path "*"` yields, which the same probe shows on `sys/seal` in the same
breath. Vault picks the most specific matching rule, so `identity/*` from
`developer` beats `*` from `admin` on this path. So the capability is real,
it comes from `developer`, and it does not depend on the operator's current
`admin` membership. P1 stands.

What does not stand is the framing. The front-matter premise and §9 imply the
grant rides on the session token generically, and P6 leans on
`policies ['default']` to argue the neighbouring path is denied. That is the
exact misreading `auth/vault.py:171` was written to prevent:

`cli/src/localstack_cli/auth/vault.py:171`
> `identity_policies` instead. Reporting only `policies` tells a developer

`vault token lookup` on the operator's session right now returns
`policies ['default']` AND `identity_policies ['admin', 'developer']`. The
plan quotes the first field and not the second.

**On your question 1 — no, do not raise a separate finding.** The repo already
raises it, deliberately and at length:

`deployments/infrastructure/developer_group.tf:7`
> ### The holder can write `identity/*` and `sys/policies/acl/*`, so they can

The lines around it read "THIS IS NOT A CONTAINMENT BOUNDARY, and no comment
here should say it is... they can grant themselves anything short of `root` in
three commands... That is the operator's deliberate choice: Developer and
Deployer are one role here." A `developer` who can write `identity/*` can join
themselves to `admin` and reach `path "*"` with sudo. That is a documented,
accepted design, not a discovery. It needs a citation in this plan, not a
ticket of its own.

### P2 — HOLDS

`deployments/infrastructure/roles.tf:131`
> external_member_entity_ids = true

`deployments/infrastructure/roles.tf:134`
> description = "Break-glass. Join for the incident, leave after. Membership is not managed by Terraform; see docs/cluster-roles.md."

The cited range 127-137 contains the resource, the flag and the metadata the
plan quotes. Membership is not Terraform-owned, so a write cannot conflict
with an apply.

### P3 — BREAKS

The plan: "The group is currently empty, so the first join writes a single
id. Probe, run live 2026-09-03: ... returned a null `member_entity_ids`."
Your briefing repeats it: "it is currently EMPTY".

Probe, live, 2026-09-03T07:53:41Z:

    group.last_update_time = 2026-09-03T07:42:45.610388828Z
    group.member_entity_ids = ['351f302a-ada1-0e79-15d3-e22a4be2e3e4']
    group.modify_index = 9

The group holds the operator's entity. It was written 07:42:45Z, after the
plan's probe. This is not a nitpick about a stale number: it is the live
instance of the failure the ticket exists to prevent, and it is sitting in the
cluster right now, unseen by both the plan and the briefing.

`docs/cluster-roles.md:56`
> > **Leaving yourself in `admin` after an incident is invisible to every

I made no write, so the state is unchanged and yours to decide on.

Consequences inside the plan: P3's "so the first join writes a single id" is
false; §8's manual check ("reports the real membership, which is currently
empty") would pass for the wrong reason; §9's "Not a new privilege... this
exposes no capability they lack today" is now true in a stronger and less
comfortable sense than intended. T1 as a TEST is still correct and still
earns its place; only the live-state claim behind it is wrong.

### P4 — HOLDS

`cli/src/localstack_cli/auth/vault.py:68`
> def _request(

The signature spans 68-75 and carries `method: str = "GET"`,
`token: str | None = None` and `body: dict[str, Any] | None = None`; line 80
sets `request.add_header("X-Vault-Token", token)`. The claim that the client
needs no new transport holds.

`cli/src/localstack_cli/auth/vault.py:155`
> def read_creds(addr: str, token: str, path: str) -> dict[str, Any]:

`read_creds` is a one-line `_request` wrapper, so "the same shape" holds for
the read half. The write half also needs `method="POST"` and a body, which
`_request` already supports.

### P5 — HOLDS (anchor off by one)

`cli/src/localstack_cli/commands/breakglass.py:10`
> - No read of `VAULT_TOKEN`, `VAULT_UNSEAL_KEY_*`, `NOMAD_TOKEN`,

`cli/src/localstack_cli/commands/breakglass.py:12`
> - No subprocess, no SSH, no `vault`/`nomad`/`consul`/`ansible`/`terraform`.

Your reading of `breakglass.py` is correct. The boundary is stated as
load-bearing at :8, the no-token-read rule at :10-11 and the no-subprocess
rule at :12. Join and leave need a token and issue a write, so they cannot
live there.

The always-exit-0 contract is at :18-20, not the cited :19-21:

`cli/src/localstack_cli/commands/breakglass.py:18`
> to printing the whole runbook rather than raising. The command always exits

Cited line 21 is the closing `"""`. Retarget to :18-20.

**On your question 3 — the `vault` group is the right home, with one caveat
to write down.** The group already has a callback and is not at risk of the
single-command collapse `main.py:19-21` warns about, and:

`cli/src/localstack_cli/commands/vault.py:18`
> from localstack_cli.commands._common import fail, refreshed_session, require_session, warn

all four helpers §7 promises to reuse are already imported. The caveat is that
`commands/vault.py` today is an `api/` consumer, and `api/` is fenced
read-only by a live test:

`cli/tests/test_read_guardrails.py:73`
> def test_the_api_layer_is_read_only() -> None:

Routing the write through `auth/vault.py` sidesteps that fence correctly, but
it puts two error vocabularies in one module: `grants` catches `ClusterError`
and hands it to `_session.explain`, while `admin` would catch `VaultError`.
That fork is defensible and it is not written down anywhere in the plan. See
R8 below, where it stops being cosmetic.

### P6 — BREAKS. This is the one that sinks the plan.

The plan marks one aspect UNCERTAIN: "whether Vault re-resolves group
membership for an already-issued token on its next request has not been probed
here". It has now been probed, without any write, and it re-resolves.

Probe, live, captured at
`.loop/scratch/D11-cli-vault-admin-join-leave.plan-validator/p6_evidence.txt`:

    now(UTC)=2026-09-03T07:53:41Z
    issue_time      = 2026-09-03T06:59:41.4932586Z
    creation_ttl    = 2764800
    ttl             = 2761560
    elapsed_since_issue_s = 3240
    policies        = ['default']
    identity_policies= ['admin', 'developer']
    accessor        = rK9lRdnj9XMhVNUfUJduqI3f
    group.last_update_time = 2026-09-03T07:42:45.610388828Z
    group.member_entity_ids = ['351f302a-ada1-0e79-15d3-e22a4be2e3e4']
    capabilities identity/entity/id/351f302a-ada1-0e79-15d3-e22a4be2e3e4 -> create, delete, list, patch, read, sudo, update

Read it in order. The token was issued at 06:59:41Z. `creation_ttl - ttl` is
3240 seconds, which is exactly the 54 minutes from 06:59:41Z to the 07:53:41Z
wall clock, so the TTL clock has run unbroken from issuance: this token has
never been renewed and never been reissued. The group gained the operator at
07:42:45Z, 43 minutes AFTER that issuance. And that same unrenewed token now
reports `identity_policies ['admin', 'developer']` and answers
`create, delete, list, patch, read, sudo, update` on
`identity/entity/id/351f302a-...`, the very path the plan's own P6 probe
recorded as `read` only.

`sys/capabilities-self` is evaluated server-side against the caller's
effective policy set on the request, so this is the authorization path and not
a display quirk. Vault attaches identity-group policies per request, not at
issuance.

**R5 is therefore wrong and must not ship.** "Vault resolves group policies at
token issuance, so the current token does not gain `admin` until re-login" is
false. Printing it would send the operator to re-login for nothing during an
incident, which is precisely the circle `commands/_session.py:1-15` exists to
break. T8, which asserts the output "names the re-login requirement", would
pin the false statement into the suite.

There is a true warning in the neighbourhood, and it is a different one. The
CLI caches the policy set at login:

`localstack whoami` prints `session.vault.policies`, the tuple stored by
`auth/session.py:50`, not a live lookup. So after `join`, Vault is already
convinced and `whoami` is not. Any brokered Nomad/Consul credential is a
separate lease minted under the old policy set and does not retroactively
widen either. Those are the two real caveats, and neither is "re-login before
the grant works".

### P7 (implicit, added) — BREAKS. respx cannot mock this client.

The plan never states this, and §7 and §8 rest on it entirely: §7 promises
"respx cases for the two new client functions", §8 says "Mocked with respx
against a fake Vault", and T3 says "Assert on `respx` call count".

`cli/src/localstack_cli/auth/vault.py:3`
> Five endpoints, over `urllib`. D1 chose the stdlib and a real HTTP server in

respx patches httpx transports. It cannot see `urllib.request.urlopen`.
Demonstrated, scratch at
`.loop/scratch/D11-cli-vault-admin-join-leave.plan-validator/p7_respx_vs_urllib.py`,
run with `uv run --project cli python`:

    NOT INTERCEPTED: VaultError -> cannot reach Vault at http://fake-vault.invalid:8200: <urlopen error [Errno -2] Name or service not known>
    CONTROL httpx status: 200 {'sealed': False}

The control line is the same respx mock intercepting httpx in the same
process, so this is respx working correctly and simply not reaching urllib.
respx is a real dev dependency (`cli/pyproject.toml:31`) and is used
correctly elsewhere, which is exactly why the mistake is easy: the existing
`vault grants` command tests in `cli/tests/commands/test_read_commands.py` DO
use respx, because `grants` goes through `api/`, which is httpx.

**On your question 4 — no, respx call count is the wrong mechanism here, and
the repo already has the right one.** You do not need to invent it:

`cli/tests/fixtures/cluster.py:3`
> The client code is a thin wrapper over `urllib`, so mocking the transport

`cli/tests/conftest.py:3`
> Every test runs against a real HTTP server or a real closed port, never a

`cli/tests/fixtures/cluster.py:116`
> def requests_for(self, path: str) -> list[Request]:

And the exact assertion T3 and T6 want already exists, one line, in the file
§7 names:

`cli/tests/auth/test_vault.py:64`
> assert [item.method for item in sent] == ["POST"]

That is the pattern: `cluster.requests_for("/v1/identity/group/name/admin")`,
then assert on the method list (empty or GET-only for the idempotent paths)
and on `sent[0].json()` for the written body. `Request` carries `method`,
`token` and `body`, so T2 and T4 can assert the exact membership list posted,
which is the regression that matters. Command-level tests do the same through
the `cluster_addr` fixture; `cli/tests/commands/test_auth_commands.py` is the
worked example.

### P8 (implicit, added) — BREAKS. §8's iterate command does not run.

§8: "Run the suite directly while iterating: `uv run pytest cli/tests -q` from
the repo root". There is no root manifest. Probe:

    $ ls /home/vscode/workspace/pyproject.toml
    /usr/bin/ls: cannot access '/home/vscode/workspace/pyproject.toml': No such file or directory
    $ uv run pytest cli/tests -q
    error: Failed to spawn: `pytest`
      Caused by: No such file or directory (os error 2)

The working invocation is the one the hook already uses:

`.pre-commit-config.yaml:68`
> entry: uv run --project cli pytest cli/tests

Verified green on the current tree: `496 passed, 21 deselected, 12 warnings in
59.95s`. This is not hypothetical pedantry; `.pre-commit-config.yaml:54-57`
records that this repo has already been bitten once by a tool that resolves
config from cwd, and §8 hands the implementer the broken form.

### §8 repo gate description — HOLDS

`.pre-commit-config.yaml:58`
> entry: uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests

`.loop/config.json` sets `"gates": ["just pre_commit"]`, the justfile maps
`pre_commit` to `pre-commit run --all-files`, and the four cli-scoped hooks
are ruff lint (:37-45), ruff format (:46-51), mypy strict (:52-65) and pytest
(:66-73). §8's description of the gate matches. Only the iterate command
above is wrong.

## Anchor drift in §4 and §6 (each a required fix, none fatal on its own)

- **§6 R3 — BREAKS.** The plan: "Take it from `auth/token/lookup-self`, the
  way `docs/cluster-roles.md:77-79` instructs."

  `docs/cluster-roles.md:77`
  > vault read -field=member_entity_ids -format=json identity/group/name/admin \

  Lines 77-79 are the current-members command and its python one-liner. The
  entity-id instruction is three lines further down:

  `docs/cluster-roles.md:82`
  > vault read -field=entity_id auth/token/lookup-self

  The anchor resolves and does not support. Retarget to :80-82, which also
  carries the "root token has none" sentence R3 depends on.

- **§4 `main.py:59` — drift.** The plan calls it "the lazy subcommand registry
  the group is reached through".

  `cli/src/localstack_cli/main.py:59`
  > "status": "localstack_cli.commands.status:app",

  That is the `status` entry. The `vault` entry is at :62.

- **§4 `commands/vault.py:23` — half-supported.** The plan: "the `vault` typer
  group already exists and its registration comment says it is a group
  'because it will hold more than one view'."

  `cli/src/localstack_cli/commands/vault.py:23`
  > app = typer.Typer(no_args_is_help=True)

  The group exists there. The quoted comment does not; it lives in the other
  file:

  `cli/src/localstack_cli/main.py:57`
  > # D3's read commands. `vault` is a group because it will hold more

  Split the citation: `commands/vault.py:23` for the group, `main.py:57-58`
  for the comment.

- **§4 `roles.tf:127-137`, `docs/cluster-roles.md:56-100`, `:56-58`,
  `auth/vault.py:68-99`, `breakglass.py:1-21` — all HOLD.**

## Contract hygiene

- **§7 code surface is incomplete. Four files the change must touch are
  missing.**

  `cli/tests/commands/test_read_commands.py:524`
  > def test_vault_has_exactly_one_subcommand() -> None:

  R1 deliberately overturns the invariant that test's name asserts. Its body
  only checks that `grants` is present and `mounts`/`policies`/`kv` are not,
  so it will not go red, and that is worse: a test whose name is a lie and
  whose assertions no longer match its intent survives the gate silently.

  `cli/tests/fixtures/cluster.py:80`
  > HEALTHY_ROUTES: dict[str, tuple[int, bytes]] = {

  Every test in §8 needs an `/v1/identity/group/name/admin` route here. The
  fixture is the harness §8 depends on and §7 does not list it.

  `README.md:26`
  > | CLI | `cli/` | Python — the `localstack` cockpit. `login`, `logout`, `whoami`, `env`, `token`, `config`, `breakglass`, `deps`, `monitor`, `status`, `service`, `secret` and `vault grants` |

  `docs/cli-read-commands.md:92`
  > ## `vault grants <job>`

  The command inventory and the CLI's own reference doc both enumerate
  commands. `.loop/config.json` enables a `documentation` review pass on the
  implementation, so an unlisted command comes back. `docs/cluster-roles.md`
  also prescribes the hand-rolled procedure this replaces; either update it or
  add a non-goal saying the doc stays as the fallback.

- **R1 has no producer in §8.** R1 names three commands; T1-T9 measure `join`
  and `leave` and nothing measures `status`. §9 leans on it hard: "`status`
  exists so the claim can be checked rather than trusted". Its only coverage
  is the live manual check §8 explicitly declines to score. Your four options:
  `widen-surface` (add a T for `status` on empty, populated and
  caller-is-a-member), `split-ticket`, `drop-requirement`, or
  `declared-proxy`. I do not pick one.

- **R8 has no producer for "names the capability needed".**

  `cli/src/localstack_cli/auth/vault.py:114`
  > return f"Vault returned HTTP {status} for {path}{detail}"

  That is what a `VaultError` 403 says: status and path, no capability, and no
  live-token-versus-dead-token split. The repo's producer for exactly that
  sentence is `commands/_session.py:explain` over
  `api/errors.MissingCapability`, and §7 routes around it. Either name the
  mapping code in §7 or say in §6 that R8's message is hand-written at the
  command layer and why `explain` is not reused. Same four options as above.

- **Discovered gates, non-goals, tests homed, forks surfaced — all clean.**
  §5 states five real non-goals. Every named test has a file. Q1-Q3 carry
  recommendations. §8's gate description matches `.pre-commit-config.yaml`.

- **Observation, advisory only.** `cli/tests/auth/test_vault.py` in §7 is
  reached by R2 and R3; `cli/tests/commands/test_vault_admin.py` by R1, R2,
  R4, R5, R6, R7. No §7 file is unreached.

- **Observation.** R2's read-modify-write has no compare-and-swap. The group
  response carries `modify_index` (observed: 9), and the plan writes back
  unconditionally. Two concurrent joins evict one another. Single-operator lab,
  so this is a note, not a fix.

## On your question 5 — the CLI, not a justfile recipe

Keep the non-goal. A recipe would be a third copy of the read-modify-write
(the doc has one, the operator's fingers have one), it gets no mypy and no
tests, and §8's T2 and T4 are the whole reason this ticket is worth doing. The
justfile's own recipes are one-liners (`list_secrets`, `get_secret`); a bash
read-modify-write over a comma-joined list would be the largest and most
dangerous thing in that file. Your argument is right; it just needs the
citation above rather than assertion.

## Most dangerous assumption

**P6.** If group policies were resolved at issuance, R5's warning would be the
command's most valuable line. They are not, and the live probe settles it:
an unrenewed token issued at 06:59:41Z carries the `admin` policy granted at
07:42:45Z. Shipping R5 means the command's headline advice is false, and T8
locks it in. Everything else on this list is a citation or a harness swap;
this one changes what the command says to a human mid-incident.

## Required fixes

1. **§6 R5 and premises P6 — rewrite.** Strike "Vault resolves group policies
   at token issuance, so the current token does not gain `admin` until
   re-login." Replace with the measured behavior: the grant is live on the
   next request, no re-login needed. If a caveat is still wanted, make it the
   true one: `localstack whoami` shows the policy set cached at login
   (`auth/session.py:50`) and will look stale, and brokered Nomad/Consul
   leases were minted under the old set. Cite the probe in P6
   (issue_time 06:59:41Z, group last_update_time 07:42:45Z,
   `creation_ttl - ttl` = 3240s proving no renewal, resulting
   `identity_policies ['admin','developer']`).
2. **§8 T8 — rewrite** to assert whatever R5 becomes. As written it pins a
   false claim.
3. **Premises P3, §8 manual check, §9 — correct the live state.** The group
   currently holds `351f302a-ada1-0e79-15d3-e22a4be2e3e4`, written
   2026-09-03T07:42:45Z. Decide separately whether to leave now; I did not
   touch it.
4. **§7 and §8 — replace respx with the FakeCluster harness.** §7's "respx
   cases", §8's "Mocked with respx against a fake Vault" and T3's "Assert on
   `respx` call count" all become the `cluster` / `cluster_addr` fixtures and
   `cluster.requests_for("/v1/identity/group/name/admin")`, following
   `cli/tests/auth/test_vault.py:61-65`.
5. **§8 — fix the iterate command** to
   `uv run --project cli pytest cli/tests -q`.
6. **§7 — add four files:** `cli/tests/fixtures/cluster.py` (new route),
   `cli/tests/commands/test_read_commands.py:524` (rename/retarget
   `test_vault_has_exactly_one_subcommand`), `README.md:26` and
   `docs/cli-read-commands.md`. Decide `docs/cluster-roles.md` explicitly:
   update or non-goal.
7. **§10 — fold #6 into the subtickets.** Subticket 1's file list needs
   `cli/tests/fixtures/cluster.py`; subticket 2's needs the doc and README
   edits.
8. **§6 R3 — retarget the anchor** from `docs/cluster-roles.md:77-79` to
   `:80-82`.
9. **§4 — retarget two anchors:** `main.py:59` to `:62` (and `:57-58` for the
   quoted comment), and split `commands/vault.py:23`.
10. **Premises P5 — retarget** `breakglass.py:19-21` to `:18-20`.
11. **Front-matter, premises P1, §9 — ground the capability claim.** Cite
    `deployments/infrastructure/developer_group.tf:103-104` as the source of
    `create, delete, list, read, update`, and
    `developer_group.tf:6-10` for why that is deliberate. Drop the implication
    that the grant rides on `default`; the same probe that produced P6's
    `policies ['default']` also returned `identity_policies` and the plan
    quotes only the first, which `auth/vault.py:165-172` warns against by name.
12. **§8 — resolve R1's missing producer** (`admin status` has no test) and
    **§6/§7 — resolve R8's** ("names the capability needed" has no producer).
    Four options each: `widen-surface`, `split-ticket`, `drop-requirement`,
    `declared-proxy`. Your call, not mine.

Fixes 1-5 are the ones that would otherwise reach an implementer as
instructions that cannot be followed or should not be. The rest are citation
work.

## Scratch

Scratch created at
`.loop/scratch/D11-cli-vault-admin-join-leave.plan-validator/`, holding
`p6_evidence.txt`, `p7_respx_vs_urllib.py` and `findings.json`. Retained
deliberately: `p6_evidence.txt` is the captured live probe behind the P6
finding and `findings.json` is the ledger the next cycle reads.
WARN — scratch artifact left at
`.loop/scratch/D11-cli-vault-admin-join-leave.plan-validator/`.
No repo file outside this verdict and that directory was written, and no
cluster state was changed.
