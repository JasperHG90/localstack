---
verdict: fail
---

# Plan review — F2-foundation-vault-oidc-provider (pass `plan-validator`)

Plan fingerprint verified locally with `sha256sum`:
`13097f496b222e83b7575faf5b50364cd8c11d42feb556f9b863f0d034f9a383`
matches the briefing. The `plan:` line is deliberately omitted because this
is a `fail` and must not authorize the `PLANNING -> READY` flip.

## Premise verdict

**PARTIALLY SOUND** — mapped to gate verdict **`fail`** by severity.

The load-bearing core survives: Vault really has no OIDC provider stack of
F2's shape, the pinned provider really can express every resource named, and
the HTTPS issuer the resolved Q2 demands really is available. But six
distinct claims broke, and four of them change *what gets built*, not merely
how it is described: the plan cannot be handed to an implementer as written
without them building the wrong number of clients, skipping a prerequisite
its own evals require, and trusting a secret guardrail that does not exist.

## Load-bearing assumptions

### P1 — The Vault provider is declared as `~>5.3.0` with an empty `provider "vault" {}` — **HOLDS**

`deployments/infrastructure/providers.tf:7-10` pins `hashicorp/vault`
`~>5.3.0`; `providers.tf:28` is `provider "vault" {}`. Both anchors resolve
exactly as described.

### P2 — The lockfile resolves that to exactly `5.3.0` at `deployments/infrastructure/.terraform.lock.hcl` — **BREAKS**

