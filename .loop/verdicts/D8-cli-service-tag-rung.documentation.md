---
verdict: pass
tree: 6da6c67b9d4c5d1ea768470924a831714522ca56
---

# Documentation freshness: D8-cli-service-tag-rung (cycle 2)

Both cycle-1 findings are fixed and accurate. Every documented surface this
change touches is still described correctly at this tree, and no new drift
appeared. The doc's claims all resolve against the code I read here, not
against the cycle-1 tree.

## Cycle-1 findings: both closed

### 1. `join`'s `catalog` docstring — fixed, and correct

`cli/src/localstack_cli/api/services.py:108-109` now reads:

    `catalog` maps every registered Consul service name to its tags. Rung
    (b) resolves against its keys and the tag rung against its values.

That split is exactly what the code does. Rung (b) tests membership in
`consul_services = set(catalog)` (`services.py:121`, used at `:142`), which
is the keys. The tag rung calls `_sole_tag_carrier`, which scans
`catalog.items()` for `name in tags` (`services.py:87`), which is the values.
The rest of the paragraph is untouched and still holds: the "silently
resolving nothing at rung (b)" argument for `catalog` being required
(`services.py:111-113`) is unaffected by the new rung.

### 2. `docs/cli-read-commands.md:56-57` — fixed

Now "Two services carrying the same tag **leave** the row unresolved". Plural
subject, plural verb. The claim itself is still backed by
`services.py:87-88` (`len(carriers) == 1`) and by
`cli/tests/api/test_services.py`
(`test_a_tag_carried_by_two_services_resolves_nothing`, which asserts
`JobSource.UNRESOLVED` and that the backend survives).

## Re-verified against this tree

Every claim in the changed prose, checked again rather than carried over:

- **`consul-tag` table row** (`docs/cli-read-commands.md:43`). "No service by
  that name, but exactly one Consul service carries a tag of that name"
  matches the branch at `services.py:154`, which runs only after the `job-id`
  branch (`:128`) and the `consul-name` branch (`:142`) both fail.
- **"MinIO declares the tag on the port the route points at"**
  (`docs/cli-read-commands.md:43`, restated at `:58-59`).
  `deployments/infrastructure/services/minio.hcl:48-52` registers the service
  `minio` on port `http_api` with `tags = ["http", "s3"]`; `minio.hcl:19-21`
  binds `http_api` to 9000; `docs/haproxy_reverse_proxy.md:16` routes
  `s3.lab.orangecluster.nl` to `192.168.2.29:9000`. The console (9001) is the
  separate `minio` route (`minio.hcl:22-24`,
  `docs/haproxy_reverse_proxy.md:15`).
- **`unresolved` row** (`:44`). "matching no job, no catalog service and no
  unique tag" is the three conditions that must fail before `services.py:173`.
- **`no-route`'s "Thirteen exist"** (`:45`). Still true: the tag rung does not
  call `routed_jobs.add` (`services.py:154-172`), so no job's own row is
  suppressed. The code comment at `:159-161` says the same thing.
- **The `backend` paragraph** (`:62-65`). Blank for `no-route` holds, since
  those rows are built without a `backend` and the field defaults to `""`
  (`services.py:64`, `:189-198`). "nothing else on that row identifies it"
  holds for an unresolved row: `job` and `health` are both `NOT_FOUND` and
  `services` is empty (`services.py:174-183`).
- **Column names.** The doc's `source` header (`:39`) and its `backend`
  column (`:62`) match `cli/src/localstack_cli/commands/service.py:73`.
- **`consul-name` paragraph** (`:51-54`) is unchanged and still true: the rung
  reads the catalog, not the checks (`services.py:121`, `:142`).
- **Module docstring ladder** (`services.py:11-21`) lists `job-id`,
  `consul-name`, `consul-tag`, `unresolved` in the branch order at `:128`,
  `:142`, `:154`, `:173`.

## No new drift

- A repo-wide grep of `*.md` (excluding `.loop/` and vendored
  `.terraform/`/`.venv/`) for the `job_source` vocabulary returns only
  `docs/cli-read-commands.md`. The two other hits (`ROADMAP.md:92`,
  `docs/notes/audit/plan-premise-sweep-2026-07.md:346-348`) use "unresolved"
  about a design fork, not a service row.
- Nothing in the repo still claims `s3` is unresolved or that
  `192.168.2.29:9000` needs to be recognized by eye. The only remaining `9000`
  hits in docs are `docs/haproxy_reverse_proxy.md:16` (the route table, still
  correct), `docs/monitoring.md:273` and `docs/observability-python.md:31,46`,
  none of which touch CLI resolution.
- `README.md:26` names `service` in a command list with no behavior claim.
  `docs/haproxy_reverse_proxy.md:13-24` is a hostname-to-backend table that
  makes no claim about how the CLI resolves a route. Neither needs an update.
- No `SKILL.md` in the repo mentions `localstack service`.

## The test changes

`cli/tests/commands/test_read_commands.py:198-215`
(`test_service_json_is_parseable`) now runs against `EDGE_WITH_AN_ORPHAN` and
asserts the set of sources is a superset of `job-id`, `consul-tag`,
`no-route` and `unresolved`, so `unresolved` is exercised somewhere now that
`s3` resolves. Tests are not a documented surface, and the comment at
`:200-201` states the reason plainly. No doc consequence.

## Slop and plain-language scan (re-run on this tree)

`docs/cli-read-commands.md` passes all three layers.

- Layer 0: no identity leaks, no `TODO`/`FIXME`/`XXX`/`HACK`, and every
  backticked identifier and path in the changed lines resolves (`consul-tag`
  is a real `JobSource` value at `services.py:42`; `minio` and `s3` are the
  real service name and tag at `minio.hcl:49-52`;
  `deployments/infrastructure/services/haproxy.hcl` cited at `:68` exists).
- Layer 1: the section leads with its thesis ("An outer join... the
  disagreements are the output"), and the new paragraph earns its five lines
  by stating the uniqueness rule, the reason, and the one live instance.
- Layer 2, mechanically re-run on the current file: zero em dashes, zero
  ` -- `, zero semicolon splices outside code, zero smart quotes, zero tier-1
  slop terms, zero self-narration, zero "not only/not just", zero British
  spellings, zero spatial-copula verbs, and no non-table prose line over 80
  characters.
- Layer 3: no unbacked quality claims.

## Findings

### Informational: ragged wrap in the fixed docstring

`cli/src/localstack_cli/api/services.py:110` is a 35-character orphan line
("Required and keyword-only, both") in the middle of a paragraph that
otherwise wraps near 75. The cycle-1 fix was inserted without reflowing the
two lines after it. Ruff does not reflow docstrings, so this passes the
gates, and the prose is correct and readable either way. Not a doc-freshness
issue and not blocking. If the doc-writer touches this file again, reflowing
`:108-113` as one paragraph would tidy it.

### Informational: pre-existing health gloss, unchanged by this diff

`docs/cli-read-commands.md:47-48` says "Health comes from each job's own
registered service names", which describes the `job-id` rung. A `consul-tag`
row's health comes from the matched service's checks (`services.py:168`),
exactly as a `consul-name` row's already did (`services.py:149`). The gloss
predates this change and this change did not make it less accurate. Noted
again only so it is not mistaken for new drift.
