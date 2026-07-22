verdict: pass
tree: 9ece3bdb9a2d388c62347a66b58137f779bf9506

# Architectural review — init-loop-scaffold-skill

Ticket: `.loop/plans/init-loop-scaffold-skill.md`
Baseline: `MANIFESTO.md` (read in full)
Scope reviewed: `skills/init-loop/SKILL.md` (new), `tests/test_manifest.py`,
`README.md`, `docs/onboarding.md`, `docs/tutorials/custom-reviews-and-actions.md`.
`.loop/ledger.json` ignored (loopctl-managed state).

## Verdict rationale

The change adds a behavioral-layer skill and repoints docs at it. It respects
every architectural boundary the manifesto states. No invariant is eroded.

### Boundary: behavioral layer vs. verifying core (Manifesto §2)

The manifesto splits the system into "Skills and agents (`skills/`, `agents/`)
[as] the behavioral layer the model runs" and "the Python core [as] the layer
that verifies what the model did" (`MANIFESTO.md:42-44`). The new artifact is a
single `skills/init-loop/SKILL.md` — pure behavioral layer. `git diff HEAD
--name-only | grep '^src/'` returns nothing: no `src/loop_harness/` file is
touched. Ticket §5's assertion (NO `src/` change; the skill orchestrates
existing behavior and does not alter it) holds by evidence, not by hand-off
claim.

### Skill orchestrates, never re-implements, harness behavior

The skill drives the existing CLI (`loopctl init`, `loopctl stamp`) and mirrors
existing harness policy rather than duplicating it in a new layer:

- Step 1 mirrors `write_example_config`'s refusal. Verified against
  `src/loop_harness/config.py:391`: `raise ConfigError(f"{path} already exists;
  edit it instead")`. The skill's quoted phrase "already exists; edit it
  instead" matches verbatim.
- Step 4 keeps the mandatory `adversarial` pass on and leaves `architectural` /
  `documentation` disabled. Verified against `EXAMPLE_CONFIG`
  (`src/loop_harness/config.py:38-43`): `adversarial` `enabled: True`,
  `architectural` `enabled: False`. This upholds the fail-safe default behind
  I8 (`MANIFESTO.md:151-155`) and the "smallest honest gate" value rather than
  weakening review.

### I5 — an empty gate list never stamps green (`MANIFESTO.md:123-127`)

Step 3 states the invariant back to the operator ("An empty gate list never
stamps green, so the config must carry at least one real gate before handoff")
and forbids fabricating gates absent from the repo. The skill defers to, rather
than bypasses, the enforcer at `stamp.py`.

### I7 / commit gate — the skill does not bypass earned evidence (`MANIFESTO.md:140-149`)

Step 7 stops at ready-to-commit and hands the commit to the operator; the
"Discipline" section makes "never commit" a hard edge. The skill never automates
past the commit gate and adds no bypass. Consistent with I7 and with the
"operator owns decisions" value (`MANIFESTO.md:256-258`).

### I10 — loop state files are harness-written only (`MANIFESTO.md:164-169`)

The skill writes `.loop/config.json` only through `loopctl init` (the CLI path)
and never hand-edits `ledger.json` or `stamp.json`; verification runs via
`loopctl stamp`. State discipline is respected.

### operator-owns-substance / harness-verifies split

Step 3 routes gate selection through `AskUserQuestion` and writes gates only on
operator confirmation ("propose, do not decide"). This matches the project's
decision-prompt convention and the manifesto value that the operator owns
design choices while the harness owns evidence (`MANIFESTO.md:256-258`).

### gitignore / commit contract (README, the ticket's cited authority)

Step 5's entries (`.loop/stamp.json`, `.loop/HALT`, `.loop/handoff.log`
ignored; `.loop/config.json` + `.loop/ledger.json` committed) match
`README.md:80-88` verbatim and are consistent with the on-disk-state description
at `MANIFESTO.md:81-88` (config.json consumer-owned and committed; stamp.json
harness-written local state).

## Findings

### F1 — informational (not a required fix; not architectural)

`skills/init-loop/SKILL.md:33` describes the placeholder gates as `uv run
pytest` and `uvx prek run --all-files`, but the shipped `EXAMPLE_CONFIG` first
gate is `git add --intent-to-add -A . && uv run pytest`
(`src/loop_harness/config.py:30`). The skill presents this informally as "the
placeholder gates" the operator replaces, so the missing `git add
--intent-to-add` prefix does not misdirect the flow (step 3 replaces these
gates wholesale). The manifesto is silent on how skills must render placeholder
text, so this is not an architectural violation. Flagged for the adversarial /
documentation reviewer, who own line-level doc accuracy; it does not change the
verdict.

## Where the baseline is silent

The manifesto states no rule on skill front-matter shape, skill file layout, or
how a bootstrap skill must sequence its steps. Those concerns (front-matter
matching existing skills, seven-step ordering, slop scan) belong to the ticket
and the documentation/adversarial passes, not to this architectural review. I
make no ruling on them.

verdict: pass