The file is not in the repository and not on disk in this worktree.
`git ls-files` returns nothing for `.terraform.lock.hcl`;
`git check-ignore -v deployments/infrastructure/.terraform.lock.hcl` reports
`deployments/.gitignore:2`; commit `3e4d2ab` ("chore: ignore terraform
files") deleted the tracked copy. The plan cites this file twice — §4 and the
§6 restriction "Provider version is pinned to `5.3.0` (`.terraform.lock.hcl`)"
— and an implementer cannot open either.

The version claim itself is true only of the operator's own checkout
(`/home/vscode/workspace/deployments/infrastructure/.terraform.lock.hcl`
carries `version = "5.3.0"`, `constraints = "~> 5.3.0"`). Inside a ticket
worktree there is no lockfile and no `.terraform/`, so
`scripts/tf_validate.sh:16-18` takes the `init -backend=false` branch and
resolves `~>5.3.0` fresh from the registry. The stated pin is not enforced
where the gate actually runs.

### P3 — Every `vault_identity_oidc_*` resource and attribute F2 needs exists in provider `5.3.0` — **HOLDS**

Checked directly against the cached provider binary
`.../hashicorp/vault/5.3.0/linux_arm64/terraform-provider-vault_v5.3.0_x5`.
Present: `vault_identity_oidc_key`, `_scope`, `_client`, `_assignment`,
`_provider`, `_role`, `vault_identity_group`, `vault_identity_entity_alias`,
`vault_identity_group_alias`, and the attributes `issuer_host`,
`https_enabled`, `allowed_client_ids`, `scopes_supported`, `rotation_period`,
`verification_ttl`, `client_secret`, `redirect_uris`, `member_entity_ids`,
`assignments`, `entity_ids`, `group_ids`. The plan's caution to verify names
against `5.3.0` was warranted and the answer is clean.

### P4 — "The only Vault resources that exist today are a KV2 mount and secrets" — **BREAKS**

False as of now. `grep -n '^resource "vault_' deployments/infrastructure/*.tf`
returns, beyond the KV2 mount and secrets:

- `deployments/infrastructure/consul_deploy_role.tf:19` `vault_consul_secret_backend_role`
- `deployments/infrastructure/nomad_deploy_role.tf:36` `vault_nomad_secret_role`
- `deployments/infrastructure/acme.tf:41` `vault_policy.acme_tls_write`
- `deployments/infrastructure/acme.tf:66` `vault_jwt_auth_backend_role.acme`
- `deployments/infrastructure/backup.tf:34,50,65,81` four more `vault_kv_secret_v2`

Live Vault agrees: `vault secrets list` shows `nomad/` and `consul/` engines
mounted alongside `secret/`. This is the classic stale-premise signature: the
narrow sub-anchors the plan cites still resolve (`secrets.tf:2-7`,
`:10-29`, `:15-29`, `:47-66`, `:69-88` all land on exactly the blocks
described), while the surrounding "only" claim went false under F5/F6/T1.

The sub-clause "**No `vault_identity_*` / OIDC resources exist anywhere**"
does still hold: `grep -rn "vault_identity" --include=*.tf .` returns nothing.

### P5 — No human auth backend exists — **HOLDS**

Live: `vault auth list` returns only `jwt-nomad/` (type `jwt`) and `token/`.
No `userpass`, `oidc`, or `ldap`. The Ansible anchor
`bootstrap/roles/nomad_server/tasks/main.yml:198-255` resolves to the
"Check/Enable/Configure JWT auth method for Nomad" task block and the
`nomad-workloads` role creation, as described.

Refinement the plan gets slightly wrong: identity **entities do already
exist** in live Vault (`vault list identity/entity/name` returns 17
auto-created `entity_*` plus one named `Jasper Ginn`). The named human entity
has `"aliases": []`, so it cannot be logged into by any method — the plan's
conclusion (a human auth backend is a real prerequisite) survives, but "there
is no `vault_identity_entity`" is repo-true and live-false.

### P6 — Vault is reachable at `http://vault.lab.orangecluster.nl` — **BREAKS**

`curl http://vault.lab.orangecluster.nl/v1/sys/health` returns **301** to
`https://vault.lab.orangecluster.nl/...`. `haproxy.hcl:91-93` is now
`frontend http_in` / `bind *:80` / `http-request redirect scheme https code
301 unless { ssl_fc }`, and `:95-96` binds `*:443 ssl crt
/secrets/haproxy.pem`. The HTTPS path returns **200** behind a
publicly-trusted `CN = *.lab.orangecluster.nl` cert issued by Let's Encrypt
(`notAfter=Oct 24 05:31:42 2026 GMT`).

This is harmless for the resolved Q2 (which already flipped to
`https_enabled = true`), but §4's plain-HTTP reachability sentence and the
whole first paragraph of Q2 ("Vault runs plaintext HTTP behind haproxy on
port 80 … the issuer will therefore be `http://…` with `https_enabled =
false`") now describe a world that T3 destroyed.

The narrower listener claim **holds**:
`bootstrap/roles/vault_server/templates/vault.hcl.j2:7` is
`api_addr = "http://{{ vault_server_ip_address }}:8200"` and `:17-20` is the
`listener "tcp"` block with `tls_disable = true`. TLS terminates at haproxy
only.

### P7 — The haproxy anchors resolve — **BREAKS (five of six wrong)**

Every `services/haproxy.hcl` line reference in §4 and in the §7 "Reference
anchors the implementer will re-open" list points at the pre-F3 file. Current
content of the cited lines versus what the plan claims:

| Plan cites | Plan claims | Actually at that line | Real location |
|---|---|---|---|
| `:51` | MinIO console host ACL | a comment about certificate renewal | `:98` |
| `:53` | Vault host ACL | a comment about `change_mode = "restart"` | `:100` |
| `:64` | MinIO `use_backend` | `{{ with secret "${tls_secret}" }}` | `:109` |
| `:66` | Vault `use_backend` | `{{ .Data.data.private_key }}` | `:111` |
| `:84-85` | `backend minio` / `192.168.2.29:9001` | `timeout client 300s` / `timeout server` | `:127-128` |
| `:91` | `backend vault` / `192.168.2.30:8200` | `frontend http_in` | `:133-134` |

T3's own reflection names this failure mode exactly: *"a path substitution is
not a rename. The sentence around an anchor almost always asserts something
about what the anchor contains, and that assertion does not travel with the
path."* The hostnames in F2's prose were swept to `lab.orangecluster.nl`; the
line numbers were not.

### P8 — `just pre_commit` runs `terraform fmt` and offline `terraform validate` — **HOLDS**

`.pre-commit-config.yaml:22-27` is the `terraform-fmt` local hook running
`terraform fmt -check -recursive`; `:28-33` is `terraform-validate` running
`scripts/tf_validate.sh`. `scripts/tf_validate.sh:8-19` iterates the three
roots including `deployments/infrastructure`, uses `init -backend=false` only
when `.terraform` is absent, then `terraform validate`. `justfile:18-19` is
the `pre_commit` recipe (the plan cites `justfile:17-18`; 17 is the comment
line — trivially off by one). `terraform` v1.14.3 is on PATH.

One operational caveat: `deployments/infrastructure/vars/prod.tfvars` is
listed in §7's code surface but is gitignored (`.gitignore` "Keep
prod.tfvars local") and absent from this worktree (`vars/` holds only
`backend-config.hcl` and `prod.tfvars.example`). The `worktree_setup` recipe
at `justfile:30-32` exists to seed it; the plan never says to run it.

### P9 — `detect-private-key` guards against a committed `client_secret` — **BREAKS**

The hook's implementation
(`~/.cache/prek/repos/321271af841bb4e8/pre_commit_hooks/detect_private_key.py`)
matches a fixed `BLACKLIST` of PEM/PuTTY private-key headers only —
`BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY`, `BEGIN PGP PRIVATE KEY
BLOCK`, and seven siblings. An OIDC client secret is an opaque random string;
a live one on this cluster reads
`hvo_secret_NnrqxJp9DZXZs33VtbGQjqQc0K0TYE1le3eQtTu83IwlOLrjQ12Jr0xAwa6pfbHb`
(`vault read identity/oidc/client/test`). Nothing in that string is on the
blocklist.

The plan asserts this guard three times and it is false each time: §6
("`detect-private-key` runs in pre-commit"), §8 ("**No hardcoded secret may
appear in the diff** (`detect-private-key` fails the gate…)"), and §9
failure mode 4 ("mitigated by KV2 convention + `detect-private-key`"). It is
also the scorer for eval row 6.

### P10 — Relying parties (MinIO, oauth2-proxy) read the `groups` claim the scope emits — **BREAKS for MinIO**

§6 requires "a claim template that exposes the group/entity claim relying
parties (**MinIO**, oauth2-proxy) read", and Q5's resolution mandates one
canonical `groups` claim "read identically by all". M2's own live-verified
context contradicts the MinIO half:
`.loop/plans/M2-minio-poc-human-tiers.md:92-95` records that MinIO's
`identity_openid` exposes `claim_name` (default `policy`) **and**
`role_policy`, and identifies `role_policy` as "the per-tier binding M2 is
built on". In MinIO's role-policy mode the policy claim is not consulted at
all — tier gating comes from Vault refusing the *client* via its assignment,
not from a claim MinIO reads. M2 confirms this shape at `:113-114` and
`:241-246`.

The scope is still needed (oauth2-proxy L1/R1/R4, Grafana G1), so this does
not sink F2. But the plan states a false mechanism for its single largest
declared consumer, and Q5's "read identically by all RPs" constraint is not
satisfiable as written.

### P11 — The clients F2 must create are "oauth2-proxy + three MinIO tiers" — **BREAKS (four mutually inconsistent counts)**

The plan and its eval disagree four ways about the deliverable:

- §6 and §10.4: "oauth2-proxy (landing page, L1) and the MinIO console tiers"
  → **4 clients**.
- The cross-cutting addendum at the plan's foot (lines 397-402): "the
  oauth2-proxy architecture is **dedicated per service**, so F2 must provision
  one `vault_identity_oidc_client` PER fronted service — `dash` (L1),
  `mlflow` (R1), `phoenix` (R4) … in addition to the MinIO-tier clients" →
  **6 clients**.
- `.loop/evals/F2-foundation-vault-oidc-provider.md:3-9` DoD: "four tier
  clients + oauth2-proxy" → **5 clients**.
- Eval row 3 (`:21`): "`_client` (×4)" → **4 clients**.

R4 independently confirms the 6-client reading
(`.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:317-319`: "the cross-cutting
note fed back into F2, that F2 must provision …"), and L1 assumes its own
client exists in F2's output (`L1-landing-oauth2-proxy.md:222`). No
implementer can satisfy both §6 and the addendum, and no scorer can grade
row 3 against a plan that names a different number.

### P12 — F2 does not stand up the human auth backend — **BREAKS (contradicts its own resolved fork and its evals)**

§5 Non-goals: "**Not** standing up the human auth backend or enrolling real
human users (see Q1 — this may be a follow-up ticket once the backend is
chosen)."

The Resolved-forks section directly overturns this: "**Q1 → userpass in this
Terraform root.** Enable a `userpass` auth backend managed in this same root;
create `vault_identity_entity` per human + `vault_identity_entity_alias`, add
to groups via `member_entity_ids`." §10.7 still hedges ("conditional on Q1")
for a fork that was settled 2026-07-23, and the eval marker's Precondition
(`.loop/evals/F2-...md:11`) still reads "ticket §11 Q1, **open**".

This is not cosmetic. Eval rows 4 and 5 both require a *scratch entity that
can obtain a Vault token*, which requires an auth method with an alias. With
Q1 excluded by §5 those two rows are unsatisfiable; with Q1 included the
non-goal is wrong. The plan must pick one.

### P13 — The close-out evals are runnable with the harness credentials — **BREAKS for the auth-code rows**

Rows 1, 2 and the §8 evals 1-2 are fine: discovery is unauthenticated and
already serves. Verified live against the existing built-in provider:
`curl https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/default/.well-known/openid-configuration`
returns **200** with `issuer`, `jwks_uri`, `authorization_endpoint`,
`token_endpoint`, `userinfo_endpoint`; the advertised `.well-known/keys`
returns **200**.

§8 eval 3 and eval rows 4-5 do not survive. `vault token lookup` on the
harness token returns `{'entity_id': '', 'policies': ['root'], 'display_name':
'root'}` — the root token carries **no entity**, and Vault's authorize
endpoint resolves the requesting entity from the caller's token before
checking the client's assignment. The advertised `authorization_endpoint` is
also a **UI** path (`/ui/vault/identity/oidc/provider/default/authorize`), so
"authorize → code → token exchange" is a browser flow unless the implementer
uses the API authorize endpoint with a *non-root, entity-bearing* token that
does not currently exist anywhere on this cluster (P5, P12). The plan's
"Honest bound" paragraph acknowledges these are post-apply, but not that they
are un-runnable with the credentials the plan says the harness has.

### P14 — The eval rows are content-checking, not shape-checking — **BREAKS (two rows)**

Required attack-surface item 4, both instances found:

- **Row 3** (`:21`), scorer "deterministic check (`terraform state list`)",
  input `terraform -chdir=deployments/infrastructure state list | grep
  vault_identity`. A bare `grep` exits 0 on **one** match. A state containing
  only `vault_identity_oidc_key` scores 100% against an Expected column that
  demands a key, a scope, four clients, per-tier assignments, a provider and
  four groups.
- **Row 6** (`:24`), scorer "deterministic check (`just pre_commit` /
  `detect-private-key`)". Per P9 the hook cannot see a client secret, so the
  row passes unconditionally — including against an `oidc.tf` with a literal
  `client_secret` in it, which is precisely the content it claims to reject.

### P15 — Nothing already occupies `identity/oidc/` — **UNCERTAIN, leaning drift**

§4 says "What is missing: the entire OIDC identity provider stack". Live
Vault is not empty:

```
vault list identity/oidc/client      -> test
vault list identity/oidc/assignment  -> allow_all, test
vault list identity/oidc/provider    -> default
vault list identity/oidc/key         -> default
vault list identity/oidc/scope       -> (none)
vault list identity/group/name       -> (none)
```

`default` and `allow_all` are Vault built-ins. `test` is not: `vault read
identity/oidc/client/test` returns a real `client_id`/`client_secret` bound
to assignment `test`, and `vault read identity/oidc/assignment/test` binds
entity `24b0480b-…` = the `Jasper Ginn` entity. No `.tf` in the repo declares
it (P4's grep), so this is unmanaged out-of-band state of unknown origin — I
could not determine who created it, hence UNCERTAIN. It will not collide with
F2's named resources, but the plan asserts a greenfield that is not quite
green, and the built-in `default` provider carries `allowed_client_ids = [*]`,
which is worth a sentence in §9 given that section's own worry about
"over-broad `allowed_client_ids`".

### P16 — Wiring `allowed_client_ids` on the key is straightforward — **BREAKS (Terraform cycle)**

§10.4 instructs "wire `allowed_client_ids` on the key" while §7 has each
`vault_identity_oidc_client` reference `key`. Those two references form a
dependency cycle (`key -> client.client_id` and `client -> key.name`) and
`terraform validate`/`plan` will reject it. Provider 5.3.0 ships the intended
escape hatch — `vault_identity_oidc_key_allowed_client_id` is present in the
binary — and the plan names neither it nor the `["*"]` alternative.

### P17 — The dependency edge on T3 delivers what F2 needs — **HOLDS (but the Q2 rationale is stale)**

`depends_on = ["T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]`.
`.loop/ledger.json` has T3 `done` (and T1, T2 `done`), so the retarget from
F3 to T3 is sound and the HTTPS issuer F2 needs exists (P6).

The stale part is the reasoning: Q2's resolution still reads "**DEPENDENCY:
F2 is blocked on F3** … This requires TLS termination for
`vault.lab.orangecluster.nl` at haproxy, which is **F3's deliverable**.
**Build order becomes F1 → F3 → F2**". T3's plan is explicit that it
"Supersedes F3" and deleted F3's PKI apparatus, so the enabling deliverable is
T1+T3's, not F3's. And F1 is still `ready`, not `done`, in the ledger — the
stated build order would make F2 blocked, while its `depends_on` does not
list F1. F1 is in fact not needed here (its `jwt-nomad` deliverable is already
live via Ansible), so this is stale prose rather than a broken edge.

## Required attack surface — explicit findings

1. **Stale premise.** Found, four instances: P4 ("only a KV2 mount and
   secrets"), P6 (`http://vault.lab.orangecluster.nl` reachability and the
   whole first half of Q2), P7 (six haproxy anchors), P17 (Q2 attributing
   TLS to F3 and the "F1 → F3 → F2" order). All four are the anchors-resolve-
   but-prose-lies signature the dispatch warned about — with P7 the anchors
   do not even resolve.
2. **Inlined conclusion.** No instance found. F2 does not cite S3
   (`S3-spike-oidc-version-claims`, ledger `dropped: true`) nor inline its
   findings; Q5 correctly leaves the claim shape open with a recommendation
   rather than asserting a spike result. The one adjacent case is P10, where
   the plan asserts a MinIO mechanism that M2's own live evidence refutes —
   that is a wrong claim, not a borrowed conclusion.
3. **Broken dependency edge.** No instance found on the incoming edges (P17:
   T3 is `done` and does deliver the HTTPS issuer). The defect is on the
   *outgoing* side instead: P11, where F2's declared output (4 clients) cannot
   satisfy L1, R1 and R4, which the plan's own addendum says need dedicated
   clients from F2.
4. **Shape-check eval.** Found, two rows: eval rows 3 and 6 (P14).
5. **Unresolvable anchor.** Found: all six `services/haproxy.hcl` references
   (P7) and `deployments/infrastructure/.terraform.lock.hcl` (P2). Not
   findings: `providers.tf:7-10`, `:28`, `secrets.tf:2-7`, `:10-29`,
   `:15-29`, `:47-66`, `:69-88`, `variables.tf:1-20`,
   `.pre-commit-config.yaml:12`, `:22-27`, `:28-33`,
   `vault.hcl.j2:7`, `:17-20`,
   `bootstrap/roles/nomad_server/tasks/main.yml:198-255` — all verified to
   resolve to the content described.

## Most dangerous assumption

**P11 — that the client set is "oauth2-proxy + three MinIO tiers".** It is
the only broken assumption that determines *what artifact exists at the end*,
and F2 has more dependents than any other in-scope ticket. Four numbers (4,
5, 6, and 4-in-the-eval) are in circulation across the plan body, its own
addendum, and its eval. Build the §6 version and L1, R1, R4 and G1 all
inherit a missing client — a defect that surfaces only once each of those
tickets is halfway implemented. Build the addendum version and the eval scores
it wrong. No implementer can read this and be right.

Runner-up: **P12**, because it makes the ticket's own acceptance evals
unsatisfiable by its own non-goals.

## Required fixes

Each must land in the plan (and, where noted, the eval marker) before this
ticket leaves `PLANNING`.

1. **Settle the client count once.** Reconcile §6, §10.4, the cross-cutting
   addendum, the eval DoD prose and eval row 3 to a single enumerated list of
   named clients. If the addendum stands, that is `dash`, `mlflow`,
   `phoenix`, plus the three MinIO tier clients, and eval row 3's "×4" must
   change. (P11; `.loop/evals/F2-...md:3-9`, `:21`.)
2. **Resolve the §5 / Q1 contradiction.** Either delete the "Not standing up
   the human auth backend" non-goal (Q1 resolved to userpass *in this root*),
   or move eval rows 4-5 out of F2's DoD. Also update the eval marker's
   Precondition, which still calls Q1 "open", and §10.7, which still calls it
   "conditional". (P12; plan §5, §10.7, `.loop/evals/F2-...md:11-15`.)
3. **Re-anchor every `services/haproxy.hcl` reference**, reopening each site
   and rewriting the surrounding sentence rather than substituting the number:
   `:51 -> :98`, `:53 -> :100`, `:64 -> :109`, `:66 -> :111`,
   `:84-85 -> :127-128`, `:91 -> :133-134`. (P7.)
4. **Delete the `detect-private-key` guarantee** from §6, §8 and §9 failure
   mode 4, and replace eval row 6's scorer with one that can actually fail —
   for example a `grep -E` for `client_secret\s*=\s*"` in the `.tf` diff.
   State plainly that the guard is the KV2 convention plus review, since the
   hook only matches PEM headers. (P9, P14.)
5. **Make eval row 3 count, not grep.** `terraform state list | grep -c
   vault_identity` against the exact expected number, or an explicit
   per-resource assertion list. (P14.)
6. **State how eval rows 4-5 obtain an entity-bearing token.** The harness
   `$VAULT_TOKEN` is root with `entity_id: ""`, and the advertised
   `authorization_endpoint` is a UI path. Name the auth method, the scratch
   entity and its alias, or reclassify both rows as operator-manual. (P13.)
7. **Correct §4's "only a KV2 mount and secrets"** to account for
   `acme.tf:41,66`, `consul_deploy_role.tf:19`, `nomad_deploy_role.tf:36` and
   `backup.tf:34,50,65,81`. Keep the accurate part: no `vault_identity_*`
   exists. (P4.)
8. **Correct the HTTP/HTTPS prose.** §4's "Vault is reachable at
   `http://vault.lab.orangecluster.nl`" is a 301; Q2's first paragraph
   describes a plaintext edge that no longer exists. Keep the resolution
   (`https_enabled = true`) and rewrite the premise under it. (P6.)
9. **Replace the `.terraform.lock.hcl` citations.** The file is gitignored
   (`deployments/.gitignore:2`) and absent from any worktree. Cite
   `providers.tf:7-10` as the pin, and note that `scripts/tf_validate.sh`
   re-resolves `~>5.3.0` from the registry in a fresh worktree. (P2.)
10. **Fix §10.4's `allowed_client_ids` instruction.** As written it creates a
    Terraform cycle with §7's `client -> key` reference. Name
    `vault_identity_oidc_key_allowed_client_id` (present in 5.3.0) or
    `["*"]` as the intended shape. (P16.)
11. **Correct the MinIO claim mechanism.** §6 and Q5 assert MinIO reads the
    `groups` claim; M2 (`:92-95`, `:113-114`) shows tiering runs on
    `role_policy`, which bypasses the claim, with Vault's per-client
    assignment doing the gating. Scope the `groups` claim to the RPs that
    genuinely consume it and drop "read identically by all". (P10.)
12. **Record the pre-existing `identity/oidc/` drift.** A `test` client and
    `test` assignment bound to the `Jasper Ginn` entity exist in live Vault
    and are not Terraform-managed; the built-in `default` provider carries
    `allowed_client_ids = [*]`. §4's "the entire OIDC identity provider
    stack" is missing overstates a greenfield. (P15.)
13. **Refresh Q2's dependency prose.** TLS termination for
    `vault.lab.orangecluster.nl` is T1+T3's deliverable; T3 supersedes F3 and
    deleted its PKI. Drop the "F2 is blocked on F3" and "F1 → F3 → F2"
    sentences, which no longer describe the ledger (F3, T1, T2, T3 all
    `done`; F1 still `ready` and not required here). (P17.)

## Method note

All cluster interaction was read-only: `vault status`, `vault auth list`,
`vault secrets list`, `vault list identity/oidc/{key,scope,client,assignment,provider}`,
`vault list identity/{group,entity}/name`, `vault read` on the `test` client,
the `test` assignment, the `default` provider and the `Jasper Ginn` entity,
`vault token lookup`, `nomad job status -short haproxy`, and `curl`/
`openssl s_client` against the edge. No `write`, `delete`, `patch`, `job run`,
`terraform apply`, or mutating git command was issued. The provider schema was
read from the operator's already-downloaded binary with `strings`; no
`terraform init` was run, so no `.terraform/` was created in this worktree.
The only file written is this verdict.
