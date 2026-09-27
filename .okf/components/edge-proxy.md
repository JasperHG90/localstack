---
type: component
title: The HAProxy edge and the oauth2-proxy gates behind it
description: "One HAProxy job on firebat terminates TLS for every lab hostname, reads its certificate from Vault KV at runtime with no Terraform link to the job that writes it, and routes by Host header to literal node addresses. Two oauth2-proxy jobs on radxa gate dash and registry-ui with one shared Vault OIDC client."
tags: [haproxy, edge, tls, oauth2-proxy, oidc, vault, dns]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: haproxy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: oauth2-proxy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/oauth2-proxy.hcl
  - id: oauth2-proxy-registry-ui-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl
  - id: oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: cli-haproxy-parser
    resource: git:3ec5d1e:cli/src/localstack_cli/api/haproxy.py
  - id: oauth2-proxy-guard
    resource: git:3ec5d1e:scripts/check_oauth2_proxy_guard.py
  - id: F3-foundation-haproxy-tls-vault-pki
    resource: loop:F3-foundation-haproxy-tls-vault-pki
  - id: T3-tls-edge-cutover-lab-domain
    resource: loop:T3-tls-edge-cutover-lab-domain
  - id: L1-landing-oauth2-proxy
    resource: git:3ec5d1e:.loop/plans/L1-landing-oauth2-proxy.md
  - id: nomad-workloads-policy
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2
  - id: unroute-monitoring
    resource: git:fe681b4:deployments/infrastructure/services/haproxy.hcl
  - id: guard-hook-removed
    resource: git:f197702:.pre-commit-config.yaml
  - id: N1-netsec-restrict-prometheus-loki-to-cluster
    resource: loop:N1-netsec-restrict-prometheus-loki-to-cluster
  - id: N2-netsec-remove-dnsmasq-for-public-dns
    resource: loop:N2-netsec-remove-dnsmasq-for-public-dns
  - id: T2-tls-dnsmasq-lab-zone-dns
    resource: loop:T2-tls-dnsmasq-lab-zone-dns
---

# The HAProxy edge and the oauth2-proxy gates behind it

Every `https://<name>.lab.orangecluster.nl` request lands on one HAProxy job
on firebat (`192.168.2.30`). It terminates TLS with a certificate it reads
from Vault, picks a backend by Host header, and dials a literal node address.
Two of those backends are oauth2-proxy jobs that add a Vault login in front
of dash and registry-ui. The route table and ports are
`docs/reference/edge-routes.md`. This page is how the pieces connect and what
breaks when you change them.

## The pieces

| Piece | Where |
| --- | --- |
| HAProxy jobspec, config heredoc, certificate template | `deployments/infrastructure/services/haproxy.hcl` |
| `nomad_job.haproxy`, passes only `tls_secret` | `deployments/infrastructure/services.tf` |
| Certificate in KV2 | `secret/data/default/haproxy/tls`, written by the [ACME job](/components/acme-certificate-job.md) |
| Firewall on firebat: 80, 443, 8404 from LAN and tailnet | `local.firewall_rules.haproxy` in `deployments/infrastructure/services.tf`, see [host firewall](/components/host-firewall.md) |
| oauth2-proxy for dash (4180) and registry-ui (4181) | `deployments/infrastructure/services/oauth2-proxy.hcl`, `oauth2-proxy-registry-ui.hcl` |
| Their OIDC client and redirect URIs | `vault_identity_oidc_client.oauth2_proxy`, `local.oauth2_proxy_redirect_url` and `local.registry_ui_redirect_url` in `deployments/infrastructure/oidc.tf` |
| Their client and cookie secrets, one copy per job | `deployments/infrastructure/secrets.tf` |
| Firewall rules on each backend host admitting `.30` | whichever root owns the service, e.g. `deployments/applications/services.tf` |

## How the certificate reaches HAProxy

