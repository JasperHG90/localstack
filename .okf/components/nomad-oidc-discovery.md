---
type: component
title: Nomad's OIDC discovery document, and why MinIO waited for it
description: "F1 delivered only Nomad's JWKS URL. MinIO's identity_openid needs an OIDC discovery document, which F10 turned on by setting server.oidc_issuer, so M1 and R5 could point at the issuer directly."
tags: [nomad, workload-identity, oidc, minio, history]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: nomad-server-template
    resource: bootstrap/roles/nomad_server/templates/nomad.hcl.j2
  - id: hashistack-server-playbook
    resource: bootstrap/playbooks/configure_hashistack_server.yml
  - id: infra-services
    resource: deployments/infrastructure/services.tf
---

# Nomad's OIDC discovery document, and why MinIO waited for it

Carved from the "What F1 delivers for M1, and what it does not" section of
the old `docs/workload-identity.md`. The chain it describes is
`docs/explanation/workload-identity.md`.

## What F1 delivers for M1, and what it does not

F1 delivered the **JWKS URL** (`http://192.168.2.30:4646/.well-known/jwks.json`)
and nothing more. Its scope was JWKS only. It did not deliver an OIDC
discovery document, which is what MinIO actually needs, so M1 could not
proceed on F1 alone.

**F10 has since enabled discovery**, so the rest of this section describes
history, not current state. Nomad now serves a discovery document at the
configured issuer:

```
curl -sk https://nomad.lab.orangecluster.nl/.well-known/openid-configuration
{"issuer":"https://nomad.lab.orangecluster.nl",
 "jwks_uri":"https://nomad.lab.orangecluster.nl/.well-known/jwks.json",
 "id_token_signing_alg_values_supported":["RS256","EdDSA"], ...}
```

MinIO's `identity_openid` consumes a discovery document
(`MINIO_IDENTITY_OPENID_CONFIG_URL`), not a bare JWKS, which is why it had to
wait. Enabling discovery meant setting `server { oidc_issuer = ... }` in the
Nomad server config and restarting the single Nomad server. That was
`F10-foundation-nomad-oidc-issuer`, and it is done. The issuer is
`nomad_oidc_issuer` in `bootstrap/playbooks/configure_hashistack_server.yml`,
rendered by `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`. MinIO read
the discovery URL as `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD` in `minio.hcl`
until it was removed on 2026-10-20
([ADR 0018](/decisions/0018-remove-minio.md)). A verifier that needs
discovery (memex in R5, MinIO in M1) can point at the issuer directly.
SeaweedFS, MinIO's successor, names the issuer in its IAM config from
`local.seaweedfs_iam` in `deployments/infrastructure/services.tf`.
