---
verdict: pass-with-required-fixes
tree: be54266169cff8f5cc7fe2959c0707472c5bec95
---

# Adversarial review — G3-alerts-standalone-telegram-bot

## Scope binding

The three scope-binding lines (`bound_paths:`, `scope:`, `citations:`) are
deliberately omitted. My briefing carried the tree fingerprint but no 64-hex
scope digest, and the instruction is to write the digest I was given and never
one I computed. This verdict therefore falls back to the whole-tree binding,
which is stricter. For the record, the reviewed path set was
`TODO.md`, `deployments/infrastructure/services.tf`,
`deployments/infrastructure/variables.tf`,
`deployments/infrastructure/vars/prod.tfvars.example`, `docs/monitoring.md`.

## Deterministic floor

`loopctl verify-eval-substance G3-alerts-standalone-telegram-bot` prints
`valid`, exit 0. No hard-fail, no advisories. Proceeded to the semantic pass.

`loopctl verify --expect-tree be54266169cff8f5cc7fe2959c0707472c5bec95` exits 0
in this worktree.

## Gate, re-run independently

`just pre_commit` re-run at this tree: all 27 hooks Passed, exit 0. Terraform
Format and Terraform Validate both green, so the new heredoc is valid HCL and
the `terraform fmt` alignment is correct.

`git diff HEAD --stat` shows nothing outside the five declared paths except
`.loop/ledger.json`, which the fingerprint builder strips.

---

## Finding 1 — REQUIRED FIX (medium)

**`docs/monitoring.md:97-98` names a log string Grafana does not emit.**

    97: alert bot delivers nothing until the operator presses Start on it. Grafana logs
    98: `403 bot can't initiate conversation with a user`, alerts fire normally in the

Grafana does not log that. I traced the whole call path for the deployed
version, `docker.io/grafana/grafana:11.5.2`
(`deployments/infrastructure/services/grafana.hcl:48`):

- `grafana/alerting@7b528a0bc1d5` `receivers/telegram/telegram.go:72-73` calls
  `tn.ns.SendWebhook(ctx, cmd)` and wraps any error as
  `failed to send telegram message: %w`.
- `newWebhookSyncCmd` (`telegram.go:142-183`) sets no `Validation` callback, so
  the body-reading branch downstream never runs.
- `grafana v11.5.2` `pkg/services/ngalert/notifier/sender.go:15` forwards to
  `notifications.SendWebhookSync`.
- `pkg/services/notifications/webhook.go:102-103`:

      ns.log.Debug("Webhook failed", "url", url.Redacted(), "statuscode", resp.Status, "body", string(body))
      return fmt.Errorf("webhook response status %v", resp.Status)

The Telegram description (`Forbidden: bot can't initiate conversation with a
user`) travels in the response body, and the body reaches the log only at
**Debug**. `deployments/infrastructure/services/grafana.hcl` sets no log level,
so Grafana runs at its default `info` and that line is suppressed. What the
operator actually sees is:

    failed to send telegram message: webhook response status 403 Forbidden

Why this matters rather than being pedantry: this paragraph exists (R8) so a
future bot swap does not look correctly configured while delivering nothing.
Its whole value is that the operator recognizes the symptom. An operator who
greps the logs for the documented string finds nothing and may rule out the
correct cause — which is the failure the sentence was written to prevent.

The underlying fact is right. `403` does appear in Grafana's log, and
`Forbidden: bot can't initiate conversation with a user` is the genuine
Telegram API response. Only the attribution to Grafana's log is wrong. A
wording fix settles it, for example: Telegram answers `403 Forbidden: bot
can't initiate conversation with a user`; Grafana logs only `failed to send
telegram message: webhook response status 403 Forbidden`, and shows Telegram's
description only at debug log level.

This fix keeps eval row 5 green: its scorer is `grep -n "403\|Start"`, and both
tokens survive.

I could not reproduce the 403 at runtime, which would need a live bot token and
a user who has not pressed Start. The call-path trace above is the runtime
evidence I could obtain without writing into the repo tree.

---

## Finding 2 — ADVISORY, needs an operator decision (low)

**Eval row 2's guardrail scorer matches zero files, so it greens on anything.**

