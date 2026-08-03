---
verdict: pass
tree: db07f904d3e56fe8bb9b61e9d0462af2abd586bb
---

# D5-cli-breakglass adversarial review (re-verification pass)

Re-run after the two required fixes from the prior
`pass-with-required-fixes` verdict landed. The prior tree was
`e8fe8e99132e0f572440f5185bc9fe9d5b02220b`; this pass binds to
`db07f904d3e56fe8bb9b61e9d0462af2abd586bb`, the tree the harness
recorded in `.loop/stamp.json` when the gate went green.

## Deterministic floor

`loopctl verify-eval-substance D5-cli-breakglass` -> `valid`. No
mechanical eval defect (no comment-only grep scorer, no stale
`depends_on`, no amendment that dropped a still-required field).

## Required fixes from the prior pass — both landed

F1 (prose ` -- ` connectors). `grep -o ' -- '
cli/src/localstack_cli/commands/breakglass_runbook.md` returns 0 hits.
All eleven prior occurrences are gone, replaced with colons, parens, or
rewrites.

F2 (prose semicolon splices at old lines 41 and 58). The runbook no
longer joins two independent clauses with a semicolon in prose. The
two semicolons the scanner still surfaces (runbook lines 62 and 170)
are inside indented code-block comments (`# root on the manager; the
CLI never does this` and `# re-authenticate; rebuilds the cache`),
not prose, so they are correctly out of scope for the splice rule.

Documentation fix. `~/.config/localstack-cli/session.json` is now
`~/.config/localstack/session.json` (runbook line 166). This matches
the actual implementation in
`cli/src/localstack_cli/auth/session.py:86` (`root / "localstack" /
"session.json"`).

## Gate

`just pre_commit` -> all 14 hooks Passed: check-json, check-ast,
check-merge-conflict, check-yaml, debug-statements,
detect-private-key, end-of-file-fixer, nomad-fmt, terraform-fmt,
terraform-validate, ruff, ruff-format, mypy (strict, cli/), pytest
(cli/). The `.ssh/id_rsa` and `.devcontainer/.env` files are gitignored
and present in the worktree, so terraform-validate resolves its
backends. `uv run --project cli pytest cli/tests/commands/ -q` -> 91
passed.

## Credential boundary (eval rows 1, 2) — holds

Row 2 grep over
`cli/src/localstack_cli/commands/breakglass.py` and
`cli/tests/commands/test_breakglass*.py` for
`init\.json|unseal|VAULT_TOKEN|subprocess|paramiko|\bssh\b` returns
only docstring, comment, and test-assertion hits — all inside runbook
TEXT or the canary test, never executable credential access. The
command source (`breakglass.py`) imports only `sys`, `urllib.error`,
`urllib.request`, `concurrent.futures`, `dataclasses`,
`importlib.resources`, and `typer`. No `os.environ` read of any
credential var, no `subprocess`, no `open("/opt/vault/init.json")`.

The canary test (`test_breakglass.py:48-82`) injects
`hvs.CANARYTOKEN` and five other token-shaped values into
`VAULT_TOKEN`, `VAULT_UNSEAL_KEY_1/2/3`, `NOMAD_TOKEN`,
`CONSUL_HTTP_TOKEN`, `CONSUL_TOKEN` via `monkeypatch.setenv`, runs
both `breakglass` and `breakglass --no-probe`, and asserts none of the
values appear in stdout or stderr. The init-file test
(`test_breakglass.py:95-116`) wraps `builtins.open` and fails if any
opened path contains `init.json`, while still asserting the path
appears as literal text in the output.

## Eval rows 3-14 — each still passes

- Row 3 (six sections plus prelude): `SECTIONS` in
  `test_breakglass.py:22-30` lists all six failure-mode headings plus
  the prelude; `test_every_section_appears_in_the_output` asserts each
  is in the command output. The prelude bounds the tailnet correctly
  (SSH on 22, edge on 443, never an API port; only `firebat` is on the
  tailnet).
- Row 4 (three routes per service): each Vault/Nomad/Consul section in
  the runbook names the edge hostname, the SSH-plus-loopback route, and
  the direct LAN address with its condition. No unconditioned LAN
  address appears.
- Row 5 (drift fails a gate): the fact tests in
  `test_breakglass_runbook_facts.py` pin manager IP, username,
  `unseal_vault` recipe, `/opt/vault/init.json`, Vault port, and each
  edge hostname to the repo file that states it.
