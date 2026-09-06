---
verdict: pass
tree: be54266169cff8f5cc7fe2959c0707472c5bec95
---

# Documentation freshness: G3-alerts-standalone-telegram-bot, cycle 1

**Verdict: pass.** Every documented surface this diff touches was updated in
the same diff, and no other doc, README, runbook or source comment in the repo
still describes alerting as riding the Hermes bot. The new section is accurate
against the Terraform and the jobspec it describes, it agrees with the rewritten
variable description, and it clears the slop scan on both the mechanical and
the judgment layers. Nothing required. Six advisories below, one of which needs
the operator.

## Scope binding: omitted deliberately

My briefing gave a tree fingerprint, a diff scope and a verdict path. It gave
no 64-hex scope digest and no `verdict_binding_inputs`. The contract says to
write the digest I was given and never one I computed for a different set, so I
omit `bound_paths`, `scope` and `citations` and let this verdict fall back to
whole-tree binding, which is stricter. The `tree:` line is the fingerprint I
was given; `.loop/stamp.json` carries the same value and
`loopctl verify --expect-tree be54266169cff8f5cc7fe2959c0707472c5bec95`
returned `ok`.

The reviewed path set, for the record:
`TODO.md`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/variables.tf`,
`deployments/infrastructure/vars/prod.tfvars.example`,
`docs/monitoring.md`.

## 1. Is any other doc left stale? No.

I searched rather than assumed. Repo-wide, excluding `.git`, `.loop`,
`.terraform`, `node_modules` and the venvs:

- `grep -rni "telegram"` over `*.md`, `*.tf`, `*.hcl`, `*.yaml`, `*.yml`,
  `*.py`, `*.json`, `*.toml`, `*.sh`. Every hit outside this diff is either
  Hermes's own wiring under `deployments/applications/`, which the ticket
  correctly leaves alone, or the Grafana jobspec itself.
- `grep -rni "alert"` over `*.md`. Outside the new section, the only hits are
  `docs/monitoring.md:159` and `:276`, and `ROADMAP.md:68` and
  `cli/src/localstack_cli/commands/breakglass_runbook.md:108`, which both name
  the unrelated `T5-tls-certificate-expiry-alert` ticket.
- `deployments/applications/services/dash/tiles.json` describes Grafana as
  `"desc": "dashboards & metrics"` and names no contact point, so the landing
  page carries no claim about where alerts land.

Before this diff, the one place in the repo that described the arrangement was
`deployments/infrastructure/variables.tf:17`, and its parenthetical
`(reuses Hermes bot token from Vault)` is exactly what the diff removes. There
is no second copy to chase.

`docs/monitoring.md:159` still says `localstack monitor` gives you
`no charts, no history, no logs, no alerting`. That stays true: the command
reads control-plane state and this ticket adds nothing to it.

## 2. Does the new section hold up against the code? Yes, on every claim.

I checked each factual claim against its source rather than against the plan.

| Doc claim | Anchor | Backing |
|---|---|---|
| Grafana sends **every** alert to one chat | `docs/monitoring.md:69` | `deployments/infrastructure/services/grafana.hcl:336`, `:342`, `:348`: the root receiver and both severity routes are all `telegram-default`, and `:311-316` declares that one contact point. |
| Provisioned from `services/grafana.hcl` | `docs/monitoring.md:70-71` | `deployments/infrastructure/services/grafana.hcl:308-328`, the `template` whose destination is `local/provisioning/alerting/contactpoints.yaml`. The bare `services/...` path matches the file's own existing style at `docs/monitoring.md:276`. |
| Token from Vault KV2 at `default/grafana/telegram` | `docs/monitoring.md:71-72` | `deployments/infrastructure/services.tf:527` resolves `telegram_secret` to `${var.secret_mount}/data/default/grafana/telegram`; `grafana.hcl:319` renders `bottoken` from it; `grafana.hcl:29` carries the `vault {}` stanza that lets it. |
| Chat id from the `telegram_alert_chat_id` variable | `docs/monitoring.md:72-73` | `deployments/infrastructure/services.tf:528` and `grafana.hcl:320`. |
| Hermes uses a different token at `default/hermes/telegram` | `docs/monitoring.md:75-76` | `deployments/applications/services.tf:241`. |
| Terraform writes neither value | `docs/monitoring.md:76-77` | `grep -rn "telegram" deployments/*/secrets.tf` exits 1 with no output. Re-run at this tree. |
| Grafana picks a swapped token up by itself | `docs/monitoring.md:78-80` | `grafana.hcl:327` is `change_mode = "restart"` on the contact-point template, so consul-template re-reads the KV2 secret and restarts the task. The doc claims no timing, which is right: the poll interval is a Nomad client setting this repo does not hold. |
| Nothing calls `getUpdates`, no webhook registered | `docs/monitoring.md:88-89` | `grep -rniE "getupdates|setwebhook"` over the tree returns exactly one hit, the doc sentence itself. |

Two claims reach outside the repo and I judged them separately.

**The BotFather claim at `docs/monitoring.md:91-94` is right, and it is the one
the plan asked me to read hardest.** R6 forbids describing the group switch as
a restriction on who may DM the bot. The section does the opposite: it says
plainly that anyone who knows the @username can open a chat, that BotFather has
no setting that stops them, and that what BotFather controls is groups. That
matches Telegram's own BotFather documentation for `/setjoingroups`, which
states that all bots must be able to process direct messages and that only the
group-add path can be restricted. The doc reports the boundary correctly and
claims no protection it does not have.

**The delivery precondition at `docs/monitoring.md:96-99` is correct and worth
its lines.** A bot cannot open a conversation, so a send into a never-opened
chat fails rather than queueing, and the failure is silent from Grafana's UI
side. Nothing else in the repo would tell an operator this. See advisory A1 for
the one imprecision in it.

## 3. Do the Terraform and the doc contradict each other? No.

`deployments/infrastructure/variables.tf:18-25` and `docs/monitoring.md:84-94`
carry the same two-part scoping story with the same enforcers: outbound is the
chat id and the repo controls it; inbound is unscoped here because nothing
reads the bot's updates. The description's closing pointer,
`See "Where alerts go" in docs/monitoring.md` at `variables.tf:24-25`, resolves
to the heading `### Where alerts go` at `docs/monitoring.md:67`. The comment at
`deployments/infrastructure/services.tf:523-526` and the example comment at
`deployments/infrastructure/vars/prod.tfvars.example:5-6` say the same thing
in fewer words and contradict neither. The old false parenthetical is gone.

`deployments/infrastructure/vars/prod.tfvars.example:7` adds the variable a
fresh checkout would otherwise never learn about, with the `"0000000000"`
placeholder the plan named. `README.md:53` still says only
`fill in GCP project, etc.`, which stays true.

## 4. Prose rules: re-run, not trusted.

I re-ran the mechanical parts myself over `docs/monitoring.md:67-99` rather
than taking the briefing's word. All clean:

- 0 em dashes, 0 ` -- ` in prose, 0 semicolon splices after stripping inline
  code, 0 tier-1 slop words, 0 British spellings, 0 smart quotes, 0 prose
  arrows, and every one of the 33 lines at or under 80 columns.
- Tier-5 sweeps also empty: spatial copula, negative parallelism, contrastive
  parallelism, throat-clearing openers, significance cluster, participial
  tails, emphasis crutches, performative honesty, the prior-art marker, and
  the three-fragment burst.

The parts a grep cannot judge:

- **Thesis-first: yes.** `docs/monitoring.md:69` states the takeaway in its
  first clause, and everything after it instances or bounds that sentence.
- **Sentence weight: carries.** I looked for a sentence to cut and did not find
  one. `This is the half the repo controls, and it is one line of the contact
  point` at `:85-86` reads at first like filler, but it is the sentence that
  makes the two-enforcer distinction land, so it stays.
- **Repetition: none.** The thesis is stated once and echoed once, at `:84`.
- Document economy scores 6/6. It ships.

## 5. Placement: the current-state half is the right home.

The briefing asked whether the second half of `docs/monitoring.md` makes this a
bad home. It does not, because the file already handles the problem. A `---`
rule at `docs/monitoring.md:351` and the paragraph at `:353-356` tell the
reader that the rest is the original build plan, that it predates the move to
`192.168.2.47` and the addition of Loki, and that its addresses and file lists
are history rather than current state. The new section sits at `:67`, well
above that line, beside the other operator-facing Grafana subsections
(*Signing in*, *If Vault is down*). That is where a reader looking for
"who gets paged" would go.

The historical half names no contact point and no Telegram anything: its
Grafana entry at `:480-491` lists only the admin password, the datasource and
the health check. So it did not go stale from this change, and no edit is owed
there. Lifting that half into its own file is real work with real value, but it
is a separate ticket and this diff is not blocked on it.

## Advisories (none required)

**A1. The quoted Grafana log line is synthesized, not literal.**
`docs/monitoring.md:98` backticks `403 bot can't initiate conversation with a
user`. Telegram returns error code 403 with the description
`Forbidden: bot can't initiate conversation with a user`, so the backticked
string joins the code to the description and drops `Forbidden: `. Backticks
present it as a literal, and an operator grepping Grafana's logs for it
verbatim may miss. Quoting only `bot can't initiate conversation with a user`
would match either way. Severity: low. Not verifiable from this repo, and the
plan already carries the whole item as premise P10 (UNCERTAIN).

**A2. The BotFather group setting is recorded undated, and only the operator
can decide what to do about that.** `docs/monitoring.md:93` states
`group joins are off` in the bare present tense. That rests on the operator's
statement of 2026-09-06 (plan Q2). The setting lives in BotFather, has no API,
and nothing in this repo can notice it being flipped, so the sentence can go
false silently and a reader would have no way to tell. An `as of 2026-09-06`
or a one-clause "check it in BotFather" would make the sentence self-dating.
Plan Q2 deliberately chose to record the setting as done rather than pending,
so overriding that is the operator's call, not mine and not the doc-writer's.
Severity: low. **This is the one item that needs the operator.**

**A3. Three bold paragraphs follow a sentence that promises two.**
`docs/monitoring.md:82` says `Two separate things scope this bot`. Then come
three bold paragraphs: outbound at `:84`, inbound at `:88`, and the delivery
precondition at `:96`. The third is not a scoping thing, but it reads as the
third member of the list. A lead-in sentence before `:96`, or a plain
sub-break, would separate them. Severity: low, cosmetic.

**A4. The insertion widens a pronoun gap it did not create.**
`docs/monitoring.md:101-103` opens `Why they are not behind the edge proxy` and
`Narrowing the firewall alone would not have made these services private`.
Both point back to Prometheus, Loki and Tempo at `:5-10`. That gap already
spanned two Grafana subsections; this adds a third, and the section now
directly above talks about bots, so `they` briefly reads as the bots.
`:104-108` disambiguates within two lines. Naming the three services in the
heading would close it for good. Severity: low, and it is pre-existing in kind.

**A5. Pre-existing, out of scope: `docs/gcs-backups.md` mis-states the
variables file.** `docs/gcs-backups.md:79-83` heads a section
`deployments/infrastructure/variables.tf` and says `Two variables`. That file
holds 11. `docs/gcs-backups.md:85-90` then shows a `prod.tfvars` with two
lines; the tracked example held three before this diff and holds four after.
Read in context the section documents the backup feature's own configuration
rather than an inventory, but the file-path heading reads as an inventory. The
staleness predates this ticket and this diff neither created it nor is scoped
to fix it. Under `.claude/rules/pre-existing-issues.md` it belongs to whoever
picks it up next; I am read-only and am recording it here so it is not lost.
Severity: low.

**A6. The doc states a live arrangement the repo cannot confirm.**
`docs/monitoring.md:69` says Grafana sends every alert to the operator's chat
with OrangeClusterAlertBot. Which bot's token actually sits at
`default/grafana/telegram` is unverifiable from here by construction: no
Terraform resource writes it (plan P2, re-probed above), so the claim rests on
the operator's statement of 2026-09-06 (plan P9). The eval marker carries rows
3 and 6 as `pending-operator` for the same reason. The section is honest about
the mechanism, and it names at `:96-99` the one condition under which every
line of the diff is right and alerts still do not arrive. Nothing to fix in
the prose. Recording it so the eval rows are not mistaken for slack.

## Ledger

Ten findings appended to
`.loop/scratch/G3-alerts-standalone-telegram-bot.documentation/findings.json`
as cycle 1. No prior ledger existed at that path, so there were no settled
findings to re-attack and no absence claims are owed. Four are
`confirmed-clean` (no stale doc elsewhere; code agreement; Terraform-to-doc
agreement; slop scan; placement), six are advisory.
