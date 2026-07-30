---
epic = "spike"
depends_on = ["S2-spike-postgres-vault-creds", "A1-audit-plan-premise-sweep"]
priority = 15
summary = "Time-boxed spike: decide whether HashiCorp Boundary earns its deploy-and-maintain cost as the session broker for programmatic and SSH access in this lab. The one artifact is a keep/drop decision document backed by evidence; no product code ships."
tags = ["spike", "boundary", "docs"]
---

# S1: Spike — evaluate HashiCorp Boundary for the localstack home lab

## 1. Title

Time-boxed spike: decide whether to adopt HashiCorp Boundary as the
session broker for programmatic and SSH access in the localstack home
lab, and record a keep/drop decision with evidence.

## 2. Size / Effort

**S (research spike).** Effort is reading and writing, not building. The
size driver is the breadth of the deploy footprint that must be
understood before a cost/benefit call can be made: Boundary spans both
the Ansible bootstrap layer and the Terraform deployment layer, mirroring
the existing HashiCorp tools. No product code ships from this ticket. The
one artifact is a written decision document.

## 3. Triggered by

Auth epic, stage S1. With Vault confirmed as the OIDC provider for humans
and HAProxy as the browser front door, the open question is whether
Boundary adds enough value at the wire/SSH layer to justify its
deploy-and-maintain cost for a solo operator. This spike answers that
question before any Boundary infrastructure is designed or built.

## 4. Context

Today the cluster has no session-brokering layer. Wire-level and SSH
access to services is direct-to-host.

- The browser front door is HAProxy on plain HTTP:80 with static
  backends and no TLS: `deployments/infrastructure/services/haproxy.hcl:48`
  (`frontend http_in` / `bind *:80`) routes host-header ACLs to static
  `backend` blocks at `haproxy.hcl:84-121` (minio, s3, vault, nomad,
  consul, phoenix, memex, prometheus, grafana, loki, mlflow, bifrost).
- Backends Boundary would target at the wire level are reachable only as
  raw host:port today, e.g. Postgres at
  `deployments/infrastructure/services/postgres.hcl:13` (static 5432 on
  firebat), the MinIO S3 API and console via
  `haproxy.hcl:87-88` (s3 192.168.2.29:9000) and `haproxy.hcl:84-85`
  (minio console 192.168.2.29:9001), and NATS at
  `deployments/infrastructure/services/nats.hcl:14` (static 4222).
- Vault is deployed by the `vault_server` Ansible role, whose task file
  `bootstrap/roles/vault_server/tasks/main.yml` is the closest existing
  model for a new controller role. It installs config, initializes,
  unseals, and wires Consul storage. The Vault listener is plain HTTP
  with TLS disabled: `bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20`
  (`tls_disable = true`).
- The `vault_server` role is invoked from
  `bootstrap/playbooks/configure_hashistack_server.yml:28-35`, alongside
  `consul_server` and `nomad_server`, all against the `manager` host
  (firebat, 192.168.2.30) defined in `bootstrap/inventory/cluster.ini:1-3`.
- On the Terraform side, the Vault provider is declared and configured at
  `deployments/infrastructure/providers.tf:7-10` and
  `providers.tf:28` (`provider "vault" {}`). There is **no**
  `hashicorp/boundary` provider declared. Confirmed by search: zero
  matches for `boundary`, `oidc`, `zitadel`, or `transit` across
  `bootstrap/` and `deployments/`.
- The only Vault engine configured in Terraform today is a single KV2
  mount: `deployments/infrastructure/secrets.tf:2-7` (`vault_mount.kvv2`).
  There is no Vault database secrets engine, no PKI, and no Transit
  engine. This matters because Boundary needs a KMS (Vault Transit can
  serve root/worker-auth/recovery keys) and its main benefit
  (brokered dynamic credentials) depends on Vault credential engines that
  do not yet exist. That dependency is the subject of ticket S2.

What is wrong/missing: there is no basis on record for deciding whether
Boundary is worth its footprint. This ticket produces that basis.

## 5. Non-goals / out of scope

- **No infrastructure ships.** No new Ansible role, no playbook edit, no
  inventory change, no Terraform resource. This is a decision, not a
  deployment.
- Not proving that Terraform *can* configure Boundary. It can
  (`boundary_scope`, `boundary_auth_method_oidc`, `boundary_target`,
  `boundary_host_catalog_*`, `boundary_credential_store_vault`,
  `boundary_credential_library_vault`, `boundary_role`). That is assumed,
  not investigated.
