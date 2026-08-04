---
verdict: pass
tree: 7e6a2b335cc1f140f2b5356d1596b5fa056658b4
---

# Adversarial review: D4-cli-cluster-tui (cycle 3, final)

## Deterministic floor

`loopctl verify-eval-substance D4-cli-cluster-tui` -> `valid` (exit 0). No
mechanical eval defect. Proceeded to the semantic pass.

## Gates, re-run here

| Gate | Result |
| --- | --- |
| `just pre_commit` | 14 hooks, all **Passed** |
| `cd cli && uv run pytest` | **375 passed, 10 deselected**, 7 snapshots passed, 54.7s |
| `loopctl verify` | `ok` |

375 against 371 at cycle 2: exactly the four new tests, no test removed.
`.loop/stamp.json` carries `tree: 7e6a2b33…`, which is the fingerprint I was
given, and `verify` binds it to the current tree.

## The five cycle-2 minors, each re-checked by running it

### A. Stale docstrings — FIXED

`tui/monitor.py:124-127` now reads "Three groups start here, not four. The job
fetch is started by the node fetch instead, because judging a `system` job
needs the node count." The module docstring at `:8-11` says the same and adds
that a failed node fetch still hands off. The surviving "four workers" on
line 1 is now a true count: four `@work` methods exist (`:133`, `:137`,
`:147`, `:151`), and lines 8-11 qualify the ordering directly beneath it. No
false claim left in either.

### B. R5 test docstring — FIXED

`test_monitor_tui.py:316-323` names Vault and Consul and states outright that
the job panel "is started BY the node fetch, so it legitimately waits on it."
The assertions at `:347-349` are exactly those three and nothing else, so the
docstring and the asserts now agree.

### C. The `5/?` branch — FIXED, and the test is not vacuous

`test_a_system_job_with_no_node_count_renders_as_unknown`
(`test_monitor_tui.py:358-370`) drives the real `MonitorApp` with the node
fetch denied. I replayed it against `JobPanel.render_value` with the
`Health.UNKNOWN` branch removed:

```
PRE-FIX JOB ROWS: ['  unknown  node-exporter       system   5/0',
                   '  unknown  promtail            system   5/0']
  FAILS PRE-FIX: "5/?" in rendered
  FAILS PRE-FIX: "5/0" not in rendered
```

Delete `widgets.py:116-119` and the test goes red. That closes the render half
of cycle-1 finding 1.

### D. The fixture-directory collision — FIXED, no dangling reference

`grep -rn "fixtures/cluster"` under `cli/` returns nothing. Seven places point
at the new path: `test_api_consul.py:13`, `test_api_nomad.py:13`,
`test_api_vault.py:13`, `test_health_rules.py:20`, `test_monitor_tui.py:32`,
`test_monitor_guardrails.py:98` and `scrub_capture.py:84`. There is no
`capture.py` anywhere, so the module-shadows-namespace-package hazard is gone
rather than moved.

`tests/fixtures/cluster.py` is intact and still imported by seven modules
(`conftest.py:17`, `auth/test_vault.py:16`, `auth/test_broker.py:15`,
`test_status.py:7`, `commands/test_breakglass_probes.py:18`,
`commands/test_token_command.py:14`, `commands/test_auth_commands.py:14`).

I checked this harder than the grep, because every file under `cli/tests/`
carries the same 22:37:21 mtime, which is the signature of a bulk rewrite over
the whole directory. `git status --short cli/tests/` lists no tracked file as
modified, so every pre-existing test module (including `conftest.py`,
`test_status.py`, `test_branding.py`, `test_platforms.py`) is byte-identical to
HEAD. The sweep rewrote them with unchanged content.

### E. The empty-but-successful fetch — FIXED, and the test is not vacuous

`widgets.py:69` is `body = self.render_value(result.value) or "  none"`.
Replayed against the pre-fix `render_result`:

```
PRE-FIX EMPTY RENDER: 'Nodes\n'
  FAILS PRE-FIX: "none" in rendered
```

**No snapshot baseline changed meaning.** All seven `.raw` files carry mtime
`21:52:52`, before `widgets.py` (`22:37:56`) and `test_monitor_tui.py`
(`22:37:50`), and all seven still pass. They were not regenerated. That is
consistent with the code: the fallback is unreachable in every snapshot case.
The three error snapshots have `value is None` and return at `widgets.py:66`
before reaching it, and the four data snapshots all render a non-empty body.

## R5 still rejects an inline implementation

