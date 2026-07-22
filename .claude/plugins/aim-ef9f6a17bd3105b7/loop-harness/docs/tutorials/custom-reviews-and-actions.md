# Tutorial: add a custom review pass and a custom action stage

By the end of this tutorial your loop will dispatch a review pass you
wrote yourself, whose verdict blocks commits until it passes, plus an
action stage you wrote yourself that runs after every implementation.
You will build both from scratch, wire them into `.loop/config.json`,
and confirm the loop picks them up.

This is a hands-on lesson, not a reference. Follow the steps in order
and you will reach a working result. For the full config schema, read
the "Extending the loop" section of the README; for how the machinery
works underneath, read `docs/onboarding.md`. This page teaches by
building.

## Before you start

You need a repo that already runs the loop harness: a `.loop/config.json`
with at least one gate and the default `adversarial` review pass. If you
do not have one yet, run the `init-loop` skill: it scaffolds the config
and proposes real gates for you.

Throughout, `loopctl` is shorthand for the harness CLI. The SessionStart
hook prints its exact path as `[loop] ctl: ...`, so the skill and these
steps can call it without you locating it.

You will create two files under the project's Claude directories and edit
one config file. Nothing here touches the harness code.

---

## Part 1: a custom review pass

A **review pass** is one reviewer agent the loop runs during the
`adversarial-review` stage. Each enabled pass writes its own verdict file
bound to the exact tree it reviewed, and the commit gate refuses the
commit until every enabled pass has a passing verdict on the current
tree. The plugin ships three passes; you are about to add a fourth.

Our example pass scans the diff for hardcoded secrets (API keys,
passwords, tokens) and fails when it finds one. Call it
`loop-secrets-reviewer`.

### Step 1: write the reviewer agent

A review-pass agent is a normal Claude Code subagent. Create
`.claude/agents/loop-secrets-reviewer.md`:

```markdown
---
name: loop-secrets-reviewer
description: Secrets review pass for the loop. Scans a ticket diff for hardcoded credentials (API keys, passwords, tokens, private keys) and FAILS its verdict when it finds one. WRITES its tree-bound verdict to the verdict file named in its briefing. Read-only toward all repo files; its only write is the verdict file.
tools: Read, Grep, Glob, Bash, Write
---

You are the secrets reviewer inside an autonomous ticket loop. Another
agent's change is handed to you as a ticket (the contract) plus a diff
(the change). Your one job: decide whether the diff introduces a
hardcoded secret.

Scan the added lines only. Treat as a finding any literal API key,
password, access token, private key block, or connection string with an
inline credential. A value read from an environment variable or a secrets
manager is NOT a finding. A placeholder in an example or test fixture
(`"your-key-here"`, `"xxxx"`, an obvious dummy) is NOT a finding; anchor
each real finding to a file:line so the reader can check it.

Never edit repo files. Never run mutating git commands.

Your final act is the one write you are allowed: write your verdict,
complete, to the verdict path in your briefing (the slug, the pass id,
and the tree fingerprint are all in the briefing). The file MUST contain,
near the top:

    verdict: pass | fail
    tree: <the 40-hex tree fingerprint you were given>

followed by your findings with evidence. The commit gate parses the
`tree:` line and refuses any commit whose tree differs, so never write a
fingerprint you were not given. After writing the file, also return the
verdict as your final message.
```

Two lines in that agent are load-bearing, and getting either wrong is the
one way this fails silently:

- The `verdict:` line. The commit gate reads it to decide pass or fail.
- The `tree:` line. It must echo the fingerprint the loop hands the agent
  in its briefing. This is what binds the verdict to one exact tree, so a
  post-review edit voids it and forces a fresh review. An agent that
  writes a verdict without a matching `tree:` line will never let a commit
  through, and the failure looks like a stuck loop, not a typo.

Everything else is the review logic, and it is yours to write.

### Step 2: enable the pass in config

Open `.loop/config.json` and add your pass to the `review_passes` list:

```json
{
  "review_passes": [
    { "id": "adversarial", "agent": "loop-reviewer",         "enabled": true },
    { "id": "secrets",     "agent": "loop-secrets-reviewer",  "enabled": true }
  ]
}
```

The `id` names the verdict file (`.loop/verdicts/<slug>.secrets.md`) and
must be a unique kebab-case token. The `agent` is the `name` from the
front matter of the file you just wrote. Leave `adversarial` enabled: you
are adding a reviewer, not replacing one.

