---
epic = "openviking"
depends_on = ["OV1-openviking-service"]
priority = 100
summary = """
Give each person their own OpenViking account. Blobs isolate at the physical path
root (/local/<account>/...) and vectors by an account_id filter, so NEW content is
separated on every upload surface including Web Studio and WebDAV, which write the
account-shared viking://resources tree and cannot be redirected by any config key.
Existing content in the lab account stays shared until an operator closes it,
by re-minting its keys from a discarded seed or by deleting the account.
"""
premise = { Q1 = "operator chose to close the lab exposure by re-minting its keys from a discarded seed, preserving the content and staying reversible, over deleting the account outright", Q2 = "every person being sole ADMIN of their own account grants nothing over any other account", Q3 = "account id equal to user id" }
measured_against = { Q1 = { kind = "package", version = "0.4.17.1", ref = "ghcr.io/volcengine/openviking:v0.4.17.1", note = "regenerate_key against a hashing-enabled manager rejects the previously issued key; see P13" }, Q2 = { kind = "package", version = "0.4.17.1", ref = "ghcr.io/volcengine/openviking:v0.4.17.1", note = "account-scoped admin routes call _check_account_access; create/list/delete account are root-only" }, Q3 = { kind = "package", version = "0.4.17.1", ref = "ghcr.io/volcengine/openviking:v0.4.17.1", note = "validate_account_id accepts jasper and veerle; user ids are namespaced per account under /local/{account_id}/_system/users.json" } }
---

# Ticket: OV2-openviking-user-scoped-resources

## 1. Title

Give each person their own OpenViking account, so newly uploaded resources are
isolated on every surface rather than only where a caller omits a target.
Content already in the shared `lab` account is not moved and stays shared until
Q1 is executed.

## 2. Size / Effort

**M.** No new subsystem and no new file, but it rewrites the identity shape:
the account local, the key-derivation locals, three Vault writes and the
remote-exec provisioner, plus four separate docs sections that describe it. What
holds it to M rather than L: the key derivation itself is unchanged (proven in
§12 P3), so no key rotates as a side effect.

## 3. Triggered by

Operator, shown that `viking://resources` is readable and writable by every user
in the account: "I DO NOT WANT THIS. I want user-scoped resources." Then, shown
that a config default misses Studio and WebDAV, chose the account split over the
cheaper partial fix.

## 4. Context

`deployments/applications/secrets.tf:273` pins one account, `openviking_account = "lab"`,
and `deployments/applications/secrets.tf:274` puts both people in it as
`jasper = "admin"` and `veerle = "user"`. Every user in an account shares
`viking://resources`: `is_accessible` in the installed openviking 0.4.17.1
returns `True` for that scope unconditionally, for read and for write.

A configured default (`user_config_defaults.add_targets.resource_uri`) does not
fix this, and that is why this ticket is shaped the way it is. It is consulted
only on the branch where a caller supplies neither `to` nor `parent`, and the
deployment's two human-facing upload surfaces both supply one:

- Web Studio's add-resource form ships prefilled with `viking://resources/` as
  the parent, so the fallback branch never runs (§12 P1).
- WebDAV builds `viking://resources` as a literal in server Python and its
  router is registered unconditionally, so no config key reaches it (§12 P2).

What DOES isolate is the account, and it does so by two different mechanisms
that the plan must not conflate. For blobs it is the path: `_uri_to_path` maps
`viking://<rest>` to `/local/<account_id>/<rest>`, so two accounts never address
the same bytes and Studio's prefilled URI and WebDAV's literal both resolve
inside the caller's own account (§12 P4). For vectors it IS a scope check:
both accounts share one `context` collection in one Postgres schema, and
`_SingleAccountBackend` ANDs an `account_id` equality into every query and
stamps it on every write (§12 P8).

The provisioner that would create those accounts already exists at
`deployments/applications/services.tf:495` — it creates one account and then
registers users into it. `create_account` in 0.4.17.1 creates the account AND
its first admin user and initializes both directory trees, so one call per
person replaces the current create-then-register-then-promote sequence (§12 P5).

