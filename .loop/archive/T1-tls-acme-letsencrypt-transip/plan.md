---
epic = "tls"
depends_on = []
priority = 70
---

# T1 — Obtain a Let's Encrypt wildcard for `*.lab.orangecluster.nl` into Vault KV2

## Title
Periodic Nomad job runs lego DNS-01 against TransIP, writes cert + key +
issuing chain to Vault KV2 `secret/data/default/haproxy/tls`. Nothing consumes
it yet; HAProxy keeps serving its current cert.

## Size / Effort
**Medium.** Driver is not the HCL. It is (a) persisting lego's account and
certificate state across periodic runs, (b) getting the single Vault token's
policy set right, and (c) writing KV2 from an image that contains only the
lego binary. The job shell mirrors `backup-minio.hcl`.

## Triggered by
F3 shipped a Vault-PKI leaf whose SAN `*.localstack` cannot match
`grafana.localstack` (a wildcard needs >=2 labels after the `*`), so no client
accepts it. Verified live: `curl: (60) SSL: no alternative certificate subject
name matches target host name`, `openssl ... verify error:num=62:hostname
mismatch`. Private-CA trust also cannot reach mobile clients without per-device
root installation. Operator elected a publicly-trusted cert on a real domain.

## Context (today's state)
Verified live 2026-07-25 unless noted.

