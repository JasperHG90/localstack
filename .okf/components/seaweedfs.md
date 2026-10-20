---
type: component
title: SeaweedFS
description: "The single-node SeaweedFS on orangepi4a that replaced MinIO on 2026-10-20: one weed server with its S3 gateway, run by the infrastructure root, with seven buckets and per-user keys from the applications root. It is the cluster's only S3 store and carries the s3 Consul tag, the s3.lab edge route and the nightly backup. Only S3 and metrics leave the host, and the volume growth and IAM flags its spikes proved are pinned by a drift test."
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
  - id: cutover-test
    resource: cli/tests/test_s3_cutover.py
  - id: haproxy-jobspec
    resource: deployments/infrastructure/services/haproxy.hcl
---

# SeaweedFS

MinIO is end of life and its published image no longer downloads, so the
cluster moved its object storage to SeaweedFS
([ADR 0016](/decisions/0016-seaweedfs-replaces-minio.md)). This page covers
the server, its buckets, keyless access and who uses it. The cutover ran
one consumer at a time in the tickets of the `seaweedfs-migration` epic.

OpenViking was first: since 2026-10-20 its blobs are in the `openviking`
bucket here, and it finds the S3 port through Consul service `seaweedfs`
([the OpenViking service](/components/openviking-service.md)). The `models`
and `datalake` buckets were restored from GCS at the same time, both empty.
Loki, Tempo and the OCI registry moved the same day. Then `seaweedfs-cutover`
moved the rest: the nightly backup reads the durable buckets from here
([GCS backups](/components/gcs-backups.md)), the `seaweedfs` service carries
the `s3` Consul tag, so the CLI's `s3` route resolves here, HAProxy's
`s3.lab.orangecluster.nl` backend points at `192.168.2.29:8333`, and the dash
tile is `seaweedfs`. `minio-removal` then removed MinIO the same day
([ADR 0018](/decisions/0018-remove-minio.md)), and `minio-volume-destroy`
deleted its `minio_data` volume ([MinIO](/components/minio.md)).

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

`storage.tf` derives everything from one catalog, `local.buckets`: seven
buckets, one IAM user per writer or reader listed there, and a `backup` user
that reads and lists the five durable buckets. The seventh, `openviking-v2`,
came with `ov-fresh-instance`: OpenViking's key writes it, and the old
`openviking` bucket has no writer and is kept as a backup
([ADR 0021](/decisions/0021-openviking-starts-over-on-a-v2-store.md)). The catalog and the action
sets came over from MinIO, without memex and mlflow-artifacts. Readers get
`s3:GetBucketLocation` and `s3:GetObject` but cannot list. Only the backup
user adds `s3:ListBucket`, because rclone lists to sync. A `restore` user has
`s3:*` on the same five buckets, for the `restore-s3` job
([GCS backups](/components/gcs-backups.md)), and stays as the restore path.
`secrets.tf` writes each job's key to `default/<job>/seaweedfs`, the backup
key to `default/backup-s3/seaweedfs`, and the restore key to
`default/restore-s3/seaweedfs`. A new bucket, memex's included, is a new
entry in `local.buckets`.
`cli/tests/test_seaweedfs_buckets.py` pins the bucket set, the derivation and
the action sets. The live isolation checks are in
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
once at start. The procedure is
`docs/how-to/give-a-job-keyless-seaweedfs-access.md`.

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
the cutover were not migrated, by operator choice, and were deleted with
MinIO's `minio_data` volume in `minio-volume-destroy`.

The OCI registry stores in the `registry` bucket here since 2026-10-20
([container registry](/components/container-registry.md)). It logs in the
same way as loki: a `seaweedfs` identity, the JWT at
`secrets/nomad_seaweedfs.jwt`, and a `local/s3-creds.sh` helper that POSTs
`RoleArn=arn:aws:iam::role/registry` and `RoleSessionName=registry`. Its
`regionendpoint` is `http://<s3_host>:8333`, from the same Consul lookup.
Its bucket was restored from GCS, not started empty, and the 725 zero-byte
`dir/` markers the restore wrote were deleted afterwards. Its static key at
`default/registry/seaweedfs` is a rollback path the job does not read.

The devcontainer's `mc` alias is `s3`, set from `AWS_ENDPOINT_URL_S3`,
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.devcontainer/.env`, which
the operator fills with the admin key from
`vault kv get secret/default/seaweedfs/admin`
([the devcontainer](/components/devcontainer.md)).

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
- **Little memory to spare on orangepi4a.** With MinIO (2560 MB), ov-dash
  (512 MB), alloy and the worker reservation, the node had under 128 MB
  unreserved, and the job could not place (`spike:seaweedfs-service/4`).
  ov-dash was stopped to make room until `minio-removal` freed MinIO's share,
  and was started again with `nomad job start ov-dash` on 2026-10-20. An
  applications-root apply does not start a stopped job.
- **Ed25519 keys.** SeaweedFS parses RSA and EC JWKS keys only. Nomad signs
  workload identities with RS256 today. If it ever adds an EdDSA key,
  SeaweedFS rejects the tokens it signs.

`cli/tests/test_seaweedfs_jobspec.py` pins the image floor (4.40 fixes
CVE-2026-77298), every flag above, the growth setting, the two mapped ports,
and that `seaweedfs` is the only jobspec carrying the `s3` tag.
`cli/tests/test_s3_cutover.py` pins the `s3` edge backend, the dash tile and
the devcontainer alias to SeaweedFS.