## 5. Non-goals / out of scope

- **Migrating or deleting anything already in the `lab` account.** Operator
  chose this explicitly. The consequence is NOT that the content becomes
  unreachable — nothing here revokes a `lab` key, and both people are likely to
  hold a working one on disk already, since `ov config add` writes it in the
  clear (`docs/openviking.md:155`). `lab` survives this apply as a live,
  still-shared account that no Vault entry points at. Q1 carries what to do
  about that; a diff that deletes or moves its content is a scope violation.
- **`server.user_config_defaults.add_targets.resource_uri`.** The earlier draft
  of this ticket set it; the operator chose accounts instead of both. Do not set
  it. `scripts/check_openviking_config.py` therefore gains no new assertion and
  its `failures` function is not touched.
- **Any change to the permission model.** `viking://resources` stays shared
  *within* an account. With one person per account that is a tree of one, which
  is the point; the hardcoded `return True` is not being fought.
- **Roles as a security control.** Each person becomes ADMIN of their own
  account because `create_account` makes its first user ADMIN and there is no
  demotion path (`deployments/applications/services.tf:560` records that
  `set_user_role` only promotes).
  ADMIN over an account of one grants nothing over anyone else.
- **Offboarding automation.** Still out of scope, but the design CHANGES what
  the hand-run call is, so the docs must change with it. Under one account per
  person `DELETE /accounts/<person>/users/<person>` can never succeed: the sole
  user of an account is its only ADMIN, and the server refuses to remove the
  last active admin (§12 P10). The working call becomes
  `DELETE /accounts/<account_id>`, which is root-only and removes the whole
  account tree. R6 requires the runbook at `docs/openviking.md:105` to be
  rewritten to that call; automating it stays out of scope for the same reason
  it always was — it destroys content.
- **Any live `terraform apply`.** This ticket lands the code; applying it is an
  operator step, per §9.

## 6. Requirements & restrictions

- **R1.** One OpenViking account per person, account id equal to the person's
  user id. Replaces the single `local.openviking_account`
  (`deployments/applications/secrets.tf:273`). Producer: `secrets.tf`, §7.
- **R2.** Derived keys carry each person's own account in the first segment and
  are otherwise unchanged, so no existing key value rotates as a side effect of
  the reshape. Producer: the `openviking_b64url` and `openviking_user_keys`
  locals (`deployments/applications/secrets.tf:293`,
  `deployments/applications/secrets.tf:304`), §7. Verified by P3.
- **R3.** The provisioner creates one account per person with that person as
  `admin_user_id`, and still reconciles each key against the seed. The
  create-user and promote-to-admin steps are removed, being redundant once each
  person is their account's first user (P5). Producer:
  `deployments/applications/services.tf:495`, §7.
- **R4.** `vault_kv_secret_v2.openviking_user_keys`
  (`deployments/applications/secrets.tf:349`) records each person's own account,
  and `vault_kv_secret_v2.hermes_openviking_key`
  (`deployments/applications/secrets.tf:388`) records jasper's, so Hermes keeps
  acting as jasper rather than pointing at a `lab` account nothing serves.
  Honouring this EMPTIES Hermes's memory: `deployments/applications/services/hermes.hcl:244`
  makes OpenViking its memory provider, so its history lives under `lab` and the
  new account starts blank. That is a certain consequence of R4, not a risk of
  missing it, and R6 requires it in the docs.
- **R5.** Terraform file layout is respected: identity locals and Vault writes
  stay in `secrets.tf`, the provisioner stays in `services.tf`. Required by
  `.claude/rules/terraform-file-layout.md`, whose table assigns `secrets.tf` the
  Vault KV writes and `services.tf` the jobs. No new `.tf` file.
- **R6.** `docs/openviking.md` describes the new identity shape: one account per
  person, what that isolates that the old shape did not, that `lab` survives
  with working keys until it is deleted, that Hermes starts with an empty
  memory, and the rewritten offboarding call from §5. Required by
  `.claude/rules/slop-scan-for-docs.md`.
