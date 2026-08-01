eval: F2-foundation-vault-oidc-provider

**Rewritten 2026-07-30** alongside the plan, against the thirteen required
fixes in `.loop/verdicts/F2-foundation-vault-oidc-provider.plan-validator.md`
and two operator decisions. The previous marker scored a scope F2 no longer
has: four tier clients plus oauth2-proxy, four identity groups, and a
`detect-private-key` guardrail that cannot fail on a Vault client secret.

**Definition of Done:** the singleton half of Vault's OIDC stack — signing
key, scope, provider, a `userpass` human auth backend with the operator's
entity and alias, and ONE throwaway smoke-test client with its group and
assignment — is defined in Terraform under `deployments/infrastructure/`,
applies cleanly, and serves an issuer at
`https://vault.lab.orangecluster.nl` whose discovery and JWKS endpoints are
reachable and against which a real human login completes end to end. No
consumer client is created here. No client secret appears in the diff.

**Scope note:** clients for `dash` (L1), `mlflow` (R1), `phoenix` (R4) and the
MinIO tiers (M2) are each created by their own ticket, together with that
ticket's group, assignment, and `vault_identity_oidc_key_allowed_client_id`
entry. A row here asserting those clients exist would fail F2 for work it was
deliberately not given.

**The trap this marker guards:** rows 6 and 7 exist because the previous
marker's secret guardrail named `detect-private-key`, which matches a fixed
blocklist of PEM headers and cannot match `hvo_secret_…`. It was a green check
asserting something false. Row 4 exists because the harness `$VAULT_TOKEN` is
root with `entity_id: ""`, so it cannot exercise an entity-gated assignment at
all, and the previous marker never said how a real one would be obtained.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The issuer advertises a discovery document over HTTPS | `curl -sf "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \| jq -e '.issuer and .jwks_uri'` | exit 0; `.issuer` is non-null AND starts `https://vault.lab.orangecluster.nl`. The scheme is load-bearing: resolved Q2 requires HTTPS, and an issuer baked into tokens is expensive to change later | deterministic check (`curl` + `jq -e` on issuer prefix) | 100% |
| The advertised JWKS is reachable and holds a signing key | `JWKS=$(curl -sf "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \| jq -r '.jwks_uri'); curl -sf "$JWKS" \| jq -e '.keys \| length > 0'` | exit 0; `keys` non-empty | deterministic check (`curl <jwks_uri>` + `jq -e`) | 100% |
| **The resource graph is COUNTED, not grepped** | `terraform -chdir=deployments/infrastructure state list \| grep -c '^vault_identity'` and the full listing | The count equals the number enumerated in the plan's §7, and the listing contains exactly: one `vault_identity_oidc_key`, one `_scope`, one `_provider`, one `_client`, one `_assignment`, one `_key_allowed_client_id`, one `vault_identity_group`, one `vault_identity_entity`, one `vault_identity_entity_alias`. A `grep` for presence passes against a half-built stack; a count does not | deterministic check (exact count and per-resource listing) | 100% |
| **A real human login yields an entity-bearing token** | `vault login -method=userpass username=<operator>` with the generated password read from KV2; then `vault token lookup -format=json \| jq -e '.data.entity_id != ""'` | Login succeeds and the token's `entity_id` is NON-EMPTY. This is the row the previous marker could not satisfy: the harness root token has `entity_id: ""`, so nothing entity-gated could ever be exercised | deterministic check (`vault login` + non-empty `entity_id`) | 100% |
| The authorization-code flow completes and carries the group claim | Using the entity-bearing token from row 4, drive `/v1/identity/oidc/provider/<provider>/authorize` with **`scope=openid groups`** (space-delimited; `openid` alone returns a token with NO groups claim however correct the template) and a `redirect_uri` matching the smoke-test client, then exchange the code at the token endpoint | A signed `id_token` is returned whose `groups` claim contains the smoke-test client's assigned group name, and that claim is an ARRAY, not a string. Decode the payload; do not treat a returned token as evidence, since Vault drops a malformed claim silently and still signs. Note the advertised `authorization_endpoint` is a UI path, so the API endpoint is the one to drive | model + rubric (adversarial review agent) | 4/5 |
| An entity outside the assignment is denied (guardrail) | A second scratch entity NOT in the smoke-test client's assignment group attempts the same flow | Authorization is DENIED; no `id_token` is issued. Without this, row 5 passing proves only that login works, not that assignment gates anything | deterministic check (authorize returns access-denied, not a token) | 100% |
| **Guardrail: no client secret in the diff, checked by a scorer that can fail** | `git diff <base>..HEAD -- '*.tf' '*.tfvars'` piped to `grep -nE -e 'client_secret[[:space:]]*=[[:space:]]*"' -e 'hvo_secret_'` | No match. **Do NOT score this with `detect-private-key`**: that hook matches a fixed blocklist of PEM headers only and passes against a literal Vault client secret, which is exactly the false-green the previous marker shipped **Pattern corrected 2026-07-31: the alternation was escaped (`\|`), which `grep -E` reads as a LITERAL pipe, so the whole guardrail searched for the string `client_secret = "|hvo_secret_` and could never match.** Verified vacuous against a file containing both leak shapes. This is the same false-green class the row was written to prevent. | deterministic check (pattern match over the diff, expected empty) | 100% |
| **Guardrail: no consumer client is created here** | `terraform -chdir=deployments/infrastructure state list \| grep vault_identity_oidc_client` | Exactly one client, and its name is the smoke-test client. No `dash`, `mlflow`, `phoenix`, or MinIO-tier client. Those belong to L1, R1, R4 and M2 per the 2026-07-30 operator decision; creating them here re-centralizes what was deliberately pushed out | deterministic check (exactly one client, named as the smoke test) | 100% |
| **Guardrail: client registration does not edit the key resource** | Read `oidc.tf` | Client ids are registered via `vault_identity_oidc_key_allowed_client_id` (verified present in pinned 5.3.0), NOT via an inline `allowed_client_ids` list on `vault_identity_oidc_key`. The inline form creates a Terraform cycle with the client's `key` reference and forces every consumer ticket to edit F2's file | deterministic check (standalone resource used; no inline `allowed_client_ids`) | 100% |
| The plan is well-formed offline before it reaches Vault | `just worktree_setup <path>`, then `just pre_commit` | Gate green. Every `vault_identity_oidc_*` and `vault_auth_backend` attribute resolves against the pinned `~>5.3.0` schema (`providers.tf:7-10`). The worktree step is required first or `terraform-validate` dies on the gitignored `.ssh/id_rsa` read at `services.tf:290` | deterministic check (`just pre_commit` green) | 100% |
| The drifting `test` client is resolved, not ignored | Read the ticket's close-out notes and `vault list identity/oidc/client` after apply | Plan Q7 is answered explicitly by the operator and the answer is carried out: either `test` and its assignment are deleted, or they are imported into Terraform with the exposed secret rotated. Leaving unmanaged drift beside a freshly managed stack is how the next audit finds a false greenfield claim | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: jasperginn 2026-07-30
