resource "minio_s3_bucket" "data_lake" {
  bucket = "datalake"
  acl    = "private"
}

resource "minio_iam_user" "ducklake_writer" {
    name = "ducklake"
}

resource "minio_iam_user" "ducklake_reader" {
    name = "ducklake_reader"
}

// See: https://docs.min.io/enterprise/aistor-object-store/administration/iam/access/
resource "minio_iam_policy" "data_lake_read_write" {
  name = "data_lake_read_write"
  policy= <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"DataLakeReadWrite",
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Principal":"*",
      "Resource": "arn:aws:s3:::${minio_s3_bucket.data_lake.id}"
    }
  ]
}
EOF
}

# NB: may need /* after resource
resource "minio_iam_policy" "data_lake_read_only" {
  name = "data_lake_read_only"
  policy= <<EOF
{
  "Version":"2012-10-17",
  "Statement": [
    {
      "Sid":"DataLakeReadWrite",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation", "s3:GetObject"],
      "Principal":"*",
      "Resource": "arn:aws:s3:::${minio_s3_bucket.data_lake.id}"
    }
  ]
}
EOF
}

resource "minio_iam_user_policy_attachment" "data_lake_writer" {
  user_name   = minio_iam_user.ducklake_writer.id
  policy_name = minio_iam_policy.data_lake_read_write.id
}

resource "minio_iam_user_policy_attachment" "data_lake_reader" {
  user_name   = minio_iam_user.ducklake_reader.id
  policy_name = minio_iam_policy.data_lake_read_only.id
}

resource "minio_accesskey" "ducklake_writer" {
  user = "${minio_iam_user.ducklake_writer.name}"
  status = "enabled"
}

resource "minio_accesskey" "ducklake_reader" {
  user = "${minio_iam_user.ducklake_reader.name}"
  status = "enabled"
}
