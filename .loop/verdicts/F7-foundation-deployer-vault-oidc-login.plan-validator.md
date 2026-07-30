---
verdict: fail
---

# Plan review — F7-foundation-deployer-vault-oidc-login (pass `plan-validator`)

Plan reviewed: `.loop/plans/F7-foundation-deployer-vault-oidc-login.md`
sha256 verified locally: `f5f135d1d9300adbb51af74cfbc9cff185c13b9d30e5031b1e03c5cf6d7e5be0`
(matches the briefing fingerprint; withheld from the header because this is a
`fail` and must not authorize the flip to `ready`).

## Premise verdict: BROKEN

The plan's whole deliverable is a policy that grants "exactly" the Vault paths
the Terraform deployer needs. That enumeration is wrong in both directions: it
omits every `sys/*`, `auth/*`, and secrets-engine-role write the deployer
performs today, and it omits at least nine KV2 paths added since authoring. A
policy built to this plan cannot run `terraform plan`, let alone `apply`, on
`deployments/infrastructure/`. Worse, the plan's own "definitive least-privilege
check" (eval row 3) would report GREEN on exactly that broken policy. Separately,
three of the plan's factual claims about neighbouring tickets went false after
authoring, and the `depends_on` edge to F2 is contradicted by the plan's own
recommendation in Q1.

## Load-bearing assumptions

### P1 — The deployer authenticates to Vault today with the static root token from the shell env. HOLDS

`deployments/infrastructure/providers.tf:28` is `provider "vault" {}` (empty,
env-driven) and the `hashicorp/vault ~>5.3.0` pin is at `:7-10`, exactly as
claimed. `.devcontainer/.env.example:10-11` seeds `VAULT_TOKEN=` / `VAULT_ADDR=`.
`bootstrap/roles/nomad_server/tasks/main.yml:189-196` slurps `/opt/vault/init.json`
and sets `vault_bootstrap_token` from `.root_token`; it is passed as `VAULT_TOKEN`
at `:202`, `:211`, `:224`, `:241`. Every cited line resolves.

### P2 — The complete set of Vault paths the deployer needs is the `default/*` KV2 paths plus `nomad/creds/deploy`, `consul/creds/deploy`, `database/creds/*`, and the policy must DENY `sys/*`, `auth/*`, `identity/*` writes. BREAKS

This is the plan's core premise (§6 requirement 2, §7, eval rows 1 and 3) and it
is false. `terraform apply` of `deployments/infrastructure/` today writes these
Vault paths, none of which are granted and three of which the plan explicitly
forbids:

| Resource | Vault path required | F7 §6 req 2 |
|---|---|---|
| `deployments/infrastructure/secrets.tf:2` `vault_mount "kvv2"` | `sys/mounts/<secret_mount>` (read on every refresh, write on create) | forbidden ("no `sys/*` management capability") |
| `deployments/infrastructure/acme.tf:41` `vault_policy "acme_tls_write"` | `sys/policies/acl/acme-tls-write` | forbidden |
| `deployments/infrastructure/acme.tf:66` `vault_jwt_auth_backend_role "acme"` | `auth/jwt-nomad/role/acme` | forbidden ("no `auth/*` … write") |
| `deployments/infrastructure/nomad_deploy_role.tf:36` `vault_nomad_secret_role "deploy"` | `nomad/role/deploy` (write) | not granted; plan grants read on `nomad/creds/deploy`, a different path |
| `deployments/infrastructure/consul_deploy_role.tf:19` `vault_consul_secret_backend_role "deploy"` | `consul/roles/deploy` (write) | not granted; plan grants read on `consul/creds/deploy` |
| F7's own `vault_policy "deployer"` (§7) | `sys/policies/acl/deployer` | forbidden by the policy it is writing |

Live confirmation that the deployer really does write these: `vault policy list`
returns `acme-tls-write` and `vault secrets list` returns the `secret/` KV2 mount
plus `nomad/` and `consul/` engines — all products of a `terraform apply` under
the root token. `vault list nomad/role` returns `deploy`; `vault list consul/roles`
returns `deploy`.

