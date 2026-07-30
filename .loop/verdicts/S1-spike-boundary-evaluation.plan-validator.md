---
verdict: fail
---

# Plan review — S1-spike-boundary-evaluation (pass `plan-validator`)

Plan: `.loop/plans/S1-spike-boundary-evaluation.md`
Fingerprint verified with `sha256sum`:
`3fa73dddaf2d425475ddd09b52b4e926768fd3bca9022dac3353758cb47c74d3` (matches
the briefing). The `plan:` line is deliberately omitted: this is a `fail` and
must not authorize the flip to `ready`.

## Premise verdict: BROKEN

Gate verdict: **fail**.

The spike's *question* survives (no other ticket has answered it — see P12).
What does not survive is the world the plan describes. The Context's front-door
premise was falsified by F3/T1-T3 on 2026-07-24/25, the deliverable path was
deleted from the repo on 2026-07-26, the plan contradicts its own operator
resolution about where the deliverable lives, the authoritative eval targets the
deleted path with two scorers that cannot pass, and the `depends_on` edge to S2
cannot deliver what the resolved fork claims it delivers.

## Load-bearing assumptions

### P1 — The browser front door is HAProxy on plain HTTP:80 with no TLS, at `haproxy.hcl:48` — **BREAKS**

Plan lines 39-41 and 146: "HAProxy on plain HTTP:80 with static backends and no
TLS: `deployments/infrastructure/services/haproxy.hcl:48` (`frontend http_in` /
`bind *:80`)", called out at line 146 as "Load-bearing for the 'front door
already covered' premise".

Repo now: `haproxy.hcl:48` is a comment line
(`### blank lines, HAProxy cannot parse `crt`, and every routed service goes`).
`frontend http_in` is at `haproxy.hcl:91` and its body is
`bind *:80` plus `http-request redirect scheme https code 301 unless { ssl_fc }`
(`haproxy.hcl:92-93`). A second frontend exists:
`frontend https_in` / `bind *:443 ssl crt /secrets/haproxy.pem`
(`haproxy.hcl:95-96`), fed by a Vault KV2 template at `haproxy.hcl:62-73` and a
static `https` port at `haproxy.hcl:15-17`.

