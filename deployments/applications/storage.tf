### The object storage catalog: every SeaweedFS bucket and the users that
### write or read it. storage below derives buckets, users, keys and policies
### from it.
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
    # The store OpenViking ran on until it started over on openviking-v2.
    # Kept as a read-only backup: no user writes it, the backup and restore
    # users reach it through the durable list below, and ov-carry-over reads
    # it (its own policy, further down).
    openviking = {
      writers = []
      readers = []
    }
    "openviking-v2" = {
      writers = [
        { "name" = "openviking", generate_access_key = true }
      ]
      readers = []
    }
    # Repo docs CI uploads for ov-sync-consumer to sync into OpenViking.
    # ov-sync-consumer reads it keylessly (local.seaweedfs_keyless_jobs in
    # the infrastructure root). CI's keys belong to ci-openviking-sync.
    "ov-sync" = {
      writers = []
      readers = []
    }
  }
}

### SeaweedFS buckets, users, keys and policies.
###
### Every bucket and user comes from `local.buckets` above. Writers get every
### action on their bucket; readers get GetBucketLocation and GetObject but
### cannot list, the grants carried over from the previous store. Only the
### backup and ov-carry-over users add s3:ListBucket, because rclone lists to
### sync or copy.
locals {
  seaweedfs_durable_buckets = ["openviking", "openviking-v2", "registry", "models", "datalake"]
  seaweedfs_read_actions    = ["s3:GetBucketLocation", "s3:GetObject"]
  seaweedfs_write_actions   = ["s3:*"]
  seaweedfs_backup_actions  = concat(local.seaweedfs_read_actions, ["s3:ListBucket"])

  seaweedfs_buckets = local.buckets

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
### durable buckets: the migration used it, and it is the restore path.
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

### ov-carry-over reads the old OpenViking bucket and writes the new one. It
### gets no write action on `openviking`, so the job cannot change the backup.
resource "aws_iam_user" "seaweedfs_carry_over" {
  name = "ov-carry-over"
}

resource "aws_iam_access_key" "seaweedfs_carry_over" {
  user = aws_iam_user.seaweedfs_carry_over.name
}

resource "aws_iam_user_policy" "seaweedfs_carry_over" {
  name = "ov-carry-over-copy"
  user = aws_iam_user.seaweedfs_carry_over.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.seaweedfs["openviking"].arn, "${aws_s3_bucket.seaweedfs["openviking"].arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = local.seaweedfs_write_actions
        Resource = [aws_s3_bucket.seaweedfs["openviking-v2"].arn, "${aws_s3_bucket.seaweedfs["openviking-v2"].arn}/*"]
      },
    ]
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
