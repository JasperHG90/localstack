---
verdict: pass-with-required-fixes
plan: f7b745ed1977443669f7163305bd5d247ea73c3b28a6d1ff1d946faff01e7e44
---

# Plan review: F10-foundation-nomad-oidc-issuer

Fingerprint verified locally with `sha256sum` before binding.

## Premise verdict: PARTIALLY SOUND

The core premise holds and is better evidenced than the plan claims. Nomad
serves no discovery document today, `server { oidc_issuer }` is the setting
that fixes it, and the `iss` change is safe for the only consumer. I settled
the plan's central open unknown against Nomad v1.11.3 source, and it resolves
in the plan's favor.

Three defects survive, none of which sink the approach: a code-surface anchor
that points at a directory that does not exist and contradicts the convention
it names, a blast-radius claim that omits that the restarting node is also the
client running the edge proxy that serves the chosen issuer URL, and an eval
that never tests the one claim it says it exists to catch.

## Per assumption

### P1 — `nomad.hcl.j2:11-14` is the bare `server` block, no `oidc_issuer` anywhere: HOLDS
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:11-14` is exactly
`server { enabled = true; bootstrap_expect = 1 }`. `grep -rn oidc_issuer
bootstrap/ deployments/ services/` returns no matches (exit 1). The
`default_identity` anchor at `:37-46` also resolves as described.

### P2 — Live: issuer empty, discovery disabled, JWKS populated: HOLDS
`GET /v1/agent/self` returns `config.Server.OIDCIssuer: ""` and
`BootstrapExpect: 1`. `GET /.well-known/openid-configuration` returns HTTP 404
with body `OIDC Discovery endpoint disabled`. `GET /.well-known/jwks.json`
returns 6 keys.

### P3 — Single server, leader, build 1.11.3: HOLDS
`nomad server members`: one member `firebat.global`, `192.168.2.30:4648`,
`alive`, leader `true`, build `1.11.3`. (The CLI on this box reports
`Nomad v2.0.3`; the briefing was right to say trust `server members`.)

### P4 — `tasks/main.yml:121-128` templates with `notify: Restart nomad`: HOLDS
`bootstrap/roles/nomad_server/tasks/main.yml:121` is `- name: Template Nomad
configuration`, and `:128` is `notify: Restart nomad`. Byte-exact on the range.

### P5 — The safety claim, that `bound_issuer: ""` means changing `iss` breaks nothing: HOLDS
This is the claim the briefing asked me to attack hardest. It survives, and
survives at a deeper level than the plan argued.

- Live: `vault read auth/jwt-nomad/config` returns `bound_issuer n/a` (empty),
  `jwks_url http://127.0.0.1:4646/.well-known/jwks.json`, `oidc_discovery_url
  n/a`, `jwks_pairs []`.
- `bound_issuer` is genuinely the only place `iss` is asserted. In
  `hashicorp/vault-plugin-auth-jwt` `path_login.go:149`, the sole issuer
  expectation is `Issuer: config.BoundIssuer` inside the `jwt.Expected`
  struct passed to `validator.Validate`. No other `issuer` reference exists in
  `path_login.go`, and `path_config.go` references it only as a stored field.
- The validator skips an empty expectation. `hashicorp/cap` `jwt/jwt.go:240`:
  `if expected.Issuer != "" && expected.Issuer != claims.Issuer`.
- I went one step past the plan and checked the roles, which the plan did not.
  `vault read auth/jwt-nomad/role/nomad-workloads` has `bound_claims <nil>` and
  `bound_subject n/a`. `.../role/acme` has `bound_claims
  map[nomad_job_id:[acme] nomad_namespace:[default]]`. Neither binds `iss`. So
  `iss` is unvalidated at the role layer too.

Vault 1.21.4. The claim holds on config, plugin source, and library source.

### P6 — Nothing else consumes Nomad's `iss`: HOLDS, with one gap I could not close
`grep -rniE "jwks|openid|oidc" deployments/` returns nothing. `vault auth list`
shows only `jwt-nomad/` and `token/`. Gap: `consul acl auth-method list`
returned 403 (`lacks permission 'acl:read'`), so I could not rule out a Consul
JWT auth method by direct read. Low risk, because `nomad.hcl.j2:32-35` hands
Consul a static token (`nomad_server_consul_token_secret`) rather than a
workload identity, so Nomad's Consul path does not present a WI JWT.

### P7 — MinIO removed `jwks_url` at the deployed tag: HOLDS
An inlined conclusion from M1/A1, so I verified it independently rather than
accepting it. The deployed tag is real:
`deployments/infrastructure/services/minio.hcl:66` pins
`docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`. Upstream at that exact
tag, `internal/config/identity/openid/openid.go:67-68` lists `JwksURL =
"jwks_url"` under `// Removed params`, `:218` puts it in `deprecatedKeys`, and
`:502-503` is `func Enabled(kvs config.KVS) bool { return kvs.Get(ConfigURL)
!= "" }`. The plan quoted this correctly.

