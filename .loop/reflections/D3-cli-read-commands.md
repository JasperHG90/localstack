---
slug: D3-cli-read-commands
blockers: []
friction: [vacuous-tests, other:plan-cited-a-gitignored-file, other:signed-eval-contradicts-shipped-code, other:overcorrected-a-review-finding]
worked: [other:reviewer-probed-the-live-cluster, other:parser-took-text-as-an-argument]
cycles: 3
gates_red: 2
harness_change: A plan that cites a gitignored path cannot be picked up at all, because verify-plan runs in a worktree that will never have it.
---

## What worked

Making the edge parser take its input as an argument rather than fetching it.
The running haproxy jobspec carries a live basic-auth password, so `service`
holds a credential in memory the moment it fetches that job. A pure function
that copies out four fields and never stores, returns or quotes its input is
a boundary a test can actually check, and the tests check it on four paths:
the dataclass, `repr()`, `--json` and the exception. The reviewer then served
a malformed config carrying a real-looking secret to the real binary and got
nothing out.

The adversarial reviewer probing the live cluster rather than reading the
code. It found the blocker by sending Vault a bogus token and reading the
actual 403 body, which is `permission denied ... invalid token` and matches
none of the strings the code was sniffing for. No amount of re-reading the
implementation would have found that, because the implementation was
self-consistent and the test that should have caught it was feeding Vault
Consul's wording.

## What worked less well

The ticket could not be picked up at all at first. The plan cited
`tmp/HANDOFF-2026-07-31.md` four times for load-bearing premises, `tmp/` is
gitignored, and `loopctl verify-plan` runs inside a worktree that will never
have it. Both claims were true and independently checkable, so the fix was to
re-anchor them to the policy template and `group_vars/all.yml` after
re-probing live. The lesson generalizes: a plan that rests on a scratch file
is unimplementable the moment the scratch file goes, and the harness catches
it at the worst possible time.

Requirement 13 shipped inverted, and the test greened on a fiction. The
command told a dead session that logging in would not help, which is the
exact circle the requirement exists to break, pointed the other way. Then the
fix over-corrected: reading a failed Nomad probe as "the token is dead" made
an ordinary missing capability report a dead session. Both directions were
wrong for the same reason, which is that a failed probe is not evidence.
The final shape says so: `True` when a probe succeeds, `None` when it fails,
and never `False` for Nomad, whose real dead-token case is classified
upstream.

Two eval rows cannot be satisfied as scored and four now contradict shipped
code. Row 6 requires `service --open` to print a brokered Consul token and
write it to the clipboard; the plan's requirement 12 explicitly reverses that
because an explicit token replaces Consul's agent default and cuts the UI
from 25 services to 2. Row 13 requires a footer naming "the filtering token",
and the correct fix was removing that claim, because the Consul read sends no
token at all. Rows 10 and 14 match files the eval's own greps were not scoped
to exclude. **None of these is amended.** Re-signing the operator's marker is
not mine to do, and both reviewers agreed the right disposition was to record
them here rather than quietly make the spec match the code.

Four findings ship open, all judged non-blocking by the reviewer at cycle 3
and all cheap: `api/vault.py`'s `token_is_live` lets an `Unreachable` escape
to typer, so a Vault 403 followed by an unreachable Vault exits with an empty
stdout and a traceback; `GRANTED_BY` has no `read-job` entry, so that denial
names no ticket; `service` still probes `haproxy`, the job whose read just
failed, costing one wasted request; and the plan's amendment note sits at
column zero and ends requirement 3's numbered list. Fixing any of them would
have moved the tree into a fourth review cycle against a cap of three.

Two pre-existing defects surfaced and were fixed. D4's guardrail forbade
`auth/token` under `api/`, which flags the `lookup-self` call requirement 13
requires; it now matches token ACQUISITION rather than use. And D2's live
login test ran `uv run` with a redirected `HOME`, so uv found an empty cache
and rebuilt `.venv` underneath the running pytest, which killed every later
HTTPS call in the same session with a bare `FileNotFoundError` out of `ssl`.
`--no-sync` fixes it. That one only became visible because this ticket added
a second batch of cluster-marked tests to run alongside them.
