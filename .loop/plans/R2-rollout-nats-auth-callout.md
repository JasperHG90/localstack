# R2: Rollout — NATS auth-callout bridge for OIDC/WI identity

## 1. Title

Deploy a NATS auth-callout bridge service and wire the `nats` server to
delegate authentication to it, so a client presenting a valid Vault
(human OIDC) or Nomad Workload Identity (machine) JWT is issued a scoped
NATS user JWT and unauthenticated clients are rejected.

## 2. Size / Effort

**L (new bridge service).** The size drivers: (1) a brand-new callout
service must be authored, containerized, and pushed to the cluster's
private registry (no off-the-shelf image exists for this repo's exact
issuer/permission mapping); (2) it introduces the cluster's first
NATS-native nkey/operator signing identity, a second identity system
that must be generated, stored in Vault, and injected via `template`;
(3) the `nats` server config (`nats.hcl:79-94`) must move from no-auth to
`authorization { auth_callout { ... } }`, a change that can lock every
client out of the bus if misconfigured. This is the first service in the
repo to consume both the Nomad WI JWKS and the Vault OIDC JWKS.

## 3. Triggered by

Auth epic, stage R2. NATS has no native OIDC verification
(nats-io/nats-server#5692), so the confirmed design (Vault = human OIDC
IdP, Nomad WI = machine identity) cannot be enforced on the bus directly.
NATS 2.10+ auth callout is the bridge: an external service validates the
incoming OIDC/WI JWT and mints a native NATS user JWT. The `nats` service
runs 2.10 today (`nats.hcl:69`, `docker.io/nats:2.10-alpine`), so the
capability is present. Informed by the S3 finding on auth-callout
maturity. Depends on F1 (Nomad WI trust) and F2 (Vault OIDC).

## 4. Context

Today the bus has **no authentication**. This is stated in three places
and all three must change or be reconciled:

- The server config template mints a plain listener with only
  `jetstream`, no `authorization` block:
  `deployments/infrastructure/services/nats.hcl:79-94` (the `template`
  block, `destination = "local/nats-server.conf"`). The container is
  launched with `args = ["--config", "/local/nats-server.conf"]`
  (`nats.hcl:70`).
- The firewall comment records the intent explicitly:
  `deployments/infrastructure/services.tf:261` (`# NATS+JetStream on
  radxa-dragon-q6a (LAN-only; no auth in v1)`), opening 4222/8222 to
  `192.168.0.0/16` at `services.tf:262-277`.
- The how-to doc states `**Auth:** none` and "Treat the bus as trusted":
  `docs/nats.md` (TL;DR section). This doc will be factually wrong once
  auth is on and must be updated (see Open Questions Q5).

The two trusted JWT issuers the callout must verify **already exist** in
the cluster:

