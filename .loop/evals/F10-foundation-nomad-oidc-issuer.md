eval: F10-foundation-nomad-oidc-issuer

**Definition of Done:** `server { oidc_issuer = "https://nomad.lab.orangecluster.nl" }`
is set in `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` from an Ansible
variable, the bootstrap run has applied it and restarted the Nomad server, and
`/.well-known/openid-configuration` serves a discovery document whose `issuer`
matches exactly and whose advertised `jwks_uri` is fetchable **from a client,
not just from the server**. Every existing Vault workload login still works.

**The defect this exists to catch.** M1 and R1 will compare the `iss` claim on a
token against the discovery document's `issuer`, literally. A value that
resolves on the Nomad host but not from MinIO's node, or a `jwks_uri` Nomad
derives from the request host rather than from `oidc_issuer`, produces a
discovery document that looks correct here and fails opaquely in the consumer.
Rows 3 and 4 are the whole point of the ticket; row 1 alone would pass against
a document no client can use.

**Before/after asymmetry.** Today `curl $NOMAD_ADDR/.well-known/openid-configuration`
returns `OIDC Discovery endpoint disabled` and `GET /v1/agent/self` reports
`Server.OIDCIssuer: ''`. Both are the pre-state to contrast against.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The discovery endpoint serves a document | `curl -sf https://nomad.lab.orangecluster.nl/.well-known/openid-configuration \| jq -e '.issuer and .jwks_uri'` | exit 0, both fields non-null. Before this ticket the same command returns `OIDC Discovery endpoint disabled` | deterministic check (`curl` + `jq -e`) | 100% |
| **The advertised issuer matches the configured value exactly** | `jq -r '.issuer'` from row 1, compared to the value set in `nomad.hcl.j2`, and to `GET /v1/agent/self \| .config.Server.OIDCIssuer` | All three are byte-identical, including scheme and absence of a trailing slash. MinIO compares `iss` literally; a trailing-slash mismatch fails validation with an opaque error in M1, not here | deterministic check (three-way exact string match) | 100% |
| **The advertised `jwks_uri` is on the SAME host and is fetchable** | `JWKS=$(curl -sf https://nomad.lab.orangecluster.nl/.well-known/openid-configuration \| jq -r '.jwks_uri'); echo "$JWKS"; curl -sf "$JWKS" \| jq -e '.keys \| length > 0'` | `$JWKS` starts with the configured issuer host, NOT `127.0.0.1` or `192.168.2.30`, and fetching it returns a non-empty `keys` array. If Nomad derives `jwks_uri` from the request rather than from `oidc_issuer`, a consumer reaching the edge is handed an unreachable internal URL and this row fails | deterministic check (host matches issuer; keys non-empty) | 100% |
| **A client that is not the Nomad host can fetch both** | From a machine other than 192.168.2.30 — the MinIO node (192.168.2.29) is the one that matters — fetch the discovery document and the advertised `jwks_uri` | Both succeed. "It works from the server" is not the property M1 needs; M1's MinIO must fetch `config_url` from where MinIO runs | deterministic check (both fetch from a non-server host) | 100% |
| **No existing Vault workload login regressed** | After the restart, for at least `haproxy`, `memex` and `grafana`: `nomad job status <job>` plus confirmation each rendered its Vault template | All allocations running, no template-render error, none stuck `pending`. `haproxy` is the sharp one: it renders the edge TLS PEM from Vault, so a broken WI login there drops every routed service | deterministic check (jobs healthy, templates rendered) | 100% |
| **The `iss` change did not break Vault's JWT trust** | `vault read auth/jwt-nomad/config`; then confirm a freshly minted WI token still authenticates | `bound_issuer` is still `""` and `jwks_url` unchanged, and a workload logging in after the restart succeeds. Verified live pre-change: `bound_issuer: ""`, so Vault does not validate `iss` — this row proves that reasoning against reality rather than trusting it | deterministic check (config unchanged, fresh login succeeds) | 100% |
| **Checked late, not just immediately** | Re-run the row 5 sweep at least 10 minutes after the restart | Still clean. A Vault template that cannot authenticate blocks and retries silently rather than failing fast, so an immediate check can pass against a job that will never render | deterministic check (clean sweep at T+10min) | 100% |
| The Nomad control plane came back | `nomad server members`; `nomad node status` | One member, `alive`, **leader** re-elected; every client node `ready`. `bootstrap_expect = 1` means there is no second server to hold the cluster during the restart, so this confirms the outage ended | deterministic check (leader elected, nodes ready) | 100% |
| **Guardrail: the change is a variable, not a literal** | `git diff -- bootstrap/roles/nomad_server/templates/nomad.hcl.j2` and the defaults or group-vars file | `oidc_issuer` renders from an Ansible variable following the same convention the file already uses for `nomad_server_ip_address`. A hardcoded hostname in the template is the thing that makes the next environment a copy-paste edit | deterministic check (variable used; default declared once) | 100% |
| **Guardrail: nothing else in the Nomad config moved** | Same diff | The `default_identity` block (`aud = ["vault.io"]`, `ttl = "1h"`), the `vault` stanza, `bootstrap_expect`, and the telemetry block are untouched. This ticket adds one key; bundling an audience or TTL change here would alter every workload token at the same moment as the restart | deterministic check (only the oidc_issuer line added) | 100% |
| **Guardrail: Vault's jwt-nomad auth was NOT switched to discovery** | `vault read auth/jwt-nomad/config` | Still trusts via `jwks_url`, with `oidc_discovery_url` empty. Plan Q2 recommends leaving it: JWKS trust works, and swapping a working trust path for tidiness risks locking every workload out of Vault for no functional gain | deterministic check (`jwks_url` still set, `oidc_discovery_url` empty) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed. This change touches a `.j2` template and YAML, so `check-yaml` and `end-of-file-fixer` are the hooks that bite; `nomad-fmt` and `terraform-*` skip | deterministic check (`just pre_commit` green) | 100% |
| F1's Q7 and M1's dependency question are closed, not left dangling | Read `.loop/plans/F1-foundation-nomad-wi-jwt-trust.md` Q7 and M1's dependency note after this ticket | Both point at F10 as the owner of `oidc_issuer` rather than at each other. F1 currently marks the template read-only and M1 blocks on F1 delivering a URL F1 never delivers; if that loop survives, this ticket fixed the cluster and not the deadlock | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: PENDING
