---
verdict: pass-with-required-fixes
plan: 4e42eb64d8233529c327900dbe4cda44e6e907a97670c3d1d6289f4d6c4d5890
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 9210fc8613912ed09e4a26e58491db561f8e74045881665fe71a0ea83f2af4a8
fix_sections: front-matter, 6, 7, premises
citations: deployments/infrastructure/services.tf:523 =       telegram_secret            = "${var.secret_mount}/data/default/grafana/telegram"
  deployments/infrastructure/services.tf:524 =       telegram_alert_chat_id     = var.telegram_alert_chat_id
  deployments/applications/services.tf:241 =       telegram_secret                = "${var.secret_mount}/data/default/hermes/telegram"
  deployments/infrastructure/variables.tf:17 =   description = "Telegram chat ID that receives Grafana alerts (reuses Hermes bot token from Vault)."
  deployments/infrastructure/variables.tf:19 =   default     = "10650075"
  deployments/applications/variables.tf:17 =   description = "Telegram numeric user ID authorised to interact with the Hermes bot (also used as the home channel)"
  deployments/applications/vars/prod.tfvars:4 = telegram_allowed_users = "10650075"
  deployments/applications/vars/prod.tfvars.example:6 = telegram_allowed_users = "0000000000"
  deployments/infrastructure/vars/prod.tfvars.example:3 = gcs_backup_bucket = "your-cluster-backup-bucket"
  deployments/infrastructure/services/grafana.hcl:29 =       vault {}
  deployments/infrastructure/services/grafana.hcl:315 =               - uid: telegram-default
  deployments/infrastructure/services/grafana.hcl:319 =                   bottoken: '{{ with secret "${telegram_secret}" }}{{ .Data.data.bot_token }}{{ end }}'
  deployments/infrastructure/services/grafana.hcl:327 =         change_mode = "restart"
  TODO.md:1 = - Use telegram channel for alerts & split from the hermes bot
  docs/monitoring.md:67 = ### Why they are not behind the edge proxy
  .claude/rules/python-testing.md:3 = description: How to write, run, and locate tests in Python projects (pytest + uv). Read before adding or changing Python code.
  .claude/rules/python-testing.md:7 = Every code change ships with a test. You cannot claim code works or a
  .claude/rules/terraform-file-layout.md:20 = | `variables.tf` | input variables |
  .claude/rules/terraform-file-layout.md:21 = | `services.tf` | Nomad jobs, host volumes, and the firewall rules that open their ports |
  .claude/rules/terraform-file-layout.md:71 = - **Jobspec files.** `templatefile("services/x.hcl", ...)` folds that whole
  .claude/rules/minimal-comments.md:10 = something absent from the source: a reason, a constraint imposed from outside
  .loop/config.json:3 =     "just pre_commit"
  justfile:19 =     pre-commit run --all-files
  .pre-commit-config.yaml:24 =         entry: terraform fmt -check -recursive
---

rebound-by: Jasper 2026-09-06T10:58:34Z (reason: RF1-RF4 applied; edits confined to the reviewer's fix_sections (front-matter, 6, 7, premises). RF1 adds premise P9 for the already-swapped Vault token, RF2 repairs P7's non-matching BRE probe, RF3 records why TODO.md:1 is deleted whole, RF4 adds R8 and P10 for the open-the-chat delivery precondition.)

# Plan review: G3-alerts-standalone-telegram-bot

## Deterministic floor

`loopctl verify-plan G3-alerts-standalone-telegram-bot` printed `valid`,
exit 0. The plan file's sha256 matches the fingerprint I was given. Proceeded
to falsification.

## Premise verdict

**PARTIALLY SOUND.**

The spine survived. The central claim the operator asked me to break, that this
change needs no functional edit, holds: P3 is corroborated by the repo itself
rather than by testimony alone, P8's two halves are both demonstrated, and
section 8's refusal to add a test survives `.claude/rules/python-testing.md`.
Three things did not survive: R7 deletes a TODO item this ticket only half
completes, the single most load-bearing assumption in the ticket is in no
premise at all, and P7's cited probe is a shell expression that cannot match
anything.

## Per-assumption findings

### Stated premises

