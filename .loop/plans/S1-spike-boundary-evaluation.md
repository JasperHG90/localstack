---
epic = "spike"
depends_on = ["S2-spike-postgres-vault-creds", "A1-audit-plan-premise-sweep"]
priority = 15
summary = "Time-boxed spike: decide whether HashiCorp Boundary earns its deploy-and-maintain cost as the session broker for programmatic and SSH access in this lab. The one artifact is a keep/drop decision document backed by evidence; no product code ships."
tags = ["spike", "boundary", "docs"]
---

# Ticket: S1-spike-boundary-evaluation

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

Auth epic, stage S1. Vault is the OIDC provider for humans and it is
deployed, not just decided: `deployments/infrastructure/oidc.tf:95`
declares `vault_identity_oidc_provider.lab` and F2 is `done`. HAProxy is
the browser front door and terminates TLS. The open question is whether
Boundary adds enough value at the wire/SSH layer to justify its
deploy-and-maintain cost for a solo operator. This spike answers that
question before any Boundary infrastructure is designed or built.

## 4. Context (re-anchored 2026-08-04)

Today the cluster has no session-brokering layer. Wire-level and SSH
access to services is direct-to-host.

- The browser front door is HAProxy terminating TLS on `*:443` with a
  Let's Encrypt wildcard for `*.lab.orangecluster.nl`:
  `deployments/infrastructure/services/haproxy.hcl:95-96`
  (`frontend https_in` / `bind *:443 ssl crt /secrets/haproxy.pem`). The
  certificate is rendered from Vault KV2 by the template at
  `haproxy.hcl:62-72`. Port 80 is a redirect only:
  `haproxy.hcl:91-93` is `frontend http_in` / `bind *:80` /
  `http-request redirect scheme https code 301 unless { ssl_fc }`. The
  static port allocations are `haproxy.hcl:10-17`.
- The routed set is host-header ACLs at `haproxy.hcl:98-118` into
  `backend` blocks at `haproxy.hcl:127-157`: minio, s3, vault, nomad,
  consul, phoenix, memex, grafana, mlflow, bifrost. **Prometheus and Loki
  are deliberately not routed** (`docs/haproxy_reverse_proxy.md:30`);
  `N1-netsec-restrict-prometheus-loki-to-cluster` is `done` and confined
  them to the cluster network. They are LAN-reachable, non-front-doored
  services, which is exactly the shape a session broker would be weighed
  against, so the doc must file them on that side of the line.
- Backends Boundary would target at the wire level are reachable only as
  raw host:port today, e.g. Postgres at
  `deployments/infrastructure/services/postgres.hcl:12-14` (`port "db"`,
  `static = 5432` on firebat), the MinIO S3 API and console via
  `haproxy.hcl:130-131` (s3 192.168.2.29:9000) and `haproxy.hcl:127-128`
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
  `hashicorp/boundary` provider declared, no `boundary_*` resource, and no
  Boundary Ansible role. A case-insensitive text grep returns **four** hits,
  none of them a Boundary artifact: S2's comment at
  `deployments/applications/database-secrets-poc.tf:10`, which records that S1
  brokers the credentials it kept standing, plus three uses of the English
  word — `developer_group.tf:6`, `developer_group.tf:104` and `roles.tf:9`,
  all about containment boundaries. Zero matches for `zitadel`.
- **Vault dynamic credentials are already a live, proven pattern here**,
  and that is an input to the cost/benefit rather than a missing
  prerequisite. Terraform manages, beyond the KV2 mount at
  `deployments/infrastructure/secrets.tf:2-7` (`vault_mount.kvv2`):
  a Consul secrets backend role (`consul_deploy_role.tf:19`), two Nomad
  secrets backend roles (`nomad_deploy_role.tf:36`, `nomad_oidc.tf:74`),
  a JWT auth backend role (`acme.tf:66`), and the human OIDC provider
  (`oidc.tf:95`). F5, F6 and F2 are all `done`.
