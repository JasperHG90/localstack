---
epic = "rollout"
priority = 65
summary = """
Record in the repo that Grafana alerts now go through OrangeClusterAlertBot, a
standalone send-only bot, not the shared Hermes bot. The Vault token was
already swapped by the operator, so no value changes: the work is correcting a
stale variable description, adding the missing variable to the tfvars example,
documenting where alerts go and what makes the bot scoped to one person, and
striking the finished TODO item.
"""
tags = ["grafana", "alerting", "telegram", "terraform", "docs"]
premise = { Q1 = "10650075 is the operator's personal Telegram user ID, not a group or channel ID, so a private chat's id carries to any bot unchanged", Q2 = "BotFather group-join for OrangeClusterAlertBot is off as of 2026-09-06", P9 = "the Vault KV value at default/grafana/telegram already holds the OrangeClusterAlertBot token, swapped by the operator before this ticket existed; operator statement 2026-09-06, unverifiable from this repo" }
---

# Ticket: G3-alerts-standalone-telegram-bot

## 1. Title

Point the repo's record of Grafana alerting at OrangeClusterAlertBot, the
standalone send-only alert bot, and write down what makes it scoped to one
person.

## 2. Size / Effort

**S.** Five files, no resource address changes, no jobspec body changes, no
`terraform plan` diff expected. The doc subsection is the only new prose.

## 3. Triggered by

Operator request, 2026-09-06: alerts move off the shared Hermes bot onto a new
`OrangeClusterAlertBot`. Operator had already swapped the Vault token before
raising it. Closes `TODO.md:1`.

## 4. Context

- Grafana's Telegram contact point reads its token from
  `default/grafana/telegram` (`deployments/infrastructure/services.tf:523`) and
  sends to one chat id (`deployments/infrastructure/services.tf:524`).
- Hermes reads a different path, `default/hermes/telegram`
  (`deployments/applications/services.tf:241`). The two bots have therefore
  been separate at the token level all along; only the token VALUE was shared,
  and the operator has already replaced the Grafana one.
- Neither secret is written by Terraform. Probe, 2026-09-06:
  `grep -rn "telegram" deployments/*/secrets.tf` exits 1 with no output. Both
  are hand-managed in Vault, so no Terraform change can or should touch them.
- `deployments/infrastructure/variables.tf:17` still describes the chat id as
  "(reuses Hermes bot token from Vault)". That parenthetical is now false and
  is the only place in the repo that describes the arrangement at all.
- `deployments/infrastructure/vars/prod.tfvars.example` sets three variables
  and omits `telegram_alert_chat_id` entirely. Probe, 2026-09-06:
  `git ls-files deployments/*/vars/` lists only `backend-config.hcl` and
  `prod.tfvars.example` in each root, so the real `prod.tfvars` is untracked
  and the example is the only tracked place a fresh checkout learns the
  variable exists.
- `docs/monitoring.md` documents reaching Prometheus, Loki, Tempo and Grafana,
  signing in, and the firewall rules, and says nothing about alerting. Probe,
  2026-09-06: `grep -rn -i "telegram" docs/*.md` exits 1 with no output.

What is missing is not wiring. It is the written record: which bot Grafana
talks to, why two Vault telegram paths exist, and what actually enforces
"only the operator sees these alerts".

## 5. Non-goals / out of scope

- **No Vault writes.** The token at `default/grafana/telegram` is
  operator-managed and already correct. No `vault_kv_secret_v2` resource is
  added for it.
- **No change to the chat id value.** Operator confirmed 2026-09-06 that
  `10650075` is their personal Telegram user ID. A private chat's id equals the
  user id whichever bot sends, so the existing value carries over.
- **No rename of the contact point.** The `telegram-default` uid at
  `deployments/infrastructure/services/grafana.hcl:315` stays. See Open
  Question Q3.
- **No change to Hermes.** `deployments/applications/` is read here as the
  precedent for per-user scoping and is not edited.
- **No new alert rules, routes, or severities.**
  `deployments/infrastructure/services/grafana/alert-rules.yaml` is untouched.
- **No BotFather automation.** Those settings have no API and are recorded in
  the doc as operator steps, not scripted.

## 6. Requirements & restrictions

