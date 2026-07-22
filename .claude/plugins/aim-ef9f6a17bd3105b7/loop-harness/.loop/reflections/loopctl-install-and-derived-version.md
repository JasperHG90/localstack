---
slug: loopctl-install-and-derived-version
blockers: []
friction: [prek-first-pass-rewrite]
worked: [other:single-source-version]
harness_change:
---

## What worked

Deriving `pyproject.toml`'s version from `.claude-plugin/plugin.json` via
hatchling's built-in regex source (`single-source-version`) collapsed two
hand-synced numbers into one with no new script or subcommand, keeping the
existing `release-claude-code-plugin` skill as the sole bump mechanism. The
guard test reproduces hatchling's own resolution, so it fails loudly if the
regex breaks. Both review passes verified the derivation by actually building.

## What worked less well

`prek-first-pass-rewrite`: the new test's assertion exceeded the 100-char line
limit, so ruff-format rewrote it on the first `prek` pass and the gate reported
a "files modified" failure before the second, clean pass. Writing the wrapped
form up front would have saved a round.