### P8 — HAProxy routes the Nomad hostname, edge reachable over HTTPS: HOLDS on content, BREAKS on path
Line numbers are byte-exact: `:101` `acl is_nomad hdr(host) -i
nomad.lab.orangecluster.nl`, `:112` `use_backend nomad if is_nomad`, `:136`
`backend nomad`, `:137` `server nomad1 192.168.2.30:4646 check`. Live:
`https://nomad.lab.orangecluster.nl/v1/agent/health` returns 200, the HTTP form
returns 301 to the HTTPS URL, and `https://nomad.lab.orangecluster.nl/.well-known/jwks.json`
returns the 6-key set through the edge. DNS resolves the host to
`192.168.2.30`, a LAN address, which supports the "reachable from any client on
the LAN" claim.

The path is wrong. The plan cites `services/haproxy.hcl`; the file is
`deployments/infrastructure/services/haproxy.hcl`. Rooted at the repo root the
cited path does not resolve.

### P9 — Nomad derives `jwks_uri` from `oidc_issuer`, not the request host: HOLDS (SETTLED)
This was the plan's flagged unknown and the highest-value thing to contribute.
It is settled, at the server's exact version.

`hashicorp/nomad` tag `v1.11.3`, `nomad/structs/keyring.go:613-640`:

```go
func NewOIDCDiscoveryConfig(issuer string) (*OIDCDiscoveryConfig, error) {
	if issuer == "" { ... }
	jwksURL, err := url.JoinPath(issuer, JWKSPath)
	...
	disc := &OIDCDiscoveryConfig{ Issuer: issuer, JWKS: jwksURL, ... }
```

`jwks_uri` is the configured issuer joined with the JWKS path. The request host
never enters it. Corroborated on this box: `grep -a` on `/usr/bin/nomad` finds
the literal `error determining jwks path: %w` and the struct tags
`JWKS...json:"jwks_uri"`-family (`id_token_signing_alg_values_supported`,
`subject_types_supported`), plus the live error body `OIDC Discovery endpoint
disabled` matching the same code path.

Second half, which the plan did not check but which matters more for M1: the
token's `iss` will equal the configured value exactly.
`nomad/encrypter.go:337-340` at v1.11.3 is `if e.issuer != "" {
claims.Issuer = e.issuer }`, with `e.issuer` seeded at `:99` from
`srv.GetConfig().OIDCIssuer`. So discovery `issuer`, `agent/self` OIDCIssuer,
and the minted `iss` are one value. The plan's recommended
`https://nomad.lab.orangecluster.nl` yields `jwks_uri
https://nomad.lab.orangecluster.nl/.well-known/jwks.json`, which I fetched live
and which returns 6 keys.

Bonus, and it endorses the plan's scheme choice: the binary carries the warning
`server.oidc_issuer = "%s" is not using https. Many OIDC implementations
require https.`

### P10 — The restart is bounded to "scheduling and the API pause, running allocations unaffected": BREAKS (incomplete, and it understates the blast radius)
The node is not a pure server. `nomad.hcl.j2:20` has `client { enabled = true
}`, and `nomad node status` lists `firebat` as an eligible, ready client
alongside four others. Restarting the agent restarts the client too.

Worse, and the plan never says it:
`deployments/infrastructure/services/haproxy.hcl:6-9` pins HAProxy with a
`constraint` on `attr.unique.hostname == firebat`, and its allocation is in
fact running on `firebat`. So the plan restarts the agent supervising the edge
proxy, and the issuer URL it recommends is served **by that proxy, on that
node**. Nomad normally reattaches task handles across an agent restart, so the
allocation usually survives, but the plan asserts the bounded outcome flatly
with no evidence and offers no rollback for the case where it does not. If the
HAProxy allocation restarts, every routed host drops at once: vault, minio, s3,
grafana, mlflow, memex, phoenix, consul, bifrost, and the new issuer URL
itself (`haproxy.hcl:98-108`).

