---
verdict: pass-with-required-fixes
tree: 2ae69df79a7a420cf021b7296471fc4e86c50a42
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY. The briefing gave a tree fingerprint but
no 64-hex scope digest and named no verdict_binding_inputs. The floor is not
mine to choose and I must never write a digest I computed for a set I chose,
so the three lines (bound_paths / scope / citations) are omitted and this
verdict falls back to the whole-tree binding, which is stricter. Every anchor
cited below carries its verbatim line inline instead. Same condition the L5
documentation pass recorded.
-->

# Documentation pass, OV1-openviking-service, cycle 1

The change ships two new docs and they are good. It leaves two existing docs
describing a cluster that no longer exists, and its own new doc overstates one
verification step. All three fixes are small and located.

No prior findings ledger existed at
`.loop/scratch/OV1-openviking-service.documentation/findings.json`, so there
was nothing to re-attack. This cycle's ledger is written there now.

## Required fixes

### DOC-1 (major) — the edge route table omits a live route

`deployments/infrastructure/services/haproxy.hcl:110` =
`    acl is_openviking hdr(host) -i openviking.lab.orangecluster.nl` and
`:189` = `    server openviking1 192.168.2.50:4182 check` add a routed
hostname. `docs/haproxy_reverse_proxy.md` is the doc that enumerates them and
it was not touched.

- `docs/haproxy_reverse_proxy.md:10` = "Every route is `https://<name>`. Plain
  HTTP on port 80 answers only with a 301" — the table is presented as the
  complete set.
- `docs/haproxy_reverse_proxy.md:25` = "| `registry-ui.lab.orangecluster.nl` |
  radxa-dragon-q6a (192.168.2.50) | 4181 |" is the last row. There is no
  `openviking` row.
- `docs/haproxy_reverse_proxy.md:29` = "HAProxy no longer gates it. `dash` and
  `registry-ui` each sit behind their own oauth2-proxy" and `:30` =
  "instance, on 4180 and 4181, both gated by Vault". A third instance now runs
  on 4182.

This is not a bar I invented. Commit 7e93194 (registry-ui, the immediately
prior comparable ticket) added its row and rewrote that same sentence in the
same commit, and those were two of the only three doc edits it made. This
change also updated the equivalent claim in code:
`deployments/infrastructure/services.tf:410` = "    # Three proxies, three
ports: 4180 gates dash, 4181 registry-ui, 4182". The doc is the one surface
left behind.

Fix: one table row (`| openviking.lab.orangecluster.nl | radxa-dragon-q6a
(192.168.2.50) | 4182 |`) and the sentence at :29-30.

### DOC-2 (medium) — the keyless-MinIO doc still says no service job holds a static key

`docs/workload-identity.md` is where the cluster records who has and has not
moved off static MinIO keys:

- `:269` = "and each keeps its key provisioned as a rollback path. memex is
  the only one"
- `:270` = "of those four still using one. Other holders exist outside this
  set: the"
- `:271` = "`backup-minio` job runs on the root credential, and `storage.tf`
  still mints"
- `:272` = "keys for buckets no job consumes."

The `openviking` key was exactly one of those unconsumed keys. The R13
documentation pass verified that clause and named it:
`.loop/verdicts/R13-rollout-loki-registry-keyless-minio.documentation.md` =
"`storage.tf` mints them for `ducklake_reader`/`writer`,
`models_reader`/`writer`, `mlflow` and `openviking`, and no jobspec under
`deployments/*/services/` names any of those buckets."

A jobspec now names it. `deployments/applications/services/openviking.hcl:111-112`
renders `access_key` and `secret_key` from
`vault_kv_secret_v2.openviking_minio_credentials`, permanently and on purpose.
A reader who starts at the keyless doc now concludes that outside
`backup-minio` no service job runs on a static MinIO key, and that is wrong.

