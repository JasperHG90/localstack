S3-spike-oidc-version-claims: verify version-dependent OIDC/auth behavior for MinIO, MLflow, NATS, Postgres against deployed image pins

## 1. Title

Time-boxed research spike that verifies the version-dependent auth
behavior of the four services on the auth-epic critical path (MinIO,
MLflow, NATS, PostgreSQL), pinned to the exact image tags deployed in
this repo, and records the impact of each verified fact on the
downstream tickets (M1, R1, R2, R3, R4). No infra change. The
deliverable is a findings doc per service.

## 2. Size / Effort

S. Reading current upstream docs and issue trackers plus resolving the
deployed versions already in-repo. Effort is driven by four
independent research threads, not by code. The only writes are
markdown findings docs.

## 3. Triggered by

Auth epic (Vault = OIDC IdP for humans, Nomad Workload-Identity JWTs =
machine identity). Downstream tickets M1/R1/R2/R3/R4 each assume a
version-dependent capability exists. This spike de-risks them by
confirming or refuting each assumption against the pinned versions
before implementation work is scheduled.

## 4. Context

Deployed image pins, resolved in-repo (cite these exact anchors in the
findings docs, do not re-guess them):

- MinIO server: `deployments/infrastructure/services/minio.hcl:66`
  pins `docker.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`. The job
  currently sets only `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` /
  `MINIO_PROMETHEUS_AUTH_TYPE` (`minio.hcl:32-40`); there is no
  `identity_openid` config today.
- MinIO Terraform provider: `aminueza/minio` constrained `~>3.8.0` in
  `deployments/applications/providers.tf`, resolved to `3.8.3` in
  `deployments/applications/.terraform.lock.hcl`. This provider is what
  R-tickets would use to declare any policy/role resources.
- MLflow: version string `"2.20.0"` at
  `deployments/applications/services.tf:196`, consumed by the image
  template `ghcr.io/mlflow/mlflow:v${mlflow_version}` at
  `deployments/applications/services/mlflow.hcl:36`. MLflow runs behind
  no auth today (`mlflow.hcl:38-41` starts `mlflow server` bare).
- NATS: `docker.io/nats:2.10-alpine` at
  `deployments/infrastructure/services/nats.hcl:69`. The embedded
  server config (`nats.hcl:79-94`) has no `authorization` /
  `auth_callout` block today.
- PostgreSQL: `docker.io/pgvector/pgvector:pg18-trixie` at
  `deployments/infrastructure/services/postgres.hcl:52` (PG18). Server
  args at `postgres.hcl:54-62` set tuning flags only; no OAuth config.
- Ingress is HTTP-only: HAProxy fronts services on port 80 with no TLS
  (`docs/haproxy_reverse_proxy.md:19`), routing `s3.localstack` to
  9000 and `minio.localstack` to 9001
  (`docs/haproxy_reverse_proxy.md:9-13`). This directly bears on the
  MinIO OIDC redirect / HTTP-vs-HTTPS thread.

What is missing: none of these version-dependent behaviors is
documented in-repo. There is no existing auth findings doc under
`docs/` to extend.

## 5. Non-goals / out of scope

- No infrastructure change. No edit to any `.hcl` job, `.tf`, provider
  config, or Vault/Nomad state. This spike is read-only toward all
  product/infra code.
- Not deciding the final auth design for any downstream ticket. The
  spike reports verified facts and their implications; M1/R1/R2/R3/R4
  make the design decisions.
- Not implementing, testing, or deploying any OIDC config, oauth2-proxy
  sidecar, NATS auth-callout service, or Postgres OAuth validator.
- Not upgrading any pinned version. If a needed capability only exists
  in a newer version, record that as a finding, do not bump the pin.
- No live probing of the running cluster (no requests to the deployed
  MinIO/NATS/Postgres). Research is from upstream docs/issues plus the
  in-repo pins.

## 6. Requirements & restrictions

Must:

- Pin every finding to the exact deployed version resolved above, not
  to "latest". A capability that exists only in a version newer than
  the pin is a NEGATIVE finding for that pin and must be labeled as
  such, with the first version that introduces it.
- Produce one findings doc per service (MinIO, MLflow, NATS,
  PostgreSQL): verified version facts, the upstream source for each
  fact (doc URL or issue number), and a short "impact on downstream
  tickets" section naming which of M1/R1/R2/R3/R4 the fact gates.
- Cite the in-repo version anchors (the `path:line` list in section 4)
  in each doc so a reader can re-resolve the pin.

Restrictions (repo principles, each cited to where the repo states
them):

- Surface tradeoffs and unresolved interpretations rather than picking
  silently (`CLAUDE.md` section 1, "Think Before Coding"). Where an
  upstream capability is ambiguous or the doc/issue is inconclusive,
  record it as an open question, do not assert a resolution.
- Documentation must pass the three-layer slop scan before it is
  reported done: P0 (no hallucinated identifiers, paths, URLs, or
  version strings; every backticked identifier and cited path
  resolves), document economy, and sentence-level checks
  (`.claude/rules/slop-scan-for-docs.md`). Every version string, image
  tag, issue number, and URL in a findings doc is a hallucination-risk
  identifier and must resolve to a real thing.
- Prose lines wrap at 80 chars; American spelling; 0-2 em dashes per
  1000 words (`.claude/rules/slop-scan-for-docs.md` Layer 2). The gate
  `pre-commit run --all-files` also runs `end-of-file-fixer` and
  `check-yaml`/`check-json` on any touched files
  (`.pre-commit-config.yaml`).

## 7. Code surface

This spike writes no code and no HCL/TF. It writes markdown findings
docs only. The in-repo files below are READ to resolve pins and cited
in the docs; none is edited.

- `deployments/infrastructure/services/minio.hcl:66` — MinIO image pin;
  read-only, cited.
- `deployments/applications/providers.tf` (minio block) and
  `deployments/applications/.terraform.lock.hcl` (aminueza/minio
  3.8.3) — MinIO provider version; read-only, cited.
- `deployments/applications/services.tf:196` and
  `deployments/applications/services/mlflow.hcl:36` — MLflow version;
  read-only, cited.
- `deployments/infrastructure/services/nats.hcl:69` — NATS image pin;
  read-only, cited.
- `deployments/infrastructure/services/postgres.hcl:52` — PG18 image
  pin; read-only, cited.
- `docs/haproxy_reverse_proxy.md:9-19` — HTTP-only ingress; read-only,
  cited (feeds MinIO redirect thread).
- Findings docs (NEW, the only writes): location to be confirmed (see
  Open Questions Q1). Candidate: `docs/notes/feat/auth-epic/`.

## 8. Tests & validation gates

This spike ships markdown findings docs, not code, so the Python test
constraint (`.claude/rules/python-testing.md`) does not apply: no code is
exercised and there is no unit-test suite. The acceptance target is
doc-completeness plus factual-grounding against the in-repo image pins,
not a live-service assertion: no cluster is probed and there is nothing
deployed by this ticket to assert against (Non-goals forbid live probing).

### Repo gate

- `just pre_commit` (runs `pre-commit run --all-files`, per root
  `justfile` `pre_commit` recipe). The configured hooks
  (`.pre-commit-config.yaml`) are: from `pre-commit-hooks` v5.0.0 —
  check-json, check-ast, check-merge-conflict, check-yaml (`--unsafe`),
  debug-statements, detect-private-key, end-of-file-fixer; and local
  hooks nomad-fmt, terraform-fmt (`terraform fmt -check -recursive`), and
  terraform-validate (`scripts/tf_validate.sh`, which validates the three
  Terraform roots offline). The config `exclude` is `^\.(claude|loop)/`,
  so the ticket file itself is not linted. The findings docs under `docs/`
  are markdown: they are subject to end-of-file-fixer (single trailing
  newline) and detect-private-key, but the terraform-fmt /
  terraform-validate and nomad-fmt hooks are typed to `.tf` / `.hcl` and
  do not touch the docs. This spike writes no `.tf` and no `.hcl`, so
  those hooks stay green by not running against new files.
