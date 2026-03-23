locals {
  roles = [
    "ducklake_owner",
    "ducklake_reader",
    "memex",
    "phoenix"
  ]
  databases = {
    ducklake = {
      owner      = "ducklake_owner"
      readers    = ["ducklake_reader"]
      extensions = []
    }
    memex = {
      owner      = "memex"
      readers    = []
      extensions = ["vector"]
    }
    phoenix = {
      owner      = "phoenix"
      readers    = []
      extensions = []
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
  length  = 16
  special = false
}

resource "postgresql_role" "role" {
  for_each = toset(local.roles)
  name     = each.key
  login    = true
  password = random_password.password[each.key].result
}

resource "postgresql_database" "database" {
  for_each = local.databases
  name                   = each.key
  owner                  = postgresql_role.role[each.value.owner].name
  lc_collate             = "C"
  connection_limit       = -1
  allow_connections      = true
  alter_object_ownership = true
}

resource "postgresql_extension" "extension" {
  for_each = {
    for tuple in flatten([
      for db_name, db_info in local.databases : [
        for ext in db_info.extensions : {
          key      = "${db_name}__${ext}"
          database = db_name
          name     = ext
        }
      ]
    ]) : tuple.key => tuple
  }

  name     = each.value.name
  database = postgresql_database.database[each.value.database].name
}

// See: https://ducklake.select/docs/stable/duckdb/guides/access_control
resource "postgresql_grant" "reader" {
  for_each    = local.database_reader_map
  
  database    = postgresql_database.database[each.value.database].name
  role        = postgresql_role.role[each.value.role].name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT"]
}
