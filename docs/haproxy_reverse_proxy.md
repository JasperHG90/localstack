# HAProxy Reverse Proxy

HAProxy runs as a Nomad job on `firebat` (192.168.2.30) and is the single
HTTPS entry point for the cluster, routing by hostname. It terminates TLS with
a publicly-trusted Let's Encrypt wildcard certificate, so browsers trust it
with nothing installed on the client.

## Service Routes

Every route is `https://<name>`. Plain HTTP on port 80 answers only with a 301
to the HTTPS URL.

| Hostname | Backend | Port |
|---|---|---|
| `minio.lab.orangecluster.nl` | orangepi4a (192.168.2.29) | 9001 (console) |
| `s3.lab.orangecluster.nl` | orangepi4a (192.168.2.29) | 9000 (API) |
| `vault.lab.orangecluster.nl` | firebat (192.168.2.30) | 8200 |
| `nomad.lab.orangecluster.nl` | firebat (192.168.2.30) | 4646 |
| `consul.lab.orangecluster.nl` | firebat (192.168.2.30) | 8500 |
| `phoenix.lab.orangecluster.nl` | orangepi4a (192.168.2.29) | 6006 |
| `memex.lab.orangecluster.nl` | jetson-orin-nano (192.168.2.46) | 8000 |
| `grafana.lab.orangecluster.nl` | ubuntu (192.168.2.47) | 3000 |
| `bifrost.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 8080 |

`phoenix` sits behind HTTP basic auth. `bifrost` authenticates
with its own native `governance.auth_config` (admin creds from Vault), so
HAProxy no longer gates it. The rest are open to anyone who reaches the edge.

**Prometheus and Loki are deliberately not routed here.** Both serve their
query APIs with no authentication, and nothing needs them through the proxy:
Grafana's datasources dial `192.168.2.47` directly from the same node, and
promtail pushes straight to Loki. Routing them would have meant every metric
and every log line readable by anyone who can reach the edge, to save a
browser tab. To reach either one while debugging, use an SSH tunnel: see
*Reaching Prometheus or Loki directly* in `docs/monitoring.md`.

The stats dashboard is at `http://192.168.2.30:8404`, outside the TLS
frontend.

## Ports

- **80** HTTP, 301-redirects everything to HTTPS
- **443** HTTPS, terminates TLS and does all hostname routing
- **8404** stats dashboard

## DNS

Nothing to configure. `*.lab.orangecluster.nl` and the bare
`lab.orangecluster.nl` resolve from public DNS to `192.168.2.30`, so any
device reaches the cluster through whatever resolver it already uses,
including phones and guests. No `/etc/hosts` entries, no local resolver.

The address is private, so the names only work from the LAN or over
Tailscale's subnet route (`192.168.2.0/24`). Resolving from elsewhere returns
an address that goes nowhere. See `docs/dns.md`.

## TLS

The certificate is a Let's Encrypt wildcard covering `*.lab.orangecluster.nl`
and the bare `lab.orangecluster.nl`, issued over DNS-01 by the `acme` job and
stored in Vault at `secret/default/haproxy/tls`. HAProxy reads it from there
with a Vault template, concatenates the certificate and key into the single
PEM its `crt` argument expects, and restarts when the stored secret changes.

Renewal is automatic. `docs/tls-certificates.md` covers issuance, the storage
format, and what to check when a renewal does not land.

## PostgreSQL

PostgreSQL is not routed through HAProxy. The proxy runs in HTTP mode and has
no TCP frontend, so there is no `postgres` hostname. Connect to the node
directly:

```bash
psql -h 192.168.2.30 -p 5432 -U <user> -d <database>
```

This works on the LAN and over Tailscale's subnet route. PostgreSQL runs on
firebat, the same host as HAProxy, so proxying it would mean a second port for
no benefit.

## Adding a New Service

1. Add an ACL, a `use_backend` and a backend to the HAProxy config template in
   `deployments/infrastructure/services/haproxy.hcl`. The ACL goes on the
   `https_in` frontend: `http_in` only redirects, so an ACL placed there can
   never route.

```
    acl is_myservice hdr(host) -i myservice.lab.orangecluster.nl
    use_backend myservice if is_myservice

backend myservice
    server myservice1 <ip>:<port> check
```

2. Run `just apply` from `deployments/infrastructure/`.

No DNS record and no certificate change is needed, as long as the name has
exactly one label in front of `lab.orangecluster.nl`. The wildcard covers
`myservice.lab.orangecluster.nl` including names that do not exist yet, but
it does **not** cover `myservice.staging.lab.orangecluster.nl`. A TLS
wildcard matches a single label, while the DNS wildcard matches at any depth,
so a two-label name resolves and the edge answers it while the certificate
fails to validate. Keep new hostnames flat, or the certificate needs a new
SAN.

The edge's previous certificate failed for a different reason worth knowing:
it was issued for `*.localstack`, and a wildcard has to sit at least two
labels above the root. `grafana.localstack` was already flat and still no
client would accept it. Flat names are necessary, not sufficient, and the
domain underneath has to be a real one.

## Files

- `deployments/infrastructure/services/haproxy.hcl` — Nomad job spec with the
  embedded HAProxy config and the certificate template
- `deployments/infrastructure/services.tf` — Terraform resource that deploys
  the job
