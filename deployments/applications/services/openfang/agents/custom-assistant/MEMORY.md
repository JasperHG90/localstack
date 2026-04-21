# Memory

Static facts this agent should always know, regardless of Memex availability:

- The cluster runs on Orange Pi boards with Armbian.
- Infrastructure uses the HashiCorp stack: Nomad, Vault, Consul.
- Container runtime is Podman, not Docker.
- All secrets live in Vault KV2. Never hardcode credentials.
- Task runner is `just` (not make).
- Memex is the external knowledge base — native OpenFang memory is disabled.
