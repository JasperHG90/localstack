---
slug: R5-rollout-memex-oidc-auth
blockers: [unresolved-design-fork]
friction: [other:stale-vendored-tree, other:reviewer-own-suggestion-wrong, other:worktree-untracked-artifacts]
worked: [other:split-on-broken-premise, other:converging-review-passes]
cycles: 3
gates_red: 1
harness_change: verify-plan should warn when a bare-basename anchor resolves inside a pinned vendored dependency tree instead of silently endorsing it
---

## What worked

**Splitting the ticket when the premise broke.** The first plan review proved
the human half impossible: Vault's OIDC provider issues an opaque batch token
as `access_token` and signs the `id_token`, while memex verifies the access
token and rejects both opaque tokens and id_tokens. No overlap. The workload
half was sound end to end. Splitting it, with an R6 stub carrying the human
path and the finding recorded as settled, kept working code moving instead of
holding it behind a fork that needs an upstream change. The stub cost minutes
and means no future planner re-derives the impossibility.

**Two review passes converging independently.** On both implementation cycles
the adversarial and documentation passes reached the same single required fix
without seeing each other's verdicts: first that `-target` cannot create W1's
window, then that `just apply target=` binds to the wrong positional. Two
agents landing on the same defect is far stronger evidence than one asserting
it, and it made the fix decision trivial.

**Reviewers correcting themselves.** The doc pass flagged its own cycle-1
claim ("inherits the 1h default") as no longer confident, then caught that a
command it had itself suggested in cycle 2 did not work. The adversarial pass
retracted a Nomad version claim. Verdicts that revise their own prior findings
are worth more than verdicts that only attack the implementer.

## What worked less well

**The vendored memex tree is a trap** (`other:stale-vendored-tree`).
`apm_modules/JasperHG90/memex/` is pinned to a pre-1.1.0 commit with no OIDC
code at all. Three files there resolve by bare basename to real-but-wrong
code: `auth.py`'s cited line range holds a different function than upstream,
`provider.py` lacks the string H2 greps for, and `config.py`'s docstring ends
early. `verify-plan` resolved `auth.py` against it and reported success, so
the deterministic floor actively endorsed a false anchor. Cost about one
planning round. The plan now warns at the head of its Premises section. This
is the `harness_change` above.

**A reviewer's own suggestion was wrong** (`other:reviewer-own-suggestion-wrong`).
Cycle 2's doc verdict handed me `just apply target=nomad_job.memex`; cycle 3
caught that `just` binds it to the positional `refresh`, so it targets
nothing. Adopting a reviewer's command without dry-running it cost a full
cycle, and cycles cap at 3. Verify a suggested command like any other premise.

**Untracked plan artifacts do not follow a worktree** (`other:worktree-untracked-artifacts`).
`git worktree add` checks out HEAD, so the plan, eval and verdict authored in
the primary checkout were absent and had to be copied across before `register`
would work. Easy to miss, and the symptom would have been a confusing "no
plan" at pickup.

**One red gate, self-inflicted.** `terraform validate` failed in the fresh
worktree for a missing `.ssh/id_rsa` until `just worktree_setup` ran. The plan
warned about exactly this; I hit it anyway by stamping before acting on my own
section 8 note.
