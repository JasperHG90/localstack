---
epic = "foundation"
depends_on = ["A1-audit-plan-premise-sweep"]
priority = 48
summary = "The shared nomad-workloads Vault policy grants every workload read/create/update on bootstrap/data/* (the GitHub PAT and Tailscale auth key) plus list on every secret path. Narrow it to the jobs that actually need it."
tags = ["vault", "nomad", "policy", "security"]
---

# F9 — Stop granting every Nomad workload write access to the bootstrap secrets

## Title
The shared `nomad-workloads` Vault policy grants every workload on the
cluster read/create/update on `bootstrap/data/*` — the GitHub PAT and the
Tailscale auth key — plus `list` on every secret path in every namespace.
Narrow it to the jobs that need it.

## Size / Effort
**Medium.** The policy edit is three lines. The effort is establishing which
jobs actually use `bootstrap/*` before removing the grant from everything
else, and applying it without breaking auth for running workloads.

## Triggered by
Surfaced by the adversarial review of F1 on 2026-07-25 and verified live the
same day. F1 was about to document this policy as job-scoped, which it is
not. Fixing the policy is out of F1's scope (F1 documents, additively), so it
gets its own ticket.

## Context (today's state)
Verified live 2026-07-25 (`vault policy read nomad-workloads`,
`vault list bootstrap/metadata`).