- **P1 — HOLDS.** `deployments/infrastructure/services.tf:523`
  > `      telegram_secret            = "${var.secret_mount}/data/default/grafana/telegram"`

  and `deployments/applications/services.tf:241`
  > `      telegram_secret                = "${var.secret_mount}/data/default/hermes/telegram"`

  Two distinct Vault paths, each on the cited line itself. The declaration is
  the line, not a nearby mention.

- **P2 — HOLDS.** Probe rerun verbatim, 2026-09-06:
  `grep -rn "telegram" deployments/*/secrets.tf` produced no output and
  `exit=1`. I widened it rather than accepting the narrow form:
  `grep -rni "telegram" deployments/ --include="*.tf"` returns nine lines, all
  of them in `services.tf` or `variables.tf` and none in a `secrets.tf` or any
  `vault_kv_secret_v2` write. No Terraform resource manages either token value.

- **P3 — HOLDS, and on stronger evidence than the plan claims.** The plan rests
  P3 on operator testimony. The repo corroborates it independently.
  `deployments/applications/variables.tf:17`
  > `  description = "Telegram numeric user ID authorised to interact with the Hermes bot (also used as the home channel)"`

  and `deployments/applications/vars/prod.tfvars:4`
  > `telegram_allowed_users = "10650075"`

  The same number, `10650075`, is set in this repo as a variable whose own
  description calls it a "Telegram numeric user ID". It is also the default of
  the alert variable at `deployments/infrastructure/variables.tf:19`
  > `  default     = "10650075"`

  So the value is used as a user ID elsewhere in the tree, by a different
  subsystem, under a description written before this ticket existed. That is
  repo evidence for the reading the operator gave, not a restatement of it. The
  plan should cite it; see required fix RF3.

- **P4 — UNCERTAIN. Anchors hold; live behavior not verifiable from here.**
  All three anchors resolve and say what the plan claims.
  `deployments/infrastructure/services/grafana.hcl:29`
  > `      vault {}`

  `deployments/infrastructure/services/grafana.hcl:319`
  > `                  bottoken: '{{ with secret "${telegram_secret}" }}{{ .Data.data.bot_token }}{{ end }}'`

  `deployments/infrastructure/services/grafana.hcl:327`
  > `        change_mode = "restart"`

  The template does read the KV path and the stanza does carry
  `change_mode = "restart"`. I tried to settle the live half and could not.
  Nomad at `192.168.2.47:4646` is reachable but ACL-protected: `GET /v1/jobs`
  returned HTTP 403 and the body `Permission denied`, as did
  `GET /v1/job/grafana/allocations`. Vault at `192.168.2.47:8200` refused the
  TCP connection outright. So whether the task has already restarted on the
  swapped token is unverified from this sandbox, not refuted. The plan already
  marks P4's timing UNCERTAIN and routes it to the eval, which is the right
  disposition; I am confirming the disposition, not the outcome.

- **P5 — HOLDS.** Probe rerun verbatim: `git ls-files deployments/*/vars/`
  returns exactly four paths, two `backend-config.hcl` and two
  `prod.tfvars.example`. Both real `prod.tfvars` files exist on disk and are
  untracked. `deployments/infrastructure/vars/prod.tfvars.example:3`
  > `gcs_backup_bucket = "your-cluster-backup-bucket"`

  is the file's last line, so §7's "append at `:3`" resolves correctly, and the
  example sets three variables with `telegram_alert_chat_id` absent, exactly as
  §4 states.

- **P6 — HOLDS.** Probe rerun verbatim: `grep -rn -i "telegram" docs/*.md`
  produced no output, `exit=1`. I widened it, because the stated probe misses
  `README.md` and `docs/**/`: `git grep -ni "telegram" -- '*.md' ':!.loop/*'`
  returns nine lines, one in `TODO.md` and eight in Hermes SOUL/SKILL files.
  No file under `docs/` mentions Telegram at all. `docs/credential-rotation.md`
  is scoped to `TAILSCALE_AUTH_KEY` and `GITHUB_PAT` by its own H1 and is not a
  competing home, so §7's choice of `docs/monitoring.md` stands.

