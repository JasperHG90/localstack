---
verdict: pass-with-required-fixes
tree: 88a65fa345712e188794ea8a69e885bcd3826a1e
---

# OV1-openviking-service — adversarial, cycle 2

Deterministic floor first: `loopctl verify-eval-substance OV1-openviking-service`
returned `valid`, exit 0, with no advisories. Tree asserted with
`loopctl verify --expect-tree 88a65fa3...` from the briefing value, exit 0.

Gate re-run independently on THIS tree, not trusted from the cycle-1 stamp
(the fingerprints differ, so the brief requires the re-run): `just pre_commit`
exit 0 in 1m08s, all hooks Passed. The two openviking hooks report
`(no files to check) Skipped` under `--all-files` because the jobspec and the
checker are untracked in this worktree, so I forced them plus ruff, mypy,
nomad-fmt, end-of-file-fixer and detect-private-key over all eight new files
with `pre-commit run --files ...`: all Passed, exit 0. Stamp written to
`.loop/scratch/OV1-openviking-service.adversarial/trust-stamp.json`.

**No scope-binding lines.** My briefing carried a tree fingerprint but no
`scope:` digest and no bound path set. Writing a digest I computed myself
would bind a set nobody asked me to review, so the three lines are omitted and
this verdict falls back to the whole-tree binding, which is stricter.

## Verdict

The two cycle-1 blockers are genuinely fixed, and so are all five of the
lesser findings the hand-off claimed. I verified each one against the code and
against upstream rather than against the summary, and M2's specific risk (that
deleting `openviking[auth]` breaks `auth_mode: "oidc"`) is disproven.

One new HIGH finding, which the fixes did not create but did leave standing:
the surviving first pip install has the same 163-package hazard that justified
deleting the third one. One flag fixes it. Two LOW items follow, one of them a
cycle-1 finding the hand-off wrongly reported as fixed.

---

## Required fix

### A13 (high) — install #1 has no `--no-deps`, so it reinstalls OpenViking and 162 other packages over the base image's locked venv

`deployments/applications/services/openviking/Dockerfile.openviking:32-34`

    RUN /usr/local/bin/python3.13 -m pip install --upgrade \
        --target /app/.venv/lib/python3.13/site-packages \
        "ov-postgres @ git+https://github.com/JasperHG90/openviking_extensions@ov-postgres-v0.2.0"

`ov-postgres`'s `pyproject.toml` at the pinned tag declares
`dependencies = ["openviking>=0.4.16", "psycopg[binary,pool]>=3.1", "pydantic>=2"]`.
Run exactly as written, that requirement resolves **163 packages**, among them
`+ openviking==0.4.17.1` itself, plus `fastapi==0.141.1`, `starlette==1.6.0`,
`pydantic==2.13.5`, `litellm==1.91.1`, `protobuf==7.36.1`, `tree-sitter==0.26.0`
and the twelve `tree-sitter-*` grammars. Measured with
`uv pip install --dry-run --upgrade --target ...` on the exact string.

pip does not treat the `--target` directory as satisfying a requirement. I
reproduced that with **pip 26.2.1**, the version P11 records inside the image:
install `idna==3.4` into a target directory, then

    pip install --dry-run --upgrade --target <that same dir> anyio

reports `Would install anyio-4.15.1 idna-3.19 typing_extensions-4.16.0`. And
`--upgrade` is what lets pip `rmtree` each existing target directory before
replacing it, so this is a replacement of the venv's contents, not a merge.

Three consequences:

1. The base image is built with `uv sync --locked` (upstream `Dockerfile:85`
   and `:91`). This RUN un-pins that whole set at build time, so two builds of
   the pinned derived tag `v0.4.17.1-1` need not produce the same image. The
   file's own comment claims the opposite at `:25-26`: "The tag is pinned:
   `main` would make the image non-reproducible." R2's premise is that the pin
   is the artifact binding; 163 floating packages is not that.
2. It replaces the base image's source-built `openviking` with the PyPI wheel.
3. The comment at `:22-23` says "Same shape as
   `services/embark/Dockerfile.embark`." The shape differs in the one flag that
   mattered there. `Dockerfile.embark:32-33`: "`--no-deps`: every transitive
   dependency is already in the venv from the base image, and resolving them
   again here would pull CPU wheels back in", above
   `Dockerfile.embark:40` = `RUN pip install --no-deps --upgrade --target ...`.

This is the same hazard as my cycle-1 A6 on the third install (165 packages).
Deleting install #3 removed the redundancy but not the cost, so the stated
rationale for the M2 fix is only half-realized.

**Not fatal, and I checked rather than assumed.** A `cp310-abi3
manylinux_2_31_aarch64` wheel exists for openviking 0.4.17.1, so the build
succeeds on the radxa target rather than falling back to an sdist that would
need rust and cmake. I downloaded that wheel and confirmed it carries
`openviking/web_studio/dist/index.html`, so the Studio bundle the upstream
Dockerfile verifies at `:113` survives the replacement. The harm is the
unlocked dependency set and its rebuild non-determinism, not a broken image.