- **R7.** Fix the stale enumeration at `docs/openviking.md:229`, which says
  "the nine config values" and then lists exactly nine of the fifteen `failures`
  actually asserts. The count matches its own list, so a count-only edit would
  leave nine items labelled fifteen: extend the LIST, then make the count match.
  Required by `.claude/rules/pre-existing-issues.md`. The checker's own
  "twelve settings" (`scripts/check_openviking_config.py:5`) is CORRECT for the
  twelve-row table beneath it and must not be touched.
- **R8.** Comments record the reasons that are not visible in the code — why one
  account per person, why the promote step is gone — not a narration of the
  resources. Required by `.claude/rules/minimal-comments.md`.
- **R9.** No new dependency (`.claude/rules/uv-installer.md` governs if that
  turns out wrong).

## 7. Code surface

| Path | Change |
|---|---|
| `deployments/applications/secrets.tf:273` | replace `openviking_account` with a per-person account mapping |
| `deployments/applications/secrets.tf:274` | `openviking_users` loses its role values; every person is their own account's admin |
| `deployments/applications/secrets.tf:285` | delete `openviking_admin_user` — one bootstrap admin no longer exists |
| `deployments/applications/secrets.tf:293` | `openviking_b64url`: encode one account segment per person, not one shared |
| `deployments/applications/secrets.tf:304` | `openviking_user_keys`: take each person's own account segment |
| `deployments/applications/secrets.tf:349` | the Vault entry's `account` and `role` fields follow the new shape |
| `deployments/applications/secrets.tf:388` | `hermes_openviking_key.account` becomes jasper's account |
| `deployments/applications/services.tf:495` | provisioner: one `POST /accounts` per person; drop the create-user and promote loops; per-account key-reconcile URL |
| `docs/openviking.md:24` | rewrite the auth section (spans 24-132): one account per person, the role table, what is isolated |
| `docs/openviking.md:99` | rewrite the offboarding runbook (spans 99-114): the per-user DELETE cannot succeed under this design; the working call is `DELETE /accounts/{account_id}` |
| `docs/openviking.md:187` | the account-shared paragraph — `viking://resources` is now a tree of one, and re-homing Hermes empties its memory |
| `docs/openviking.md:229` | extend the listed values to all fifteen, then fix "nine" (R7) |
| `docs/openviking.md:339` | stale twice: "two lines in `local.openviking_users`" no longer describes adding a person |

`ov.conf.json` is NOT in this list, deliberately: §5 drops the config default.
`scripts/check_openviking_config.py` is not in it either — its "twelve settings"
docstring is correct for its own table, so R7 is confined to the docs.

## 8. Tests & validation gates

Gate command, from `.loop/config.json` `gates`: `just pre_commit`
(`justfile:19`, `pre-commit run --all-files`).

1. `terraform fmt -check -recursive` and `scripts/tf_validate.sh` pass on
   `deployments/applications`. These are the gates that actually cover the two
   `.tf` files this ticket rewrites, and `just pre_commit` runs both
   (`justfile:19`).
2. `terraform plan` against `deployments/applications` is read and every listed
   resource accounted for. Expect churn on the three Vault KV entries in §7 and
   a provisioner re-run; expect NO change to `nomad_job.openviking`. An
   unexplained resource in that plan blocks the ticket.
3. `python3 scripts/check_openviking_config.py --self-test` still passes. This
   is a pure no-regression check: no §7 row touches the checker, and R7
   explicitly leaves its "twelve settings" docstring alone. Hook
   `openviking-config-guard-self-test`, `.pre-commit-config.yaml:100`.
4. Markdown gates on `docs/openviking.md` per `.claude/rules/slop-scan-for-docs.md`.

Stated rather than pretended: no gate in this repo runs a deployed OpenViking,
so nothing here proves the accounts are actually created or that Studio lands in
the right tree. That is the operator verification in §9, and §12 P7 marks it
UNCERTAIN.

## 9. Risk assessment

- **Blast radius.** Identity for one service. Three Vault paths change content,
  the provisioner re-runs, and every OpenViking key in circulation changes its
  account segment. Nothing outside `deployments/applications` reads these.
