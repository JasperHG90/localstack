<p align="center">
  <img src="docs/assets/banner.png" alt="loop harness" width="640">
</p>

An evidence-verified ticket loop for Claude Code, packaged as a
plugin: the model proposes, the harness verifies, and git is ground
truth. Every lifecycle claim ("gates passed", "review done") must be
backed by an artifact bound to the exact tree it certifies, so an
agent cannot talk its way past a stage it has not earned.

## What it enforces

- **Evidence stamps.** `loopctl stamp` runs YOUR repo's configured
  gate commands and binds the exit codes to a tree fingerprint. The
  commit hook refuses `git commit` on a tree with no fresh green
  stamp.
- **A validated lifecycle.** Tickets move ready, implementing, gates,
  self-review, adversarial-review, commit, done — every `loopctl
  advance` re-checks its entry criteria against live evidence.
  Findings loop back to gates, capped; `blocked` carries a coded
  reason.
- **Tree-bound adversarial review.** The bundled `loop-reviewer`
  agent re-runs the gates itself and writes its own verdict file with
  a `tree:` fingerprint. Mid-ticket commits are refused unless a
  passing verdict matches the exact current tree, so post-review
  edits force a re-review.
- **Git-is-truth reconciliation.** The ledger records what git cannot
  (stage, attempts, blockers); `loopctl reconcile` corrects it from
  commit history, never the reverse.
- **Per-ticket reflection.** `loopctl finish` refuses to close a
  ticket without a schema-valid `.loop/reflections/<slug>.md` recording
  what worked and what did not. Existence and schema are enforced;
  quality is not graded. `loopctl distill` aggregates the friction tags
  across reflections and hands the recurring ones to the
  `ticket-planner` agent, closing a self-improvement loop under the
  same ticket discipline.
- **A kill switch.** `.loop/HALT` stops the loop and hands control to
  the operator; the commit gate steps aside while it is engaged.

All hooks fail OPEN on internal errors: a harness bug must never
wedge commits or sessions. Only genuine policy violations block.

## Install

As a Claude Code plugin (direct):

```bash
claude plugin marketplace add /path/to/loop-harness-plugin
claude plugin install loop-harness@loop-harness
```

Or via aim, or any mechanism that places this directory under
`.claude/plugins/` — the hooks, the `implement-ticket` skill, and the
`loop-reviewer` agent register automatically. The harness is
stdlib-only: the system `python3` (3.11+) is the only requirement.

### Optional: `loopctl` on your PATH

The plugin path above needs no install. To also run `loopctl` as a
standalone command outside a session, install it as a tool:

```bash
uv tool install .            # from a clone (or: just install)
uv tool install git+https://github.com/JasperHG90/loop-engineering-harness.git
```

This is purely additive: the SessionStart hook still injects the
zero-install invocation path, so a consumer repo never depends on it.

## Configure the consumer repo

Run the `init-loop` skill to set up a fresh repo: it scaffolds
`.loop/config.json`, proposes real gate commands from the repo's own
manifests, applies the gitignore contract below, verifies with a dry
stamp, and stops at ready-to-commit. The skill is the setup path, so you
never need to locate the plugin-internal CLI by hand.

It writes a starter `.loop/config.json`, which you then edit to the
repo's blessed gate invocations:

```json
{
  "gates": [
    "git add --intent-to-add -A . && uv run pytest",
    "uvx prek run --all-files"
  ],
  "plans_dir": "~/.claude/plans",
  "notify_title": "loop harness",
  "max_review_cycles": 3
}
```

An empty gate list never stamps green: an unconfigured repo fails
loudly instead of certifying untested trees. Commit `.loop/config.json`
and `.loop/ledger.json`; gitignore `.loop/stamp.json`, `.loop/HALT`,
and `.loop/handoff.log`.

To stop generated working-tree files (build output, install lockfiles,
committed logo assets) from staling an otherwise-unchanged stamp, add a
`fingerprint_ignore` list of git pathspecs the fingerprint subtracts:

```json
{
  "fingerprint_ignore": ["docs/assets/", "*.lock"]
}
```

These are git pathspecs, not `.gitignore` globs, so `*` crosses
directory boundaries (`*.lock` matches paths ending in `.lock`, not
`aim.lock.toml`). The list only ever subtracts, so any change outside it
still stales the stamp. Scope each pattern to a generated path: an
over-broad pathspec like `.` or `src` shadows real source and silently
disables the guarantee. An empty pattern is rejected.

## What ships

- `loopctl` — the CLI over every harness operation, including
  `reflect` (author/validate a ticket reflection) and `distill`
  (aggregate reflections for the planner).
- **skill `init-loop`** — bootstraps the harness into a fresh repo:
  scaffolds the config, proposes real gates from the repo's manifests,
  and stops at ready-to-commit.
- **skill `create-ticket`** — authors one ticket in the loop's
  contract; the single source of truth for the ticket format.
- **agent `ticket-planner`** — a repo-aware subagent that explores,
  then writes a ticket against that contract (the delegated,
  context-heavy authoring path).
