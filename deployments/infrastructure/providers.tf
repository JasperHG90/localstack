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
    null = {
      source  = "hashicorp/null"
      version = "~>3.2.0"
    }
    # consul = {
    #   source  = "hashicorp/consul"
    #   version = "~>2.22.0"
    # }
  }
}

provider "nomad" {}

provider "vault" {}
