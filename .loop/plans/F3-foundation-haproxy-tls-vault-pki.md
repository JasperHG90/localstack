# F3 — TLS at the HAProxy edge via Vault PKI (foundation)

## Title
Terminate TLS at the HAProxy edge with a Vault-PKI-issued leaf cert,
redirect HTTP to HTTPS, and keep the existing static backends unchanged.

## Size / Effort
**Medium.** Two coordinated surfaces: new Vault PKI Terraform (a CA
mount, a role, and — the sharp edge — an authorization grant so the
HAProxy Nomad workload may issue a leaf), plus an in-place rewrite of
the HAProxy job's frontend to add a `vault {}` stanza, a cert template,
a `:443 ssl` frontend, and an HTTP-to-HTTPS redirect. The effort driver
is not the HCL: it is the authorization fork (see Open Questions Q1),
because the current Nomad-workload Vault policy does not cover a PKI
issue path, so the job cannot fetch a cert until that gap is closed.

## Triggered by
Home-lab auth epic, foundation ticket F3. OAuth cookies and OIDC
tokens for the planned landing page (L1 oauth2-proxy, L2 Homepage) and
the human OIDC console flows must never traverse cleartext. The edge is
plain HTTP:80 today (`deployments/infrastructure/services/haproxy.hcl:48-49`),
so TLS at the HAProxy edge is a hard prerequisite for L1/L2 and any
human console flow.

## Context (today's state)
The HAProxy edge is a single Nomad job:
`deployments/infrastructure/services/haproxy.hcl`.

- Network stanza exposes only `http` (static 80 → 8080) and `stats`
  (static 8404): `haproxy.hcl:11-19`. No `:443` port.
- Task runs the `haproxy:3.1-alpine` podman image with
  `network_mode = "host"` and `cap_add = ["NET_BIND_SERVICE"]`
  (`haproxy.hcl:21-29`), so binding a privileged port such as 443
  directly on the host works without extra mapping.
- The task has **no `vault {}` stanza** (confirmed: the only "vault"
  matches in the file are the `vault.localstack` backend at
  `haproxy.hcl:53,66,90-91`). Contrast `minio.hcl:30`, which shows the
  established `vault {}` + Vault-templated `template` pattern.
- The single `frontend http_in` binds `*:80` (`haproxy.hcl:48-49`),
  then routes ~12 host ACLs to static backends
  (`haproxy.hcl:51-75`), each backend a hardcoded `server <ip>:<port>`
  (`haproxy.hcl:84-121`). All routed hostnames are `*.localstack`
  (e.g. `minio.localstack`, `vault.localstack`, `grafana.localstack`).
- The config is rendered by a `template` block into `local/haproxy.cfg`
  (`haproxy.hcl:31-124`), fed one interpolation `${openfang_password}`
  from Terraform (`services.tf:308-316`).

Terraform for this layer:
- `secrets.tf` manages a KV2 mount and `vault_kv_secret_v2` resources
  (`secrets.tf:1-88`). There is **no PKI mount and no `vault_policy`
  resource anywhere in the layer.**
- Vault provider is `hashicorp/vault ~>5.3.0` (`providers.tf:7-10`),
  unauthenticated block `provider "vault" {}` (`providers.tf:28`).
- HAProxy firewall rules open only ports 80 and 8404
  (`services.tf:182-192`); there is no rule for 443.

The authorization reality (the blocker to internalize before coding):
- Nomad workloads authenticate to Vault via a JWT auth backend
  `jwt-nomad` with a single default role `nomad-workloads`
  (`bootstrap/roles/nomad_server/tasks/main.yml:219-238`).
- That role attaches exactly one policy, `nomad-workloads`
  (`bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json:12`).