Live cluster: `http://192.168.2.30:80` returns `301`;
`https://192.168.2.30:443` completes a TLS handshake; the served certificate is
`subject=CN = *.lab.orangecluster.nl`, `issuer=... Let's Encrypt ... CN = YE2`,
valid `Jul 26 2026` to `Oct 24 2026`. `https://vault.lab.orangecluster.nl/v1/sys/health`
returns `200`. Corroborated by `docs/haproxy_reverse_proxy.md:3-10` ("single
HTTPS entry point ... Plain HTTP on port 80 answers only with a 301") and
`docs/tls-certificates.md:1-7`.

This is the classic pattern: the anchor is *stale by line* and *false by claim*.

### P2 — `haproxy.hcl:84-121` is the static-backend inventory, and it includes prometheus and loki — **BREAKS**

Plan lines 41-43 and 146. Two separate failures.

Location: `haproxy.hcl:84-121` is the `defaults` tail, the `userlist`, and the
two frontends. The `backend` blocks are at `haproxy.hcl:127-157`.

Membership: the routed set is minio, s3, vault, nomad, consul, phoenix, memex,
grafana, mlflow, bifrost (`haproxy.hcl:109-118`, `127-157`). Prometheus and Loki
are **not** routed. `docs/haproxy_reverse_proxy.md:29` states it explicitly:
"**Prometheus and Loki are deliberately not routed here.**" N1
(`N1-netsec-restrict-prometheus-loki-to-cluster`) is `done` in the ledger. The
plan names both as front-door backends.

This matters to the spike directly: Prometheus and Loki are precisely the
LAN-exposed, non-front-doored services a session broker would be weighed
against, and the plan files them on the wrong side of the line.

### P3 — MinIO console at `haproxy.hcl:84-85`, S3 API at `haproxy.hcl:87-88` — **BREAKS**

Plan lines 47-49. Actual: `backend minio` / `server minio1 192.168.2.29:9001` at
`haproxy.hcl:127-128`; `backend s3` / `server s3_1 192.168.2.29:9000` at
`haproxy.hcl:130-131`. The host:port facts are right; both anchors point at
`defaults`/`userlist` lines.

### P4 — Postgres static 5432 (`postgres.hcl:13`) and NATS static 4222 (`nats.hcl:14`) are raw host:port today — **HOLDS**

`deployments/infrastructure/services/nats.hcl:14` is exactly `static = 4222`.
`deployments/infrastructure/services/postgres.hcl:13` is `port "db" {` with
`static = 5432` on line 14 — off by one, inside the block it names. Both jobs
run (`nomad job status`: `postgres`, `nats` both `running`). Neither is routed
through HAProxy. Substantively sound.

### P5 — Vault runs plain HTTP (`vault.hcl.j2:19-20`, `tls_disable = true`) and `vault_server` is the closest model for a new controller role — **HOLDS**

`bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20` is
`address = "0.0.0.0:8200"` / `tls_disable = true`. Live: `https://192.168.2.30:8200`
fails the handshake, `http://192.168.2.30:8200/v1/sys/health` returns `200`,
`VAULT_ADDR=http://192.168.2.30:8200`. `bootstrap/roles/vault_server/tasks/main.yml`
exists. `bootstrap/roles/nomad_server/` has `files/ handlers/ tasks/ templates/`
as described (plan lines 154-156).

Note for the doc, not a break: F3 shipped TLS *at the edge only*. Vault's own
listener is still plain HTTP behind HAProxy. The plan gets this right; P1 is
where it goes wrong.

### P6 — `vault_server` is invoked from `configure_hashistack_server.yml:28-35` against `manager`/firebat (`cluster.ini:1-3`) — **HOLDS**

`bootstrap/playbooks/configure_hashistack_server.yml:28-35` is exactly the
"Configure Vault manager" play with `hosts: manager`;
`:37-44` is the `nomad_server` play, so the `:28-44` span at plan line 157 also
resolves. `bootstrap/inventory/cluster.ini:1-3` is `[manager]` / `firebat
ansible_host=192.168.2.30` / `firebat ansible_user=firebat`.

### P7 — No `hashicorp/boundary` provider; zero matches for `boundary`, `oidc`, `zitadel`, `transit` under `bootstrap/` and `deployments/` — **HOLDS**

`deployments/infrastructure/providers.tf:7-10` is the `vault` required_provider
block, `:28` is `provider "vault" {}`. A case-insensitive recursive grep for
`boundary|oidc|zitadel|transit` over `bootstrap/` and `deployments/` returns
zero hits. `bootstrap/roles/tailscale/` exists (Q5's premise holds).

### P8 — The only Vault engine configured in Terraform is a single KV2 mount; the dynamic-credential benefit "depends on Vault credential engines that do not yet exist" — **BREAKS (partially)**

Plan lines 67-73. The *database*, *PKI*, and *Transit* half holds: live
`vault secrets list` shows no `database/`, no `pki/`, no `transit/`. (F3's slug
says `vault-pki`, but it shipped ACME/Let's Encrypt into KV2 instead — see
`docs/tls-certificates.md:1-7` and the `haproxy.hcl:46` comment "a PKI issue
response *did*". So "no PKI" survives F3 by accident.)

What breaks is the absolute claim. Live `vault secrets list` returns
`bootstrap/ (kv)`, `consul/ (consul)`, `nomad/ (nomad)`, `secret/ (kv2)`, plus
`cubbyhole/ identity/ sys/`, and `vault auth list` returns `jwt-nomad/ (jwt)`.
F5 (`F5-foundation-vault-nomad-secrets-engine`) and F6
(`F6-foundation-vault-consul-secrets-engine`) are both `done` in the ledger.
Terraform itself now manages roles on those backends:
`deployments/infrastructure/consul_deploy_role.tf:19`
(`vault_consul_secret_backend_role.deploy`) and
`deployments/infrastructure/acme.tf:66` (`vault_jwt_auth_backend_role.acme`).

So two dynamic credential engines *do* exist, and Terraform is no longer
KV2-only. For a spike whose whole thesis is "Boundary's main benefit depends on
credential engines that do not exist", that is load-bearing: the correct framing
is that Vault dynamic credentials are already a live, proven pattern in this
cluster, which *strengthens* the "Boundary is redundant" side of the ledger the
spike is weighing. The plan hands the spike the opposite starting point.

### P9 — The deliverable lives at `docs/notes/boundary-evaluation.md`, and the repo has `docs/notes/` with `feat/` and `main/` subdirs — **BREAKS**

Plan lines 143, 206, 292-296. `docs/notes/` **does not exist**. `ls docs/`
returns `architecture/ bootable_nvme_guide.md credential-rotation.md
delete_nomad_dynamic_host_volume.md dns.md gcs-backups.md
haproxy_reverse_proxy.md jetson_nano_orin_init.md monitoring.md nats.md
nats-postgres-cdc-bridge.md observability-python.md riscv-integration.md
tls-certificates.md` — no `notes/`, no `rfcs/`. `git ls-files | grep -E 'notes/|rfcs/'`
returns nothing.

It existed at authoring time and was deleted after:
`git log --diff-filter=D --name-only -- docs/notes` shows commit `cc22050`
("docs: update plans", **2026-07-26 22:27 +0200**) removing
`docs/notes/.gitignore`, `docs/notes/config.json`, `docs/notes/main/2025*.md`.
The plan was authored 2026-07-24. Textbook stale premise.

### P10 — The eval at `.loop/evals/S1-spike-boundary-evaluation.md` is a usable authoritative DoD — **BREAKS (three ways)**

Plan line 242 declares the eval "the binding Definition of Done ... what the
loop-reviewer scores against". It cannot be satisfied.

**(a) Wrong path, contradicting the plan's own operator resolution.** Five of
seven eval rows (`evals/…:10, 12, 13, 14, 15`) target
`docs/notes/boundary-evaluation.md`, and row 7 (`evals/…:16`) asserts "The only
added/modified product path is `docs/notes/boundary-evaluation.md`". But the
plan's own **Resolved forks (operator, 2026-07-23)** at plan lines 319-321 says
"**Q1 → `docs/rfcs/boundary-evaluation.md`.** Operator chose an RFC location
rather than `docs/notes/`." The plan's section 7 (line 143) and Q1 (line 295)
were never updated either. An implementer who obeys the operator fails five
100%-threshold DoD rows; one who obeys the eval overrides an operator decision
and writes into a directory that no longer exists.

**(b) Row 3's scorer can never pass.** `evals/…:12` scores with
`grep -Eq 'boundary_controller\|boundary_worker' <doc>`. Under `-E`, `\|` is an
*escaped literal pipe*, not alternation. Probed:

    printf 'a boundary_controller role\n' > t.md
    grep -Eq 'boundary_controller\|boundary_worker' t.md   # NOMATCH
    grep -Eq 'boundary_controller|boundary_worker'  t.md   # MATCH

A correct doc scores 0 on a 100% threshold row; only a doc containing the
literal string `boundary_controller|boundary_worker` passes.

**(c) Row 6's guardrail exits non-zero on success.** `evals/…:15` scores
`grep -ci zitadel <doc>` and expects output `0`. `grep -c` returns **exit
status 1** when the count is zero (probed: `grep -ci zitadel t.md` prints `0`,
`exit=1`). Any exit-code-based harness marks the clean case as a failure.

**Shape-check findings (attack surface 4), as required.** Row 1 (`test -f`) is
pure file-existence: an empty file at the path scores 100%. Rows 3 and 4 are
greps for tokens the plan itself already lists, so a doc that merely copies the
plan's Non-goals block satisfies both without producing a single finding. Row 4
(`evals/…:13`) is worse than a shape check: its *Expected* column instructs the
doc to cite `secrets.tf:2-7` "as the sole engine that exists today", which P8
shows is now false — the DoD would certify a factual error. Only rows 2 and 5
(model + rubric) actually test whether the spike answered its question. For a
spike, that ratio is the wrong way round.

### P11 — S2 is a hard blocker because S1 must "test the real 'keep' path (Vault credential engines) end-to-end" — **BREAKS**

Plan lines 322-324 (Resolved forks Q2). The dependency edge cannot deliver.

*S1 cannot test anything.* Plan lines 80-82: "**No infrastructure ships.**"
Plan lines 206-207: "No live cluster calls: there is no deployed Boundary to
assert against." There is no end-to-end path in S1's scope for S2 to enable.

*S2 leaves nothing behind.* `.loop/plans/S2-spike-postgres-vault-creds.md:353-354`:
"**Cleanup.** After the live checks, tear down the PoC engine, role, and job",
repeated at `:417` ("Tear down PoC resources"). S2's deliverable is a decision
doc, not a persistent Vault database secrets engine.
`.loop/plans/S2-spike-postgres-vault-creds.md:107-108` confirms the other
direction: "**No Boundary work.** S1 owns Boundary."

*The plan contradicts itself on the same fork.* Open Question Q2 at plan lines
299-301 recommends the opposite of the resolution: "let S1 proceed now — ...
The spike should not wait on S2." Both texts ship in the same file.

*And S2 is unrun.* Ledger: `S2-spike-postgres-vault-creds` is `stage: ready`,
`attempts: 0`. Serializing a doc-only spike behind an unrun, review-defective
spike buys nothing that a citation would not.

### P12 — The spike's question is still open; no other ticket has answered it — **HOLDS**

A grep for `\bboundary\b` across `.loop/plans/`, `.loop/evals/`, and
`.loop/reflections/` (excluding S1's own files) returns only:
`plans/S2-…:41,107-108` (defers to S1), `plans/R1-…:74` (points at S1 as the
sibling plan), and unrelated uses of "boundary" as a common noun in
`plans/R3-…:337` and `plans/R2-…:176,247`. `grep -ri boundary docs/` returns
nothing. No ticket pre-decides KEEP or DROP.

This is the one place S1 differs from dropped-S3: **S1 is not redundant.** Its
question is genuinely unanswered, and F3 shipping TLS at the edge does not
answer "is a session broker worth it at the wire/SSH layer". The plan should be
fixed, not dropped.

### P13 — "No session-brokering layer today; wire-level and SSH access is direct-to-host" — **HOLDS**

No `boundary` anywhere in the repo (P7), none in the live Nomad job list
(`acme backup-minio backup-postgres bifrost grafana haproxy hermes loki memex
minio mlflow nats node-exporter phoenix postgres prometheus promtail
talat-consumer talat-shim`). `bootstrap/roles/tailscale/` is the only adjacent
access layer, correctly surfaced as Q5 (plan lines 311-315).

### P14 — "Vault confirmed as the OIDC provider for humans" (plan line 28), so Boundary's OIDC auth method has an IdP to consume — **UNCERTAIN**

As a *design decision* this is fine and matches the epic. As a *state* it is not
yet true, and the plan never says which. Live: `vault list identity/oidc/provider`
returns only the built-in `default`; `identity/oidc/client` returns a single
`test` client; `vault auth list` has no OIDC method for humans. The enabling
ticket `F2-foundation-vault-oidc-provider` is `stage: ready`, `attempts: 0`.

The plan carefully ties the credential-engine prerequisite to S2 (requirement 4,
plan lines 118-120) but never ties the OIDC-auth-method prerequisite to F2, even
though `boundary_auth_method_oidc` is named in Non-goals at plan line 84. A KEEP
verdict inherits an unrun F2 as a second hard prerequisite. Not a break on its
own; a gap the fix list should close.

### P15 — The tests-and-gates section matches this repo — **HOLDS**

Root `justfile:17-19` defines `pre_commit: pre-commit run --all-files`.
`.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`; hooks are
`pre-commit-hooks` v5.0.0 (check-json, check-ast, check-merge-conflict,
check-yaml `--unsafe`, debug-statements, detect-private-key, end-of-file-fixer)
plus local nomad-fmt (`types: [hcl]`), terraform-fmt
(`terraform fmt -check -recursive`), terraform-validate
(`scripts/tf_validate.sh`). Every detail at plan lines 177-191 checks out.
Non-goals (section 5) are explicit and the doc gates are homed on the
deliverable file. Contract hygiene is otherwise fine — which is exactly why the
existing gates saw nothing wrong.

## Most dangerous assumption

**P10(a) — that the eval's `docs/notes/boundary-evaluation.md` is the agreed
deliverable path.** It is the single one that, if wrong, sinks the plan, because
it is wrong three times over at once: the directory no longer exists in the repo
(P9), the operator explicitly resolved the fork the other way to `docs/rfcs/`
(plan lines 319-321), and the *authoritative* DoD (plan line 242) hardcodes the
superseded path into five 100%-threshold rows including a guardrail that forbids
touching any other path. There is no way to run this ticket to a passing DoD.
P1 is the more embarrassing staleness; P10(a) is the one that makes the ticket
unexecutable.

## Required fixes before this plan leaves PLANNING

1. **Rewrite the front-door premise (P1, P2, P3).** Section 4 must say the edge
   is HAProxy terminating TLS on `*:443` with a Let's Encrypt wildcard
   (`haproxy.hcl:95-96`, cert templated from Vault KV2 at `haproxy.hcl:62-73`),
   with `*:80` a 301 redirect (`haproxy.hcl:91-93`). Re-anchor the backend
   inventory to `haproxy.hcl:127-157`, minio console to `:127-128`, s3 to
   `:130-131`. Drop prometheus and loki from the routed set and note they are
   deliberately unrouted (`docs/haproxy_reverse_proxy.md:29`, N1 `done`).
2. **Correct the Vault-engine claim (P8).** Replace "the only Vault engine
   configured in Terraform ... no database secrets engine, no PKI, no Transit"
   with the live state: `nomad/` and `consul/` dynamic secrets engines exist
   (F5, F6 `done`), `jwt-nomad/` auth exists, Terraform manages
   `vault_consul_secret_backend_role` (`consul_deploy_role.tf:19`) and
   `vault_jwt_auth_backend_role` (`acme.tf:66`); what is absent is `database/`,
   `pki/`, and `transit/`. State that existing dynamic-credential coverage is an
   input to the cost/benefit, not just a missing prerequisite.
3. **Settle the deliverable path once (P9, P10a).** Pick `docs/rfcs/boundary-evaluation.md`
   per the operator resolution, note that `docs/rfcs/` must be created and that
   `docs/notes/` was deleted in `cc22050` (2026-07-26), then update plan line
   143, Q1 (lines 292-296), section 8 (lines 193, 206), and **every row of
   `.loop/evals/S1-spike-boundary-evaluation.md`** to the same path. One path,
   one place.
4. **Fix the two broken eval scorers (P10b, P10c).** Row 3: drop the backslash —
   `grep -Eq 'boundary_controller|boundary_worker'`. Row 6: score on output or
   invert — e.g. `! grep -qi zitadel <doc>`, or `[ "$(grep -ci zitadel <doc>)" = 0 ]`.
5. **Repair eval row 4's Expected (P10d).** Stop requiring the doc to call
   `secrets.tf:2-7` "the sole engine that exists today". Require instead that it
   name the *missing* engines (`database`, `transit`) against the live inventory
   and tie the database engine to S2.
6. **Resolve or drop the S2 edge (P11).** Either delete the `depends_on` on S2
   and cite S2 as a documented prerequisite (which is what the doc-only scope
   and S2's teardown at `S2-…:353-354` actually support), or state a concrete
   artifact S2 leaves behind that S1 consumes. Delete the contradicting Q2
   recommendation at plan lines 299-301 so only one answer ships.
7. **Name F2 as the second KEEP prerequisite (P14).** `boundary_auth_method_oidc`
   needs a Vault OIDC provider; live Vault has only the built-in `default`
   provider and a stray `test` client, and `F2-foundation-vault-oidc-provider`
   is `ready`/unrun. Say "confirmed as the design decision, not yet deployed
   (F2)" rather than "confirmed".
8. **Strengthen the eval's finding checks.** Rows 1, 3, and 4 all pass against a
   doc that copies the plan's own Non-goals block. Add at least one rubric-scored
   row that the doc's verdict cites evidence *not already present in the plan*
   (e.g. the Tailscale-SSH overlap from Q5, or the existing `nomad/`/`consul/`
   dynamic-credential precedent), so "the spike produced a document" cannot be
   mistaken for "the spike produced a finding".

## Note on scope

P12 holds: this spike is **not** redundant and should not be dropped the way S3
was. The question it asks is unanswered by F3, by the TLS chain, and by every
other plan in `.loop/plans/`. Fix the premise and the eval, and it is worth
running.

## Method

Read-only throughout. Repo reads under
`/home/vscode/workspace/.loop/worktrees/A1-audit-plan-premise-sweep`; live reads
were `vault status`, `vault secrets list`, `vault auth list`,
`vault list identity/oidc/{provider,client,key}`, `nomad job status`, `curl`,
and `openssl s_client`. No mutating command was issued against Vault, Nomad,
Consul, Terraform, or git. The only file written is this verdict.