**Fix:** add `--no-deps` to that RUN. All three of ov-postgres's declared
dependencies are covered without resolution: `openviking` and `pydantic` ship
in the base image (P11, upstream `pyproject.toml:32-80`), and
`psycopg[binary,pool]` is RUN #2, which resolves exactly four packages. I read
ov_postgres's own third-party imports to be sure the flag is safe: `openviking`,
`psycopg`, `psycopg_pool`, `pydantic`, and nothing else. Correct the `:22-23`
comment in the same edit.

---

## Cycle-1 findings: each fix verified, not taken on report

**A1 / B1 — CLOSED.** The `#subdirectory=packages/ov-postgres` fragment is gone
(`Dockerfile.openviking:34`). Reproduced both directions with
`uv pip install --dry-run --no-deps`: the bare form exits 0 and resolves to
commit `9466e7ee`; the fragment form fails with "The source distribution ... has
no subdirectory `packages/ov-postgres`". The GitHub trees API at
`ov-postgres-v0.2.0` lists a root `pyproject.toml` and `src`, no `packages`, and
that `pyproject.toml` declares `name = "ov-postgres"`. The comment at `:28-31`
is accurate about `main` versus this tag.

**A2 / B2 — CLOSED.** `random_password.openviking_root_key`,
`vault_kv_secret_v2.openviking_root_key`, the templatefile variable and the
`root_api_key` line in ov.conf are all gone. Grepping the tree outside `.loop/`
for `root_api_key|openviking_root_key` returns one hit, `docs/openviking.md:127`,
which describes `auth_mode: "trusted"` as a candidate follow-up and is correct.
Section 7's declared KV surface (`db`, `bifrost`, `minio`) is now exactly what
`secrets.tf` writes.

**A3 / H1 — CLOSED.** `oauth2-proxy-openviking.hcl:76` =
`OAUTH2_PROXY_COOKIE_EXPIRE="3600s"`, matching `id_token_ttl = 3600` on the
Vault client in `oidc.tf`. Valid Go duration. `cookie_refresh` is unset, so
there is no refresh-versus-expire validation conflict.

**A4 / H2 — CLOSED.** `OAUTH2_PROXY_SET_AUTHORIZATION_HEADER` is absent. Both
places that argued for it now say the opposite: the jobspec comment at `:16-18`
("upstream documents it as setting the Authorization Bearer RESPONSE header")
and `docs/openviking.md:32-34`. Not reworded around the old claim — the claim
is reversed and the setting is gone.

**A5 / M1 — CLOSED.** `destination = "secrets/ov.conf"` (`:166`) and
`OPENVIKING_CONFIG_FILE = "/secrets/ov.conf"` (`:79`). No `local/ov.conf`
anywhere in the tree. On the interaction you asked about: `change_mode` is
destination-independent, and the `env` block is a static variable that never
touches the template, so neither is disturbed. P11 records the image runs as
root, so the 0700 secrets tmpfs is readable. This deviates from section 7's
literal "a `local/ov.conf` template", on my cycle-1 instruction, because the
realized design inlines four credentials in that file rather than taking P17's
env-placeholder split. Recorded, not held against the diff.

**A6 / M2 — CLOSED as written, and the risk you flagged is disproven.**
Deleting `openviking[auth]` does not break `auth_mode: "oidc"`.
`python-jose[cryptography]` is required by BOTH the `auth` extra and the `bot`
extra (OpenViking `uv.lock:3852-3853`, and the `bot` group at `:3703`), and the
upstream Dockerfile installs `--extra bot --extra gemini` (`:85`, `:91`), so
jose is in the image without the auth extra. `httpx` is a plain base dependency.
The OIDC plugin imports jose lazily inside `_check_jwt_available`, and
`plugins/__init__.py` registers `OIDCAuthPlugin` only if that import chain
works. The auth extra's one unique member is `python-ldap`, which the OIDC path
never touches and which has no wheels, so installing it in a runtime image
without libldap headers would likely have failed the build anyway. The deletion
is right twice over. The package-count cost the finding named survives in
install #1, which is A13.

**A7 / M3 — CLOSED, with a positive control.** `ALLOWED_CUSTOM_PARAMS` is now
exactly the fifteen fields `PgVectorParams` declares plus `schema`, read off
`src/ov_postgres/config.py` at the pinned tag, where
`model_config = ConfigDict(extra="forbid", populate_by_name=True)` and
`db_schema: str = Field(alias="schema")`. Control: adding `tz_policy`,
`min_pool_size`, `max_pool_size`, `connect_timeout` and `application_name` to
the real jobspec now yields `[]` failures where cycle 1 got a false
"which ov-postgres forbids", and a planted `schemaa` typo is still caught.

**A9 — CLOSED.** The `secrets.tf` header now reads "All three" and three
resources follow. Folded into the A2 fix, as predicted.

**A11 — settled, re-confirmed on this tree.** The rerank assertion still
measures the port alone, and both block regexes still hard-code indentation
depth. Both regexes still match the current file and `_vectordb_backend`
returns the adapter path, so nothing drifted. Acceptable as recorded.

