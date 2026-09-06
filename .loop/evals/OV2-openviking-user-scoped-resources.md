eval: OV2-openviking-user-scoped-resources

**Definition of Done:** jasper and veerle each hold an OpenViking account of
their own, and nothing either uploads is visible to the other — through the API,
through Web Studio, through WebDAV, or through semantic search.

Every row below needs a deployed service. Nothing in this repo runs one
(`scripts/check_openviking_config.py:25` says so in its own docstring), so a
green `just pre_commit` says nothing about rows 1-7 or row 9. Row 8 is the only
one a gate covers.

Rows 2 and 3 exist because they are exactly what killed the first design: a
configured default never reaches Studio (its form ships prefilled) or WebDAV
(its target is a literal in server Python). If the account split is right, both
land in the caller's own tree with no config involved.

| # | Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|---|---|---|---|---|---|---|
| 1 | A person's uploaded resource is invisible to the other through the API. | As jasper: `curl -H "X-API-Key: $JASPER" -X POST $OV_URL/api/v1/resources` adding a file named `jasper-only-<uuid>`. Then as veerle: `GET /api/v1/fs/ls?uri=viking://resources` and `GET /api/v1/fs/ls?uri=viking://`. | Veerle's listing contains no `jasper-only-<uuid>` at any depth. Jasper's own listing does contain it. Both calls return 200 — this is separation, not a 403. | Veerle's listing shows the file, or veerle gets a 500/403 that hides whether separation happened at all. | Human, against the live cluster | 100% |
| 2 | Web Studio's prefilled target lands in the caller's own account. | Log into Studio as jasper, add a resource WITHOUT editing the prefilled `viking://resources/` parent. Log in as veerle, open the same view. | Jasper sees the resource. Veerle's Studio shows an empty resources tree. The prefill is untouched in both sessions. | Veerle sees jasper's resource. This is the exact failure the config-default design shipped with, so this row is the ticket's reason to exist. | Human with rubric, in a browser | 100% |
| 3 | WebDAV's hardcoded `viking://resources` lands in the caller's own account. | Mount `$OV_URL/webdav/resources` with jasper's key, write `dav-<uuid>.txt`. Mount the same URL with veerle's key, list. | Jasper's mount lists the file. Veerle's mount does not. Neither mount errors. | Veerle's mount lists jasper's file, proving the hardcoded literal crosses accounts. | Human, against the live cluster | 100% |
| 4 | GUARDRAIL. Semantic search does not cross accounts, even though both accounts share one Postgres schema. | As jasper, ingest a document containing a distinctive nonsense phrase. Wait for indexing. As veerle, `POST /api/v1/retrieve` querying that exact phrase. | Veerle gets zero hits. Jasper gets the document. | Veerle gets any hit at all, or a snippet of jasper's text in a result. The blobs can be isolated while the vectors are not: `storage.vectordb` points both accounts at one `openviking` schema, and this row is the only thing that checks it. | Human, against the live cluster | 100% |
| 5 | Each person's key carries their own account, and no key's secret changed. | `vault kv get -mount=secret default/openviking-users/jasper` and `.../veerle`. Compare each `api_key`'s third segment to its value before the apply. | `account` reads `jasper` and `veerle` respectively. The first segment of each key decodes to that same account. The THIRD segment is byte-identical to its pre-apply value. | Any third segment changed, which would mean the reshape silently rotated a credential rather than re-homing it. | Deterministic: shell diff of the pre/post key segments | 100% |
| 6 | Hermes still acts as jasper, in jasper's account. | `vault kv get -mount=secret default/hermes/openviking`. Then have Hermes write a memory and, as jasper, list `viking://~/memories`. | The KV entry's `account` reads `jasper`. Jasper's listing shows Hermes's write. | The entry still reads `lab`, in which case Hermes reads and writes successfully into an account nobody else uses and the failure is silent. | Human, against the live cluster | 100% |
| 7 | The provisioner is idempotent: a second apply changes nothing and rotates no key. | Run `just apply` in `deployments/applications` twice. Capture both keys from Vault after each run. | The second apply reports no changes to the three Vault KV entries. Both keys identical across runs. The provisioner's account POSTs return 409 and are treated as success. | The second run reports key churn, or the provisioner fails on 409 rather than accepting it. | Human, against the live cluster | 100% |
| 8 | The repo's own gates stay green and the plan holds no surprises. | `just pre_commit`; `terraform fmt -check` and `scripts/tf_validate.sh` in `deployments/applications`; read `terraform plan`. | All green. The plan lists the three Vault KV entries and the provisioner, and NOTHING touching `nomad_job.openviking`. | Any unexplained resource in the plan, or a changed `nomad_job.openviking` — the jobspec is not in this ticket's code surface. | Deterministic | 100% |
| 9 | The old `lab` account's keys are dead and its content survives, which is the close the operator chose. | Before the apply, save a working `lab` key. After the operator runs the Q1 runbook (POST a throwaway seed to `/accounts/lab/users/<user>/key` for both users, keeping neither key nor seed), use the saved key: `GET /api/v1/fs/ls?uri=viking://resources`. | The saved key is refused with 401. Then, re-minting once more with a seed you DO keep produces a key that reads the old tree intact — proving the content was preserved, not destroyed. | The saved key still reads, meaning the re-mint did not revoke; or the recovery re-mint comes back to an empty tree, meaning content was lost. Option (b) was chosen precisely because it is reversible, so both halves must hold. | Human, against the live cluster | 100% |

Row 9 exists because the plan's second draft claimed the old account became
unreachable and that was wrong: nothing in this change revokes a `lab` key, and
`docs/openviking.md:155` records that `ov config add` writes one to disk in the
clear. So both people plausibly hold a working key to the old shared tree right
now. Until Q1 is settled and executed, this eval passing means new uploads are
isolated and every existing one is still shared — which is half of what was
asked for. Do not read rows 1-8 green as the job being done.

signed-off-by: JasperHG90 2026-09-06T13:20:15Z

Sign-off provenance, stated plainly because this line is agent-settable and
buys auditability rather than proof. JasperHG90 settled every fork in this eval
by hand before leaving: the account-split approach over the config default, Q1
option (b) for closing the old `lab` account, the nine-row count, and
human-against-live-cluster at 100% for the seven rows no gate can reach. They
were then shown this assembled table and approved it. They did not personally
run any row; seven of nine still await them at a terminal or a browser.

plan: 48bf33716dc265d6dbc07023a7283e1525e58c524e74fe578797f6782270b1af
