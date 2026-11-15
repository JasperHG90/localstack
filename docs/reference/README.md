<!-- kmctl writes this index from the pages in this folder: run kmctl check --fix to update it, do not edit it by hand. -->
# Reference

- [Bootstrap secrets](bootstrap-secrets.md): Where the Tailscale auth key and the GitHub registry credentials are stored in Vault after day-0, and which playbooks read them.
- [Break-glass recovery](cli-breakglass.md): What `localstack breakglass` prints and probes, and what it never touches.
- [Pinned CLIs and PATH shims](cli-deps.md): How `localstack deps` pins the vault, nomad and consul CLIs to the cluster's versions, and what its PATH shims do.
- [`localstack login`](cli-login.md): What `localstack login` brokers, where it keeps the session, and how `env`, `token`, `whoami`, `config` and `logout` use it.
- [Reading the cluster](cli-read-commands.md): What `localstack status`, `service`, `secret` and `vault grants` report, where each reads from, and which token it uses.
- [Cluster roles](cluster-roles.md): The human and machine roles on the cluster, where each is defined, how `admin` membership works, and which to use when a service logs people in through Vault.
- [dash: the cluster landing page](dash.md): What the dash landing page shows, who can sign in, the tile config format, and what the status backend can read.
- [DNS for the lab zone](dns.md): The public DNS records that point the lab zone at the cluster edge, and why `.consul` names do not resolve from the LAN.
- [HAProxy Reverse Proxy](edge-routes.md): Every hostname the HAProxy edge serves, the backend and port behind it, who may reach it, and the edge's ports and certificate.
- [Nightly GCS Backup Jobs](gcs-backups.md): What the two nightly jobs copy to Google Cloud Storage, where their credentials come from, and how the GCS bucket is set up.
- [GitHub Actions](github-actions.md): The lab-auth action: its inputs, outputs, what it exports and what the calling job must set.
- [Monitoring stack](monitoring.md): Who can reach Prometheus, Loki, Tempo and Grafana, where alerts go, how to send traces, and what `localstack monitor` shows.
- [NATS and JetStream](nats.md): Connection facts, JetStream limits and subject conventions for the cluster's NATS broker.
- [OpenViking](openviking.md): Where OpenViking runs, how its retrieval differs from stock, how callers authenticate with Vault tokens, and what its config guard asserts.
- [Python service observability](python-observability.md): How a Python service on the cluster reaches Prometheus, Loki, Tempo and Grafana, and the naming conventions that make the links work.
- [registry-ui: what the cluster registry holds](registry-ui.md): What registry-ui shows, who may sign in to it, how it reads the registry, and how its backend is tested.
- [Retrieval quality](retrieval-quality.md): The three retrieval dashboards, the driftwatch canary metrics they read, and the alerts that compare each run against the last fortnight.
- [TLS certificates](tls-certificates.md): How the wildcard edge certificate is issued, renewed, stored in Vault and served, and why the lego state volume matters.
- [Human login to Vault, and the OIDC issuer it feeds](vault-human-auth.md): Where human Vault credentials are, which OIDC issuer a service points at, what the developer group grants, and the claims a service can read.
- [Vault login MFA](vault-login-mfa.md): The just recipes that enroll and reset a TOTP second factor on Vault logins, and which sign-in surfaces that factor covers.
