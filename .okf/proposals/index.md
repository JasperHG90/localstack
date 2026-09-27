# Proposals

Designs and plans that were not built, or were superseded, kept with their reasoning.

* [Credential Rotation: TAILSCALE_AUTH_KEY & GITHUB_PAT](bootstrap-credential-rotation.md) - Unbuilt plan for `just rotate_tailscale` and `just rotate_github`: a `rotate_secrets.yml` playbook that writes the new value to Vault and pushes it to every host that consumes it.
* [Building our own OpenViking dashboard](openviking-dashboard.md) **(deprecated)** - Superseded proposal for a dashboard that held each person's OpenViking key server-side. Vault identity tokens removed the key, the dashboard was built as ov-dash, and only the search and retrieval findings still stand.
* [Short-lived Postgres credentials from Vault](postgres-dynamic-credentials.md) - The S2 spike's findings for R3: how a Vault-minted Postgres user does memex's work, the SET ROLE statement that makes revocation work, what a pool does when the lease expires, the runbook, and what the spike left running.
* [PostgreSQL CDC to NATS bridge](postgres-nats-cdc-bridge.md) - A design, never deployed, for a pg-nats-bridge job that turns Postgres LISTEN/NOTIFY triggers into NATS JetStream messages so services can react to Memex writes. No such job, trigger or image exists in deployments/.
* [Adding Orange Pi RV2 (RISC-V) to the Cluster](riscv-worker-node.md) - Unbuilt plan to join an Orange Pi RV2 (riscv64) as a Nomad worker: cross-compile Nomad, Consul, the Podman driver and NATS, extend the Ansible arch map, and run NATS + JetStream and node_exporter on it.
* [Two-factor auth on Vault logins, the handoff](vault-login-mfa.md) - Built and tested but not applied as of 2026-09-12: TOTP on the userpass mount, localstack login speaking Login MFA, and the ov-dash jwt-lab chain that lets the enforcement name the mount. Holds the Terraform inventory and the next steps.