- **Reversibility.** The Terraform reverts cleanly. The SERVER does not: accounts
  created by the provisioner are not deleted by reverting it, and content written
  into a per-person account stays there. So this is reversible in configuration
  and one-way in data, the same asymmetry the earlier draft carried.
- **A live account nobody watches, the likeliest surprise.** After apply, `lab`
  still exists holding everything uploaded so far, still shared between two
  users, and its keys are NOT revoked — the provisioner only re-mints keys for
  the accounts it creates. Anyone still holding a `lab` key keeps full read and
  write on the old shared tree, and `docs/openviking.md:155` records that
  `ov config add` writes that key to disk in the clear. So the exposure this
  ticket exists to close stays open for existing content until an operator step
  removes it. Q1 carries that step. Both people will ALSO see an empty resources
  tree under their new accounts and may read that as data loss.
- **Hermes, both ways.** Its key is a copy under its own KV prefix
  (`deployments/applications/secrets.tf:388`). Miss R4 and Hermes keeps a
  `lab`-account key: it reads and writes successfully into an account nobody
  else uses, and the failure is silent. Honour R4 and Hermes starts with an
  empty memory, since `deployments/applications/services/hermes.hcl:244` makes
  OpenViking its memory provider. The second is certain, not conditional.
- **Provisioner failure mode.** `POST /accounts` returning 409 is treated as
  success today. That stays correct per-person, but it also means a
  half-provisioned run cannot be told from a complete one by exit status. The
  existing `set -e` (`deployments/applications/services.tf:519`) plus trap
  (`deployments/applications/services.tf:527`) is what fails the apply.
- **Not fixed by this ticket.** Within an account `viking://resources` is still
  shared and still the Studio/WebDAV default. That is harmless at one person per
  account and becomes live again the moment a second person joins one.

## 10. Subtickets

One loop iteration, ordered:

1. `secrets.tf`: account mapping, key locals, the three Vault writes (R1, R2, R4).
2. `services.tf`: provisioner reshape (R3).
3. `terraform fmt` and `scripts/tf_validate.sh`, then read `terraform plan` (gates 1-2).
4. `docs/openviking.md` rewrite plus the count fix (R6, R7).
5. `just pre_commit` (gates 3-4).

R5, R8 and R9 are cross-cutting restrictions rather than steps: R5 constrains
where steps 1-2 put code, R8 governs any comment they write, R9 forbids a
dependency none of them needs. None has a deliverable of its own, which is why
none names a file in §7.

## 11. Open questions

**Q1 — The `lab` account survives with working keys. What closes it?** `tag: data`

The operator chose "leave existing data, out of scope", answered against a
design where existing content merely stayed shared. It still stays shared AND
reachable: nothing revokes a `lab` key and both people plausibly hold one on
disk. So new uploads are isolated while every existing one remains readable by
both — half of what the ticket was asked for.

An earlier draft recommended a per-user DELETE. P10 kills that: jasper is
`lab`'s only ADMIN and cannot be removed, and a user-DELETE only clears
`viking://user/<uid>` anyway, never `viking://resources`. Three real options:

- **(a) `DELETE /accounts/lab`** — root-only, closes it completely, and removes
  the content with it. Irreversible.
- **(b) Re-mint both `lab` keys from a throwaway seed** via
  `POST /accounts/lab/users/<user>/key`, keeping neither the minted key nor the
  throwaway seed — the key is deterministic in the seed, so retaining the seed
  retains the key. The keys on
  people's laptops stop working; the content survives, reachable again only by
  re-minting with the root key. This is the same call the provisioner already
  relies on (`deployments/applications/services.tf:566`).
- **(c) Leave it live and documented.** Old material stays shared.

**SETTLED — operator chose (b)** on 2026-09-06. Recorded in the front-matter
`premise` table so pickup re-asks whether it still holds.

**Recommendation was (b).** It closes the exposure without destroying anything and
stays reversible, which (a) is not. It costs one runbook block in the docs and
no code. VERIFIED (§12 P13): driving the real `regenerate_key` against a
hashing-enabled manager rejects the previously issued key.

