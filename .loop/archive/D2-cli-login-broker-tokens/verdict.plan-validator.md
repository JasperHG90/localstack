---
verdict: pass-with-required-fixes
plan: 120784fa3859f5ac9f2ca67552a649197732c8e966db41e8a107a65a1315b0c2
---

# D2-cli-login-broker-tokens — plan review (re-run after the 2026-08-02 edits)

Fingerprint recomputed with `sha256sum`: matches the briefing
(`120784fa…b0c2`). The prior passing verdict bound `cba65704…8775` and is
stale.

## Premise verdict: PARTIALLY SOUND

The ticket's core premise is sound and I re-measured all of it against the
live cluster: a `userpass` Vault session that eagerly brokers
`nomad/creds/deploy` and `consul/creds/deploy`, caches them, and hands them
out through `env` and `token`. Every load-bearing measurement in §4 still
holds today.

The three edits under review are a different story. The `admin` procedure
itself is correct and non-destructive, which was the sharpest thing to check
and it passed. But the resolution did not propagate into the two sections
that decide what actually ships (§7's doc spec and §10's subticket 11), the
one argument the plan advances for preferring `admin` over the throwaway is
false, and §9 carries three broken anchors and two stale counts. Separately,
D1 landed on `main` since the last review and shipped an HTTP and test
harness that §7, §8 and Q2 do not know exists.

All of it is fixable in prose. None of it blocks implementation once fixed.

## Per assumption

### The three edits under review

**P1 — F14's `admin` grants what §9 claims (list and revoke token
accessors). HOLDS.**
`vault policy read admin` on the live cluster returns `path "*"` with
`["create","read","update","patch","delete","list","sudo"]`, matching
`deployments/infrastructure/roles.tf:31-116`. `vault read
identity/group/name/admin` returns the group live, `policies [admin]`,
`id d40f1623-…`. `vault policy read default` names none of
`auth/token/accessors`, `auth/token/lookup-accessor` or
`auth/token/revoke-accessor` (grep for `accessor` hits only a comment at
`:84`), so nothing more specific shadows the glob on those three paths.
§9's claim at plan `:927-931` is correct.

**P2 — `admin` membership survives `terraform apply`. HOLDS.**
`roles.tf:131` sets `external_member_entity_ids = true`, and the header at
`roles.tf:118-126` states the intent. `docs/cluster-roles.md:45-51` records
the same property as measured against an apply that really writes the group.
The group exists live with the Terraform-set metadata, so the apply
succeeded against the pinned provider (`providers.tf:7-10`, `~>5.3.0`).

**P3 — a `default`-only token is denied `vault list auth/token/accessors`,
an `admin` token is allowed. HOLDS by derivation; the direct probe is
UNCERTAIN.** I could not re-run the plan's measurement read-only: it needs a
`default`-only token and minting one is a write. What I can confirm is both
necessary conditions. `default` grants nothing on that path and Vault is
default-deny, and `admin`'s glob carries `sudo`, which that endpoint
requires. Sound but derived, not re-measured.

**P4 — §9's join/leave procedure is non-destructive. HOLDS, with one gap.**
The snippet at plan `:934-942` reads the current membership first and passes
`member_entity_ids="<current>,<you>"` to join and `"<current-without-you>"`
to leave. It does not reintroduce the evict-everyone bug: the write does
replace the list, and the snippet says so in its own comment. It matches
`docs/cluster-roles.md:70-94`.