There is also a standing coupling the plan should state: after this change the
cluster's OIDC issuer and its JWKS are reachable only while HAProxy is up. This
is not a bootstrap loop for Vault, which trusts `jwks_url` at
`http://127.0.0.1:4646`, but M1's MinIO and R1's oauth2-proxy cannot validate a
token whenever the edge is down.

### P11 — The new variable follows the `nomad_server_ip_address` convention, in `defaults/main.yml` or inventory group vars, "with a default": BREAKS
Both cited locations are wrong, and the requirement contradicts itself.

- `bootstrap/roles/nomad_server/defaults/` does not exist. `find
  bootstrap/roles -type d -name defaults` returns nothing: no role in this repo
  has a `defaults/` directory at all.
- There is no group-vars directory. The inventory is a single file,
  `bootstrap/inventory/cluster.ini`.
- The actual convention is an inline `vars:` block on the role invocation:
  `bootstrap/playbooks/configure_hashistack_server.yml:41-44` sets
  `nomad_server_ip_address: "192.168.2.30"` and
  `nomad_server_consul_token_secret`.
- Requirement 1 says "sourced from an Ansible variable with a default ...
  matching how `nomad_server_ip_address` is already used in the same file."
  `nomad_server_ip_address` has no default; it is a required role var supplied
  by the playbook. The two halves of that sentence cannot both be satisfied.

This propagates into eval row 8, below.

### P12 — Repo gate anchors: HOLDS
`justfile:30-32` is exactly the `worktree_setup path:` recipe and its two
lines. `pre_commit` is `pre-commit run --all-files` (`justfile:18-19`).

### P13 — `depends_on = []` is right: PARTIALLY (no hard edge needed, but the ordering is wrong)
No file write-conflict exists. F1 marks `nomad.hcl.j2` read-only and its code
surface targets `tasks/main.yml:198-271`; F10 writes `nomad.hcl.j2` and marks
`tasks/main.yml` read-only. F10 consumes nothing F1 produces, so I would not
add a `depends_on` edge.

The collision is one of ownership, not data. F1 is `stage: ready` in
`.loop/ledger.json` and therefore pickable right now, and F1's Q7
(`F1-foundation-nomad-wi-jwt-trust.md:571-590`) recommends doing exactly this
change inside F1: "add it as a subticket here". F10's plan defers closing that
question to subticket 6, after the change lands. Nothing prevents F1 from being
picked up first and making the same edit. The relay must run first, not last.

## Most dangerous assumption

**P10.** With P9 settled in the plan's favor, the remaining claim that can
actually hurt the cluster is "running allocations are unaffected." The plan
restarts the only Nomad server, which is also the client that runs the edge
proxy, which serves the very issuer URL the plan chooses. If that allocation
does not reattach, the whole edge drops and the plan has neither predicted it
nor written a rollback for it.

## Required fixes

1. **Fix the variable location (P11).** Replace the code-surface line naming
   `bootstrap/roles/nomad_server/defaults/main.yml` or inventory group vars
   with the real convention: an inline `vars:` entry on the `nomad_server` role
   invocation at `bootstrap/playbooks/configure_hashistack_server.yml:41-44`,
   alongside `nomad_server_ip_address`. Drop "with a default" from requirement
   1, or say explicitly that this ticket introduces the repo's first role
   default and accept that it diverges from the convention it cites.
2. **Correct the blast radius (P10).** State in the risk section that
   `nomad.hcl.j2:20` makes firebat a combined server and client, that
   `haproxy.hcl:6-9` pins the edge proxy to it, and that the recommended issuer
   URL is served by an allocation on the node being restarted. Add the standing
   coupling: after this change, OIDC discovery and JWKS are available only
   while HAProxy is up. Add a rollback note for the case where the HAProxy
   allocation does not reattach.
3. **Fix the haproxy path (P8).** `services/haproxy.hcl` does not resolve from
   the repo root. It is `deployments/infrastructure/services/haproxy.hcl`. The
   three line numbers are correct.
