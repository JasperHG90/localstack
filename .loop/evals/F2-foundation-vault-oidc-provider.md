eval: F2-foundation-vault-oidc-provider

Definition of Done: Vault's OIDC identity provider stack (key, scope,
four tier clients + oauth2-proxy, per-tier assignments, provider, and the
four identity groups) is defined in Terraform under
`deployments/infrastructure/oidc.tf`, applies cleanly, and serves one
shared issuer whose discovery + JWKS endpoints are reachable and whose
group claim gates each client on its assigned identity group. Client
secrets land in Vault KV2, never in the diff.

Precondition (ticket §11 Q1, open): no human auth backend exists yet, so
identity groups may have empty membership at apply time. The auth-code
flow row (row 4) exercises a scratch entity added to the client's
assignment group solely for the test; it does not depend on the human
enrollment fork being settled.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The shared issuer advertises a discovery document | `curl -sf -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \| jq -e '.issuer and .jwks_uri'` | exit 0; non-null `issuer` and `jwks_uri` returned | deterministic check (`curl` discovery endpoint + `jq -e`) | 100% |
| The advertised JWKS is reachable and holds a signing key | `JWKS=$(curl -sf -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/identity/oidc/provider/<provider>/.well-known/openid-configuration" \| jq -r '.jwks_uri'); curl -sf "$JWKS" \| jq -e '.keys \| length > 0'` | exit 0; `keys` array non-empty | deterministic check (`curl <jwks_uri>` + `jq -e`) | 100% |
| The full OIDC resource graph exists after apply | `terraform -chdir=deployments/infrastructure state list \| grep vault_identity` | lists `vault_identity_oidc_key`, `_scope`, `_client` (×4), `_assignment` (per tier), `_provider`, and the four `vault_identity_group` resources | deterministic check (`terraform state list`) | 100% |
| A scratch auth-code flow yields an id_token carrying the right group claim | scratch entity added to `<client>`'s assignment group; run authorize to code to token exchange against `<provider>`/`<client>` | a signed id_token is returned whose `groups` claim (per Q5) contains the client's assigned group name | model + rubric (adversarial review agent) | 4/5 |
| An entity outside a tier's assignment group is denied that client (guardrail) | scratch entity NOT in `<client>`'s assignment group attempts the auth-code flow against `<client>` | authorization is DENIED; no id_token issued for that client | deterministic check (auth-code request returns access-denied, not a token) | 100% |
| No client secret appears in the committed diff (guardrail) | `just pre_commit` over the staged `.tf` change; `git diff` of `oidc.tf` / `secrets.tf` | `detect-private-key` passes; every `client_secret` is written via `vault_kv_secret_v2` to `vault_mount.kvv2.path`, never as a literal in `.tf` | deterministic check (`just pre_commit` / `detect-private-key`) | 100% |
| The plan is well-formed offline before it reaches Vault | `just pre_commit` (runs `terraform fmt -check -recursive` + offline `terraform validate` via `scripts/tf_validate.sh`) | gate green; every `vault_identity_oidc_*` attribute resolves against the pinned provider `5.3.0` schema | deterministic check (`terraform validate` / `just pre_commit`) | 100% |
