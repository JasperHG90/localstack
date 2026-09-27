# Documentation

Writing about this cluster is in two places, each for a different reader.

| What is it? | Where is it? | Who is it for? | What does it contain? |
| --- | --- | --- | --- |
| User documentation | `docs/`, listed below | Anyone who runs the cluster, logs in to a service on it, or deploys a job onto it | How-to guides, reference and explanation, sorted by the [Diátaxis](https://diataxis.fr/) framework |
| Repository knowledge | [`.okf/`](../.okf/index.md) | Agents and people working on this repository | Decision records, lessons learned the hard way, unbuilt proposals, and build history |

How-to guides are for a task you are doing now. Reference describes what
exists: commands, routes, roles, services. Explanation says why the cluster is
shaped the way it is.

## How-to guides

**Logging in and access**

- [Log in to Vault](how-to/log-in-to-vault.md)
- [Get the operator password](how-to/get-the-operator-password.md)
- [Rotate the Vault operator password](how-to/rotate-the-vault-operator-password.md)
- [Sign in to Nomad with Vault](how-to/sign-in-to-nomad-with-vault.md)
- [Sign in to Grafana](how-to/sign-in-to-grafana.md), or
  [without Vault](how-to/sign-in-to-grafana-without-vault.md) when Vault is down
- [Log in to memex from a laptop](how-to/log-in-to-memex-from-a-laptop.md)
- [Join and leave the admin group](how-to/join-and-leave-the-admin-group.md)
- [Add an app-user tier](how-to/add-an-app-user-tier.md)
- [Add a service that logs people in through Vault](how-to/add-a-vault-oidc-client.md)

**Revoking access**

- [Revoke a lost or stolen session](how-to/revoke-a-lost-or-stolen-session.md)
- [Delete a lost session's Nomad and Consul tokens](how-to/delete-a-lost-sessions-brokered-tokens.md)
- [Revoke memex human tokens](how-to/revoke-memex-human-tokens.md)

**Two-factor login**

- [Roll out Vault login MFA](how-to/roll-out-vault-login-mfa.md)
- [Turn off Vault login MFA](how-to/turn-off-vault-login-mfa.md)
- [Remove Vault login MFA completely](how-to/remove-vault-login-mfa.md)

**Workload identity**

- [Verify the workload identity chain](how-to/verify-the-workload-identity-chain.md)
- [Give a job keyless MinIO access](how-to/give-a-job-keyless-minio-access.md)
- [Give an aws-sdk-go v1 service keyless MinIO access](how-to/give-an-aws-sdk-go-service-keyless-minio-access.md)
- [Exchange a workload JWT for MinIO credentials](how-to/exchange-a-workload-jwt-for-minio-credentials.md)
- [Verify memex OIDC for workloads and humans](how-to/verify-memex-oidc.md)

**Edge, DNS and certificates**

- [Add a service to the edge](how-to/add-a-service-to-the-edge.md)
- [Check that lab names resolve](how-to/check-lab-dns.md)
- [Check the edge certificate](how-to/check-the-edge-certificate.md)
- [Recover a failed certificate renewal](how-to/recover-a-failed-certificate-renewal.md)
- [Test ACME job changes on staging](how-to/test-acme-job-changes-on-staging.md)

**Monitoring and observability**

- [Reach Prometheus or Loki directly](how-to/reach-prometheus-or-loki-directly.md)
- [Narrow the monitoring firewall rules](how-to/narrow-the-monitoring-firewall-rules.md)
- [Expose Python metrics to Prometheus](how-to/expose-python-metrics-to-prometheus.md)
- [Ship Python logs to Loki](how-to/ship-python-logs-to-loki.md)
- [Send Python traces to Tempo](how-to/send-python-traces-to-tempo.md)
- [Respond to a retrieval-quality alert](how-to/respond-to-a-retrieval-quality-alert.md)
- [Re-seed the driftwatch baseline](how-to/reseed-the-driftwatch-baseline.md)

**Backups**

- [Run a backup job on demand](how-to/run-a-backup-job-on-demand.md)
- [Apply a backup infrastructure change](how-to/apply-a-backup-infrastructure-change.md)

**NATS and JetStream**

- [Set up the nats CLI](how-to/set-up-the-nats-cli.md)
- [Publish and subscribe with the nats CLI](how-to/publish-and-subscribe-with-the-nats-cli.md)
- [Create a JetStream stream](how-to/create-a-jetstream-stream.md)
- [Use NATS from Python](how-to/use-nats-from-python.md)
- [Connect a Nomad job to NATS](how-to/connect-a-nomad-job-to-nats.md)
- [Check JetStream disk usage](how-to/check-jetstream-disk-usage.md)
- [Remove a JetStream stream](how-to/remove-a-jetstream-stream.md)
- [Reset a JetStream consumer](how-to/reset-a-jetstream-consumer.md)

**Services**

- [Call OpenViking from the CLI](how-to/call-openviking-from-the-cli.md)
- [Connect Claude Code to OpenViking](how-to/connect-claude-code-to-openviking.md)
- [Verify an OpenViking deployment](how-to/verify-an-openviking-deployment.md)
- [Add, remove, or reorder a dash tile](how-to/change-a-dash-tile.md)
- [Rebuild and deploy the dash images](how-to/rebuild-the-dash-images.md)
- [Rebuild and deploy the registry-ui images](how-to/rebuild-the-registry-ui-images.md)

**Nodes and storage**

- [Move the Orange Pi OS to an NVMe drive](how-to/move-orange-pi-os-to-nvme.md)
- [Delete a Nomad dynamic host volume](how-to/delete-a-nomad-dynamic-host-volume.md)

## Reference

**The `localstack` CLI**

- [`localstack login`](reference/cli-login.md)
- [Reading the cluster](reference/cli-read-commands.md): `status`, `service`,
  `secret` and `vault grants`
- [Pinned CLIs and PATH shims](reference/cli-deps.md)
- [Break-glass recovery](reference/cli-breakglass.md)

**Identity and access**

- [Human login to Vault, and the OIDC issuer it feeds](reference/vault-human-auth.md)
- [Cluster roles](reference/cluster-roles.md)
- [Vault login MFA](reference/vault-login-mfa.md)
- [Bootstrap secrets](reference/bootstrap-secrets.md)

**Edge**

- [HAProxy routes and ports](reference/edge-routes.md)
- [DNS for the lab zone](reference/dns.md)
- [TLS certificates](reference/tls-certificates.md)

**Observability and backups**

- [Monitoring stack](reference/monitoring.md)
- [Python service observability](reference/python-observability.md)
- [Retrieval quality](reference/retrieval-quality.md)
- [Nightly GCS backup jobs](reference/gcs-backups.md)

**Services**

- [OpenViking](reference/openviking.md)
- [dash, the cluster landing page](reference/dash.md)
- [registry-ui](reference/registry-ui.md)
- [NATS and JetStream](reference/nats.md)

**Architecture diagrams**

- [Cluster architecture](reference/architecture/architecture.png)
  ([draw.io source](reference/architecture/architecture.drawio.png))
- [OpenViking OIDC](reference/architecture/openviking_oidc.drawio.png)

## Explanation

- [Nomad Workload Identity and the Vault JWT trust chain](explanation/workload-identity.md)
- [Why the cluster roles are shaped the way they are](explanation/cluster-roles.md)
- [Vault OIDC tokens, and what a relying party has to know](explanation/vault-oidc-tokens.md)
- [Two-factor auth on Vault logins](explanation/vault-login-mfa.md)
- [Why lab names are in public DNS](explanation/public-lab-dns.md)
- [Why monitoring is not behind the edge](explanation/why-monitoring-is-not-behind-the-edge.md)
- [The retrieval-quality canary](explanation/retrieval-quality-canary.md)
- [Why each backup job has its own credentials](explanation/backup-job-credentials.md)
- [OpenViking identity](explanation/openviking-identity.md)
- [How dash reaches two tasks through one route](explanation/dash-routing.md)
- [Why registry-ui stays cheap, and where it stops scaling](explanation/registry-ui-cost.md)
