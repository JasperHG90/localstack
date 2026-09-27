# How to add a service to the edge

## Introduction

This gives a Nomad service an `https://<name>.lab.orangecluster.nl` route
through the HAProxy edge, with a trusted certificate and no DNS change.

## Prerequisites

- The service's node address and port.
- A Terraform setup that can run `just apply` in
  `deployments/infrastructure/`.
- A hostname with exactly one label in front of `lab.orangecluster.nl`, see
  step 1.

## Directions

### Step 1: Add the route to the HAProxy config template

Add an ACL, a `use_backend` and a backend to the HAProxy config template in
`deployments/infrastructure/services/haproxy.hcl`. The ACL goes on the
`https_in` frontend: `http_in` only redirects, so an ACL placed there can
never route.

```
    acl is_myservice hdr(host) -i myservice.lab.orangecluster.nl
    use_backend myservice if is_myservice

backend myservice
    server myservice1 <ip>:<port> check
```

No DNS record and no certificate change is needed, as long as the name has
exactly one label in front of `lab.orangecluster.nl`. The wildcard covers
`myservice.lab.orangecluster.nl` including names that do not exist yet, but
it does **not** cover `myservice.staging.lab.orangecluster.nl`. A TLS
wildcard matches a single label, while the DNS wildcard matches at any depth,
so a two-label name resolves and the edge answers it while the certificate
fails to validate. Keep new hostnames flat, or the certificate needs a new
SAN.

### Step 2: Apply the infrastructure root

Run `just apply` from `deployments/infrastructure/`.

## Additional resources

- [Edge routes, ports and files](../reference/edge-routes.md)
- [DNS for the lab zone](../reference/dns.md)
- [TLS certificates](../reference/tls-certificates.md)
