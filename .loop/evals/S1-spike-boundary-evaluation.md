eval: S1-spike-boundary-evaluation

Definition of Done: `docs/notes/boundary-evaluation.md` exists and answers the
spike — an evidence-backed KEEP/DROP verdict, a two-layer deploy footprint, the
S2 credential-engine prerequisite, and a good-fit/poor-fit split — with no
Zitadel reference and no infrastructure shipped.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The decision doc exists at the agreed path | `test -f docs/notes/boundary-evaluation.md` | Exit code 0 — the file is present at `docs/notes/boundary-evaluation.md` (Q1 path) | deterministic check (`test -f docs/notes/boundary-evaluation.md`) | 100% |
| The reader gets an unambiguous, evidence-backed verdict | Read the verdict section of `docs/notes/boundary-evaluation.md` | Exactly one of KEEP or DROP stated as a verdict line, justified by solo-operator deploy/maintenance cost vs benefit; the verdict does NOT rest solely on "Terraform can express the config" | model + rubric (adversarial review agent) | 4/5 |
| The doc enumerates the footprint across both deploy layers | `grep -Eq 'boundary_controller\|boundary_worker' docs/notes/boundary-evaluation.md && grep -q 'hashicorp/boundary' docs/notes/boundary-evaluation.md` | Exit 0 — bootstrap layer names a `boundary_controller` (or `boundary_worker`) role AND the Terraform layer names the `hashicorp/boundary` provider | deterministic check (`grep -Eq 'boundary_controller\|boundary_worker' … && grep -q 'hashicorp/boundary' …`) | 100% |
| A KEEP path ties its Vault prerequisite to ticket S2 | `grep -q 'S2' docs/notes/boundary-evaluation.md && grep -q 'secrets.tf' docs/notes/boundary-evaluation.md` | Exit 0 — the doc references `S2` alongside the required Vault credential engine(s) and cites `secrets.tf` (KV2 at `secrets.tf:2-7`) as the sole engine that exists today | deterministic check (`grep -q 'S2' … && grep -q 'secrets.tf' …`) | 100% |
| The reader can tell good-fit from poor-fit and the verdict is closed out | Read the fit-analysis and closing sections of `docs/notes/boundary-evaluation.md` | Wire-level/SSH good-fit targets (Postgres, MinIO S3 API, NATS, Phoenix gRPC, Memex API, node SSH) are separated from the web-UI poor-fit set (Grafana, MinIO console, MLflow, Phoenix UI); on KEEP the doc states minimal PoC scope, on DROP it states reopen conditions | model + rubric (adversarial review agent) | 4/5 |
| Guardrail: the dropped Zitadel design is never referenced | `grep -ci zitadel docs/notes/boundary-evaluation.md` | Output `0` — no case-insensitive match for `zitadel` anywhere in the doc | deterministic check (`grep -ci zitadel docs/notes/boundary-evaluation.md`) | 100% |
| Guardrail: no infrastructure ships — the change is doc-only | `git diff --name-only HEAD` (and `git status --porcelain`) | The only added/modified product path is `docs/notes/boundary-evaluation.md`; no new or changed file under `bootstrap/` or `deployments/`, and no `.tf`, `.hcl`, Ansible role, playbook, or inventory file | deterministic check (`git diff --name-only HEAD` shows only `docs/notes/boundary-evaluation.md`) | 100% |