- Row 6 (drift catches the N4 edit): I changed `from_ip` for port 8200
  in `bootstrap/playbooks/configure_network.yml:18` from
  `192.168.0.0/16` to `192.168.2.30/32` and re-ran
  `test_lan_address_pinned_to_configure_network_yml[vault]`. It went
  RED with the exact assertion the row requires. The anchor set
  includes `configure_network.yml`, not `haproxy.hcl` alone. File
  restored after.
- Row 7 (no vacuous pass): the `_require` helper
  (`test_breakglass_runbook_facts.py:27-31`) calls `pytest.fail` when
  the parser returns None. I stripped every `from_ip` value from
  `configure_network.yml` and re-ran; all three parametrized cases
  failed with `parser found no from_ip for port ...`. File restored
  after.
- Row 8 (single source, loadable outside a checkout):
  `test_runbook_prints_from_outside_a_checkout` chdirs to `tmp_path`
  and asserts the runbook still prints. `docs/breakglass.md` is a
  pointer only — it duplicates no steps. The runbook is
  force-included in the wheel via
  `cli/pyproject.toml:[tool.hatch.build.targets.wheel.force-include]`.
- Row 9 (probes never take the command down):
  `test_exit_code_is_zero_even_when_probes_fail` and the
  `except Exception: diagnosis = ""` guard at `breakglass.py:237`
  ensure a failed probe degrades to the full runbook with exit 0.
- Row 10 (probe distinguishes sealed from unreachable):
  `test_vault_sealed_renders_reachable_but_sealed` points the edge at
  a 503 and asserts the diagnosis says "sealed", not "unreachable".
- Row 11 (closed firewall is not an outage):
  `test_edge_up_lan_dark_is_a_firewall_change_not_an_outage` asserts
  `bg.FIREWALL_CHANGE` is in the output and "unreachable" is absent
  from the diagnosis. The `FIREWALL_CHANGE` string at
  `breakglass.py:69-73` matches the eval's required string verbatim.
- Row 12 (Consul leader signal):
  `test_consul_reports_the_leader_address` and
  `test_consul_no_leader_is_reported_not_called_an_outage` cover the
  200 and empty-leader cases. The 403 TCP-fallback path is in the
  source (`_probe` returns "reachable, not authorized" on a non-200
  that is not a network error, via the `HTTP {status}` branch).
- Row 13 (prose gates): 0 em dashes in the runbook, 0 tier-1 slop
  words, 0 self-narration phrases, 0 British spellings, 0 smart
  quotes in prose (the smart-quote hits are all inside code blocks or
  inline code). Lines wrap at 80.
- Row 14 (repo gate): `just pre_commit` all Passed, as above.

## Scope — clean

Every changed line traces to the ticket:
- `cli/src/localstack_cli/commands/breakglass.py` (new) — the command.
- `cli/src/localstack_cli/commands/breakglass_runbook.md` (new) — the
  runbook text, loaded with `importlib.resources`.
- `cli/tests/commands/test_breakglass.py`,
  `test_breakglass_probes.py`,
  `test_breakglass_runbook_facts.py` (new) — the test suite.
- `cli/src/localstack_cli/main.py` (+1 line) — lazy subcommand
  registration.
- `cli/pyproject.toml` (+3 lines) — force-include the runbook in the
  wheel. No new dependency (the command uses only stdlib `urllib`).
- `docs/breakglass.md` (new) — pointer, not a second copy.
- `README.md` (+2/-2) — adds `breakglass` to the CLI command list and
  the docs list.
- `.loop/evals/D5-cli-breakglass.md`, `.loop/plans/D5-cli-breakglass.md`,
  `.loop/ledger.json`,
  `.loop/verdicts/D5-cli-breakglass.plan-validator.md` — loop metadata.

No out-of-scope edits. No pre-existing dead code touched. No new
dependency added with `uv pip` (none added at all).

## Tree fingerprint note

`git write-tree` from the working directory computes
`7ea56e27e68f96d953860c6e1396d0e526a7503b`, which differs from the
given `db07f904...` because `.loop/history/D5-cli-breakglass.jsonl`
is an untracked harness-generated metadata file (it records a prior
failed gate run under the old tree `e8fe8e99...`) that `git add -A`
stages but the harness excludes from its fingerprint. `.loop/stamp.json`
(confirmed gitignored) records `tree: db07f904...` with `just
pre_commit` exit 0 at 2026-08-03T17:13:58Z. I bind to the fingerprint I
was given and that the harness recorded, per the briefing's instruction
never to write a fingerprint I was not given.

## Verdict

pass. Both required fixes landed, the credential boundary holds, all
fourteen eval rows pass, the gate is green, and scope is clean.