- **Markdown slop-scan** on every findings doc, per
  `.claude/rules/slop-scan-for-docs.md`: run all three layers before
  declaring done. Layer 0 P0 is the load-bearing one here — no fabricated
  version string, image tag, issue number, config-key name, or URL; every
  backticked identifier and cited `path:line` must resolve. Run
  `Skill(scribe:slop-detector)` on each doc over 100 words, confirm prose
  wraps at 80 chars, American spelling, and the 0-2 em-dash-per-1000-words
  budget.

### Evals (doc)

These are the acceptance target. They are the checks that the spike
actually answered its question, grep-able against the findings docs. No
live cluster calls: research is from upstream docs/issues plus the in-repo
pins only.

1. **One findings doc per service.** A separate findings doc exists for
   each of the four critical-path services — MinIO, MLflow, NATS, and
   PostgreSQL 18 (paths per Open Questions Q1/Q2; operator confirms the
   four-plus-one shape and location before S3.1 writes the first file).
2. **Each fact is pinned to the in-repo image tag.** Each doc records its
   verified version fact against the exact deployed pin resolved in
   section 4, and cites the in-repo anchor so a reader can re-resolve it:
   MinIO `RELEASE.2025-09-07T16-13-09Z`
   (`deployments/infrastructure/services/minio.hcl:66`) plus the
   `aminueza/minio` 3.8.3 provider pin; MLflow `2.20.0`
   (`deployments/applications/services.tf:196`); NATS `2.10-alpine`
   (`deployments/infrastructure/services/nats.hcl:69`); PostgreSQL 18
   (`deployments/infrastructure/services/postgres.hcl:52`). A capability
   that exists only in a version newer than the pin is recorded as a
   NEGATIVE finding for that pin, labeled as such with the first version
   that introduces it. Grep each doc for its pin string.
3. **Each fact carries a resolvable upstream source.** Every verified
   claim names its upstream source (doc section or issue number) and
   states whether the claim holds AT the pinned version. A claim without a
   resolvable source is marked UNVERIFIED, not asserted.
4. **Each doc names its downstream-ticket impact.** Every findings doc has
   an "impact on downstream tickets" section naming which of M1, R1, R2,
   R3, R4 the fact gates. Grep each doc for the downstream ticket IDs it
   affects.
5. **Consolidation exists.** A fifth consolidation doc (per S3.5 / Open
   Question Q2, candidate `impact.md`) maps each verified fact to the
   downstream ticket it gates across M1, R1, R2, R3, R4, so each ticket
   can link the single service file it depends on.

An adversarial review (`.claude/rules/adversarial-reviews.md`) closes the
loop: before reporting done, hand the findings docs to a review sub-agent
to confirm each fact is pinned, sourced, and correctly labeled
verified/negative/unverified.

The eval marker for this ticket (Definition of Done plus the five-column
scenario table) lives at `.loop/evals/S3-spike-oidc-version-claims.md`.

## 9. Risk assessment

- Blast radius: near zero for infra (read-only, no infra change). The
  real risk is a WRONG finding that silently mis-guides a downstream
  ticket (e.g. asserting MinIO multi-IdP works claim-based when the
  pinned release requires per-provider `role_policy`). Mitigation: pin
  to version, cite source, mark unverified claims.
- Reversibility: fully reversible (delete/rewrite a markdown doc).
- Likeliest failure modes: (a) conflating "latest docs" behavior with
  the pinned version behavior; (b) hallucinating a config-key name or
  issue number under the doc gate; (c) resolving the wrong pin (e.g.
  reading MLflow as 3.x when `services.tf:196` pins 2.20.0). Each is
  caught by the version-pinning requirement plus the P0 slop scan.