- **Machine (Nomad WI):** Nomad serves a JWKS at
  `http://<nomad>:4646/.well-known/jwks.json` — this exact URL is already
  consumed by Vault's JWT auth method configuration in
  `bootstrap/roles/nomad_server/tasks/main.yml:220`
  (`jwks_url="http://127.0.0.1:4646/.well-known/jwks.json"`,
  `jwt_supported_algs="RS256,EdDSA"`). Nomad workloads receive a default
  identity with `aud = ["vault.io"]` and 1h TTL:
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42-44`. A client
  job that talks to NATS will need its own additional WI `identity` block
  with a NATS-specific audience (see Open Questions Q3).
- **Human (Vault OIDC):** provided by F2 (Vault as OIDC provider). Vault
  runs as plain HTTP (`provider "vault" {}`, `providers.tf:28`); its
  OIDC discovery/JWKS endpoint is an F2 deliverable this ticket consumes,
  not defines.

The established secret-injection and provisioning conventions this
service must follow:

- **Vault template injection**: services read secrets via a `template`
  block with `{{ with secret "<path>" }}...{{ end }}` and a `vault {}`
  block. Canonical example: `deployments/infrastructure/services/postgres.hcl:70`
  (`vault {}`) and `postgres.hcl:72-80` (the `template` rendering
  `POSTGRES_PASSWORD` from `${postgres_secret}`).
- **Secret provisioning**: a `random_password` + `vault_kv_secret_v2`
  pair in Terraform, named `default/<job>/<entry>`, mounted on
  `vault_mount.kvv2`. Canonical example:
  `deployments/infrastructure/secrets.tf:10-30` (minio: `random_password`
  then `vault_kv_secret_v2` with `name = "default/minio/localstack"`).
  The full mount is `var.secret_mount` (`variables.tf:1-4`).
- **Job registration**: each service is a `nomad_job` resource using
  `templatefile(...)` with Vault secret paths passed as vars. The `nats`
  job is registered at `deployments/infrastructure/services.tf:364-366`
  (currently `templatefile(..., {})` — no vars).

What is missing: the callout service does not exist; the `nats` server
does not delegate auth; there is no NATS nkey/operator signing identity
in Vault; and no client requests a NATS-scoped WI audience.

## 5. Non-goals / out of scope

- **Not building the human OIDC IdP (F2) or the Nomad WI trust (F1).**
  This ticket consumes their JWKS/issuer endpoints; it does not stand
  them up. If F1/F2 are not landed, this ticket is blocked (see Risk).
- **Not migrating existing NATS clients' behavior semantics.** JetStream
  streams, subjects, and the `docs/nats.md` pub/sub patterns stay as-is;
  only the auth handshake in front of them changes.
- **Not adding TLS to the NATS listener.** The bus stays plain TCP on the
  LAN; the callout validates a bearer JWT, it does not add mTLS. TLS is a
  separate concern (surface in Q4, do not build).
- **Not designing a full RBAC matrix for every service.** Deliver a
  minimal, explicit subject-permission mapping sufficient to prove the
  success criteria (one machine role, one human role). Broader
  per-service permissions are follow-up work.
- **Not replacing NATS's native account/operator model.** The callout
  bridges external OIDC/WI identity *into* NATS's native user-JWT model.
  The nkey/operator JWT system is NATS-internal and is not an OIDC thing;
  do not conflate the two or try to make Vault mint NATS operator JWTs.
- **Not touching the `nats-exporter` task** (`nats.hcl:102-143`) beyond
  what auth forces (the exporter scrapes the monitor port 8222, not the
  client port; confirm it is unaffected, do not redesign it).

## 6. Requirements & restrictions

The rollout MUST:

1. **Deploy an auth-callout service** that: subscribes to the NATS auth
   callout request subject; extracts the presented JWT from the connect
   request; validates it against **both** trusted issuers — Nomad WI
   JWKS (`main.yml:220` URL) and Vault OIDC JWKS (F2) — checking
   signature, issuer, audience, and expiry; on success mints and returns
   a **signed NATS user JWT** whose permissions match the caller's
   identity class; on failure (invalid, expired, or absent token)
   returns an error so NATS rejects the connection.
2. **Configure the `nats` server to delegate authentication** by adding
   an `authorization { auth_callout { ... } }` stanza to the config
   template at `nats.hcl:79-94`, naming the callout's issuer account and
   the auth user NATS uses to invoke the callout. Existing `jetstream`
   config must be preserved.
3. **Wire the callout's NATS signing key (nkey seed / account signing
   key) via a Vault `template`**, following the `postgres.hcl:70,72-80`
   pattern — never hardcoded. The key material is provisioned in
   Terraform as a `random_password`/generated-nkey + `vault_kv_secret_v2`
   pair named `default/nats-auth-callout/<entry>`
   (`secrets.tf:10-30` pattern), and the path is passed into both the
   `nats` job and the callout job via `templatefile` vars
   (`services.tf:364-366` is where the `nats` job gains a var; a new
   `nomad_job "nats_auth_callout"` is added nearby).
4. **Satisfy the success criteria end to end**: a client presenting a
   valid Vault or Nomad WI JWT is issued a scoped NATS user JWT and can
   pub/sub on its permitted subjects; a client with an invalid or absent
   token is rejected.

Restrictions the repo enforces (each cited):

- **Secrets only in Vault KV2, never hardcoded** (`CLAUDE.md`, "Key
  Conventions"). The NATS signing key and any callout credentials go
  through `vault_kv_secret_v2` + a `template` block. `detect-private-key`
  (`.pre-commit-config.yaml`) will fail the commit if a key seed is
  committed to an HCL/source file.
- **Simplicity / no speculative build** (`CLAUDE.md` sections 1-2 and
  `.claude/rules/...`): minimal permission mapping, no configurability
  that R2's success criteria do not require. Present the identity->subject
  mapping as a tradeoff, do not silently invent a broad RBAC scheme.
- **Podman, not Docker** (`CLAUDE.md`, "Key Conventions"): the callout
  task uses `driver = "podman"` like every task in `nats.hcl:35,103`.
- **HCL formatting** (`.pre-commit-config.yaml`, `nomad-fmt` hook; `just
  format` = `nomad fmt -recursive`): all new/edited `.hcl` must be
  `nomad fmt`-clean.
- **All code needs tests** (`.claude/rules/python-testing.md`): the
  callout service's validation logic (accept valid, reject
  invalid/expired/wrong-audience/absent) ships with tests. If written in
  Python, use `uv` + `uv run pytest`, mock only the true external
  boundary (the JWKS fetch via respx), and mark any test that hits a live
  NATS/Vault with an `integration` marker excluded from the default run.
- **Docs must stay truthful** (`.claude/rules/slop-scan-for-docs.md`):
  the `**Auth:** none` claim in `docs/nats.md` becomes a hallucination
  once auth is on; update it (Q5). Any doc edit passes the three-layer
  slop scan.
- **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`).