- **A Vault `database` secrets engine exists and is running**, left
  standing by S2 for this spike. `docs/postgres-vault-dynamic-creds-spike.md`
  ("What this spike left running") names the kept resources: the
  `database` mount, connection `postgres-poc` against firebat as
  `vault-dbengine-admin`, and role `s2-poc`. The same document states
  the handover explicitly: "S1 inherits a working `database/creds/s2-poc`
  path from this spike rather than a description of one, so it can test
  brokering against real credentials." The declarations are in
  `deployments/applications/database-secrets-poc.tf`.
- What Vault does **not** have is a `transit/` mount or a `pki/` mount.
  Transit matters because Boundary wants a KMS for its root,
  worker-auth and recovery keys, so a KEEP verdict adds a Transit mount
  to the footprint. Confirmed by search: no `vault_mount` of either type
  in `deployments/`.

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
   names the **Vault engines the footprint still needs**, against the
   live inventory rather than a blanket "none exist". Specifically: a
   `transit/` mount for Boundary's KMS does not exist and must be added;
   the `database/` engine S2 left running (`database/creds/s2-poc`) is
   the credential library a PoC would broker, and the doc ties that back
   to ticket S2.
5. If the recommendation is **drop**, states what would have to change
   for the answer to flip (the reopen conditions).
6. Names both remaining prerequisites for a KEEP path and says which are
   already met. `boundary_auth_method_oidc` needs an OIDC issuer:
   `vault_identity_oidc_provider.lab` (`oidc.tf:95`) is deployed and F2
   is `done`, so that one is met. A Transit KMS mount is not.

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

- **CREATE** `docs/rfcs/boundary-evaluation.md` — the decision document,
  and the only file the ticket writes. The path is settled: the operator
  resolved Q1 to `docs/rfcs/` on 2026-07-23. The directory does not exist
  yet, so the ticket creates it. Every other section of this plan and
  every row of `.loop/evals/S1-spike-boundary-evaluation.md` names the
  same path.
- `deployments/infrastructure/services/haproxy.hcl:95-96,91-93,127-157` —
  cite as the existing browser front door: TLS terminated on `*:443`,
  `*:80` a 301, and the routed backend inventory. Load-bearing for the
  "front door already covered" premise. Prometheus and Loki are outside
  that set (`docs/haproxy_reverse_proxy.md:30`).
- `bootstrap/roles/vault_server/tasks/main.yml` and
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20` — cite as
  the role template a `boundary_controller` role would mirror, and as
  evidence the cluster runs plain-HTTP HashiCorp services today.
- `bootstrap/roles/nomad_server/` (role structure:
  `tasks/`, `templates/`, `handlers/`, `files/`) — second model for the
  new role's shape.
- `bootstrap/playbooks/configure_hashistack_server.yml:28-45` and
  `bootstrap/inventory/cluster.ini:1-3` — cite as the wiring points a new
  controller role would plug into.
- `deployments/infrastructure/providers.tf:7-10,28` — cite as the place a
  `hashicorp/boundary` provider would be added, and as proof none exists.
- `deployments/infrastructure/secrets.tf:2-7` — the KV2 mount. Cite it as
  one engine among several, never as the only one.
- `deployments/infrastructure/consul_deploy_role.tf:19`,
  `nomad_deploy_role.tf:36`, `acme.tf:66`, `oidc.tf:95` — cite as the
  live dynamic-credential and OIDC precedent Boundary is weighed against.
- `deployments/applications/database-secrets-poc.tf` and
  `docs/postgres-vault-dynamic-creds-spike.md` — cite as the `database`
  engine S2 left running, and the credential path
  (`database/creds/s2-poc`) a Boundary PoC would broker.

## 8. Tests & validation gates

This spike ships one markdown decision doc, not code, so the
`all-code-needs-tests` rule (`.claude/rules/python-testing.md`) does not
apply — no code is exercised and there is no unit-test suite to run. The
acceptance target is doc-completeness plus factual-grounding, not a
live-service assertion: nothing is deployed by this ticket to probe
against.

### Repo gate

- `just pre_commit` (runs `pre-commit run --all-files`, per root
  `justfile:18`). `.pre-commit-config.yaml` declares **fourteen** hooks.
  **Three** of them can touch a markdown file under `docs/`:
  **end-of-file-fixer** (`:13`, single trailing newline),
  **detect-private-key** (`:12`), and **check-merge-conflict** (`:8`), which
  is `types: [text]` and so reaches any text file — confirmed by running
  `prek run check-merge-conflict --files docs/haproxy_reverse_proxy.md`, which
  reports `Passed` rather than `Skipped`. The other eleven are typed or scoped
  away: check-json (`:6`), check-ast (`:7`), check-yaml (`:9`) and
  debug-statements (`:11`) match other file types;
  nomad-fmt (`:16`) is typed to `.hcl`; terraform-fmt (`:22`) and
  terraform-validate (`:28`) are typed to `.tf`; and ruff (`:37`),
  ruff-format (`:46`), mypy (`:52`) and pytest (`:66`) are scoped to
  `^cli/`. Since this ticket adds no `.tf`, `.hcl` or Python, those twelve
  stay green by not running against anything it writes.
  `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so this ticket
  file is not linted either.
