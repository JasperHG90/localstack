### Vault brokers the deployer's Consul token: `vault read consul/creds/deploy`
### mints a short-lived Consul ACL token carrying only the `deploy` policy,
### replacing the static god-mode Consul bootstrap token the deployer uses
### today. Consuming this brokered token in the provider is F8; F6 only stands
### up and proves the brokering path.
###
### The `consul` secrets engine mount, its `config/access` (which holds the
### Consul management token), AND the scoped `deploy` Consul ACL policy are all
### owned by Ansible bootstrap (bootstrap/playbooks/enable_consul_secrets.yml).
### Each requires the Consul management token, which the config-split invariant
### keeps out of Terraform. The pinned vault provider (~>5.3.0) attaches a
### Consul policy to a role only BY NAME via consul_policies; it cannot author
### the policy's rules through Vault. So the policy is created Consul-side in
### Ansible and referenced here by name, and Terraform authenticates to Vault
### only.
###
### ttl/max_ttl (30m/60m, in seconds) bound each minted token's lease; the
### deployer renews within a long run once F8 wires it up.
resource "vault_consul_secret_backend_role" "deploy" {
  backend         = "consul"
  name            = "deploy"
  consul_policies = ["deploy"]
  ttl             = 1800
  max_ttl         = 3600
}