## 7. Code surface

- **`deployments/infrastructure/services/nats.hcl:79-94`** — EDIT the
  server-config `template`: add `authorization { auth_callout { issuer:
  ..., auth_users: ..., account: ... } }`, preserving `jetstream`
  (`nats.hcl:86-90`). Add a `vault {}` block and a second `template` (or
  extend) to inject the callout issuer public key / auth-user creds from
  Vault, mirroring `postgres.hcl:70,72-80`.
- **`deployments/infrastructure/services/nats.hcl:70`** — VERIFY the
  `--config` arg path still points at the rendered config after the edit.
- **CREATE `deployments/infrastructure/services/nats-auth-callout.hcl`**
  — the new callout job (Podman task, `vault {}` + `template` for the
  signing key, image pulled from the cluster's private registry on
  firebat:5000 per `services.tf:194`). Model structure on `nats.hcl`.
- **`deployments/infrastructure/services.tf:364-366`** — EDIT the
  `nomad_job "nats"` to pass the new Vault secret path(s) into
  `templatefile(...)` (currently `{}`), and ADD a `nomad_job
  "nats_auth_callout"` resource beside it.
- **`deployments/infrastructure/secrets.tf`** (pattern at `:10-30`) —
  ADD a `random_password`/generated-nkey + `vault_kv_secret_v2` named
  `default/nats-auth-callout/<entry>` on `vault_mount.kvv2`.
- **`deployments/infrastructure/services.tf:262-277`** — REVIEW the
  `nats` firewall rules and UPDATE the `no auth in v1` comment at
  `services.tf:261`; if the callout service needs its own port reachable,
  add a rule (Q2).
- **`bootstrap/roles/nomad_server/tasks/main.yml:220`** — READ-ONLY
  anchor: the Nomad WI JWKS URL the callout validates machine tokens
  against. `nomad.hcl.j2:42-44` — READ-ONLY anchor: default WI audience
  (`vault.io`), context for the client-side audience decision (Q3).
- **CREATE the callout service source + tests** — location and language
  are Q1. Its validation logic is the tested code surface.
- **`docs/nats.md`** — EDIT the `**Auth:**` line and any "no auth"
  statement to describe the callout handshake (Q5).

## 8. Tests & validation gates

Two tiers: a repo gate that must pass before any apply, and live evals
that prove the R2 success criteria against the running cluster.

### Repo gate (pre-apply, offline)

- **`just pre_commit`** (root `justfile` `pre_commit:` =
  `pre-commit run --all-files`). Configured hooks
  (`.pre-commit-config.yaml`): check-json, check-ast,
  check-merge-conflict, check-yaml (`--unsafe`), debug-statements,
  **detect-private-key** (fails on a committed nkey seed),
  end-of-file-fixer, **nomad-fmt** (all `.hcl` must be `nomad fmt`
  clean), and the Terraform hooks **terraform-fmt** (`terraform fmt
  -check -recursive`) plus **terraform-validate** (runs
  `scripts/tf_validate.sh`, which `terraform validate`s each root:
  `deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`). The new `secrets.tf` and
  `services.tf` edits are therefore format-checked and validated by this
  gate; there is no "Terraform not validated" caveat. `.pre-commit-config.yaml:1`
  excludes `^\.(claude|loop)/`, so this ticket file is not linted, but
  the new HCL, TF, service source, and `docs/nats.md` are.