Nothing in Terraform links `nomad_job.haproxy` to `nomad_job.acme`. The acme
job writes KV at runtime, and HAProxy's template blocks until the secret
exists. So a fresh cluster brings the edge up only after the first acme run.

- The job declares a bare `vault {}`, so it gets the Ansible-owned
  `nomad-workloads` role. That policy grants a read on
  `secret/data/<namespace>/<job_id>/*`
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`),
  and `default/haproxy/tls` is exactly the `haproxy` job's own prefix. T3
  removed F3's dedicated role for that reason. Renaming the job breaks the
  read.
- The template reads `.Data.data.certificate` and `.Data.data.private_key`.
  KV2 nests one level deeper than the PKI response F3 used. The wrong path
  renders blank lines, HAProxy cannot parse `crt`, and every route goes down
  at once. `issuer_chain` is left out because `certificate` already carries
  the chain.
- `perms = "0644"` is required. The image runs as uid 99 while Nomad
  renders as the agent user, so 0600 leaves HAProxy unable to read its key.
  F3 found this by inspecting the image. T3 proved it with the real PEM:
  `haproxy -c` at 0600 fails.
- `change_mode = "restart"`: a renewal restarts HAProxy. No hitless reload
  was confirmed for this image under podman.

## Routing

- ACLs belong on `https_in`. `http_in` only redirects to HTTPS, so an ACL there
  never routes. There is no `default_backend`, so an unknown Host gets a 503.
- Every `server` line is a literal `ip:port`, not a Consul lookup. Moving a
  backend to another node means editing this heredoc, and editing it
  re-registers the job.
- `localstack service` parses the rendered config from the Nomad API with
  line regexes (`cli/src/localstack_cli/api/haproxy.py`). It expects
  `acl is_<name> hdr(host) -i <host>`, `use_backend <b> if is_<name>` and
  `server <id> <ip>:<port>`. A different ACL style, such as a map file,
  makes that command fail with a parse error. The parser copies four fields
  and never
  keeps the input, because the jobspec once held a basic-auth password.
- Only the `registry` and `hermesgw` backends set `X-Forwarded-Proto`, and
  `hermesgw` sets `X-Forwarded-For` rather than appending it, so a client
  cannot choose the address Hermes rate-limits by. `registry` also raises
  `timeout server` to 1800s for the silence while a large upload finishes
  into MinIO.
- The stats frontend on 8404 has no auth and is open to the LAN and the
  tailnet. Prometheus scrapes `/metrics` there.

Adding a route has two halves in two places. The route goes in
`haproxy.hcl`. The backend's host also needs a ufw rule admitting
`192.168.2.30` on that port, in the root that owns the service. The how-to
`docs/how-to/add-a-service-to-the-edge.md` covers only the first half.

Prometheus and Loki were routed until the N1 follow-on (`fe681b4`). N1 had
admitted `.30` on their ports so the edge could proxy them, which left every
metric and log line readable through the edge with no password. Nothing
used those routes, so the follow-on deleted them. The why for users is
`docs/explanation/why-monitoring-is-not-behind-the-edge.md`.

## Who authenticates

The file holds no `http-request auth` any more. Each backend is one of these:

- **An oauth2-proxy gate**: dash, registry-ui.
- **Native OIDC against Vault**: grafana, hermes-gateway, openviking (ov-dash).
- **The service's own credential**: bifrost, openviking-api, memex, the
  MinIO console and S3 API, registry (htpasswd, because podman and docker
  cannot answer an HAProxy challenge), and Vault, Nomad and Consul.

[ADR 0009](/decisions/0009-openviking-has-no-browser-surface.md) records
why OpenViking lost its proxy, and port 4182 now belongs to ov-dash.

## The oauth2-proxy jobs

- **Reverse-proxy mode.** HAProxy has no `auth_request`. Forward-auth would
  need SPOE or Lua, so L1 made oauth2-proxy the backend itself, holding the
  upstreams (L1 plan, Q2).
- **On radxa, not firebat.** firebat had about 100 MHz of reservable CPU
  left when L1 ran. The upstreams are loopback addresses to tasks on the
  same node (dash on 8000 and 8001, registry-ui on 8002 and 8003). The dash
  and registry-ui jobs live in `deployments/applications`, so the port
  numbers are literals agreed across two roots with no reference between
  them ([Terraform roots](/components/terraform-roots.md)). A path-scoped
  upstream matches exactly, not as a prefix
  (`docs/explanation/dash-routing.md`, [dash](/components/dash.md)).
- **One client, two jobs.** `vault_identity_oidc_client.oauth2_proxy` holds
  both redirect URIs and both jobs use its credentials. The secrets are
  written twice, under `default/oauth2-proxy/*` and
  `default/oauth2-proxy-registry-ui/*`, because `nomad-workloads` scopes a
  read to the job's own ID. The registry-ui proxy's first deploy failed on
  exactly that 403.
- **Who gets in is decided at Vault.** Neither proxy filters
  (`EMAIL_DOMAINS="*"`, no allowed group). The client names the `operators`
  assignment, so a person in neither operator group fails at Vault's
  authorize step. It was `allow_all` until OpenViking consumers got Vault
  identities. The clients and assignments are in
  [the Vault OIDC provider](/components/vault-oidc-provider.md).
- **Settings that validate while wrong.** The header of `oauth2-proxy.hcl`
  lists seven: plural env names, `SKIP_PROVIDER_BUTTON` pinned `false`,
  `OIDC_EMAIL_CLAIM="sub"` because only `openid` is requested,
  `PROVIDER="oidc"`, a `0.0.0.0` bind, and the `/ping` health check. `REVERSE_PROXY` stays unset because HAProxy sends no
  `X-Forwarded-*` to these backends. The cookie secret is 32 alphanumerics,
  which oauth2-proxy base64-decodes to 24 bytes, a legal size.
- `scripts/check_oauth2_proxy_guard.py` refuses a skip-auth key in either
  jobspec. Commit `f197702` removed its pre-commit hook, so nothing runs it
  today.

## The edge is on the auth path

Vault's OIDC issuer is `https://vault.lab.orangecluster.nl`
(`var.vault_issuer_host`), and MinIO reads Nomad's discovery document through
`https://nomad.lab.orangecluster.nl`. An edge outage therefore breaks token
verification as well as browsers. The ACME job writes to Vault on the direct
listener for the same reason: renewal must not depend on the certificate it
renews. `localstack breakglass` lists the direct addresses for when the edge
is the thing that broke.

## Lab DNS

The lab zone has no machinery in this repository. Two public A records point
at `192.168.2.30` ([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md)),
and `.consul` is not forwarded
([ADR 0004](/decisions/0004-consul-names-are-not-forwarded.md)). F4 planned a
dnsmasq resolver for `.localstack` and was dropped. T2 built it for the lab
zone, and N2 removed it the same day, reversing T2 on purpose. The only
residue was ufw's port 53 rule on firebat, which Terraform could not delete.
Records are `docs/reference/dns.md`.

## History

- `1507226` put HAProxy on host networking and started Terraform firewall
  rules.
- F3 added TLS with a Vault PKI leaf for `*.localstack`, which no client
  accepts ([edge certificate names](/practices/edge-certificate-names.md)).
- T3 cut over to the Let's Encrypt wildcard in one apply, renamed every host
  and destroyed the PKI mount. T4 re-pinned the acme and dnsmasq images by
  digest alone, because the podman driver rejects a tag plus a digest.
- L1 added the dash gate, and L5 copied it for registry-ui.

## Checks

No gate renders `haproxy.hcl`. F3, T3 and the N1 follow-on each rendered the
config, ran `haproxy -c` in `haproxy:3.1-alpine`, and ran negative controls
first. Repeat that before applying a config change. T5, the certificate
expiry alert, is blocked and nothing measures days to expiry. N4, which would
leave the edge as the only way into each service, is still in planning.