Editing `config.json` changes the verification contract, so it stales a
green stamp: the loop re-runs the gates and re-reviews on your next
`loopctl stamp`. That is expected.

### Step 3: confirm the config parses

The config is plain JSON validated against a schema. Check the JSON first:

```bash
python3 -m json.tool .loop/config.json
```

If that prints your config back, the syntax is good. The harness validates
the schema (unique ids, a non-empty `agent`, valid types) on the next
`loopctl stamp` and at session start. A malformed pass raises a
`ConfigError` naming the offending entry, so a broken config fails loudly
rather than skipping review.

### Step 4: watch it gate a commit

Run any ticket through the loop (see the worked example in
`docs/onboarding.md` if you need a refresher). At the `adversarial-review`
stage, the loop now dispatches both passes concurrently against one frozen
tree fingerprint. Each writes its own verdict:

```console
$ ls .loop/verdicts/
my-ticket.adversarial.md
my-ticket.secrets.md
```

Open `my-ticket.secrets.md` and you will see your agent's own words:

```markdown
verdict: pass
tree: 4f2a9c1e7b3d8a05f6c2e1b9d4a7c3e8f0b6d2a1

Scanned the added lines. No hardcoded credentials: the new client reads
its token from os.environ["API_TOKEN"] (src/app/client.py:14). No findings.
```

Now the payoff. The commit gate requires a passing, tree-bound verdict
from **every** enabled pass. If your secrets reviewer writes
`verdict: fail`, the commit is blocked even when the adversarial pass
passed and the stamp is green. You have added an enforced check to the
loop without touching a line of harness code.

To prove the block to yourself, add a line like `API_KEY =
"sk-live-abc123"` inside the ticket's scope, re-run the review, and watch
the secrets verdict come back `fail` and the commit refuse.

---

## Part 2: a custom action stage

A review pass gates the commit. An **action stage** does not: it is
advisory. The loop dispatches it at a lifecycle anchor to *do* something
(edit a file, send a report), but it writes no verdict and blocks nothing.
Use an action stage when you want work done automatically, not when you
want a rule enforced. If you need enforcement, use a review pass.

Our example keeps a changelog current: after every implementation, an
agent appends a one-line entry to `CHANGELOG.md`. Call it
`loop-changelog-writer`.

### Step 1: write the action agent

Create `.claude/agents/loop-changelog-writer.md`:

```markdown
---
name: loop-changelog-writer
description: Changelog-writer action stage for the loop. Given a ticket and its diff, appends one entry describing the change under the Unreleased heading in CHANGELOG.md. Advisory: produces no verdict and does not gate the commit.
tools: Read, Edit, Write
---

You are the changelog writer inside an autonomous ticket loop. You are
handed a ticket (the contract) and the diff (the change). Append exactly
one bullet under the "## [Unreleased]" heading in CHANGELOG.md, phrased
for a human reading release notes: what changed and why, one line.

Create CHANGELOG.md with an "## [Unreleased]" heading if it does not
exist. Touch nothing else. Do not restate the diff line by line; describe
the user-visible change. You write no verdict; your edit is your only
output.
```

Notice the smaller tool set: an action agent that edits files needs
`Edit`/`Write`, and it deliberately has no verdict contract to satisfy.

### Step 2: enable the stage in config

Add an `action_stages` list to `.loop/config.json`:

```json
{
  "action_stages": [
    { "id": "update-changelog", "type": "agent", "ref": "loop-changelog-writer", "after": "implementing" }
  ]
}
```

The `after` value is the key decision. Your agent edits a file, so it
**must** run at `after: implementing`. That anchor fires before the stamp,
so the changelog edit is stamped, reviewed, and committed together with
the code. A tree-mutating stage that ran later would change the tree after
the stamp and stale it, forcing a re-gate. An action that only reports
(and edits nothing) can safely run at `after: done`, where it fires after
the ticket closes and is purely informational.

The `type` is `agent` here; it can also be `skill` to dispatch a project
skill by name instead. The `id` must be unique across both `review_passes`
and `action_stages`.

### Step 3: confirm and run

Validate the JSON as before:

```bash
python3 -m json.tool .loop/config.json
```

Then run a ticket. During implementation, before the stamp, the loop
dispatches your writer. When the ticket commits, its `CHANGELOG.md` entry
rides in the same commit as the code:

