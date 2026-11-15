<!-- kmctl writes this index from the pages in this folder: run kmctl check --fix to update it, do not edit it by hand. -->
# Explanation

- [Why each backup job has its own credentials](backup-job-credentials.md): Why each backup job reads its own copy of the PostgreSQL, SeaweedFS and GCS credentials under its own job path.
- [Why the cluster roles are shaped the way they are](cluster-roles.md): What the developer, admin and app-user roles buy, what they do not, and why removing someone does not end their session.
- [How dash reaches two tasks through one route](dash-routing.md): How oauth2-proxy sends dash's one hostname to its frontend and backend tasks.
- [OpenViking identity](openviking-identity.md): Why OpenViking takes account and user from Vault entity metadata, what that costs, and why an agent shares its person's identity.
- [Why lab names are in public DNS](public-lab-dns.md): Why lab names resolve from public DNS to a private address, what that exposes, and why there is no local resolver.
- [Why registry-ui stays cheap, and where it stops scaling](registry-ui-cost.md): Why the registry-ui walk of the cluster registry stays cheap, and at what size it stops fitting.
- [The retrieval-quality canary](retrieval-quality-canary.md): Why driftwatch dials embark directly, and what a canary over a fixed corpus cannot tell you.
- [Two-factor auth on Vault logins](vault-login-mfa.md): Why the TOTP second factor is on the Vault userpass login, and what it leaves uncovered.
- [Vault OIDC tokens, and what a relying party has to know](vault-oidc-tokens.md): What a service that verifies Vault OIDC tokens itself has to know, and how to revoke a long-lived ID token.
- [Why monitoring is not behind the edge](why-monitoring-is-not-behind-the-edge.md): Why Prometheus, Loki and Tempo have no route through the edge proxy, and what that costs.
- [Nomad Workload Identity and the Vault JWT trust chain](workload-identity.md): How a Nomad task's Workload Identity JWT, or a GitHub workflow's Vault identity token, becomes a scoped Vault token or SeaweedFS credential, and the conventions a new consumer follows.