- Not designing the Vault credential engines themselves (that is S2).
- Not evaluating Boundary as an OIDC provider. Boundary consumes OIDC; it
  is not an IdP. Vault remains the IdP per the confirmed auth decisions.
- Not changing HAProxy, TLS, or the browser front door.
- Not solving web-UI access. Grafana, MinIO console, MLflow, and Phoenix
  UI are a poor Boundary fit and stay behind HAProxy.

## 6. Requirements & restrictions

The spike MUST deliver a written decision document that:

1. States a clear **keep or drop** recommendation for Boundary, with the
   reasoning grounded in the solo-operator cost/benefit, not in whether
   Terraform can express the config.
2. Enumerates the **deploy footprint across both layers**, anchored to
   the existing HashiCorp tooling it would mirror:
   - Bootstrap layer: a new `boundary_controller` role (and likely a
     `boundary_worker`) modeled on `bootstrap/roles/vault_server/` and
     `bootstrap/roles/nomad_server/`, wired into
     `configure_hashistack_server.yml` and `inventory/cluster.ini`.
     Needs a backing Postgres (existing PG18 on firebat, or dedicated)
     and a KMS (Vault Transit).
   - Deployment layer: a new `hashicorp/boundary` Terraform provider and
     the resource set listed in Non-goals, configured only once the
     controller runs.
3. Separates the **good fit** (Postgres, MinIO S3 API, NATS, Phoenix
   gRPC, Memex API, node SSH — wire-level and SSH access) from the
   **poor fit** (web UIs, where a localhost proxy port breaks
   host-header, TLS, cookie, and OIDC-callback behavior).
4. If the recommendation is **keep**, defines the **minimal PoC scope**
   (the smallest set of targets and roles that would prove value) and
   names the **Vault credential engines that must exist first**, tying
   that prerequisite explicitly to ticket S2.
5. If the recommendation is **drop**, states what would have to change
   for the answer to flip (the reopen conditions).

Restrictions the repo enforces (each cited):

- **Simplicity / no speculative build** (`CLAUDE.md` sections 1-2): the
  spike must resist scoping in a build. Surface tradeoffs, do not pick a
  design silently.
- **Docs economy and slop scan** (`.claude/rules/slop-scan-for-docs.md`):
  the decision doc is markdown and MUST pass the three-layer slop scan
  (no identity leaks, no hallucinated identifiers or paths, thesis-first,
  American spelling, prose wrapped at 80 chars, em-dash budget). Every
  backticked path/identifier in the doc must resolve to a real thing.
- **Never reference Zitadel.** It was dropped from the auth design. Any
  mention in the decision doc is a factual error to fix.

## 7. Code surface

This ticket writes **one new documentation file** and touches no product
code. The paths below are read-only anchors the doc must cite correctly,
plus the single file the ticket creates.

- **CREATE** `docs/notes/boundary-evaluation.md` (recommended path; see
  Open Questions Q1) — the decision document. This is the only file the
  ticket writes.
- `deployments/infrastructure/services/haproxy.hcl:48,84-121` — cite as
  the existing browser front door and the static-backend inventory of
  services in scope. Load-bearing for the "front door already covered"
  premise.