- **skill `implement-ticket`** — drives one ticket through the
  lifecycle.
- **agent `loop-reviewer`** — the adversarial reviewer that writes
  its own tree-bound verdict.

The two ticket-authoring artifacts and the two ticket-executing ones
close the loop end to end: plan a ticket, run it, review it, close
it — all in one contract, no external planner required.

## Use

The SessionStart hook prints the ledger, the HALT state, and the
exact `loopctl` invocation path into every session. Author a ticket
with `create-ticket` (or delegate to `ticket-planner` for real
features), then the `implement-ticket` skill drives one ticket per
invocation:

```
loopctl reconcile / ledger      where everything stands
loopctl register <slug>         adopt a ticket
loopctl advance <slug> <stage>  validated transition, never trusted
loopctl stamp                   run gates + record evidence
loopctl reflect <slug>          scaffold / validate a ticket reflection
loopctl finish <slug>           close + fold the ledger into the commit
loopctl distill                 aggregate reflections for the planner
loopctl halt / resume / status  the kill switch
```

Design questions a ticket does not answer are a `blocked` state
(`unresolved-design-fork`), never a judgment call — pair the loop
with a decision record (a `DECISIONS.md`) the operator owns.

## Development

```bash
uv sync
uv run pytest
uvx prek run --all-files
```

The harness is deliberately dependency-free (`src/loop_harness/`,
stdlib only) so consumers need no install step; keep it that way.

### Releasing

Bump the plugin version with the `release-claude-code-plugin` skill: it
edits the `version` in `.claude-plugin/plugin.json`, commits, and
pushes. `pyproject.toml` derives its version from that same file (via
`[tool.hatch.version]`), so `uv tool install` reads the new number with
no second edit: one place to change.

## Extending the loop

A gate is any shell command that exits non-zero on violation — that
is the extension mechanism. Whatever you add to `gates` becomes
enforced machinery: the stamp records its exit code, the commit hook
refuses the tree until it passes, and the reviewer re-runs it. No
plugin change needed. Examples:

```json
{
  "gates": [
    "git add --intent-to-add -A . && uv run pytest --cov --cov-fail-under=85",
    "uvx prek run --all-files",
    "uv run bandit -q -r src/",
    "./scripts/slop_scan.sh docs/"
  ]
}
```

Guidelines for writing a gate:

- Exit non-zero on violation and print WHY to stdout/stderr; the
  agent reads the output and fixes the cause.
- Keep it deterministic: a flaky gate teaches the loop to distrust
  red, which is worse than no gate.
- Every configured gate runs on every stamp even after an earlier
  one fails, and every exit code is recorded — order them
  cheapest-first for faster feedback, not for short-circuiting.

### Selectable review passes and action stages

Review at the `adversarial-review` stage is a config-selected list, not a
single reviewer. Each `review_passes` entry names an `agent` that writes
its own tree-bound verdict, and the commit gate requires a passing verdict
from EVERY enabled pass. The plugin ships three:

```json
{
  "review_passes": [
    { "id": "adversarial",   "agent": "loop-reviewer",     "enabled": true },
    { "id": "architectural", "agent": "loop-architect",    "enabled": false, "baseline": "MANIFESTO.md" },
    { "id": "documentation", "agent": "loop-doc-reviewer", "enabled": false }
  ]
}
```

Adversarial review ships on; the architectural pass (reviews the diff
against a `baseline` doc) and the documentation pass (fails when
documented behavior drifts) are opt-in. A pass can name any agent in the
project's `.claude/agents/`, so a custom enforced review is just another
entry. Review is disableable, but only deliberately: an empty or
all-disabled list is a loud config error unless you also set
`"require_review": false`, which gates commits on the stamp alone and is
warned about at session start.

`action_stages` are advisory, not enforced. Each dispatches a project
artifact (an `agent` or a `skill`, by `ref`) at a lifecycle anchor,
writes no verdict, and gates nothing:

```json
{
  "action_stages": [
    { "id": "update-documentation", "type": "agent", "ref": "loop-doc-writer", "after": "implementing" },
    { "id": "report-out",           "type": "skill", "ref": "your-report-skill", "after": "done" }
  ]
}
```

A tree-mutating stage such as the `loop-doc-writer` must run at `after:
implementing`, so its doc edits are stamped, reviewed, and committed with
the code. Because the harness cannot prove an advisory stage ran, docs are
kept honest by the enforced `documentation` review pass, not by the writer
action. Stage ids are unique across both lists.

For a hands-on walkthrough that builds a custom review pass and a custom
action stage from scratch, see
[docs/tutorials/custom-reviews-and-actions.md](docs/tutorials/custom-reviews-and-actions.md).

Lifecycle transitions carry their own checks beyond the gates: `finish`
enforces a schema-valid `.loop/reflections/<slug>.md` (see the reflection
mechanism above). `loopctl distill` then aggregates those reflections and
hands the recurring friction to the `ticket-planner` agent, so the loop
authors its own improvement tickets under the normal ticket discipline.
Transition-level checks like this are extended by changing the plugin,
not by configuration.
