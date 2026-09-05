locals {
  buckets = {
    datalake = {
      writers = [
        { "name" = "ducklake_writer", generate_access_key = true }
      ],
      readers = [
        { "name" = "ducklake_reader", generate_access_key = true }
      ]
    }
    memex = {
      writers = [
        { "name" = "memex", generate_access_key = true }
      ],
      readers = []
    }
    loki = {
      writers = [
        { "name" = "loki", generate_access_key = true }
      ],
      readers = []
    }
    tempo = {
      writers = [
        { "name" = "tempo", generate_access_key = true }
      ],
      readers = []
    }
    # Model weights (LLMs, embedding models). Split reader/writer like
    # datalake rather than single-writer like the service buckets above:
    # models are pushed rarely by an operator and pulled often by jobs, so
    # a puller gets a read-only key and cannot overwrite a model it loads.
    # No Vault KV entry yet -- the convention here is that creds land in
    # Vault when a job consumes them (memex, loki, tempo), not at bucket
    # creation (datalake and mlflow-artifacts have none).
    models = {
      writers = [
        { "name" = "models_writer", generate_access_key = true }
      ],
      readers = [
        { "name" = "models_reader", generate_access_key = true }
      ]
    }
    # Blob store for the OCI registry. Its own bucket, not shared with
    # `models`: the registry owns the layout under this prefix and addresses
    # everything by digest, so nothing else should be writing into it.
    registry = {
      writers = [
        { "name" = "registry", generate_access_key = true }
      ],
      readers = []
    }
    # mlflow the service is gone (services.tf, secrets.tf, database.tf), but
    # this bucket is kept on request rather than destroyed along with it —
    # whatever's in it stays reachable until it's deliberately emptied and
    # this entry removed.
    "mlflow-artifacts" = {
      writers = [
        { "name" = "mlflow", generate_access_key = true }
      ],
      readers = []
    }
    openviking = {
      writers = [
        { "name" = "openviking", generate_access_key = true }
      ]
      readers = []
    }
  }

  all_minio_users = distinct(flatten([
    for bucket in local.buckets : concat(
      [for writer in bucket.writers : writer.name],
      [for reader in bucket.readers : reader.name]
    )
  ]))

  access_key_users = flatten([
    for bucket in local.buckets : concat(
      [for writer in bucket.writers : writer.name if writer.generate_access_key],
      [for reader in bucket.readers : reader.name if reader.generate_access_key]
    )
  ])
}

### Workload-identity policy for the tempo job.
###
### The NAME is the mechanism. MinIO's `NOMAD` OIDC target runs in claim
### mode, so it applies the policy named by the JWT's `nomad_job_id` claim.
### `tempo` here must stay spelled exactly like the job id in
### services/tempo.hcl. The bucket module's `tempo_read_write` does NOT
### match: claim mode compares the whole string.
###
### This is deliberately NOT in modules/bucket/. That module is shared by
### every bucket, and this convention has one consumer. Promote it there
### once a second job proves it. The bucket is a plain string for the same
### reason M1 used one: `minio_s3_bucket.bucket` lives inside
### `module.buckets`, which exports nothing.
###
### No `minio_iam_user_policy_attachment`, unlike the policies the bucket
### module emits: this one is assumed through STS by a workload identity,
### never attached to a standing user. The `tempo` user below keeps its own
### static key and its own attachment, deliberately, as the rollback path.
resource "minio_iam_policy" "tempo_wi" {
  name   = "tempo"
  policy = <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"TempoOwnBucketOnly",
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Principal":"*",
      "Resource": ["arn:aws:s3:::tempo", "arn:aws:s3:::tempo/*"]
    }
  ]
}
EOF
}

### Workload-identity policies for loki and registry, the same shape as
### tempo's above and for the same reason: claim mode applies the policy NAMED
### by the JWT's `nomad_job_id`, so each name must match its job id exactly.
###
### Unlike tempo, these two reach MinIO through an AWS `credential_process`
### helper rather than minio-go's web-identity provider, because both vendor
### aws-sdk-go v1, which cannot be pointed at a non-AWS STS. The policy side is
### identical either way: the exchange still arrives with no RoleArn and is
### resolved by the job id.
resource "minio_iam_policy" "loki_wi" {
  name   = "loki"
  policy = <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"LokiOwnBucketOnly",
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Principal":"*",
      "Resource": ["arn:aws:s3:::loki", "arn:aws:s3:::loki/*"]
    }
  ]
}
EOF
}

resource "minio_iam_policy" "registry_wi" {
  name   = "registry"
  policy = <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"RegistryOwnBucketOnly",
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Principal":"*",
      "Resource": ["arn:aws:s3:::registry", "arn:aws:s3:::registry/*"]
    }
  ]
}
EOF
}

resource "minio_iam_user" "users" {
  for_each = toset(local.all_minio_users)
  name     = each.key
}

resource "minio_accesskey" "users" {
  for_each = toset(local.access_key_users)
  user     = minio_iam_user.users[each.key].name
  status   = "enabled"
}

module "buckets" {
  for_each = local.buckets
  source   = "./modules/bucket"

  name = each.key
  permissions = {
    readers = [for reader in each.value.readers : reader.name]
    writers = [for writer in each.value.writers : writer.name]
  }

  depends_on = [minio_iam_user.users]
}