**Q2 — Everyone becomes ADMIN of their own account. Is that acceptable?**
`tag: design`

Forced, not chosen: `create_account` makes its first user ADMIN and
`set_user_role` only promotes, so an account of one has no USER-only shape.
ADMIN scopes to its own account and grants no cross-user read (measured in
OV1 and recorded at `docs/openviking.md:179`).

**Recommendation:** accept. Note it in the docs role table rather than working
around it.

**Q3 — Should the account id equal the user id, or be derived?** `tag: design`

Equal is simplest and makes a key self-describing when parsed. The cost is that
renaming a person changes both, and a future shared account would need a name
that is not a person's.

**Recommendation:** equal, as scoped in R1. Revisit only if a shared account is
ever wanted.

## Premises / assumptions

**P1 — Web Studio sends an explicit parent, so a configured default cannot
reach it.**

Evidence: the shipped bundle in the installed openviking 0.4.17.1 prefills the
add-resource form, and the request builder drops the field only when it is
empty:

```console
$ grep -o 'useState("viking://[^"]*")' web_studio/dist/assets/add-resource-page-*.js
useState("viking://resources/")
```

An unedited form therefore posts `parent: "viking://resources/"`. This premise
is what disqualifies the config-default design, so it is load-bearing for
choosing the account split at all.

**P2 — WebDAV hardcodes the shared scope in server Python and is registered
unconditionally.**

Evidence: read from the installed openviking 0.4.17.1. Read-only; `sed -n` prints
and changes nothing.

```console
$ cd "$(python -c 'import openviking,os;print(os.path.dirname(os.path.dirname(openviking.__file__)))')"
$ sed -n '73p' openviking/server/routers/webdav.py
    return "viking://resources" if not resource_path else f"viking://resources/{resource_path}"
$ sed -n '630p' openviking/server/app.py
    app.include_router(webdav_router)
```

Those two files live in the installed wheel, not in this repo, so they carry no
repo anchor by design — the `cd` above is how the implementer re-reads them.

No configuration key reaches either line.

**P3 — The account split does not rotate any key's secret, because account_id is
not in the derivation.**

Probe: `generate_api_key` from the installed 0.4.17.1 against a local
re-implementation of the `secrets.tf` derivation. Read-only; it computes hashes
and writes nothing.

```console
lab     /jasper   match=True  parses_to=('lab', 'jasper')
jasper  /jasper   match=True  parses_to=('jasper', 'jasper')
veerle  /veerle   match=True  parses_to=('veerle', 'veerle')
```

`derive_seeded_api_key_secret(user_id, seed)` takes no account, so only the
first segment moves. Per-person account ids are legal: `validate_account_id`
accepts `jasper` and `veerle`.

**P4 — For blobs, the account is the first segment of the physical path, so two
accounts cannot address the same bytes.**

Evidence: the method is `_AccessMixin._uri_to_path`, line 430 of
`storage/viking_fs/_access.py` in the installed 0.4.17.1. An earlier draft of
this plan named `_uri_to_agfs_path`, which does not exist in this version:

```console
$ uv run --with "openviking==0.4.17.1" python -c "<dir() over _AccessMixin>"
methods: ['_uri_to_path', '_uri_to_tree_path']
hasattr _uri_to_agfs_path: False
```

Its docstring states the mapping: `viking://{remainder}` to
`/local/{account_id}/{remainder}`. Read-only; `dir()` and `inspect.getsource`
execute nothing. The running-store half stays UNCERTAIN under P7.

**P5 — One `POST /accounts` per person replaces create-then-register-then-promote.**

Evidence: `create_account` in `openviking/server/routers/admin.py` of the
installed 0.4.17.1 takes `admin_user_id`, mints that user's key via
`manager.create_account(...)`, then calls `initialize_account_directories` and
`initialize_user_directories`. So the account, its first ADMIN user and both
directory trees exist after one call.

