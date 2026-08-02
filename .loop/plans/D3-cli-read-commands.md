---
epic = "cli"
depends_on = ["D1-cli-package-skeleton", "D2-cli-login-broker-tokens"]
priority = 20
summary = "Add four read-only synthesis commands to the localstack CLI (status, service, secret, vault grants), each answering a question no single native CLI can. All data comes from the Nomad, Vault and Consul HTTP APIs, never from the repo tree. Two of the four need Vault read grants the brokered human token does not hold today; F7 owns that policy and this ticket states it as a precondition rather than widening anything itself."
tags = ["cli", "nomad", "vault", "consul", "haproxy"]
---

# D3 — Four read-only synthesis commands for `localstack`

## Title
Add `status`, `service [<name>] [--open]`, `secret <service>` and
`vault grants <job>` to the `localstack` CLI, backed by a client layer D4's
TUI can import, rendered as rich tables with `--json` on every command. Each
command joins data across Vault, Nomad, Consul and the haproxy edge. The
commands consume the tokens D2 obtains and add no auth logic of their own.

## Size / Effort
**Medium to large.** Four commands, but only one of them is mechanical. The
effort is concentrated in three places:

- `service` is a three-way join over sources that share no key. The haproxy
  routing table, the Nomad job list and the Consul catalog line up on 6 of 10
  routes and disagree on the rest. Specifying and rendering that disagreement
  honestly is the command's whole value.
- `vault grants` has to render a Vault-templated policy without hardcoding
  either the template's variable set or its current path count. The policy has
  already changed shape once (F9 took it from six path blocks to three).
- Two of the four commands cannot read their own inputs with the credential
  D2 brokers today. Establishing that, scoping around it, and relaying it is
  most of the remaining thinking. See Preconditions.

## Triggered by
Operator request: developer conveniences on top of the `localstack` CLI, so
that everyday cluster questions do not need three separate binaries and a
management token. Narrowed by the operator on 2026-07-31 to a governing rule:
**the cockpit does what no native CLI can. It does not restate what
`vault kv list` and `nomad job status` already do.** Seven mirror commands
were cut under that rule and three synthesis commands replaced them.

D1 builds the package skeleton and the Python gates. D2 lands login and token
brokering. D3 is the first batch of commands that consume them.

## Context (verified live 2026-07-31 unless noted)

### There is no CLI yet
No `cli/` directory, no `pyproject.toml` at the repo root, and no `typer`
anywhere in tracked code. `requirements.txt:3,5` already list `httpx` and
`hvac`, which is the closest thing to prior art. D1 owns the package layout
(`cli/src/localstack_cli/`, src layout, its own `cli/pyproject.toml`, per its
code surface in `.loop/plans/D1-cli-package-skeleton.md`), the dependency
file, the
`cluster` pytest marker, and the ruff/mypy/pytest pre-commit hooks. D3 adds
modules inside what D1 built and uses the paths D1 chose.

### Preconditions: the brokered credentials cannot read two of these commands' inputs
This is the ticket's most dangerous assumption and it is false as stated in
earlier drafts. Write it down before anything else.

`deployments/infrastructure/auth_userpass.tf:24-36` writes the operator
userpass account with `token_policies = []`, deliberately: "this account
exists to obtain an identity, not standing privilege." So a human token from
`localstack login` carries `default` and nothing else. Live `default` grants
neither `sys/policies/acl/*` nor `secret/metadata/*`; its path list is
self-lookup, cubbyhole, wrapping and renew only.

`deployments/infrastructure/nomad_deploy_role.tf:13-30` grants the brokered
Nomad token `submit-job`, `read-job` and five `host-volume-*` capabilities,
with no `list-jobs` and no `node` read. The comment at `:4-5` says the
omission is deliberate.

What each command actually renders against the cluster as it stands today:

| Command | Live outcome with D2's brokered credentials |
|---|---|
| `vault grants <job>` | **Dead.** `GET /v1/sys/policies/acl/nomad-workloads` is denied, and that call is the command's only input |
| `secret <service>` | **Half dead.** The Nomad jobspec read works under `read-job`; every `secret/metadata/<path>` existence check is denied |
| `status` | **Partial.** Vault seal state works (`sys/health` is unauthenticated: 200 with no token). Nomad nodes and jobs are 403. Consul health is filtered to 2 of 25 services |
| `service` | **Partial.** `GET /v1/job/<id>` works; `GET /v1/jobs` is 403, so the unrouted-job half of the join is empty. Consul health filtered to 2 of 25 |

**The grants this ticket needs, and who owns them:**

| Grant | Needed by | Owner |
|---|---|---|
| Vault `sys/policies/acl/nomad-workloads` read | `vault grants` | **F7** (the human Vault policy) |
| Vault `secret/metadata/*` read | `secret <service>` | **F7** |
| Nomad `list-jobs` plus `node` read | `status`, `service` | D4's conditional `nomad_read_role.tf`, or G2. See Q1 |

F7 is `blocked` in the ledger with `unresolved-design-fork`. **F7 is a stated
precondition, not a `depends_on` edge**, because adding the edge would park
D3 behind a blocked ticket while two of its four commands are implementable
and testable offline today. The fork this creates is Q2, and it is an
operator call, not something this ticket may absorb into a footnote.

D3 must not widen any policy. Relaying these three grants to F7, D2 and D4 is
subticket 1.

### The haproxy routing table is in the Nomad API, not in the repo
An earlier draft had `service` parse
`deployments/infrastructure/services/haproxy.hcl`. That is wrong twice.

**The repo file is not a jobspec.** It is a Terraform `templatefile` input
wired at `deployments/infrastructure/services.tf:318-323`, with
`${tls_secret}` at `:64`, `${openfang_password}` at `:89` and
`$${attr.unique.hostname}` at `:7`. It does not parse as HCL, and the routing
block lives inside a heredoc. Anything reading it parses an unrendered
template.

**Nomad serves the rendered config.** `GET /v1/job/haproxy` returns
`TaskGroups[].Tasks[].Templates[]`; the entry whose `DestPath` is
`local/haproxy.cfg` carries `EmbeddedTmpl`, 2327 bytes, containing the
`acl is_minio hdr(host) -i minio.lab.orangecluster.nl` lines verbatim.
Probed live with a management token.

This also aligns D3 with D4, whose `talat-*` trap bullet says the panel
"reads the **API**, never the repo tree"
(`.loop/plans/D4-cli-cluster-tui.md`).

