terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "~>2.5.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "~>5.3.0"
    }
    minio = {
      source  = "aminueza/minio"
      version = "~>3.8.0"
    }
    consul = {
      source  = "hashicorp/consul"
      version = "~>2.22.0"
    }
    postgresql = {
      source = "cyrilgdn/postgresql"
      version = "~>1.26.0"
    }
  }
}

provider "nomad" {}

provider "vault" {}

provider "consul" {
  # NB: provider does not read address from env var
  address    = "localstack.local:8500"
  datacenter = "localstack"
}

provider "minio" {
  minio_server = "${data.consul_service.minio.service[0].node_address}:9000"
  minio_user = ephemeral.vault_kv_secret_v2.minio_admin.data.access_key
  minio_password = ephemeral.vault_kv_secret_v2.minio_admin.data.secret_key
}

provider "postgresql" {
  host            = data.consul_service.postgres.service[0].node_address
  port            = "5432"
  username        = ephemeral.vault_kv_secret_v2.postgres_admin.data.username
  password        = ephemeral.vault_kv_secret_v2.postgres_admin.data.password
  sslmode         = "disable"
  connect_timeout = 15
}
