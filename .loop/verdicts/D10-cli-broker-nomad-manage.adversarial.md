---
verdict: pass
tree: 22f22dd2e66bc98d601d30b63a609075c8eb6074
bound_paths: ROADMAP.md, cli/src/localstack_cli/auth/broker.py, cli/src/localstack_cli/auth/session.py, cli/src/localstack_cli/commands/login.py, cli/src/localstack_cli/commands/logout.py, cli/src/localstack_cli/commands/monitor.py, cli/src/localstack_cli/commands/service.py, cli/src/localstack_cli/commands/status.py, cli/tests/auth/test_broker.py, cli/tests/auth/test_session.py, cli/tests/commands/test_auth_commands.py, cli/tests/commands/test_monitor_command.py, cli/tests/commands/test_read_commands.py, cli/tests/fixtures/cluster.py, docs/cli-login.md, docs/cli-read-commands.md, docs/monitoring.md, docs/vault-human-auth.md
scope: 9519411c143077364219b322289582420f54bbb728bd4bebd9f1b4aa3aad560f
---

# Adversarial review, cycle 3: D10-cli-broker-nomad-manage

## Deterministic floor

`loopctl verify-eval-substance D10-cli-broker-nomad-manage` returned exactly
`valid`: no R1-R9 hard-fail, no advisory (including no R8 plan-drift, since
neither the plan nor the eval marker moved this cycle — confirmed below by
diffing the two cycles' write-trees directly, not by trusting the claim).
Proceeded to the semantic pass.

## Confirmed independently: the only change since cycle 2 is docs/monitoring.md

Both `b46ee9a01b4353aea60bc78708620703339f0d5a` (cycle 2's tree) and
`22f22dd2e66bc98d601d30b63a609075c8eb6074` (this cycle's) are real
`git write-tree` objects (`tree_fingerprint` in `stamp.py` is literally
`git write-tree` over a throwaway index with `.loop/` stripped), so rather
than trust the hand-off summary I diffed the two tree objects directly:

    git diff --stat b46ee9a0...5d 22f22dd2...74
    docs/monitoring.md | 12 +++++-------
    1 file changed, 5 insertions(+), 7 deletions(-)

One file, one hunk. No plan file, no eval marker, no code file, no other
doc moved between cycle 2 and cycle 3. This is the ground-truth check the
task description asked for, done via the tree objects rather than by
inspecting the working directory's uncommitted status (which mixes in the
whole ticket's history since the last commit and would not by itself prove
"only this changed since cycle 2").

## Re-attach: every settled finding re-opened, not rubber-stamped

Read `.loop/scratch/D10-cli-broker-nomad-manage.adversarial/findings.json`
(11 entries, D10-ADV-1 through D10-ADV-11, spanning cycles 1-2). None of
their anchors fall in `docs/monitoring.md`, so per the reviewer-brief
resume rule each gets one absence-claim line, except the two gate findings
which the tree-fingerprint change requires re-running fresh:

- D10-ADV-1 (non-goal: `secret.py`/`env.py`/`whoami.py`/`config.py`/
  `token.py` never widen to `nomad_manage`) — no change in scope, still
  holds; none of the five appear in `git diff --stat` this cycle either.
- D10-ADV-2 (SCHEMA_VERSION gate), D10-ADV-3 (`ensure_fresh`
  independence), D10-ADV-4 (respx footgun avoided), D10-ADV-5 (logout
  accessor loop) — no change in scope, still hold; none of their anchor
  files (`session.py`, `broker.py`, `test_read_commands.py`, `logout.py`)
  appear in this cycle's diff.
- D10-ADV-7 (missing `test_live_login.py` extension, non-blocking) — no
  change in scope, still holds; the file remains absent from the diff and
  the eval's `pending-operator` row still covers it.
- D10-ADV-8 (eval-substance clean) — reaffirmed above with a fresh run,
  same clean result.
- D10-ADV-9 (no code files changed since cycle 1) — no change in scope,
  still holds; this cycle touches only `docs/monitoring.md`, so the claim
  extends unbroken through cycle 3 as well.
- D10-ADV-10 (doc rewrites match code) — no change in scope for the four
  files it covers (`cli-login.md`, `cli-read-commands.md`,
  `vault-human-auth.md`, `ROADMAP.md`); none of them changed this cycle.
- D10-ADV-6 / D10-ADV-11 (gates green) — superseded by the fresh run
  below, since the tree fingerprint moved again
  (`b46ee9a0...` to `22f22dd2...`) and the reviewer-brief rule requires a
  new check on a new tree rather than reuse of the stale trust-stamp.

## The one new claim, checked against the actual code and infra

The rewritten paragraph (`docs/monitoring.md:87-91`) makes three
checkable claims. All three were traced to source rather than accepted on
the strength of the prose:

- **"the node and job panels read through `manage` instead."**
  `monitor.py:44` reads `session.credential("nomad_manage")` — the *only*
  credential lookup in the command — and hands its token to
  `tui/monitor.py`'s `Sources`, whose `self.nodes` and `self._jobs`
  fetchers (`tui/monitor.py:55,57`) both close over that same
  `nomad_token`. There is no second, `deploy`-sourced token anywhere in
  the monitor code path, so "read through `manage` instead [of `deploy`]"
  is literally what the code does, not an approximation.
- **"`nomad/creds/deploy`'s policy grants neither `list-jobs` nor
  `node:read`."** Read `nomad_deploy_role.tf:21-49` directly: the
  `deploy` ACL policy's only namespace capabilities are `submit-job`,
  `read-job`, and the `host-volume-*` set; its own top-of-file comment
  says so explicitly ("no list-jobs / dispatch-job / read-logs / read-fs,
  and no node / agent / operator access"). `list-jobs` and `node:read`
  are absent, confirming the doc's specific capability claim rather than
  a vaguer "the policy is restrictive."
- **"A denial still names the capability it is missing."**
  `api/errors.py:43` — `f"{self.service}: denied. The token lacks
  {self.capability}."` — unchanged code, confirming the behavior the doc
  describes as already shipped is in fact already shipped.

The old text this replaced additionally referenced a "developer" Vault
policy as the thing that "already grants that read." Checked
`nomad_oidc.tf:81-83`'s comment: `developer` there is a *Vault* policy
gating whether a human may read the `nomad/creds/manage` secret, not a
Nomad ACL capability grant — a different fact from "the `manage` role's
token has `list-jobs`/`node:read`." The new text drops that reference
entirely and names the actual Nomad ACL capabilities instead
(`list-jobs`, `node:read`), which is more precise, not merely re-tensed.
No regression in accuracy from removing it.

Cross-checked the new "second Nomad credential" framing against the two
sibling docs for internal consistency: `cli-read-commands.md:107` says
"brokers two Nomad credentials" and `cli-login.md:204` lists both
`nomad/creds/deploy` and `nomad/creds/manage`. "A second... credential"
(monitoring.md) and "two credentials" (cli-read-commands.md) describe the
same fact with no contradiction.

No stale "pending" or "today they will say denied" phrasing survives
elsewhere in `docs/monitoring.md` — the only other hit for
"pending"/"not yet"/"today they will" in the file is an unrelated ufw
sentence ("carries whatever else is pending in this root", line 214),
which the diff does not touch.

## Gates, independently reproduced against the current tree

Tree `22f22dd2e66bc98d601d30b63a609075c8eb6074` differs from the stale
trust-stamp's `b46ee9a0...`, so per the reviewer-brief rule the stamp was
not reused. Ran the exact command `.loop/stamp.json` records
(`just pre_commit`, bounded, ~90s) fresh against the current tree:

    check json...............................................................Passed
    check python ast.........................................................Passed
    check for merge conflicts................................................Passed
    check yaml...............................................................Passed
    debug statements (python)................................................Passed
    detect private key.......................................................Passed
    fix end of files.........................................................Passed
    Nomad Format (fmt -recursive)............................................Passed
    Terraform Format (fmt -check -recursive).................................Passed
    Terraform Validate (per root)............................................Passed
    Ruff (lint)..............................................................Passed
    Ruff (format)............................................................Passed
    Mypy (strict, cli/)......................................................Passed
    Pytest (cli/)............................................................Passed

Full `pre-commit run --all-files`, not a scoped subset, because a
one-paragraph markdown edit is cheap enough that the whole gate finishes
inside the wall-clock bound and there was no need to reach for a trust
stamp this cycle. `loopctl verify` independently returns `ok`, confirming
`.loop/stamp.json`'s recorded result matches a freshly computed tree
fingerprint for the tree as briefed. Trust-stamp file left as cycle 2 last
wrote it (keyed to `b46ee9a0...`); not rewritten this cycle since the
full gate was re-run directly rather than trust-stamped, so there is
nothing new to record there.

## Scope

18 bindable changed files: the 17 cycle 2 bound plus `docs/monitoring.md`,
newly touched this cycle. `.loop/ledger.json` stays excluded from
`bound_paths` (a loop-owned write output that `paths_fingerprint` itself
refuses to hash — confirmed by invoking the helper directly this cycle,
same refusal cycle 2 hit). `scope:` above is the digest `paths_fingerprint`
computed over exactly this 18-path bound set, run directly against the
installed `loop_harness.stamp` module at review time from this worktree.

## Verdict

**pass.** Verified directly, not on the strength of the hand-off
description: the two cycles' certified trees are real `git write-tree`
objects, and diffing them shows exactly one file, `docs/monitoring.md`,
changed — no plan, no eval marker, no code, no other doc. Every checkable
claim in the rewritten paragraph holds against current code and
infrastructure: `monitor.py:44` and `tui/monitor.py`'s node/job fetchers
use only the `manage` credential; `nomad_deploy_role.tf`'s `deploy` policy
genuinely lacks `list-jobs` and `node:read`; `errors.py:43`'s
capability-naming denial is unchanged and already shipped. The dropped
reference to a "developer" Vault policy is a precision gain, not a
regression, since that policy actually gates a different thing (a human's
Vault read access) from what the new text claims (the Nomad ACL grants
`manage` carries as a management-type token). The full `just pre_commit`
gate reproduces green fresh against the current tree, independently, not
via stamp reuse. All ten findings the diff does not touch (D10-ADV-1
through D10-ADV-5, D10-ADV-7 through D10-ADV-10) remain settled with no
new evidence to overturn them; the two gate findings are superseded by
this cycle's fresh, green re-run.
</content>
