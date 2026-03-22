# HAProxy Reverse Proxy

HAProxy runs as a Nomad job on `firebat` (192.168.2.30) and provides a unified HTTP entry point for all cluster services via hostname-based routing.

## Service Routes

| Hostname | Backend | Port |
|---|---|---|
| `minio.localstack` | orangepi4a (192.168.2.29) | 9001 (console) |
| `s3.localstack` | orangepi4a (192.168.2.29) | 9000 (API) |
| `vault.localstack` | firebat (192.168.2.30) | 8200 |
| `nomad.localstack` | firebat (192.168.2.30) | 4646 |
| `consul.localstack` | firebat (192.168.2.30) | 8500 |

The stats dashboard is available at `http://192.168.2.30:8404`.

## Ports

- **80** — HTTP entry point (mapped to 8080 inside the container to avoid privileged port binding)
- **8404** — HAProxy stats dashboard

## DNS Setup

Your client machine needs `*.localstack` resolving to `192.168.2.30`. Add these entries to `/etc/hosts` on your Mac:

```
192.168.2.30 minio.localstack s3.localstack vault.localstack nomad.localstack consul.localstack postgres.localstack
```

If connecting remotely via Tailscale, traffic routes through firebat's subnet route (`192.168.2.0/24`).

## PostgreSQL

HAProxy supports TCP proxying, but PostgreSQL already runs on firebat (192.168.2.30:5432) — the same host as HAProxy. Since HAProxy can't bind to a port already in use, and using an alternative port (e.g. 15432) would add complexity without benefit, connect to PostgreSQL directly:

```
psql -h postgres.localstack -p 5432 -U <user> -d <database>
```

This works both on LAN and remotely via Tailscale's subnet route. If PostgreSQL moves to a different node in the future, it can be added as a TCP frontend in HAProxy.

## Adding a New Service

1. Add ACL and backend entries in the HAProxy template inside `deployments/infrastructure/services/haproxy.hcl`:

```
    acl is_myservice hdr(host) -i myservice.localstack
    use_backend myservice if is_myservice

backend myservice
    server myservice1 <ip>:<port> check
```

2. Add the hostname to your `/etc/hosts`.
3. Run `just apply` from `deployments/infrastructure/`.

## Files

- `deployments/infrastructure/services/haproxy.hcl` — Nomad job spec with embedded HAProxy config
- `deployments/infrastructure/services.tf` — Terraform resource that deploys the job
