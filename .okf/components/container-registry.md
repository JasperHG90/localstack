---
type: component
title: Container registry
description: "The OCI registry on ubuntu stores every blob in the registry MinIO bucket, authenticates with one htpasswd user, and is reachable only through the HAProxy edge. It serves KitOps ModelKits to embark today. No job pulls a container image from it, and podman rejects a tag-plus-digest image reference."
tags: [registry, oci, kitops, modelkit, podman, minio, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: registry-jobspec
    resource: git:3ec5d1e:deployments/applications/services/registry.hcl
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: haproxy
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: embark-jobspec
    resource: git:3ec5d1e:deployments/applications/services/embark.hcl
  - id: embark-pull
    resource: git:3ec5d1e:deployments/applications/services/embark/pull.sh
  - id: registry-commit
    resource: git:f1091dc
  - id: relativeurls-commit
    resource: git:b9dbaf1
  - id: T4-tls-fix-podman-image-digest-refs
    resource: loop:T4-tls-fix-podman-image-digest-refs
  - id: R13-rollout-loki-registry-keyless-minio
    resource: loop:R13-rollout-loki-registry-keyless-minio
---

# Container registry

A `registry:3.1.1` (CNCF distribution) job with no local state. The browsing
UI is a separate service: `docs/reference/registry-ui.md` for users, and
[registry-ui](/components/registry-ui.md) for how it is built.

## The pieces

| Piece | Where |
| --- | --- |
| Job `registry`, pinned to ubuntu, ports 5000 (API) and 5001 (debug) | `deployments/applications/services/registry.hcl` |
| `nomad_job.registry`, `depends_on` the claim-mode policy | `deployments/applications/services.tf` |
| Firewall: 5000 from HAProxy (.30) only, 5001 closed | `local.firewall_rules["registry"]`, same file |
| Bucket `registry` and claim-mode policy `registry` | `deployments/applications/storage.tf` |
| Push credential `random_password.registry_push`, KV `default/registry/auth` | `deployments/applications/secrets.tf` |
| Copies for pullers: `default/embark/registry`, `default/registry-ui/registry` | same file |
| Edge route `registry.lab.orangecluster.nl`, `backend registry` | `deployments/infrastructure/services/haproxy.hcl` |

The job is in the applications root because its bucket and policy are.
HAProxy is in the infrastructure root and points at `192.168.2.47:5000` as a
literal, so moving the job off ubuntu means editing the other root too.

## Why it is shaped this way

- **The edge is the only way in.** podman and docker refuse a plain-HTTP
  registry, and no node manages `registries.conf`, so HAProxy's TLS is what
  makes clients trust it. The firewall admits HAProxy alone.
- **htpasswd, not OIDC.** The OCI distribution spec offers htpasswd or a
  Docker-specific token server. oauth2-proxy would break every machine client,
  since podman cannot follow a browser redirect (f1091dc). HAProxy adds no
  auth of its own for the same reason.
- **ubuntu, not firebat.** firebat, HAProxy's node, is committed to about
  3100 MHz by Postgres and HAProxy, and the scheduler refused it. Sitting next
  to MinIO would not help, since each blob crosses the wire once either way.
- **Keyless MinIO access.** Since R13 the S3 driver gets short-lived
  credentials from `local/minio-creds.sh`, a `credential_process` helper that
  trades the job's Nomad JWT at MinIO's STS. Mechanism and helper contract:
  `docs/how-to/give-an-aws-sdk-go-service-keyless-minio-access.md`. The job
  keeps `vault {}` because the htpasswd still comes from Vault.

## One user for everything

The htpasswd file has one user, `push`. embark and registry-ui only read, but
their KV copies carry the same password, so each holds push rights. Rotating
means tainting `random_password.registry_push`: the registry reads htpasswd
as a file at start, so the new hash reaches it through a restart, and all
three KV entries change in the same apply.

`bcrypt_hash` is an attribute of `random_password`, computed once and kept in
state. The `bcrypt()` function would re-salt on every plan, rewrite the secret
and restart the registry on every apply.

## What it holds and who pulls

Its one machine client is embark's `model-pull` prestart task, which unpacks
KitOps ModelKits listed in
`deployments/applications/services/embark/models.json`. How that pull works
and its traps are in [embark](/components/embark.md). registry-ui also reads
the registry.

No jobspec pulls a container image from this registry. Task images come from
`ghcr.io`, `docker.io` and `quay.io`. The dash tile documents `podman push` and
`kit push` for people.

## Traps

- **Large pushes and TLS.** Behind HAProxy the registry built absolute
  `Location` URLs with `http`. The client followed them back to `https`,
  dropped `Authorization` on the scheme change, and every chunked upload
  failed as "authentication required" while small blobs worked.
  `relativeurls: true` fixes it, and HAProxy's `X-Forwarded-Proto` fixes it
  again independently (b9dbaf1).
- **Finalizing is silent.** HAProxy's `timeout server 1800s` covers the pause
  while the registry finalizes a multi-GB multipart upload into MinIO. The
  300s default is an inactivity timer, which a streaming push resets.
- **Health on the debug port.** With htpasswd on, `/v2/` answers 401, which
  Consul reads as critical, so the check hits `/debug/health` on 5001.
- **Deleting a tag frees nothing.** `delete.enabled` allows
  `registry garbage-collect`, and no job runs it.
- **Double escaping in the helper.** The helper passes through Terraform's
  `templatefile` and then Nomad's template engine. Escape `${` as `$${` and
  leave every other `$` alone. A `$$1` reached the shell as PID-then-1 in R13.
- **Two MinIO addresses.** The helper uses `minio_host` from Consul, the
  storage block a literal `192.168.2.29`.
- **Not backed up.** `backup-minio` syncs only `openviking`, so every image and
  ModelKit exists only on orangepi4a.

## Image references in jobspecs (T4)

The podman driver rejects `name:tag@sha256:...`. It first parses the string as
a transport name, fails, retries as `docker://<ref>`, and containers/image
then refuses a reference that has both a tag and a digest. The first error is
the one shown, so the message reads `unsupported transport`. `terraform
validate`, `nomad fmt` and `nomad job validate` all accept the string. Only
the driver rejects it, at pull time.

Pin by digest alone with the version in a comment, as `acme.hcl` does, or by
tag alone, as every other jobspec does.
