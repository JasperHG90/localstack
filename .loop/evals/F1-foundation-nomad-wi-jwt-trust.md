eval: F1-foundation-nomad-wi-jwt-trust

**Definition of Done:** The Nomad Workload Identity to Vault JWT trust chain is
documented in `docs/workload-identity.md` — JWKS URL, `jwt-nomad` backend, the
`nomad-workloads` role and **the shared policy's real scope, including its
`bootstrap/data/*` write grant**, the fixed-claims constraint, the
Ansible/Terraform ownership split, the one-token-per-task rule, and the
audience convention — and a scratch Nomad job proves keyless Vault KV reads on
the live cluster while the existing `vault.io` audience is left intact so every
running workload keeps authenticating.

*Rows 3, 6 and 8 corrected 2026-07-25. Row 6 previously asserted the policy
"scopes reads to the caller's own `nomad_job_id` path" — a green check
licensing a false conclusion, since the shared policy also grants
`bootstrap/data/*` read/create/update and cluster-wide `secret/metadata/*`
list to every workload. Row 3 previously required capturing a WI JWT that is
never written to disk under the plan's original identity stanza.*

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Operator can discover the JWKS endpoint M1 will point MinIO at | `curl -s "$NOMAD_ADDR/.well-known/jwks.json" \| jq '.keys \| length'` | Prints an integer >= 1; the same URL is cited in `docs/workload-identity.md` | deterministic check (`curl $NOMAD_ADDR/.well-known/jwks.json` + `jq '.keys \| length'`) | 100% |
| The doc is honest about what F1 delivers for M1 — JWKS, not OIDC discovery | `curl -s "$NOMAD_ADDR/.well-known/openid-configuration"`; then read the doc | The endpoint returns `OIDC Discovery endpoint disabled`, and the doc states plainly either that Q7 was resolved to enable it here (in which case the endpoint returns a discovery document instead) or that M1 owns enabling it. A doc that promises MinIO a `config_url` this cluster does not serve is a FAIL | deterministic check (endpoint response matches the doc's claim) | 100% |
| Operator confirms Vault trusts the Nomad `nomad-workloads` role on the expected audience | `vault read -format=json auth/jwt-nomad/role/nomad-workloads` | Exit 0; `.data.bound_audiences` contains `vault.io` and `.data.token_policies` contains `nomad-workloads` | deterministic check (`vault read auth/jwt-nomad/role/nomad-workloads`) | 100% |
| A workload authenticates to Vault with its WI JWT and reads its own scoped secret keylessly | Deploy `tests/wi-vault-probe.nomad.hcl` (carrying `identity { name = "vault_default" aud = ["vault.io"] file = true }`), read the rendered JWT from the alloc at `secrets/nomad_vault_default.jwt`, then `vault write -format=json auth/jwt-nomad/login role=nomad-workloads jwt=<wi-jwt>` | The JWT file EXISTS in the alloc (it does not under an unnamed `identity` block — that is the point of the `name`); login exits 0 and returns a client token whose `token_policies` include `nomad-workloads`; the job renders `secret/data/default/wi-test/probe` non-empty | deterministic check (`nomad alloc fs` for the JWT, then `vault write auth/jwt-nomad/login`) | 100% |
| Reader understands the trust config, the ownership split, and the audience convention without reverse-engineering Ansible | Read `docs/workload-identity.md` | Thesis-first, cites real paths/URLs, and covers: the JWKS URL; the `jwt-nomad` backend; the shared role/policy; the fixed-claims constraint; `secret/data/<namespace>/<job_id>/<entry>`; the Ansible-root-of-trust vs Terraform-per-job-role split with `acme.tf:41-90` as the worked example; the `vault { role = }` selection mechanism; the rule that a dedicated role REPLACES `nomad-workloads` so a job needing both must list both policies; and one audience per verifying service (never per job) | model + rubric (adversarial review agent) | 4/5 |
| Fixed-claims constraint holds: no custom claims are relied on | `vault read -format=json auth/jwt-nomad/role/nomad-workloads \| jq '.data.claim_mappings'` | Maps exactly `nomad_namespace`, `nomad_job_id`, `nomad_task` and no others; policy scoping keys only on those | deterministic check (`vault read auth/jwt-nomad/role/nomad-workloads`, claim_mappings assertion) | 100% |
| Another job's secret prefix is denied to a valid WI token | Using the client token minted above, `VAULT_TOKEN=<wi-token> vault kv get -mount=secret default/other-job/probe` | HTTP 403 / permission denied. **Asserts only that a different job's `secret/data/` prefix is denied — NOT that the token is job-scoped generally** | deterministic check (`vault kv get default/other-job/probe` returns 403) | 100% |
| The doc records the real blast radius: the shared policy is NOT job-scoped | Using the same WI token, `VAULT_TOKEN=<wi-token> vault kv get -mount=bootstrap github`; then read the doc's threat-model section | The read **succeeds**, demonstrating every workload can read (and per the policy, overwrite) the bootstrap credentials — GitHub PAT and Tailscale auth key. The doc states this explicitly rather than describing the policy as per-job scoped. A doc claiming job-scoping while this read succeeds is a FAIL | deterministic check (`vault kv get -mount=bootstrap github` succeeds AND the doc documents it) | 100% |
| Existing `vault.io` audience is not renamed, so live workloads keep working | `vault read -format=json auth/jwt-nomad/role/nomad-workloads \| jq -c '.data.bound_audiences'`; confirm an existing workload (e.g. memex) still reads its secret | `bound_audiences` still equals `["vault.io"]`; `default_identity { aud = ["vault.io"] }` in `nomad.hcl.j2` untouched | deterministic check (`vault read auth/jwt-nomad/role/nomad-workloads`, bound_audiences unchanged) | 100% |
