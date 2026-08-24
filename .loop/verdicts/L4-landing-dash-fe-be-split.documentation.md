---
verdict: pass
tree: 455bba201cbbc05b646e473fa65918cf316ac412
---

# Documentation review: L4-landing-dash-fe-be-split (cycle 2)

**Verdict: pass.** The only change since cycle 1 is a two-line deletion in
code (an orphaned constant), which touches no documented surface. Every
cycle-1 finding is re-checked below and still holds; nothing in this cycle's
delta reopens any of them.

Note on the verdict header, unchanged from cycle 1: this diff still DELETES
a path (`deployments/applications/services/dash/Dockerfile`, replaced by
`deployments/applications/services/dash/backend/Dockerfile`), which the
reviewer-brief names as the one case that cannot be scope-bound (a deleted
file cannot be hashed into a bound set). Per that brief ("Omit the three
lines there and let the verdict fall back... the omission is safe and
merely expensive"), `bound_paths`/`scope`/`citations` are omitted from the
header above, same as cycle 1, and this verdict falls back to whole-tree
binding against `tree:` alone. No `scope:` digest was supplied in this
pass's briefing either, which independently points to the same fallback.
(`skills/reviewer-brief/SKILL.md` does not exist anywhere in this
worktree — confirmed by `find` — same absence noted for the slop-scan
rules file in cycle 1; this review applies the fallback rule as stated
directly in the review briefing text.)

## What changed since cycle 1 (the delta this cycle reviews)

Confirmed via `git diff` (working tree vs. the index, which holds the
cycle-1-reviewed state) that the *only* change outside `.loop/` machinery
is:

```
deployments/applications/services/dash/backend/src/dash_app/consul_client.py
@@ -11,8 +11,6 @@ from dataclasses import dataclass
-HEALTH_READ = "service:read"
-
 PASSING = "passing"
```

- `git diff --stat` (working tree vs. index, excluding `.loop/`) shows
  exactly one file touched, 2 deletions, 0 insertions:
  `deployments/applications/services/dash/backend/src/dash_app/consul_client.py`.
- `git diff --stat -- docs/dash-landing-page.md` (working tree vs. index)
  returns empty — the doc file is byte-identical to the state cycle 1
  reviewed and passed.
- Repo-wide grep for `HEALTH_READ` outside `.loop/` and `.venv` finds only
  the unrelated `cli/src/localstack_cli/api/consul.py:25,47,80` (the
  original CLI module this backend file was copied from, per its own
  docstring at `consul_client.py:3` — a different file, untouched by this
  diff, and not renamed/removed). No hit in `docs/dash-landing-page.md` or
  any other tracked `.md` file (the two `.loop/archive/D7-*` hits are
  historical plan-validator records from an unrelated, already-closed
  ticket, not live documentation).
- Repo-wide grep for the removed constant's value, `"service:read"`,
  across all tracked `.md` files outside `.loop/` returns nothing — no doc
  ever named this capability string.
- Grep for `HEALTH_READ` inside
  `deployments/applications/services/dash/backend/` (source and tests)
  returns nothing even before this cycle's deletion in the working tree
  would be expected to remove hits — i.e. the constant was genuinely
  unreferenced anywhere in the backend, confirming it was dead/orphaned as
  the ticket briefing states, not a public surface any doc could have been
  describing.

`docs/dash-landing-page.md`'s "What the status backend can and cannot
read" section (`docs/dash-landing-page.md:86-95`) describes the backend's
*Nomad* ACL role (`read-job`, `list-jobs`, `node:read`) — a different,
still-accurate claim about a different credential than the removed Consul
constant. This section is untouched by the delta and remains accurate.

**Conclusion: this delta touches no documented surface.** No doc names the
removed constant, its value, or any behavior it implied (it implied
nothing observable — it was unused). No update to `docs/dash-landing-page.md`
or any other doc was required, and none was made.

## Re-attack of cycle-1 findings (from
`.loop/scratch/L4-landing-dash-fe-be-split.documentation/findings.json`)

All seven cycle-1 findings are re-attached against the current tree. None
of their anchors or claims fall inside this cycle's one-file delta
(`consul_client.py` is not the anchor of any of them), so each is
reconfirmed by absence-claim rather than re-run from scratch, per this
cycle's briefing:

- **L4-DOC-1** (`docs/dash-landing-page.md:1-17`, two-task split /
  copied-not-imported framing): no change in scope this cycle — the doc
  file is byte-identical to cycle 1 (confirmed above), and the backend
  tree structure (`health.py`, `nomad_client.py`, `consul_client.py`,
  `services.py` all present with their provenance docstrings) is
  unaffected by a 2-line internal deletion in one of those files. Still
  holds.
- **L4-DOC-2** (`docs/dash-landing-page.md:54-72`, rebuild recipe/var
  names): no change in scope — `deployments/applications/justfile` and
  `deployments/applications/services.tf` are untouched by this cycle's
  delta (not in the working-tree diff). Still holds.
- **L4-DOC-3** (`docs/dash-landing-page.md:74-84`, oauth2-proxy
  multi-upstream routing): no change in scope —
  `deployments/infrastructure/services/oauth2-proxy.hcl` and
  `deployments/infrastructure/services.tf` are untouched by this cycle's
  delta. Still holds.
- **L4-DOC-4** (repo-wide staleness sweep,
  `docs/haproxy_reverse_proxy.md:24`): no change in scope — re-ran the
  same greps (`dash/app`, `rebuild_dash\b`, `dash_version`,
  `dash_upstream`) outside `.loop/`; same zero-hit result as cycle 1. Still
  holds.
- **L4-DOC-5** (`.pre-commit-config.yaml:75-101`, hook id/path
  consistency): no change in scope — `.pre-commit-config.yaml` is
  untouched by this cycle's delta. Still holds.
- **L4-DOC-6** (`docs/dash-landing-page.md:95`, slop-scan on new prose):
  no change in scope — the doc file is byte-identical to cycle 1. Still
  holds.
- **L4-DOC-7** (`pyproject.toml:2-4,13`, informational, not a fail): no
  change in scope — `deployments/applications/services/dash/backend/pyproject.toml`
  is untouched by this cycle's delta (not in the working-tree diff).
  Remains informational, not scored against this verdict, same as cycle 1.

## Cross-cycle resume

No new findings are opened this cycle: the delta under review
(`consul_client.py`'s 2-line dead-constant removal) touches no documented
surface, so there is nothing to re-attack beyond confirming the cycle-1
ledger's seven entries by absence-claim, done above. The ledger at
`.loop/scratch/L4-landing-dash-fe-be-split.documentation/findings.json` is
left unmodified: all seven entries remain accurately `settled-pass` /
`informational-no-fix-required` for cycle 2, with no status changes
warranted by a diff outside their anchors.
