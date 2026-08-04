---
slug: D4-cli-cluster-tui
blockers: []
friction: [vacuous-tests, pytest-basename-collision, other:worktree-missing-gitignored-rules, other:eval-row-unmet-on-a-precondition]
worked: [other:captured-the-real-cluster, other:mutation-checked-the-load-bearing-test]
cycles: 3
gates_red: 1
harness_change: worktree_setup now symlinks .claude, since .gitignore drops it and verify-plan refuses any plan citing a rule file.
---

## What worked

Capturing the whole live cluster rather than authoring fixtures. All 19 jobs,
5 nodes, 41 checks, scrubbed by a script that is committed beside them. Every
premise the plan rested on was confirmed by the capture rather than taken on
trust: no `JobSummary` key on `/v1/jobs/statuses`, `Allocs: null` on the three
periodic parents, `GroupCountSum: 1` against five running allocations on both
system jobs, and the two `talat-*` jobs that exist nowhere in the repo. A
hand-written fixture would have encoded the tidy cluster I imagined, and the
health rules would have passed against it while lying about the real one.

Mutation-checking the one test that carries the most weight. R5 says no source
may block the UI, and I had written the fetches inline: every test still
passed, because injected fetchers return instantly. After moving to workers I
rebuilt the inline version and confirmed the new test goes red against it. The
reviewer then did the same independently. A test for a timing property is
worth nothing until you have watched it fail.

## What worked less well

The first implementation passed its own tests while breaking the requirement
they existed for. Fetching in line froze the whole screen for the slowest
source, which is precisely what requirement 5 forbids, and nothing caught it
because every fixture was in memory. Self-review caught it, not the suite.

Then the same shape again, one layer down. A `system` job was judged by
`running >= expected` with `expected` taken from the node count, so with no
node count `0 >= 0` made a job running nowhere read HEALTHY. The reviewer
found it. My own test fixture had hidden it: it passed `known or
cluster_nodes()` where production passes `known` straight through, so the
tests could never see a missing node count. A test helper that is more
generous than production is not a test.

Two eval rows could not be satisfied as scored. Row 3 greps for `/v1/jobs\b`,
and `\b` matches between `jobs` and `/`, so the pattern flags
`/v1/jobs/statuses` and fails every correct implementation. Row 10 wants the
brokered token to read jobs and nodes, and the CLI brokers
`nomad/creds/deploy`, which grants neither. **Row 10 is unmet and is recorded
here as unmet**, not worked around: both Nomad panels say "denied" until
`nomad/creds/manage` is brokered. The docs say so plainly and the live test
fails with the capability it wanted.

The worktree could not run the ticket at all at first. `.gitignore` drops
`.claude`, so no worktree has `.claude/rules/`, and this plan cites those rule
files, so `loopctl verify-plan` refused the pickup. Fixed by symlinking
`.claude` in `worktree_setup`, beside the SSH key that is there for the same
reason.

Smaller: my fixtures directory `tests/fixtures/cluster/` collided by name with
the pre-existing `tests/fixtures/cluster.py` that `conftest.py` imports, and
worked only because a module beats a namespace package. Renamed to `capture/`.
The plan and eval still name the old path; nothing scores vacuously on it, but
it is a divergence a reader will trip on.
