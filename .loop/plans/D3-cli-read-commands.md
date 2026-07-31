---
epic = "cli"
depends_on = ["D2-cli-login-broker-tokens"]
priority = 20
summary = "Add read-only Nomad, Vault and Consul commands to the localstack CLI, rendered with rich over the HTTP APIs. Live checks show the brokered deploy tokens cannot list Nomad jobs (403) and see only 2 of 25 Consul services, so the ticket scopes the surface to what those tokens can do and relays the gaps to D2."
tags = ["cli", "nomad", "vault", "consul"]
---

# D3 — Read-only `localstack` commands over Nomad, Vault and Consul

## Title
Add three typer groups (`nomad`, `vault`, `consul`) of read-only commands to
the `localstack` CLI, backed by a client layer D4's TUI can import, rendered
as rich tables with `--json` on every command. The commands consume the
tokens D2 obtains and add no auth logic of their own.

## Size / Effort
**Medium.** Eight small commands over three HTTP APIs is mechanical. The
effort is concentrated in two places:

- `vault grants` has to render a Vault-templated policy without hardcoding
  either the template's variable set or its current path count, because the
  live policy and the repo template already disagree (see Context).
- Two of the eight commands do not work with D2's brokered tokens as those
  tokens are scoped today. Establishing that, scoping around it, and
  relaying it to D2 is most of the thinking.

## Triggered by
Operator request: developer conveniences on top of the `localstack` CLI, so
that everyday cluster questions do not need three separate binaries and a
management token. D1 builds the package skeleton. D2 lands login and token
brokering. D3 is the first batch of commands that consume them.

## Context (verified live 2026-07-31 unless noted)

### There is no CLI yet
No `cli/` directory, no `pyproject.toml` at the repo root, and no `typer`
anywhere in tracked code. `requirements.txt:3,5` already list `httpx` and
`hvac`, which is the closest thing to prior art. D1 owns the package layout,
its dependency file, and its `justfile` recipes. D3 adds modules inside
whatever D1 built.

### The brokered Nomad token cannot list jobs. Verified, not assumed.
`deployments/infrastructure/nomad_deploy_role.tf:13-30` defines the `deploy`
Nomad ACL policy with `submit-job`, `read-job` and the five `host-volume-*`
capabilities. The comment at `:4-5` says out loud that `list-jobs` is
excluded on purpose. `deployments/infrastructure/nomad_deploy_role.tf:36-41`
is the `vault_nomad_secret_role` that mints `type = "client"` tokens
carrying that one policy.

Minted a token from `nomad/creds/deploy` (30m lease, revoked afterward) and
ran it against the live cluster:

| Call | Result with the brokered `deploy` token |
|---|---|
| `nomad job status` (list all) | **403 Permission denied** |
| `nomad job status hermes` | works, including deployment and allocations |
| `nomad job inspect hermes` | works |
| `nomad node status` | 403 Permission denied |
| `nomad job status doesnotexist` | 404 job not found |

`GET /v1/jobs` returns 403 for the deploy token and 200 for a management
token. The 404 on an unknown job matters: Nomad does not leak existence, so
"not found" and "not allowed" are distinguishable, which the error path can
rely on.

### The brokered Consul token silently under-reports the catalog
`bootstrap/playbooks/enable_consul_secrets.yml:39-58` creates the Consul
`deploy` policy. It grants `key_prefix "terraform/"` write, `session_prefix
"terraform/"` write, `service "minio"` read, `service "postgres-db"` read,
and `node_prefix ""` read. There is no `service_prefix`.
`deployments/infrastructure/consul_deploy_role.tf:19-25` is the Vault role
that references it by name with a 30m/60m TTL.

Live, against `http://192.168.2.30:8500`:

| Caller | `GET /v1/catalog/services` |
|---|---|
| no token at all | **200, all 25 services** |
| brokered `deploy` token | **200, exactly `minio` and `postgres-db`** |
| bogus token | 403 `ACL not found` |

Consul filters the catalog by ACL and returns 200 either way. A list command
that passes the brokered token gets a short answer with no error. The
anonymous policy on this cluster already exposes the full catalog, so the
restriction protects nothing here and only misleads the reader.