- That policy grants read only under
  `secret/data/<namespace>/<job_id>/*` and `bootstrap/*`
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-23`).
  **It grants nothing on a `pki/` path.** A `vault {}` token minted for
  the HAProxy job therefore cannot call a PKI issue endpoint until a
  grant is added. This binding lives in **bootstrap Ansible**, not in
  the Terraform layer this ticket otherwise edits — a layer-crossing
  decision (Q1).

## Non-goals / out of scope
- Dynamic consul-template ingress. The static `server <ip>:<port>`
  backend model (`haproxy.hcl:84-121`) stays exactly as is. Deferred.
- Backend/upstream TLS (HAProxy-to-service). This ticket terminates TLS
  at the edge only; backends stay plain HTTP.
- oauth2-proxy, Homepage, and OIDC console wiring (L1/L2). This ticket
  only makes HTTPS available for them.
- Distributing the CA trust root to client machines/browsers. Out of
  scope; note it as a follow-up so the padlock is "valid" only once
  clients trust the CA.
- Changing hostnames, ACLs, the `stats` frontend (`haproxy.hcl:77-82`),
  or the `openfang_users` basic-auth backends
  (`haproxy.hcl:45-46,100,116,120`).
- mTLS / client-cert auth at the edge.

## Requirements & restrictions
1. HTTPS must be reachable at the edge on `:443` with a leaf cert
   issued by a Vault PKI engine, valid for every hostname the frontend
   currently routes (all `*.localstack`).
2. Plain HTTP `:80` must 301-redirect to HTTPS; no routed service is
   served over cleartext after this change.
3. Every existing backend and its routing must keep working unchanged
   (Non-goal: touching backends). Requirement per CLAUDE.md §3
   "Surgical Changes": every changed line traces to this request.
4. Cert material must be delivered by a Nomad `template` block using the
   job's Vault Workload Identity, matching the repo pattern
   (`minio.hcl:30-40`). No cert or private key may be written to disk in
   the repo or committed — the `detect-private-key` pre-commit hook
   (`.pre-commit-config.yaml:12`) must stay green, and CLAUDE.md
   "Secrets: all in Vault KV2. Never hardcode credentials" applies.
5. Cert renewal must trigger an HAProxy reload. Use Nomad template
   `change_mode` (the repo uses both `change_mode="signal"` +
   `change_signal="SIGHUP"` in `prometheus.hcl:143-144` and
   `change_mode="restart"` in `grafana.hcl:249`). Pick one and justify
   (recommendation in Q4).
6. Secret-path convention: any Vault paths follow the repo convention
   `secret/data/<namespace>/<job_id>/<entry>`
   (`vault_nomad_workloads.hcl.j2:1`); a PKI mount is a new engine, so
   name its mount and role explicitly and record the choice (Q2).
7. Terraform provider pins are fixed at `providers.tf:1-24`; use the
   already-pinned `hashicorp/vault ~>5.3.0`. Do not bump provider
   versions.
8. Per `.claude/rules/adversarial-reviews.md`, an adversarial sub-agent
   review runs before this is reported done.

## Code surface
- `deployments/infrastructure/services/haproxy.hcl:11-19` — add an
  `https` port (`static = 443`) to the network stanza.
- `deployments/infrastructure/services/haproxy.hcl:21-30` — add a
  `vault {}` stanza to the `haproxy` task (currently absent) so the job
  gets a Workload Identity Vault token.
- `deployments/infrastructure/services/haproxy.hcl:31-124` — inside the
  config `template`, and/or as a second `template` block: render the
  leaf cert + key (+ issuing CA) into a single PEM file the frontend
  can `bind ... ssl crt <file>`. Add `change_mode`/`change_signal` for
  renewal reload. Note HAProxy needs cert and key concatenated in one
  PEM.
- `deployments/infrastructure/services/haproxy.hcl:48-75` — convert the
  frontend: `bind *:443 ssl crt <pem>`, move the ACL/`use_backend`
  block (`:51-75`) onto the HTTPS frontend, and reduce the `:80`
  frontend to a scheme redirect (e.g. `http-request redirect scheme
  https code 301 unless { ssl_fc }`). Backends (`:84-121`) stay
  verbatim.
- `deployments/infrastructure/services.tf:182-192` — add an
  `allow ... to any port 443 proto tcp` rule (LAN `192.168.0.0/16` and
  Tailscale `100.64.0.0/10`, mirroring the existing 80/8404 pattern).
- `deployments/infrastructure/services.tf:308-316` — if the cert role
  name / PKI mount must reach the job, thread it through the existing
  `templatefile(...)` var map (today only `openfang_password`).
- `deployments/infrastructure/secrets.tf` (or a new `pki.tf` in the
  same dir) — add the PKI Terraform: a `vault_mount` of type `pki`, CA
  material (`vault_pki_secret_backend_root_cert` or an intermediate
  chain), a URLs config, and a `vault_pki_secret_backend_role`
  scoped to `localstack` domains. Follow the resource style of
  `secrets.tf:2-7`.
- **Authorization grant (Q1 decides the file):** either
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  (add a PKI issue path to the shared policy) or a new Terraform
  `vault_policy` + a dedicated `jwt-nomad` role plus a per-job
  `vault { role = ... }` override. Nothing in the current job or policy
  authorizes a PKI issue call, so this grant is mandatory, not
  optional.

## 8. Tests & validation gates
This layer is Terraform + Nomad HCL, with no unit-test harness and no
CI. Acceptance runs against the live cluster: `VAULT_ADDR`,
`VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are
set in this environment, so the evals below are runnable, not manual.

