---
verdict: pass
plan: 1b08cda8b5ee1c1bc5cfd280af4c1123db0f8bd45d64c529b2b065bc8e32f7a9
---

# Plan review: D6-cli-deps-and-shims (second pass, pass `plan-validator`)

Plan reviewed: `/home/vscode/workspace/.loop/plans/D6-cli-deps-and-shims.md`
Plan fingerprint (sha256, from the briefing): `1b08cda8b5ee1c1bc5cfd280af4c1123db0f8bd45d64c529b2b065bc8e32f7a9`

## Premise verdict: SOUND

The four fixes applied since the first `pass-with-required-fixes` verdict all
hold against the live repo. Every load-bearing external fact re-verifies.

## Fixes re-falsified

1. **deps.py path corrected.** Plan §7 (`:298`) names
   `cli/src/localstack_cli/commands/deps.py`. `ls cli/src/localstack_cli/commands/`
   shows six D2-shipped modules (`login.py`, `logout.py`, `whoami.py`,
   `env.py`, `token.py`, `config.py`) plus `_common.py`. D6 adding `deps.py`
   there follows the real layout. The prior `cli/src/localstack_cli/deps.py`
   misplacement is gone. HOLDS.

2. **Lazy registration.** `cli/src/localstack_cli/main.py:28` imports
   `LAZY_SUBCOMMANDS` from `localstack_cli._lazy`; `:42` registers the six D2
   commands via `LAZY_SUBCOMMANDS.update({...})`. No eager `@app.command()` in
   the file. Plan §7 (`:301-303`) says D6 adds a `LAZY_SUBCOMMANDS["deps"]`
   entry pointing at `localstack_cli.commands.deps:app`, matching the six D2
   entries. HOLDS.

3. **"First sub-command" removed.** Plan §7 (`:279-285`) says D2 established
   the convention with six command modules and D6 follows it; six modules
   confirmed on disk. The prior false claim that "D6 is the first ticket to
   add a sub-command" is gone. HOLDS.

4. **"typer-only" removed.** `cli/pyproject.toml:7-9` lists `click>=8.0`,
   `rich>=15.0.0`, `typer>=0.27.0` as runtime dependencies. Plan §7
   (`:307-309`) says D1's runtime deps are click, rich, typer, and pyyaml is
   D6's addition. HOLDS.

## Per-assumption findings

### P1 — `nomad` has no credential-file mechanism. HOLDS.
`strings -a /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE` returns `0`. The plan
carries the 2.0.3-vs-2.0.4 caveat (`:45-49`) and schedules a re-check of the
pinned 2.0.4 binary during subticket 4.

### P2 — `vault`/`consul` credential-file failure modes. HOLDS.
D2 R11/R12 reversals cited at `.loop/archive/D2-cli-login-broker-tokens/plan.md`
and re-stated in the plan. Carried from a signed-off D2; no new code claim to
re-probe.

### P3 — `all.yml` is the single version source. HOLDS.
`bootstrap/inventory/group_vars/all.yml:9-13` declares consul 2.0.2-1,
vault 2.0.3-1, nomad 2.0.4-1, nomad-driver-podman 0.6.4-1.
`bootstrap/playbooks/install_dependencies.yml:22,118-121,138` iterates
`hashistack_versions`. Both anchors resolve.

### P4 — `releases.hashicorp.com` serves these versions. HOLDS.
`https://releases.hashicorp.com/nomad/2.0.4/nomad_2.0.4_linux_arm64.zip`
returns HTTP 200. So do `consul/2.0.2/consul_2.0.2_linux_arm64.zip` and
`vault/2.0.3/vault_2.0.3_linux_arm64.zip`. `nomad_2.0.4_SHA256SUMS` and
`consul_2.0.2_SHA256SUMS` return 200. The plan hedges the exact format into
subticket 2 (`:433-435`), which is the right call.

### P5 — The shim contract falls through on non-zero and empty success. HOLDS.
The contract (`:142-151`) carries three guards: `|| exec` on non-zero,
`[ -n "$T" ] || exec` on zero-empty, and `REAL` as an absolute literal so it
cannot recurse.

### P6 — Bin/shim split, absolute literal, not `/usr/bin/nomad`. HOLDS.
R4 (`:234-242`) puts binaries in `$LOCALSTACK_HOME/bin`, shims in
`$LOCALSTACK_HOME/shims`; R7 (`:260-269`) writes the expanded absolute path
into the shim body. The contract block shows
`REAL="/home/vscode/.localstack/bin/nomad"` as a literal. Consistent across
five plan locations (R4, R5, R7, contract block, Q4 resolution). This was the
prior fatal finding; it is fixed.

### P7 — The `cli/` layout is settled by D1 and D2. HOLDS.
`.loop/archive/D1-cli-package-skeleton/plan.md:95-97` bans speculative
scaffolding. D2 made `commands/` real: six modules confirmed on disk.
`main.py:42` registers them lazily via `LAZY_SUBCOMMANDS`. Plan §7 says D6
adds `deps` as a leaf command module under `commands/`, registered lazily.
Matches the repo.

### P8 — An installed `localstack` can read `all.yml`. UNCERTAIN (as the plan states).
The plan marks this UNCERTAIN itself (`:506-508`) and provides R1a's
four-step resolver plus a walk-up-start test seam (`:220-226`) so the failure
branch is reachable from a test. The uncertain case is covered by a loud
non-zero exit, not a silent fallback. Acceptable.

### P9 — The eval rows are testable. HOLDS.
`.loop/evals/D6-cli-deps-and-shims.md` carries the scoping rules: row 1
greps `cli/src/`, row 6 clears `NOMAD_TOKEN`, row 7 uses the
absolute-literal seam for a counter script, every row redirects
`LOCALSTACK_HOME` to `tmp_path`.

## Most dangerous assumption

P6, the bin/shim directory split. If shims and pinned binaries shared a
directory, `--with-shims` would overwrite Nomad 2.0.4 with a script that runs
the unpinned system binary, and the ticket would ship a `nomad` more drifted
than before it ran, while every other eval row scored green. The plan holds
this consistently across R4, R5, R7, the contract block, and the Q4
resolution, and the eval marker scores it in rows 8, 9 and 12. Sound in the
plan; it must be held during implementation.

## Contract hygiene

- **Anchors resolve:** `all.yml:9-13`, `install_dependencies.yml:22,118-121,138`,
  `main.py:11-14,42`, `pyproject.toml:7-9`, D1 plan `:95-97` all verified.
- **Gates match the repo:** `just pre_commit` with ruff, mypy (strict),
  pytest; default suite stays offline via `-m 'not cluster'` in
  `pyproject.toml`.
- **Non-goals explicit (§5):** no cluster changes, no terraform, no
  nomad-driver-podman, no second version source, no token logic, no
  CONSUL_HTTP_TOKEN_FILE.
- **Tests homed in `cli/tests/`**, one module per source module, mirroring
  the tree per D1 rule 6.
- **Forks surfaced and resolved (§11 + "Forks resolved 2026-07-31")**, all
  followed the recorded recommendations.

Verdict: pass. The premise is SOUND and the four required fixes from the
first pass are verified against the live repo.