### `talat-consumer` and `talat-shim` exist in Nomad and nowhere else
Nomad reports **19 running jobs**. The repo holds 17 jobspecs: 11 under
`deployments/infrastructure/services/` and 6 under
`deployments/applications/services/`. `talat-shim` and `talat-consumer` have
no file in this repository. Further, `talat-consumer` does not register in
Consul either, so the Consul catalog is also not a complete job list. Any
command that enumerates jobs must call `GET /v1/jobs`.

### Vault mounts and policies, live
`vault secrets list`: `bootstrap/` (kv), `consul/`, `cubbyhole/`,
`identity/`, `nomad/`, `secret/` (kv v2), `sys/`.
`vault policy list`: `acme-tls-write`, `default`, `nomad-workloads`, `root`.
`vault auth list`: only `jwt-nomad/` (accessor `auth_jwt_649fd6cc`) and
`token/`. **There is no human-facing OIDC auth method on this Vault today**,
and F7, the ticket that would add one, is `blocked`.

### The templated policy, and why a naive print is worthless
`nomad-workloads` is a single policy shared by every workload, templated per
token. Live it reads:

```
path "secret/data/{{identity.entity.aliases.auth_jwt_649fd6cc.metadata.nomad_namespace}}/{{identity.entity.aliases.auth_jwt_649fd6cc.metadata.nomad_job_id}}/*"
```

Printing that tells a developer nothing about what `hermes` can reach. The
resolution is exact and cheap because only two variables appear:
`nomad_namespace` and `nomad_job_id`. Confirmed by reading a live entity
(`identity/entity/id/05c40bd9-...`): its alias on `auth_jwt_649fd6cc` is
named `memex` and carries `{"nomad_job_id": "memex", "nomad_namespace":
"default", "nomad_task": "memex", "role": "nomad-workloads"}`. So
substituting the namespace and the job id reproduces what Vault computes.

