---
verdict: pass
tree: 4312c61eb2458e521ea19f417b950eadbf5f6501
---

# OV1-openviking-service — adversarial, cycle 3 (review cap)

**No scope-binding lines.** My briefing carried a tree fingerprint but no
`scope:` digest, no bound path set and no `verdict_binding_inputs`. Writing a
digest I computed myself would bind a set nobody asked me to review, so the
three lines are omitted and this verdict falls back to the whole-tree binding,
which is stricter. Same as cycles 1 and 2.

## Deterministic floor

`loopctl verify-eval-substance OV1-openviking-service` → `valid`, exit 0, no
advisories. `loopctl verify --expect-tree 4312c61e…` → `ok`, exit 0, taken from
the briefing. Proceeded to the semantic pass.

## Gate

Re-run on THIS tree, not trusted from the cycle-2 stamp (its fingerprint
`88a65fa3…` differs, so the brief requires the re-run): `just pre_commit`
exit 0. The two openviking hooks again report `(no files to check) Skipped`
under `--all-files`, because `openviking.hcl` and `check_openviking_config.py`
are untracked and `pre-commit run --all-files` walks `git ls-files`. Forced
them plus ruff, ruff-format, mypy (strict), nomad-fmt, terraform-fmt,
terraform-validate, end-of-file-fixer, detect-private-key and the
oauth2-proxy guard over all new and changed paths with
`pre-commit run --files …`: every one Passed, exit 0. Stamp rewritten at
`.loop/scratch/OV1-openviking-service.adversarial/trust-stamp.json`.

## Verdict

**Pass.** Nothing blocking remains. All five reported fixes are real; one is
half-done and the half that is missing is a comment. The two cycle-1 blockers
and the cycle-2 high finding are closed on evidence I gathered myself, not from
the hand-off.

Three advisories follow. None of them should hold the commit, and I am saying
that deliberately: at the review cap a `pass-with-required-fixes` on a comment
would cost the ticket a block for a defect no gate, no apply and no runtime can
observe. They should ride along in the next touch of these files.

---

## Fixes verified

### A13 — `--no-deps` (was the cycle-2 required fix). Closed.

`deployments/applications/services/openviking/Dockerfile.openviking:39` =
`RUN /usr/local/bin/python3.13 -m pip install --no-deps --upgrade \`

The flag is there, and it omits nothing OpenViking needs. I checked the import
set against what the base image actually ships rather than taking my own
cycle-2 note for it:

- The built wheel's `METADATA` declares exactly three runtime requirements:
  `openviking>=0.4.16`, `psycopg[binary,pool]>=3.1`, `pydantic>=2`. Nothing
  else exists for `--no-deps` to drop.
- `openviking` and `pydantic` (2.12.5) ship in the base image — `pydantic` is a
  direct requirement in OpenViking v0.4.17.1's `uv.lock`.
- `psycopg` and `psycopg_pool` come from RUN #2. It carries no `--no-deps`, so
  the `pool` extra resolves: psycopg 3.2.3's metadata lists
  `psycopg-pool; extra == "pool"`.
- `ov_postgres`'s only third-party imports are those four; everything else in
  its seven modules is stdlib or relative.

I also ran the real install into scratch rather than reasoning about it:
`uv pip install --no-deps --target …` exits 0, builds from commit `9466e7ee`,
and installs exactly one top-level package, `ov_postgres`. Build isolation
still resolves `hatchling`/`hatch-vcs`, so `--no-deps` does not break the
build the way it would if it applied to build requirements.

The cited precedent is verbatim correct:
`deployments/applications/services/embark/Dockerfile.embark:32` =
`# --no-deps: every transitive dependency is already in the venv from the base`

The `:22-23` "Same shape as services/embark/Dockerfile.embark" sentence is now
true as written: it claims sameness about `--target`, and embark uses
`--target` too.

### A8 — the storage.tf comment. Closed, and the scope call is: acceptable.

`deployments/applications/storage.tf:35` =
`    # creation (datalake and mlflow-artifacts have none).`

You asked me to judge this rather than assume it. **It is not a violation.**
Section 7 says the file is untouched unless Q1 keeps the workload-identity
path, but `.claude/rules/minimal-comments.md` carves out exactly this case:
"Comments already in the file fall under CLAUDE.md section 3: leave them be
unless your change makes them wrong." Your `default/openviking/minio` write is
what made it wrong, so fixing it is the rule operating, not being bent. The
edit is one comment line inside a `locals` map — no resource, no heredoc, no
`templatefile` body — so it is state-free by the terraform-file-layout rule's
own test, and `terraform fmt -check` and `terraform validate` both pass.