### Repo gate (pre-apply guard — must be green before `just apply`)
- **`just pre_commit`** (`justfile:17-18` → `pre-commit run
  --all-files`). This gate is Terraform-aware: beyond the JSON/YAML/AST
  hooks, `detect-private-key`, `end-of-file-fixer`, and `nomad fmt
  -recursive` on `*.hcl`, it runs the local `terraform-fmt`
  (`terraform fmt -check -recursive`) and `terraform-validate` (via
  `scripts/tf_validate.sh`) hooks (`.pre-commit-config.yaml:22-33`).
  `tf_validate.sh` validates `deployments/infrastructure` offline, so a
  `vault_mount`/PKI resource with a wrong argument name fails here, not
  at apply. `.loop/` and `.claude/` are excluded
  (`.pre-commit-config.yaml:1`), so this ticket file is not scanned.
  - **Command:** `just pre_commit`
  - **Expected:** every hook reports `Passed`; exit 0. The edited
    `haproxy.hcl` survives `nomad fmt`, the new PKI `.tf` survives
    `terraform fmt` + `terraform validate`, and no key/cert is caught by
    `detect-private-key`.
- **Terraform plan** (second pre-apply guard, now runnable — Consul
  backend + Vault auth are reachable via the set env vars):
  - **Command:** `terraform -chdir=deployments/infrastructure plan`
  - **Expected:** a clean plan that *adds* the PKI mount, CA, role, the
    443 firewall rule, and the HAProxy job change, and *destroys no*
    existing backend, KV mount, or firewall resource.

### Evals (live cluster — close-out acceptance, run after `just apply`)
Substitute `<edge-host>` with the HAProxy edge address (the node the job
runs `network_mode = "host"` on), `<role>` with the PKI role from Q3,
and `pki` with the mount from Q2. Command + expected result each.

1. **Vault PKI mount and role exist.**
   - **Command:** `vault read pki/roles/<role>`
   - **Expected:** returns the role; `allowed_domains` contains
     `localstack`, `allow_subdomains` is `true` (per Q3 wildcard
     recommendation).
   - **Command:** `vault read pki/cert/ca`
   - **Expected:** returns the CA certificate PEM (used in eval 3 to
     verify the chain). Record its issuer CN.

2. **HAProxy alloc is healthy.**
   - **Command:** `nomad job status haproxy`
   - **Expected:** `Status = running`, the latest deployment is
     `successful`, and the alloc is `healthy` (not `pending`/`failed`).
     A stuck-`pending` alloc is the signature of the Q1 authorization
     gap: the `vault {}` PKI template never renders.

3. **TLS is served at the edge and chains to the Vault PKI CA.**
   - **Command:** `curl -kv --resolve grafana.localstack:443:<edge-host>
     https://grafana.localstack/`
   - **Expected:** the TLS handshake succeeds and the routed backend
     answers (HTTP 200/302 from Grafana), proving `:443 ssl` is live.
   - **Command:** `openssl s_client -connect <edge-host>:443 -servername
     grafana.localstack </dev/null 2>/dev/null | openssl x509 -noout
     -issuer -subject -ext subjectAltName`
   - **Expected:** the `issuer=` line equals the CA issuer CN from eval
     1 (`vault read pki/cert/ca`), confirming the leaf chains to the
     Vault PKI CA; the SAN covers `*.localstack` / `grafana.localstack`.

