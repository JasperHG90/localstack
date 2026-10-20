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
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    consul = {
      source  = "hashicorp/consul"
      version = "~>2.22.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~>1.26.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~>3.2.0"
    }
    bifrost = {
      source  = "AirHelp-OSP/bifrost"
      version = "~>0.1.0"
    }
  }
}

provider "nomad" {}

provider "vault" {}

provider "consul" {
  # NB: provider does not read address from env var
  address    = "192.168.2.30:8500"
  datacenter = "localstack"
}

### The aws provider talks to SeaweedFS, not AWS: its S3 and IAM endpoints
### are SeaweedFS's S3 port, which also serves the embedded IAM API
### (spike:seaweedfs-buckets/2).
provider "aws" {
  region                      = "us-east-1"
  access_key                  = ephemeral.vault_kv_secret_v2.seaweedfs_admin.data.access_key
  secret_key                  = ephemeral.vault_kv_secret_v2.seaweedfs_admin.data.secret_key
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
  s3_use_path_style           = true

  endpoints {
    s3  = "http://${data.consul_service.seaweedfs.service[0].node_address}:8333"
    iam = "http://${data.consul_service.seaweedfs.service[0].node_address}:8333"
  }
}

provider "postgresql" {
  host            = data.consul_service.postgres.service[0].node_address
  port            = "5432"
  username        = ephemeral.vault_kv_secret_v2.postgres_admin.data.username
  password        = ephemeral.vault_kv_secret_v2.postgres_admin.data.password
  sslmode         = "disable"
  connect_timeout = 15
}

provider "bifrost" {
  # Endpoint is carried by null_resource.bifrost_ready.triggers. Reading a
  # null_resource attribute here gives the provider an explicit dependency on
  # Bifrost being up (bifrost_ready depends on nomad_job.bifrost and re-polls
  # /health on every redeploy), so the provider cannot configure — and virtual
  # keys cannot refresh — against a down or mid-restart gateway. Provider blocks
  # take no depends_on; a resource reference is the Terraform-native way to
  # express this dependency.
  endpoint = null_resource.bifrost_ready.triggers["endpoint"]
  username = ephemeral.vault_kv_secret_v2.bifrost_admin.data.username
  password = ephemeral.vault_kv_secret_v2.bifrost_admin.data.password
}