I checked the fix does not overshoot. `openviking` belongs off that list and
`datalake`/`mlflow-artifacts` belong on it: the generic
`vault_kv_secret_v2.minio_credentials` `for_each` at `secrets.tf:273` writes
`default/minio/<user>` for every key, which is the operator path, while the
list is about the per-consumer copies. The `openviking` bucket and its access
key at `storage.tf:63-68` are untouched from HEAD, and there is still no
`minio_iam_policy` named `openviking`, so Q1's guardrail row holds.

### A14 — the operator verification commands. Closed, both instances.

`docs/openviking.md:97` = `$ ssh radxa@192.168.2.50 curl -s http://127.0.0.1:1933/ready`

`docs/openviking.md:105` = `$ ssh radxa@192.168.2.50 curl -s -o /dev/null -w '%{http_code}' \`

You found the second instance yourself and it was a real one. **No third
command in that fence has the flaw.** The fence holds five: those two, a
browser `open` through the edge at `:100` (which is the check, not a victim of
the proxy), and two local scripts at `:110` and `:115` — `scripts/bifrost_smoke.py`
and `scripts/embark_rerank.py` both exist.

I confirmed the premise from both ends instead of trusting the reasoning.
`oauth2-proxy-openviking.hcl` carries no `SKIP_AUTH_*` key, so nothing is
exempt at the edge; and OpenViking's `/ready` needs no auth — its handler
carries no `require_role` dependency and documents itself as
"No authentication required (designed for K8s probes)". So the loopback form
returns the readiness JSON the comment promises, and the Consul check at
`openviking.hcl:56-64` is sound for the same reason.

### DOC-15, DOC-18. Closed.

`docs/haproxy_reverse_proxy.md` goes from 1 over-80 line at HEAD to 0. The
rewrapped paragraph also carries the new fact rather than only the new width:
`openviking`'s proxy forwards the ID token, unlike its two siblings.

The command fence's convention is "no terminal period on a lead comment", and
every comment in it obeys. The period at `:112` is mid-comment, separating two
sentences, which is required there.

### DOC-17. **Half done.** See A15 below.

---

## Advisory — not blocking

### A15 (low). The DOC-17 fix landed on one of the two anchors it named.

`deployments/infrastructure/services.tf:217` =
`### OpenViking's workspace, its OAuth SQLite db and RAGFS's local scratch.`

The jobspec twin was fixed:
`deployments/applications/services/openviking.hcl:32` =
`    ### Holds ov.conf's workspace and RAGFS's local scratch. The vectors live`

The documentation verdict's DOC-17 named both files explicitly. Fixing one
leaves the two comments on the same volume contradicting each other, which is
worse than the state before the fix, when they at least agreed.

The surviving clause is false, and I can now prove it with the upstream the
doc reviewer could not reach: OpenViking's `OAuthConfig.enabled` defaults to
`False`, and `app.py` gates the `OAuthStore` and every `/oauth` route behind
`if ov_cfg.oauth.enabled:`. The rendered `ov.conf` in this jobspec carries no
`oauth` key at all, so the SQLite file is never created. Delete the clause.

### A16 (low). The new `--no-deps` comment miscounts, and contradicts its own file.

`deployments/applications/services/openviking/Dockerfile.openviking:37` =
`# psycopg, psycopg_pool and pydantic; the base image carries three and RUN #2`

The base image carries **two** of the four — `openviking` and `pydantic`.
RUN #2 supplies **two** — `psycopg` and `psycopg_pool`, because
`psycopg[binary,pool]` pulls `psycopg-pool` and that RUN has no `--no-deps`.
`psycopg` appears nowhere in OpenViking's `uv.lock`, which is also what
`:12-13` of this same file already says: "Neither ov-postgres nor psycopg is
in the upstream image." The two sentences cannot both be true.

This is the stranded-prose pattern again, and it came from transcribing my own
cycle-2 note: that note said ov-postgres's *three declared deps* are covered,
which became "the base image carries three".

The flag is right and nothing is omitted, so this costs nothing today. It
costs something later: a reader who believes `psycopg_pool` ships in the base
could strip `pool` from RUN #2 as redundant, and `adapter.py`'s
`from psycopg_pool import ConnectionPool` would fail at OpenViking's startup,
not at build. Suggested: "the base image carries openviking and pydantic; RUN
#2 supplies psycopg and, through the `pool` extra, psycopg_pool."

### A10 (low, carried from cycle 1). Unreferenced templatefile variable.