## 10. Subtickets

Ordered; the four research threads are independent and may run in any
order, but consolidation (S3.5) depends on all four.

1. S3.1 MinIO — verify at `RELEASE.2025-09-07T16-13-09Z`: (a) multiple
   simultaneous named `identity_openid` configs (Vault AND Nomad as
   two providers) and whether policy mapping via the OpenID `policy`
   claim can coexist across two providers or forces `role_policy`
   (RoleArn) per provider; (b) STS `AssumeRoleWithWebIdentity`
   behavior and the policy-claim mapping; (c) OIDC callback/redirect
   paths, HTTP-vs-HTTPS support, and browser-to-host redirect-URI
   matching given HTTP-only ingress (`docs/haproxy_reverse_proxy.md`).
   Note the `aminueza/minio` 3.8.3 provider's support (or lack) for
   declaring these resources.
2. S3.2 MLflow — confirm MLflow `2.20.0` (`services.tf:196`) has no
   native OIDC/SSO (context: issue #10922 was the SSO request); verify
   whether any newer MLflow line adds it, and confirm oauth2-proxy
   front-auth is therefore required. Verify oauth2-proxy bearer-JWT
   (`--skip-jwt-bearer-tokens` / OIDC issuer) config for machine access.
3. S3.3 NATS — verify auth-callout maturity at `nats:2.10-alpine`:
   whether callout can validate an external Vault/Nomad JWT and return
   a signed NATS user JWT, and the 2.10-line specifics (e.g. encrypted
   callout requests / xkey).
4. S3.4 PostgreSQL 18 — verify at `pgvector/pgvector:pg18-trixie`
   whether a usable OAuth validator library exists for Vault/Nomad
   tokens or must be written (PG18 OAUTHBEARER validator hook). This
   gates Path B in S2/R3.
5. S3.5 Consolidate — one impact summary mapping each verified fact to
   the downstream ticket it gates (M1, R1, R2, R3, R4). Depends on
   S3.1-S3.4. Run the doc gate + `just pre_commit` and report.

## 11. Open questions

- Q1 (location of deliverables): Where do the findings docs live?
  Options: `docs/` (flat, alongside `nats.md`), a new
  `docs/architecture/auth/`, or `docs/notes/feat/auth-epic/` (matches
  the existing `docs/notes/feat/bifrost-grafana-metrics/` convention).
  Recommendation: `docs/notes/feat/auth-epic/<service>.md`, one file
  per service, since these are epic working notes, not stable
  reference docs. Operator to confirm before S3.1 writes the first
  file.
- Q2 (one doc vs four): The task says "a findings doc per service"
  (four files). Recommendation: keep four files plus the S3.5
  consolidation summary as a fifth (`impact.md`), so each downstream
  ticket can link the single service file it depends on. Confirm the
  four-plus-one shape is acceptable.
- Q3 (memex WI-JWKS claim): the shared epic context states "memex
  already verifies Nomad WI JWTs against JWKS," but the deployed memex
  job (`deployments/applications/services/memex.hcl:138-141`) shows
  only static `MEMEX_SERVER__AUTH__KEYS` API keys and no JWKS/OIDC
  issuer env. Recommendation: treat the JWKS claim as unverified
  in-repo and, if S3 has spare budget, add a one-line note flagging the
  gap for whichever ticket owns memex auth; otherwise leave it entirely
  to that ticket. This spike does not own memex.
- Q4 (MinIO redirect scheme): given HTTP-only ingress
  (`docs/haproxy_reverse_proxy.md:19`), does MinIO's OIDC
  redirect-URI matching tolerate `http://` callbacks, or does Vault-as-
  IdP force TLS on the MinIO console callback? Recommendation: S3.1
  records the answer as a verified fact and flags it to R-tickets
  rather than resolving the ingress-TLS decision here.
