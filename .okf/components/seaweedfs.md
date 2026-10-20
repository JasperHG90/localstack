---
type: component
title: SeaweedFS
description: "The single-node SeaweedFS on orangepi4a that replaces MinIO: one weed server with its S3 gateway, run by the infrastructure root beside MinIO until the cutover, with six buckets and per-user keys from the applications root. Only S3 and metrics leave the host, and the volume growth and IAM flags its spikes proved are pinned by a drift test."
tags: [seaweedfs, s3, object-storage, terraform, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-10-19
sources:
  - id: seaweedfs-jobspec
    resource: deployments/infrastructure/services/seaweedfs.hcl
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: jobspec-test
    resource: cli/tests/test_seaweedfs_jobspec.py
  - id: app-storage
    resource: deployments/applications/storage.tf
  - id: app-providers
    resource: deployments/applications/providers.tf
  - id: app-secrets
    resource: deployments/applications/secrets.tf
  - id: buckets-test
    resource: cli/tests/test_seaweedfs_buckets.py
---

# SeaweedFS

MinIO is end of life and its published image no longer downloads, so the
cluster moves its object storage to SeaweedFS
([ADR 0016](/decisions/0016-seaweedfs-replaces-minio.md)). This page covers
the server and its buckets. Keyless access and the cutover come in later
tickets of the `seaweedfs-migration` epic. Until the cutover MinIO keeps serving every
consumer and keeps the `s3` Consul tag ([MinIO](/components/minio.md)).

## What runs

`nomad_job.seaweedfs` in `deployments/infrastructure/services.tf` runs one
`weed server` (master, volume, filer and S3 gateway in one process) from
`docker.io/chrislusf/seaweedfs:4.48`, pinned to orangepi4a, on the
`seaweedfs_data` dynamic host volume. The admin identity is read from
`default/seaweedfs/admin` and rendered into the file passed to
`-s3.config`. The embedded IAM API shares the S3 port, 8333. Prometheus
scrapes `/metrics` on 9327. The Consul check is `GET /healthz` on 8333.

## Buckets and users

The applications root manages them with the `hashicorp/aws` provider, whose S3
and IAM endpoints are SeaweedFS's port 8333. The minio provider's IAM
resources fail against SeaweedFS (`spike:seaweedfs-buckets/2`). The provider
finds the server through `data "consul_service" "seaweedfs"`, which the
brokered `deploy` Consul token may read because
`bootstrap/playbooks/enable_consul_secrets.yml` grants it, and logs in with
the admin key.

`storage.tf` derives everything from MinIO's `local.buckets`: six buckets
(memex and mlflow-artifacts are not recreated), one IAM user per MinIO user
with the same writer or reader split and MinIO's exact action sets from
`modules/bucket`, and a `backup` user that reads and lists the four durable
buckets. Readers get `s3:GetBucketLocation` and `s3:GetObject` but cannot
list, as on MinIO. Only the backup user adds `s3:ListBucket`, because rclone
lists to sync.
`secrets.tf` writes each job's key to `default/<job>/seaweedfs` beside its
MinIO key, and the backup key to `default/backup-minio/seaweedfs`.
`cli/tests/test_seaweedfs_buckets.py` pins the bucket set, the derivation and
the action sets against MinIO's. The live isolation checks are in
`spike:seaweedfs-buckets/3` and `spike:seaweedfs-buckets/4`.

## Traps

- **Only S3 and metrics may leave the host.** Master, volume and filer bind
  to loopback (`-ip.bind=127.0.0.1`), because the filer's IAM gRPC has no
  auth unless `jwt.filer_signing.key` is set, and the worker base rule
  already opens 20000:32000 to the LAN. The S3 gRPC port, 18333, follows
  `-s3.ip.bind` and cannot be turned off, so no Nomad port and no firewall
  rule may name it.
- **Volume growth.** S3 puts each bucket in its own collection, and the
  master's default `copy_1 = 7` grows seven volumes per collection: only
  four of six buckets took a first write in a spike. The jobspec renders a
  `master.toml` with `copy_1 = 2` and uses 1 GiB volumes with
  `-volume.max=0`, so the slot count follows free disk.
- **The IAM API is read-only by default.** Without `-s3.iam.readOnly=false`
  every IAM write fails with 403, including Terraform's.
- **No memory to spare on orangepi4a.** With MinIO (2560 MB), ov-dash
  (512 MB), alloy and the worker reservation, the node had under 128 MB
  unreserved, and the job could not place. `ov-dash` is stopped until
  `minio-removal` frees MinIO's share and starts it again
  (`spike:seaweedfs-service/4`) with `nomad job start ov-dash`. An
  applications-root apply leaves the stopped job alone.
- **Ed25519 keys.** SeaweedFS parses RSA and EC JWKS keys only. Nomad signs
  workload identities with RS256 today. If it ever adds an EdDSA key,
  SeaweedFS rejects the tokens it signs.

`cli/tests/test_seaweedfs_jobspec.py` pins the image floor (4.40 fixes
CVE-2026-77298), every flag above, the growth setting, the two mapped ports,
and the absence of the `s3` tag.
