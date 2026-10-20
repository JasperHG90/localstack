---
type: component
title: Container registry
description: "The OCI registry on ubuntu stores every blob in the registry SeaweedFS bucket, authenticates with one htpasswd user, and is reachable only through the HAProxy edge. It serves KitOps ModelKits to embark today. No job pulls a container image from it, and podman rejects a tag-plus-digest image reference."
tags: [registry, oci, kitops, modelkit, podman, seaweedfs, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: registry-jobspec
    resource: deployments/applications/services/registry.hcl
  - id: app-services
    resource: deployments/applications/services.tf
  - id: app-secrets
    resource: deployments/applications/secrets.tf
  - id: app-storage
    resource: deployments/applications/storage.tf
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: haproxy
    resource: deployments/infrastructure/services/haproxy.hcl
  - id: embark-jobspec
    resource: deployments/applications/services/embark.hcl
  - id: embark-pull
    resource: deployments/applications/services/embark/pull.sh
---

# Container registry

A `registry:3.1.1` (CNCF distribution) job with no local state. The browsing
UI is a separate service: `docs/reference/registry-ui.md` for users, and
[registry-ui](/components/registry-ui.md) for how it is built.

## The pieces

| Piece | Where |
| --- | --- |
| Job `registry`, pinned to ubuntu, ports 5000 (API) and 5001 (debug) | `deployments/applications/services/registry.hcl` |
| `nomad_job.registry`, given SeaweedFS's address from `data.consul_service.seaweedfs` | `deployments/applications/services.tf` |
| Firewall: 5000 from HAProxy (.30) only, 5001 closed | `local.firewall_rules["registry"]`, same file |
| SeaweedFS bucket `registry` | `aws_s3_bucket.seaweedfs` in `deployments/applications/storage.tf` |
| SeaweedFS role `registry` | `local.seaweedfs_keyless_jobs` in `deployments/infrastructure/services.tf` |
| Push credential `random_password.registry_push`, KV `default/registry/auth` | `deployments/applications/secrets.tf` |
| Copies for pullers: `default/embark/registry`, `default/registry-ui/registry` | same file |
| Edge route `registry.lab.orangecluster.nl`, `backend registry` | `deployments/infrastructure/services/haproxy.hcl` |

The job is in the applications root because its bucket is.
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
  to SeaweedFS would not help, since each blob crosses the wire once either
  way.
- **Keyless SeaweedFS access.** The S3 driver gets short-lived credentials
  from `local/s3-creds.sh`, a `credential_process` helper that trades the
  job's `seaweedfs` identity (JWT at `/secrets/nomad_seaweedfs.jwt`) at
  SeaweedFS's STS on port 8333. It sends
  `RoleArn=arn:aws:iam::role/registry` and `RoleSessionName=registry`, and
  the role's trust policy admits only this job
  ([ADR 0017](/decisions/0017-seaweedfs-keyless-roles-bound-per-job.md)).
  Helper contract:
  `docs/how-to/give-an-aws-sdk-go-service-keyless-minio-access.md`. The job
  keeps `vault {}` because the htpasswd still comes from Vault. Static
  keys at `default/registry/seaweedfs` and the older `default/registry/minio`
  stay provisioned as rollback paths, and no job reads them. The registry was
  keyless on MinIO from R13 until 2026-10-20, through the same helper under
  the name `minio-creds.sh`.

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
  while the registry finalizes a multi-GB multipart upload into SeaweedFS.
  The 300s default is an inactivity timer, which a streaming push resets.
  The comment beside it in `haproxy.hcl` still says MinIO.
- **Pulls go to SeaweedFS directly.** A blob GET answers with a redirect to a
  presigned SeaweedFS URL on port 8333, signed with the STS session
  credentials, so a puller must reach orangepi4a on 8333 as well as the edge.
  The firewall opens 8333 to `192.168.0.0/16` only.
- **Health on the debug port.** With htpasswd on, `/v2/` answers 401, which
  Consul reads as critical, so the check hits `/debug/health` on 5001.
- **Deleting a tag frees nothing.** `delete.enabled` allows
  `registry garbage-collect`, and no job runs it.
- **Double escaping in the helper.** The helper passes through Terraform's
  `templatefile` and then Nomad's template engine. Escape `${` as `$${` and
  leave every other `$` alone. A `$$1` reached the shell as PID-then-1 in R13.
- **The helper must name the role.** SeaweedFS refuses an exchange without
  `RoleArn` and `RoleSessionName`. Both the helper and `regionendpoint` take
  `s3_host` from Consul, so the job names no address by hand.
- **No off-site copy of new pushes yet.** `backup-minio` still syncs MinIO's
  `registry` bucket, which gets no writes since 2026-10-20, so anything pushed
  after the cutover has no GCS copy until the backup reads SeaweedFS
  (`seaweedfs-cutover`).

## The move to SeaweedFS (2026-10-20)

The registry was stopped, `backup-minio` forced, and `restore-s3` dispatched
for `registry` ([GCS backups](/components/gcs-backups.md)). The restore
writes a zero-byte `dir/` key for every directory in GCS, 725 of them, which
the registry never had on MinIO. They were deleted before the registry
started again, so the bucket holds what MinIO held. All 33 tags read back
unchanged and a new push worked (`spike:seaweedfs-cutover-registry/2`). An
earlier spike pushed, served and garbage-collected on SeaweedFS with only the
role's credentials (`spike:seaweedfs-cutover-registry/1`). MinIO's `registry`
bucket is left as it was.

## Image references in jobspecs (T4)

The podman driver rejects `name:tag@sha256:...`. It first parses the string as
a transport name, fails, retries as `docker://<ref>`, and containers/image
then refuses a reference that has both a tag and a digest. The first error is
the one shown, so the message reads `unsupported transport`. `terraform
validate`, `nomad fmt` and `nomad job validate` all accept the string. Only
the driver rejects it, at pull time.

Pin by digest alone with the version in a comment, as `acme.hcl` does, or by
tag alone, as every other jobspec does.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- commit `f1091dc`
- commit `b9dbaf1`
- loop ticket `T4-tls-fix-podman-image-digest-refs` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R13-rollout-loki-registry-keyless-minio` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R11-rollout-registry-keyless-minio`, a stub R13 superseded (its plan is in `.loop/plans/` in git history before `5b2ed1b`)
- loop ticket `seaweedfs-cutover-registry` (its plan, spikes and verdicts are under `.loop/`)
