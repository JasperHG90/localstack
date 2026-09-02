---
epic = "rollout"
depends_on = ["R9-rollout-tempo-keyless-minio"]
priority = 8
summary = "Move memex off its static MinIO access key onto Workload Identity. Unlike the others this needs application changes in the memex repo, not just jobspec config, so it is the slowest of the four despite being the one we own."
stub = true
---

# Ticket: R12-rollout-memex-keyless-minio

## Triggered by

M1 landed keyless MinIO access; R9 makes tempo the first real consumer.
memex holds a static MinIO key like the rest
(`deployments/applications/services/memex.hcl:124-127`, rendered into
`MEMEX_SERVER__FILE_STORE__ACCESS_KEY_ID` and
`__SECRET_ACCESS_KEY`).

## Vision & rough premises

Same end state as R9: a named `identity` block for the `minio` audience, a
`minio_iam_policy` named `memex`, no static key, Vault entry kept as
rollback.

The distinguishing fact is where the work lands.

- **VERIFIED** — memex takes its S3 credentials as two explicit settings in
  its own configuration schema (`MEMEX_SERVER__FILE_STORE__ACCESS_KEY_ID` /
  `__SECRET_ACCESS_KEY`), not through an ambient credential chain. There is
  no environment variable this repo can set to make it exchange a JWT.
- **VERIFIED** — the image is ours:
  `ghcr.io/jasperhg90/memex-jetson:${memex_version}`
  (`memex.hcl:38`). So the change is available to us, unlike loki's.
- **UNVERIFIED** — memex's file store would need to learn either a
  web-identity credential provider or, if it uses boto3, to accept an
  `AssumeRoleWithWebIdentity` profile. That work lives in the MEMEX REPO,
  not this one, so this ticket coordinates two repos and cannot be a
  single-repo loop iteration as written.
- **UNVERIFIED** — whether memex's S3 layer refreshes credentials at all.
  A one-hour STS credential is useless to a process that reads its config
  once at startup and holds the client forever. This may be the real work,
  larger than the exchange itself.

## Non-goals

- Doing the memex-side code change under this ticket. That belongs in the
  memex repo and should be its own work item there.
- Removing the static key before the new path is proven.
- Touching tempo, loki or registry.

## Open questions

- Q1. Does this ticket split? Recommendation: yes. One item in the memex
  repo to add web-identity support and credential refresh, and a thin one
  here to flip the jobspec once a memex version shipping it exists. Wire
  the ordering through `depends_on` and a `memex_version` bump.
- Q2. Is it worth it? memex is the only one of the four whose fix requires
  writing code, and it is also the one whose static key we rotate most
  easily. Recommendation: do it last, after tempo, loki and registry have
  shown whether the keyless path is worth the friction in practice.
- Q3. Does memex's client refresh expiring credentials? Recommendation:
  answer this before planning; if it does not, the ticket is a refresh-loop
  feature wearing a credentials hat, and should be sized as one.
