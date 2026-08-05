---
verdict: pass
plan: 5eb310c25e6822229393a92423a55cc60ffee870512353efb7b9d529e300a42c
---

# Plan review: S1-spike-boundary-evaluation (cycle 3, pass id `plan-validator`)

Reviewed 2026-08-04 against `/home/vscode/workspace`. This verdict replaces the
cycle-2 verdict, which bound the pre-fix plan fingerprint
`2ec1a0c9a87c9d3cc23bac9a8f431866faf46317b88664c39cb9bb5d2b703174`.

## Premise verdict

**SOUND.**

All twelve stated premises hold. Every load-bearing anchor resolves. All four
deterministic scorers in the marker were run verbatim against throwaway good and
bad documents; each passes the good doc and fails the matching bad one. Row 8's
new form was probed against nine mutation shapes. The two premises the plan
could previously only assert from Terraform (P8, P9) were confirmed against the
live Vault. The four fixes from cycle 2 are correctly and completely applied.

This is a clean pass. I found no defect that changes a gate command, an eval
row, a threshold, or a conclusion. The three residues listed at the end are
editorial and explicitly not required fixes.

## Deterministic floor

`loopctl verify-plan S1-spike-boundary-evaluation` returns `valid`, with two
warnings only (`ambiguous file basename 'providers.tf'`, `'secrets.tf'`). Both
are disambiguated by full path everywhere the plan cites them, e.g.
`deployments/infrastructure/providers.tf:7-10`. No hard-fail.

## Per-assumption findings

### P1 — HOLDS. The front door terminates TLS.

`deployments/infrastructure/services/haproxy.hcl:95-96` is `frontend https_in` /
`bind *:443 ssl crt /secrets/haproxy.pem`. `:91-93` is `frontend http_in` /
`bind *:80` / `http-request redirect scheme https code 301 unless { ssl_fc }`.
Read verbatim; both match.

### P2 — HOLDS. Ten routed services, Prometheus and Loki excluded.

ACLs begin at `haproxy.hcl:98` (`acl is_minio`) and `use_backend` ends at `:118`
(`use_backend bifrost`), so `98-118` is exact. Backends run `:127` (`backend
minio`) to `:156-157` (`backend bifrost`), so `127-157` is exact. The routed set
is minio, s3, vault, nomad, consul, phoenix, memex, grafana, mlflow, bifrost —
ten, with no prometheus or loki backend in the file.
`docs/haproxy_reverse_proxy.md:30` reads "**Prometheus and Loki are deliberately
not routed here.**"

### P3 — HOLDS. Wire targets are raw host:port.

`postgres.hcl:12-14` is `network {` / `port "db" {` / `static = 5432`.
`nats.hcl:14` is `static = 4222`. `haproxy.hcl:130-131` is `backend s3` /
`server s3_1 192.168.2.29:9000 check`; `:127-128` is `backend minio` /
`server minio1 192.168.2.29:9001 check`.

### P4 — HOLDS. `vault_server` is the closest role model; services run plain HTTP.

`bootstrap/roles/vault_server/tasks/main.yml` exists (4.2K).
`bootstrap/roles/vault_server/templates/vault.hcl.j2:19-20` is
`address = "0.0.0.0:8200"` / `tls_disable = true`.
`bootstrap/roles/nomad_server/` contains `files/ handlers/ tasks/ templates/`
exactly as claimed.

### P5 — HOLDS. The wiring points exist.

`bootstrap/playbooks/configure_hashistack_server.yml:28-35` is `Configure Vault
manager` / `hosts: manager` / `- role: vault_server`; `:37-45` is the sibling
Nomad play. `bootstrap/inventory/cluster.ini:1-3` is `[manager]` /
`firebat ansible_host=192.168.2.30`.

### P6 — HOLDS, and the corrected count is exact.

`grep -rin boundary bootstrap deployments` returns exactly four hits, at exactly
the four anchors the plan now names:
`deployments/applications/database-secrets-poc.tf:10`,
`deployments/infrastructure/developer_group.tf:6`, `developer_group.tf:104`,
`deployments/infrastructure/roles.tf:9`. All four are prose; three are the
English word in containment-boundary comments. `zitadel` returns zero.
`providers.tf:1-24` declares nomad, vault, null and google (plus a commented-out
consul block at `:19-22`, which is not a declared provider); `:28` is
`provider "vault" {}`. **Fix 2 is correct.**

### P7 — HOLDS. Dynamic credentials are already live.

`consul_deploy_role.tf:19` is `resource "vault_consul_secret_backend_role"
"deploy"`; `nomad_deploy_role.tf:36` is `vault_nomad_secret_role "deploy"`;
`nomad_oidc.tf:74` is `vault_nomad_secret_role "manage"`; `acme.tf:66` is
`vault_jwt_auth_backend_role "acme"`; `oidc.tf:95` is
`vault_identity_oidc_provider "lab"`. All five resolve to the declared type.

### P8 — HOLDS, confirmed live.

