---
verdict: pass
plan: e998446c52f7e011f3029675e0d3a89551f52d28a7f0b12c540c57bff69a6f9e
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: bdb282b94c9af9d96f41cad12379e4761d63ba788f8d3e54e338ad60c50d78b9
citations:
.loop/plans/L3-landing-dash-app.md:319 =   — it needs an explicit `cd "$(git rev-parse --show-toplevel)"` (or
deployments/applications/justfile:38 = tag=$(grep -E '^\s*hermes_version\s*=' services.tf | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
cli/pyproject.toml:41 = markers = [
cli/pyproject.toml:44 = addopts = "-m 'not cluster'"
.loop/ledger.json:157 =       "dropped": true,
.loop/ledger.json:158 =       "drop_reason": "superseded by L3-landing-dash-app: custom app with config-driven tiles, connect-info modals, and cli-backed live status; L2's gethomepage design cannot produce any of the three and has zero commits",
deployments/infrastructure/services/oauth2-proxy.hcl:54 = OAUTH2_PROXY_UPSTREAMS="static://200"
deployments/infrastructure/oidc.tf:176 = assignments      = ["allow_all"]
deployments/infrastructure/services/haproxy.hcl:107,118,155-156 = acl is_dash / use_backend dash / backend dash / server dash1 192.168.2.50:4180 check
cli/src/localstack_cli/api/health.py:101 = def judge_all(jobs: list[Job], nodes: list[Node]) -> list[JobHealth]:
cli/src/localstack_cli/api/services.py:91 = def join(
cli/src/localstack_cli/commands/_common.py:26-34 = def require_session() -> Session: ... raise fail("not logged in. Run `localstack login`.")
cli/src/localstack_cli/commands/service.py:40 = session = refreshed_session(require_session())
deployments/infrastructure/nomad_oidc.tf:74-79 = resource "vault_nomad_secret_role" "manage" { ... type = "management" ... }
deployments/infrastructure/nomad_deploy_role.tf:21-50 = rules_hcl grants submit-job/read-job/host-volume-* only
deployments/infrastructure/acme.tf:87 = token_policies         = ["nomad-workloads", vault_policy.acme_tls_write.name]
deployments/infrastructure/redis_secrets_engine.tf:181 = token_policies         = ["nomad-workloads", vault_policy.redis_cache_read[each.key].name]
cli/src/localstack_cli/api/consul.py:44-46 = def list_checks(...): """Every check, passing or not. No token is sent."""
deployments/applications/services.tf:171-224 = memex_auth_keys/memex_auth_oidc jsondecode/jsonencode round-trip
cli/pyproject.toml:5-13 = requires-python + dependencies = [click, httpx, pyyaml, rich, textual, typer] (no toml reader)
.pre-commit-config.yaml:45,51,64,72 = files: '^cli/' on ruff/ruff-format/mypy/pytest
deployments/applications/services/hermes/Dockerfile:1-44 = full file, zero COPY of local Python source
cli/src/localstack_cli/commands/secret.py:10-11 = "No value is ever read."
.devcontainer/Dockerfile:7 = RUN pipx install --force uv==0.11.16
bootstrap/inventory/group_vars/all.yml:12 = nomad: 2.0.4-1
---

## Deterministic floor

`loopctl verify-plan L3-landing-dash-app` reports `valid` on this cycle's
plan text. Proceeding to the re-attack of the three cycle-1 findings, plus a
quick sanity pass over everything else.

## Cycle-2 scope

This is a resume cycle per the reviewer-brief resume protocol. Cycle 1
(verdict `pass-with-required-fixes`) found P1-P17 SOUND and three implicit
premises BROKEN: P18 (docker build context breaks under `just`'s cwd
pinning), P19 (wrong `pyproject.toml` line-range citation), P20 (stale
"not yet executed" language for the L2 ledger drop). The operator reports
all three were addressed in the plan text; per the brief's "re-attach, do
not rubber-stamp" instruction, each is re-opened below on fresh evidence,
not accepted on say-so. P1-P17 are unaffected by this round's edits (no
diff touched Context §4's substantive claims, the ACL grant shape, the
`uv` path-dependency mechanics, or any of their anchors); rather than
re-demonstrating the two live probes again, I confirmed the sections they
depend on are byte-identical in intent to cycle 1 by rereading the full
plan end to end and diffing my reading against the cycle-1 citation list —
no drift found.

## Per-finding re-attack

- **P18 — RESOLVED, re-demonstrated live.** Cycle-1 claim: the literal
  `docker build -f deployments/applications/services/dash/Dockerfile .`
  command, pasted into a `rebuild_dash` justfile recipe, would resolve
  relative to `deployments/applications` (the justfile's own directory,
  which `just` always pins recipe bodies to), not the repo root, breaking
  `COPY cli/`. The plan's fix, added to Requirement 5 (§6):
  `.loop/plans/L3-landing-dash-app.md:317-323`
  > **A second, related deviation the recipe itself must handle:** `just`
  > pins a recipe's working directory to its own justfile's directory
  > (`deployments/applications/`), never the repo root, so `rebuild_dash`
  > cannot copy `rebuild_hermes`'s body verbatim — it needs an explicit
  > `cd "$(git rev-parse --show-toplevel)"` (or equivalent
  > repo-root-relative pathing) before the `docker build` call, or the
  > widened context silently resolves to the wrong directory and `COPY
  > cli/` fails (plan-validator finding P18, demonstrated live against a
  > scratch justfile).
  and §7's Dockerfile bullet is reworded to match
  (`.loop/plans/L3-landing-dash-app.md:400-412`), explicitly disclaiming
  the literal in-recipe command form and pointing back at Requirement 5's
  fix. I did not take the prose at its word. I re-ran the live `just`
  probe from cycle 1 against a fresh scratch justfile, this time
  including the exact fix line:
  ```
  $ mkdir -p .../cycle2_p18/deployments/applications
  $ cat > .../cycle2_p18/deployments/applications/justfile <<'EOF'
  rebuild_dash_sim:
      #!/usr/bin/env bash
      set -euo pipefail
      echo "cwd-before-cd: $(pwd)"
      cd "$(git rev-parse --show-toplevel)"
      echo "cwd-after-cd: $(pwd)"
      ls -d deployments/applications/services 2>/dev/null && echo "REPO-ROOT-RELATIVE-PATH-RESOLVES: yes" || echo "..no"
  EOF
  $ (cd .../cycle2_p18/deployments/applications && just rebuild_dash_sim)
  cwd-before-cd: /home/vscode/workspace/.loop/scratch/L3-landing-dash-app.plan-validator/cycle2_p18/deployments/applications
  cwd-after-cd: /home/vscode/workspace
  deployments/applications/services
  REPO-ROOT-RELATIVE-PATH-RESOLVES: yes
  $ just --justfile .../cycle2_p18/deployments/applications/justfile rebuild_dash_sim   # invoked from elsewhere
  cwd-before-cd: /home/vscode/workspace/.loop/scratch/.../deployments/applications
  cwd-after-cd: /home/vscode/workspace
  deployments/applications/services
  REPO-ROOT-RELATIVE-PATH-RESOLVES: yes
  ```
  This is captured, re-runnable evidence (ran cleanly twice, both
  invocation styles, straightforward mechanism, not flaky) that (a) `just`
  still pins the recipe body's starting cwd to the justfile's own
  directory, confirming the original bug is real, and (b) the plan's
  specific fix, `cd "$(git rev-parse --show-toplevel)"` as the recipe's
  first line, unconditionally lands the rest of the recipe body at the
  real repo root regardless of invocation style, from which
  `deployments/applications/services/dash/Dockerfile` and `.` (repo root)
  both resolve exactly as Requirement 5 and §7 now describe. This is a
  mechanical fix I verified by executing it, not by reading the prose.
  Scratch removed after the probe
  (`rm -rf .loop/scratch/L3-landing-dash-app.plan-validator/cycle2_p18`).
  Cycle-1 P18 is resolved.

- **P19 — RESOLVED.** Cycle-1 claim: §6's Restrictions cited
  `cli/pyproject.toml:23-30` for the `markers`/`addopts` pair, but those
  lines are `[tool.hatch.build...force-include]` +
  `[dependency-groups]`, unrelated to `addopts`. The citation is now
  `cli/pyproject.toml:41-44`
  (`.loop/plans/L3-landing-dash-app.md:349`
  > `cli/pyproject.toml:41-44`'s `addopts = "-m 'not cluster'"` — the new
  > app's own `pyproject.toml` needs the same marker/addopts pair (§7).
  ). Re-read the live file at exactly that range:
  `cli/pyproject.toml:41-44`
  > markers = [
  >     "cluster: hits the live cluster (network, real Vault/Nomad/Consul)",
  > ]
  > addopts = "-m 'not cluster'"
  The new anchor resolves to and supports the exact claim attached to it —
  the `markers`/`addopts` pair the Restrictions bullet describes. Cycle-1
  P19 is resolved.

- **P20 — RESOLVED, stale language corrected throughout.** Cycle-1 claim:
  the ledger drop of `L2-landing-homepage` had already run (uncommitted
  working-tree state) but the plan text in five places still described it
  as pending/not-yet-executed. Re-checked the ledger state fresh this
  cycle:
  `.loop/ledger.json:157-158`
  >       "dropped": true,
  >       "drop_reason": "superseded by L3-landing-dash-app: custom app
  >       with config-driven tiles, connect-info modals, and cli-backed
  >       live status; L2's gethomepage design cannot produce any of the
  >       three and has zero commits",
  and via `loopctl ledger` live:
  > L2-landing-homepage: dropped [epic: landing] ... [reason: superseded
  > by L3-landing-dash-app: ...]
  Both confirm `dropped` is the ledger's live, displayed state, matching
  the plan's own recommended reason text verbatim. Then checked every
  location named in the re-attack instructions, plus a full-file grep for
  residual stale phrasing (`not yet executed`, `has not been updated yet`,
  `not run by this planning pass`, `recorded here but not`, `live gap
  between decided`):
  - **Header note** (`:11-18`): "has since been **executed**: `loopctl
    ledger` shows `L2-landing-homepage: dropped`..." — updated.
  - **§9 risk bullet** (`:514-519`): "L2 was resolved to drop, and the
    ledger now reflects it. ... The risk this bullet originally flagged
    ... no longer applies." — updated.
  - **§10 subticket 1** (`:544-549`): "Ledger housekeeping: mark
    `L2-landing-homepage` dropped. **DONE.** ... No longer blocking for
    step 9." — updated.
  - **§11 Q1 execution note** (`:585-590`): "has since been run outside
    that pass — `loopctl ledger` shows `L2-landing-homepage: dropped`." —
    updated.
  - **Closing changelog** (`:774-781`): "**This has since been run,
    outside this planning pass, as anticipated above.** `loopctl ledger`
    confirms `L2-landing-homepage: dropped` with that exact reason text."
    — updated.
  The full-file grep's only remaining hits are the header's own
  changelog meta-line ("the plan previously described the L2 drop as not
  yet executed when by review time it already had been," `:28`, correctly
  describing history, not current state) and §5's non-goal / §4's L2
  bullet ("running `loopctl drop` is outside this planning pass's own
  scope," `:96-97,243-246`), which state a scope boundary about the
  planning pass's own role, not a claim about the ledger's current state
  — both remain accurate as written and do not need further edits. Cycle-1
  P20 is resolved.

## Absence claims — P1-P17 (unaffected by this round's edits)

P1 through P17 — no change in scope, still HOLDS. This round's diff
touches only Requirement 5/§7's build-context wording (P18), one citation
in §6 Restrictions (P19), and the L2-drop status language across
front-matter/§4/§5/§9/§10/§11/changelog (P20). None of those edits alter
Context §4's substantive claims, the Nomad ACL grant shape, the `uv`
path-dependency mechanics, the JSON tile-format precedent, the
`require_session` evidence, or any of the P1-P17 anchors — confirmed by a
full re-read of the current plan text against the cycle-1 citation list,
anchor for anchor, with no drift found.

## Premise verdict: SOUND

All 20 assumptions (the plan's own P1-P17 plus the three implicit,
load-bearing claims cycle 1 added as P18-P20) now HOLD. The three
cycle-1 BREAKS were narrow, mechanical corrections, not design flaws, and
all three are demonstrated fixed above rather than merely re-read.

## Most dangerous assumption

Unchanged from cycle 1: **P17** (`cli/` is reachable as a plain `uv` path
dependency without a workspace) remains the assumption the whole backend
design leans hardest on, and it was demonstrated live in cycle 1 (editable
install + import probe from the exact nested nesting depth). Nothing this
cycle touches that claim.

## Hygiene (secondary)

Unchanged from cycle 1 and still clean: real code surface with resolved
anchors (including the two re-pointed anchors this cycle, P18/P19); gates
discovered from `.pre-commit-config.yaml` and the root `justfile`, not
assumed; explicit non-goals; tests homed under
`.../dash/app/tests/...`; all four resolved forks documented in §11 with
the rejected alternative and its cost; all eight §6 requirements map to a
named producer in §7 and a check in §8.

## Required fixes

None. All three cycle-1 required fixes are confirmed resolved on fresh
evidence, not on the operator's say-so alone.
