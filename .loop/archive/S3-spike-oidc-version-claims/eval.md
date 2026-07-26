eval: S3-spike-oidc-version-claims

Definition of Done: a findings doc exists for each critical-path service
(MinIO, MLflow, NATS, PostgreSQL 18) plus a consolidation doc, every version
fact is pinned to the exact in-repo image tag and carries a resolvable upstream
source, each doc names the M1/R1/R2/R3/R4 tickets it gates, and no infra is
touched and no live cluster is probed.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Reader finds one findings doc per critical-path service | `ls docs/notes/feat/auth-epic/` (location per Open Question Q1, operator-confirmed) | A separate findings doc is present for each of MinIO, MLflow, NATS, and PostgreSQL 18 | deterministic check (`ls` the findings dir for the four service files) | 100% |
| Each version fact is pinned to the deployed image tag | grep each service doc for its pin string | MinIO doc contains `RELEASE.2025-09-07T16-13-09Z` (and the `aminueza/minio` 3.8.3 provider pin), MLflow `2.20.0`, NATS `2.10-alpine`, PostgreSQL `pg18`; each cites its in-repo anchor and any capability newer than the pin is labeled NEGATIVE with the first version that introduces it | deterministic check (grep each doc for its pin string) | 100% |
| Each doc names its downstream-ticket impact | `grep -E 'M1|R1|R2|R3|R4' docs/notes/feat/auth-epic/<service>.md` per doc | Every findings doc has an "impact on downstream tickets" section naming which of M1, R1, R2, R3, R4 the fact gates | deterministic check (grep the downstream ticket IDs) | 100% |
| Reader gets a consolidation mapping facts to gating tickets | inspect the fifth consolidation doc (candidate `impact.md`) | The consolidation doc is present and maps each verified fact to the M1/R1/R2/R3/R4 ticket it gates so each ticket can link the single service file it depends on | deterministic check (consolidation file present, grep the ticket IDs) | 100% |
| Every verified fact is correct at the pin, sourced, and its impact is sound | adversarial review agent reads all five docs against the cited upstream docs/issues | Each verified version fact holds AT the pinned version, carries a resolvable upstream source (doc section or issue number) or is marked UNVERIFIED rather than asserted, and its downstream impact on M1/R1/R2/R3/R4 is sound | model + rubric (adversarial review agent) | 4/5 |
| Spike ships docs only, probes nothing, and never names Zitadel | `git diff --stat` for the spike branch and `grep -ri zitadel docs/notes/feat/auth-epic/` | Only markdown docs are added; no `.hcl`, `.tf`, provider config, or `.env` is modified; no live-cluster probe is recorded; no reference to Zitadel appears | deterministic check (`git diff --stat` shows docs only; `grep -ri zitadel` returns nothing) | 100% |
