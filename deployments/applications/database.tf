locals {
  roles = [
    "ducklake_owner",
    "ducklake_reader"
  ]
  databases = {
    ducklake = {
      owner = "ducklake_owner"
      readers = ["ducklake_reader"]
    }
  }

  database_reader_map = {
    for tuple in flatten([
      for db_name, db_info in local.databases : [
        for reader in db_info.readers : {
          key = "${db_name}__${reader}"
          value = {
            database = db_name
            role     = reader
          }
        }
      ]
    ]) : tuple.key => tuple.value
  }
}

resource "random_password" "password" {
  for_each = toset(local.roles)
  length           = 16
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "postgresql_role" "role" {
  for_each = toset(local.roles)
  name     = each.key
  login    = true
  password = random_password.password[each.key].result
}

resource "postgresql_database" "ducklake" {
  for_each = local.databases
  name                   = each.key
  owner                  = postgresql_role.role[each.value.owner].name
  lc_collate             = "C"
  connection_limit       = -1
  allow_connections      = true
  alter_object_ownership = true
}

// See: https://ducklake.select/docs/stable/duckdb/guides/access_control
resource "postgresql_grant" "reader" {
  for_each    = local.database_reader_map
  
  database    = each.value.database
  role        = postgresql_role.role[each.value.role].name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT"]
}
