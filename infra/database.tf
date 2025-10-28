resource "postgresql_role" "ducklake" {
  name     = "ducklake"
  login    = true
  password = random_password.postgres_ducklake.result
}

resource "postgresql_database" "ducklake" {
  name                   = "ducklake"
  owner                  = postgresql_role.ducklake.name
  lc_collate             = "C"
  connection_limit       = -1
  allow_connections      = true
  alter_object_ownership = true
}