- **Callout service unit tests** (`.claude/rules/python-testing.md`,
  `all-code-needs-tests`). The callout is a new Python service (Q1:
  `nats-py` under, e.g., `applications/nats-auth-callout/`), so its own
  test command is **`uv run pytest`**. Parametrized validator cases:
  valid Nomad WI token accepted; valid Vault OIDC token accepted;
  expired token rejected; wrong-audience token rejected; wrong-issuer
  token rejected; absent token rejected. Mock the JWKS fetch at the HTTP
  boundary (respx for httpx) with fixture JWKS; sign fixture JWTs with a
  test key. Any test hitting live NATS/Vault carries an `integration`
  marker excluded from the default run.
- **Doc slop scan** (`.claude/rules/slop-scan-for-docs.md`) on the
  `docs/nats.md` edit: Layer 0 categorical (no stale `Auth: none`
  hallucination), thesis-first, American spelling, 80-char wrap.

### Evals — live acceptance (needs F1+F2 landed; runnable now)

The cluster is reachable: `VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`,
`NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set, so these evals are
runnable, not hypothetical. Each maps 1:1 to a Requirement-6.4 success
criterion. All depend on F1 (Nomad WI trust) and F2 (Vault OIDC JWKS)
being deployed (Q6); without them the callout has no issuer to validate
against and the evals cannot pass. Run evals 1-2 after Subticket 3
(callout registered) as a pre-apply smoke check; run the full set 1-5 at
close-out (Subticket 7).

1. **Allocs healthy (pre-apply smoke, then close-out).**
   Command: `nomad job status nats` and `nomad job status
   nats-auth-callout`.
   Expected: both jobs `running`; every alloc `running` with its health
   check passing (the callout alloc healthy, and the `nats` alloc still
   healthy after the `auth_callout` config change).
2. **Machine identity: issuance + scoped pub/sub (close-out).**
   Command: from a client holding a valid Nomad WI JWT that carries the
   NATS-scoped audience (Q3), save a context and pub/sub on a permitted
   subject, e.g. `nats context save wi --server <nats>:4222 --creds
   <wi-jwt>` then `nats sub <permitted-subject>` and `nats pub
   <permitted-subject> hello`.
   Expected: connection accepted, a scoped NATS user JWT is minted, and
   the published message is delivered to the subscriber (exit 0).
3. **Human identity: issuance + scoped pub/sub (close-out).**
   Command: same as eval 2 but presenting a valid Vault (human OIDC) JWT.
   Expected: connection accepted, a scoped user JWT is minted, and
   pub/sub on a permitted subject succeeds.
4. **Non-permitted subject denied (close-out).**
   Command: reusing the same valid token from eval 2 or 3, `nats pub
   <non-permitted-subject> nope` (and `nats sub` on it).
   Expected: a permissions-violation error; the operation is refused even
   though the connection authenticated. Proves the minted user JWT is
   scoped, not full-access.
5. **Invalid / absent token rejected — fail-closed (close-out).**
   Command: connect presenting a malformed/expired JWT, then connect with
   no token at all, e.g. `nats pub <any-subject> x --server <nats>:4222`
   with no `--creds`.
   Expected: connection **rejected** (authorization violation), no user
   JWT issued in either case. Confirms the fail-closed posture (Q4): an
   absent token never yields access.

### Before reporting done

- **Adversarial review** (`.claude/rules/adversarial-reviews.md`):
  confirm eval 5 truly rejects invalid/absent tokens (not silently
  allowed) and that no key material leaked into a committed file
  (cross-check the `detect-private-key` gate result).

### Eval marker

- The five-column eval marker for these scenarios lives at
  `.loop/evals/R2-rollout-nats-auth-callout.md` (validate with `loopctl eval
  R2-rollout-nats-auth-callout`).

## 9. Risk assessment

- **Blast radius: high on the bus.** A malformed `auth_callout` stanza in
  `nats.hcl:79-94`, or a callout service that is down, can lock **every**
  NATS client out (existing JetStream producers/consumers in `docs/nats.md`
  included). The callout is a hard dependency in the connect path.
- **Reversibility: high but not instant.** Reverting the `nats.hcl`
  `authorization` block and re-applying restores open access; but any
  client reconfigured to send a JWT must also be reverted. Keep the
  no-auth config diff small and revertible.
- **Likeliest failure modes:**
  1. **Callout availability = bus availability.** If the callout crashes,
     new connections fail. Mitigation: health check, and decide the
     failure posture (fail-closed is correct for auth; document it).
  2. **Conflating the two identity systems.** Trying to make Vault issue
     NATS operator JWTs, or treating the nkey signing key as an OIDC
     secret. Mitigation: Non-goals and Requirement 3 keep them separate.
  3. **Key leak.** Committing an nkey seed to HCL/TF. Mitigation:
     `detect-private-key` gate + Vault-only injection (Requirement 3).
  4. **Blocked on F1/F2.** The callout cannot validate tokens whose JWKS
     endpoints do not yet exist. Mitigation: dependency stated; Q6 asks
     the operator to confirm F1/F2 are landed before the loop runs.
  5. **Audience mismatch.** Nomad's default WI audience is `vault.io`
     (`nomad.hcl.j2:43`); if the callout expects a NATS-specific audience
     but clients send the default, valid machines are rejected. Mitigation:
     Q3 settles the client-side audience contract up front.

## 10. Subtickets

Ordered, dependency-aware.

1. **Provision the NATS signing identity in Vault.** Add the
   `random_password`/nkey + `vault_kv_secret_v2`
   (`default/nats-auth-callout/*`) in `secrets.tf` (pattern `:10-30`).
   Depends on: nothing.
2. **Build the callout service + unit tests.** Validate WI + Vault JWTs
   against their JWKS (`main.yml:220` URL for machine), mint scoped NATS
   user JWTs. Full accept/reject test matrix. Depends on: 1 (signing key
   shape), F1/F2 (issuer/JWKS endpoints).
3. **Package and register the callout job.** New
   `nats-auth-callout.hcl` (Podman, `vault {}` + signing-key `template`),
   image to the private registry (`services.tf:194`), new
   `nomad_job "nats_auth_callout"` in `services.tf`. Depends on: 2.
4. **Wire the `nats` server to delegate auth.** Add
   `authorization { auth_callout { ... } }` to `nats.hcl:79-94`, inject
   the issuer/auth-user creds via Vault, pass the path through the
   `nomad_job "nats"` `templatefile` (`services.tf:364-366`). Depends
   on: 1, 3.
5. **Client-side WI audience + one worked client.** Give a sample client
   job a NATS-scoped WI `identity` (Q3) and prove issuance + scoped
   pub/sub. Depends on: 4.
6. **Firewall + docs.** Reconcile `services.tf:261-277` and update
   `docs/nats.md` `**Auth:**` (Q5). Depends on: 4.
7. **Integration acceptance + adversarial review.** Depends on: 5, 6.

## 11. Open questions

Operator should settle Q1-Q4 and Q6 before the loop runs; Q5 is a
mechanical follow-on.

- **Q1 — Language and location of the callout service?** The repo is
  HCL/Terraform/Ansible with Python tooling conventions
  (`.python-version` = 3.12, `uv`, pytest rules). *Recommendation:* write
  it in Python with `nats-py` (already the blessed client per
  `docs/nats.md` section 2) under a new top-level dir (e.g.
  `applications/nats-auth-callout/`), tested with `uv run pytest`.
  Operator confirm the path and language.
- **Q2 — Where does the callout run, and does it need a firewall rule?**
  It must reach the NATS client port (4222) and both JWKS endpoints
  (Nomad 4646, Vault 8200). *Recommendation:* colocate on
  radxa-dragon-q6a with the `nats` server (same constraint as
  `nats.hcl:8-10`) so the callout<->NATS hop stays on-host; no new
  inbound LAN rule needed. Confirm.
- **Q3 — What audience do NATS clients put in their WI token?** Nomad's
  default WI audience is `vault.io` (`nomad.hcl.j2:43`). *Recommendation:*
  require clients to declare an additional WI `identity` block with a
  dedicated audience (e.g. `nats.io`) and have the callout require it, so
  a Vault-bound token is not silently accepted by NATS. Settle the exact
  audience string before build (it is a contract between every client and
  the callout).
- **Q4 — Fail-closed confirmation and TLS posture.** Auth callout should
  fail closed (no token = reject). *Recommendation:* fail closed,
  explicitly; leave the listener plain-TCP on the LAN (no mTLS) per
  Non-goals. Confirm the operator accepts a bearer-JWT-over-plain-TCP LAN
  posture for now.
- **Q5 — `docs/nats.md` scope of edit.** *Recommendation:* update the
  `**Auth:**` TL;DR line and the "no auth" wording to a short callout
  description with a pointer to this rollout; do not rewrite the whole
  how-to. Mechanical, low risk.
- **Q6 — Are F1 and F2 landed?** This ticket consumes the Nomad WI trust
  (F1) and the Vault OIDC JWKS (F2). *Recommendation:* operator confirms
  both are deployed before the loop starts; otherwise Subticket 2 has no
  Vault-side issuer to validate against and the integration gate cannot
  pass.