**P6 — Two people, named in one place.**
`deployments/applications/secrets.tf:274` is the only declaration of who exists.
`path:line` anchor, current tree.

**P7 — UNCERTAIN: no gate here exercises a running OpenViking, and no probe in
this plan touched one.** `scripts/check_openviking_config.py:25` says so in the
checker's own docstring. So P4's path mapping is read from source rather than
observed against the live store, and nothing has confirmed that the existing
`lab` account behaves as Q1 assumes after the new accounts exist. §8 declines to
claim otherwise and §9 carries it as the primary risk.

**P8 — For vectors, isolation is an account filter rather than a path, and it
holds.** Both accounts share one `context` collection in one Postgres schema, so
this was the plan's most plausible fatal gap and it does not materialise.

Evidence: `_SingleAccountBackend` in `storage/viking_vector_index_backend.py` of
the installed 0.4.17.1 binds an account and applies it on every side —
`Eq("account_id", self._bound_account_id)` ANDed into queries at lines 535 and
657, record filtering on read at 349 and 470, the field stamped on write at 236
and 425, and a mismatched record rejected at 230. `account_id` is a declared
schema field (line 56).

This is why §4 names two mechanisms. If a future version drops that filter, the
blobs stay isolated and search silently stops being, which no gate here would
catch.

**P9 — Nothing in this change revokes an existing `lab` key.** The provisioner
re-mints keys only for the accounts it creates (the reconcile loop at
`deployments/applications/services.tf:566`), and no call in it deletes a user or
an account — the comment at `deployments/applications/services.tf:550` says so
outright. The root key and seed stay in Vault at
`deployments/applications/secrets.tf:316` and
`deployments/applications/secrets.tf:335`, so a `lab` key can also be re-minted
by hand. This is the premise Q1 turns on, and it is the opposite of what an
earlier draft of this plan claimed.

**P10 — Under one account per person, a per-user DELETE can never succeed, so
the offboarding call in the docs must change.**

Evidence: `begin_user_deletion`, line 440 of `server/api_keys/legacy.py` in the
installed 0.4.17.1, counts active admins and refuses at one, lines 462-468. An
earlier draft named `_request_user_deletion`, which does not exist in this
version — the same defect cycle 2 caught in P4, so the name is quoted from
`grep` here rather than recalled:

```console
$ sed -n '462,468p' openviking/server/api_keys/legacy.py
            if user_info.get("role") == Role.ADMIN:
                active_admins = sum(
                    info.get("role") == Role.ADMIN and not info.get("deletion")
                    for info in account.users.values()
                )
                if active_admins <= 1:
                    raise FailedPreconditionError("Cannot delete the last active account admin")
```

The branch tests the TARGET's role and the account's admin count, never the
caller's, and the fence is unconditional across the whole chain: the route's
`Role.ROOT` special-case at `server/user_deletion.py` line 136 only picks
task-owner ids before calling `begin_user_deletion` unconditionally at line 147.
So holding the root key does not get past it. `create_account` makes
its first user ADMIN (P5), so every account this ticket creates has exactly one
admin and its sole member is undeletable. The working call is
`DELETE /accounts/{account_id}`, root-only, which removes the account tree with
it. This is why §5's offboarding bullet changed rather than being dropped.

**P13 — Re-minting a key invalidates the one already issued, so Q1 option (b)
actually closes the exposure.** This is the premise §5, §6 R6, §9 and Q1 all
defer to, and it was UNVERIFIED for one cycle.

Probe: `NewAPIKeyManager.regenerate_key` driven against a hashing-enabled
manager in a scratch directory, twice from clean, both runs identical. Nothing
in the repo or the deployment was touched.

```console
BEFORE re-mint: old key resolves -> user lab veerle
AFTER  re-mint: old key REJECTED -> UnauthenticatedError: Invalid API Key
```

Both resolution paths were exercised, not only the fast one. There is no key
cache in `server/auth/plugins/api_key.py`, `ov.conf.json` declares no oauth
block, the job runs one alloc, and `reload()` rebuilds from the persisted new
hash — so no stale acceptor survives the re-mint.