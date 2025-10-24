terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = ">= 2.0.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.0.0"
    }
    minio = {
      source  = "aminueza/minio"
      version = ">= 3.0.0"
    }
  }
}

provider "nomad" {
  #secret_id = "<REDACTED_NOMAD_SECRET_ID>"
}

provider "vault" {}