- R1. `deployments/infrastructure/variables.tf:17` must stop claiming the alert
  chat reuses the Hermes bot token, and must instead state the two properties
  the value carries: it is the operator's own Telegram user ID, and it is the
  entire outbound scope of the alert bot.
- R2. `telegram_alert_chat_id` must appear in
  `deployments/infrastructure/vars/prod.tfvars.example` with a placeholder, so
  a fresh checkout sees it. Match the existing placeholder style of
  `deployments/applications/vars/prod.tfvars.example:6`, which uses
  `"0000000000"` for the sibling variable.
- R3. Terraform edits reuse the existing subsystem files. Per
  `.claude/rules/terraform-file-layout.md`,
  `deployments/infrastructure/variables.tf` holds input variables and
  `deployments/infrastructure/services.tf` holds Nomad jobs. No new `.tf` file.
- R4. Any comment added to `deployments/infrastructure/services.tf` must record
  a reason absent from the source, per `.claude/rules/minimal-comments.md`:
  why two Vault telegram paths exist and who owns their values. It must not
  narrate the line below it.
- R5. The doc subsection follows `.claude/rules/plain-language.md` and passes
  `.claude/rules/slop-scan-for-docs.md`: prose wrapped at 80 columns to match
  the rest of `docs/monitoring.md`, zero em dashes, no "comprehensive",
  "robust", "seamless", no "not just X but Y", no participial tail-loading.
- R6. The doc must distinguish the two halves of the scoping honestly, because
  they have different enforcers: outbound is the single `chatid` in the
  contact point, inbound is the absence of any reader of the bot's updates.
  BotFather's group switch must not be described as restricting who may DM the
  bot, because it does not.
- R8. The doc must name the delivery precondition: the operator has to open the
  chat with the alert bot themselves, because Telegram forbids a bot from
  starting a conversation, and a send into a chat that was never opened fails
  rather than queueing. Nothing else in the repo would say so, and it is the
  step the next bot swap will trip over. Name it even though this repo cannot
  prove it; see P10.
- R7. `TODO.md:1` reads `- Use telegram channel for alerts & split from the
  hermes bot`. Both halves are satisfied, so the line is deleted, but the
  reason has to be recorded rather than assumed. The split half is this
  ticket. The channel half is satisfied by the operator's own usage: their
  request of 2026-09-06 opened "I'm changing the telegram channel for alerts
  -- they should now go to a new bot called OrangeClusterAlertBot", using
  "channel" for the destination and then naming a bot, and they separately
  confirmed the destination is their personal user ID rather than a Telegram
  channel. So "channel" in that TODO line is loose speech for "a separate
  Telegram destination", which this ticket delivers. Were that reading wrong,
  the correct edit is to narrow the line to its channel half rather than
  delete it.

## 7. Code surface

| File | Anchor | Change | Requirement |
|---|---|---|---|
| `deployments/infrastructure/variables.tf` | `:17` | Rewrite the `description` of `telegram_alert_chat_id`: operator's own user ID, the alert bot's whole outbound scope, no longer the Hermes token. | R1, R3 |
| `deployments/infrastructure/services.tf` | `:523` | Add a `###` note above the `telegram_secret` argument recording that this path holds the standalone alert bot's token, hand-managed in Vault, separate from `default/hermes/telegram`. | R3, R4 |
| `deployments/infrastructure/vars/prod.tfvars.example` | `:3` | Append `telegram_alert_chat_id` with a placeholder and a one-line comment. | R2 |
| `docs/monitoring.md` | after `:66` | New `### Where alerts go` subsection between "If Vault is down" and "Why they are not behind the edge proxy". Covers both scoping halves and the open-the-chat precondition. | R5, R6, R8 |
| `TODO.md` | `:1` | Delete the item, both halves being satisfied per R7's recorded reasoning. | R7 |

No file outside this table is touched. Needing one is the
`out-of-scope-fix-needed` blocker.

## 8. Tests & validation gates

**No automated test is added, and that is a deliberate claim, not an
omission.** The diff changes a Terraform variable `description`, two comments,
one example-file line, one doc subsection, and one TODO line. None of it is
executable: `description` is not persisted in Terraform state, and the
`###` comments sit in the `templatefile` argument map in
`deployments/infrastructure/services.tf`, not inside the jobspec body that
`nomad_job.jobspec` stores. There is no behavior to assert, so there is no
test file in section 7 to hold one. `.claude/rules/python-testing.md` governs
code changes; this diff contains no code path.

