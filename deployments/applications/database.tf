resource "random_password" "postgres_ducklake_owner" {
  length           = 16
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_password" "postgres_ducklake_reader" {
  length           = 16
  special          = false
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "postgresql_role" "ducklake_owner" {
  name     = "ducklake"
  login    = true
  password = random_password.postgres_ducklake_owner.result
}

resource "postgresql_role" "ducklake_reader" {
  name     = "ducklake_reader"
  login    = true
  password = random_password.postgres_ducklake_reader.result
}

resource "postgresql_database" "ducklake" {
  name                   = "ducklake"
  owner                  = postgresql_role.ducklake_owner.name
  lc_collate             = "C"
  connection_limit       = -1
  allow_connections      = true
  alter_object_ownership = true
}

// See: https://ducklake.select/docs/stable/duckdb/guides/access_control
resource "postgresql_grant" "ducklake_reader" {
  database    = postgresql_database.ducklake.name
  role        = postgresql_role.ducklake_reader.name
  schema      = "public"
  object_type = "table"
  privileges  = ["SELECT"]
}
