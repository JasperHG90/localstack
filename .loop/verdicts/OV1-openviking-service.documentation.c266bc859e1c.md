---
verdict: pass-with-required-fixes
tree: 88a65fa345712e188794ea8a69e885bcd3826a1e
---

<!--
SCOPE BINDING OMITTED, DELIBERATELY. This cycle's briefing again gave a tree
fingerprint but no 64-hex scope digest, and named no verdict_binding_inputs.
The floor is not mine to choose and I must never write a digest I computed for
a set I chose, so bound_paths / scope / citations are omitted and this verdict
falls back to the whole-tree binding, which is stricter. Every anchor cited
below carries its verbatim line inline instead. Same condition cycle 1 recorded.

For the record, the artifact reviewed was the working tree against 765a90b:
modified .pre-commit-config.yaml, deployments/applications/secrets.tf,
deployments/applications/services.tf, deployments/infrastructure/oidc.tf,
deployments/infrastructure/secrets.tf, deployments/infrastructure/services.tf,
deployments/infrastructure/services/haproxy.hcl, docs/haproxy_reverse_proxy.md,
docs/workload-identity.md, scripts/check_oauth2_proxy_guard.py; added
deployments/applications/services/openviking.hcl,
deployments/applications/services/openviking/Dockerfile.openviking,
deployments/applications/services/openviking/README.md,
deployments/applications/services/openviking/justfile,
deployments/infrastructure/services/oauth2-proxy-openviking.hcl,
docs/openviking.md, scripts/check_openviking_config.py.
-->

# Documentation pass, OV1-openviking-service, cycle 2

All three cycle-1 required fixes are real, and each is accurate against the
code rather than merely present. The advisories landed too. The adversarial
rewrites stranded less prose than expected: the two the implementer already
caught were the substantive ones. What is left is one Layer 2 wrap regression
in the doc the DOC-1 fix edited, and three advisories.

---

## Required

### DOC-15. The DOC-1 fix inserted two sentences without re-wrapping the paragraph.

```
docs/haproxy_reverse_proxy.md:30 = HAProxy no longer gates it. `dash`, `registry-ui` and `openviking` each sit behind their own
docs/haproxy_reverse_proxy.md:34 = OpenViking validates that same token itself rather than trusting the proxy. `grafana` reaches that same Vault
```

`:30` is 92 characters and `:34` is 109. At HEAD the file carried exactly one
over-80 line, the 91-character predecessor of `:30`. This edit leaves two, and
`:34` is now the longest line in the file: the new sentence ends at column 75
and `` `grafana` reaches that same Vault `` is tacked on behind it rather than
starting the next line.

`.claude/rules/slop-scan-for-docs.md` Layer 2 check 1 mandates the 80-character
wrap on every markdown file a change touches, and this change touches this one.
The bar is met elsewhere in the same diff: `docs/openviking.md` holds zero
over-80 lines across 141 lines. `docs/workload-identity.md`'s four added lines
also wrap cleanly.

The content is correct, so this is narrow: re-wrap `:28-37`.

---

## Advisory

### DOC-16. `storage.tf`'s inline twin of the sentence DOC-2 fixed is now false.

```
deployments/applications/storage.tf:35 =     # creation (datalake, openviking, mlflow-artifacts have none).
deployments/applications/secrets.tf:254 = resource "vault_kv_secret_v2" "openviking_minio_credentials" {
```

`:33-35` reads "No Vault KV entry yet -- the convention here is that creds land
in Vault when a job consumes them (memex, loki, tempo), not at bucket creation
(datalake, openviking, mlflow-artifacts have none)." This change writes exactly
that per-job entry, `secret/default/openviking/minio`, so the parenthetical is
false in the sense the comment means.

I checked the obvious escape and it does not apply: the generic
`vault_kv_secret_v2.minio_credentials` `for_each` at `secrets.tf:273-281` writes
to `default/minio/<user>`, a different prefix outside the job's own read path,
and is not what this comment tracks.

