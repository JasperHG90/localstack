# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infrastructure-as-code project for a home lab cluster running on Orange Pi boards. Uses the HashiCorp stack (Nomad, Vault, Consul) with Podman as the container runtime. Deploys PostgreSQL, MinIO, a private Docker registry, and monitoring (Prometheus, Loki, Grafana).

## Common Commands

### Root justfile
```bash
just format          # Format Nomad HCL files (nomad fmt -recursive)
just setup           # Install pre-commit hooks
just pre_commit      # Run pre-commit checks on all files
just unseal_vault    # Unseal Vault using keys from env
```

### Bootstrap (bootstrap/)
```bash
just ssh_keygen      # Generate SSH keys for cluster nodes
just setup           # Install Ansible Galaxy collections
just bootstrap       # Full cluster setup: SSH + Ansible playbooks
```

### Deployments (deployments/infrastructure/ and deployments/applications/)
```bash
just init            # terraform init
just apply           # terraform apply with prod.tfvars
just destroy         # terraform destroy
```

### Database Migrations (applications/migrations/)
```bash
just up              # Run migrations forward
just down            # Roll back migrations
```

## Architecture

Three layers, deployed in order:

1. **Bootstrap** (`bootstrap/`) — Ansible playbooks and roles that install Nomad, Vault, Consul, CNI plugins, and configure Podman on cluster nodes. Inventory defines server vs client nodes.

2. **Infrastructure** (`deployments/infrastructure/`) — Terraform that provisions Vault secret mounts, generates service passwords, creates Nomad dynamic host volumes, and deploys core service jobs (PostgreSQL, MinIO, Docker Registry). State stored in Consul backend.

3. **Applications** (`deployments/applications/`) — Terraform that creates PostgreSQL databases/roles (e.g. DuckLake), MinIO buckets/IAM policies (via reusable `modules/bucket/`), and writes credentials to Vault KV2. Also state in Consul.

Database schema changes go through `applications/migrations/` using golang-migrate.

## Key Conventions

- **Task runner**: `just` (not make). Each major directory has its own `justfile`.
- **Container runtime**: Podman (not Docker) on the cluster nodes. Dev container uses Docker-in-Docker.
- **Secrets**: All in Vault KV2. Never hardcode credentials. Bootstrap secrets come from `bootstrap/.env` (see `.env.example`).
- **Terraform providers**: Nomad, Vault, Consul, MinIO, PostgreSQL — all configured in respective `providers.tf` files.
- **Pre-commit hooks**: JSON/YAML validation, AST checks, private key detection, Nomad HCL formatting. Run `just pre_commit` before committing.
- **Python**: 3.12 (see `.python-version`).