Row 2's second scorer is `git grep -n 10650075 -- 'deployments/*/vars/'`. Quoted
that way it is a git pathspec, and a trailing slash after a wildcard matches
nothing. Control test with a string that IS in those files:

    git grep -n secret_mount -- 'deployments/*/vars/'    -> exit 1, no output
    git grep -n secret_mount -- 'deployments/*/vars/*'   -> 2 hits

So the scorer would have returned clean even if the operator's real ID had been
pasted into the example file. The correct pathspec is `'deployments/*/vars/*'`.
The plan's P5 writes the same glob unquoted, where the shell expands it and it
works, so the defect is confined to the eval marker.

The substantive property nonetheless holds. Checked properly: `10650075`
appears in no tracked file under `deployments/*/vars/*`. Its only tracked
occurrences outside `.loop/` are `deployments/infrastructure/variables.tf` (the
pre-existing `default`, which Q4 deliberately keeps) and the plan artifacts.
Row 2 passes on substance.

This does not block the diff. The eval marker is signed and outside the
reviewed path set, and amending it needs `loopctl eval-amend` from the marker's
signer. **Operator decision required**: leave the row as-is knowing its second
scorer is decorative, or amend the pathspec.

---

## Finding 3 — nit, no action

`docs/monitoring.md:88-89` states "no webhook is registered for this token".
That is a claim about Telegram's servers, not about this repo. The adjacent
repo-checkable half is verified: `grep -rniE "getupdates|setwebhook"` across the
tree returns only the doc's own new line. Practically true given the operator
owns the token and the repo is the only consumer. Not misleading; recorded only
so a later reader knows it was considered.

---

## What I attacked and cleared

### 1. "This diff changes nothing executable" — CLEARED, two independent proofs

**The `###` block lands in the templatefile argument map, not the jobspec.**
Read directly: the comment sits at `deployments/infrastructure/services.tf`
between `alert_rules = file(...)` and `telegram_secret = ...`, inside the `{ }`
map that is `templatefile`'s second argument. `services/grafana.hcl`, the body
`nomad_job.jobspec` stores, is not in the diff at all.

Mechanical proof rather than assertion: stripping `###` comment lines and
normalizing only leading indent and the padding around `=`, while preserving
string interiors, makes old and new `services.tf` byte-identical. The only
non-comment change is `terraform fmt` padding on two lines:

    old  telegram_secret            = "${var.secret_mount}/data/default/grafana/telegram"
    new  telegram_secret        = "${var.secret_mount}/data/default/grafana/telegram"

HCL comments and inter-token whitespace are not semantic, so `templatefile`
receives an identical map and renders a byte-identical jobspec. `nomad_job.grafana`
will not appear in the plan.

**The heredoc `description` stays out of state.** Settled empirically with a
reproducer built entirely outside the repo tree (terraform 1.14.3): applied a
config carrying the OLD one-line description plus a `terraform_data` consumer,
then swapped in the EXACT new heredoc and planned.

    No changes. Your infrastructure matches the configuration.

The resulting state file contains zero occurrences of the description text or
the variable name; its keys are `check_results, lineage, outputs, resources,
serial, terraform_version, version`. Variable metadata is not persisted.

Residual: a real `terraform plan` could still list unrelated drift. That is
outside this diff's control and section 8 already assigns it to the operator.

### 2. The Telegram claims in `### Where alerts go` — CLEARED, and this is the strongest part of the diff

The plan's named likeliest failure (R6, "the doc asserts a protection that does
not exist") does not occur. I fetched `core.telegram.org/bots/features` and
found the doc's claim stated almost verbatim by Telegram, in the BotFather
section:

    /setjoingroups - toggle whether your bot can be added to groups or not. All
    bots must be able to process direct messages, but if your bot was not
    designed to work in groups, you can disable this.

That confirms both halves at `docs/monitoring.md:91-93`: BotFather has no
setting stopping strangers from DMing the bot, and what it does control is
groups. The doc says so plainly and credits no protection that does not exist.
`grep -niE "only you can message|cannot message|can.t message"` returns nothing.

`getUpdates` is a real API method, and Telegram's own text ("two mutually
exclusive ways of receiving updates ... the getUpdates method on one hand and
webhooks on the other") backs the inbound-listener paragraph exactly.

On "a bot cannot start a conversation": I searched `/bots/api`, `/bots/faq` and
`/bots`. The rule is stated nowhere in Telegram's documentation, and `initiate`
does not appear in the relevant sense. Premise P10 already records this
honestly as UNCERTAIN, so the plan is not overclaiming. The remaining defect is
Finding 1, which is about attribution to Grafana's log, not about the rule.