This is the adversarial pass's own L1, still unretired: `storage.tf` is not in
this diff. I report it because it is the inline twin of the
`docs/workload-identity.md` sentence DOC-2 just fixed, and the two now disagree
about the same fact. Severity on that finding belongs to the pass that raised
it, so I leave it advisory rather than escalating.

### DOC-17. Two comments say the volume holds an OAuth SQLite db; the doc says that subsystem is off.

```
deployments/infrastructure/services.tf:217 = ### OpenViking's workspace, its OAuth SQLite db and RAGFS's local scratch.
deployments/applications/services/openviking.hcl:32 =     ### Holds ov.conf's workspace, the OAuth SQLite db and RAGFS's local
docs/openviking.md:36 = OpenViking's own OAuth 2.1 implementation is **off**. It is an authorization
```

The adversarial M2 fix deleted the `openviking[auth]` install that supplies that
subsystem, and `auth_mode` is `"oidc"`. Nothing in this tree or the ticket
evidences the file. Two surfaces in one change now disagree about whether an
OAuth subsystem is live.

Advisory, not required: I cannot read upstream from here, so I cannot prove
OpenViking does not create that file regardless of `auth_mode`. Resolve by
citing the upstream path that creates it, or cut the clause.

I checked the neighboring word and it is clean, so do not "fix" it: `RAGFS` is
correct upstream naming, not a typo for the `agfs` config key. The ticket at
line 806 cites `crates/ragfs/src/plugins/s3fs/client.rs` and the provider string
`"ragfs-s3fs"`.

### DOC-18. One stray period in the DOC-3 fix.

```
docs/openviking.md:107 = # rerank reaches embark, in the bare-string shape OpenViking sends.
```

The four sibling comments in the same `console` fence (`:94`, `:97`, `:100`,
`:104`) carry no terminal period. One character. The two explanatory lines below
it at `:108-109` are full sentences and do want theirs.

---

## Re-attack of the cycle-1 ledger

Every finding the diff touches was re-opened at its anchor and re-checked
against this tree, not confirmed from cycle 1's reasoning.

### The three required fixes: all real, all accurate

**DOC-1 — closed-fixed.** The row is there:

```
docs/haproxy_reverse_proxy.md:26 = | `openviking.lab.orangecluster.nl` | radxa-dragon-q6a (192.168.2.50) | 4182 |
```

It matches `haproxy.hcl`'s new `acl is_openviking`, `use_backend openviking`
and `server openviking1 192.168.2.50:4182 check`. The prose now names three
proxies and three ports, and its new clause is the one claim worth checking
rather than assuming:

```
docs/haproxy_reverse_proxy.md:32 = SSO with flat any-authenticated-user access. `openviking`'s proxy differs
deployments/infrastructure/services/oauth2-proxy-openviking.hcl:75 =         OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER="true"
```

True, and true as a difference: neither sibling jobspec sets it. A repo-wide
grep for `AUTHORIZATION_HEADER` returns five hits, all accounted for. Wrapping
regressed, tracked above as DOC-15.

**DOC-2 — closed-fixed.** The added clause is accurate on every limb:

```
docs/workload-identity.md:272 = keys for buckets no job consumes. `openviking` is no longer one of those: its
docs/workload-identity.md:275 = drops the session token STS credentials require. See `docs/openviking.md`.
```

`applications/storage.tf:63-65` mints the key with `generate_access_key = true`,
`applications/secrets.tf:254-261` writes it to Vault, and `openviking.hcl:110-112`
renders it into `ov.conf`. The stated reason matches `docs/openviking.md:53-57`
and the pointer resolves. Style matches the surrounding paragraph, which already
tracks exceptions inline (memex), and all four added lines wrap under 80.

**DOC-3 — closed-fixed, and this one earned the most checking.** The claim was
downgraded to embeddings only and the rerank half given its own command:

