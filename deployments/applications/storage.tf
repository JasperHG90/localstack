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
      readers = [
        { "name" = "openfang", generate_access_key = true }
      ]
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