**Two shapes are in play right now and the command must survive both.**
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`
holds F9's narrowed **three** path blocks. Live Vault still serves the
pre-F9 **six** blocks, including `secret/metadata/*` list and
`bootstrap/data/*` read/create/update. F9 is `done` in the ledger and merged
in the template, and the Ansible run that applies it has not happened.
The accessor is not a constant either:
`bootstrap/roles/nomad_server/tasks/main.yml:253-255` derives
`auth_method_accessor` from `vault auth list` at bootstrap time, and
`:266-268` writes the rendered policy. Nothing may hardcode
`auth_jwt_649fd6cc` or a path count.

### Local binaries are a major version ahead of the servers
| Component | Server | Binary on PATH in the devcontainer |
|---|---|---|
| Nomad | 1.11.3 | 2.0.3 |
| Vault | 1.21.4 | 2.0.3 |
| Consul | 1.22.6 | 2.0.1 |

Separately, this devcontainer runs an `rtk` shim (`rtk 0.42.4`) that rewrites
shelled commands, so `subprocess` output is not guaranteed to be the
binary's own output. Both facts argue against shelling out.

### Auth failure codes, live
| API | no token | bad token | valid but under-scoped |
|---|---|---|---|
| Nomad | 403 `Permission denied` | 403 `Permission denied` | 403 |
| Vault | 403 | 403 (`permission denied` + `invalid token`) | 403 |
| Consul | 200, unfiltered | 403 `ACL not found` | 200, filtered |

Vault answers 403 for an invalid token and for an insufficient one alike.
`GET /v1/auth/token/lookup-self` separates them: it returns 200 for a live
token regardless of policy, and 403 for a dead one.

### The repo gate is green today
`just pre_commit` (`justfile:17-19`) passes on a clean tree. `check python
ast` and `debug statements (python)` currently report "no files to check"
and will start running once `cli/` exists (`.pre-commit-config.yaml:7,11`).
`.pre-commit-config.yaml:1` excludes only `.claude/` and `.loop/`, so `cli/`
is in scope. **There is no ruff, mypy or pytest hook in this repo today.**

## Non-goals / out of scope
- **No auth handling.** No token file reading, no login flow, no renewal, no
  address resolution from the environment. All of it comes from D2's
  interface. Gaps go to Open Questions as findings for D2, never into
  workarounds here.
- **No writes of any kind.** No `submit-job`, no restart, no stop, no
  scaling, no KV writes, no ACL changes.
- **Never print a secret value.** `vault kv` lists keys. Reading a value is
  out of scope for this ticket and is not a follow-up to sneak in.
- **No policy changes.** Widening the Nomad or Consul `deploy` policy is
  infrastructure work under a different owner (see Q1, Q2). D3 must not edit
  `nomad_deploy_role.tf`, `consul_deploy_role.tf` or
  `enable_consul_secrets.yml`.
- **No TUI.** D4 owns rendering beyond rich tables. D3's obligation is to
  leave a client layer D4 can import.
- **Not an ops console.** No logs, no exec, no alloc filesystem, no node or
  agent inspection, no metrics. The brokered token cannot do most of it
  anyway (`nomad node status` is 403).
- **No new Consul KV browsing.** The brokered token holds write on
  `key_prefix "terraform/"`, which is Terraform state. Nothing in this CLI
  reads it.
- **Does not resolve whether a specific token is authorized.** `vault
  grants` renders what a policy grants. The authoritative per-token answer
  is `sys/capabilities`, which needs the workload's own token.

## Requirements & restrictions

1. **Commands call the HTTP APIs with `httpx`. No `subprocess`.** Driven by
   the version drift table above and by the `rtk` shim. It also makes the
   default test suite offline via respx, which
   `.claude/rules/python-testing.md` names as the standard tool for `httpx`.
2. **Two layers, and the lower one imports neither typer nor rich.**
   `cli/localstack/api/` returns dataclasses. `cli/localstack/commands/`
   renders them. D4 imports `api/` and nothing else. This is the concrete
   reuse contract D4 depends on.
3. **Command surface, exactly these eight:**
   | Command | API call |
   |---|---|
   | `localstack nomad jobs` | `GET /v1/jobs` |
   | `localstack nomad job <id>` | `GET /v1/job/<id>` + `/v1/job/<id>/allocations` |
   | `localstack vault mounts` | `GET /v1/sys/mounts` |
   | `localstack vault policies` | `LIST /v1/sys/policies/acl` |
   | `localstack vault policy <name>` | `GET /v1/sys/policies/acl/<name>` |
   | `localstack vault grants <job>` | `GET /v1/sys/policies/acl/nomad-workloads`, rendered |
   | `localstack vault kv [path]` | `LIST /v1/secret/metadata/<path>`, keys only |
   | `localstack consul services` | `GET /v1/catalog/services` |
4. **`--json` on every command**, emitting the command's own dataclass, so
   the JSON never drifts from the table. Table is the default.
5. **`vault grants <job>` shows both columns: the raw template line and the
   resolved path**, plus capabilities. It must:
   - fetch the policy text at runtime and never embed a copy;
   - discover the accessor by regex over the fetched text
     (`identity\.entity\.aliases\.([^.]+)\.metadata\.(\w+)`), never
     hardcode `auth_jwt_649fd6cc`;
   - substitute `nomad_job_id` from the argument and `nomad_namespace` from
     a `--namespace` option defaulting to `default`;
   - leave any variable it cannot fill visible as `{{...}}` and mark that
     row, so a future template variable is never silently dropped;
   - work unchanged against the live six-block policy and F9's three-block
     policy;
   - print a one-line footer saying the view is rendered from policy text,
     not an authorization decision.
6. **`consul services` states that the result is ACL-filtered.** Given the
   verified 2-of-25 behavior, a bare table is a lie. Print a footer naming
   the token whose ACLs filtered the list and pointing at Q2's finding.
7. **One failure mode for a missing or dead token, on every command.** Catch
   D2's typed error, plus HTTP 403, and exit non-zero with a single message
   naming the affected service and telling the reader to run
   `localstack login`. Where the service allows it, separate "not logged in"
   from "not allowed":
   - Vault: call `GET /v1/auth/token/lookup-self`. 403 means expired, so say
     "run `localstack login`". 200 plus a 403 on the real call means the
     token lacks the grant, so name the path.
   - Nomad: 403 on `/v1/jobs` while `/v1/job/<known>` succeeds means the
     token lacks `list-jobs`. Say that, name the policy, do not say "login".
   - Consul: 403 means the token is bad, and a short list is a scope problem
     which requirement 6 covers.
8. **`.claude/rules/python-testing.md`: live-cluster tests carry a marker
   and are excluded from the default run.** Default `pytest` is offline.
9. **`.claude/rules/uv-installer.md`: dependencies land via `uv add`**, never
   `uv pip`.
10. **`.claude/rules/prek-code-quality.md`: go through the task runner.** The
    gate is `just pre_commit`, plus whatever Python gate D1 established.
11. **`.claude/rules/plain-language.md` applies to help text and error
    messages**, which are user-facing surfaces.
12. **`.claude/rules/adversarial-reviews.md`: adversarial review before
    done.**

## Code surface

New, all under the package D1 creates. Paths assume `cli/localstack/`; if
D1 chose a different root, keep the shape and change the prefix.

- `cli/localstack/api/nomad.py`: new. `list_jobs()`, `get_job(job_id)`
  returning dataclasses. Maps 403 on `/v1/jobs` to a missing-`list-jobs`
  error, and 404 to job-not-found.
- `cli/localstack/api/vault.py`: new. `list_mounts()`, `list_policies()`,
  `read_policy(name)`, `list_kv_keys(path)`, `token_is_live()` wrapping
  `auth/token/lookup-self`.
- `cli/localstack/api/grants.py`: new. Parses policy HCL into
  `(path, capabilities)` pairs, extracts the accessor and variable names by
  regex, substitutes `nomad_namespace` and `nomad_job_id`, and reports
  unresolved variables. The one piece of real logic in the ticket.
- `cli/localstack/api/consul.py`: new. `list_services()`.
- `cli/localstack/api/errors.py`: new. `NotAuthenticated`,
  `MissingCapability`, `NotFound`, each carrying the service name.
- `cli/localstack/commands/nomad.py`: new. Typer group `nomad`, commands
  `jobs` and `job`.
- `cli/localstack/commands/vault.py`: new. Typer group `vault`, commands
  `mounts`, `policies`, `policy`, `grants`, `kv`.
- `cli/localstack/commands/consul.py`: new. Typer group `consul`, command
  `services`, with the ACL-filter footer.
- `cli/localstack/commands/render.py`: new. Shared table rendering and the
  `--json` path.
- The CLI entrypoint D1 created: modified. Register the three groups. D1
  owns the file, and D3 adds three `add_typer` calls.
- The CLI's dependency file D1 created: modified. Add `httpx`, `rich`,
  `typer` if D1 did not, and `respx` plus `pytest` as dev dependencies, all
  via `uv add`.

Tests, all new:

- `cli/tests/conftest.py`: respx fixture, fake token fixture standing in
  for D2's interface.
- `cli/tests/fixtures/policies.py`: the two `nomad-workloads` texts,
  verbatim: the live six-block form and F9's three-block form.
- `cli/tests/api/test_nomad.py`
- `cli/tests/api/test_vault.py`
- `cli/tests/api/test_grants.py`
- `cli/tests/api/test_consul.py`
- `cli/tests/commands/test_render.py`
- `cli/tests/commands/test_auth_failure.py`
- `cli/tests/cluster/test_live.py`: marked, excluded by default.

Read-only, do not edit, but read them:

- `deployments/infrastructure/nomad_deploy_role.tf:13-30`: the capability
  set the Nomad commands must live within.
- `bootstrap/playbooks/enable_consul_secrets.yml:39-58`: the Consul ACL
  rules that filter the catalog.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`
  holds F9's three-block shape, one of the two the grants renderer handles.
- `bootstrap/roles/nomad_server/tasks/main.yml:253-255`: proof the accessor
  is derived at bootstrap, so it cannot be a constant.
- `deployments/applications/services.tf:1-9`: the two Consul services the
  brokered token can read, and the only two Terraform looks up.

## Tests & validation gates

### Repo gate (verified green on a clean tree today)
- `just pre_commit` (`justfile:17-19`). Adding `cli/` activates `check
  python ast` and `debug statements (python)`
  (`.pre-commit-config.yaml:7,11`), which currently skip for want of Python
  files. Both must pass.
- Worktree prerequisite: `just worktree_setup <path>` (`justfile:29-31`), or
  `terraform-validate` fails on the missing tfvars.

### Python gate
The repo has **no ruff, mypy or pytest hook** today. D1 owns establishing
one. D3 runs whatever D1 landed. If D1 landed none, raise it as a finding
for D1 under `.claude/rules/pre-existing-issues.md` rather than inventing a
gate mid-ticket.

Default suite is offline and must stay so:
`uv run pytest` from the CLI package root.

### Tests to add
Offline, respx-backed, in the files listed in the code surface:

1. `test_grants.py::test_resolves_live_six_block_policy`: feed the verbatim
   live text, assert `secret/data/default/hermes/*` appears resolved with
   `["read"]`.
2. `test_grants.py::test_resolves_f9_three_block_policy`: same input job,
   feed F9's three-block text, assert the three rows resolve and the removed
   `bootstrap/data/*` row is absent. **These two together are the anti-
   hardcoding gate.**
3. `test_grants.py::test_accessor_is_discovered_not_hardcoded`: rewrite the
   accessor in the fixture to `auth_jwt_deadbeef`, assert resolution still
   works.
4. `test_grants.py::test_unknown_variable_is_marked_not_dropped`: inject a
   third variable, assert the row survives and is flagged unresolved.
5. `test_grants.py::test_namespace_option_changes_resolution`.
6. `test_nomad.py::test_list_jobs_403_reports_missing_list_jobs`: a
   reproducing test for the verified live failure. Assert the message names
   `list-jobs` and does **not** say "run `localstack login`".
7. `test_nomad.py::test_job_404_reports_not_found`.
8. `test_nomad.py::test_list_jobs_parses_nineteen_job_payload`.
9. `test_consul.py::test_services_footer_states_acl_filtering`: assert the
   footer renders when the payload is short.
10. `test_vault.py::test_lookup_self_403_maps_to_not_authenticated`.
11. `test_vault.py::test_lookup_self_200_plus_403_maps_to_missing_grant`.
12. `test_vault.py::test_kv_lists_keys_and_never_requests_a_value`: assert
    no `/v1/secret/data/` call is issued. Use `assert
    respx_mock["data"].call_count == 0`, not a bare `assert_not_called`,
    per the python-testing rule.
13. `test_auth_failure.py::test_every_command_exits_nonzero_without_a_token`
   : parametrized across all eight commands. This is the requirement-7
    gate.
14. `test_render.py::test_json_flag_matches_table_source`: parametrized,
    asserts `--json` serializes the same dataclass the table renders.

Marked live tests in `cli/tests/cluster/test_live.py`, excluded from the
default run via `addopts`:

15. `test_live.py::test_nineteen_jobs_from_the_api`: guards the
    `talat-shim` / `talat-consumer` trap. Asserts both appear, so a future
    implementation that reads `deployments/` fails here.
16. `test_live.py::test_vault_mounts_include_the_seven_known_paths`.
17. `test_live.py::test_grants_resolves_against_whatever_vault_serves` —
    fetches the real policy, resolves for a real job, asserts no unresolved
    variables remain. Passes before and after F9's apply.

## Risk assessment

- **Blast radius: small and one-directional.** Every call is a GET or a
  LIST. Nothing in this ticket can change cluster state. A bug produces a
  wrong screen, not a wrong cluster.
- **Reversibility: total.** Delete the modules and the three `add_typer`
  calls.
- **Likeliest failure mode: a command that lies quietly.** `consul services`
  returning 2 of 25 with a 200 is the verified case, and a naive `vault
  grants` that prints the template is the second. Both fail by looking
  correct. Requirements 5, 6 and tests 1 to 4 and 9 exist for this.
- **Second likeliest: enumerating jobs from `deployments/`** because
  `/v1/jobs` 403s under the brokered token. That silently drops `talat-shim`
  and `talat-consumer`. Test 15 catches it, but only when the marked suite
  runs, so the reviewer must check the source of the job list by eye.
- **Third: printing a secret.** `vault kv` is one wrong path away from
  `/v1/secret/data/`. Test 12 asserts the call is never made.
- **Dependency risk, real and current.** D3 depends on D2, and D2's own
  ground is soft: there is no human OIDC auth method on this Vault, and F7,
  which would add one, is `blocked` on an unresolved fork. If D2 ships with
  a placeholder for the human Vault credential, the four `vault` commands
  are untestable against the cluster. The offline suite still runs, so D3
  is implementable, and subticket 1 must confirm D2's interface exists
  before any command is written.
- **Grants rendering can drift from Vault's own substitution.** The lexical
  render is exact for the two variables in use today, and it is an
  approximation in principle. The footer in requirement 5 is what keeps it
  honest. Test 4 keeps it from degrading silently.
- **Both policies are moving.** F9's apply changes `nomad-workloads` from
  six blocks to three. Tests 1 and 2 pin both. Q1 and Q2 may change the
  Nomad and Consul `deploy` policies, which would widen what the commands
  can see without breaking them.

## Subtickets (ordered)

1. **Confirm D2's interface before writing anything.** Establish the exact
   call that returns Vault, Nomad and Consul tokens plus their addresses,
   and the typed errors it raises. Relay any gap to D2 with the
   `relay-finding` skill. Do not build around a missing piece.
2. **Settle Q1 and Q2 with the operator.** Both change what `nomad jobs` and
   `consul services` can show. Building either command first risks
   rewriting it.
3. **Client layer:** `api/errors.py`, then `api/nomad.py`, `api/vault.py`,
   `api/consul.py`. Tests 6 to 12 alongside. No typer, no rich in these
   files.
4. **`api/grants.py` and tests 1 to 5.** Write the two policy fixtures from
   the verbatim texts first, then the resolver. This is the ticket's real
   work, so give it its own commit.
5. **Command layer and `render.py`,** including `--json`. Tests 13 and 14.
6. **The two honesty footers** (requirements 5 and 6) and the unified auth
   failure message (requirement 7).
7. **Marked live suite** (tests 15 to 17), plus the `addopts` exclusion.
   Confirm `uv run pytest` stays offline and that `-m <marker>` reaches the
   cluster.
8. **Gates:** `just pre_commit` and D1's Python gate, both green.
9. **Adversarial review** per `.claude/rules/adversarial-reviews.md`. Brief
   the reviewer specifically on the two quiet-lie failure modes and on the
   job-list source.

## Open questions

**Q1: The brokered Nomad token cannot list jobs. Who fixes it, and how?**
Verified live: `GET /v1/jobs` returns 403 because
`nomad_deploy_role.tf:13-30` deliberately withholds `list-jobs`. Options:

  a. Add `list-jobs` to the `deploy` policy. Cheapest, and it blurs a policy
     whose comment states least privilege for the deployer as its purpose.
  b. Add a separate `read` Nomad ACL policy plus a `nomad/creds/read` Vault
     role, and have D2 broker both.
  c. Drop `localstack nomad jobs` and ship only `nomad job <id>`.
  d. Read the job list from `deployments/**/services/*.hcl`.

  *Recommendation: (b), owned by D2 or a new infrastructure ticket, not by
  D3.* A read CLI and a Terraform deployer are different roles and should
  not share a token. Reject (d) outright: it misses `talat-shim` and
  `talat-consumer`, both verified running with no file in this repo.
  Meanwhile D3 ships `nomad jobs` as specified, working under any token
  holding `list-jobs` and failing with the precise message in requirement 7
  otherwise. That keeps D3 unblocked either way.

**Q2: Should the Consul `deploy` policy get `service_prefix "" { policy =
"read" }`?** Verified: the brokered token sees 2 of 25 services, while an
anonymous caller sees all 25 with a 200. So the restriction hides nothing
from anyone and only truncates the CLI's answer.

  *Recommendation: yes, add it, as a finding relayed to D2 or to a small
  infrastructure ticket that edits
  `bootstrap/playbooks/enable_consul_secrets.yml:39-58`.* It grants no
  visibility the anonymous policy does not already give. D3 must not make
  that edit. Until it lands, requirement 6's footer keeps the short list
  honest. Do not "fix" this by dropping the token, which would work today
  and would break the moment the anonymous policy tightens.

**Q3: Does `vault grants <job>` show the raw policy, the resolved paths, or
both?**
  *Recommendation: both, side by side, resolved by lexical substitution.*
  Raw alone is what the operator correctly called near-useless. Resolved
  alone hides that the grant is templated and shared, which is the fact a
  developer most needs when they wonder why another job cannot read their
  secret. Two columns cost nothing and teach the mechanism. Lexical
  substitution is exact here because only `nomad_namespace` and
  `nomad_job_id` appear, confirmed against a live entity alias.

**Q4: Should `grants` instead read the job's real entity alias metadata?**
Verified possible: the alias on `auth_jwt_649fd6cc` is named for the job and
carries `nomad_job_id`, `nomad_namespace` and `nomad_task`. It would be
exact rather than approximate.
  *Recommendation: no, not in this ticket.* It needs `identity/entity/id/*`
  read or `identity/lookup/entity` write, which a scoped human policy is
  unlikely to grant. It also only works for jobs that have already logged
  in, so it would fail on exactly the new job someone is debugging. Revisit
  if a template variable appears that lexical substitution cannot fill,
  which test 4 will detect.

**Q5: Do the four `vault` commands survive F7's future `deployer` policy?**
They need `sys/mounts` read, `sys/policies/acl` list, `sys/policies/acl/<n>`
read, and `secret/metadata/*` list. F7 is `blocked` with the recorded reason
that its deployer policy "forbids the `sys/*` and `auth/*` writes its own
terraform apply performs". So the policy that will govern a human Vault
token is unsettled and currently leans away from `sys/*`.
  *Recommendation: relay those four paths to F7 and D2 as required read
  grants, and have D3 depend on nothing more than them.* Do not widen a
  policy from this ticket. Test 11 makes the failure legible if the grant is
  absent.

**Q6: What is the live-test marker called?**
  *Recommendation: `cluster`, declared in the package's `markers` and
  excluded via `addopts = "-m 'not cluster'"`.* If D1 already chose a name,
  use D1's rather than adding a second marker. The repo rule's own examples
  use `integration`, which reads as "any external system"; these tests need
  this specific cluster reachable, and the name should say so.

**Q7: Is `localstack vault kv` in scope at all?** The operator asked to
"list Vault secrets", which maps to `vault secrets list` (mounts) in the
cited facts and to KV keys in everyday use.
  *Recommendation: ship both `vault mounts` and `vault kv`, keys only.*
  `secret/default/` lists 18 job prefixes live, including `gemini` and
  `openfang`, which correspond to no running job. That is a genuinely useful
  view. Values stay out under the hard non-goal, and test 12 enforces it.

## Scope revised, 2026-07-31

The operator settled the CLI's command surface and this ticket lost most of
it. The governing rule: **the cockpit does what no native CLI can. It does not
restate what `vault kv list` and `nomad job status` already do.**

### Cut

`nomad jobs`, `nomad job <id>`, `vault mounts`, `vault policies`,
`vault policy <name>`, `vault kv [path]`, `consul services`.

Every one is a native command under a new name. They cost a second surface to
maintain, they lag the tool they mirror, and they add nothing a developer with
the real CLI on PATH cannot already do. The `deps` ticket puts those CLIs on
PATH, so the mirrors are not even a fallback.

### Kept and added

| Command | Why it survives the rule |
| --- | --- |
| `status` | Vault seal state, Nomad nodes and allocations, Consul checks in one view. No single tool spans all three |
| `service [<name>] [--open]` | Joins the Nomad job, its Consul health check, and the haproxy hostname. The URL lives in `services/haproxy.hcl`, which neither Nomad nor Consul can see |
| `secret <service>` | Which KV2 paths a job's `template` stanzas read, and whether each exists. Vault cannot say which job wants a path; Nomad cannot say whether it is there |
| `vault grants <job>` | Already in scope and already synthesis: resolves the `nomad-workloads` policy template against a job. Unchanged |

`service --open` absorbs the `localstack ui consul` command locked earlier in
D2 §12. One verb, not two. Consul is the service that needs a token pasted,
so `service consul --open` prints the brokered token alongside the URL; that
is a per-service quirk, not its own command.

### What did not change

The `api/` and `commands/` split, the no-subprocess rule, the offline test
suite, the read-only guardrail, and every `vault grants` correctness
requirement stand as written. They were never about which commands exist.

`status` here is the one-shot, scriptable renderer. D4 owns the live Textual
view and is renamed `localstack monitor` to match. Both read the same `api/`
layer, which is what this ticket's reuse-contract row already required.

### Consequences

- **The eval marker's signature was cleared.** It was signed against the
  eight-command scope on the same day the scope changed. Re-sign before
  implementing.
- **The D2 read-role finding matters more, not less.** This ticket previously
  worked around the brokered `deploy` token's limits by scoping its surface to
  what that token could reach. `status` and `service` both want data the token
  is denied: `GET /v1/jobs` returns 403, and Consul's catalog silently filters
  to 2 of 25 services. The commands must report that rather than render a
  confident, wrong table, which is what the ACL-footer and the
  not-allowed-versus-not-logged-in rows now enforce.
- **Re-read this ticket after `G2-nomad-ui-oidc-login` lands.** G2 gives a
  human a `developer`-scoped Nomad token, which can list jobs. That does not
  widen this ticket's scope by itself, but it changes which of these rows are
  exercising a real constraint and which are exercising a stale one.