`deployments/applications/services.tf:405` =
`      openviking_base_image = "ghcr.io/volcengine/openviking:v0.4.17.1"`

`grep -c openviking_base_image` in `openviking.hcl` is still 0. Harmless:
`templatefile` tolerates unreferenced vars and `terraform validate` passes, and
the pin is still doing its job because the justfile greps that line out of
`services.tf`. A `locals` entry would say what it is. Not required.

### A17 (informational). Guard docstring names two proxies, `JOBSPECS` names three.

`scripts/check_oauth2_proxy_guard.py:4` =
`dash and registry-ui each sit entirely behind their own oauth2-proxy, and`

Reads as historical rationale rather than a count, and the next sentence
already says "over every oauth2-proxy jobspec in the repo". Noted only because
A8 was fixed on the same principle.

---

## Re-attacked, and what I found

Every settled finding, per the re-attach rule. Nothing rubber-stamped.

- **A7 (closed) — re-derived, still exact.** I diffed `ALLOWED_CUSTOM_PARAMS`
  against `PgVectorParams` at the pinned tag programmatically: 15 declared
  fields plus the `schema` alias, zero missing and zero extra. Also checked the
  jobspec's values, not just its keys: `"index_method": "flat"` is a legal
  `IndexMethod` literal (`Literal["flat", "hnsw", "ivfflat", "auto"]`), which
  the checker does not assert.
- **P2 / R13 (settled) — re-attacked with a live planted exemption.** Mirrored
  the three jobspecs into scratch, ran the guard clean (exit 0), planted
  `OAUTH2_PROXY_SKIP_AUTH_ROUTES` in the **new** jobspec, and the guard exited 1
  naming that file and printing its full message. The hook's widened `files:`
  pattern matches `oauth2-proxy-openviking.hcl`. Both halves of R13 hold.
- **P6 (new, clean) — the justfile's guard message, checked at runtime.** That
  string is a literal no gate exercises and the first of its kind here, so
  reading it proves nothing. I mirrored the justfile into scratch at the same
  relative depth (its `set dotenv-filename` is path-relative), and: `just show`
  printed exactly the two `services.tf` pins, and rewriting the base to
  `:latest` made `just build` print
  `!! openviking_base_image is :latest, which is not a pin. Use a version tag.`
  and exit 1 before docker ran. R2's "DERIVES rather than restates" is real.
- **A11 (settled) — unchanged, still acceptable.** The rerank assertion still
  measures the port alone and both block regexes still hard-code indentation.
  Both still match the real jobspec: a non-matching rerank regex would raise
  "no rerank section", and the forced hook run passes.
- **A1, A2, A3, A4, A5, A6, A9, P1, P3, P4, P5** — no change in scope, still
  hold. Spot-confirmed the two that this cycle's edits sat next to: the
  Dockerfile still has exactly the two `--target` installs section 7 calls for
  (A6's third is still gone), and the jobspec's config body is byte-unchanged
  around the volume-comment edit, so P1's `extra=forbid` clearance stands.
- **A12** — no change in scope, still holds. `docs/openviking.md`'s verification
  block records no radxa headroom measurement, so R1's placement precondition
  is still unretired. Deploy-time obligation, not commit-blocking.

## Scope

Three paths sit outside section 7's declared surface:
`deployments/applications/storage.tf`, `docs/haproxy_reverse_proxy.md`,
`docs/workload-identity.md`.

All three are prose this diff falsified — a new edge hostname the haproxy
routing table enumerates, a "keys for buckets no job consumes" claim
`openviking` now contradicts, and the KV comment A8 named. Section 7's "Gates
and docs" bullet under-listed rather than the diff over-reaching, and leaving
any of the three would be the exact stale-prose failure this review keeps
catching. I score the eval's "no collateral damage" row **4/5**, which meets
its threshold. Every other changed line traces to a section 7 bullet.

`.loop/ledger.json` is harness state and is stripped from the fingerprint.

## What a green stamp here does not cover

Unchanged from cycle 2 and worth restating at the cap, because nothing in this
tree can close it: no image is built, no apply is run, and every runtime row in
the eval is unscored. R15's runtime half is a labelled proxy by design. In
particular nothing here measures whether a live Vault-issued ID token is
accepted, whether a foreign audience is refused, whether an embedding or rerank
call reaches embark, or whether a collection persists into the `openviking`
schema. The eval records those as unproducible rather than rescoring them
against `terraform validate`, which is the right call, and the operator
verification block in `docs/openviking.md` is where they get answered.