I checked whether `docs/openviking.md:44-65` carrying the fork is enough under
this repo's conventions, and it is not, for two reasons the repo itself
supplies. That section of `workload-identity.md` already tracks its exception
inline rather than delegating it ("memex is the only one of those four still
using one"), and the R13 reviewer treated the sentence as load-bearing enough
to verify clause by clause. The service doc is where you land if you came
asking about OpenViking; the keyless doc is where you land if you came asking
who is not keyless.

Fix: one clause. The existing sentence has the right shape for it.

### DOC-3 (medium) — the runbook credits the smoke test with a check it does not make

`docs/openviking.md:100` = "# embeddings and rerank actually reach embark" and
`:101` = "$ python3 scripts/bifrost_smoke.py".

The script makes five assertions and only one of them concerns embark:
`scripts/bifrost_smoke.py:15` = "    5. embeddings reach embark", registered at
`:231` = "        (\"embeddings reach embark\",
partial(assert_embeddings_reach_embark, base, vk)),". Its rerank traffic lives
in assertion 1, which expects a refusal: `:122` = "                f\"inference
auth: expected 401 for {label}, got {status}. \"". And it sends the wrong
shape on purpose: `:17` = "Assertion 1 sends documents in the OBJECT form on
purpose. Bifrost parses the" — the object form, not the bare-string form that
is the whole reason this ticket depended on U7.

So the one command in the runbook that a reader would use to prove rerank
works proves nothing about rerank. Given that `docs/openviking.md:67-77` makes
rerank-through-Bifrost the ticket's second fork, a green run read as
confirmation is the exact wrong conclusion.

Fix: either narrow the comment to "embeddings actually reach embark", or add a
rerank probe with bare-string documents beside it. The doc's own honesty about
limits elsewhere (`:86` = "It does **not** measure anything about a running
service.") is the standard to match.

## Advisory (not required)

- `docs/openviking.md:18` = "The image is derived.
  `services/openviking/README.md` covers building it, and" — that path does not
  resolve from the repo root, and there are two `services/` directories. The
  repo uses both forms (`docs/observability-python.md:72` short,
  `docs/registry-ui.md:22` full), so this is a clarity nit, not a
  hallucination.
- `docs/openviking.md:94` = "$ open
  https://openviking.lab.orangecluster.nl/studio". Nothing in this tree or in
  the ticket evidences `/studio`; it appears only in comments this change
  wrote. Unverifiable offline and self-correcting at deploy time. Confirm on
  first deploy.
- `docs/openviking.md:82` = "values that fail silently: the embedding
  dimension, the `custom_params` key" lists five checks, matching the script's
  own docstring. The script makes six:
  `scripts/check_openviking_config.py:85` = "    backend =
  _vectordb_backend(text)" asserts `storage.vectordb.backend` too.
- `deployments/applications/services/openviking/README.md:7` = "|
  `Dockerfile.openviking` | The derived image: upstream OpenViking plus
  `ov-postgres` and `psycopg`. |" — the Dockerfile installs a third layer,
  `Dockerfile.openviking:42` = "    \"openviking[auth]==0.4.17.1\"". That table
  row is the only place image contents are enumerated.
- `docs/openviking.md:38` = "client is created in the infrastructure root; the
  applications root reads it" is a semicolon splice.
  `.claude/rules/slop-scan-for-docs.md` marks these low confidence and says
  surface, do not auto-rewrite. One instance in 878 words.
- `docs/vault-human-auth.md:42` lists the consumer clients as "(nomad, memex,
  oauth2-proxy, grafana)" and is now one short, and `:291` /
  `docs/cluster-roles.md:172` still say "Four of the six known consumers".
  Recorded but NOT required: registry-ui added a proxy and touched neither, so
  the repo does not maintain these counts. Fixing them is a separate cleanup.

## Checked and clear

