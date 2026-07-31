eval: G2-nomad-ui-oidc-login

**Forks resolved 2026-07-31.** Q1 the `developer` policy is **imported**
into Terraform, not replaced or referenced. Q2 `token_locality = "global"` and
`max_token_ttl = 8h`. Q3 a dedicated `nomad-developers` Vault group. Q4 the
callback paths get verified against the running UI before they are written
into the Vault client.

**Definition of Done:** Nomad is a registered OIDC client of Vault's `lab`
provider, and a developer who is a member of the bound Vault group can sign
in to the Nomad web UI at `https://nomad.lab.orangecluster.nl` and to
`nomad login` from a terminal, receiving in both cases an ACL token that
carries the `developer` policy and nothing more. A developer outside that
group is refused. The `developer` Nomad policy is consumed by name and this
ticket authors no copy of it.

**The trap this marker guards.** F2 shipped a defect of exactly this shape and
caught it only because a gate decoded the token: Vault drops a `groups` claim
it cannot render and **still signs and returns the token**. Nothing errors.
The relying party then sees a valid login with no groups, the binding rule
matches nothing, and the user gets a token with no policy. Rows 2 and 3 exist
because a row that merely asserts "a token came back" passes against that
defect. Row 4 exists because rows 2 and 3 passing prove only that login works,
not that the assignment gates anything.

**Second trap: the wrong provider works.** Vault's built-in `default` provider
advertises `allowed_client_ids = ["*"]`. An auth method pointed at it
completes a login successfully, over plaintext HTTP against a raw IP, while
bypassing every scoping decision F2 made. Row 6 is a positive check on the
issuer for that reason; a login succeeding is not evidence it was scoped.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The auth method exists and is type OIDC | `nomad acl auth-method list` and `nomad acl auth-method info <name>` | Exactly one OIDC auth method. Before this ticket the cluster has **none** (verified 2026-07-31), so its presence is attributable to this change | deterministic check (exactly one OIDC auth method present) | 100% |
| **A real UI login yields a token carrying `developer`** | Complete the browser flow at `https://nomad.lab.orangecluster.nl` as a member of the bound group, then `nomad acl token self` with the issued token | Login completes AND the token's `Policies` list contains `developer` and is NOT empty. **An empty policy list is the signature of the dropped-claim defect and must fail this row**, even though the login itself succeeded and a token was issued | deterministic check (token issued; `Policies` contains `developer`; list non-empty) | 100% |
| **The `groups` claim actually arrives, decoded not assumed** | Obtain the `id_token` Vault issues to this client with `scope=openid groups`, decode its payload, and separately read `oidc_scopes` off the auth method | The decoded payload has a `groups` claim that is a JSON **array** containing the bound group name, AND `oidc_scopes` on the auth method includes `groups`. Both halves are required: the config check alone cannot see a template that renders wrong, and a token alone cannot show the scope was requested rather than defaulted | deterministic check (payload `groups` is a non-empty array containing the bound group; `oidc_scopes` includes `groups`) | 100% |
| **A non-member is denied (guardrail)** | A scratch Vault entity NOT in the bound group attempts the same UI login. Delete it afterwards | Authorization is REFUSED and no Nomad ACL token is issued. The control must be shown to discriminate: the scratch entity must **first log in to Vault successfully and carry a non-empty `entity_id`**, so the refusal is attributable to the assignment rather than to a broken login | deterministic check (Vault login succeeds with non-empty entity_id; Nomad authorization refused; no token) | 100% |
| `nomad login` works from a terminal | `nomad login -method=<name>` on a machine with a browser, using the default callback `localhost:4649` | A token is returned carrying `developer`. This is a separate row from the UI because it exercises the **second** redirect URI: omitting `http://localhost:4649/oidc/callback` from either `allowed_redirect_uris` or the Vault client's `redirect_uris` breaks CLI login while leaving the UI working, so a UI-only check reports green on a half-broken ticket | deterministic check (`nomad login` returns a token carrying `developer`) | 100% |
| **The auth method points at `lab`, not Vault's `default` provider** | Read `oidc_discovery_url` and `bound_issuer` off the auth method | Both resolve to `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`. HTTPS and the `lab` path are both load-bearing. A method aimed at `default` logs in successfully while bypassing the provider's `allowed_client_ids`, so this cannot be inferred from a working login | deterministic check (discovery URL and bound issuer both the `lab` HTTPS issuer) | 100% |
| PKCE is enabled | Read `oidc_enable_pkce` off the auth method | `true`. Required from Nomad 1.10 per HashiCorp's Vault-to-Nomad guide; the cluster runs 2.0.4 | deterministic check (`oidc_enable_pkce == true`) | 100% |
| The client is registered in both places Vault requires | `terraform state list` plus `vault read identity/oidc/provider/lab` | A `vault_identity_oidc_key_allowed_client_id` exists for the Nomad client AND the client id appears in the `lab` provider's `allowed_client_ids`. These are two separate registrations and omitting the provider one makes Vault refuse the authorization request. Also assert the key resource carries **no inline** `allowed_client_ids` | deterministic check (standalone key registration present; client id in provider list; no inline attribute on the key) | 100% |
| **Guardrail: no client secret in the diff, scored by something that can fail** | `git diff <base>..HEAD -- '*.tf' '*.tfvars'` piped to `grep -nE 'client_secret[[:space:]]*=[[:space:]]*"\|hvo_secret_'` | No match. **Do NOT score this with `detect-private-key`**: it matches a fixed blocklist of PEM headers and passes against a literal Vault client secret. F2's marker records that exact false green | deterministic check (pattern match over the diff, expected empty) | 100% |
| **The `developer` policy is consumed, never re-authored** | `grep -rn 'developer' deployments/**/*.tf`, `terraform state list | grep nomad_acl_policy`, and `nomad acl policy list` | **No `nomad_acl_policy` resource named `developer` in the diff or in Terraform state**, and exactly one `developer` policy live. **Corrected 2026-07-31: Ansible owns this policy** (`bootstrap/roles/nomad_server/tasks/main.yml:182-184`, source at `files/nomad_developer_policy.hcl`); an earlier version of this row accepted an import, which would give one policy two owners. The next `just bootstrap` re-applies Ansible's copy, Terraform then reports drift, and they fight forever. The binding rule references it by name | deterministic check (no Terraform-managed `developer` policy; exactly one live) | 100% |
| **Guardrail: existing access is unbroken** | After apply: `vault read nomad/creds/deploy` then `nomad acl token self` with it; and `nomad acl auth-method list` for the workload path | The brokered `deploy` token still mints and still reports `Type = client`, `Policies = [deploy]`. The `jwt-nomad` Vault mount that workloads use is untouched. This ticket is additive; a regression here means it changed the machine paths while aiming at the human one | deterministic check (deploy token mints and is unchanged; jwt-nomad mount untouched) | 100% |
| The `developer` grant is stated, not stumbled into | Read the ticket's close-out notes | The notes state plainly that members of the bound Vault group receive `alloc-exec` and `alloc-node-exec`, which is shell access inside running allocations and on the node. Q1 and the §Risk note flag this; the close-out must confirm the operator accepted it rather than inheriting it silently from a pre-existing policy | model + rubric (adversarial review agent) | 4/5 |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. This change is Terraform, so `terraform fmt -check` and `terraform validate` per root are what bite | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
