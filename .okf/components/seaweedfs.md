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
  - id: loki-jobspec
    resource: deployments/applications/services/loki.hcl
  - id: tempo-jobspec
    resource: deployments/applications/services/tempo.hcl
  - id: registry-jobspec
    resource: deployments/applications/services/registry.hcl
  - id: alert-rules
    resource: deployments/infrastructure/services/grafana/alert-rules.yaml
---

# SeaweedFS

MinIO is end of life and its published image no longer downloads, so the
cluster moves its object storage to SeaweedFS
([ADR 0016](/decisions/0016-seaweedfs-replaces-minio.md)). This page covers
the server, its buckets, keyless access and who has moved. The cutover runs
one consumer at a time in the tickets of the `seaweedfs-migration` epic.

OpenViking was first: since 2026-10-20 its blobs are in the `openviking`
bucket here, and it finds the S3 port through Consul service `seaweedfs`
([the OpenViking service](/components/openviking-service.md)). The `models`
and `datalake` buckets were restored from GCS at the same time, both empty.
Loki, Tempo and the OCI registry moved the same day, so no workload uses
MinIO any more. Only `backup-minio` still reads it, and MinIO keeps the `s3`
Consul tag and edge route, until `seaweedfs-cutover`
([MinIO](/components/minio.md)).

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
lists to sync. A `restore` user has `s3:*` on the same four buckets, for the
`restore-s3` job ([GCS backups](/components/gcs-backups.md)), and goes with
MinIO in `minio-removal`.
`secrets.tf` writes each job's key to `default/<job>/seaweedfs` beside its
MinIO key, the backup key to `default/backup-minio/seaweedfs`, and the
restore key to `default/restore-s3/seaweedfs`.
`cli/tests/test_seaweedfs_buckets.py` pins the bucket set, the derivation and
the action sets against MinIO's. The live isolation checks are in
`spike:seaweedfs-buckets/3` and `spike:seaweedfs-buckets/4`.

## Keyless access

The job renders a second config file, `secrets/iam.json`, passed with
`-s3.iam.config`: Nomad's issuer as an OIDC provider with audience
`seaweedfs`, one role and policy per entry in `local.seaweedfs_keyless_jobs`
(`deployments/infrastructure/services.tf`), `defaultEffect: Deny`, and the STS
signing key from `default/seaweedfs/sts`. Each role is bound to its job by
`nomad_job_id` and `sub`
([ADR 0017](/decisions/0017-seaweedfs-keyless-roles-bound-per-job.md)).
`cli/tests/test_seaweedfs_iam_config.py` renders the file through Terraform
and checks it. Adding a job means a restart, because the server reads the file
once at start.

## Who uses it

Loki and Tempo store in their `loki` and `tempo` buckets here since
2026-10-20 ([the observability pipeline](/components/observability-pipeline.md)).
Both log in keylessly with a `seaweedfs` identity whose JWT is at
`secrets/nomad_seaweedfs.jwt`, and both find the server through
`data.consul_service.seaweedfs`, passed to the jobspec as `s3_host`. Tempo
sets `AWS_ROLE_ARN = "arn:aws:iam::role/tempo"` and points minio-go's
`TEST_IAM_ENDPOINT` at `http://<s3_host>:8333`. Without the role ARN
minio-go sends no `RoleArn`, SeaweedFS has nothing to resolve, and minio-go
falls back to anonymous S3 with no error. Loki's `credential_process` helper,
`local/s3-creds.sh`, POSTs `RoleArn=arn:aws:iam::role/loki` and
`RoleSessionName=loki` to the same STS. Their static keys at
`default/loki/seaweedfs` and `default/tempo/seaweedfs` are the rollback path
and are not rendered into the jobs.

The `loki` and `tempo` buckets started empty. Logs and traces written before
the cutover stay in MinIO's `loki` and `tempo` buckets, unread, until MinIO
is removed. The operator chose not to migrate them.

The OCI registry stores in the `registry` bucket here since 2026-10-20
([container registry](/components/container-registry.md)). It logs in the
same way as loki: a `seaweedfs` identity, the JWT at
`secrets/nomad_seaweedfs.jwt`, and a `local/s3-creds.sh` helper that POSTs
`RoleArn=arn:aws:iam::role/registry` and `RoleSessionName=registry`. Its
`regionendpoint` is `http://<s3_host>:8333`, from the same Consul lookup.
Its bucket was restored from GCS, not started empty, and the 725 zero-byte
`dir/` markers the restore wrote were deleted afterwards. Its static key at
`default/registry/seaweedfs` is a rollback path the job does not read.

## Monitoring

Grafana has a SeaweedFS dashboard (`services/grafana/seaweedfs.json` in the
infrastructure root). Two alerts in
`deployments/infrastructure/services/grafana/alert-rules.yaml` watch it:
`SeaweedFSDown` fires when Prometheus cannot scrape 9327 for 5 minutes, and
`SeaweedFSDiskError` fires when the volume server marks a disk in error.
`ScrapeJobMissing` also fires if the `seaweedfs` scrape job disappears.

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