- **Markdown slop-scan** on the deliverable doc
  (`docs/rfcs/boundary-evaluation.md`), per
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
`docs/rfcs/boundary-evaluation.md`. No live cluster calls: there is no
deployed Boundary to assert against.

1. **Deliverable exists at the agreed path.** The file
   `docs/rfcs/boundary-evaluation.md` exists (the operator settled Q1 on
   2026-07-23; the ticket creates `docs/rfcs/`).
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
4. **KEEP prerequisites named against the live inventory.** The doc says
   which Vault engines a KEEP verdict still needs (`transit/` for the KMS)
   and which it inherits (`database/`, left running by S2, brokering
   `database/creds/s2-poc`), tying the inherited half to ticket S2, and cites
   `secrets.tf` for the KV2 mount as one engine among several. That is four
   terms the marker's row greps, matching §7's requirement to cite
   `secrets.tf` and never call it the only engine. A doc that claims KV2 is
   the only engine fails this eval: it is not.
5. **Good-fit vs poor-fit split present.** The doc separates the
   wire-level / SSH good-fit targets from the web-UI poor-fit set, and on
   a KEEP verdict also states the minimal PoC scope; on a DROP verdict it
   states the reopen conditions.
6. **The verdict cites evidence this plan does not already contain.** A
   doc that copies this plan's Non-goals and Context blocks satisfies the
   grep rows without producing a finding. The verdict must rest on at
   least one thing weighed here for the first time: the Tailscale-SSH
   overlap (Q5), or the live `nomad/`/`consul/`/`database/` dynamic
   credential precedent, or the measured cost of the Transit mount.

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
3. **Inventory the Vault engines against the live state.** Name what a
   Boundary PoC would broker (`database/creds/s2-poc`, left running by
   S2) and what the footprint still adds (`transit/` for the KMS). Do not
   repeat the stale claim that KV2 is the only engine. Depends on: 2.
4. **Write the verdict.** Keep or drop, with reasoning. If keep, the
   minimal PoC scope + required Vault engines. If drop, the reopen
   conditions. Depends on: 1-3.
5. **Slop scan + adversarial review.** Run the doc gates and fix
   findings. Depends on: 4.

## 11. Open questions

Q1 and Q2 are settled; see "Resolved forks" below. They stay listed so
the record shows what was asked, not so the loop reopens them. Q3-Q5 are
for the spike itself to answer and are listed so the loop does not
resolve them silently.

- **Q1 — Where does the decision doc live?** *Settled:*
  `docs/rfcs/boundary-evaluation.md`.
- **Q2 — Is S2 a hard blocker or a parallel track?** *Settled:* hard
  blocker, and it is now satisfied — S2 is `done`.
