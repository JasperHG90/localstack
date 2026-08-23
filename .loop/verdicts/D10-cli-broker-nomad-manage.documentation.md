---
verdict: pass
tree: 22f22dd2e66bc98d601d30b63a609075c8eb6074
bound_paths: ROADMAP.md, cli/src/localstack_cli/auth/broker.py, cli/src/localstack_cli/auth/session.py, cli/src/localstack_cli/commands/login.py, cli/src/localstack_cli/commands/logout.py, cli/src/localstack_cli/commands/monitor.py, cli/src/localstack_cli/commands/service.py, cli/src/localstack_cli/commands/status.py, cli/tests/auth/test_broker.py, cli/tests/auth/test_session.py, cli/tests/commands/test_auth_commands.py, cli/tests/commands/test_monitor_command.py, cli/tests/commands/test_read_commands.py, cli/tests/fixtures/cluster.py, docs/cli-login.md, docs/cli-read-commands.md, docs/monitoring.md, docs/vault-human-auth.md
scope: 9519411c143077364219b322289582420f54bbb728bd4bebd9f1b4aa3aad560f
---

# Documentation review — cycle 3 (final)

## Re-opened finding: D10-doc-8 — FIXED, VERIFIED

Claim: `docs/monitoring.md:87-93` told the reader, in present tense, that
the Nomad node/job panels in `localstack monitor` "will say 'denied'"
today and that this stays true "until the CLI also brokers
`nomad/creds/manage`" — stale the moment this diff's `monitor.py` change
landed, since it is exactly that brokering.

Fix made this cycle: the paragraph at `docs/monitoring.md:87-91` now
reads:

    `localstack login` brokers a second Nomad credential, `nomad/creds/manage`,
    for exactly this: `nomad/creds/deploy`'s policy grants neither `list-jobs`
    nor `node:read`, so the node and job panels read through `manage` instead.
    A denial still names the capability it is missing rather than showing an
    empty table, which is the designed behavior for a genuine policy gap.

Verified against code, end to end:
- `cli/src/localstack_cli/commands/login.py:114` brokers `nomad_manage`.
- `cli/src/localstack_cli/auth/broker.py:26,34` map the `nomad_manage` key
  to Vault path `nomad/creds/manage`.
- `cli/src/localstack_cli/auth/session.py:70` stores it as
  `Session.nomad_manage`.
- `cli/src/localstack_cli/commands/monitor.py:44` reads it via
  `session.credential("nomad_manage")`.

The doc's claim ("brokers a second Nomad credential... for exactly this")
matches the code exactly. No stale "will say denied" or "until the CLI
also" language remains anywhere in the file. Status: **fixed-verified**.

## Fresh repo-wide sweep for the same defect class

This phrase pattern ("stale future-tense caveat left behind after the gap
it describes closed") had already appeared 3 times in this one diff
(`docs/cli-read-commands.md`, `ROADMAP.md`, `docs/monitoring.md`), so I
ran an independent sweep beyond the literal strings already checked,
covering paraphrases: `until (the )?(cli|login)`, `not (yet|currently)
(brokered|available)`, `will say ["']denied`, `stays?/remains? partial`,
`for now (returns|shows|denies)`, plus manual greps for `denied`,
`nomad/creds/manage`, `nomad/creds/deploy`, and `TODO/FIXME/XXX/HACK`
across `docs/`, `ROADMAP.md`, and `README.md`.

Result: zero live hits in any reader-facing doc. The only matches for the
phrase pattern anywhere in the repo are in `.loop/archive/*/verdict*.md`
and `.loop/archive/*/plan.md` — historical review artifacts from earlier
tickets (`D4`, `D3`), not documentation a user reads, and out of this
review's scope. No new finding.

## Cycle 1–2 findings re-attached (diff since cycle 2 touched only `docs/monitoring.md`)

Per the re-attach instruction, every settled finding was re-opened at its
anchor and re-confirmed against the current file state and the current
code, not assumed to still hold:

- **D10-doc-1** (`docs/cli-login.md:52`) — still reads "Four credentials"
  with the `manage` token row at line 59. Holds.
- **D10-doc-2** (`docs/cli-login.md:128,136,140`) — still "every credential
  dies together" / "four credentials ... cascades to the other three" /
  "all four". Holds.
- **D10-doc-3** (`docs/cli-login.md:204`) — Preconditions still names all
  three paths (`nomad/creds/deploy`, `nomad/creds/manage`,
  `consul/creds/deploy`). Holds.
- **D10-doc-4** (`docs/cli-read-commands.md:107-113`) — still states login
  brokers both Nomad credentials and which commands use which. Cross-checked
  again against `status.py:34`, `service.py:41`, `monitor.py:44` (all
  `nomad_manage`) and `secret.py:39`/`env.py:32` (both still `nomad`). Holds.
- **D10-doc-5** (`docs/vault-human-auth.md`) — re-read the full file;
  the safety-critical manual revocation procedure at lines 240-250 still
  names both accessors explicitly (line 241) and the closing line
  (line 249) still says "re-mint all three". Holds.
- **D10-doc-6** (`ROADMAP.md:344-346`) — still past tense: "`D10` closed
  the gap: `login` now also brokers `nomad/creds/manage`...". Holds.
- **D10-doc-7** (`cli/src/localstack_cli/auth/session.py:3-4`) — docstring
  still says "One file, four entries" naming both Nomad roles. Holds.

No regressions: `git status` for this cycle shows the working tree
unchanged except for `docs/monitoring.md` relative to the cycle-2 state,
consistent with the fix being scoped to that one file, and I independently
re-read each of the other six anchors above rather than trusting that
scoping claim alone.

## Verdict

All 8 findings across 3 cycles are now `fixed-verified`. The fresh sweep
found no further instance of this defect class, and no other documented
surface in the diff (CLI flags, config keys, error contracts, public
functions) drifted from the docs. Pass.