The gap is the empty-group case. `vault read identity/group/name/admin`
returns `member_entity_ids []` right now, so the first responder to follow
D2's snippet literally types `member_entity_ids=",<your-id>"` with a leading
comma. `docs/cluster-roles.md:84-87` handles this explicitly ("If the group
is empty, pass your id alone, with no leading comma"); D2's snippet does
not, and D2's snippet is the one a responder reads mid-incident. It also
says "Three commands" above four commands.

**P5 — the `depends_on` edge to `F14-foundation-role-taxonomy` is real.
PARTIALLY HOLDS.** It is real in §9, which now leads with a procedure that
cannot exist without `vault_policy.admin` and `vault_identity_group.admin`.
F14 is `done` and merged (`5469d6c`), so the edge costs nothing and blocks
nothing. But D2 ships no `deployments/` change (§5), so the only artifact
that could consume F14 is `docs/cli-login.md`, and see P6: the spec for that
doc still describes the throwaway. As written, the edge is real in the
reasoning and decorative in the deliverable.

**P6 — the Q-relay resolution is internally consistent and nothing else
assumes the unresolved state. BREAKS.** Q-relay at plan `:1319-1322` says
"§9 leads with the `admin` procedure; the throwaway is not the primary
path". Two places did not get the memo, and both are what an implementer
builds from:

- §7's `docs/cli-login.md` bullet (plan `:640-650`) specifies the doc's
  revocation content as "three credentials; `logout` and an accessor revoke
  each end all three by cascade, and the accessor revoke needs no root; if
  neither is available it is cut-then-delete". No mention of `admin`.
- §10 subticket 11 (plan `:1157-1162`) says the doc must establish "that
  **neither needs root** — a `developer` can write itself the accessor
  policy in §9 and run it". That is the throwaway route stated as the
  answer.

An implementer following §7 and §10 ships a doc with no `admin` in it, which
is the state the operator resolved away from.

**P7 — "a `terraform apply` mid-incident silently strips the hand-built
grant", the sharp reason Q-relay gives for preferring `admin`. BREAKS.**
Plan `:982-986` and Q-relay `:1347-1350` both assert this, citing
`developer_group.tf:144`. The claim only holds if the responder attaches the
accessor policy to the `developer` **group**, and §9 at plan `:961` forbids
exactly that: "Attach that policy to a THROWAWAY ENTITY, never to the
`developer` group." A throwaway policy plus a throwaway entity plus a
throwaway userpass user are all invisible to Terraform, so no apply touches
them. `auth_userpass.tf:38-44` shows the only Terraform-managed entity is
`operator`, and it is not what the procedure uses.

This is a leftover from the draft that attached to the group. The resolution
itself survives: `admin` still wins on fewer commands, no teardown order
whose mistakes leave live credentials behind, and no orphan policy. But the
argument as stated is false, and it is the one the plan calls "the sharp
one".

**P8 — §9's `developer_group.tf` anchors resolve. BREAKS, three of them.**
G2 (`0882560`) added a `nomad/creds/manage` block and shifted the file.
Measured against `main`:

| Plan cites | For | Actually at that line |
|---|---|---|
| `developer_group.tf:141-147` (plan `:884`) | the group binding policies at request time | `nomad/creds/manage` and `consul/creds/deploy` blocks |
| `developer_group.tf:123-129` (plan `:910`) | read on both creds paths | `nomad/creds/deploy` only; consul is at `:144` |
| `developer_group.tf:144` (plan `:983`) | `policies` managed as a single-element list | `path "consul/creds/deploy" {` |

Correct anchors: the group resource is `developer_group.tf:158-164`,
`policies = [vault_policy.developer.name]` at `:161`, `nomad/creds/deploy`
at `:123`, `consul/creds/deploy` at `:144`.

**P9 — the accessor counts in §9. BREAKS (drift).** The plan states "20
accessors, measured 2026-08-02" broken down as 14 workload, 1 root, 5
`userpass` (plan `:973-976`), and "Five live accessors share `path
auth/userpass/login/operator`" (`:987-996`). Live right now:
`vault list auth/token/accessors` returns **25**, and looking each one up by
accessor gives **10** at `auth/userpass/login/operator`. The argument gets
stronger, not weaker, so nothing collapses. But these numbers are destined
for `docs/cli-login.md` and they went stale inside a single day. §9's own
closing line already says the doc "must carry the shape, not a list"; the
numbers should follow that rule.

**P10 — `docs/vault-human-auth.md` is an uncommitted working-tree edit and
`main` carries a falsified bullet. BREAKS.** Plan `:645-650` and `:670-676`
say the revocation section is uncommitted, will be absent from a worktree,
that `main` shows a claim these measurements falsify, and "Commit the doc
alongside this ticket". All false now. `git diff HEAD --
docs/vault-human-auth.md` is empty and the corrected revocation section is
on `main` at `docs/vault-human-auth.md:130-215`. §11 Q7 (plan `:1569-1572`)
already says the doc "is now merged on `main`", so the plan contradicts
itself.

Worse for P6: that merged section leads with the **throwaway**
(`docs/vault-human-auth.md:176-206`, "Do that on a throwaway entity, never
on the `developer` group") and never mentions `admin`. §7 instructs the
implementer to cite it as saying "the same thing" as §9. It no longer does.
The repo now has two incident runbooks with different primary remedies and
D2 assigns no owner to the difference. The same false terraform-strip claim
from P7 sits in that file too.

### The rest of the plan, re-checked given the edits

**P11 — D1's shipped surface matches §7 and §11's four checks. HOLDS.**
D1 is merged (`577535d`, `132ea79`) and `done` in the ledger. Package root
`cli/src/localstack_cli/`, console script
`localstack = "localstack_cli.main:main"` (`cli/pyproject.toml:12-13`), the
`cluster` marker with `addopts = "-m 'not cluster'"`, and the four Python
hooks (`ruff`, `ruff-format`, `mypy` strict, `pytest`) in the root
`.pre-commit-config.yaml`. Q1's narrative paragraph is stale ("D1's code is
not on `main`", "`loopctl ledger` reads `ready`") and §7's "not authored
yet" is stale, but both tell the implementer to confirm against the merged
tree, and the confirmation passes.

**P12 — Q2's `httpx` plus `respx` decision. BREAKS as a settled fork.** D1
shipped neither. `cli/pyproject.toml:6-10` lists `click`, `rich`, `typer`
and nothing else, and `cli/src/localstack_cli/status.py:9-12` does its HTTP
with stdlib `urllib.request`. More pointed, `cli/tests/conftest.py:1-5`
states D1's testing stance outright: "Every test runs against a real HTTP
server or a real closed port, **never a mocked urllib**", backed by
`cli/tests/fixtures/cluster.py`'s `FakeCluster`. Q2 anticipated a collision
with `hvac` and got one with `urllib` plus a real local server instead.

This touches every one of §8's 23 offline rows, all specified "against
`respx`", and it runs into the rule the plan itself cites:
`.claude/rules/python-testing.md:77-89` ("do not mock a dependency you can
exercise for real cheaply") and its instruction to check whether the project
already standardized on a tool. `respx` is named at `:89` as the tool for
`httpx`, so it is not wrong. It is a fork the plan believes is closed.

**P13 — §7's `conftest.py` additions are new. PARTIALLY BREAKS.**
`cli/tests/conftest.py:52-65` already has an autouse `isolated_environment`
fixture that redirects `HOME` into `tmp_path` and deletes `VAULT_TOKEN`. §7
asks for both as if neither exists. Only the `XDG_CONFIG_HOME` redirect and
the session-file fixture are actually new. The existing fixture also points
all three addresses at a closed loopback port, which happens to be
compatible with R2 (loopback is exempt), but the plan should say so rather
than leave it to be rediscovered.

**P14 — "`config` lands here because it reads the resolved `vault_addr` and
the session file, both of which this ticket owns" (R13, plan `:513-515`).
BREAKS.** Address resolution is D1's, on `main`, at
`cli/src/localstack_cli/config.py:20-48` (`Config.from_env()`). D2 owns the
session file, not the addresses. Related: §7 proposes `commands/config.py`
alongside the existing `localstack_cli/config.py`, and `auth/vault.py` is
specified as "Reads `VAULT_ADDR`" rather than reading `Config`. Also
unowned: R11's `env_token_differs` duplicates `status.py:113-126`
`current_token()`, whose docstring already encodes the same precedence rule
R11 is built on. The plan should say plainly that `status.current_token()`
stays the single answer to "which token would a bare `vault` use" and that
`auth/` calls it rather than reimplementing it.

**P15 — the core auth premise. HOLDS, every claim re-measured today.**
- `vault auth list` returns `jwt-nomad/`, `token/`, `userpass/` with
  accessor `auth_userpass_ca653bd3` and F2's description.
- `auth_userpass.tf:13-17` backend, `:24-27` comment, `:28-36` generic
  endpoint with `token_policies = []` at `:34`, `:38-53` entity and alias.
  All resolve.
- `vault policy read default` grants exactly the set §4 lists, and grants no
  `nomad/creds/*`, no `consul/creds/*`, no KV2 read, no `sys/leases/revoke`.
- `vault read nomad/role/deploy`: `type client`, `policies [deploy]`
  (`nomad_deploy_role.tf:36-41`). `vault read nomad/config/lease`:
  `ttl 30m`, `max_ttl 1h`
  (`bootstrap/roles/nomad_server/tasks/main.yml:309`).
- `vault read consul/roles/deploy`: `ttl 1800`, `max_ttl 3600`,
  `token_type client` (`consul_deploy_role.tf:19-25`).
- `sys/config/state/sanitized`: `default_lease_ttl 0`, listener
  `tls_disable true`. `VAULT_ADDR=http://192.168.2.30:8200`. R2's refusal is
  still needed.
- `.devcontainer/devcontainer.json:38-39` is `"--env-file",
  ".devcontainer/.env"`; `.devcontainer/.env:8` is `VAULT_TOKEN`, `:5` is
  `CONSUL_TOKEN`. `.env.example:2,6,10,11` as cited.
- `strings /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE` returns 0 against 2
  for `CONSUL_HTTP_TOKEN_FILE` in `/usr/bin/consul`, and an exact-match grep
  for `CONSUL_TOKEN` in the consul binary returns 0. Nomad v2.0.3.
- `~/.vault-token` exists at mode 600 (10 bytes, not the 8 the plan says).
- `vault audit list`: "No audit devices are enabled".
- `deployments/infrastructure/justfile:8,12,16` all read
  `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}`.
- `consul.hcl.j2:29-32` sets `tokens { agent, default }` to the agent token,
  so R14's cut stands on a true premise.

Independent corroboration for R11 and Q4: `status.py:113-118`'s own comment
says "`VAULT_TOKEN` wins over the file, matching the Vault CLI's own order".
D1 measured the same thing separately. Note that `ROADMAP.md`'s locked block
still carries the pre-correction bullet ("It is why the stock `vault` CLI
needs no shim"); D2 and D6 are right and the roadmap is stale there.

**P16 — R10's byte-exact stdout survives D1's banner. HOLDS.**
`main.py:59-64` returns early when `ctx.invoked_subcommand is not None`, so
`print_banner` and `probe_cluster` never run for `localstack token nomad`.
Worth stating in the plan as a fact rather than luck, since it is the whole
basis of D6's shim safety. §7 should also acknowledge `LAZY_SUBCOMMANDS` and
the one-command-collapse rule that `main.py:11-21` documents, since §7 tells
the implementer to add six registrations "one line each" without naming the
mechanism.

**P17 — the gates section. HOLDS.** `.loop/config.json` gate is
`just pre_commit`; the root config runs the four Python hooks with mypy
`strict = true` over `cli/src cli/tests`; `cli/justfile` provides `check`,
`test`, `test_cluster` (`:12-13`), `lint`, `typecheck`; `.github/workflows/`
holds only `claude-ollama.yaml` and `hermes-interactive.yaml`, no Python
job. Every `.claude/rules/python-testing.md` anchor in §6 resolves.

**P18 — the `ROADMAP.md` locked-surface citation. HOLDS.** The file is
deleted in the working tree (`git status` shows ` D ROADMAP.md`) but present
in `HEAD`, so a worktree branched from committed state has it. The committed
version carries the block: `login | logout | whoami | env | token <svc> |
config          D2`, and the `ui consul` fold into `service consul --open`.
Citing it by name was the right call.

## Most dangerous assumption

**P6.** The plan believes the Q-relay resolution reached the sections that
decide what ships. It did not. §7 and §10 still specify the throwaway as the
content of `docs/cli-login.md`, so an implementer who builds to the plan
produces a doc with no `admin` in it, contradicting §9 on the same page and
leaving the new `F14` dependency edge with nothing to justify it. P7
sharpens it: the one argument the plan gives for the switch is false, so a
reviewer reading only §7 and §10 has no reason to notice anything is
missing.

## Required fixes

1. **Propagate the `admin` resolution into §7 and §10.** §7's
   `docs/cli-login.md` bullet and §10 subticket 11 must lead with joining
   `admin` and name the throwaway as the fallback, matching §9 and Q-relay.
   Otherwise drop the `F14` dependency, because nothing shipped consumes it.
2. **Fix or scope the terraform-strip claim.** The residual at plan
   `:982-986` and Q-relay's use of it at `:1347-1350` are false for the
   throwaway procedure as written: a throwaway policy on a throwaway entity
   is invisible to Terraform. Either restate it as applying only to the
   forbidden attach-to-the-group variant, or drop it and rest the `admin`
   preference on the reasons that do hold: fewer commands, no teardown
   order, no orphan policy. The same claim in
   `docs/vault-human-auth.md:196-198` needs an owner.
3. **Correct the three `developer_group.tf` anchors** per the table under
   P8: `:161` for the managed `policies` list, `:158-164` for the group
   binding, `:123` and `:144` for the two creds paths.
4. **Fix `docs/vault-human-auth.md`'s status in §7.** It is committed on
   `main`, its revocation section is correct, and there is nothing to commit
   alongside this ticket. Then resolve the contradiction it now has with §9:
   it leads with the throwaway and never mentions `admin`, so §7 cannot
   claim the two say the same thing.
5. **Re-open Q2 against what D1 actually shipped.** `cli/pyproject.toml` has
   no `httpx` and no `hvac`; `status.py` uses stdlib `urllib.request` and
   `cli/tests/conftest.py:1-5` plus `cli/tests/fixtures/cluster.py` build
   the suite on a real local HTTP server, not a mock. Decide and record
   whether D2 adds a second HTTP stack plus `respx` or extends
   `FakeCluster`, and update the 23 offline rows in §8 to match. Cite
   `.claude/rules/python-testing.md:77-89` either way.
6. **Name the owner of the code that already exists.**
   `status.current_token()` (`status.py:113-126`) already answers R11's
   "which token would a bare `vault` use"; `Config.from_env()`
   (`config.py:20-48`) already resolves the addresses R13 claims this ticket
   owns; `cli/tests/conftest.py:52-65` already redirects `HOME` and clears
   `VAULT_TOKEN`. §7, R11 and R13 must say which side owns each rather than
   re-specifying them as new. Also correct R13's stated reason for living in
   D2.
7. **Handle the empty-group case in §9's join snippet.** `admin` has
   `member_entity_ids []` today, so the snippet as written produces a
   leading comma on the first real use. Add the branch
   `docs/cluster-roles.md:84-87` already has, add the read-membership
   command inline, and fix "Three commands" over four.
8. **Replace §9's hardcoded accessor counts with the shape.** Live today: 25
   accessors, 10 at `auth/userpass/login/operator`, against the plan's 20
   and 5. §9's own closing line already asks for shape over list.

## Notes, not blocking

- Q1's "D1's code is not on `main`" and §7's "D1 ... is not authored yet"
  are stale; both instruct confirmation at pickup and the confirmation
  passes.
- `~/.vault-token` is 10 bytes, not 8.
- §7 should note `LAZY_SUBCOMMANDS` and the single-command-collapse rule
  (`main.py:11-21`), and record that the root callback's banner does not
  fire for subcommands (`main.py:59-64`), which is what keeps R10's stdout
  clean.
- `ROADMAP.md`'s locked block still says the `vault` CLI needs no shim. D2's
  §12 and D6 are correct and the roadmap is stale; not D2's to fix, but do
  not let it reopen Q4.
- New test subdirectories `cli/tests/auth/` and `cli/tests/commands/` need
  `__init__.py`, following `cli/tests/fixtures/__init__.py`.
- The signed eval marker (`.loop/evals/D2-cli-login-broker-tokens.md`,
  `signed-off-by: JasperHG90 2026-07-31`) carries all four guardrails the
  plan names and does not need re-signing: the Q-relay change moved runbook
  prose, not shipped behavior.
