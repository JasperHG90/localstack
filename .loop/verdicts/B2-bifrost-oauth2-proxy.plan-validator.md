---
verdict: pass
plan: c30e3a5e0fc66584acd6eaa259a9423b62111b5917e39464b3231e8a5fa85260
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: 58b0d0a3ce92310e648446257eb00878a1aa2e667c5cd25514f0c9de59eb2ddb
citations: deployments/applications/services/bifrost.hcl:13 = `        static = 8080`
  deployments/applications/services/bifrost.hcl:101 = `    "enforce_auth_on_inference": true`
  deployments/applications/services/bifrost.hcl:105 = `      "is_enabled": true,`
  deployments/applications/services.tf:507 = `      bifrost_host     = "192.168.2.50"`
  deployments/applications/services.tf:553 = `    endpoint = "http://192.168.2.50:8080"`
  deployments/applications/providers.tf:67 = `  endpoint = null_resource.bifrost_ready.triggers["endpoint"]`
  deployments/applications/services/hermes.hcl:158 = `    base_url="http://127.0.0.1:8080/v1",`
  deployments/applications/services/memex.hcl:168 = `MEMEX_SERVER__DEFAULT_MODEL__BASE_URL=http://${bifrost_host}:8080/v1`
  deployments/infrastructure/services/prometheus.hcl:135 = `              - targets: ["192.168.2.50:8080"]`
  deployments/infrastructure/services/haproxy.hcl:176 = `    server bifrost1 192.168.2.50:8080 check`
  deployments/infrastructure/services/haproxy.hcl:179 = `    server dash1 192.168.2.50:4180 check`
  deployments/infrastructure/services/oauth2-proxy.hcl:95 = `        image        = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"`
  deployments/infrastructure/services.tf:340 = `      rules    = ["allow from 192.168.2.30 to any port 4180 proto tcp"]`
  deployments/infrastructure/oidc.tf:100 = `  oidc_provider_client_ids = [`
  deployments/infrastructure/oidc.tf:118 = `  name               = "lab"`
  deployments/infrastructure/oidc.tf:200 = `  assignments      = ["allow_all"]`
  deployments/infrastructure/secrets.tf:212 = `  name  = "default/oauth2-proxy/oidc"`
  deployments/infrastructure/secrets.tf:233 = `  special = false`
  bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1 = `path "secret/data/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_namespace{{ '}}' }}/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_job_id{{ '}}' }}/*" {`
  justfile:19 = `    pre-commit run --all-files`
  cli/tests/fixtures/haproxy_cfg.py:40 = `    acl is_bifrost    hdr(host) -i bifrost.lab.example`
---

# Plan review: B2-bifrost-oauth2-proxy (plan-validator)

Deterministic floor: `loopctl verify-plan B2-bifrost-oauth2-proxy` returned
`valid`. Plan file sha256 matches the briefed fingerprint
(`c30e3a5e...5260`); the snapshot at
`.loop/verdicts/B2-bifrost-oauth2-proxy.plan-validator.snapshot.md` hashes
identically, so the reviewed bytes are the bound bytes. No prior verdict
cycle exists for this slug, so there were no settled findings to re-attack.

Note: `skills/reviewer-brief/SKILL.md` and `skills/create-ticket/SKILL.md`
are absent from this checkout; I honored the bounds as briefed (5-minute
wall clock per invocation, scratch under `.loop/scratch/<slug>.<pass-id>/`)
and checked contract hygiene against the harness's established plan shape.

## Premise verdict

**SOUND.**

Operator decisions 1-3 in §3 (per-app proxy; skip-auth exactly `/v1/*` and
`/anthropic/*`; native admin auth stays on) were treated as settled, not
relitigated.

## Per-assumption findings

- **P1 — HOLDS.** `deployments/applications/services/bifrost.hcl:13`
  > static = 8080
  and `:41`
  > network_mode = "host"
  and `:6-9` pin the group to `radxa-dragon-q6a`; the service address comes
  from `:23` via `deployments/applications/services.tf:507`
  > bifrost_host     = "192.168.2.50"
  One static host-network port on that node, as claimed. The "UI + admin
  API + inference all on 8080" framing is consistent with the B1 baseline
  and `docs/haproxy_reverse_proxy.md:23` routing the whole host to 8080.

