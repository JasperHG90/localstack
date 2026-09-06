---
slug: L6-landing-dash-service-groups
blockers: []
friction: [prek-first-pass-rewrite, other:edited-tree-during-stamp, other:ungated-frontend, other:self-referential-template-comment]
worked: [reviewer-boilerplate]
harness_change: stamp could refuse to start when the worktree has uncommitted edits younger than a few seconds, or warn that a concurrent edit will read as a gate failure
cycles: 2
gates_red: 1
---

## What worked

The plan review paid for itself twice over. It falsified P10 by actually
rendering the jobspec through Nomad's parser instead of reading the code, and
found that banning `${` was the wrong guard: `%{` is the opener that parses
cleanly and rewrites the deployed text. It also caught two files missing from
the code surface, one of which (`test_cluster.py`) is excluded from the gate,
so nothing would ever have gone red.

Both implementation passes earned their keep. The adversarial pass found two
frontend defects with no gate behind them, and the more serious one is a defect
I could not have found the way I was looking: `.fe-button { display: flex }`
outranks the UA's `[hidden] { display: none }` because the cascade sorts by
origin before specificity, so the panel's button never hid and carried the
previously opened tile's href. My own static check verified element ids and
payload keys and passed while that bug was live. Right check, wrong altitude.

## What worked less well

**Ungated frontend.** This repo runs no JS test and no JS linter, and this
environment has no browser and no JS runtime, so `index.html` was never
executed by anyone in the loop, including both reviewers. Every conclusion
about it is spec-derived. Five of the eval's nine rows exist only because of
that gap. This is the ticket's real residual risk and it does not shrink until
someone loads the page.

**Edited the tree during a stamp.** I made edits while `loopctl stamp` was
running, so `pre-commit` reported "files were modified by this hook" and three
hooks went red, two of them in files this ticket never touched. It read as a
real failure and cost a diagnosis pass plus a full re-stamp. Nothing warns
about this; the gate just goes red somewhere confusing.

**A comment that broke the thing it described.** The `dash.hcl` comment
explaining that `${` and `%{` are forbidden spelled both out, and
`templatefile()` reads the whole file including comments, so `terraform
validate` failed on the comment. The comment now says why it cannot name them.

**prek rewrote on the first pass, twice.** `ruff format` rewrote a test file
during the pre-stamp pass on two separate cycles, each time turning a clean run
red before it was clean again.