```console
$ git show --stat HEAD | head
    my-ticket: add rate limiting to the API client

 CHANGELOG.md          | 1 +
 src/app/client.py     | 12 ++++++++++
 tests/test_client.py  |  8 ++++++++
```

The changelog line is part of the change, not a follow-up commit. That is
the whole point of the `after: implementing` anchor.

---

## Part 3: an action, then gated

Parts 1 and 2 built the two halves separately: a review pass that gates,
an action stage that works. The next question writes itself: what if you
want an action to run AND be enforced? There is no single "gated action"
switch. You compose the two pieces you already have. The action stage
does the work; a review pass gates on the result. Both bind to the same
frozen tree, so they travel in one commit.

Take the changelog from Part 2. The `loop-changelog-writer` action
appends an entry, but nothing proves it did: an action writes no verdict,
so a run that quietly skipped the changelog commits just the same. To
turn "the changelog is written" into "the changelog is enforced", add a
review pass that fails when a code change carries no changelog entry.

### Step 1: write the gating reviewer

Create `.claude/agents/loop-changelog-reviewer.md`:

```markdown
---
name: loop-changelog-reviewer
description: Changelog review pass for the loop. FAILS its verdict when a diff changes src/ but adds no entry under the Unreleased heading in CHANGELOG.md. WRITES its tree-bound verdict to the verdict file named in its briefing. Read-only toward all repo files; its only write is the verdict file.
tools: Read, Grep, Glob, Bash, Write
---

You are the changelog reviewer inside an autonomous ticket loop. You are
handed a ticket (the contract) and a diff (the change). Your one job:
decide whether a user-visible code change was recorded in the changelog.

If the diff touches src/ but the added lines under the "## [Unreleased]"
heading in CHANGELOG.md are empty, that is a finding: fail. A docs-only
or test-only diff needs no entry, so pass. Anchor a finding to the
missing evidence (src/ changed at file:line; no Unreleased entry).

Never edit repo files. Never run mutating git commands.

Your final act is the one write you are allowed: write your verdict,
complete, to the verdict path in your briefing, with the `verdict:` and
`tree:` lines at the top, exactly as the secrets reviewer in Part 1 did.
Then return the verdict as your final message.
```

### Step 2: enable both, in order

The action and the reviewer are two separate config entries: the action
writes the changelog during implementation, the reviewer gates on what
the action produced:

```json
{
  "action_stages": [
    { "id": "update-changelog", "type": "agent", "ref": "loop-changelog-writer", "after": "implementing" }
  ],
  "review_passes": [
    { "id": "adversarial", "agent": "loop-reviewer",           "enabled": true },
    { "id": "changelog",   "agent": "loop-changelog-reviewer",  "enabled": true }
  ]
}
```

The lifecycle orders them, and that ordering is what makes the pattern
work. The action fires at `after: implementing`, before the stamp, so its
changelog edit is stamped, reviewed, and committed with the code. The
review pass then reads that same frozen tree and gates the commit. When
the action wrote the entry, the reviewer passes and the commit proceeds.
When anything left the changelog empty, the reviewer fails and the commit
is refused, exactly like the secrets pass in Part 1.

That is the whole pattern. The action does the work so a human does not
have to; the review pass makes the work mandatory. Each half alone falls
short: the action without the pass is advisory, and the pass without the
action gates a chore no one is doing. Together they automate the work and
enforce it in the same commit.

---

## What you learned, and which one to reach for

You built both halves of the loop's extension surface, and the way to
combine them:

| You want | Build a | It runs at | It gates commits? |
|----------|---------|-----------|-------------------|
| An enforced check | review pass | `adversarial-review` | Yes, via a tree-bound verdict |
| Automatic work done | action stage | any lifecycle anchor | No, advisory only |
| Work done AND enforced | action stage + a review pass | `implementing`, then `adversarial-review` | Yes, the pass gates the action's result |

The rule of thumb: if a human should be blocked from committing when the
check fails, write a review pass, because only a verdict gates the commit.
If you just want a chore handled, write an action stage. Wanting docs kept
fresh is the classic trap: the `loop-doc-writer` action *writes* docs, but
only the `documentation` review pass, whose verdict gates the commit, can
*guarantee* they stay fresh. Writing is advisory; enforcing needs a
verdict. When you want both, compose them as Part 3 shows: the action
keeps the artifact current, and a review pass makes it mandatory.

From here, the README's "Extending the loop" section is the reference for
every field you touched, and `docs/onboarding.md` explains why the verdict
and the tree fingerprint work the way they do.
