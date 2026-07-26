---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 12
summary = "Point Grafana's built-in generic OAuth client at Vault's OIDC provider, so Grafana joins single sign-on without an oauth2-proxy in front of it. Configuration only; Grafana already authenticates, so this improves the login rather than closing a hole."
tags = ["grafana", "oidc", "vault", "terraform"]
---

# G1 — Sign in to Grafana with Vault OIDC, natively

## Title
Point Grafana's built-in generic OAuth client at Vault's OIDC provider, so
Grafana joins the single sign-on story without an oauth2-proxy in front of it.

## Size / Effort
**Small.** Configuration only: a handful of `GF_AUTH_GENERIC_OAUTH_*` settings
and an OIDC client in Terraform. No new job, no proxy, no HAProxy change. The
effort is in the lockout question (Q1) and role mapping (Q2), not the wiring.

## Triggered by
Operator, 2026-07-26. Every other human-facing service in the rollout epic is
planned behind oauth2-proxy, and Grafana was assumed to be covered by one of
those tickets. It is not: R1 covers MLflow, R4 Phoenix, R2 NATS, R3 Postgres,
and L1 is the landing page. Grafana was never assigned. It also does not need
a proxy, because it speaks OIDC itself:
https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/generic-oauth/

## Context (today's state)
- Grafana is NOT unauthenticated. Measured 2026-07-26:
  `curl http://192.168.2.47:3000` returns 302 to its login page. It is
  therefore not urgent in the way Prometheus and Loki were, and this ticket
  improves the login rather than closing a hole.
- Auth today is a local admin account. The password is a Terraform
  `random_password` written to Vault KV2 and injected via a Vault-templated
  `template { env = true }` block (`secrets.tf:46-66`,
  `services.tf` grafana job vars, `services/grafana.hcl`). Re-read those
  anchors; line numbers have moved this week.
- The job already has a `vault {}` stanza and the env-template pattern this
  change extends. No new mechanism is required.
- **Vault's OIDC provider does not exist yet.** F2 is the ticket that creates
  the issuer, keys, scopes and clients. This ticket consumes it and is gated
  on it in `depends_on`.
- F2's plan already anticipates per-tier identity groups
  (`minio-admins`, `minio-readers`, `minio-writers`, `dashboard-users`). Q2
  below decides whether Grafana maps roles from those or treats every
  authenticated user the same.
- The edge serves `grafana.lab.orangecluster.nl` after the cutover, so the
  redirect URI must use that hostname rather than the node address or the old
  `.localstack` name.

## Non-goals / out of scope
- **Putting Grafana behind oauth2-proxy.** It has a native OIDC client; a
  proxy in front would be a second, redundant auth layer.
- Creating the Vault OIDC provider, issuer, or signing keys. That is F2.
- Changing Grafana's network reachability. N1 deliberately leaves its firewall
  rule alone.
- Migrating dashboards, datasources, or alert rules.
- Removing Grafana's local admin account. See Q1: that is the lockout
  question, and this ticket should not silently answer it.
- Anonymous or viewer-without-login access.

## Requirements & restrictions
1. Grafana authenticates users against Vault's OIDC provider using its own
   generic OAuth client. No proxy.
2. The client ID and secret come from Vault KV2 via the existing
   `template { env = true }` pattern, never hardcoded (`CLAUDE.md` Secrets
   convention). `detect-private-key` (`.pre-commit-config.yaml:12`) stays
   green.
3. The OIDC client is declared in Terraform beside F2's other clients, not
   created by hand in Vault.
4. `root_url` and the redirect URI use the post-cutover hostname
   `https://grafana.lab.orangecluster.nl`. A mismatched redirect URI is the
   most common failure and presents as a provider-side error, not a Grafana
   one.
5. Preserve a way in that does not depend on Vault (Q1). Vault being sealed or
   the OIDC provider misconfigured must not mean nobody can reach the
   dashboards that would diagnose it.
6. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
7. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services/grafana.hcl` — add the
  `GF_AUTH_GENERIC_OAUTH_*` settings and `GF_SERVER_ROOT_URL` to the existing
  env template. Re-read for current line numbers.
- `deployments/infrastructure/oidc.tf` (created by F2) — add a
  `vault_identity_oidc_client` for Grafana with its redirect URI.
- `deployments/infrastructure/secrets.tf` — store the client secret in KV2
  following the `random_password` + `vault_kv_secret_v2` shape at `:46-66`.
- `deployments/infrastructure/services.tf` — thread the new secret path into
  the grafana `templatefile(...)` var map.
- `docs/monitoring.md` — how to sign in, and how to recover if OIDC is down.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`).
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> adds the
  OIDC client and the secret, updates the grafana job in place. Destroys
  nothing.

### Evals — the authoritative set is `.loop/evals/G1-grafana-native-oidc-login.md`
(author with `create-eval` before implementation; `require_eval` is on).
The load-bearing rows are: a real browser login end to end, the local-admin
fallback still working per Q1, and the guardrail that an unauthenticated
request is still refused.

## Risk assessment
- **Lockout is the main risk.** Configured wrong, or with Vault sealed, and
  nobody can log in to the monitoring system precisely when something is
  broken. Requirement 5 and Q1 exist for this. Grafana is where you look when
  the cluster misbehaves, so losing it during an incident is worse than the
  problem it was meant to solve.
- **Redirect URI mismatch** is the likeliest configuration error and produces
  an opaque provider-side error.
- **Dependency on F2 is real, not nominal.** Nothing here can be tested until
  the issuer exists.
- **Blast radius: one service, and it already requires a login.** This is a
  login upgrade, not a hole being closed.
- **Reversibility: high.** Remove the env settings and the local admin login
  works exactly as before.

## Subtickets (ordered)
1. OIDC client + client secret in Terraform (after F2 lands).
2. Grafana env settings, including `root_url` and the redirect URI.
3. Apply; log in through a browser end to end.
4. Verify the Q1 fallback actually works, by signing in that way deliberately.
5. Docs.
6. Adversarial review.

## Open questions
- **Q1 — Keep the local admin account, or make OIDC the only way in?**
  *Recommendation:* keep it. Grafana is the tool you reach for when Vault or
  the network is misbehaving, and an OIDC-only configuration means an incident
  in the identity layer also blinds the monitoring. Keeping local login is a
  slightly larger credential surface for a much smaller failure mode. If the
  operator prefers OIDC-only, that decision should be explicit rather than a
  side effect, and the recovery path should be documented before it is needed.
- **Q2 — Map OIDC groups to Grafana roles, or give everyone the same role?**
  F2 plans identity groups including `dashboard-users`. *Recommendation:*
  start flat, with every authenticated user an Editor, matching the epic's
  stated "any successful login is authorized" posture for a single-operator
  home lab. Role mapping is straightforward to add later via
  `role_attribute_path`, and is unnecessary complexity until there is a second
  human with different needs.
- **Q3 — Does `auto_login` or `oauth_auto_login` get enabled?** It skips the
  Grafana login page and jumps straight to Vault. *Recommendation:* leave it
  off initially. With it on, a broken OIDC configuration can make the login
  page itself unreachable, which interacts badly with Q1's fallback.
