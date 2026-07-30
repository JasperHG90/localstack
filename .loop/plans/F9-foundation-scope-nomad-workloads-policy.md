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
- So minio, memex, hermes, grafana, postgres, prometheus, loki, nats, the
  backup jobs, and any future workload can read AND overwrite both
  credentials. The Tailscale key is the sharper edge: it admits a new device
  to the tailnet.
- The comment says "for rotation jobs", so the grant was written for a
  specific consumer and applied to the default role that everything inherits.
  **Which jobs actually read `bootstrap/*` is not yet established** — that is
  subticket 1, and it decides the shape of the fix.
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
4. Decide and record whether `list` on `secret/metadata/*` (cluster-wide)
   narrows to the job's own namespace. It leaks path names, not values —
   lower severity than the write grant, and it may have a consumer.
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
2. **Ordinary jobs still read their own secrets.** For at least three live
   jobs across different nodes (e.g. memex, grafana, minio), confirm the
   alloc is healthy and its rendered template is non-empty after the policy
   is applied. A blocked template is the signature of an over-narrowed
   policy.
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
