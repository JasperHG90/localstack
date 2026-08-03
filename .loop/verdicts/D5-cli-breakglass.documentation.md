---
verdict: pass
tree: db07f904d3e56fe8bb9b61e9d0462af2abd586bb
---

# D5-cli-breakglass documentation-freshness review (re-verify)

Re-verified after the required fix from the prior pass landed. The prior
verdict (pass-with-required-fixes, tree e8fe8e99) flagged one load-bearing
hallucination: the runbook named the session cache at
`~/.config/localstack-cli/session.json` when the code writes
`~/.config/localstack/session.json`. That fix is now in. No new drift was
introduced.

## Required fix: confirmed applied

`cli/src/localstack_cli/commands/breakglass_runbook.md:166` now reads:

    (`~/.config/localstack/session.json` by default)

`cli/src/localstack_cli/auth/session.py:86` returns
`root / "localstack" / "session.json"`, which resolves to
`~/.config/localstack/session.json` under the default XDG config home. The
runbook and the code agree. The distribution-name/config-directory confusion
that caused the prior fail is gone.

## Runbook anchors: every backticked path, command, and host resolves

Checked each against the repo file that governs it. All resolve:

- `192.168.2.30`, user `firebat` -> `bootstrap/inventory/cluster.ini:1-3`
  (`firebat ansible_host=192.168.2.30`, `ansible_user=firebat`).
- `/opt/vault/init.json` -> `bootstrap/roles/vault_server/tasks/main.yml`
  (lines 106, 119, 137).
- `just unseal_vault` -> root `justfile` recipe; `scripts/unseal_vault.sh`
  guard requires `VAULT_UNSEAL_KEY_1..3`, `VAULT_ADDR`, `VAULT_TOKEN`
  (lines 6-9).
- `configure_network.yml` allows 8200, 4646, 8500 from `192.168.0.0/16` ->
  `bootstrap/playbooks/configure_network.yml` (lines 13, 18, 21).
- `N4-netsec-edge-only-service-access` -> `.loop/plans/N4-netsec-edge-only-service-access.md`
  exists.
- `vault.lab.orangecluster.nl`, `nomad.lab.orangecluster.nl`,
  `consul.lab.orangecluster.nl` -> `deployments/infrastructure/services/haproxy.hcl`
  ACLs at lines 100-102.
- Vault listener `0.0.0.0:8200` -> `bootstrap/roles/vault_server/templates/vault.hcl.j2:19`.
- `localstack whoami`, `localstack login`, `localstack env` -> backing
  modules exist at `cli/src/localstack_cli/commands/{whoami,login,env}.py`.
- `--no-probe` -> `cli/src/localstack_cli/commands/breakglass.py:219`
  (`typer.Option(..., "--no-probe", ...)`); `docs/breakglass.md:6` documents
  the same flag with the same effect.

## Drift tests: green

`uv run --project cli pytest cli/tests/commands/test_breakglass_runbook_facts.py`
passed 12/12. The suite pins every runbook fact to its source file with a
self-check that the parse found something, so a green run means the anchors
are live, not vacuous.

## docs/breakglass.md: accurate pointer

The pointer page states the credential boundary, names the six failure
modes, and points at `localstack breakglass` for the full text. It documents
`--no-probe` with the same semantics as the code. It duplicates no steps,
honoring the single-copy requirement.

## Prose gates (plain-language, slop-scan)

- No identity leaks in either doc.
- No bare `TODO`/`FIXME`/`XXX`/`HACK` stubs.
- No prose `--` connectors: `grep -n ' -- ' breakglass_runbook.md` returns
  zero matches. The prior `--` occurrences in prose were removed.
- Two semicolons remain, both inside fenced code blocks as inline comments
  (`# root on the manager; the CLI never does this` at line 62,
  `# re-authenticate; rebuilds the cache` at line 170). Neither is a prose
  splice.
- No tier-1 slop words. No smart quotes outside code. No em dashes.

## README and command registration

`README.md:26` lists `breakglass` in the CLI command table. `main.py:50`
registers `"breakglass": "localstack_cli.commands.breakglass:app"`. The
backing module `cli/src/localstack_cli/commands/breakglass.py` exists and
exports `app`. No invented command, no stale row.

## Conclusion

The one required fix landed and no new documentation drift was introduced.
Every documented surface the change touches was updated in step. A reader
following the current docs would not be misled.