`deployments/applications/database-secrets-poc.tf:200-204` declares
`vault_mount "database"` with `type = "database"`; `:212` is
`name = "postgres-poc"`; `:288` is `role_name = "s2-poc"`.
`docs/postgres-vault-dynamic-creds-spike.md:387-396` is the "What this spike
left running" list, and `:354` carries the quoted handover sentence verbatim.
Against the live Vault (`http://192.168.2.30:8200`, `sealed:false`):
`LIST database/roles` returns `["s2-poc"]` and `LIST database/config` returns
`["postgres-poc"]`. The inherited credential path is real, not described.

### P9 — HOLDS, confirmed live and stronger than claimed.

No `vault_mount` of type `transit` or `pki` anywhere under `deployments/`. The
live mount table is `agent-registry/ bootstrap/ consul/ cubbyhole/ database/
identity/ nomad/ secret/ sys/` — no `transit/`, no `pki/`. A KEEP verdict does
add a Transit mount.

### P10 — HOLDS.

`ls docs/` shows `architecture/` and `notes/`, and no `rfcs/`.

### P11 — HOLDS, counts exact.

Case-insensitive `boundary` matches exactly seven plans (F8, N4, R1, R2, R3, R7,
S1) and five docs (breakglass, cluster-roles, notes/audit/plan-premise-sweep,
postgres-vault-dynamic-creds-spike, vault-human-auth).
`.loop/plans/R1-rollout-mlflow-oauth2-proxy.md:74` reads "is the sibling plan
`.loop/plans/S1-spike-boundary-evaluation.md`" and
`.loop/plans/R7-rollout-postgres-consumer-cutover.md:153` reads "previously
handed them to `S1-spike-boundary-evaluation` and cited". Both are pointers back
at S1. No ticket pre-decides KEEP or DROP.

### P12 — HOLDS.

`justfile:18-19` is `pre_commit:` / `pre-commit run --all-files`.
`.pre-commit-config.yaml:1` is `exclude: '^\.(claude|loop)/'`.

### P13 (implicit, added by me) — HOLDS. The Boundary resource names in §5 are real.

Checked against the Terraform registry API for `hashicorp/boundary` (latest
1.6.1): `boundary_scope`, `boundary_auth_method_oidc`, `boundary_target`,
`boundary_host_catalog_static`, `boundary_host_catalog_plugin`,
`boundary_credential_store_vault`, `boundary_credential_library_vault` and
`boundary_role` all resolve as resources. The `boundary_host_catalog_*` glob
covers both real variants. §9's mitigation to label these prospective is sound.

## The four cycle-2 fixes, verified

### Fix 1 — row 8's untracked hole. CLOSED.