- **`docs/openviking.md` under `.claude/rules/slop-scan-for-docs.md`.** Layer 0:
  every backticked identifier and command resolves, verified against this tree
  rather than assumed. `scripts/bifrost_smoke.py` and
  `scripts/check_openviking_config.py` exist; I ran the latter and its
  self-test (both exit 0), so `:81`'s claim that it runs in pre-commit and
  asserts those values is true. `data "vault_identity_oidc_client_creds"
  "openviking"` is at `deployments/applications/services.tf:45`.
  `OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER` is at
  `oauth2-proxy-openviking.hcl:67`. Dimension 768, `auth_mode: "oidc"`,
  `audience` equal to `client_id`, the `openviking` schema, the `openviking`
  bucket, `embark/embedding` and `embark/reranker`, the absent `vlm` block, and
  the absence of a `minio_iam_policy` named `openviking` all match
  `openviking.hcl`. The `ov_collections` / `ov_indexes` / `dbg_fts*` claims are
  the ticket's measured premises (Q4). Only DOC-4 and DOC-7 fall short, both
  advisory. Layer 1: thesis at `:3-5`, every sentence carries or bounds it, no
  restated headings, no throat-clears — 6/6. Layer 2: 0 em dashes, 0 ` -- `,
  0 curly quotes, 0 British spellings, 0 lines over 80 characters, 0 tier-1
  slop, 0 self-narration, 0 hedging seesaw, 0 "not just"/"not only", 0
  participial tails, 0 spatial copula, 0 significance cluster, 0 emphasis
  crutch, 0 performative honesty, 0 prior-art marker; one semicolon (advisory
  above). The heading `:44` = "### MinIO uses a static key, not workload
  identity" is bare-trailing contrastive negation, and I judged it a keep: the
  contrast is the content, and it does not survive removal. Layer 3: no
  "production-ready", "fast", "robust" or "scalable" claim to evidence.
- **`docs/dns.md`, `docs/tls-certificates.md`.** Neither enumerates services;
  both document wildcard behavior.
  `docs/haproxy_reverse_proxy.md:107-114` already says a new flat label needs
  no DNS record and no certificate change, and `openviking` is flat. Correct as
  they stand.
- **`README.md:62`.** A category-level gate summary that already omits
  `oauth2-proxy-guard`, `terraform-validate` and three pytest hooks.
  registry-ui added 43 lines of hooks without touching it. Two more hooks do
  not make it wrong.
- **`README.md:14`, `ROADMAP.md`.** The Applications bullet is illustrative
  (it omits embark, dash, registry-ui and bifrost already); ROADMAP is a dated
  snapshot ("State, end of 2026-08-01"). Neither is maintained per service.
- **`docs/registry-ui.md:28-30`** = "Neither jobspec sets a skip-auth key, and
  that absence is the gate. `scripts/check_oauth2_proxy_guard.py` runs as a
  pre-commit hook over both files to keep it that way." The antecedent is the
  two jobspecs named in that section, the guard does still run over both, and
  the sentence claims no exclusivity. Not stale. Guard and self-test both exit
  0 with the third jobspec added.
- **`docs/cluster-roles.md`.** Names no consumers; its only affected line is
  the same soft count listed under advisory.
- **`docs/credential-rotation.md`.** Covers bootstrap secrets (tailscale,
  github), not per-service Vault KV. Untouched by this change's surface.
- **`docs/dash-landing-page.md:4-7`.** Its parenthetical already omits
  registry-ui, which does have a tile, so it is a snapshot the repo does not
  maintain. The gap would be config (`tiles.json`), not docs, and the ticket
  scoped no tile.
- **`deployments/applications/services/openviking/README.md` against
  `services/embark/README.md`.** Same shape, same bar: file table, the
  operator-step warning, the `just` recipes, the no-drift note, the
  ghcr.io pull note. Every recipe it names exists in the justfile beside it
  (`show`, `build`, `verify`, `push`, `release`), and its two non-obvious
  claims check out: `openviking/justfile:48-51` does refuse a `:latest` base,
  and `embark/justfile:29` does derive its base by stripping `-jetson`. Only
  DOC-6 falls short.
- **Comments and prose under `.claude/rules/minimal-comments.md` and
  `plain-language.md`.** The headers on `openviking.hcl`,
  `oauth2-proxy-openviking.hcl` and the new script's docstring record what the
  source cannot say: why there is no `minio_iam_policy`, why the check is
  `/ready` rather than `/health`, why `custom_params` is fenced, which seven
  settings pass every gate while being wrong. No narration, no restated
  identifiers, no bare TODO, no changelog entries. Active voice throughout.

## Ledger and stamp

- `.loop/scratch/OV1-openviking-service.documentation/findings.json` — 14
  entries, DOC-1 through DOC-14, three `open-required`, five
  `open-advisory`, six closed.
- `.loop/scratch/OV1-openviking-service.documentation/trust-stamp.json` — the
  two guard runs, keyed on this cycle's tree fingerprint. Neither qualifies for
  a stamp on its own terms (sub-second, no state mutated); recorded so a later
  cycle sees they were run.