4. **Plain HTTP redirects to HTTPS.**
   - **Command:** `curl -sI --resolve grafana.localstack:80:<edge-host>
     http://grafana.localstack/`
   - **Expected:** `HTTP/1.1 301` with `Location:
     https://grafana.localstack/`. No routed service answers 200 over
     cleartext.

5. **Existing routed services still answer through HTTPS (routing and
   basic-auth intact).**
   - **Command:** `curl -sk -o /dev/null -w '%{http_code}\n' --resolve
     grafana.localstack:443:<edge-host> https://grafana.localstack/`
   - **Expected:** `200` — the plain backend still resolves over the new
     HTTPS frontend.
   - **Command:** `curl -sk -o /dev/null -w '%{http_code}\n' --resolve
     mlflow.localstack:443:<edge-host> https://mlflow.localstack/`
   - **Expected:** `401` — the `openfang_users` basic-auth backend
     (`haproxy.hcl:116`) still enforces auth through HTTPS, proving the
     ACL move preserved both routing and auth.

Because there is no automated unit test for infra HCL, the
reproducing-test rule in `.claude/rules/python-testing.md` does not bind
here; the live evals above and the adversarial review
(`.claude/rules/adversarial-reviews.md`) are the acceptance evidence.

**Eval marker:** the seven scenarios above are encoded as the five-column
Definition-of-Done marker at `.loop/evals/F3-foundation-haproxy-tls-vault-pki.md` (co-author it
with the `create-eval` skill before implementation).

## Risk assessment
- **Blast radius: high but contained to the edge.** HAProxy is the
  single ingress for ~12 services (`haproxy.hcl:51-75`). A broken
  frontend rewrite (bad `crt`, unrenderable template, failed Vault
  auth) takes the whole edge down until rolled back. It does not touch
  the backends themselves.
- **Authorization is the top failure mode.** If the PKI grant (Q1) is
  missing or misscoped, the `vault {}` template blocks and the alloc
  never becomes healthy — a silent outage, not an error at plan time.
- **Cert coverage mismatch.** If the leaf's SANs do not cover every
  `*.localstack` host, some services 200 while others throw cert
  errors. A wildcard `*.localstack` (Q3) removes this class of failure.
- **Reload correctness.** `change_mode="signal"` with the wrong signal,
  or an image whose PID 1 does not hot-reload, silently serves a stale
  cert after renewal; `change_mode="restart"` is blunt but obviously
  correct (Q4).
- **Reversibility: high.** Revert is `git revert` + re-apply the job;
  the PKI mount can be left in place or torn down independently. No data
  migration, no state coupling to backends.
- **Trust distribution.** Even a correct setup shows "untrusted" in
  browsers until the CA root is distributed to clients (out of scope) —
  set expectations so this is not read as a failure.

## Subtickets (ordered, dependency-aware)
1. **PKI engine in Terraform.** Add the `vault_mount` (pki), CA
   material, URLs, and a `vault_pki_secret_backend_role` scoped to
   `localstack`. `terraform validate` passes. (Resolves Q2, Q3.)
2. **Authorization grant.** Per Q1, grant the HAProxy workload the PKI
   issue capability (shared-policy path edit vs dedicated role +
   `vault { role }`). This must land before subticket 4 can run
   healthy.
3. **Firewall + network port.** Open 443 in `services.tf:182-192` and
   add the `https` port at `haproxy.hcl:11-19`.
4. **HAProxy job rewrite.** Add `vault {}`, the cert `template` with the
   chosen `change_mode`, `bind *:443 ssl crt`, move ACLs to the HTTPS
   frontend, and reduce `:80` to a 301 redirect. `nomad fmt` clean.
5. **Verify + adversarial review.** Run the live evals in Section 8,
   then the adversarial sub-agent review.

