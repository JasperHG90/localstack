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

### SeaweedFS, beside MinIO until the cutover.
###
### Every bucket and user comes from `local.buckets` above, and the action
### sets are MinIO's from modules/bucket, so each user keeps exactly its MinIO
### grant. memex and mlflow-artifacts are not recreated (operator, 2026-10-19).
### Only the backup user adds s3:ListBucket, because rclone lists to sync.
locals {
  seaweedfs_dropped_buckets = ["memex", "mlflow-artifacts"]
  seaweedfs_durable_buckets = ["openviking", "registry", "models", "datalake"]
  seaweedfs_read_actions    = ["s3:GetBucketLocation", "s3:GetObject"]
  seaweedfs_write_actions   = ["s3:*"]
  seaweedfs_backup_actions  = concat(local.seaweedfs_read_actions, ["s3:ListBucket"])

  seaweedfs_buckets = {
    for name, bucket in local.buckets : name => bucket
    if !contains(local.seaweedfs_dropped_buckets, name)
  }

  seaweedfs_users = merge([
    for name, bucket in local.seaweedfs_buckets : merge(
      { for w in bucket.writers : w.name => { bucket = name, actions = local.seaweedfs_write_actions } },
      { for r in bucket.readers : r.name => { bucket = name, actions = local.seaweedfs_read_actions } },
    )
  ]...)
}

resource "aws_s3_bucket" "seaweedfs" {
  for_each = local.seaweedfs_buckets
  bucket   = each.key
}

resource "aws_iam_user" "seaweedfs" {
  for_each = local.seaweedfs_users
  name     = each.key
}

resource "aws_iam_access_key" "seaweedfs" {
  for_each = local.seaweedfs_users
  user     = aws_iam_user.seaweedfs[each.key].name
}

resource "aws_iam_user_policy" "seaweedfs" {
  for_each = local.seaweedfs_users
  name     = "${each.key}-${each.value.bucket}"
  user     = aws_iam_user.seaweedfs[each.key].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = each.value.actions
      Resource = [aws_s3_bucket.seaweedfs[each.value.bucket].arn, "${aws_s3_bucket.seaweedfs[each.value.bucket].arn}/*"]
    }]
  })
}

### restore-s3 (infrastructure root) writes the GCS backups back into the
### durable buckets during the cutover. Removed with MinIO.
resource "aws_iam_user" "seaweedfs_restore" {
  name = "restore"
}

resource "aws_iam_access_key" "seaweedfs_restore" {
  user = aws_iam_user.seaweedfs_restore.name
}

resource "aws_iam_user_policy" "seaweedfs_restore" {
  name = "restore-durable-write"
  user = aws_iam_user.seaweedfs_restore.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = local.seaweedfs_write_actions
      Resource = flatten([
        for b in local.seaweedfs_durable_buckets :
        [aws_s3_bucket.seaweedfs[b].arn, "${aws_s3_bucket.seaweedfs[b].arn}/*"]
      ])
    }]
  })
}

### The backup job reads SeaweedFS from the cutover on. Read-only, on the
### durable buckets only.
resource "aws_iam_user" "seaweedfs_backup" {
  name = "backup"
}

resource "aws_iam_access_key" "seaweedfs_backup" {
  user = aws_iam_user.seaweedfs_backup.name
}

resource "aws_iam_user_policy" "seaweedfs_backup" {
  name = "backup-durable-read"
  user = aws_iam_user.seaweedfs_backup.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = local.seaweedfs_backup_actions
      Resource = flatten([
        for b in local.seaweedfs_durable_buckets :
        [aws_s3_bucket.seaweedfs[b].arn, "${aws_s3_bucket.seaweedfs[b].arn}/*"]
      ])
    }]
  })
}
