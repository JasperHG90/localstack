terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
variable "endpoint" {}
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
resource "aws_s3_bucket" "b" { bucket = "tfapp" }
resource "aws_iam_user" "u" { name = "tfapp" }
resource "aws_iam_access_key" "k" { user = aws_iam_user.u.name }
resource "aws_iam_user_policy" "p" {
  name = "tfapp-rw"
  user = aws_iam_user.u.name
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["s3:*"], Resource = [aws_s3_bucket.b.arn, "${aws_s3_bucket.b.arn}/*"] }]
  })
}
output "id" { value = aws_iam_access_key.k.id }
output "secret" {
  value     = aws_iam_access_key.k.secret
  sensitive = true
}