I ran the row's exact predicate (`git status --porcelain -- bootstrap
deployments` empty AND `git diff --name-only HEAD -- bootstrap deployments`
empty AND `test -f` on the deliverable) across nine throwaway repos:

| case | result | status output |
| --- | --- | --- |
| doc-only baseline | PASS | (empty) |
| staged new `.tf` | FAIL | `A  deployments/infrastructure/boundary.tf` |
| untracked new `.tf` | FAIL | `?? deployments/infrastructure/boundary.tf` |
| untracked `bootstrap/roles/boundary_controller/` | FAIL | `?? bootstrap/roles/boundary_controller/` |
| deleted tracked, unstaged | FAIL | ` D …/secrets.tf` |
| deleted tracked, staged | FAIL | `D  …/secrets.tf` |
| renamed within `deployments/` | FAIL | `R  …/secrets.tf -> …/renamed.tf` |
| modified tracked, unstaged | FAIL | ` M …/providers.tf` |
| modified tracked, staged | FAIL | `M  …/providers.tf` |
| submodule added under `deployments/` | FAIL | `A  deployments/vendored` |

The four cases the plan's history claims to have reproduced reproduce exactly.
The three shapes the briefing asked me to attack — deletes, renames, submodules
— are all caught, because `git status --porcelain` reports `D`, `R` and `A`, and
the diff catches them independently.

**Bounded residual, not a fix.** `git status --porcelain` without `--ignored`
does not list gitignored files, so a file matching a `.gitignore` rule under
`bootstrap/` or `deployments/` slips both checks. I reproduced this: an ignored
`boundary.tf` PASSes. In this repo the reachable ignore rules are
`**/vars/prod.tfvars` (root `.gitignore`), `deployments/.gitignore`
(`.terraform`, `.terraform.lock.hcl`) and `bootstrap/.gitignore` (`.env`). None
can hold an Ansible role or a Terraform resource: a new role is tracked YAML and
a new resource is a tracked `.tf`, and row 8 fails on both (cases c, d, and the
ignore-variant with a non-matching `.tf` all FAIL). The hole is real in the
abstract and unreachable by the failure mode row 8 exists to catch. Adding
`--ignored` would trade it for false failures on every `.terraform/` directory a
`terraform init` leaves behind. Leave it as is.

### Fix 2 — F3's count. CORRECT.

See P6. Four hits, three of them the English word, at exactly
`developer_group.tf:6`, `:104` and `roles.tf:9`. §4 and P6 agree with each other
and with the repo.

### Fix 3 — F5's hook count. CORRECT on substance.

From the cached upstream `.pre-commit-hooks.yaml`
(`~/.cache/prek/repos/321271af841bb4e8/`): `check-merge-conflict` is
`types: ['text']`, `detect-private-key` is `types: ['text']`, and
`end-of-file-fixer` is `types: ['text']` — exactly three reach a `docs/`
markdown. The four typed away are `check-json` (`json`), `check-ast` (`python`),
`check-yaml` (`yaml`) and `debug-statements` (`python`). All fourteen hook line
numbers cited in §8 resolve correctly against `.pre-commit-config.yaml`
(`:6 :7 :8 :9 :11 :12 :13 :16 :22 :28 :37 :46 :52 :66`), and fourteen is the
right total. `prek` is not on PATH in this environment, so I verified the type
filters from the hook definitions rather than by re-running the plan's cited
command; the conclusion is the same.

### Fix 4 — §8 item 4. CORRECT.

§8:280-287 now says "That is four terms the marker's row greps", matching marker
row 4, which greps exactly four: `S2`, `database/creds/s2-poc`, `transit/` and
`secrets.tf`. The stale three-term description is gone.

## Deterministic scorers, run verbatim

| row | good doc | bad doc | result |
| --- | --- | --- | --- |
| 1 `test -f` | exit 0 | — | correct |
| 3 `grep -q -e boundary_controller -e boundary_worker … && grep -q 'hashicorp/boundary' …` | exit 0 | exit 1 with `hashicorp/boundary` removed | correct; the `-e` alternation also passes a worker-only doc, as intended |
| 4 four-term chain | exit 0 | exit 1 when `` `transit/` `` is replaced by "encrypted in transit" | correct; the trailing-slash defense works as documented |
| 7 `! grep -qi zitadel` | exit 0 | exit 1 with a Zitadel line appended | correct |

No dead scorer, no false pass, no false fail. This is the first cycle in three
where every deterministic row behaves.

## Contract hygiene

- **Real code surface, resolved anchors.** Every `path:line` in §4, §7 and the
  Premises block was opened and matched. Zero broken anchors.
- **Discovered gates.** `just pre_commit` verified at `justfile:18-19`; the hook
  inventory verified against `.pre-commit-config.yaml` and the upstream hook
  definitions.
- **Explicit non-goals.** §5, six of them.
- **Tests homed.** Every eval row targets `docs/rfcs/boundary-evaluation.md`,
  which §7 lists as the single CREATE.
- **Forks surfaced.** Q3-Q5 open with recommendations; Q1-Q2 settled in
  "Resolved forks". Both `depends_on` targets
  (`S2-spike-postgres-vault-creds`, `A1-audit-plan-premise-sweep`) are stage
  `done` in `.loop/ledger.json`.
- **Path consistency.** `docs/notes/` appears in the marker only at line 10,
  where it says "No row names `docs/notes/`", and in the plan only at :375, :487
  and :508, all rejecting or historical.

## Most dangerous assumption

**P8** — that the `database/creds/s2-poc` path S2 left standing is actually
live, not merely declared. It is the one premise resting on cluster state rather
than repo text, and requirement 4, eval row 4 and subticket 3 all depend on it.
I confirmed it directly: `LIST database/roles` returns `["s2-poc"]` and
`LIST database/config` returns `["postgres-poc"]` against the live Vault. It
holds today. If S2's resources were torn down, this premise and three downstream
sections go with it.

## Not required fixes (editorial; do not re-plan for these)

Reported because the briefing asked for a contradiction sweep. None changes a
command, a threshold or a conclusion, and none justifies a fourth cycle.

1. **§8:241 says "those twelve stay green" six lines after §8:235 says "The
   other eleven".** Fix 3 moved `check-merge-conflict` out of the typed-away
   group and updated the first count (14 − 3 = 11, and the enumeration that
   follows lists exactly eleven) but left the summarizing clause at "twelve".
   The operative statement — that the typed-away hooks never run against
   anything this ticket writes — is correct either way. Correct the word the
   next time the file is touched for another reason.
2. **§7:189 over-claims that "every row" of the marker names the deliverable
   path.** Marker row 6 names only `.loop/plans/S1-spike-boundary-evaluation.md`
   in its Input. The claim's substance — no row names `docs/notes/` — holds.
3. **The history section at :500 writes "ACLs to `:99-118`"** where §4:50 and
   P2:400 both write the correct `98-118` (`acl is_minio` is at line 98). The
   two load-bearing statements are right; the historical narration is off by one
   line.

**Operational note, not a plan defect:** `.loop/ledger.json` records S1 at stage
`blocked`, not `planning`. Both `depends_on` targets are `done`, so the block
should clear, but the operator may need to move the stage before the
`PLANNING -> READY` flip is attempted.