4. **Move the F1 Q7 relay to subticket 1 (P13).** F1 is `ready` and its Q7
   tells its implementer to make this exact change. Relay before touching the
   template, not after.
5. **Record P9 as settled and demote the hedge.** Q1's closing paragraph tells
   the implementer to confirm whether `jwks_uri` follows the issuer or the
   request host. It follows the issuer:
   `nomad/structs/keyring.go:613-640` at v1.11.3 is `url.JoinPath(issuer,
   JWKSPath)`, and `nomad/encrypter.go:337-340` sets the token's `iss` to the
   same configured value. Cite it and keep eval row 3 as the confirmation.

## Eval shape-check (`.loop/evals/F10-foundation-nomad-oidc-issuer.md`)

The eval is mostly well aimed. Row 4 (fetch from a non-server host) and row 7
(re-check at T+10 minutes) are both genuinely load-bearing and easy to have
omitted. Row 5 is not vacuous: I confirmed all three named jobs really do use
Vault workload identity (`haproxy.hcl:39,64`; `memex.hcl:44,52`;
`grafana.hcl:29,79`), and haproxy really does render the edge TLS PEM. Rows 9
and 10 are good guardrails. Three problems:

- **Row 8 would fail a correct implementation.** It scores the default against
  "the defaults or group-vars file". Neither exists in this repo (P11). An
  implementer who correctly follows
  `configure_hashistack_server.yml:41-44` fails a 100%-threshold row. Rewrite
  the scorer to name the playbook `vars:` block.
- **The eval never tests the defect it says it exists to catch.** Its own lead
  says "M1 and R1 will compare the `iss` claim on a token against the discovery
  document's `issuer`, literally." No row decodes a token. Rows 1 to 3 check
  the discovery document, row 2 adds `agent/self` and the template, row 6
  checks Vault's config. A build whose discovery `issuer` is correct but whose
  minted `iss` differs passes all twelve rows and fails opaquely in M1. Per
  `encrypter.go:339` they will match in practice, which is exactly why the row
  is cheap to add and wrong to omit: add a row that decodes a freshly issued WI
  JWT and asserts `iss` is byte-identical to the discovery `issuer`.
- **The eval hard-codes the answer to an open question.** The Definition of
  Done and rows 1 and 3 pin `https://nomad.lab.orangecluster.nl`, while plan Q1
  is still open and ends "Operator confirms the value before subticket 2." A
  fork the plan leaves open is silently decided in the scorer, and if the
  operator picks anything else those rows fail a correct implementation.
  Either close Q1 in the plan or parameterize the rows on the configured value.

The eval is unsigned (`signed-off-by: PENDING`), which is expected at this
stage.

## Contract hygiene

- **Code surface with resolved anchors:** two defects, P8 (wrong path prefix)
  and P11 (nonexistent directory). All other anchors resolve byte-exact.
- **Discovered, not assumed, gates:** correct. `just pre_commit` and
  `justfile:30-32` both verified, and the plan is honest that there is no CI
  and no Ansible test harness.
- **Explicit non-goals:** present and unusually good. Declining to set
  `bound_issuer` in the same ticket is the right call for the reason given.
- **Tests homed in the code surface:** the eval names concrete files and
  commands; rows 5, 8, 9 and 11 tie to real paths.
- **Forks surfaced, not silently decided:** Q1 and Q2 are surfaced with
  recommendations in the plan, but Q1's answer is then pre-committed in the
  eval. See above.

## Attack-surface summary

1. **Stale premise:** none found. Every current-state claim reproduces live.
2. **Inlined conclusion:** the MinIO `jwks_url` removal (P7) is inherited from
   M1/A1 rather than established here, but I verified it at the deployed tag
   and it is true.
3. **Broken dependency edge:** no hard edge missing; an ordering fix is
   required against F1 (P13).
4. **Shape-check eval:** three findings, one of which fails a correct
   implementation (row 8) and one of which is a missing row for the eval's own
   stated defect.
5. **Unresolvable anchor:** two. `services/haproxy.hcl` (wrong prefix) and
   `bootstrap/roles/nomad_server/defaults/main.yml` (does not exist).

All work was read-only. No mutating command was run against the repo, Vault,
Nomad, or Consul.
