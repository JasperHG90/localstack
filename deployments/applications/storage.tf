# resource "minio_iam_user" "ducklake" {
#     name = "ducklake"
# }

# resource "minio_s3_bucket" "data_lake" {
#   bucket = "datalake"
#   acl    = "private"
# }

# resource "minio_iam_policy" "data_lake_policy" {
#   name = "data_lake_policy"
#   policy= <<EOF
# {
#   "Version":"2012-10-17",
#   "Statement": [
#     {
#       "Sid":"DataLakeReadWrite",
#       "Effect": "Allow",
#       "Action": ["s3:*"],
#       "Principal":"*",
#       "Resource": "arn:aws:s3:::${minio_s3_bucket.data_lake.id}"
#     }
#   ]
# }
# EOF
# }

# resource "minio_iam_user_policy_attachment" "data_lake" {
#   user_name   = minio_iam_user.ducklake.id
#   policy_name = minio_iam_policy.data_lake_policy.id
# }

# resource "minio_accesskey" "ducklake" {
#   user = "${minio_iam_user.ducklake.name}"
#   status = "enabled"
# }
