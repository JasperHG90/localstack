# Copy of the storage.tf shapes (deployments/applications) for the openviking
# policy move. var.step = 1 is today's catalog, 2 is the plan's change.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
variable "endpoint" {}
variable "step" { type = number }
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "SPIKEADMINKEY0000001"
  secret_key                  = "spikeAdminSecret0000000000000000000000001"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  s3_use_path_style           = true
  endpoints {
    s3  = var.endpoint
    iam = var.endpoint
  }
}
locals {
  buckets_step1 = {
    loki = {
      writers = [{ "name" = "loki", generate_access_key = true }]
      readers = []
    }
    openviking = {
      writers = [{ "name" = "openviking", generate_access_key = true }]
      readers = []
    }
  }
  buckets_step2 = {
    loki = {
      writers = [{ "name" = "loki", generate_access_key = true }]
      readers = []
    }
    openviking = {
      writers = []
      readers = []
    }
    openviking-v2 = {
      writers = [{ "name" = "openviking", generate_access_key = true }]
      readers = []
    }
  }
  buckets = var.step == 1 ? local.buckets_step1 : local.buckets_step2

  seaweedfs_durable_buckets = var.step == 1 ? ["openviking"] : ["openviking", "openviking-v2"]
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

output "ov_id" { value = aws_iam_access_key.seaweedfs["openviking"].id }
output "ov_secret" {
  value     = aws_iam_access_key.seaweedfs["openviking"].secret
  sensitive = true
}
output "backup_id" { value = aws_iam_access_key.seaweedfs_backup.id }
output "backup_secret" {
  value     = aws_iam_access_key.seaweedfs_backup.secret
  sensitive = true
}