## Open questions
- **Q1 — How is the HAProxy workload authorized to issue a PKI leaf,
  and in which layer?** The shared `nomad-workloads` policy
  (`vault_nomad_workloads.hcl.j2:1-23`) covers no `pki/` path, and it is
  Ansible-owned while the epic says PKI goes in Terraform.
  *Recommendation:* create a **dedicated** Vault policy granting only
  `pki/issue/<role>` (create/update) plus a dedicated `jwt-nomad` role,
  and set `vault { role = "haproxy" }` on the job, rather than widening
  the shared policy (which would let every workload mint certs —
  violates least privilege). This keeps the grant scoped, but it splits
  ownership: the JWT auth backend is bootstrapped in Ansible
  (`nomad_server/tasks/main.yml:206-238`), so managing a second role in
  Terraform crosses the layer boundary. Operator must confirm the split
  (Terraform `vault_jwt_auth_backend_role` + `vault_policy` against the
  existing `jwt-nomad` mount) or elect to keep it in Ansible.
- **Q2 — Root or intermediate CA, and mount path?** The epic allows
  either. *Recommendation:* a single self-signed **root** CA at mount
  `pki` for the home lab (no external issuer to chain from; simpler),
  deferring an intermediate until there is a reason. Confirm the mount
  name (`pki`) and CA CN/TTL.
- **Q3 — One wildcard leaf `*.localstack` or a multi-SAN leaf listing
  each host?** The frontend routes ~12 distinct `*.localstack`
  hostnames (`haproxy.hcl:51-62`). *Recommendation:* issue a single
  wildcard `*.localstack` leaf (role `allowed_domains=["localstack"]`,
  `allow_subdomains=true`); it covers every current and future
  subdomain with one cert and one template. Confirm wildcard is
  acceptable vs an explicit SAN allow-list.
- **Q4 — Reload strategy on renewal: `restart` or `signal`?** The repo
  uses both patterns (`grafana.hcl:249` restart; `prometheus.hcl:143`
  SIGHUP). *Recommendation:* start with `change_mode="restart"` — the
  `haproxy:3.1-alpine` entrypoint does not obviously support a hitless
  USR2 reload under podman, and a brief restart on the (long) renewal
  interval is acceptable for a home lab. Revisit hitless reload only if
  the restart blip proves disruptive.
- **Q5 — Leaf TTL / renewal cadence?** Not specified. *Recommendation:*
  role `max_ttl` ~72h with the template renewing at ~2/3 life, balancing
  churn against blast radius. Confirm.
- **Q6 — Edge hostname set.** The epic names `dash.localstack` and
  "console hostnames" that do not yet exist in the frontend
  (`haproxy.hcl:51-62`). *Recommendation:* the wildcard from Q3 already
  covers them, so add no new ACLs in this ticket (they arrive with
  L1/L2). Confirm no new routing is expected here.

## Resolved forks (operator, 2026-07-23)

- **Q1 → Dedicated scoped policy + role, in Terraform.** PKI-for-TLS is
  not needed at bootstrap (cluster comes up over HTTP; TLS is a later
  hardening step), and the epic puts PKI in Terraform. Create a
  dedicated `vault_policy` granting only `pki/issue/<role>` plus a
  dedicated `vault_jwt_auth_backend_role` against the existing (Ansible-
  created) `jwt-nomad` mount; set `vault { role = "haproxy" }` on the
  job. Do NOT widen the shared `nomad-workloads` policy.
- **Q2 → Self-signed root CA at mount `pki`.** Single root for the home
  lab; no intermediate until there is a reason. Confirm CA CN/TTL.
- **Q3 → Wildcard `*.localstack` leaf.** Role
  `allowed_domains=["localstack"]`, `allow_subdomains=true`. Blast-radius
  downside is moot here: haproxy terminates TLS centrally, so all keys
  live in one alloc regardless of wildcard-vs-per-host. One cert, one
  template, covers future subdomains.
- **Q4 → `change_mode="restart"`.** haproxy:3.1-alpine has no confirmed
  hitless USR2 reload under podman; a brief restart on the long renewal
  interval is acceptable. Revisit only if disruptive.
- **Q5 → `max_ttl` ~72h, renew at ~2/3 life (~48h).** Balances renewal
  churn (and restart blips) against exposure window.
- **Q6 → No new ACLs.** The Q3 wildcard already covers `dash.localstack`
  and future console hosts; routing for them arrives with L1/L2.

**Note:** F2 is blocked on F3 (F2-Q2 requires an https OIDC issuer, which
needs this ticket's TLS termination for `vault.localstack`). Build order:
F1 → F3 → F2.