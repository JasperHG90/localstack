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

provider "postgresql" {
  sslmode         = "disable"
}