```
docs/openviking.md:107 = # rerank reaches embark, in the bare-string shape OpenViking sends.
docs/openviking.md:108 = # bifrost_smoke.py does NOT cover this: its rerank calls assert a 401 and
docs/openviking.md:110 = $ python3 scripts/embark_rerank.py
```

`scripts/embark_rerank.py` exists, is tracked, and does what the doc says:

```
scripts/embark_rerank.py:112 =     query: str, documents: list[str], vk: str, top_n: int | None = None
```

Bare strings, posted to `http://192.168.2.50:8080/v1/rerank` against
`embark/reranker` (`:41-42`). The disclaimer about the smoke script is also
true, not a hedge:

```
scripts/bifrost_smoke.py:17 = Assertion 1 sends documents in the OBJECT form on purpose. Bifrost parses the
scripts/bifrost_smoke.py:120 =         if status != 401:
```

Both commands as printed run with no arguments: `bifrost_smoke.py:202` gives
`--base-url` a default. The runbook is now a set of steps an operator can
actually execute.

### The advisories: all five taken

- **DOC-4 — closed-fixed.** `docs/openviking.md:19` carries
  `` `deployments/applications/services/openviking/README.md` ``, which resolves
  from the repo root.
- **DOC-5 — closed-fixed.** The doc enumerates six and states no count;
  `scripts/check_openviking_config.py:6` reads "six settings each fail in a way
  a healthy-looking service would hide", and `failures()` makes exactly six
  assertions in the doc's order. I ran the checker and its `--self-test`: both
  exit 0.
- **DOC-6 — closed-fixed.** `README.md:7` names `` `ov-postgres` `` and
  `` `psycopg[binary,pool]` ``, which is now the whole of the Dockerfile: the
  `openviking[auth]` `RUN` is gone and a repo-wide grep for it returns nothing.
  The 115-character table row is fine; `embark/README.md` runs to 153.
- **DOC-7 — closed-fixed.** `docs/openviking.md:98` is
  `$ open https://openviking.lab.orangecluster.nl/`.
- **DOC-8 — closed-fixed.** Zero semicolon splices in the file this cycle.

### The five closed findings: absence claims

- DOC-9 — no change in scope, still holds. The diff adds
  `vault_identity_oidc_client.openviking` at `oidc.tf:106` and does not touch
  `docs/vault-human-auth.md`. Those counts were already unmaintained before this
  ticket; not a fix this ticket owes.
- DOC-10 — no change in scope, still holds. I re-opened
  `docs/registry-ui.md:28-30` this cycle rather than trusting cycle 1: the
  antecedent at `:28` is "Neither jobspec", meaning dash's and registry-ui's, and
  the guard does still run over both. Widening it to three makes no sentence
  there false. `:20`'s "The two share the OIDC client and the cookie secret"
  also survives, because openviking's proxy gets its own client
  (`infrastructure/secrets.tf:294-296`) and only shares the cookie secret.
- DOC-11 — no change in scope, still holds. I re-opened `README.md:62`: it is a
  parenthetical category list that already omits several hooks. Two more do not
  make it false.
- DOC-12 — no change in scope, still holds. `openviking.lab.orangecluster.nl` is
  a flat label under the wildcard, and `haproxy_reverse_proxy.md:110-117` already
  says a flat label needs no DNS or certificate change.
- DOC-13 — no change in scope, still holds. No tile was scoped; that fix would be
  `tiles.json`, not docs.

---

## Slop scan, re-run in full on `docs/openviking.md`

The file changed substantially, so all three layers were re-run rather than
carried over. 951 words, 141 lines.