Gates, discovered from `.loop/config.json` (`"gates": ["just pre_commit"]`)
and `.pre-commit-config.yaml`:

1. `just pre_commit` runs `pre-commit run --all-files`. The hooks that bite
   here are `terraform-fmt` (`terraform fmt -check -recursive`),
   `terraform-validate` (`scripts/tf_validate.sh`), `end-of-file-fixer`, and
   `check-yaml`. Must be green. Covers R1, R2, R3, R7.
2. `terraform plan` in `deployments/infrastructure` must report **0 to change**,
   per `.claude/rules/terraform-file-layout.md`. This needs live Vault and
   Nomad credentials, so it is an operator-run gate, not a sandbox one. Any
   resource it does list must be accounted for before the ticket closes.
   Covers R3 and R4, which together assert the edits stay outside the jobspec.
3. Doc review by reading, against R5 and R6. The slop scan in
   `.claude/rules/slop-scan-for-docs.md` is the checklist; the em-dash count
   (`grep -o "—" docs/monitoring.md | wc -l`) and the 80-column wrap are the
   two mechanical parts of it.

Live verification belongs in the eval marker, not here: whether a firing alert
actually lands in OrangeClusterAlertBot is a property of the running cluster
and the swapped Vault token, not of this diff. The scenario set is
`.loop/evals/G3-alerts-standalone-telegram-bot.md`; its rows 3 and 6 carry
`verdict: pending-operator` for exactly that reason.

## 9. Risk assessment

- **Blast radius: near zero.** No resource address, no jobspec body, no Vault
  path, no variable value changes. Worst realistic outcome of a mistake in the
  Terraform half is a `terraform fmt` failure caught by the gate.
- **Reversibility: total.** Every line is a comment, a description, an example
  value, or prose. `git revert` restores the previous state with no live
  effect.
- **Likeliest failure mode: the doc asserts a protection that does not
  exist.** Writing "BotFather restricts who can message the bot" would be
  false and would leave the operator believing a stranger cannot DM it. R6
  exists to catch this, and it is the one thing the reviewer should read
  hardest.
- **Second failure mode: the ticket is mistaken for the cutover.** The cutover
  already happened in Vault. If a reader concludes alerts start flowing only
  once this merges, they will misdiagnose a delivery failure. The doc must
  say the token is hand-managed.

## 10. Subtickets

Single iteration, ordered:

1. Terraform, covering R1, R2, R3, R4:
   `deployments/infrastructure/variables.tf:17` description,
   `deployments/infrastructure/services.tf:523` comment,
   `deployments/infrastructure/vars/prod.tfvars.example` line.
2. `docs/monitoring.md`: the `### Where alerts go` subsection, covering R5
   and R6.
3. `TODO.md:1` removal, covering R7.
4. `just pre_commit`, then hand the operator the `terraform plan` gate.

## 11. Open questions

- **Q1 — resolved 2026-09-06.** Is `10650075` a personal user ID or a group
  id? Operator confirmed: personal user ID. Recorded in the `premise`
  front-matter. Had it been a group, the ticket would have grown a value change
  and a membership audit.
- **Q2 — resolved 2026-09-06.** Should the repo document the BotFather
  settings? Operator confirmed yes, and separately confirmed group-join is now
  off. The doc records it as done, not as a pending step.
- **Q3 — open, recommendation: leave it.** Should the contact point uid and
  name `telegram-default`
  (`deployments/infrastructure/services/grafana.hcl:315`) be renamed to name
  the new bot? Renaming means editing the jobspec, which re-registers the job,
  and updating four `receiver:` references in the notification policy
  (`deployments/infrastructure/services/grafana.hcl:336`, `:342`, `:348`).
  Grafana provisions contact points by uid, so the old uid would be orphaned
  in its database rather than replaced. The name is generic enough to survive
  a bot swap, which is exactly what just happened to it. Recommend keeping it
  and spending nothing here.
- **Q4 — open, recommendation: keep.** `deployments/infrastructure/variables.tf`
  carries `default = "10650075"`, a real personal identifier in a tracked file.
  Dropping the default would force every apply to supply it. The root already
  commits the operator's real email as a default in the same file
  (`deployments/infrastructure/variables.tf:33`, `acme_email`), so removing
  this one alone buys nothing. Recommend keeping the default and adding the
  example line per R2.