- **P7 — BREAKS as written; claim independently confirmed.** The stated probe
  is `grep -rni "getupdates|setwebhook" deployments/ cli/ scripts/`. That is a
  basic regular expression, in which `|` is a literal character, so the pattern
  searches for the eleven-character string `getupdates|setwebhook`. It exits 1
  on every repository on earth, including one that polls `getUpdates` on every
  line. The stated evidence therefore grounds nothing. I ran the corrected form,
  `grep -rniE "getupdates|setwebhook" deployments/ cli/ scripts/`: also no
  output, `exit=1`. I also ran the stronger check the plan should have used,
  `git grep -n "telegram_secret"`, which shows the only consumer of the alert
  path is `deployments/infrastructure/services/grafana.hcl:319`, a Grafana
  contact point's outbound `bottoken`. Grafana contact points send and never
  poll. The claim is true; the citation attached to it is void. See RF2.

- **P8 — HOLDS, demonstrated.** Both halves are code-form, so I ran them rather
  than reading them.

  Half one, a variable `description` is not persisted in state. Scratch root
  with the real declaration copied verbatim, `terraform apply` against no
  provider, then the state file read back:

      "outputs": {"chat": {"value": "10650075","type": "string"}},
      "resources": [],

  `grep -c "reuses Hermes" terraform.tfstate` returned `0`, exit 1. The
  description string is nowhere in state.

  Half two, `###` comments inside the `templatefile` argument map stay out of
  the rendered jobspec. Scratch root with two `###` lines placed exactly where
  §7 puts them, above `telegram_secret` in the map. `terraform console` output:

      <<EOT
      job "x" { token = "secret/data/default/grafana/telegram" chat = "10650075" }
      EOT

  and `terraform plan` agreed. Neither comment line reaches the rendered
  string, so `nomad_job.jobspec` does not move. This is the distinction
  `.claude/rules/terraform-file-layout.md:71` draws
  > `- **Jobspec files.** \`templatefile("services/x.hcl", ...)\` folds that whole`

  and the plan lands on the safe side of it. The root also parsed, validated
  and planned with the comments in place, so the placement is legal HCL.

  Scratch created at `.loop/scratch/G3-alerts-standalone-telegram-bot.plan-validator/`.

### Premises the plan left implicit

- **P9 (added) — BREAKS.** R7 assumes `TODO.md:1` is completed by this ticket.
  `TODO.md:1`
  > `- Use telegram channel for alerts & split from the hermes bot`

  The item has two halves joined by `&`. This ticket does the second, the split
  from the Hermes bot. It explicitly declines the first: §5 says "**No change to
  the chat id value.** ... `10650075` is their personal Telegram user ID", and
  Q1 resolves that the id is a personal user ID rather than a channel. Alerts
  after this ticket land in a private chat, not a Telegram channel. The plan
  cannot both draw a sharp channel-versus-user-ID line in Q1 and then strike a
  TODO that asks for a channel on the grounds that the line is finished.
  Deleting it discards live operator intent with no record. This is the one
  finding that changes what the implementer writes.