- **P2 — HOLDS.** `deployments/applications/services/bifrost.hcl:31-36`
  > check {
  >   type     = "http"
  >   path     = "/health"
  The Consul check rides the service registered at address
  `${bifrost_host}` (`:23`), never the edge.
  `deployments/applications/services.tf:553`
  > endpoint = "http://192.168.2.50:8080"
  and `:561` curls `${self.triggers.endpoint}/health`;
  `deployments/applications/providers.tf:67`
  > endpoint = null_resource.bifrost_ready.triggers["endpoint"]
  All health/readiness paths are direct-to-node, so no `/health` skip route
  is needed at the proxy.

- **P3 — HOLDS.** `deployments/applications/services/hermes.hcl:158`
  > base_url="http://127.0.0.1:8080/v1",
  `deployments/applications/services/memex.hcl:168` (and `:175`, `:178`)
  > MEMEX_SERVER__DEFAULT_MODEL__BASE_URL=http://${bifrost_host}:8080/v1
  `deployments/infrastructure/services/prometheus.hcl:129-135` scrapes with
  basic auth against
  > - targets: ["192.168.2.50:8080"]
  Re-ran the grep: the only matches for the edge hostname are
  `docs/haproxy_reverse_proxy.md`, `deployments/applications/services/dash/tiles.json`
  (dashboard link), and `haproxy.hcl` itself; the "CLI test fixture" the
  plan mentions is `cli/tests/fixtures/haproxy_cfg.py:40`
  > acl is_bifrost    hdr(host) -i bifrost.lab.example
  (a fake domain, hence the exact-hostname grep misses it). No in-repo
  consumer does inference through the edge.

- **P4 — HOLDS.** `deployments/infrastructure/services/haproxy.hcl:175-176`
  > backend bifrost
  >     server bifrost1 192.168.2.50:8080 check
  and `:178-179`
  > backend dash
  >     server dash1 192.168.2.50:4180 check
  Bare pass-through today; the dash backend proves the edge-to-proxy shape
  on the same node. `acl is_bifrost` at `:106`, `use_backend bifrost` at
  `:118` as cited.

- **P5 — HOLDS.** `deployments/infrastructure/services/oauth2-proxy.hcl:95`
  > image        = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"
  Header traps at `:10-23` (plural `EMAIL_DOMAINS`/`UPSTREAMS`,
  `PROVIDER=oidc`, 0.0.0.0 bind, `OIDC_EMAIL_CLAIM=sub`, `REVERSE_PROXY`
  unset) read exactly as the plan summarizes; `:6-8` says
  > Reusable pattern: R1 (MLflow) and R4 (Phoenix) copy this job.
  Wiring at `deployments/infrastructure/services.tf:465-489` and firewall
  at `:334-341` resolve as cited.

- **P6 — HOLDS.** `deployments/infrastructure/oidc.tf:94`
  > ### >>> CONSUMER TICKETS: APPEND YOUR CLIENT HERE. <<<
  with the list at `:100-106`; provider `lab` at `:117-126`
  > name               = "lab"
  never-`default` warning at `:112-116`; worked consumer at `:192-211` with
  `:200`
  > assignments      = ["allow_all"]
  Branch-3 allow_all is documented at `docs/vault-human-auth.md:288-292`
  > **No group and no assignment**: set `assignments = ["allow_all"]` on the
  and the scope-request rule at `:306-314`
  > Finally, make your client **request** every scope it needs, not just read it.

- **P7 — HOLDS.** `deployments/infrastructure/secrets.tf:212`
  > name  = "default/oauth2-proxy/oidc"
  and the cookie trap comment at `:227-230`
  > ### oauth2-proxy cookie secret. 32 raw ASCII characters, passed straight
  > ### through with no base64 wrapping: oauth2-proxy's SecretBytes
  with `random_password` `length = 32`, `special = false` at `:231-234`.

- **P8 — HOLDS (probe re-run).** `grep -rn '4181' deployments/` returns
  nothing (exit 1, captured this pass). Port 4181 is unused in the
  deployments tree.

- **P9 — HOLDS (external, honestly bounded; spot-checked).** The premise
  cites four dated sources and states why it is load-bearing. Live
  spot-check this pass: `https://docs.getbifrost.ai/features/sso-with-google-github`
  returns 200 and its body carries "Coming soon" (captured), matching the
  "SSO is enterprise/coming soon" claim. The remaining source details are
  consistent with the B1 baseline in-repo (`bifrost.hcl:98-109` native
  admin auth + inference enforcement). Bounded appropriately.

- **P10 — HOLDS (external, honestly bounded; source-corroborated).** The
  plan defers exact env name/separator/anchoring to a real v7.13.0
  container, the same way L4 did (`oauth2-proxy.hcl:46-57`
  > ### Verified against a real oauth2-proxy v7.13.0
  ). Corroborated this pass against the pinned upstream tag: v7.13.0
  `docs/docs/configuration/overview.md:215` documents
  `--skip-auth-route` / toml `skip_auth_routes`
  ("Format: method=path_regex OR ... path_regex"), and v7.13.0
  `oauthproxy.go` `isAllowedPath` (captured):
  > matches := route.pathRegex.MatchString(requestutil.GetRequestPath(req))
  Go `MatchString` matches anywhere in the path, so the regex is NOT
  implicitly anchored and `^/v1/`, `^/anthropic/` are required to keep
  `/v1foo` gated — exactly the premise. Container verification of the
  env-form specifics (name, comma separator) remains correctly scheduled
  for implementation.

- **P11 — UNCERTAIN (as the plan itself declares).** Websocket log-tail
  behavior of Bifrost 1.6.7's dashboard is unproven; the plan bounds the
  failure to a degraded log tail and flags a post-cutover manual check. The
  author disclaimed the measurement; no probe forced.

- **P12 — HOLDS.** `justfile:18-19`
  > pre_commit:
  >     pre-commit run --all-files
  `.pre-commit-config.yaml:16-32` carries nomad-fmt, terraform-fmt, and
  `scripts/tf_validate.sh`; `.loop/config.json` lists `"just pre_commit"`
  as the sole gate and sets `"require_eval": true` (read this pass).

- **P13 — HOLDS.**
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1`
  > path "secret/data/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_namespace{{ '}}' }}/{{ '{{' }}identity.entity.aliases.{{ auth_method_accessor }}.metadata.nomad_job_id{{ '}}' }}/*" {
  KV read is scoped to `<namespace>/<job_id>/*`, so job
  `oauth2-proxy-bifrost` reading `default/oauth2-proxy-bifrost/*` is the
  required pairing. L1 (`job "oauth2-proxy"` reading
  `default/oauth2-proxy/*`) confirms the pattern in practice.

- **P14 — HOLDS (probe re-run).** `.loop/ledger.json` stages read this
  pass (captured): `B1-bifrost-native-auth-and-virtual-keys done`,
  `L1-landing-oauth2-proxy done`, `F2-foundation-vault-oidc-provider done`,
  `G1-grafana-native-oidc-login done`. No `depends_on` gates needed.

## Most dangerous assumption

**P10.** A wrong skip-auth env name or separator passes every repo gate
(`nomad fmt` / `terraform validate` cannot see it) and either leaves
inference cookie-gated at the edge or exposes admin paths. The source
corroboration above removes the anchoring uncertainty, but the env-form
specifics still ride on the planned container verification; the plan
schedules that check and the eval rows assert the anchored regexes, which
is the right containment.

## Contract hygiene

- Code surface anchors in §7 all resolve to the claimed things (checked
  above under P1-P8).
- Gates discovered, not assumed: §8 matches `justfile`,
  `.pre-commit-config.yaml`, and `.loop/config.json` exactly (P12).
- Non-goals explicit (§5), including the N4 collision hand-off.
- No tests directory involved; the plan says so and names the eval file
  plus its load-bearing static rows, matching `require_eval` and B1's
  archived precedent.
- Forks surfaced with recommendations (Q1-Q3), none silently decided.
- Every §6 requirement has a producer: R1/R2 in the eval's skip-auth and
  live-check rows, R3/R4 structurally (`git diff` empty rows), R5-R9 as
  file assertions in §7's surface. The plan's "no unmeasurable-requirement
  forks" claim checks out.

Observation (advisory): §7's doc update
(`docs/haproxy_reverse_proxy.md:23-26`) is reached by no §6 requirement;
it is listed in subticket 4 and is harmless surface.

Scratch: created at `.loop/scratch/B2-bifrost-oauth2-proxy.plan-validator/`,
no files written, scratch removed at end of pass.
