# localstack

Infrastructure-as-code for a personal homelab cluster running on Orange Pi and Radxa single-board computers. Built on the HashiCorp stack (Nomad, Vault, Consul) with Podman as the container runtime.

This is my lab, not a general-purpose template — topology, hostnames, and service choices are specific to my hardware. It's public as a reference, not as a product.

## What it runs

- **Core:** Nomad, Vault, Consul
- **Data:** PostgreSQL, MinIO (S3-compatible), a private Docker registry, DuckLake
- **Observability:** Prometheus, Loki, Grafana, HAProxy (reverse proxy + metrics)
- **Applications:** [Hermes](https://github.com/JasperHG90/hermes) (AI gateway + agent), [Memex](https://github.com/JasperHG90/memex) (notes/memory service), Phoenix (LLM tracing)
- **Backups:** nightly GCS off-site jobs for PostgreSQL and MinIO

## Layout

The repo is three layers, deployed in order:

| Layer | Path | What it does |
|---|---|---|
| Bootstrap | `bootstrap/` | Ansible playbooks — install Nomad/Vault/Consul/Podman/CNI on the nodes, seed initial secrets |
| Infrastructure | `deployments/infrastructure/` | Terraform — Vault mounts, dynamic host volumes, core services (PostgreSQL, MinIO, registry) |
| Applications | `deployments/applications/` | Terraform — databases/roles, MinIO buckets/policies, application Nomad jobs |

Database schema changes live in `applications/migrations/` and run through [golang-migrate](https://github.com/golang-migrate/migrate).

Service-level docs are in `docs/` (HAProxy routing, monitoring, GCS backups, credential rotation, etc.).

## Conventions

- **Task runner:** [`just`](https://github.com/casey/just) — each major directory has its own `justfile`.
- **Container runtime:** Podman on the cluster nodes. Dev container uses Docker-in-Docker.
- **Secrets:** everything lives in Vault KV2. Nothing in this repo should contain a real credential — the handful of operator-local values (`prod.tfvars`, `.devcontainer/.env`) are gitignored and shipped as `.example` stubs.
- **Terraform state:** Consul backend.
- **Python:** 3.12 (see `.python-version`).

## Getting started

You will need: a cluster of Linux nodes with SSH access, a reachable Vault/Nomad/Consul set (bootstrapped from `bootstrap/`), and `just` + Terraform locally.

```bash
# 1. Bootstrap cluster nodes (from a machine with SSH access)
cd bootstrap/
cp .env.example .env       # fill in initial secrets
just setup                 # install Ansible collections
just bootstrap             # SSH keys + playbooks

# 2. Provision infrastructure
cd ../deployments/infrastructure/
cp vars/prod.tfvars.example vars/prod.tfvars   # fill in GCP project, etc.
just init && just apply

# 3. Provision applications
cd ../applications/
cp vars/prod.tfvars.example vars/prod.tfvars   # fill in bot identity, etc.
just init && just apply
```

Pre-commit hooks (JSON/YAML lint, HCL format, private-key detection) — run `just setup` from the repo root, then `just pre_commit` before committing.

## Local dev container

`.devcontainer/` has a Dockerfile for a reproducible shell with Terraform, Ansible, Nomad, Vault, Consul, MinIO CLI, and `just` preinstalled. Copy `.devcontainer/.env.example` to `.devcontainer/.env` and fill in your cluster credentials before starting the container.

## License

MIT — see [LICENSE](./LICENSE).
