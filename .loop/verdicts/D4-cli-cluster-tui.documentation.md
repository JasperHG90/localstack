---
verdict: pass
tree: 7e6a2b335cc1f140f2b5356d1596b5fa056658b4
---

# Documentation-freshness review, cycle 3 (final): D4-cli-cluster-tui

Re-bind of the cycle-2 pass onto the tree the adversarial pass produced. No
new doc drift. The three code changes since
`b82b18c9da705dcba7452efbe42ca13a52e6381e` touch no documented surface, and
every anchor the cycle-2 verdict rested on still resolves at this tree. Both
deferrals you named are correct deferrals, not required fixes; my reasoning
for each is below.

`docs/monitoring.md` and `README.md` are byte-identical to the tree I passed
at cycle 2 (`git diff` still shows the same 49-line addition to
`docs/monitoring.md:46-93` and the same one-line edit at `README.md:26`).

## New change 1: fixture rename — no documented surface

`cli/tests/fixtures/cluster/` moved to `cli/tests/fixtures/capture/`. No
markdown in the repo names any test fixture path (`grep -rn "fixtures"
--include=*.md .` outside `.loop/` returns nothing), and the pre-existing
`cli/tests/fixtures/cluster.py` it collided with is still imported by seven
test modules (`cli/tests/conftest.py:17`, `cli/tests/auth/test_vault.py:16`,
`cli/tests/auth/test_broker.py:15`, `cli/tests/test_status.py:7`,
`cli/tests/commands/test_breakglass_probes.py:18`,
`cli/tests/commands/test_token_command.py:14`,
`cli/tests/commands/test_auth_commands.py:14`). Test-internal, and demanding
a doc for it would be inventing documentation the repo never had.

## New change 2: the corrected fetch-ordering docstrings — doc still true

This is the one that could have drifted, so I checked the sentence word by
word. `docs/monitoring.md:58-59`:

> Each source is fetched on its own with its own timeout, so a sealed Vault
> degrades one panel instead of hanging the screen.

Each clause still holds against the corrected code:

- **"Each source is fetched on its own"** — four separate workers, each in
  its own `group`: `tui/monitor.py:133` (vault), `:137` (nodes), `:147`
  (jobs), `:151` (consul). The chaining changes *when* the jobs worker
  starts, not that it is its own worker.
- **"with its own timeout"** — `api/_http.py:43` builds a fresh
  `httpx.Timeout(timeout)` per call and `:46` raises `Timeout(service, ...)`,
  so the timeout is per fetch, not per screen.
- **The stated consequence is about Vault**, which waits on nothing
  (`tui/monitor.py:129`). Unaffected by the node-to-job chain.

The doc never claimed the four start at the same instant, and the failure
isolation it does claim survives the chain: `_fetch_into` catches
`ClusterError` (`tui/monitor.py:160`) and bare `Exception` (`:164`), then
`_work_jobs()` fires unconditionally at `:145`. A dead Nomad node fetch
therefore still hands off, exactly as the corrected module docstring says at
`tui/monitor.py:8-11`. The jobs panel is never stranded behind a dead source,
so there is no reader who acts on `:58-59` and gets a different outcome.

The corrected docstrings (`tui/monitor.py:1-18` and `:114-128`) are internal
prose, not a documented surface, and they now agree with the code rather than
contradicting it. That is a fix in the right direction.

## New change 3: `  none` for a successful empty fetch — no doc change required

`tui/widgets.py:69` renders `"  none"` when `render_value` returns an empty
string on a successful fetch. Two doc sentences sit near this and neither
drifts:

- `docs/monitoring.md:89` — "Both Nomad panels name the capability they are
  missing instead of showing an empty table." That is the *denial* path,
  where `result.value is None`, so `result.empty` is true and
  `tui/widgets.py:66` returns `result.problem`. Line 69 is never reached.
  Unchanged.