- `bootstrap/roles/vault_server/tasks/main.yml` and
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20` — cite as
  the role template a `boundary_controller` role would mirror, and as
  evidence the cluster runs plain-HTTP HashiCorp services today.
- `bootstrap/roles/nomad_server/` (role structure:
  `tasks/`, `templates/`, `handlers/`, `files/`) — second model for the
  new role's shape.
- `bootstrap/playbooks/configure_hashistack_server.yml:28-44` and
  `bootstrap/inventory/cluster.ini:1-3` — cite as the wiring points a new
  controller role would plug into.
- `deployments/infrastructure/providers.tf:7-10,28` — cite as the place a
  `hashicorp/boundary` provider would be added, and as proof none exists.
- `deployments/infrastructure/secrets.tf:2-7` — cite as the sole existing
  Vault engine (KV2), evidence that the credential engines Boundary would
  broker (S2) do not yet exist.

## 8. Tests & validation gates

This spike ships one markdown decision doc, not code, so the
`all-code-needs-tests` rule (`.claude/rules/python-testing.md`) does not
apply — no code is exercised and there is no unit-test suite to run. The
acceptance target is doc-completeness plus factual-grounding, not a
live-service assertion: nothing is deployed by this ticket to probe
against.

### Repo gate

- `just pre_commit` (runs `pre-commit run --all-files`, per root
  `justfile` `pre_commit:` recipe). The configured hooks
  (`.pre-commit-config.yaml`) are: from `pre-commit-hooks` v5.0.0 —
  check-json, check-ast, check-merge-conflict, check-yaml (`--unsafe`),
  debug-statements, detect-private-key, end-of-file-fixer; and local
  hooks nomad-fmt, terraform-fmt (`terraform fmt -check -recursive`), and
  terraform-validate (`scripts/tf_validate.sh`, which validates the three
  Terraform roots offline). `.pre-commit-config.yaml:1` excludes
  `^\.(claude|loop)/`, so the ticket file itself is not linted. The
  decision doc under `docs/` is markdown: it is in scope for
  end-of-file-fixer (single trailing newline) and detect-private-key, but
  the terraform-fmt / terraform-validate and nomad-fmt hooks are typed to
  `.tf` / `.hcl` and do not touch the doc. Because this ticket adds no
  `.tf` and no `.hcl`, those hooks stay green by not running against new
  files.
- **Markdown slop-scan** on the deliverable doc
  (`docs/notes/boundary-evaluation.md`), per
  `.claude/rules/slop-scan-for-docs.md`: run all three layers before
  declaring done. Layer 0 (identity leaks, hallucinated
  paths/identifiers, bare stubs) is categorical — every backticked
  `path:line` and every prospective Boundary provider/resource name must
  resolve or be labeled prospective. Run `Skill(scribe:slop-detector)` on
  the doc (over 100 words), confirm prose wraps at 80 chars, American
  spelling, and the 0-2 em-dash-per-1000-words budget.

### Evals (doc)

These are the acceptance target. They are the checks that the spike
actually answered its question, and they are grep-able against
`docs/notes/boundary-evaluation.md`. No live cluster calls: there is no
deployed Boundary to assert against.

1. **Deliverable exists at the agreed path.** The file
   `docs/notes/boundary-evaluation.md` exists (path per Open Questions
   Q1; operator confirms before the loop runs).
2. **Explicit verdict with evidence.** The doc states one of KEEP or DROP
   as an unambiguous verdict (grep for a `KEEP` / `DROP` verdict line),
   and the verdict is backed by solo-operator cost/benefit reasoning, not
   by "Terraform can express the config". A doc that only restates that
   Terraform can configure Boundary fails this eval.
3. **Two-layer deploy footprint enumerated.** The doc names both layers
   of the footprint: the Ansible bootstrap layer (a `boundary_controller`
   role, and likely a `boundary_worker`, modeled on
   `bootstrap/roles/vault_server/` and `bootstrap/roles/nomad_server/`,
   wired into `configure_hashistack_server.yml` and `inventory/cluster.ini`,
   with its backing Postgres and Vault-Transit KMS needs) AND the
   Terraform deployment layer (a `hashicorp/boundary` provider added at
   `deployments/infrastructure/providers.tf` and its resource set). Grep
   for both `boundary_controller` (or `boundary_worker`) and
   `hashicorp/boundary`.
4. **KEEP prerequisites tie to S2.** The doc enumerates the Vault
   credential engines a KEEP verdict would require first (e.g. a database
   secrets engine for Postgres) and confirms none exist today beyond the
   single KV2 mount (`deployments/infrastructure/secrets.tf:2-7`),
   explicitly tying that prerequisite to ticket S2. Grep for an `S2`
   reference alongside the credential-engine list.
5. **Good-fit vs poor-fit split present.** The doc separates the
   wire-level / SSH good-fit targets from the web-UI poor-fit set, and on
   a KEEP verdict also states the minimal PoC scope; on a DROP verdict it
   states the reopen conditions.

An adversarial review (`.claude/rules/adversarial-reviews.md`) closes the
loop: before reporting done, hand the doc to a review sub-agent to
confirm the verdict is evidence-backed and every anchor is accurate.

**Authoritative DoD:** the eval marker at `.loop/evals/S1-spike-boundary-evaluation.md` is the binding Definition of Done for this ticket; its five-column scenario table is what the loop-reviewer scores against.

## 9. Risk assessment

- **Blast radius:** near zero. One new markdown file under `docs/`. No
  runtime, no infrastructure, no state.
- **Reversibility:** total. Deleting the doc reverts the change.
- **Likeliest failure modes:**
  1. **Scope creep into a build** — the spike starts drafting the role or
     Terraform instead of deciding. Mitigation: Non-goals forbid any
     infra; the deliverable is a doc.
  2. **Answering the wrong question** — proving Terraform can configure
     Boundary rather than weighing deploy/maintenance cost vs benefit for
     a solo operator. Mitigation: Requirement 1 and the acceptance check.
  3. **Hallucinated anchors** — citing Boundary provider resources or
     repo paths that do not exist. Mitigation: every repo `path:line` is
     verified against the tree; Boundary provider resource names are
     labeled as prospective, not present.
  4. **Referencing Zitadel** — a stale-design error. Mitigation: explicit
     restriction in section 6.

## 10. Subtickets

Ordered, dependency-aware. All within the single spike.

1. **Frame the decision.** Restate the one question (is Boundary worth
   the footprint given Vault OIDC + HAProxy already cover the browser
   door) and the good-fit vs poor-fit boundary. Depends on: nothing.
2. **Map the two-layer footprint.** Document the `boundary_controller`
   (+ worker) Ansible role modeled on `vault_server`/`nomad_server`, its
   wiring into `configure_hashistack_server.yml` + inventory, its backing
   Postgres and Vault-Transit KMS needs; then the Terraform provider and
   resource set. Depends on: 1.
3. **Establish the S2 prerequisite.** Identify the Vault credential
   engines (database secrets engine for Postgres, etc.) Boundary would
   broker and confirm none exist today (`secrets.tf:2-7`), tying the
   prerequisite to ticket S2. Depends on: 2.
4. **Write the verdict.** Keep or drop, with reasoning. If keep, the
   minimal PoC scope + required Vault engines. If drop, the reopen
   conditions. Depends on: 1-3.
5. **Slop scan + adversarial review.** Run the doc gates and fix
   findings. Depends on: 4.

## 11. Open questions

Each fork the request/repo does not settle, with a recommendation. The
operator should settle Q1 and Q2 before the loop runs; Q3-Q5 are for the
spike itself to answer and are listed so the loop does not resolve them
silently.

- **Q1 — Where does the decision doc live?** The repo has `docs/notes/`
  (with `feat/` and `main/` subdirs) and topic docs at `docs/` root
  (e.g. `docs/haproxy_reverse_proxy.md`). *Recommendation:*
  `docs/notes/boundary-evaluation.md`, since this is an evaluation note,
  not a how-to. Operator confirm.
- **Q2 — Is S2 a hard blocker or a parallel track?** The keep path
  depends on Vault credential engines that S2 defines. *Recommendation:*
  treat S2 as a documented prerequisite for any Boundary PoC, but let S1
  proceed now — S1 produces the decision, S2 the engines. The spike
  should not wait on S2.
- **Q3 — Backing Postgres: reuse firebat PG18 or dedicate one?**
  Boundary's controller needs a Postgres. *Recommendation (for the spike
  to weigh, not the loop to pick):* reuse the existing PG18 on firebat
  (`postgres.hcl:13`) with a dedicated database to avoid a second
  Postgres to maintain; note the coupling risk (Boundary down if that PG
  is down). Surface as a tradeoff in the doc.
- **Q4 — Controller and worker on one node or split?** Solo home lab
  favors collocation on firebat (the `manager` host), mirroring
  vault/nomad/consul. Surface, do not pre-decide.
- **Q5 — Node SSH via Boundary vs Tailscale SSH?** A `tailscale` role
  already exists (`bootstrap/roles/tailscale/`). The doc should compare
  Boundary SSH brokering against the Tailscale access already in place,
  since overlap weakens the SSH-access justification. This comparison is
  part of the spike's cost/benefit, not a fork to settle up front.

## Resolved forks (operator, 2026-07-23)

- **Q1 → `docs/rfcs/boundary-evaluation.md`.** Operator chose an RFC
  location rather than `docs/notes/`. The `docs/rfcs/` directory does not
  exist yet — create it as part of this spike.
- **Q2 → Hard blocker: S2 first.** S1 waits on S2 so the Boundary
  evaluation can test the real "keep" path (Vault credential engines)
  end-to-end. **Spike order: S2 → S1.** (S3 remains independent.)
- **Q3–Q5** are for the spike itself to answer in the doc (backing
  Postgres, controller/worker collocation, Boundary-SSH vs Tailscale-SSH)
  — surfaced as tradeoffs, not settled up front.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: BROKEN. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/S1-spike-boundary-evaluation.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: Its deliverable path `docs/notes/` was deleted after authoring, the operator's own resolved fork chose `docs/rfcs/`, and the eval hardcodes the dead path into five 100%-threshold rows. The spike is unexecutable to a passing Definition of Done. It is NOT redundant, unlike dropped S3 -- fix it, do not drop it.

This ticket is **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reverse design decisions or need an
operator call. **Do not implement from this plan as written.** Work the
verdict's required-fix list, then re-dispatch `loop-plan-reviewer` before
unblocking.