## Premises / assumptions

- **P1.** Grafana's alert token and Hermes's token read from two different
  Vault paths already. `Evidence:` `deployments/infrastructure/services.tf:523`
  reads `default/grafana/telegram`;
  `deployments/applications/services.tf:241` reads `default/hermes/telegram`.

- **P2.** Neither telegram secret is written by Terraform, so the repo cannot
  and must not manage the token value. `probe:`
  `grep -rn "telegram" deployments/*/secrets.tf` exits 1 with no output.
  Probed 2026-09-06.

- **P3.** `10650075` is the operator's personal Telegram user ID, so the value
  is bot-independent and needs no change. `Evidence:` operator statement,
  2026-09-06, answering a direct question that named both readings. Telegram
  assigns a private chat the same id as the user, so the chat survives the bot
  swap.

- **P4.** Grafana reloads the swapped token on its own, with no Terraform run.
  `Evidence:` `deployments/infrastructure/services/grafana.hcl:29` declares
  `vault {}` on the task; `:319` renders `bottoken` from the Vault path inside
  a `template` stanza whose `change_mode` at `:327` is `restart`, so
  consul-template re-reads the KV2 secret on its poll and restarts the task,
  and Grafana re-provisions the contact point on start. **UNCERTAIN** as to
  timing: the poll interval is a Nomad client setting not visible in this repo.
  The eval's live row settles it; an operator can force it with a job restart.

- **P5.** `deployments/infrastructure/vars/prod.tfvars` is untracked, so the
  example file is the only tracked record of the variable. `probe:`
  `git ls-files deployments/*/vars/` returns four paths, every one of them a
  `backend-config.hcl` or a `prod.tfvars.example`. Probed 2026-09-06.

- **P6.** No documentation covers alerting today. `probe:`
  `grep -rn -i "telegram" docs/*.md` exits 1 with no output. Probed
  2026-09-06.

- **P7.** Nothing in this repo reads the alert bot's incoming updates, so
  inbound messages are dropped by absence rather than by policy. `probe:`
  `git grep -n "telegram_secret"` returns one alert-side consumer,
  `deployments/infrastructure/services/grafana.hcl:319`, which renders
  `bottoken` into a send-only contact point and never reads back. `probe:`
  `grep -rniE "getupdates|setwebhook" . --exclude-dir=.git --exclude-dir=.loop
  --exclude-dir=.terraform` exits 1 with no output. Both probed 2026-09-06.
  The earlier form of the second probe was a BRE whose `|` was literal, so it
  could not have matched; the `-E` form above is the one that was run.

- **P9.** The Vault KV value at `default/grafana/telegram` already holds the
  OrangeClusterAlertBot token. This is the assumption every other premise
  rests on: if it is false, the diff documents an arrangement that does not
  exist. `Evidence:` operator statement, 2026-09-06, that the swap was done
  before the request was raised. **UNCERTAIN**, and unverifiable from this
  repo by construction: `deployments/infrastructure/services.tf:523` names the
  path and carries no value, and P2 establishes that no Terraform resource
  writes it. Settling it means reading Vault, which is an operator action.

- **P10.** A private chat accepts Grafana's sends only once the operator has
  opened it, because Telegram forbids a bot from starting a conversation.
  Until then a send fails rather than queueing. **UNCERTAIN**: the exact rule
  is not stated in `core.telegram.org/bots/api`, `/bots/features`, `/bots/faq`
  or `/bots`, so this rests on the widely reported `403 bot can't initiate
  conversation with a user` response rather than on vendor documentation. It
  is named because it is the one condition under which every line of this
  diff is correct and alerts still do not arrive. R8 carries it into the doc.

- **P8.** The diff moves no Terraform state. `Evidence:` a variable
  `description` is not stored in state, and the `###` comments land in the
  `templatefile` argument map in `deployments/infrastructure/services.tf:523`,
  outside the `.hcl` body that `.claude/rules/terraform-file-layout.md` warns
  is folded into `nomad_job.jobspec`. **UNCERTAIN** until the operator runs
  the plan, which is why section 8 carries it as a gate.