- **Q3 — Backing Postgres: reuse firebat PG18 or dedicate one?**
  Boundary's controller needs a Postgres. *Recommendation (for the spike
  to weigh, not the loop to pick):* reuse the existing PG18 on firebat
  (`postgres.hcl:12-14`) with a dedicated database to avoid a second
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
  exist yet, so the spike creates it. This plan and the eval marker both
  name that path and only that path.
- **Q2 → Hard blocker: S2 first, and S2 is now `done`.** The edge holds
  and it delivered something concrete: S2 deliberately left the `database`
  mount, the `postgres-poc` connection and the `s2-poc` role standing for
  this spike. Its own words: "S1 inherits a working
  `database/creds/s2-poc` path from this spike rather than a description
  of one, so it can test brokering against real credentials"
  (`docs/postgres-vault-dynamic-creds-spike.md`). Keep the `depends_on`.
- **Q3–Q5** are for the spike itself to answer in the doc (backing
  Postgres, controller/worker collocation, Boundary-SSH vs Tailscale-SSH),
  surfaced as tradeoffs rather than settled up front.

## Premises / assumptions

- **P1.** The browser front door terminates TLS; it is not plain HTTP.
  `Evidence:` `deployments/infrastructure/services/haproxy.hcl:95-96`
  (`frontend https_in`, `bind *:443 ssl crt /secrets/haproxy.pem`),
  `:91-93` (port 80 is a 301 redirect), `:62-72` (the certificate is
  rendered from Vault KV2). Corroborated by `docs/tls-certificates.md`
  and `docs/haproxy_reverse_proxy.md`. Re-anchored 2026-08-04.

- **P2.** The routed set is ten services and excludes Prometheus and
  Loki, so both are LAN-exposed rather than front-doored.
  `Evidence:` ACLs at `haproxy.hcl:98-118`, backends at `:127-157`;
  `docs/haproxy_reverse_proxy.md:30` states the exclusion outright;
  `N1-netsec-restrict-prometheus-loki-to-cluster` is `done`.

- **P3.** The wire-level targets are raw host:port with no broker in
  front. `Evidence:` `deployments/infrastructure/services/postgres.hcl:12-14`
  declares `port "db"` with `static = 5432`.
  `deployments/infrastructure/services/nats.hcl:14` is `static = 4222`.
  `haproxy.hcl:130-131` routes s3 to 192.168.2.29:9000 and `:127-128`
  the minio console to 192.168.2.29:9001.

- **P4.** `vault_server` is the closest existing model for a
  `boundary_controller` Ansible role, and HashiCorp services here run
  plain HTTP behind the edge. `Evidence:`
  `bootstrap/roles/vault_server/tasks/main.yml` exists;
  `bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20` is
  `address = "0.0.0.0:8200"` / `tls_disable = true`;
  `bootstrap/roles/nomad_server/` has `files/ handlers/ tasks/
  templates/`.

- **P5.** A new controller role plugs into the existing manager wiring.
  `Evidence:` `bootstrap/playbooks/configure_hashistack_server.yml:28-35`
  is the `vault_server` play against `hosts: manager`, and `:37-45` is
  the sibling play for Nomad. The host it targets is defined in
  `bootstrap/inventory/cluster.ini:1-3` as `[manager]` / firebat
  192.168.2.30.

- **P6.** Nothing here is built yet: no `hashicorp/boundary` provider, no
  `boundary_*` resource, no Boundary Ansible role. `Evidence:`
  `deployments/infrastructure/providers.tf:1-24` lists nomad, vault,
  null and google only; `:28` is `provider "vault" {}`. A recursive
  case-insensitive grep for `boundary` over `bootstrap/` and `deployments/`
  returns four hits and every one is prose: S2's comment at
  `deployments/applications/database-secrets-poc.tf:10`, and the English word
  at `developer_group.tf:6`, `developer_group.tf:104` and `roles.tf:9`.
  `zitadel` returns nothing anywhere.