- The shared policy is
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`, **24
  lines**, and it is what `jwt-nomad`'s `default_role` attaches. Every job
  using a bare `vault {}` holds it. Live, that is **fifteen of the nineteen
  running jobs**: `acme` is the one job with a dedicated role (`Role: acme`),
  and `nats`, `node-exporter` and `promtail` declare no `vault` block at all
  and hold nothing.
  *(Corrected 2026-07-30 by A1's plan review. This previously read "every job
  except haproxy", which is inverted: `haproxy.hcl:39` IS a bare `vault {}`
  and live `nomad job inspect haproxy` reports `Role: ""`. Consequence for
  this ticket: haproxy renders the edge TLS PEM from Vault, so it must be IN
  the verification population, not exempt from it. Eval 2's population of
  memex, grafana, minio omits it. Note also that two holders, `talat-consumer`
  and `talat-shim`, have NO job file in this repo, so a repo-side grep will
  miss them.)*
- Its grants:
  - `:1-7` `read` on `secret/data/{{ns}}/{{job_id}}/*` and the bare path.
    This is the intended, job-scoped part.
  - `:9-15` `list` on `secret/metadata/{{ns}}/*` **and on
    `secret/metadata/*`** — cluster-wide secret-path enumeration.
  - `:17-24` **`read`, `create`, `update` on `bootstrap/data/*`** and `list`
    on `bootstrap/metadata/*`, commented "Bootstrap secrets (for rotation
    jobs)".
- `vault list bootstrap/metadata` returns `github` and `tailscale` — the
  GitHub PAT and the Tailscale auth key
  (`docs/credential-rotation.md:20,29`).
- **So sixteen of the nineteen running jobs can read AND overwrite both
  credentials**, plus any future workload: the fifteen default-role holders
  below, plus `acme`, whose dedicated role also carries `nomad-workloads` in
  its `token_policies` (`acme.tf:87`). Fifteen is the right number for the
  *verification population* (the jobs whose reads could break), but sixteen is
  the right number for the *exposure*. The full list, from
  `nomad job inspect` over all nineteen live jobs on 2026-07-30:
  `backup-minio`, `backup-postgres`, `bifrost`, `grafana`, `haproxy`,
  `hermes`, `loki`, `memex`, `minio`, `mlflow`, `phoenix`, `postgres`,
  `prometheus`, `talat-consumer`, `talat-shim`. Note `nats` is NOT among them
  (no `vault` block), and `talat-consumer`/`talat-shim` have no job file in
  this repo, so a repo-side grep misses two live holders. The Tailscale key is
  the sharper edge: it admits a new device to the tailnet.
  *(Corrected 2026-07-30: this list previously named nats, which holds
  nothing, and omitted six jobs that do.)*
- The comment says "for rotation jobs", so the grant was written for a
  specific consumer and applied to the default role that everything inherits.
  **No workload consumes it. Established 2026-07-30, three ways:** an inspect
  of all nineteen live jobs shows zero references to the `bootstrap` mount; a
  repo-wide grep shows zero; and `docs/credential-rotation.md:34-40` is a
  section titled "Why Ansible (Not Nomad Periodic Jobs)" stating both
  credentials are rotated from the host by design. Subticket 1 confirms rather
  than searches, and the fix is deletion, not a dedicated role.
  *(This bullet previously read "Which jobs actually read `bootstrap/*` is not
  yet established". The F9 plan review gathered the evidence; folding it in
  here is that review's recommended fix.)*
- The mechanism for a narrower grant already exists and is proven: the acme
  job's `acme.tf:41-90` creates a dedicated `vault_policy` +
  `vault_jwt_auth_backend_role` on the same `jwt-nomad` mount, selected with
  `vault { role = ... }` (`services/acme.hcl:73-75`).
- **One token per task.** A Nomad task performs a single JWT login and holds
  a single token, so naming a dedicated role REPLACES `nomad-workloads`
  rather than adding to it. That is why `acme.tf:87` sets `token_policies` to
  BOTH `nomad-workloads` and the dedicated policy. Any job moved onto its own
  role must be granted its KV reads there too, or it breaks.

## Non-goals / out of scope
- Rotating the exposed credentials. Worth doing, but it is a separate
  operational task and this ticket should not conflate "narrow the policy"
  with "assume compromise".
- Documenting the trust chain. That is F1.
- Changing the `vault.io` audience, the JWKS/OIDC configuration, or the
  `jwt-nomad` mount itself.
- Migrating the shared policy's ownership out of Ansible.
- Touching any job that does not need a change.

## Requirements & restrictions
1. After this ticket, a workload holding only `nomad-workloads` cannot read
   or write `bootstrap/data/*`.
2. Any job that genuinely needs `bootstrap/*` gets it through a dedicated
   `vault_jwt_auth_backend_role` + `vault_policy` selected with
   `vault { role = ... }`, mirroring `acme.tf:41-90`. That role's
   `token_policies` must ALSO carry `nomad-workloads` (or re-grant the job's
   KV paths), or the job loses its own secret reads — see Context.
3. **Establish the consumer list before removing anything.** Removing a
   grant something silently depends on is the failure mode here, and it
   surfaces as a template that blocks forever rather than a clear error.
4. **DECIDED 2026-07-30: the unscoped `secret/metadata/*` list is REMOVED.**
   The namespace-scoped `secret/metadata/{{ns}}/*` list on the line above it
   survives, so a workload can still enumerate its own namespace; only
   cluster-wide enumeration goes. It leaked path names, not values, so it is
   lower severity than the write grant, but it had no consumer: workload
   templates `read` specific data paths and do not `list` metadata at all.
   Decided rather than deferred because the plan required a recorded answer
   and either outcome was acceptable; this is the narrower one.
5. The shared policy is Ansible-owned
   (`bootstrap/roles/nomad_server/tasks/main.yml`, the task that writes it).
   Applying a change means re-running that bootstrap task against the live
   Vault; that is a manual runbook step the loop gate does not exercise.
   Call it out in the risk section and the runbook.
6. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
7. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:17-24`
  — remove or narrow the `bootstrap/*` grants.
- Same file `:9-15` — narrow the cluster-wide
  `secret/metadata/*` list, per requirement 4.
- `deployments/infrastructure/<consumer>.tf` **(new, only if subticket 1
  finds a real consumer)** — the dedicated policy and JWT role for it,
  pattern `acme.tf:41-90`.
- The consuming jobspec under `deployments/infrastructure/services/` — add
  `vault { role = ... }`, pattern `services/acme.hcl:73-75`.
- `docs/credential-rotation.md` — update if it documents the current grant
  as the mechanism rotation jobs rely on.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` (`justfile:18-19`) -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`,
  added `3c12c7a`), or `terraform-validate` fails on the gitignored
  `.ssh/id_rsa`.

### Evals (live) — encoded in `.loop/evals/<slug>.md`
1. **The grant is gone.** Mint a WI token for an ordinary job (or use the
   F1 probe job), then `vault kv get -mount=bootstrap github` -> **403**.
   Before this ticket the same command succeeds; that contrast is the point.
2. **Every default-role holder still reads its own secrets.** All fifteen,
   not a sample: `backup-minio`, `backup-postgres`, `bifrost`, `grafana`,
   **`haproxy`**, `hermes`, `loki`, `memex`, `minio`, `mlflow`, `phoenix`,
   `postgres`, `prometheus`, `talat-consumer`, `talat-shim`. Confirm each
   alloc is healthy and its template rendered. A blocked template is the
   signature of an over-narrowed policy.
   **haproxy is the one that matters most.** It reads
   `secret/data/default/haproxy/tls` (`services.tf:323`) to render the edge
   PEM, and that read stays covered by the surviving job-scoped grant. So a
   blocked haproxy template after this change means the policy was
   over-narrowed and must trigger the rollback in the runbook — and until it
   does, every routed service is down.
3. **The named consumer still works**, if subticket 1 found one: its job
   reaches `running` and reads `bootstrap/*` through its dedicated role.
4. **Metadata list narrowed**, per requirement 4: a WI token's
   `vault list secret/metadata` either fails or returns only its own
   namespace, matching whatever the ticket decided.
5. **No workload regressed:** `nomad job status` across all jobs shows no
   allocation stuck `pending` on template rendering, checked at least 10
   minutes after applying (a blocked Vault template does not fail fast).

## Risk assessment
- **Blast radius: every workload's Vault token.** This policy is attached to
  the default role that nearly every job uses. Over-narrow it and templates
  block cluster-wide — and they block, they do not error, so the symptom is
  allocations sitting `pending` rather than a clear failure.
- **The change applies via an Ansible re-run against live Vault**, not
  Terraform, so it is not covered by `terraform plan` review and cannot be
  previewed the same way.
- **Reversibility: high but manual.** Restore the previous policy content and
  re-run the bootstrap task. Keep the prior policy text to hand during the
  change.
- **Do not batch this with other bootstrap changes.** If something breaks,
  the cause should be unambiguous.
- **F1 collision, recorded rather than silently resolved.** F1
  (`F1-foundation-nomad-wi-jwt-trust`, stage `ready`) documents this policy as
  it currently stands and says "Do not narrow it either"
  (`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:169`, and its requirement 1,
  whose line number the relay insertion shifted — re-read the file rather than
  trusting a cite). F9
  falsifies that. No `depends_on` edge was added, because the two tickets do
  not need ordering — they conflict on *content*, not sequence, and adding an
  edge would imply F1 must run first when the opposite is true. Instead the
  finding is relayed onto F1 so whoever picks it up re-plans against the
  narrowed policy. If F1 lands first it is merely stale; if F9 lands first F1
  is wrong, which is why the relay exists.

## Runbook: applying this change

The loop commits the template. **It does not apply it.**

**The Ansible task cannot be run in isolation.** `nomad_server` has zero
`tags:`, so `--tags` cannot select it, and the two policy tasks
(`tasks/main.yml:257-271`) depend on facts set earlier in the same role
(`vault_bootstrap_token` at `:194-196`, `auth_method_accessor` at `:253-255`),
so `--start-at-task` fails too. The only Ansible path is the whole
`playbooks/configure_hashistack_server.yml`, which also runs the
`consul_server` and `vault_server` roles — which is exactly the batching this
ticket says to avoid.

**So apply it directly instead**, and **do NOT try to render the Jinja
template by hand.**

*Corrected 2026-07-30 after both review passes caught the same defect.* This
step previously said "the template's only variable is `auth_method_accessor`".
That is true of Jinja *variables* and false of the *file*: every surviving
path line is double-escaped, `{{ '{{' }}...{{ '}}' }}`, so that Jinja emits
Vault's own ACL templating. Substituting only the accessor leaves those
literals in place, and Vault then accepts a policy whose templated paths match
nothing. All fifteen holders silently lose their own KV read, haproxy
included, which drops every routed service.

The manager already has the correctly rendered file. The Ansible task wrote it
there (`tasks/main.yml:257-263`), unescaped and with the accessor substituted,
before feeding it to `vault policy write`. Edit that file; never re-render.

On the manager (192.168.2.30), as root:

1. **Set up an admin session and capture rollback.** The `VAULT_TOKEN` is
   required: without it `vault policy read` fails and the redirect leaves an
   EMPTY backup, so the rollback in this runbook would wipe the policy rather
   than restore it.
   ```
   export VAULT_ADDR=http://127.0.0.1:8200
   export VAULT_TOKEN=$(jq -r '.root_token' /opt/vault/init.json)
   vault policy read nomad-workloads > /root/nomad-workloads.bak.hcl
   test -s /root/nomad-workloads.bak.hcl || { echo "EMPTY BACKUP - STOP"; exit 1; }
   cp /opt/nomad/policies/vault_nomad_workloads.hcl /root/vault_nomad_workloads.hcl.bak
   ```
2. **Edit the already-rendered file in place and write it.** Delete exactly
   three `path` blocks from
   `/opt/nomad/policies/vault_nomad_workloads.hcl` — the unscoped
   `secret/metadata` list, and the two `bootstrap` blocks — **and the
   `# Bootstrap secrets (for rotation jobs)` comment line above them**, which
   is otherwise left behind advertising a grant that no longer exists. Leave
   the two job-scoped `secret/data` reads and the namespace-scoped
   `secret/metadata` list untouched, and do not touch the
   `identity.entity.aliases` text inside the surviving blocks.
   ```
   vault policy write nomad-workloads /opt/nomad/policies/vault_nomad_workloads.hcl
   P=$(vault policy read nomad-workloads)
   echo "$P" | grep -c '^path'                    # expect: 3
   echo "$P" | grep -c 'path "bootstrap'          # expect: 0
   echo "$P" | grep -ci 'bootstrap'               # expect: 0 (catches the comment)
   echo "$P" | grep -c 'secret/metadata/{{'       # expect: 1 (the SCOPED list survives)
   ```
   The third assertion is case-insensitive on purpose: a case-sensitive grep
   for `bootstrap` returns 0 against a surviving `# Bootstrap secrets` comment
   and would pass a policy that still advertises the deleted grant. The fourth
   distinguishes deleting the unscoped `secret/metadata` block from deleting
   the scoped one by mistake; eval row 9 would also catch that at step 3, but
   later and less clearly.
   **These assertions are for this one-shot apply.** After a future full
   bootstrap run the committed template's own comment contains the word
   "bootstrap" (`vault_nomad_workloads.hcl.j2:14`), so `grep -ci` legitimately
   returns non-zero then. Only `grep -c 'path "bootstrap'` stays valid
   long-term.
   **No restart, no job disruption:** tokens carry policy *names* and the body
   is resolved per request, so the change takes effect on the next Vault call
   from every existing token.
3. **Verify against the eval marker, in order:** the 403 deny checks with a
   NON-root token, then all fifteen holders healthy, then the edge still
   serving TLS, then **re-check at T+10 minutes** — a blocked Vault template
   retries silently rather than failing, so an immediate pass proves little.
4. **The superseded note on `docs/notes/audit/plan-premise-sweep-2026-07.md`
   is already appended** by this ticket's commit, not by you. Its ground-truth
   section describes the policy as 24 lines with six `path` blocks in the
   present tense, and that goes false about the REPO FILE at merge — earlier
   than the apply, and the event this loop controls — so deferring it to
   apply-time left a window where a reader of that section opens a file
   contradicting it. The note is an appended line, never a rewrite: the
   section stays A1's dated record. After step 2, extend that line with the
   date the live cluster changed too.

The next full bootstrap run is a no-op for this policy: the committed template
renders exactly the three blocks step 2 leaves behind. If they ever disagree,
the template wins and the bootstrap run silently corrects the drift.

**Rollback**, if any template blocks: on the manager, with `VAULT_TOKEN` set
as in step 1, `vault policy write nomad-workloads /root/nomad-workloads.bak.hcl`.
Confirm the backup is non-empty first; step 1's `test -s` guard exists so this
is never in doubt. This
restores access immediately and needs no re-login and no Ansible run, because
tokens carry policy names and the body resolves per request. Re-add the removed
blocks to the committed template afterwards, or the next bootstrap run undoes
the rollback.

## Subtickets (ordered)
1. **Establish the consumer list.** Search every live job and the repo for
   reads of `bootstrap/*`; check what the "rotation jobs" comment refers to
   and whether those jobs still exist. Output: a list of jobs that genuinely
   need the grant, possibly empty.
2. Narrow or remove the grants in the template. If step 1 found consumers,
   add their dedicated role + policy first, and verify them before removing
   the shared grant.
3. Apply via the bootstrap task; run evals 1-5.
4. Update `docs/credential-rotation.md` if affected.
5. Adversarial review.

## Open questions
- **Q1 — Rotate the exposed credentials as a follow-up?** Both have been
  readable by every workload on the cluster for as long as the grant has
  existed. Nothing suggests compromise, and the workloads are all
  operator-owned. *Recommendation:* rotate the Tailscale auth key (cheap,
  and it is the credential that admits a device to the network), and treat
  the GitHub PAT on its own schedule. Out of scope here either way —
  raise as its own ticket.
- **Q2 — Does anything actually consume `bootstrap/*` today?** Subticket 1
  answers it. *Recommendation:* if the answer is "nothing", delete the
  grants outright rather than building a dedicated role for a hypothetical
  consumer.
- **Q3 — Narrow `list` on `secret/metadata/*` in the same change, or
  separately?** *Recommendation:* same change — it is the same file, the
  same apply, and the same eval run. Split only if subticket 1 shows a
  consumer that makes it contentious.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: PARTIALLY SOUND. Gate verdict: `pass-with-required-fixes`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/F9-foundation-scope-nomad-workloads-policy.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: The core survives attack. The inverted haproxy/acme claim was corrected inline by A1. Remaining: no eval marker exists at all, and there is no dependency edge to F1, which requires documenting this same policy unchanged.

A1 applied the mechanical corrections marked inline above. The remaining
required fixes are in the verdict. Author and sign an eval marker before
this ticket can be picked up.
