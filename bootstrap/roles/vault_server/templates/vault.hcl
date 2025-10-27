# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: BUSL-1.1

# Full configuration options can be found at https://developer.hashicorp.com/vault/docs/configuration

ui           = true
api_addr     = "http://{{ vault_server_ip_address }}:8200"
cluster_addr = "http://{{ vault_server_ip_address }}:8201"

storage "consul" {
  address = "127.0.0.1:8500"
  path    = "vault/"
  token   = "{{ vault_server_consul_token_secret }}"
}

# HTTPS listener
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