- **P7.** Vault dynamic credentials are already live here, so the
  "Boundary unlocks dynamic credentials" argument is weaker than it
  looks. `Evidence:` a `vault_consul_secret_backend_role` at
  `consul_deploy_role.tf:19`; a `vault_nomad_secret_role` at
  `nomad_deploy_role.tf:36` and another at `nomad_oidc.tf:74`; a
  `vault_jwt_auth_backend_role` at `acme.tf:66`; the
  `vault_identity_oidc_provider` at `oidc.tf:95`. F2, F5, F6 all `done`.

- **P8.** A `database` secrets engine exists and brokers real Postgres
  credentials today. `Evidence:`
  `deployments/applications/database-secrets-poc.tf` declares the mount,
  connection and role; `docs/postgres-vault-dynamic-creds-spike.md`
  ("What this spike left running") lists them as kept for S1.

- **P9.** Vault has no `transit/` and no `pki/` mount, so a KEEP verdict
  adds a Transit mount for Boundary's KMS. `Evidence:` no `vault_mount`
  of either type anywhere under `deployments/`. F3 shipped TLS through
  ACME into KV2, not through a Vault PKI engine
  (`docs/tls-certificates.md`, `haproxy.hcl:62-72`).

- **P10.** The deliverable path is `docs/rfcs/boundary-evaluation.md` and
  the directory must be created. `Evidence:` `ls docs/` has
  `architecture/` and `notes/` but no `rfcs/`; the operator's resolved
  fork above chose it.