- **Credential provisioned.** `secret/data/default/acme/transip` holds
  `account_name` (TransIP login username, NOT the email) and `private_key`
  (PKCS#8, 2048-bit). `POST /v6/auth` -> 201; `GET /v6/domains` -> 200 listing
  `jasperginn.nl`, `orangecluster.nl`, `orangehomelab.nl`.
- **No IP whitelist needed.** Key pair is `Whitelisted IP: Nee`. A token minted
  with `global_key: true` works from any address. OMITTING `global_key`
  defaults it to `false` and every subsequent call fails `Remote IP is not
  authorized`. lego's gotransip client requests a global token by default.
- **CAA published.** `orangecluster.nl`, name `lab`, content
  `0 issue "letsencrypt.org"`. The apex carries no CAA, so RFC 8659's fallback
  to the `issue` tag at `lab.orangecluster.nl` governs wildcard issuance.
- **lego env contract** (https://go-acme.github.io/lego/dns/transip/):
  `TRANSIP_ACCOUNT_NAME`, `TRANSIP_PRIVATE_KEY_PATH` (a FILE path — the key
  must be rendered to disk). Optional `TRANSIP_PROPAGATION_TIMEOUT` (default
  600s), `TRANSIP_POLLING_INTERVAL` (10s), `TRANSIP_TTL` (10s).
- **Node architectures** (`nomad node status -verbose`): firebat
  (192.168.2.30) is **amd64**; orangepi4a, radxa-dragon-q6a, ubuntu, and
  jetson-orin-nano are arm64. All Nomad 1.11.3. `goacme/lego` publishes
  amd64, arm64, and arm manifests, so architecture constrains nothing here.
- **Periodic-job pattern:** `services/backup-minio.hcl:3` (`type = "batch"`),
  `:6-9` (`periodic { crons, prohibit_overlap }`), `:13-15` (hostname
  constraint), `:22` (image), `:24` (entrypoint/command override), `:28`
  (`vault {}`), `:30-52` (credential templates into `secrets/`). Registered in
  Terraform at `backup.tf:109-116`.
- **Host-volume pattern:** `services.tf:2-20` (`nomad_dynamic_host_volume`,
  `plugin_id = "mkdir"`, hostname constraint, `single-node-writer`).
- **ONE TOKEN, ONE ROLE.** A Nomad task has a single `vault` block and performs
  a single JWT login, so it holds exactly one policy set. `jwt-nomad`'s
  `default_role` is `nomad-workloads`, whose policy
  (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-7`)
  grants only `read` on `secret/data/<ns>/<job_id>/*`. F3's dedicated role
  (`pki.tf:113`) sets `token_policies` to the dedicated policy ALONE, dropping
  `nomad-workloads`. Copying that shape here would leave the `acme` job unable
  to read its own TransIP credential. See requirement 5.

## Non-goals / out of scope
- HAProxy consuming the cert. It keeps serving the F3 PKI leaf. T3.
- Renaming any hostname, ACL, or backend. T3.
- Deleting `pki.tf`. T3.
- dnsmasq / LAN resolution. T2. DNS-01 validates against public TransIP DNS
  and does not need it.
- Certificate distribution to clients. Public trust makes it unnecessary.
- Expiry alerting. Moved to T3 as a hard requirement, since silent expiry only
  becomes an outage once HAProxy serves this cert.

## Requirements & restrictions
1. Cert covers `*.lab.orangecluster.nl` AND `lab.orangecluster.nl` (a wildcard
   does not match the bare name). Let's Encrypt via DNS-01, the only challenge
   type yielding a wildcard.
2. **lego state MUST persist across runs.** `lego renew` calls `log.Fatalf`
   when the account is unregistered or no certificate exists in `--path`
   (`cmd/cmd_renew.go`), and each periodic child job gets a fresh alloc dir.
   Provision a `nomad_dynamic_host_volume` on firebat, mount it, and point
   `--path` at it so `.lego/accounts/` and `.lego/certificates/` survive.
   Without this the job either fails every run or (if "fixed" with `lego run`)
   re-issues daily and trips the rate limit within a week.
3. Do NOT pass `--ari-disable`. ACME Renewal Information is on by default and
   ARI-driven renewals are exempt from Let's Encrypt rate limits.
4. Job is Nomad `batch` + `periodic`, matching `backup-minio.hcl:3-9`. Daily
   cron with `lego renew --days 30` no-ops until inside the renewal window and
   self-heals a failed day, preserving ~30 days of margin.
5. **The `acme` JWT role's `token_policies` must include BOTH
   `nomad-workloads` AND the new write policy** — or the write policy must
   itself grant `read` on `secret/data/default/acme/*`. The role must also
   replicate `claim_mappings` for `nomad_namespace` and `nomad_job_id`
   (`pki.tf:104-108`), because `nomad-workloads` is templated on
   `identity.entity.aliases.<accessor>.metadata.*` and resolves to nothing
   without them. Do NOT widen the shared Ansible-owned policy.
6. The write grant is `create` + `update` on exactly
   `secret/data/default/haproxy/tls`. **No `secret/metadata/*` capability is
   needed** for a KV2 data write.
7. **Write with `vault write secret/data/... data=@file`, not `vault kv put`.**
   The `kv` helper preflights `GET sys/internal/ui/mounts/<path>`
   (`command/kv_helpers.go`), which the `default` policy does not grant; a 403
   there fails the command. A raw `write` or HTTP `PUT` does no preflight.
8. **Name the write-back tooling.** `goacme/lego` is `FROM alpine:3` with only
   `ca-certificates`, `tzdata`, and `/usr/bin/lego`, and `ENTRYPOINT
   ["/usr/bin/lego"]`. There is no `vault`, `curl`, or `jq`. Override the
   entrypoint (pattern `backup-minio.hcl:24`) and either add a second task
   with a Vault-capable image or state the exact JSON-escaping strategy for a
   multi-line PEM. Hand-rolled `sh` escaping is how a stored-but-unloadable
   cert happens.
9. Pass `--dns.resolvers=1.1.1.1:53`. lego queries the authoritative NS for
   TXT propagation, but uses the SYSTEM resolver for apex determination. Once
   T2 lands, the system resolver is dnsmasq; pinning a public resolver keeps
   renewal independent of the LAN resolver entirely.
10. Credentials read from Vault via `template` into `secrets/`, never inlined
    (`CLAUDE.md` Secrets convention; pattern `backup-minio.hcl:30-52`).
11. Pinned image tag or digest, no `:latest` (`grafana.hcl:48`, `nats.hcl:69`;
    `backup-minio.hcl:22` uses `:latest` and is the exception, not the
    pattern).
12. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
13. `.claude/rules/adversarial-reviews.md`: adversarial review before done.
14. No secret value reaches the repo or job stdout. `detect-private-key`
    (`.pre-commit-config.yaml:12`) stays green; logs ship to Loki via promtail.

## Code surface
- `deployments/infrastructure/services/acme.hcl` **(new)** — batch+periodic
  job constrained to firebat: pinned lego image with overridden entrypoint,
  `vault { role = ... }`, templates rendering `TRANSIP_ACCOUNT_NAME` and the
  private key to `secrets/transip.key`, the host-volume mount for `--path`,
  the lego invocation, and the KV2 write-back.
- `deployments/infrastructure/acme.tf` **(new)** — `nomad_dynamic_host_volume`
  for lego state (pattern `services.tf:2-20`); `vault_policy` per requirements
  5-6; `vault_jwt_auth_backend_role` on backend `jwt-nomad` bound to
  `nomad_job_id = "acme"` / `nomad_namespace = "default"` with both policies
  and the claim mappings; `resource "nomad_job" "acme"` via `templatefile(...)`
  (pattern `backup.tf:109-116`).
- `docs/tls-certificates.md` **(new)** — the renewal loop, the KV2 field
  contract, how to check last renewal, how to recover a failed one.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. `.claude/rules/python-testing.md`
does not bind (no Python). Cluster reachable; `VAULT_*`, `NOMAD_*`, `CONSUL_*`
set in this environment.

### Repo gate
- **Command:** `just pre_commit` (`justfile:17-19`) -> all Passed.
- **Worktree note:** run `just worktree_setup <path>` first (added `3c12c7a`)
  or `tf_validate.sh` fails on the gitignored `.ssh/id_rsa`.
- **Command:** `terraform -chdir=deployments/infrastructure plan` -> adds the
  volume, policy, JWT role, and job. Destroys nothing.

### Evals — the authoritative set is `.loop/evals/T1-tls-acme-letsencrypt-transip.md`
The marker is the acceptance contract; the rows below are its narrative form.
Note the marker's rate-limit guard: **production issuance is blocked until
idempotency passes against the staging endpoint** (operator decision,
2026-07-25).
1. Job completes: `nomad job status acme` -> latest batch alloc `complete`,
   exit 0.
2. Cert in Vault: `vault kv get secret/default/haproxy/tls` returns the agreed
   fields.
3. Cert correct: leaf piped to `openssl x509 -noout -issuer -subject -ext
   subjectAltName -dates` -> Let's Encrypt intermediate issuer, SAN covers
   `*.lab.orangecluster.nl` and `lab.orangecluster.nl`, ~90d validity.
4. Chain validates against the SYSTEM trust store — the whole point:
   `openssl verify -untrusted <chain> <leaf>` -> OK, with no `-CAfile`.
5. **Idempotent (run against STAGING, before the production flip):** run the
   job twice; the second run leaves the cert serial unchanged. This is the
   rate-limit guard and must pass before any production issuance.
6. State survives: after two runs, the host volume contains
   `.lego/accounts/` and `.lego/certificates/`.
7. No leakage: `nomad alloc logs <alloc>` contains no `BEGIN ... PRIVATE KEY`.

## Risk assessment
- **Blast radius: near zero on success.** Nothing consumes the output;
  HAProxy untouched. A failed job is a failed batch alloc, not an outage.
- **Rate limits are the real hazard.** Let's Encrypt allows 50
  certs/registered-domain/week and 5 per exact identifier set per week. A job
  that re-issues every run exhausts that in under a week and locks out
  issuance — which then blocks T3. Requirements 2-4 and eval 5 exist for this.
- **TransIP propagation.** Default 600s; TransIP is slow. Shortening it causes
  intermittent challenge failures that look like credential problems and burn
  a rate-limit slot each time.
- **Credential blast radius.** The TransIP key is ACCOUNT-WIDE (no per-zone
  scoping) and usable from any IP. Compromise reaches `jasperginn.nl` DNS
  including its MX. Mitigated by the CAA record and 2FA on the account.
- **Reversibility: high.** Stop the job, delete the KV entry, destroy the
  volume.

## Subtickets (ordered)
1. `acme.tf`: host volume, policy, JWT role (both policies + claim mappings).
   `terraform validate` clean.
2. `acme.hcl`: job rendering credentials, mounting the volume, invoking lego
   against the STAGING endpoint. Prove DNS-01 completes.
3. KV2 write-back; verify field shape; eval 5 and 6 on staging.
4. Flip to production, re-issue, run evals 3 and 4.
5. `docs/tls-certificates.md`.
6. Adversarial review.

## Open questions
- **Q1 — Renewal cadence.** *Recommendation:* daily cron with `lego renew
  --days 30`. Self-healing and preserves the full 30-day margin, unlike a
  60-day cron where one failure consumes it.
- **Q2 — Staging vs production during implementation.** *Recommendation:*
  implement against `https://acme-staging-v02.api.letsencrypt.org/directory`,
  flip to production only once the challenge and the write-back both work end
  to end. Staging's limits are far looser and its certs are untrusted, which
  is fine because T1 serves nothing. **Note:** staging and production keep
  separate account state, so flipping requires a fresh registration in the
  same `--path`.
- **Q3 — KV2 field names.** The interface T3 codes against.
  *Recommendation:* `certificate`, `private_key`, `issuer_chain`, mirroring
  Vault PKI's naming so T3's template changes minimally.
- **Q4 — One task or two?** Requirement 8 allows a second task with a
  Vault-capable image. *Recommendation:* two tasks in one group sharing the
  volume — lego issues, a small task with the vault CLI writes. Cleaner than
  hand-escaping a PEM into JSON in busybox `sh`.
