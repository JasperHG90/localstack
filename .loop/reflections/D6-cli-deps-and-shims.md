---
slug: D6-cli-deps-and-shims
blockers: []
friction: [prek-first-pass-rewrite, other:uncommitted-planning-state, other:grep-scorer-hits-its-own-rationale, other:cap-blocks-a-known-low]
worked: [other:executed-shims-not-read, other:offline-guard-caught-a-real-leak]
cycles: 3
gates_red: 0
harness_change: loopctl reconcile writes the ledger but nothing commits it, so a worktree branched from HEAD silently starts from stale plans.
---

## What worked

Running the shims as real processes rather than asserting on template text.
Every fall-through row executes a fixture binary and counts calls, so the
reviewer could mutate the template four ways and watch existing assertions
catch all four. Rows that only read the rendered string would have passed
every mutant.

Adding a socket guard to the suite paid for itself immediately. It started
as a defensive fixture for eval row 13 and it caught a real defect in this
ticket's own code: `install_tool` took `base: str = RELEASES_BASE`, a default
frozen at import, so a test that redirected the module attribute still
reached `releases.hashicorp.com`. The reviewer then found the guard was not
enough on its own, since `breakglass` catches broadly and swallowed the
refusal. Recording refusals and re-asserting at teardown, where nothing is
left to catch it, is what actually closed the row.

Re-running the plan's own probe was worth the download. The plan asked for
`NOMAD_TOKEN_FILE` to be re-checked against the pinned binary rather than the
installed one, and the pinned Nomad confirmed zero occurrences. The shim
stays, on measurement rather than on inheritance.

## What worked less well

The tree was not where the ledger said it was. `loopctl reconcile` had
rewritten the ledger and a planning pass had revised four plans and their
verdicts, and none of it was committed. The worktree branched from HEAD, so
it started with a stale D6 plan that failed `verify-plan` outright, and the
first read of the ledger disagreed with the second depending on which
checkout answered. Committing the planning output first fixed it, but the
failure mode is silent and costs a full worktree teardown to notice.

Two scored greps hit the code that explains them. Row 1 forbids a HashiStack
version literal under `cli/src`, and the first thing it caught was the
docstring example in `strip_revision`. Row 12 forbids the Consul token-file
variable in the diff, and it catches the module docstring explaining why that
variable is refused, the doc page saying the same, and the two tests that
assert its absence. Row 1 carved tests out of its own grep for exactly this
reason; row 12 did not, so it is unsatisfiable by construction. The rationale
was reworded around it rather than deleted, but the row wants an amendment at
the next signature.

The review cap and a known finding collided at the end. Both passes returned
`pass` at cycle 3 and both flagged the same LOW: the ROADMAP rewrite
introduced one semicolon splice, the same shape it removed from three other
files. Fixing it moves the tree, invalidates both verdicts and needs a fourth
cycle against a cap of three, so a one-word defect ships to protect a bounded
process. `ROADMAP.md:221` and `docs/cli-deps.md:34`, where "Any run" is
over-broad because `--remove-shims` returns before versions are resolved, are
both open and both cheap.

Ruff's format hook reports rather than rewrites, so the first prek pass
listed four files and fixing them meant running `uvx ruff format` separately
before the gate would go green.