### That jobspec carries a live password
`deployments/infrastructure/services.tf:322` interpolates
`random_password.openfang_basic_auth.result` into the template. Probed live:
the running job's `EmbeddedTmpl` contains
`user admin insecure-password <24-char literal>`, the real value, not a
placeholder. Any implementation of `service` that fetches the haproxy job
holds a live credential in memory, and one `--json` dump or one stack trace
prints it. Requirement 8 is the guardrail.

### The three-way join does not line up, and that is the point
Live counts: **10 routed hostnames, 19 Nomad jobs, 25 Consul services.**
The haproxy backends address servers by literal IP and port
(`server memex1 192.168.2.46:8000`), never by Consul service name or Nomad
job id, so there is no shared key. The route table, resolved live:

| Route | Hostname | haproxy backend | Nomad job | Consul service |
|---|---|---|---|---|
| `minio` | `minio.lab.orangecluster.nl` | `192.168.2.29:9001` | `minio` | `minio`, `minio-console` |
| `s3` | `s3.lab.orangecluster.nl` | `192.168.2.29:9000` | **none** | **none by that name** |
| `vault` | `vault.lab.orangecluster.nl` | `192.168.2.30:8200` | **none** | `vault` |
| `nomad` | `nomad.lab.orangecluster.nl` | `192.168.2.30:4646` | **none** | `nomad` |
| `consul` | `consul.lab.orangecluster.nl` | `192.168.2.30:8500` | **none** | `consul` |
| `phoenix` | `phoenix.lab.orangecluster.nl` | `192.168.2.29:6006` | `phoenix` | `phoenix`, `phoenix-grpc` |
| `memex` | `memex.lab.orangecluster.nl` | `192.168.2.46:8000` | `memex` | `memex` |
| `grafana` | `grafana.lab.orangecluster.nl` | `192.168.2.47:3000` | `grafana` | `grafana` |
| `mlflow` | `mlflow.lab.orangecluster.nl` | `192.168.2.50:5050` | `mlflow` | `mlflow` |
| `bifrost` | `bifrost.lab.orangecluster.nl` | `192.168.2.50:8080` | `bifrost` | `bifrost` |

Thirteen live jobs carry no edge route at all: `acme`, `backup-minio`,
`backup-postgres`, `haproxy`, `hermes`, `loki`, `nats`, `node-exporter`,
`postgres`, `prometheus`, `promtail`, `talat-consumer`, `talat-shim`.
Requirement 5 states the join rule that renders all of this.

### `talat-consumer` and `talat-shim` exist in Nomad and nowhere else
Nomad reports **19 running jobs**. The repo holds 17 jobspecs: 11 under
`deployments/infrastructure/services/` and 6 under
`deployments/applications/services/`. `talat-shim` and `talat-consumer` have
no file in this repository. `talat-consumer` does not register in Consul
either, so the Consul catalog is not a complete job list. Any command that
enumerates jobs must call `GET /v1/jobs`.

### Every Vault reference in every live jobspec is a static literal
This is what makes `secret <service>` possible, and it was never written
down. Probed all 19 live jobs: every Vault reference inside every
`EmbeddedTmpl` is a literal path, in the shape
`{{ with secret "secret/data/default/hermes/github" }}`, with **zero**
computed `secret (...)` calls anywhere in the fleet. Sample counts: `hermes`
7 paths, `bifrost` 6, `memex` 4 distinct, `talat-shim` 1. A regex over the
template text therefore answers "which KV2 paths does this job read".

Existence is checkable without reading a value:
`GET /v1/secret/metadata/default/memex/postgres` returns **200** with
`created_time`, `current_version` and `versions`, and **no `data` field**.
A missing path returns **404**. Both probed live. The command never needs to
touch `/v1/secret/data/`, which is requirement 9's guardrail.

Regex extraction is exact only while the fleet stays literal. Requirement 6
makes an unparseable or computed reference render as unknown rather than be
dropped.

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

Consul filters by ACL and returns 200 either way. Any view carrying Consul
data gets a short answer with no error. Requirement 7 is the footer that
keeps it honest.

### Vault mounts, auth methods and policies, live
`vault secrets list`: `bootstrap/` (kv), `consul/`, `cubbyhole/`,
`identity/`, `nomad/`, `secret/` (kv v2), `sys/`.
`vault policy list`: `acme-tls-write`, `default`, `default-ceiling`,
`nomad-workloads`, `root`.
`vault auth list`: `jwt-nomad/` (accessor `auth_jwt_649fd6cc`), `token/`
and **`userpass/`**.

`userpass/` is live, created by `deployments/infrastructure/auth_userpass.tf:13-15`,
with the operator user at `:29` and the identity alias at `:48-54`. D2
settled the human login on userpass, under "How this ticket informs F7's
replan", point 1: "The login method is `userpass`, not OIDC. Operator
decision" (`.loop/plans/D2-cli-login-broker-tokens.md`). So the question of
*how* a human authenticates is closed. What remains open is only *what the
resulting token may read*, which is the Preconditions table above.

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
"default", "nomad_task": "memex", "role": "nomad-workloads"}`. Substituting
the namespace and the job id reproduces what Vault computes.

**Live Vault serves three path blocks.** F9 is applied
(`tmp/HANDOFF-2026-07-31.md:43-52`: "The live `nomad-workloads` policy went
from 6 path blocks to 3"), and re-probed today: `GET
/v1/sys/policies/acl/nomad-workloads` returns `data.policy` with exactly
three `path` blocks, matching
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`.
The removed blocks were unscoped `secret/metadata/*` list and
`bootstrap/data/*` plus `bootstrap/metadata/*`.

The renderer must still handle both shapes, and not because a switchover is
coming. This policy has already changed block count once, and code that
hardcodes a count breaks the next time it is narrowed or widened. The
accessor is not a constant either:
`bootstrap/roles/nomad_server/tasks/main.yml:253-255` derives
`auth_method_accessor` from `vault auth list` at bootstrap time, and
`:265-268` writes the rendered policy. Nothing may hardcode
`auth_jwt_649fd6cc` or a path count.

### Server versions, live
Corrected. An earlier draft had all six numbers wrong with the direction
inverted. `tmp/HANDOFF-2026-07-31.md:11-12` records the 2.x upgrade landing
on all five nodes on 2026-07-31.

| Component | Live server | Binary on PATH in the devcontainer |
|---|---|---|
| Nomad | **2.0.4** (`/v1/agent/self`) | 2.0.3 |
| Vault | **2.0.3** (`/v1/sys/health`) | 2.0.3 |
| Consul | **2.0.2** (`/v1/agent/self`) | 2.0.1 |