One phrasing note, not a defect: "group joins are off, so the bot cannot be
added anywhere the operator did not put it". With `/setjoingroups` disabled
nobody can add the bot to a new group, while existing memberships persist, so
the sentence is defensible as written.

### 3. "Grafana reloads the swapped token by itself" — CLEARED

Verified against the jobspec rather than the sentence.
`deployments/infrastructure/services/grafana.hcl:29` declares `vault {}` on the
task; `:319` renders `bottoken` straight from the Vault path via the
consul-template `secret` function; `:327` sets `change_mode = "restart"`; and
`:326` writes to `local/provisioning/alerting/contactpoints.yaml`, which `:55`
mounts read-only at `/etc/grafana/provisioning/alerting/contactpoints.yaml`.
So a Vault edit re-renders, restarts the task, and Grafana re-provisions the
contact point on start. The doc claims no timing, which is correct, since P4's
poll interval is a Nomad client setting not visible here.

### 4. Scope — CLEAN

Every changed line traces to section 7. The `terraform fmt` realignment is not
scope creep: it touches exactly the two lines the ticket already edits
(`telegram_secret` is the section 7 anchor), it is forced by the `terraform-fmt`
gate because the new comment starts a fresh alignment group, and it changes no
parsed value. Refusing it would fail the gate.

`TODO.md` line 1 was verbatim what R7 quotes and only that line is gone. The
doc section sits at `docs/monitoring.md:67`, between `### If Vault is down`
(`:54`) and `### Why they are not behind the edge proxy` (`:101`), as section 7
requires. The short-form path style `services/grafana.hcl` matches the file's
existing convention (`:276`, `:468`, `:493`, `:504`, `:516`), so it follows
CLAUDE.md section 3 rather than inventing a style.

### 5. Eval rows runnable here

- **Row 1 — PASS.** `grep -n "reuses Hermes" ...variables.tf` exits 1. The
  replacement carries both required properties ("the operator's own numeric
  user ID" and "that bot's entire outbound scope") and names neither Hermes nor
  its Vault path.
- **Row 2 — PASS on substance**, with the scorer defect in Finding 2. Exactly
  one line, `telegram_alert_chat_id = "0000000000"`, matching the style of
  `deployments/applications/vars/prod.tfvars.example:6`.
- **Row 4 — PASS**, and strongly, per section 2 above. Deterministic floor
  clean, human read clean, backed by Telegram's own page.
- **Row 5 — PASS by the row's letter** (`grep -n "403\|Start"` matches, and the
  explanation is present), but the row's expected wording bakes in the same
  misattribution as Finding 1, so the grep passing is not evidence the sentence
  is true.
- **Rows 3 and 6** carry `verdict: pending-operator` and need the live cluster.
  Not run.

### 6. Premises re-probed

P1 (`deployments/applications/services.tf:241` reads `default/hermes/telegram`),
P2 (`grep -rn "telegram" deployments/*/secrets.tf` exits 1), P5 (four tracked
paths under the vars dirs), P6 and P7 all reproduce. So the R4 comment's
substantive claims are true: Hermes really does read a different path, and no
Terraform resource writes either value. That comment records an absence and a
cross-root fact, which is exactly the warranted case in
`.claude/rules/minimal-comments.md`.

P9 remains unverifiable from the repo, as the plan states. Nothing in this diff
depends on it being checkable here.

### 7. Doc quality (R5)

New section: zero lines over 80 columns, zero em dashes in the file, no ` -- `,
no tier-1 slop, no semicolon splice, no participial tail, no smart quotes.

---

## Verdict

**pass-with-required-fixes.** Nothing is broken, no gate is red, no Terraform
state moves, and the diff's central claim survives two independent proofs. The
plan's own named likeliest failure is not merely avoided but handled better
than the plan required, with Telegram's wording confirmed at the source.

Finding 1 is the one thing that should not ship as written: a newly-added
diagnostic sentence names a log string the deployed Grafana does not emit, in
the one paragraph whose entire value is helping an operator recognize a silent
failure. It is a wording change confined to `docs/monitoring.md:97-98`.

Finding 2 is for the operator, not the implementer, and does not block.

Scratch artifacts, including the findings ledger, are under
`.loop/scratch/G3-alerts-standalone-telegram-bot.adversarial/`.