- **P11.** No other ticket answers this spike's question, so it is not
  redundant the way S3 was. `Evidence:` re-run 2026-08-04, a
  case-insensitive grep for `boundary` matches seven plans and five docs,
  and every hit is either the English word or a pointer back at S1. The
  pointers are `.loop/plans/R1-rollout-mlflow-oauth2-proxy.md:74` ("the
  sibling plan") and
  `.loop/plans/R7-rollout-postgres-consumer-cutover.md:153`. The substantive
  one is `docs/postgres-vault-dynamic-creds-spike.md`'s "Does this need
  Boundary" section, which answers only the machine half and hands the human
  half to S1. No ticket pre-decides KEEP or DROP. Note S2's own plan has
  moved to `.loop/archive/` since the earlier probe was written.

- **P12.** The repo gate is `just pre_commit` and it does not lint this
  plan. `Evidence:` `justfile:18` defines the recipe;
  `.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`.

## Plan review history

### 2026-07-30 (A1 premise sweep) — BROKEN, `fail`

Reviewed by `loop-plan-reviewer` against the repo and the live cluster as part
of `A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed
clean. The verdict is
`.loop/verdicts/S1-spike-boundary-evaluation.plan-validator.md`.

Headline defect: the eval hardcoded `docs/notes/boundary-evaluation.md` into
five 100%-threshold rows while the operator's own resolved fork chose
`docs/rfcs/`, so the ticket could not be run to a passing Definition of Done.
The front-door and Vault-engine premises were also stale. The spike was never
redundant, unlike dropped S3.

### 2026-08-04 — required fixes applied

All eight required fixes are in. What changed, and what the repo says now:

1. **Front door re-anchored** (§4, P1-P3). HAProxy terminates TLS on `*:443`
   (`haproxy.hcl:95-96`) with the certificate rendered from Vault KV2
   (`:62-72`); `*:80` is a 301 (`:91-93`). Backends moved to `:127-157`,
   ACLs to `:99-118`, minio console to `:127-128`, s3 to `:130-131`.
   Prometheus and Loki dropped from the routed set and filed as the
   deliberately-unrouted case (`docs/haproxy_reverse_proxy.md:30`, N1 `done`).
2. **Vault-engine claim corrected** (§4, P7-P9). The old "KV2 is the only
   engine" is gone. Live: Consul, Nomad and JWT backends plus the human OIDC
   provider, and a `database` engine. Absent: `transit/`, `pki/`.
3. **Deliverable path settled once** (§7, §8, Q1, P10, and every eval row):
   `docs/rfcs/boundary-evaluation.md`. The only surviving mentions of the old
   `docs/notes/` path are in this history section and in Q1, both of which
   name it to reject it.
4. **Both broken eval scorers fixed and probed.** Row 3 now uses
   `grep -q -e boundary_controller -e boundary_worker`, avoiding the pipe
   entirely: a `\|` written to survive the markdown table reaches `grep -E`
   as a literal escaped pipe and never matches. Row 7 is `! grep -qi zitadel`
   rather than `grep -ci`, which exits 1 on the clean case.
5. **Eval row 4 repaired.** It no longer requires the doc to call
   `secrets.tf:2-7` the sole engine. It requires the live inventory:
   `database/creds/s2-poc` tied to S2, and `transit` as the engine still to
   add.
6. **S2 edge resolved in its favor.** S2 is `done` and deliberately left the
   `database` mount, the `postgres-poc` connection and the `s2-poc` role
   standing for this spike, so the dependency delivers a concrete artifact.
   The contradicting Q2 recommendation is deleted.
7. **F2 no longer a hanging prerequisite.** `vault_identity_oidc_provider.lab`
   is deployed (`oidc.tf:95`) and F2 is `done`, so
   `boundary_auth_method_oidc` has an issuer. Requirement 6 says which
   prerequisites are met and which are not.
8. **Eval strengthened against shape-passing.** A new rubric row fails a doc
   whose verdict rests only on material this plan already contains.

Structural: the plan now carries the `# Ticket:` header and a
`Premises / assumptions` section; `loopctl verify-plan` returns `valid`.

### 2026-08-04, second pass — PARTIALLY SOUND, `pass-with-required-fixes`

F2, F4 and F6 confirmed correct and complete. F2 was isolated and shown to be
load-bearing: a doc containing `S2`, `database/creds/s2-poc`, `secrets.tf` and
the phrase "encrypted in transit" but no Vault Transit mount passes the old
bare `transit` and fails the new `transit/`. The `secrets.tf` re-addition was
judged right rather than gate-appeasement, since §7 independently requires the
citation.

Four fixes, applied:

1. **Row 8 had a demonstrated false pass.** `git diff HEAD` never reports
   untracked files, and the eval is scored *before* the commit, so untracked
   is the live state at scoring time. A new
   `deployments/infrastructure/boundary.tf` or a whole
   `bootstrap/roles/boundary_controller/` left unstaged passed the row — which
   is exactly the shape scope-creep-into-a-build takes, and this row is the
   only mechanical thing standing between this spike and that. The Input now
   pairs `git status --porcelain` with the diff, restoring what the first
   fix dropped. Reproduced here across four cases: doc-only passes, and a
   staged `.tf`, an untracked `.tf` and an untracked role directory all fail.
2. **F3 undercounted.** The grep returns four hits, not one: S2's comment plus
   three uses of the English word at `developer_group.tf:6`, `:104` and
   `roles.tf:9`. The conclusion holds — nothing Boundary-shaped is built — but
   §4 and P6 now say what the command actually returns.
3. **F5 was wrong on one hook.** `check-merge-conflict` is `types: [text]`, so
   **three** hooks reach a `docs/` markdown, not two, and §8 had listed it
   among the twelve supposedly typed away. Confirmed live: `prek run
   check-merge-conflict --files docs/haproxy_reverse_proxy.md` reports
   `Passed`, where `check-json` reports `Skipped`.
4. **A contradiction the `secrets.tf` re-addition introduced.** §8 item 4
   still described a three-term check while the marker's row greps four at
   100%. Same pattern as every other ticket in this batch: the fix landed at
   the site the reviewer named and left the prose that describes it stale.

Shape-check status: better against the naive copy — a §4+§5 copy now fails
rows 3 and 7 — but a §4+§5+§6 copy with the Zitadel line stripped still passes
all four deterministic rows. Rubric row 6 remains the sole guard there and was
judged adequately worded.