**Layer 0.** Zero identity leaks. Zero `TODO`/`FIXME`/`XXX`/`HACK`. Every
backticked path, identifier and command resolves in this tree: `embark_rerank.py`,
`bifrost_smoke.py`, `check_openviking_config.py`, the service README,
`data "vault_identity_oidc_client_creds" "openviking"` (`applications/services.tf:45`),
`OAUTH2_PROXY_PASS_AUTHORIZATION_HEADER` (`oauth2-proxy-openviking.hcl:75`), the
asserted absence of a `minio_iam_policy` named `openviking` (grep confirms none),
`U7-upgrade-bifrost-2x` (commit 765a90b), `/ready` (`openviking.hcl:60`),
`embark/embedding` and `embark/reranker` (`:135`, `:145`), dimension 768 (`:136`),
port 1933 (`:28`), 4182 (`oauth2-proxy-openviking.hcl:49`). Backticks balance on
every line. The upstream OpenViking and Bifrost claims (`S3Config.validate_config`,
`Credentials::new`, the 1.6.11 boundary) are unverifiable offline and were cleared
in cycle 1 against the ticket's recorded probes.

**Layer 1.** Thesis at `:3-5`. Every heading earns its section, no restated
headings, no throat-clears. 6/6.

**Layer 2.** 0 em dashes. 0 ` -- ` in prose. 0 smart quotes. 0 semicolon splices.
0 tier-1 slop. 0 self-narration. 0 hedging seesaw. 0 "not just"/"not only".
0 participial tails. 0 British spellings. 0 lines over 80. 0 trailing whitespace.
Tier 5: 0 spatial copula, 0 negative or contrastive parallelism, 0 throat-clearing
openers, 0 three-fragment bursts, 0 significance cluster, 0 emphasis crutch,
0 performative honesty, 0 prior-art marker, 0 loop/cascade vocabulary, 0 prose
arrows or `+` conjunctions.

**Layer 3.** No quality claims to evidence. The doc's assertions are mechanical
and each is measured or cited.

The only nit is DOC-18 above.

---

## What I confirmed clean (do not re-derive next cycle)

- The `SET_AUTHORIZATION_HEADER` removal is complete and consistent. Five
  repo-wide hits: `docs/openviking.md:25` and
  `oauth2-proxy-openviking.hcl:8`/`:75` set and explain `PASS`;
  `docs/openviking.md:32` and `oauth2-proxy-openviking.hcl:16` warn against
  `SET`. No surface anywhere still recommends it, and no jobspec sets it.
- The `root_api_key` deletion strands nothing. One repo-wide match for "root
  key", `docs/openviking.md:127`, and it describes what `auth_mode: "trusted"`
  would need in a future ticket rather than claiming one is provisioned.
- The `openviking[auth]` deletion strands nothing. Zero repo-wide matches.
- The `ov.conf` move strands nothing. `local/ov.conf` appears nowhere;
  `openviking.hcl:79` and `:166` agree on `secrets/ov.conf`, and no doc names
  the path at all.
- Every numeric claim in the new prose. `oauth2-proxy-openviking.hcl:7` "two
  siblings"; `:24` "Seven settings", and the list that follows holds seven;
  `applications/secrets.tf:235` "All three", and three resources follow;
  `docs/openviking.md:68` "those two fields", meaning `access_key` and
  `secret_key`.
- `deployments/applications/services/openviking/README.md`. Every recipe it
  prints exists in the justfile beside it (`show`, `build`, `verify`, `push`,
  `release`), `just build` does refuse a `:latest` base (`justfile:48-51`), and
  `bootstrap/playbooks/configure_podman.yml` resolves.
- No other doc in the repo mentions OpenViking, so nothing else could have gone
  stale. There is no docs index to add the page to; `README.md:30` is a
  category-level pointer.
- `docs/gcs-backups.md`, `docs/dns.md`, `docs/tls-certificates.md`,
  `docs/dash-landing-page.md`: none enumerates jobs, buckets, host volumes or
  virtual keys in a way this change falsifies.

---

## Verdict

**pass-with-required-fixes.** The docs describe the cluster this change builds,
and the three fixes cycle 1 asked for are real rather than reworded. One
required fix remains and it is cosmetic in content but mandated by the repo's
own doc gate: re-wrap `docs/haproxy_reverse_proxy.md:28-37` to 80 columns.
DOC-16, DOC-17 and DOC-18 are advisory. DOC-16 in particular is the adversarial
pass's unretired L1 and should not be lost.
