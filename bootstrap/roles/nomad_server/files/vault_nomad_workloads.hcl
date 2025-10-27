path "kv/data/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_job_id}}/*" {
  capabilities = ["read"]
}

path "kv/data/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_job_id}}" {
  capabilities = ["read"]
}

path "kv/metadata/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/*" {
  capabilities = ["list"]
}

path "kv/metadata/*" {
  capabilities = ["list"]
}

path "secret/data/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_job_id}}/*" {
  capabilities = ["read"]
}

path "secret/data/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_job_id}}" {
  capabilities = ["read"]
}

path "secret/metadata/{{identity.entity.aliases.auth_jwt_67fec82c.metadata.nomad_namespace}}/*" {
  capabilities = ["list"]
}

path "secret/metadata/*" {
  capabilities = ["list"]
}