The plan names this exact failure mode in §9 ("an under-broad policy breaks the
very next `terraform apply`") and claims "the §4 path enumeration + eval 2 guard
that". Eval 2 only exercises KV2 read/write, so it cannot catch any of the six
rows above. And eval row 3 asserts that `vault write sys/policies/acl/xyz`
returning 403 proves the policy is correct — but the deployer legitimately writes
`sys/policies/acl/*` (that is how `vault_policy.acme_tls_write` and F7's own
`vault_policy.deployer` get created). The plan's definitive guardrail therefore
certifies a policy that breaks the deploy path.

Note I did not probe this live: minting a `deployer` token requires `vault policy
write` and `vault token create`, both mutating, and my brief is read-only. The
finding rests on the resource-to-endpoint mapping of the pinned `hashicorp/vault
~>5.3.0` provider, which is unambiguous for `vault_mount` (`sys/mounts`),
`vault_policy` (`sys/policies/acl`), and `vault_jwt_auth_backend_role`
(`auth/<backend>/role/<name>`).

### P3 — The §4 enumeration of `default/*` KV2 secrets the deployer manages is complete. BREAKS

§10 subticket 2 makes the enumeration load-bearing ("enumerating every `default/*`
KV2 data + metadata path (§4)"). It is missing at least nine paths that exist in
the repo today:

- `deployments/infrastructure/secrets.tf:101` — `default/bifrost/credentials`
  (a `data` source read, so the policy needs `read` on it)
- `deployments/infrastructure/secrets.tf:106` — `default/prometheus/bifrost-admin`
- `deployments/infrastructure/backup.tf:34,50,65,81` — four `default/backup-postgres/*`
  and `default/backup-minio/*` writes; `backup.tf` is not mentioned anywhere in §4 or §7
- `deployments/applications/secrets.tf:107` — `default/hermes/bifrost`
- `deployments/applications/secrets.tf:119` — `default/memex/bifrost`
- `deployments/applications/secrets.tf:130` — `default/bifrost/db`

Live `vault kv list secret/default` returns 18 prefixes (`acme/`, `backup-minio/`,
`backup-postgres/`, `bifrost/`, `gemini`, `grafana/`, `haproxy/`, `hermes/`,
`loki/`, `memex/`, `minio/`, `mlflow/`, `openfang/`, `phoenix/`, `postgres/`,
`prometheus/`, `talat-consumer/`, `talat-shim/`) against the plan's eleven.
Cause is commits after the 2026-07-24 authoring date: `ac3267b` (2026-07-29, B1)
and `e17d8d0` (2026-07-30) added the bifrost KV writes.

### P4 — `nomad/creds/deploy` and `consul/creds/deploy` do not exist yet, F5/F6 have "no ticket authored", and `.loop/plans/` has no F5/F6/F8 file. BREAKS

All three sub-claims are false:

- F5 and F6 are `done` in `.loop/ledger.json` and archived at
  `.loop/archive/F5-foundation-vault-nomad-secrets-engine/` and
  `.loop/archive/F6-foundation-vault-consul-secrets-engine/`.
- Their code shipped on 2026-07-24, the same day F7 was authored: commits
  `a539d64` (F5) and `21044c0` (F6), landing
  `deployments/infrastructure/nomad_deploy_role.tf` and
  `deployments/infrastructure/consul_deploy_role.tf`.
- `.loop/plans/F8-foundation-deployer-provider-cutover.md` exists (F8 is `ready`).
- Live: `vault list nomad/role` and `vault list consul/roles` both return `deploy`,
  so `nomad/creds/deploy` and `consul/creds/deploy` are readable now.

This cascades into §2 ("only fully exercisable once F5/F6 land"), §5 non-goals,
§9 failure mode (3), §11 cross-refs, and the §8 "honest bound" on eval 4 — all of
which now describe a world that no longer exists. It also means F5/F6 already
established the deployer-facing shape and comments (`nomad_deploy_role.tf:32-35`,
`consul_deploy_role.tf:1-18`) that F7 should be consuming rather than speculating
about.

### P5 — F2 is the OIDC identity source this ticket depends on, and the login role can be "pointed at the F2 issuer". BREAKS (broken dependency edge)

The frontmatter carries `depends_on = ["F2-foundation-vault-oidc-provider", ...]`,
§6 requirement 1 says the login reuses "the F2 OIDC provider as the issuer",
§10 subticket 3 says "pointed at the F2 issuer", and eval row 4 says "against the
F2 issuer". But the plan's own Q1 (`:349-367`) concludes the opposite: Vault
cannot be its own upstream IdP for a login method, so reusing F2's issuer is
circular, and the recommendation is Google OIDC. Both statements cannot be true.

Evidence that F2 cannot deliver a login method: F2's Resolved Q1
(`.loop/plans/F2-foundation-vault-oidc-provider.md:370-374`) chose **userpass**
as the human auth backend, and F2's §5 non-goals (`:93-97`) say F2 "only produces
the issuer + clients + secrets" for downstream RPs. Live Vault confirms nothing
of F2 exists yet: `vault auth list` returns only `jwt-nomad/` and `token/`.

The template match from the briefing is exact: F7 needs an OIDC *login* method;
its dependency F2 delivers an OIDC *provider* only. If Q1 resolves to the plan's
own recommendation (Google), `depends_on = F2` is wrong and F7 unblocks
immediately. The plan surfaces the fork honestly in §11 but never reconciles it
with the frontmatter, the requirements, or the eval — so the requirement and the
eval encode a conclusion the plan elsewhere says is impossible.

### P6 — F2's resolved human-login backend is userpass. HOLDS; the anchor BREAKS

Claim is correct: `.loop/plans/F2-foundation-vault-oidc-provider.md:370-374`
("Q1 → userpass in this Terraform root"). But F7 cites `:351-356` twice (at
`:96-97` and `:353-354`), and those lines are F2's *Q5* group-claim
recommendation, not Resolved Q1. The F2 plan was rewritten by `a6cc9c6`
(2026-07-26, T3 hostname cutover) after F7 was authored, shifting the offsets.

### P7 — F3's resolved fork chose a dedicated `vault_policy` resource in Terraform. HOLDS; the anchor BREAKS

Claim is correct, at `.loop/archive/F3-foundation-haproxy-tls-vault-pki/plan.md:335`
("Q1 → Dedicated scoped policy + role, in Terraform"). But F7 cites
`.loop/plans/F3-foundation-haproxy-tls-vault-pki.md` (§4 `:105-107`), and that
path no longer exists — F3 is `done` and archived. More usefully, F3 shipped, so
the precedent is now concrete in-repo at `deployments/infrastructure/acme.tf:41`
(`vault_policy "acme_tls_write"`) and `:66` (`vault_jwt_auth_backend_role "acme"`).
The plan points the implementer at a deleted plan document instead of the working
code that answers the same question.

### P8 — The remaining `path:line` anchors resolve. MOSTLY HOLDS; two BREAK

Resolve correctly: `deployments/infrastructure/providers.tf:28` and `:7-10` and
`:15-18,30-32` (google); `deployments/infrastructure/secrets.tf:2-7,15-29,37-44,52-66,74-88`;
`deployments/infrastructure/variables.tf:1-4`; `deployments/applications/variables.tf:1`;
`deployments/applications/secrets.tf:1-9,11-18,22-29,31-38,42-49,53-60,62-69,79-86,94-100`;
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-15` and
`:1-24` (file is exactly 24 lines, KV2 data/metadata split as described);
`bootstrap/roles/nomad_server/tasks/main.yml:189-196,202,211,224,241`.

Break:
- `deployments/applications/providers.tf:32` (cited in §4 as the empty vault
  provider). Line 32 is the closing brace of `required_providers`; the block is
  now at `:36`. B1 inserted the `bifrost` provider at `:27-30`.
- `deployments/applications/secrets.tf:102-110` (cited as `default/minio/<user>`,
  `for_each`). That range is now the `bifrost_hermes_key` comment and resource;
  `minio_credentials` moved to `:137-145`.

Minor: `justfile:16-18` for the `pre_commit` recipe is `:17-19` (16 is blank).

### P9 — The gate is `just pre_commit` running `pre-commit run --all-files`, with `terraform-fmt` and `terraform-validate` hooks over `.tf`. HOLDS

`.loop/config.json` `gates` = `["just pre_commit"]`; `justfile:18-19` runs
`pre-commit run --all-files`; `.pre-commit-config.yaml:22-26` (`terraform-fmt`,
`terraform fmt -check -recursive`, `types: [terraform]`) and `:28-32`
(`terraform-validate`, `entry: scripts/tf_validate.sh`); `scripts/tf_validate.sh`
exists and is executable. Gates are discovered, not assumed.

### P10 — An https issuer for `vault.lab.orangecluster.nl` is available, inherited from F3/F2 Q2. HOLDS

Live probe: `curl -sk https://vault.lab.orangecluster.nl/v1/sys/health` returns
200, and haproxy terminates TLS for that host
(`deployments/infrastructure/services/haproxy.hcl:96` bind `*:443 ssl crt`,
`:100` `acl is_vault`, `:111` `use_backend vault`, `:133-134`). The re-planned
T1/T2/T3 Let's Encrypt chain did not invalidate this.

### P11 — A policy may reference not-yet-existing backing paths, so eval 4's brokered read can't be exercised until F5/F6 land. BREAKS

Vault policies indeed need no backing path, so the first half is fine. The second
half is stale: F5/F6 landed (see P4), so the brokered reads are exercisable today.
The `database/` mount genuinely does not exist (`vault secrets list` has no
`database/`), and S2/R3 are still `ready`, so the `database/creds/*` half of this
assumption holds.

### P12 — The root token remains a fallback until F8, so a broken `deployer` policy cannot lock the operator out. HOLDS

F8 is `ready`, not `done`; `deployments/*/providers.tf` still declare empty
env-driven vault providers, and `.devcontainer/.env.example:10` still seeds
`VAULT_TOKEN`. Reversibility as stated.

### P13 — The eval file encodes the Definition of Done. HOLDS structurally, but row 3 is a false guardrail

`.loop/evals/F7-foundation-deployer-vault-oidc-login.md` exists with six rows.
**No row uses an `ls`, `grep`, or file-existence scorer** — all six are
"Deterministic check" over `vault` / `terraform` / `just` commands, so the
shape-check-eval attack surface reports clean. The substantive problem is row 3
(see P2): it asserts `vault write sys/policies/acl/xyz` → 403 proves correctness,
when the deployer must be able to write `sys/policies/acl/*`. Row 4 also depends
on the unresolved Q1 and inherits P5's contradiction.

## Required attack surface — findings

1. **Stale premise.** Three instances: P4 (F5/F6 done and shipped, F8 plan
   exists), P3 (nine-plus new KV2 paths from B1), P7/P6 (F3 archived; F2 plan
   rewritten by T3, shifting the cited offsets).
2. **Inlined conclusion.** No hardcoded inlining found, and this is to the plan's
   credit: §7 explicitly says "Do not hardcode the issuer host", and no issuer
   URL, client id, redirect URI, or auth mount path from F2 is asserted as
   settled. Live Vault has `identity/oidc/provider/default` (issuer
   `http://192.168.2.30:8200/v1/identity/oidc/provider/default`) and a leftover
   client `test` (`client_id Me1SFwFrPWG2TziSDUaLTItaPpLgusBe`, empty
   `redirect_uris`), none of which F7 assumes anything about. The related but
   distinct defect is P5: F2's *existence as a usable dependency* is asserted in
   the frontmatter, requirements, and eval while Q1 argues it cannot serve.
3. **Broken dependency edge.** Found: P5. `depends_on = F2`, but F2 delivers an
   OIDC provider (IdP for downstream RPs, human backend userpass) and cannot
   deliver the `oidc` *login* auth method F7 needs.
4. **Shape-check eval.** No instance found. No `ls`/`grep`/file-existence scorer
   in the eval file. Row 3 is defective for a different reason (P2/P13).
5. **Unresolvable anchor.** Found: `.loop/plans/F3-foundation-haproxy-tls-vault-pki.md`
   (file gone), `F2-...md:351-356` (wrong content), `deployments/applications/providers.tf:32`
   (wrong content), `deployments/applications/secrets.tf:102-110` (wrong content).

## Most dangerous assumption

**P2** — that the deployer needs no `sys/*`, `auth/*`, or secrets-engine-role
write. It is the ticket's entire deliverable, it is false, and the plan's own
"definitive least-privilege check" would certify the broken result as correct.
Shipping this plan produces a `deployer` policy that cannot run `terraform plan`
on `deployments/infrastructure/`, with a green eval.

## Required fixes before this plan can leave PLANNING

1. **Re-derive the policy from the resource graph, not from a KV list.** Walk
   every `vault_*` resource in both roots and map each to its Vault endpoint. At
   minimum add: `sys/mounts/<secret_mount>` (`secrets.tf:2`),
   `sys/policies/acl/*` scoped to the policies the deployer owns
   (`acme.tf:41`, plus F7's own `deployer` policy),
   `auth/jwt-nomad/role/*` (`acme.tf:66`), `nomad/role/deploy`
   (`nomad_deploy_role.tf:36`), `consul/roles/deploy`
   (`consul_deploy_role.tf:19`). Restate §6 requirement 2 accordingly; the
   least-privilege story becomes "scoped `sys`/`auth` paths", not "no `sys`/`auth`".
2. **Rewrite eval row 3.** `vault write sys/policies/acl/xyz` is a legitimate
   deployer action, so it cannot be the guardrail. Pick a genuinely out-of-scope
   probe (for example `vault token create -policy=root`, `vault auth enable`, or
   a `sys/policies/acl/` name outside the deployer's owned set) and add a
   positive row that proves `terraform plan` on `deployments/infrastructure/`
   succeeds under a `deployer` token — the check that would have caught P2.
3. **Refresh the §4 KV2 enumeration** to include `default/bifrost/credentials`
   (read), `default/prometheus/bifrost-admin`, the four `backup.tf` paths
   (`default/backup-postgres/*`, `default/backup-minio/*`), `default/hermes/bifrost`,
   `default/memex/bifrost`, and `default/bifrost/db`. Add `deployments/infrastructure/backup.tf`
   to the reference anchors in §7. Consider whether a prefix grant on
   `<mount>/data/default/*` is the honest shape, given the list churns every ticket.
4. **Correct the F5/F6/F8 state** in §2, §4, §5, §8 ("honest bound"), §9 failure
   mode (3), and §11 cross-refs: F5 and F6 are `done`, their code is at
   `deployments/infrastructure/nomad_deploy_role.tf` and `consul_deploy_role.tf`,
   `nomad/creds/deploy` and `consul/creds/deploy` are live, and F8 has a plan.
   Eval row 4's brokered read is exercisable now.
5. **Reconcile the F2 dependency.** Either settle Q1 to an external IdP (the
   plan's own recommendation) and drop `F2-foundation-vault-oidc-provider` from
   `depends_on`, striking "the F2 issuer" from §6 requirement 1, §10 subticket 3,
   and eval row 4 — or state concretely what F2 must additionally deliver for the
   login half to work. As written the frontmatter and Q1 contradict each other.
6. **Repair the anchors:** replace `.loop/plans/F3-foundation-haproxy-tls-vault-pki.md`
   with the shipped precedent `deployments/infrastructure/acme.tf:41,66` (and, if
   the plan text is still wanted, `.loop/archive/F3-foundation-haproxy-tls-vault-pki/plan.md:335`);
   change `F2-...md:351-356` to `:370-374`; change
   `deployments/applications/providers.tf:32` to `:36`; change
   `deployments/applications/secrets.tf:102-110` to `:137-145`; change
   `justfile:16-18` to `:17-19`.
7. **Note `vars/prod.tfvars` is git-ignored** (`.gitignore:12`), so §7's code
   surface can only touch `vars/prod.tfvars.example` inside the loop.

## Contract hygiene (secondary)

Explicit non-goals: present and specific (§5). Tests homed in the code surface:
§8 states this explicitly and it holds for the files it names, though the
enumeration gap in P3 means `backup.tf` belongs in §7. Gates: discovered, not
assumed (P9). Forks: surfaced with recommendations in §11, and Q1 is honestly
flagged as load-bearing — the defect is that the rest of the plan proceeds as if
Q1 were already resolved the other way. The contract sections are all present;
the premise beneath them is what fails.
