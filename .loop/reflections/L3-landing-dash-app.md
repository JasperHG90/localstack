---
slug: L3-landing-dash-app
blockers: []
friction: [other:planning-review-not-auto-dispatched, other:uv-editable-stale-build, other:worktree-missing-gitignored-secret, other:docker-multistage-editable-install-breaks, other:vault-kv2-vs-dynamic-secret-nesting, other:reviewer-verdict-scope-citation-commas]
worked: [other:adversarial-review-caught-real-runtime-bugs, other:plan-review-caught-real-plan-defects-before-code, other:build-and-run-the-image-not-just-read-the-diff]
harness_change: "loop-implementation-doc-reviewer's verdict scope/citations format is undocumented in reviewer-brief and its naive comma-split parser (loop_harness/hooks.py's _split_list_field) breaks on any cited source line whose own text contains a comma -- either document the citations: format's constraints for reviewer agents, or make the parser comma-aware (split only on the citations: block's own line boundaries, not on commas inside quoted content)."
---

## What worked

- **Adversarial review earned its cost.** Cycle 1 found two real, confirmed
  defects that every earlier gate (ruff, mypy, pytest, terraform validate)
  missed because neither is the kind of thing a static gate catches: a
  Docker multi-stage build silently shipping a broken editable-install
  redirect (crashes only at container runtime, on the exact import path the
  whole ticket exists to wire up), and a Vault template reading the wrong
  response nesting for a secrets-engine credential (fails only when Vault
  actually renders it). Both were reproduced live (built and ran the actual
  container; read the actual response-parsing code) rather than argued from
  the diff, which is what made the fixes trustworthy rather than guesses.
- **The plan-review pass, run before implementation started, caught three
  real defects for the cost of one review pass** rather than three
  discovered mid-implementation: a `just` cwd-pinning bug in the `docker
  build` recipe, a wrong citation line range, and stale "not yet executed"
  language after the L2 drop actually ran. Cheaper to fix in prose than in
  code.
- **Building and running the actual Docker image**, not just re-reading the
  diff, is what let both AR1's fix and its verification be genuine rather
  than plausible-sounding.

## What worked less well

- **This ticket's plan-review pass was never auto-dispatched.** It was
  authored via a direct `ticket-planner` invocation rather than the full
  `create-ticket` skill, which is what normally wires up the
  planning-review dispatch. Nothing in `implement-ticket`'s own protocol
  checks for this gap -- I only caught it because `loopctl next` listed the
  ticket under "in planning (awaiting plan review)" rather than
  "actionable," and noticed the mismatch. A ticket authored any other way
  (a raw planner call, a hand-written plan file) can silently skip this
  gate the same way.
- **`uv add --editable <path>` does not pick up new source files added
  after the initial `uv add`.** The freshly scaffolded package built an
  empty wheel (the source directory was still empty at `uv add` time), and
  `uv sync` afterward reported "Checked 35 packages" rather than
  rebuilding, leaving the package silently un-importable until
  `uv sync --reinstall-package <name>` forced it.
- **A git worktree does not carry gitignored local files the primary
  checkout has**, including an SSH private key `terraform validate`'s own
  provisioner code expects at a repo-relative path. Worked around by
  generating a fresh, meaningless throwaway keypair scoped to the worktree
  purely to satisfy `file()`'s existence check -- copying the real one was
  correctly refused by the environment's own safety classifier.
- **The documentation reviewer's own verdict file broke `loopctl advance
  commit`**, not because of anything wrong in the ticket: several
  `citations:` entries quoted their cited source line's full text, and one
  of those quoted lines itself contained a comma
  (`` `.Data.secret_id`, NOT `` ), which `loopctl`'s citation parser splits
  on unconditionally, turning one citation into two fragments -- one
  keeping its `path:line` prefix, the other becoming un-anchored text that
  fails the "cited path is in bound_paths" check and silently zeroes the
  whole scope digest. Diagnosed by reading `loop_harness/hooks.py` and
  `lifecycle.py` directly rather than guessing, then fixed by stripping the
  `= <quoted content>` suffix from every citation entry (the parser only
  needs the bare `path:line`; the quoted content was never load-bearing).