- `docs/monitoring.md:59-60` — "A fetch that fails keeps the last value and
  marks it stale." Still true: `tui/widgets.py:71` prefixes
  `(stale: {problem})` regardless of whether the kept body renders as rows or
  as `  none`.

`  none` is a new rendering for a state the docs never described. Nothing in
the repo enumerates panel body text, so no list is now incomplete.

## Deferral 1: `nomad/creds/manage` is a management token — I agree, defer

Your call is right. Not a required fix, and I would not raise it again.

The doc-freshness test is whether a reader following `docs/monitoring.md`
would now be wrong. Every claim in `:87-93` is true at this tree:

- "`localstack login` brokers `nomad/creds/deploy`" —
  `cli/src/localstack_cli/auth/broker.py:25`.
- "until the CLI also brokers `nomad/creds/manage`" — the role exists,
  `deployments/infrastructure/nomad_oidc.tf:74-77`.
- "The `developer` policy already grants that read, so the change is to the
  broker, not to Terraform" —
  `deployments/infrastructure/developer_group.tf:140-142`.

The privilege warning is a design-and-security fact about the *role*, not a
behavior of `localstack monitor`, and the repo already carries it in full at
`docs/vault-human-auth.md:82-89` ("mints a global Nomad **management**
token: anything in Nomad, including minting more Nomad tokens"), with the
same reasoning duplicated in the Terraform comment at
`developer_group.tf:135-139`. The repo is not silent, so no reader is
misled by omission. Whoever changes the broker owns restating it, because
that is the ticket where the decision actually gets made. Your plan recording
the widening as operator-accepted closes the loop on the record.

Downgraded from advisory to noted. It has now survived two review cycles
without becoming wrong, which is the definition of a scope question rather
than drift.

## Deferral 2: `ROADMAP.md:101` — I agree, defer

Also right. `ROADMAP.md:88-103` is the "Waiting on one re-review round"
table, and D4 genuinely is in review at this tree, so the entry is not yet
false. D6 (`:98`, shipped at `ad2c157`) and D5 (`:102`, shipped at `3c44b6c`)
are the stale rows, and both predate this change. Fixing them is roadmap
bookkeeping, not this ticket's diff. The settled command surface at
`ROADMAP.md:247` already carries `monitor  D4`, which is the line a reader
looking for the command actually lands on, and it is correct.

## Cycle-2 anchors, re-verified at this tree

Every one still resolves:

| Doc claim | Anchor | Status |
| --- | --- | --- |
| `monitor` in the CLI row (`README.md:26`) | `main.py:51` | holds |
| The other eight command names in that row | `main.py:44-53` | all eight resolve |
| `--refresh`, default 5s (`:62-66`) | `commands/monitor.py:23-27`, `tui/monitor.py:33` | holds |
| `--refresh 0` is manual-only | `tui/monitor.py:108-109`, binding at `:74` | holds |
| Login required (`:68-69`) | `commands/monitor.py:46` | holds |
| Three env vars (`:71-72`) | `config.py:11-13` | exactly these three |
| Capability names `list-jobs`, `node:read` (`:84-85`) | `api/nomad.py:28-29` | holds |
| Four panels, that order (`:48-49`) | `tui/monitor.py:94-102` | holds |
| `q` quits, `r` refreshes (`:60`) | `tui/monitor.py:74` | holds |

## Slop scan, `docs/monitoring.md:46-93` (re-run at this tree)

| Check | Result |
| --- | --- |
| Em dashes | 0 |
| ` -- ` in prose | 0 |
| Semicolon splice (code stripped) | 0 |
| Tier-1 slop | 0 |
| Lines over 80 chars | 0 |
| Smart quotes | 0 |
| Identity leaks, hallucinated paths, bare stubs | none |

The two negative-parallelism instances from cycle 2 are unchanged and remain
keeps: the heading at `:46` and "the change is to the broker, not to
Terraform" at `:92-93`, where the contrast tells a reader which repo layer to
edit and does not survive removal.