The servers are level with or **ahead of** the local binaries, not behind
them. Version drift is therefore no longer the argument against shelling
out. Two arguments remain and they are enough: this devcontainer runs an
`rtk` shim (`rtk 0.42.4`) that rewrites shelled commands, so `subprocess`
output is not guaranteed to be the binary's own output; and D6 puts more
shims on PATH. HTTP plus respx also gives an offline default test suite,
which `.claude/rules/python-testing.md` requires.

### N4 reshapes where these commands point
`N4-netsec-edge-only-service-access` is in `planning` and changes three
things D3 touches:

1. It closes direct LAN access to Nomad, Vault, Consul and MinIO, making
   `https://<name>.lab.orangecluster.nl` the only route in. Its "Measured
   exposure" table shows the edge already answers for all of them today
   (`.loop/plans/N4-netsec-edge-only-service-access.md`); the closure itself
   is N4's requirement R8. The URL column `service` renders is exactly that
   hostname, so N4 strengthens the command rather than changing it.
2. It moves this repo's own addresses onto the edge, including
   `.devcontainer/.env`'s `VAULT_ADDR`, `NOMAD_ADDR` and `CONSUL_HTTP_ADDR`
   (N4 § "What this repo points at today" for the current values, and N4's
   requirement R6, "This repo's own addresses move to the edge in the same
   change"). **Cited by section and quote, not by line: N4 is under active
   edit and its line numbers move.** D3 must take all
   three addresses from D1's `config.py` and
   hardcode no IP, host or port anywhere, so N4 is a config change and not a
   D3 change. Requirement 2 states this.
3. It may edit `haproxy.hcl` to close or authenticate the stats page on 8404
   (its code surface lists `deployments/infrastructure/services/haproxy.hcl`
   as a possible edit "for 8404"). Two consequences: `service` must never read the stats page for
   routing data, and its `EmbeddedTmpl` parser must not depend on byte
   offsets, line numbers or the current backend count. Test 9 pins that.

### Auth failure codes, live
| API | no token | bad token | valid but under-scoped |
|---|---|---|---|
| Nomad | 403 `Permission denied` | 403 `Permission denied` | 403 |
| Vault | 403 | 403 (`permission denied` + `invalid token`) | 403 |
| Consul | 200, unfiltered | 403 `ACL not found` | 200, filtered |

Vault answers 403 for an invalid token and for an insufficient one alike.
`GET /v1/auth/token/lookup-self` separates them: it returns 200 for a live
token regardless of policy, and 403 for a dead one. Nomad returns 404 for an
unknown job under a token that may read jobs, so "not found" and "not
allowed" stay distinguishable there too.

### The repo gate is green today
`just pre_commit` (`justfile:17-19`) passes on a clean tree. `check python
ast` and `debug statements (python)` currently report "no files to check"
and will start running once `cli/` exists (`.pre-commit-config.yaml:7,11`).
`.pre-commit-config.yaml:1` excludes only `.claude/` and `.loop/`, so `cli/`
is in scope. **There is no ruff, mypy or pytest hook in this repo today.**
D1 adds all three as local hooks scoped `files: '^cli/'`
(`.loop/plans/D1-cli-package-skeleton.md`, "The three hooks to add"), which
is why D3 now carries an explicit `depends_on` edge to D1. D3 runs those hooks; it does
not author them.

## Non-goals / out of scope
- **No mirror of a native CLI.** The seven commands cut on 2026-07-31
  (`nomad jobs`, `nomad job <id>`, `vault mounts`, `vault policies`,
  `vault policy <name>`, `vault kv [path]`, `consul services`) stay cut. Each
  was a native command under a new name, costing a second surface to
  maintain. D6 puts the real CLIs on PATH, so the mirrors are not a fallback
  either. Re-adding any of them is scope creep.
- **No auth handling.** No token file reading, no login flow, no renewal, no
  address resolution from the environment. All of it comes from D2's
  interface. Gaps go to Open Questions as findings for D2, never into
  workarounds here.
- **No writes of any kind.** No `submit-job`, no restart, no stop, no
  scaling, no KV writes, no ACL changes.
- **Never print a secret value.** `secret <service>` prints paths and a
  present, missing or denied marker (requirement 6's three states). Reading a
  KV2 value is out of scope and is not a
  follow-up to sneak in. Neither is any other field of the haproxy jobspec.
- **No policy changes.** Widening the Nomad or Consul `deploy` policy, or
  the human Vault policy, is infrastructure work under a different owner
  (Preconditions, Q1, Q3). D3 must not edit `nomad_deploy_role.tf`,
  `consul_deploy_role.tf`, `auth_userpass.tf` or
  `enable_consul_secrets.yml`, and must not author `nomad_read_role.tf`.
- **No TUI.** D4 owns the live Textual view, renamed `localstack monitor`.
  D3's `status` is the one-shot, scriptable renderer. D3's obligation is to
  leave a client layer D4 can import.
- **Not an ops console.** No logs, no exec, no alloc filesystem browsing, no
  metrics scraping.
- **No Consul KV browsing.** The brokered token holds write on
  `key_prefix "terraform/"`, which is Terraform state. Nothing here reads it.
- **`service` does not row-key on Consul.** Consul registers 25 services,
  many of them a second port of one job (`minio-console`, `phoenix-grpc`,
  `nats-monitor`, `nats-exporter`, `postgres-exporter`, `haproxy-stats`,
  `nomad-client`). Making them rows would triple-count. Consul is a column.
- **Does not resolve whether a specific token is authorized.** `vault
  grants` renders what a policy grants. The authoritative per-token answer
  is `sys/capabilities`, which needs the workload's own token.

## Requirements & restrictions

1. **Commands call the HTTP APIs with `httpx`. No `subprocess`.** Driven by
   the `rtk` shim and by D6's shims, and it makes the default suite offline
   via respx, which `.claude/rules/python-testing.md` names as the standard
   tool for `httpx`.
2. **Two layers, and the lower one imports neither typer nor rich.**
   `cli/src/localstack_cli/api/` returns dataclasses.
   `cli/src/localstack_cli/commands/` renders them. D4 imports `api/` and
   nothing else. This is the concrete reuse contract D4 depends on. The
   `api/` layer takes its three addresses from D1's `config.py` and contains
   no literal IP, hostname or port, so N4's address move does not touch it.
3. **Command surface, exactly these four:**
   | Command | API calls |
   |---|---|
   | `localstack status` | `GET /v1/sys/health` (Vault, no token needed); `GET /v1/nodes` and `GET /v1/jobs` (Nomad); `GET /v1/health/state/any` (Consul) |
   | `localstack service [<name>] [--open]` | `GET /v1/job/haproxy` (routes, from `Templates[].EmbeddedTmpl`); `GET /v1/jobs` and `GET /v1/job/<id>` (Nomad); `GET /v1/health/state/any` (Consul) |
   | `localstack secret <service>` | `GET /v1/job/<service>` (Nomad); `GET /v1/secret/metadata/<path>` per referenced path (Vault) |
   | `localstack vault grants <job>` | `GET /v1/sys/policies/acl/nomad-workloads`, rendered |

   Two further calls are **diagnostic only**, issued by any command after a
   403 so requirement 13 can tell a dead session from a missing grant:
   `GET /v1/auth/token/lookup-self` (Vault) and `GET /v1/job/<known>` (Nomad,
   to prove a `/v1/jobs` 403 is a missing `list-jobs` rather than a dead
   token). They never run on the success path.

   No other command may be registered. Adding a fifth needs a new ticket.
4. **`status` fetches its three sources concurrently, each with its own
   timeout, and no source may blank another.** A source that fails renders an
   error panel naming the service and the reason, and the command exits
   non-zero. Three green panels produced by a swallowed timeout is the
   failure this exists to prevent. Vault's `sys/health` needs no token, so
   the Vault panel is the one that works before F7 lands.
5. **`service` performs a stated outer join.** Rows are keyed by the union of
   haproxy routes and Nomad job ids. Consul is a column, never a row key.
   - **Routes** come from `GET /v1/job/haproxy`, from the `Templates[]` entry
     whose `DestPath` is `local/haproxy.cfg`. Parse `acl is_<n> hdr(host) -i
     <host>`, `use_backend <b> if is_<n>`, and each `backend <b>` block's
     `server <id> <ip>:<port>`. Never read
     `deployments/infrastructure/services/haproxy.hcl`, and never read the
     stats page.
   - **Route to job**, in order: (a) a Nomad job whose id equals the route
     name; (b) failing that, a Consul service whose name equals the route
     name, which is how `vault`, `nomad` and `consul` resolve, since they are
     agent endpoints backed by no Nomad job; (c) failing both, the row is
     **unresolved**: render the hostname and the raw `ip:port` backend, and
     mark job and health as not found. `s3` is the live example of (c) and
     rendering it that way is correct output, not a bug.
   - **Health, per rung.** For a rung-(a) row, read the job's
     `TaskGroups[].Tasks[].Services[].Name` from `GET /v1/job/<id>` and match
     those names against Consul checks. Never guess by job id. For a rung-(b)
     row, health comes from the matched Consul service's own checks and the
     job column renders "no job (agent endpoint)", which is what `vault`,
     `nomad` and `consul` render. For a rung-(c) row, both columns render not
     found.
   - **Unrouted jobs**: every Nomad job with no route gets a row with an
     empty URL. Thirteen exist live.
   - **Missing means missing**: a job with no Consul check renders "no
     check", never healthy; a route with no job renders and is never dropped.
   - `service <name>` matches a route name first, then a job id, and says
     which it matched.
6. **`secret <service>` reports what a job asks for and whether it is
   there.** Extract KV2 paths by regex over each `Templates[].EmbeddedTmpl`
   of `GET /v1/job/<service>`. For each distinct path, call
   `GET /v1/secret/metadata/<path>`: 200 is present, 404 is **missing**, 403
   is **denied** and is a third state, never folded into missing. A reference
   the regex cannot resolve to a literal path renders as **unknown** with the
   raw fragment elided, never dropped. Deduplicate paths, and keep the task
   name that referenced each one.
7. **Every view carrying Consul data states that it is ACL-filtered.** Given
   the verified 2-of-25 behavior, a bare table is a lie. `status` and
   `service` both print a footer naming the token whose ACLs filtered the
   list and pointing at Q3's finding.
8. **No credential from a jobspec template ever reaches output.** The running
   haproxy job's `EmbeddedTmpl` contains the openfang basic-auth password in
   plaintext (`services.tf:322`, verified live). The parser extracts only the
   route fields named in requirement 5 into its dataclass, and the raw
   template text is never stored on a dataclass, never serialized by
   `--json`, and never included in an exception message or a traceback. The
   same rule covers `secret <service>`: only the extracted path string
   crosses the boundary, never the surrounding template text. Test 10 and
   test 16 pin both paths.
9. **`secret <service>` never issues a request to `/v1/secret/data/`.**
   Existence comes from the metadata endpoint, which returns no `data` field.
10. **`--json` on every command**, emitting the command's own dataclass, so
    the JSON never drifts from the table. Table is the default.
11. **`vault grants <job>` shows both columns: the raw template line and the
    resolved path**, plus capabilities. It must:
    - fetch the policy text at runtime from `data.policy` and never embed a
      copy;
    - discover the accessor by regex over the fetched text
      (`identity\.entity\.aliases\.([^.]+)\.metadata\.(\w+)`), never
      hardcode `auth_jwt_649fd6cc`;
    - substitute `nomad_job_id` from the argument and `nomad_namespace` from
      a `--namespace` option defaulting to `default`;
    - leave any variable it cannot fill visible as `{{...}}` and mark that
      row, so a future template variable is never silently dropped;
    - work unchanged against a three-block policy and a six-block policy,
      with no path count anywhere in the source;
    - print a one-line footer saying the view is rendered from policy text,
      not an authorization decision.
12. **`service <name> --open` prints the URL before it tries to open
    anything**, and exits zero when no browser exists. Use stdlib
    `webbrowser` from `commands/`, never `api/`.

    **It brokers no token, for Consul or anything else.** An earlier version
    carried a token-print-and-clipboard requirement verbatim from D2's
    `ui consul`, on the reasoning that pasting a token is the only way into
    the Consul UI. **That reasoning is false here**, measured 2026-08-01:
    `consul_server/templates/consul.hcl.j2:29-32` puts the agent token on
    `tokens.default`, so unauthenticated requests see everything — 25
    services, 5 nodes, 41 health checks, and 200 on `/ui/`, directly and
    through the edge over TLS. And an explicit token **replaces** that default
    rather than merging, so the brokered `deploy` token, which grants service
    read on `minio` and `postgres-db` only, would cut the UI from 25 services
    to 2. It degrades what it claims to enable.

    D2 cut `ui consul` on the same evidence, so there is nothing to absorb.
    Q4 is settled by that: no token, no clipboard, no OSC 52.
13. **One failure mode for a missing or dead token, on every command.** Catch
    D2's typed error, plus HTTP 403, and exit non-zero with a single message
    naming the affected service. Separate "not logged in" from "not allowed":
    - Vault: call `GET /v1/auth/token/lookup-self`. 403 means the session is
      dead, so say "run `localstack login`". 200 plus a 403 on the real call
      means the token lacks the grant, so name the denied path and the ticket
      that grants it (F7, per Preconditions).
    - Nomad: 403 on `/v1/jobs` while `/v1/job/<known>` succeeds means the
      token lacks `list-jobs`. Say that, name the policy, do not say "login".
    - Consul: 403 means the token is bad; a short list is a scope problem
      which requirement 7 covers.
14. **`.claude/rules/python-testing.md`: live-cluster tests carry D1's
    `cluster` marker and are excluded from the default run.** Default
    `pytest` is offline.
15. **`.claude/rules/uv-installer.md`: dependencies land via `uv add`**,
    never `uv pip`.
16. **`.claude/rules/prek-code-quality.md`: go through the task runner.** The
    gate is `just pre_commit`, which by then includes D1's ruff, mypy and
    pytest hooks.
17. **`.claude/rules/plain-language.md` applies to help text and error
    messages**, which are user-facing surfaces.
18. **`.claude/rules/adversarial-reviews.md`: adversarial review before
    done.**

## Code surface

New, all under the package D1 creates at `cli/src/localstack_cli/`. If D1
chose a different root, keep the shape and change the prefix.

- `cli/src/localstack_cli/api/errors.py`: new. `NotAuthenticated`,
  `MissingCapability`, `NotFound`, each carrying the service name and, for
  `MissingCapability`, the denied path or capability.
- `cli/src/localstack_cli/api/nomad.py`: new. `list_jobs()`,
  `get_job(job_id)`, `list_nodes()`, returning dataclasses. Maps 403 on
  `/v1/jobs` to a missing-`list-jobs` error and 404 to job-not-found. Exposes
  `job_templates(job_id)` returning `(task_name, dest_path, embedded_tmpl)`
  triples for the two commands that need template text, and nothing else may
  reach for `EmbeddedTmpl` directly.
- `cli/src/localstack_cli/api/vault.py`: new. `health()` wrapping
  `sys/health` with no token, `read_policy(name)` returning `data.policy`,
  `metadata_exists(path)` returning present/missing/denied, and
  `token_is_live()` wrapping `auth/token/lookup-self`.
- `cli/src/localstack_cli/api/consul.py`: new. `list_checks()` over
  `GET /v1/health/state/any`, returning check state keyed by service name in
  one call, plus the flag saying a token was used so the footer can name it.
- `cli/src/localstack_cli/api/haproxy.py`: new. Parses a rendered
  `haproxy.cfg` into `Route(name, hostname, backend_host, backend_port)`
  dataclasses. **Takes the config text as an argument**, so it is pure and
  testable, and it copies out only the four route fields. It never returns,
  logs or stores the input text. This is where requirement 8 is enforced.
- `cli/src/localstack_cli/api/services.py`: new. The join in requirement 5.
  Takes routes, jobs and checks; returns `ServiceRow` dataclasses with an
  explicit `job_source` field recording which rung of the ladder resolved the
  row (`job-id`, `consul-name`, `unresolved`).
- `cli/src/localstack_cli/api/secrets.py`: new. Extracts KV2 paths from
  template text by regex, deduplicates, keeps the referencing task name,
  marks unresolvable references unknown. Returns
  `SecretRef(path, task, state)`.
- `cli/src/localstack_cli/api/grants.py`: new. Parses policy HCL into
  `(path, capabilities)` pairs, extracts the accessor and variable names by
  regex, substitutes `nomad_namespace` and `nomad_job_id`, and reports
  unresolved variables. No path count anywhere.
- `cli/src/localstack_cli/api/status.py`: new. Fetches the three sources
  concurrently, each with its own timeout, and returns a `ClusterStatus`
  dataclass in which each section is either data or a named error. No
  exception from one source may escape and kill another.
- `cli/src/localstack_cli/commands/status.py`: new. Renders `ClusterStatus`.
- `cli/src/localstack_cli/commands/service.py`: new. `service [<name>]`, the
  `--open` flag, `webbrowser`, the OSC 52 copy, and the consul token print.
- `cli/src/localstack_cli/commands/secret.py`: new. `secret <service>`.
- `cli/src/localstack_cli/commands/vault.py`: new. Typer group `vault` with
  the single command `grants`.
- `cli/src/localstack_cli/commands/render.py`: new. Shared table rendering,
  the `--json` path, and the two footers (ACL filtering, policy-text
  disclaimer).
- `cli/src/localstack_cli/main.py`: modified. Register `status`, `service`,
  `secret` and the `vault` group. D1 owns the file; D3 adds four
  registrations.
- `cli/pyproject.toml`: modified. Add `httpx` as a runtime dependency and
  `respx` as a dev dependency, both via `uv add`. `typer`, `rich`, `pytest`,
  `ruff` and `mypy` are D1's.

Tests, all new, mirroring the source tree per D1's layout:

- `cli/tests/conftest.py`: respx fixture, fake token fixture standing in for
  D2's interface.
- `cli/tests/fixtures/policies.py`: two `nomad-workloads` texts, verbatim:
  the live three-block form and the pre-F9 six-block form.
- `cli/tests/fixtures/haproxy_cfg.py`: a rendered `haproxy.cfg` matching the
  live shape, **including the `insecure-password` line**, so the leak tests
  have something real to catch. Use an obvious fake value, never the live
  one.
- `cli/tests/fixtures/jobs.py`: Nomad job payloads including a job whose
  template references a KV2 path, one with no Consul service, and the
  19-job list payload.
- `cli/tests/api/test_nomad.py`
- `cli/tests/api/test_vault.py`
- `cli/tests/api/test_consul.py`
- `cli/tests/api/test_haproxy.py`
- `cli/tests/api/test_services.py`
- `cli/tests/api/test_secrets.py`
- `cli/tests/api/test_grants.py`
- `cli/tests/api/test_status.py`
- `cli/tests/commands/test_render.py`
- `cli/tests/commands/test_service_open.py`
- `cli/tests/commands/test_auth_failure.py`
- `cli/tests/cluster/test_live.py`: marked `cluster`, excluded by default.

Read-only, do not edit, but read them:

- `deployments/infrastructure/auth_userpass.tf:24-36`: the empty
  `token_policies` that makes the Preconditions table true.
- `deployments/infrastructure/nomad_deploy_role.tf:13-30`: the capability set
  the Nomad calls live within.
- `deployments/infrastructure/services.tf:318-323`: proof the haproxy jobspec
  carries a rendered password, which requirement 8 guards.
- `bootstrap/playbooks/enable_consul_secrets.yml:39-58`: the Consul ACL rules
  that filter the catalog.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`:
  the live three-block shape.
- `bootstrap/roles/nomad_server/tasks/main.yml:253-255`: proof the accessor
  is derived at bootstrap, so it cannot be a constant.
- `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:4-33`: the
  live `developer` Nomad policy, which Q1 turns on.

## Tests & validation gates

### Repo gate (verified green on a clean tree today)
- `just pre_commit` (`justfile:17-19`). Adding `cli/` activates `check
  python ast` and `debug statements (python)`
  (`.pre-commit-config.yaml:7,11`), plus the ruff, mypy and pytest hooks D1
  appended. All must pass.
- Worktree prerequisite: `just worktree_setup <path>` (`justfile:29-31`), or
  `terraform-validate` fails on the missing tfvars.

### Python gate
D1 owns it: ruff, mypy and pytest as local hooks scoped `files: '^cli/'`
(`.loop/plans/D1-cli-package-skeleton.md`, "The three hooks to add").
D3 runs what D1 landed.
If D1 landed none, that is a finding for D1 under
`.claude/rules/pre-existing-issues.md`, not a gate to invent mid-ticket.

Default suite is offline and must stay so: `uv run --project cli pytest`.

### Tests to add
Offline, respx-backed, in the files listed in the code surface.

**`service` and the join (requirement 5):**

1. `test_haproxy.py::test_parses_ten_routes_from_rendered_config`: feed the
   fixture, assert all ten route names, hostnames and `ip:port` backends.
2. `test_services.py::test_route_resolves_by_job_id`: `memex` resolves to the
   `memex` job with `job_source == "job-id"`.
3. `test_services.py::test_agent_route_resolves_by_consul_name`: `vault`,
   `nomad` and `consul` back onto no Nomad job and resolve through the Consul
   catalog, with `job_source == "consul-name"`.
4. `test_services.py::test_unresolved_route_renders_with_backend`: `s3`
   renders its hostname and `192.168.2.29:9000`, marked unresolved, and is
   **not** dropped.
5. `test_services.py::test_unrouted_job_gets_a_row_with_no_url`: `hermes`
   appears with an empty URL.
6. `test_services.py::test_job_without_consul_check_is_not_healthy`: a job
   with no Consul service renders "no check", never a healthy marker.
7. `test_services.py::test_two_routes_to_one_host_do_not_collapse`: `minio`
   and `s3` point at the same host on different ports (`:9001` and `:9000`).
   Assert both rows render, `minio` at rung (a) and `s3` at rung (c), and
   that neither is dropped or merged. The ladder matches on names, not
   backends, so the shared host must not tempt an implementation into
   deduplicating. See Q7 for why the ladder stops short of resolving `s3`.
8. `test_services.py::test_named_lookup_prefers_route_then_job`.
9. `test_haproxy.py::test_parser_survives_a_changed_config`: reorder the
   backends, add one, drop the stats frontend (N4's likely edit), assert the
   remaining routes still parse. No line numbers, no counts.

**The credential guardrail (requirement 8):**

10. `test_haproxy.py::test_password_never_leaves_the_parser`: the fixture
    contains `insecure-password`; assert the parser's return value,
    `repr()`, and the `--json` output of `service` contain neither the
    literal nor the substring `insecure-password`. Also assert a parse
    failure raises an exception whose `str()` does not contain the input
    text.

**`secret <service>` (requirements 6 and 9):**

11. `test_secrets.py::test_extracts_distinct_kv2_paths_per_task`: a two-task
    fixture, assert paths deduplicate and each keeps its task name.
12. `test_secrets.py::test_missing_path_is_flagged_missing`: metadata 404
    renders the path marked missing, not omitted.
13. `test_secrets.py::test_denied_path_is_a_third_state`: metadata 403
    renders "denied", distinct from missing, naming the grant. This is the
    Preconditions failure made legible.
14. `test_secrets.py::test_unresolvable_reference_renders_unknown`: a
    computed `secret (...)` reference renders as unknown rather than being
    dropped.
15. `test_secrets.py::test_never_requests_a_kv2_value`: assert
    `respx_mock["kv_data"].call_count == 0`, not a bare `assert_not_called`,
    per the python-testing rule.
16. `test_secrets.py::test_no_template_text_in_output`: the fixture's
    template carries a plausible-looking password line; assert it appears in
    no table cell, no `--json` field, and no error message.

**`status` (requirement 4):**

17. `test_status.py::test_one_dead_source_does_not_blank_the_others`: Vault
    200, Nomad 200, Consul times out. Assert Vault and Nomad sections carry
    data, the Consul section names Consul and its error, and the exit code
    is non-zero.
18. `test_status.py::test_vault_section_needs_no_token`: assert the
    `sys/health` request carries no `X-Vault-Token` header.
19. `test_status.py::test_nomad_403_renders_a_named_denial_not_an_empty_table`.

**`vault grants` (requirement 11):**

20. `test_grants.py::test_resolves_the_three_block_policy`: feed the verbatim
    live text, assert `secret/data/default/hermes/*` resolves with
    `["read"]`.
21. `test_grants.py::test_resolves_the_six_block_policy`: same job, the
    pre-F9 six-block text, assert every row resolves. **These two together
    are the anti-hardcoding gate: two shapes, neither privileged.**
22. `test_grants.py::test_accessor_is_discovered_not_hardcoded`: rewrite the
    accessor in the fixture to `auth_jwt_deadbeef`, assert resolution still
    works.
23. `test_grants.py::test_unknown_variable_is_marked_not_dropped`: inject a
    third variable, assert the row survives and is flagged unresolved.
24. `test_grants.py::test_namespace_option_changes_resolution`.

**Cross-cutting (requirements 7, 10, 12, 13):**

25. `test_render.py::test_json_flag_matches_table_source`: parametrized over
    all four commands, asserts `--json` serializes the same dataclass the
    table renders.
26. `test_render.py::test_consul_footer_appears_on_every_consul_view`:
    parametrized over `status` and `service`.
27. `test_render.py::test_grants_footer_disclaims_authorization`.
28. `test_service_open.py::test_open_prints_url_and_exits_zero_without_a_browser`:
    monkeypatch `webbrowser.open` to raise, assert the URL is on stdout and
    the exit code is zero.
29. `test_service_open.py::test_open_consul_prints_the_token_even_when_copy_succeeds`.
30. `test_auth_failure.py::test_every_command_exits_nonzero_without_a_token`:
    parametrized across all four commands. The requirement-13 gate.
31. `test_auth_failure.py::test_nomad_403_says_list_jobs_not_login`.
32. `test_auth_failure.py::test_vault_live_token_plus_403_names_the_path`.

**The client layer itself (code surface `api/nomad.py`, `api/vault.py`,
`api/consul.py`):**

33. `test_nomad.py::test_list_jobs_403_maps_to_missing_list_jobs`: the mapping
    requirement 13 depends on, tested at the client layer rather than only
    through the command.
34. `test_nomad.py::test_job_404_maps_to_not_found`, and
    `test_list_jobs_parses_the_nineteen_job_payload` from the fixture.
35. `test_nomad.py::test_job_templates_returns_task_dest_and_text_triples`:
    the one accessor allowed to hand out `EmbeddedTmpl`.
36. `test_vault.py::test_metadata_exists_maps_200_404_403_to_three_states`,
    and `test_lookup_self_403_maps_to_not_authenticated`.
37. `test_consul.py::test_list_checks_keys_by_service_name_in_one_call`, and
    `test_list_checks_records_whether_a_token_was_used` so the footer in
    requirement 7 has something to name.

Marked `cluster` tests in `cli/tests/cluster/test_live.py`, excluded from the
default run via D1's `addopts`:

38. `test_live.py::test_nineteen_jobs_from_the_api`: guards the `talat-shim`
    and `talat-consumer` trap. Asserts both appear, so an implementation that
    reads `deployments/` fails here.
39. `test_live.py::test_haproxy_routes_come_from_the_job_api`: fetches
    `GET /v1/job/haproxy`, asserts ten routes parse and that
    `deployments/infrastructure/services/haproxy.hcl` was never opened.
40. `test_live.py::test_grants_resolves_against_whatever_vault_serves`:
    fetches the real policy, resolves for a real job, asserts no unresolved
    variables remain. Shape-independent by construction.
41. `test_live.py::test_secret_paths_exist_for_a_known_job`: resolves
    `memex`'s four distinct paths against live metadata. Skips with a clear
    reason, rather than failing, when the token lacks `secret/metadata/*`
    read, since that is the Preconditions gap and not a code defect.

## Risk assessment

- **Blast radius: small and one-directional.** Every call is a GET. Nothing
  here can change cluster state. A bug produces a wrong screen, not a wrong
  cluster.
- **Reversibility: total.** Delete the modules and the four registrations.
- **Likeliest failure mode: a command that lies quietly.** Three verified
  cases: Consul returning 2 of 25 with a 200; a `service` table that inner
  joins and so hides exactly the broken rows; a `vault grants` that prints
  the template. All three fail by looking correct. Requirements 5, 7 and 11
  and tests 2 to 8, 20 to 24 and 26 exist for this.
- **Leaking the openfang password.** Verified live in the haproxy job's
  `EmbeddedTmpl` (`services.tf:322`). One `--json` dump or one unhandled
  parse error prints it. Requirement 8 and tests 10 and 16 are the guard, and
  the reviewer must check the boundary by eye as well.
- **Enumerating jobs from `deployments/`** because `/v1/jobs` 403s under the
  brokered token. That silently drops `talat-shim` and `talat-consumer`, and
  the same shortcut would take the routing table from an unrendered
  Terraform template. Tests 38 and 39 catch it, but only when the marked
  suite runs, so the reviewer must check the source of both by eye.
- **Dependency risk, and it is the big one.** Two of four commands cannot
  read their inputs under the credential D2 brokers today, and the ticket
  that fixes that (F7) is blocked. See Preconditions and Q2. The offline
  suite still runs and every command is implementable and testable, so D3 is
  not blocked from being built; it is blocked from being useful on this
  cluster. That distinction belongs to the operator, not to this plan.
- **The regex over template text is exact only while the fleet stays
  literal.** Verified today: zero computed `secret (...)` calls across 19
  jobs. Requirement 6's unknown state is what keeps a future computed
  reference from silently vanishing, and test 14 keeps it from degrading.
- **Grants rendering can drift from Vault's own substitution.** The lexical
  render is exact for the two variables in use today, and an approximation in
  principle. The footer in requirement 11 keeps it honest; test 23 keeps it
  from degrading silently.
- **N4 moves the addresses under this ticket.** Requirement 2 keeps every
  address in D1's config, so N4 is a config change. Test 9 keeps the haproxy
  parser from breaking on N4's likely stats-page edit.

## Subtickets (ordered)

1. **Confirm D2's interface, and relay the three grants.** Establish the
   exact call that returns Vault, Nomad and Consul tokens plus their
   addresses, and the typed errors it raises. Then relay, with the
   `relay-finding` skill: `sys/policies/acl/nomad-workloads` read and
   `secret/metadata/*` read to **F7**; the Nomad `list-jobs` plus node read
   to **D4** (which already claims `nomad_read_role.tf`); and the
   `ui consul` absorption to **D2**. Do not build around a missing piece.
2. **Settle Q1, Q2 and Q3 with the operator.** Q2 decides whether `status`
   and `service` ship before a read-scoped token exists. Building either
   command first risks rewriting it.
3. **Client layer, part one:** `api/errors.py`, then `api/nomad.py`,
   `api/vault.py`, `api/consul.py`. Tests 33 to 37 alongside. No typer, no
   rich in these files.
4. **`api/haproxy.py` and `api/services.py`, with tests 1 to 10.** The join
   is the ticket's real work and the guardrail sits inside it. Give it its
   own commit, and write the fixture with the `insecure-password` line before
   the parser, so test 10 can fail first.
5. **`api/secrets.py` and tests 11 to 16.**
6. **`api/grants.py` and tests 20 to 24.** Write the two policy fixtures from
   the verbatim texts first, then the resolver.
7. **`api/status.py` and its concurrency, tests 17 to 19, test 17 first.**
8. **Command layer and `render.py`,** including `--json`, both footers,
   `--open` and the unified auth-failure message. Tests 25 to 32.
9. **Marked live suite** (tests 38 to 41), plus confirming D1's `addopts`
   exclusion holds. Confirm `uv run --project cli pytest` stays offline and
   that `-m cluster` reaches the cluster.
10. **Gates:** `just pre_commit`, including D1's ruff, mypy and pytest hooks,
    all green.
11. **Adversarial review** per `.claude/rules/adversarial-reviews.md`. Brief
    the reviewer on three things: the quiet-lie failure modes, the source of
    the job list and the routing table, and the password guardrail.

## Open questions

**Q1: `status` and `service` need a Nomad token that can list jobs and read
nodes. Who provides it?**
Verified live: `GET /v1/jobs` returns 403 under the brokered `deploy` token
because `nomad_deploy_role.tf:13-30` withholds `list-jobs` on purpose. What
changed since the last draft is that **the policy already exists**. `GET
/v1/acl/policies` returns `['deploy', 'developer']`, and
`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:4-33` grants
`list-jobs`, `read-job`, `read-logs`, `node` read, `agent` read and
`operator` read, applied by Ansible at
`bootstrap/roles/nomad_server/tasks/main.yml:182-184`. Live `LIST
/v1/nomad/role` returns only `['deploy']`, so the missing piece is one
`vault_nomad_secret_role`, not a new policy.

Options:

  a. Add a `vault_nomad_secret_role` bound to the existing `developer`
     policy, and have D2 broker it. One resource, no new policy text.
  b. Author a narrower `nomad_read_role.tf` granting only `list-jobs`,
     `read-job` and node read. `developer` also carries `submit-job`,
     `alloc-exec` and `read-logs`, which a read-only CLI has no business
     holding.
  c. Add `list-jobs` to the `deploy` policy. Rejected: it blurs a policy
     whose comment states least privilege for the deployer as its purpose.
  d. Read the job list from `deployments/**/services/*.hcl`. Rejected
     outright: it misses `talat-shim` and `talat-consumer`, both verified
     running with no file in this repo, and it contradicts
     D4's `talat-*` trap bullet, "reads the **API**, never the repo tree"
     (`.loop/plans/D4-cli-cluster-tui.md`).

  *Recommendation: (b), owned by D4, not by D3.*
  D4's Q2 option (b) already claims
  `deployments/infrastructure/nomad_read_role.tf` as its own conditional
  deliverable (`.loop/plans/D4-cli-cluster-tui.md`), so two sibling tickets must not author the same file. D3
  authors nothing and relays the requirement. Reuse over (a) is tempting, but
  brokering `alloc-exec` and `submit-job` to a read-only CLI is a real
  widening, and `developer` was written for humans at a terminal, not for a
  token a CLI holds for 30 minutes.
  Note also that G2's "Why this matters beyond the browser"
  (`.loop/plans/G2-nomad-ui-oidc-login.md`) says this
  ticket's narrow-surface justification weakens once G2 lands, since G2 gives
  a human a `developer`-scoped Nomad token by another route. Re-read Q1 after
  G2.

**Q2 (operator fork): do `status`, `service` and `secret` ship before F7
grants the reads they need?**
Not a review finding and not something this plan may decide. As things
stand, `vault grants` renders nothing at all, `secret <service>` renders
every row "denied", and `status` renders one working panel of three. The
honest-denial path (requirement 13) makes that legible rather than wrong,
but D4's Q2 rejects exactly this shape for its own panel: "a panel whose
headline widgets say 'denied' is not worth shipping"
(`.loop/plans/D4-cli-cluster-tui.md`).

  Options: (a) implement all four now, ship them denied, and let F7 and Q1
  light them up; (b) implement and merge all four but register only `service`
  until the grants land; (c) hold D3 until F7 unblocks.

  *Recommendation: (a).* Every command is fully testable offline against
  respx, the code is identical either way, and the denial messages are
  themselves the artifact that tells the operator which grant is missing.
  Holding the ticket buys nothing and loses the pressure the denial messages
  create. But this is the operator's call, and it should be made before
  subticket 3 starts.

**Q3: should the Consul `deploy` policy get `service_prefix "" { policy =
"read" }`?** Verified: the brokered token sees 2 of 25 services, while an
anonymous caller sees all 25 with a 200. The restriction hides nothing from
anyone and only truncates the CLI's answer.

  *Recommendation: yes, as a finding relayed to D2 or to a small
  infrastructure ticket that edits
  `bootstrap/playbooks/enable_consul_secrets.yml:39-58`.* It grants no
  visibility the anonymous policy does not already give. D3 must not make
  that edit. Until it lands, requirement 7's footer keeps the short answer
  honest. Do not "fix" it by dropping the token, which would work today and
  break the moment the anonymous policy tightens, which is exactly what N4 is
  for.

**Q4: who owns `ui consul`, D2 or D3?**
D2 §12 locks `localstack ui consul`
(`.loop/plans/D2-cli-login-broker-tokens.md`, §12): broker a Consul token,
copy it with OSC 52, print it as a fallback, open the URL. D3's `service
<name> --open` covers the same ground for ten services rather than one.

  *Recommendation: D3 owns it, D2 drops `ui consul`, and D3 carries D2's two
  hard requirements verbatim* (print the token even when the clipboard write
  succeeds; prefer OSC 52 because it travels over SSH and through the
  devcontainer). One verb, not two. Consul is the only service needing a
  token pasted, which is a per-service quirk, not its own command. **This is
  a decision D3 cannot make alone**: D2 is still in `planning` with `ui
  consul` in its locked design, so subticket 1 relays the cut to D2 and the
  operator confirms. If D2 keeps it, D3 drops the token print from `--open`
  and keeps only the URL.

**Q5: does `vault grants <job>` show the raw policy, the resolved paths, or
both?**
  *Recommendation: both, side by side, resolved by lexical substitution.*
  Raw alone is what the operator correctly called near-useless. Resolved
  alone hides that the grant is templated and shared, which is the fact a
  developer most needs when they wonder why another job cannot read their
  secret. Two columns cost nothing and teach the mechanism. Lexical
  substitution is exact here because only `nomad_namespace` and
  `nomad_job_id` appear, confirmed against a live entity alias.

**Q6: should `grants` instead read the job's real entity alias metadata?**
Verified possible: the alias on `auth_jwt_649fd6cc` is named for the job and
carries `nomad_job_id`, `nomad_namespace` and `nomad_task`. It would be exact
rather than approximate.
  *Recommendation: no, not in this ticket.* It needs `identity/entity/id/*`
  read or `identity/lookup/entity` write, on top of the two grants F7 already
  owes this ticket. It also only works for jobs that have already logged in,
  so it would fail on exactly the new job someone is debugging. Revisit if a
  template variable appears that lexical substitution cannot fill, which test
  23 will detect.

**Q7: should `service` resolve the `s3` row by matching the backend `ip:port`
against Consul service instances?**
It would turn today's one unresolved row into a resolved one, since
`192.168.2.29:9000` is the `minio` job's S3 port. The cost is one
`GET /v1/catalog/service/<name>` per service, 25 calls, to replace a single
`GET /v1/health/state/any`.
  *Recommendation: no.* Requirement 5's third rung renders the hostname and
  the raw backend, which tells the reader everything the extra 25 calls
  would, and it stays correct for a backend that points somewhere Consul
  never knew about. Revisit only if unresolved rows become common.