I rebuilt `MonitorApp` with a no-worker `refresh_all` that fetches the four
sources in line on the UI thread, and replayed the body of
`test_a_slow_source_does_not_delay_the_others`:

```
NODES : 'Nodes\n  ok       jetson-orin-nano    ready/eligible\n  ok    '
ASSERTION FAILED: "firebat" not in nodes_text
```

The worker chain and the docstring rewrite did not weaken the proof of the
refresh contract.

## The two other new tests, checked for substance

- `test_the_job_panel_still_renders_when_the_node_fetch_dies` (`:373-381`)
  pins the hand-off at `tui/monitor.py:145`. An early `return` in `_work_nodes`
  on a failed fetch leaves the panel on `no data yet` and drops `memex`.
- `test_an_unexpected_error_degrades_one_panel_rather_than_the_app`
  (`:383-396`) pins the bare `except` at `tui/monitor.py:164-170`. Without it
  Textual's `exit_on_error` default kills all four panels.

Both guard behavior that already shipped, and both fail against the plausible
break. Neither is a tautology.

## Regressions found

None. `api/health.py`, `api/nomad.py`, `commands/monitor.py` and the fixture
JSON are unchanged since the cycle-2 pass, and nothing in the three files that
did change reaches beyond the five findings.

## Informational, not findings

- **Eval row 18 and the plan still name the pre-rename path.** Row 18 greps
  `cli/tests/fixtures/cluster/`, and `.loop/plans/D4-cli-cluster-tui.md:385`,
  `:428` and `:565` say the same. That path no longer exists, because the
  rename was made on my own cycle-2 recommendation. Nothing scores vacuously:
  `verify-eval-substance` passes, and `test_monitor_guardrails.py:98` globs the
  real `fixtures/capture/*.json`. Worth one line in the reflection so the
  ledger records the divergence rather than leaving a future reader to grep a
  directory that is not there.
- **Row 18 also names the package source, which the guardrail test does not
  cover.** `test_no_token_value_appears_in_a_fixture_or_baseline` searches the
  fixtures and the baselines only. I greped the third place by hand:
  `grep -rn "hvs\.|hvo_|hvb\." cli/src/localstack_cli/` returns nothing, and so
  does the same grep over the fixtures and baselines. The substance holds; the
  automated check covers the two places a token could plausibly leak.
- **Row 19's "httpx reused" was inaccurate about the starting state.**
  `git show HEAD:cli/pyproject.toml` lists click, pyyaml, rich and typer, and
  the pre-existing HTTP code (`auth/vault.py`, `breakglass.py`, `install.py`,
  `status.py`) uses `urllib.request`. So D4 adds httpx as a new declared
  dependency rather than reusing a declared one. The row names httpx and respx
  explicitly and respx only mocks httpx, so the choice is eval-sanctioned, and
  it was in the tree at cycle 2 when I passed it. Recording it, not raising it.
- **Row 10 stays unmet.** The CLI still brokers `nomad/creds/deploy`.
  `docs/monitoring.md` says "**Today they will say 'denied.'**" with the reason
  and the fix, and `test_api_live.py:52-59` `pytest.fail`s naming
  `nomad/creds/manage` instead of passing on an ambient token. Carry it in the
  ledger.
- **Grafana boundary (row 16, the rubric row): 5/5.** No metrics, no charts,
  no history, no logs, no alerting, no dashboard framework. No writes:
  `test_monitor_guardrails.py:118-123` bans `.post(`, `.put(`, `.delete(` and
  `.patch(` across `api/` and `tui/`. No Terraform and no Ansible in the diff.
- **Scope is clean.** Tracked changes are `.gitignore` (the snapshot report),
  `README.md` (one word), `cli/pyproject.toml` (deps plus `asyncio_mode`),
  `cli/uv.lock`, `main.py` (one lazy entry) and `docs/monitoring.md`.
  `.loop/ledger.json` is harness bookkeeping. Every line traces to the ticket.

## Verdict

**pass.** The tree moved only where the five cycle-2 minors said it should.
Each fix is real rather than cosmetic, and I confirmed the two that add
assertions by replaying them against the pre-fix code and watching them go red.
The rename left no dangling reference and did not disturb
`tests/fixtures/cluster.py` or any other tracked test file. The `  none`
fallback cannot fire in any snapshot case, and the baselines were not
regenerated. R5 still fails against an inline implementation.

Nothing in the shipped tree is wrong, so there is no required fix. Commit it.