- **P10 (added) — UNCERTAIN.** The plan assumes the carried-over chat id is
  sufficient for delivery from a different bot. §5 states it as
  "A private chat's id equals the user id whichever bot sends, so the existing
  value carries over." The id equality is right. Sufficiency is a separate
  claim: a Telegram private chat exists per bot, and a bot cannot post into one
  the user has never opened. I tried to ground the exact rule and could not.
  I fetched `core.telegram.org/bots/api`, `/bots/features`, `/bots/faq` and
  `/bots`, and none of the four states "a bot cannot initiate a conversation".
  The closest grounded line, from `/bots/features`, is
  > "Users will see a Start button the first time they open a chat with your bot."

  which establishes a per-bot user-side start action without settling the send
  behavior. So: UNCERTAIN, not BREAKS. It matters anyway, because it is the
  only plausible mechanism by which the arrangement the doc describes could be
  inert while every line of the diff is correct. §8 already routes the outcome
  to the eval ("whether a firing alert actually lands in OrangeClusterAlertBot
  ... belongs in the eval marker"), so the ticket is not blind to it; the doc is
  merely silent about the cause. See RF4.

- **P11 (added) — UNVERIFIED, and absent from the Premises section.** The whole
  ticket rests on: the Vault value at `default/grafana/telegram` already holds
  the OrangeClusterAlertBot token. If that is false, this diff ships a written
  record of an arrangement that does not exist, which is the exact failure §9
  names as its second failure mode. That assumption appears in §5 as a non-goal
  ("The token at `default/grafana/telegram` is operator-managed and already
  correct") and in §3, which is outside the bound set. It appears in no `P` and
  in no front-matter `premise` entry, while the two smaller operator claims,
  Q1 and Q2, both do. I cannot verify it: Vault at `192.168.2.47:8200` refused
  the connection, and `git grep -n "grafana/telegram"` shows the only tracked
  reference is `deployments/infrastructure/services.tf:523`, a path reference
  carrying no value. Nothing in the repo records the swap, by design. That is
  fine; leaving it out of Premises is not. See RF1.

## Most dangerous assumption

**P11: that the Vault value at `default/grafana/telegram` is already the
OrangeClusterAlertBot token.** Every other premise is downstream of it. P1
through P8 could all hold and the ticket would still ship a doc describing a
cutover that never happened, and §7's own table has no file that would show the
error. It is unverifiable from the repo and from this sandbox, it rests on a
single operator statement, and it is the one load-bearing claim the Premises
section does not carry. Promoting it to a premise costs one paragraph and makes
the ticket's real dependency legible to the implementer and the eval.

## Required fixes

- **RF1 (premises, front-matter).** Add a premise stating that the Vault value
  at `default/grafana/telegram` already holds the OrangeClusterAlertBot token,
  sourced to the operator statement of 2026-09-06 and marked unverifiable from
  the repo. Add the matching entry to the front-matter `premise` map beside Q1
  and Q2. Anchor: `deployments/infrastructure/services.tf:523`
  > `      telegram_secret            = "${var.secret_mount}/data/default/grafana/telegram"`

  which names the path and carries no value, so nothing in the tree can confirm
  or refute it.

- **RF2 (premises).** Repair P7's probe. As written,
  `grep -rni "getupdates|setwebhook"` is a BRE with a literal `|` and matches
  nothing anywhere. Replace it with the `-E` form, or better with the check that
  actually supports the claim: `git grep -n "telegram_secret"`, whose only
  alert-side hit is `deployments/infrastructure/services/grafana.hcl:319`
  > `                  bottoken: '{{ with secret "${telegram_secret}" }}{{ .Data.data.bot_token }}{{ end }}'`

  a send-only contact point. The conclusion is unchanged; the evidence has to be
  evidence.

- **RF3 (§6, §7).** Resolve the TODO half this ticket does not do. R7 currently
  reads "`TODO.md:1` is removed, since this ticket completes it". Either narrow
  the edit so the line keeps its unfinished half (the channel), or record the
  operator's confirmation that "channel" was loose speech for "a separate
  Telegram destination" and the item is done. Do not delete a line that asks for
  a channel while §5 declines to create one. Anchor: `TODO.md:1`
  > `- Use telegram channel for alerts & split from the hermes bot`

- **RF4 (§6, §7).** R6 already splits outbound from inbound honestly. Extend it
  by one clause: the doc must record that the operator has to open a chat with
  the alert bot for delivery to work, because that is the precondition a future
  bot swap will trip over and the repo has no other place that would say so.
  This is the class of fact `.claude/rules/minimal-comments.md:10` calls worth
  writing:
  > `something absent from the source: a reason, a constraint imposed from outside`

  Mark it as unproven if the plan prefers; the point is that it is named.

## Contract hygiene (checked, and clean apart from the above)

- **Code surface anchors resolve and support.** All five §7 rows check out.
  `deployments/infrastructure/variables.tf:17`
  > `  description = "Telegram chat ID that receives Grafana alerts (reuses Hermes bot token from Vault)."`

  is the stale parenthetical R1 targets, and `git grep -ni "hermes bot token"`
  returns that line and nothing else, so §4's "only place in the repo" is exact.
  `docs/monitoring.md:67`
  > `### Why they are not behind the edge proxy`

  confirms "after `:66`" lands between "If Vault is down" (`:54`) and that
  heading. `deployments/applications/vars/prod.tfvars.example:6`
  > `telegram_allowed_users = "0000000000"`

  confirms the placeholder style R2 tells the implementer to match.

- **Gates discovered, not assumed.** `.loop/config.json:3`
  > `    "just pre_commit"`

  and `justfile:19`
  > `    pre-commit run --all-files`

  and `.pre-commit-config.yaml:24`
  > `        entry: terraform fmt -check -recursive`

  match §8 exactly. I ran the terraform half of gate 1 in this sandbox:
  `terraform fmt -check -recursive .` exits 0, and `bash scripts/tf_validate.sh`
  exits 0 across all three roots (one pre-existing deprecation warning on
  `data.vault_kv_secret_v2.bifrost_admin`, not an error). So the gate is green
  before the change and runs offline, which is what §8 claims. §8's split of
  gate 2 (`terraform plan`) to the operator is correct: Vault is unreachable
  from here.

- **§8's no-test claim survives `.claude/rules/python-testing.md`.** The rule's
  own scope line, `.claude/rules/python-testing.md:3`
  > `description: How to write, run, and locate tests in Python projects (pytest + uv). Read before adding or changing Python code.`

  and its constraint at `:7`
  > `Every code change ships with a test. You cannot claim code works or a`

  The diff adds no Python and no executable path: a variable `description`
  (demonstrated above to be absent from state), HCL comments (demonstrated above
  to be absent from the rendered jobspec), one example-file line, prose, and a
  TODO deletion. The rule binds Python code changes and this is not one. §8's
  reasoning is correct as written and its "no test file in section 7 to hold
  one" is consistent rather than evasive.

- **Non-goals explicit.** §5 states six, each naming the thing not done.

- **Requirements reachable by a measurement.** Every requirement has a producer
  in §7: R1 to `variables.tf`, R2 to `prod.tfvars.example`, R3 to both `.tf`
  rows, R4 to `services.tf`, R5 and R6 to `docs/monitoring.md`, R7 to `TODO.md`.
  R5's quantities are mechanical and I checked their baseline:
  `grep -o '—' docs/monitoring.md | wc -l` returns `0` today, so the em-dash
  target is measurable against a clean file, and prose in that file already
  wraps at 80 (the 31 over-length lines are all table rows and code blocks).
  In the reverse direction, no §7 file is unreached by a requirement. No
  `unmeasurable-requirement` gap.

- **Forks surfaced.** Q3 and Q4 are open and each carries a recommendation.
  R3's file-layout claim is correct: `.claude/rules/terraform-file-layout.md:20`
  > `| \`variables.tf\` | input variables |`

  and `:21`
  > `| \`services.tf\` | Nomad jobs, host volumes, and the firewall rules that open their ports |`

## Observations (advisory, no fix required)

- **A `###` comment above `services.tf:523` will force a re-alignment.** I
  demonstrated it on a scratch copy: `terraform fmt -check` exits 3 when the
  comment is inserted without re-aligning, and `terraform fmt` then shifts
  `telegram_secret` and `telegram_alert_chat_id` left to their own alignment
  group. It is whitespace only and moves no state, and §9 already names a
  `terraform fmt` failure as the worst Terraform outcome, so the plan is not
  wrong. The implementer should simply expect two extra changed lines.
- **`terraform fmt` does not reach `.tfvars.example`.** It formats `.tf` and
  `.tfvars`, so R2's new line is aligned by hand and only `end-of-file-fixer`
  guards that file. §8's "Covers ... R2" still holds through that hook.
- **Q4's anchor is off by a few lines.** It cites
  `deployments/infrastructure/variables.tf:33` for `acme_email`; the block spans
  `:28` to `:32` and the default is on `:31`, while `:33` is blank. Section 11
  sits outside `bound_paths` by design, so this is not a required fix, but the
  operator may want it corrected while editing nearby.
- **`.claude/rules/slop-scan-for-docs.md` points at
  `.claude/rules/markdown-formatting.md`, which does not exist** in
  `.claude/rules/`. Pre-existing and outside this plan; R5 states the 80-column
  rule itself, so nothing in the plan depends on the missing file.

## Scratch

Scratch created at `.loop/scratch/G3-alerts-standalone-telegram-bot.plan-validator/`.
The terraform roots and fetched HTML were removed at end of pass. The findings
ledger is retained deliberately, per `skills/reviewer-brief`, so the next cycle
can read it.

WARN — scratch artifact left at
`.loop/scratch/G3-alerts-standalone-telegram-bot.plan-validator/findings.json`
(the mandated ledger, retained on purpose).
