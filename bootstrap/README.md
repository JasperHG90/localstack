# Bootstrap

Ansible playbooks and roles for provisioning the cluster. Run `just bootstrap` to execute the full pipeline.

## Prerequisites

### Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```shell
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DOCKER_REGISTRY_PASSWORD` | Password for the private Docker registry |
| `MINIO_ROOT_PASSWORD` | MinIO root password |
| `CONSUL_AGENT_TOKEN_SECRET` | Consul agent ACL token |
| `VAULT_CONSUL_TOKEN_SECRET` | Vault's Consul ACL token |
| `NOMAD_CONSUL_TOKEN_SECRET` | Nomad's Consul ACL token |
| `TAILSCALE_AUTH_KEY` | Tailscale auth key for subnet router |
| `GITHUB_USER` | GitHub username for ghcr.io access |
| `GITHUB_PAT` | GitHub classic PAT with `read:packages` scope (fine-grained tokens don't support packages) |

### GitHub Container Registry

A **classic** personal access token is required (not fine-grained):

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select `read:packages` scope
4. Add to `.env` as `GITHUB_PAT`

## Setup for *every node*

The following setup needs to be executed on every node, *before* running ansible commands.

### Create SSH keys

1. Run `just ssh_keygen`. This will generate keys in /home/vscode/workspace.
2. Copy them to all your nodes:

```shell
# Example
ssh-copy-id -i ${HOME}/workspace/.ssh/id_rsa.pub localstack@192.168.2.31
```

3. Log into the device:

```shell
ssh localstack@192.168.2.31
```

4. Modify ssh config:

```shell
# Should contain
# PubkeyAuthentication yes
# PasswordAuthentication no
# ChallengeResponseAuthentication no
# UsePAM no
sudo nano /etc/ssh/sshd_config
```

5. Restart service

```shell
sudo systemctl restart ssh
```

6. Test

```shell
ssh -i /home/vscode/workspace/.ssh/id_rsa localstack@192.168.2.31
```

### Enable passwordless `sudo`

1. Create new sudoers file:

```shell
# This command uses your current sudo password one last time
# For different users: replace 'localstack'
sudo visudo -f /etc/sudoers.d/90-localstack-nopasswd
```

2. Paste the following:

```shell
# NB: mind the user
localstack ALL=(ALL) NOPASSWD: ALL
```

3. Verify:

```shell
sudo ls -l /etc/sudoers.d/
```

4. Test:

```shell
sudo whoami
```