**A12 — absence claim: no change in scope, still holds.** R1's radxa headroom
precondition is unretired. `docs/openviking.md`'s verification block records no
measurement. Deploy-time obligation, not commit-blocking.

---

## Also open (low, not blocking)

### A8 (low) — a cycle-1 finding reported as fixed that was not

`deployments/applications/storage.tf:33-35`, byte-identical to HEAD
(`git diff --stat` on that file is empty):

    # No Vault KV entry yet -- the convention here is that creds land in
    # Vault when a job consumes them (memex, loki, tempo), not at bucket
    # creation (datalake, openviking, mlflow-artifacts have none).

This diff adds `vault_kv_secret_v2.openviking_minio_credentials` at
`default/openviking/minio`, so `openviking` now belongs in the first list, not
the second. `.claude/rules/minimal-comments.md`: leave existing comments be
unless your change makes them wrong. This change makes it wrong. Drop
`openviking` from the parenthetical.

The hand-off said every cycle-1 finding was accepted and fixed. This one was
not. Flagging the mismatch, not just the comment.

### A14 (low) — the first operator verification command cannot return what its comment says

`docs/openviking.md:94-95`:

    # the service is up and its backends opened
    $ curl -s https://openviking.lab.orangecluster.nl/ready

`haproxy.hcl` routes that hostname to `192.168.2.50:4182`, the proxy.
`oauth2-proxy-openviking.hcl` sets no skip-auth route, which is precisely what
`scripts/check_oauth2_proxy_guard.py` enforces and what
`.pre-commit-config.yaml:83` now covers for this file. oauth2-proxy gates every
path but its own `/oauth2/*` and `/ping`, so an unauthenticated curl gets the
sign-in page or a 401, never the readiness JSON. The probe that works is
against the node, which is what the Consul check does (`openviking.hcl:56-64`);
`services.tf`'s firewall admits only `192.168.2.50` to 1933, so it has to run on
radxa. Point the line at `http://192.168.2.50:1933/ready` and say where it runs,
or drop it and lean on the Consul check.

Nothing is deployed, so this is reasoned from the config and oauth2-proxy's
documented default, not from a live request.

### A10 (low, unchanged) — `openviking_base_image` is a templatefile variable the template never reads

`grep -c openviking_base_image deployments/applications/services/openviking.hcl`
is 0. `terraform validate` passes, since `templatefile` tolerates unreferenced
variables, and R2 is satisfied because the line is in `services.tf` where the
justfile reads it. Recorded so the placement is not mistaken for a value the
jobspec consumes. Not required.

---

## What I checked for breakage and found clean

- **Stale text around the three removals.** Grepped the whole tree for
  `root_api_key`, `openviking_root_key`, `local/ov.conf`, `two oauth2-prox`,
  `two proxies`, `both proxies`, `4180 and 4181`. The only survivors are
  `deployments/infrastructure/secrets.tf:252` and `:260` ("both proxies declare
  a bare `vault {}`", "The two proxies gate different hostnames"), which sit
  inside the registry-ui block and describe the pair sharing
  `vault_identity_oidc_client.oauth2_proxy`. The new block at `:294-298`
  explicitly says it does NOT share that client, so those two sentences are
  still true of what they describe. Not a finding.
- **The proxy-count edits.** `services.tf:410` now reads "Three proxies, three
  ports" with the 4182 rule beneath it; `docs/haproxy_reverse_proxy.md` names
  4180, 4181 and 4182 and adds the route row. Consistent with
  `haproxy.hcl:186` and the new `backend openviking` at `192.168.2.50:4182`.
- **The `bifrost_smoke.py` documentation fix is true.** `scripts/bifrost_smoke.py:17-18`
  says the rerank assertion sends the OBJECT form on purpose, and `:115-122`
  asserts a 401. `scripts/embark_rerank.py` exists.
- **Terraform references resolve.** `minio_accesskey.users["openviking"]` exists
  (the `openviking` bucket's writer carries `generate_access_key = true`),
  and `postgresql_role.role["openviking"]` / `random_password.password["openviking"]`
  exist (`database.tf:8`, `:34-35`, both `for_each` over `local.roles`).
- **R13's guard.** Forcing the hook with the openviking proxy in the file list
  produced "oauth2-proxy carries no auth exemption ... Passed" rather than
  Skipped, which is live evidence the widened `files:` pattern matches the new
  filename. Settled finding P2 undisturbed.
- **The checker runs green** on the real jobspec and its `--self-test` passes.

## Not re-derived

Per the briefing, scope and R11, the ov.conf templating layers, R13's guard and
the checker's `_vectordb_backend` scoping fix were cleared in cycle 1 and
nothing in this cycle's changes disturbs them. Settled entries P1 through P5 in
the ledger stand.

Ledger updated at `.loop/scratch/OV1-openviking-service.adversarial/findings.json`:
seven findings closed with evidence, three left open, one absence claim, two new
(A13, A14).
