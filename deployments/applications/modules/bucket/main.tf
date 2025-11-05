locals {
    name_underscore = replace(var.name, "-", "_")
}

resource "minio_s3_bucket" "bucket" {
  bucket = var.name
  acl    = var.acl
}

// See: https://docs.min.io/enterprise/aistor-object-store/administration/iam/access/
resource "minio_iam_policy" "policy_read_write" {
  name = "${local.name_underscore}_read_write"
  policy= <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"DataLakeReadWrite",
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Principal":"*",
      "Resource": "arn:aws:s3:::${minio_s3_bucket.bucket.id}"
    }
  ]
}
EOF
}

# NB: may need /* after resource
resource "minio_iam_policy" "policy_read_only" {
  name = "${local.name_underscore}_read_only"
  policy= <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"DataLakeReadWrite",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation", "s3:GetObject"],
      "Principal":"*",
      "Resource": "arn:aws:s3:::${minio_s3_bucket.bucket.id}"
    }
  ]
}
EOF
}

resource "minio_iam_user_policy_attachment" "bucket_writer" {
  for_each = toset(var.permissions.writers)

  user_name   = each.key
  policy_name = minio_iam_policy.policy_read_write.id
}

resource "minio_iam_user_policy_attachment" "bucket_reader" {
  for_each = toset(var.permissions.readers)

  user_name   = each.key
  policy_name = minio_iam_policy.policy_read_only.id
}
