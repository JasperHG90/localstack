---
verdict: fail
---

# D3-cli-read-commands — plan premise review

Plan reviewed: `.loop/plans/D3-cli-read-commands.md`
(sha256 `ccc9f1d0c46b4a381c03ff083f0f09ee3514160549b8dd0e80649e51a52b3b2c`,
withheld from the header because this is a `fail`).
Pass id: `plan-validator`. Repo root: `/home/vscode/workspace`.

## Premise verdict: BROKEN

The 2026-07-31 scope cut was appended, not applied. Lines 1 to 511 still
specify the eight-command surface in full: the front matter, the title, the
size estimate, requirement 3 ("exactly these eight"), the entire code
surface, all 17 tests and subtickets 3 to 7. The appendix at `:513-568`
deletes seven of those commands and adds three new ones. An implementer
reading top to bottom builds the cut surface; an implementer reading the
appendix has no requirements, no API calls, no code surface and no tests for
`status`, `service` or `secret <service>`. The eval scores exactly those
three at a 100% deterministic threshold
(`.loop/evals/D3-cli-read-commands.md:36-39`).

Under that, four Context claims the plan labels "verified live 2026-07-31"
are false against the live cluster today, and the surviving commands are
blocked on grants no token holds.

## Per assumption

### P1. `service` must read the haproxy routing table from the repo, because "neither Nomad nor Consul can see it" (`:534`) — BREAKS

Falsified twice.

Nomad can see it. `GET /v1/job/haproxy` returns
`TaskGroups[].Tasks[].Templates[].EmbeddedTmpl` for `local/haproxy.cfg`,
2327 bytes, containing the `hdr(host)` ACL block verbatim. Probed live with
the management token. The `acl is_minio hdr(host) -i
minio.lab.orangecluster.nl` lines the command wants are in the API response.

The repo file is not a jobspec. `deployments/infrastructure/services/haproxy.hcl`
is a Terraform `templatefile` input: `${tls_secret}` at `:64`,
`${openfang_password}` at `:89`, and `$${attr.unique.hostname}` at `:7`,
wired at `deployments/infrastructure/services.tf:318-323`. It does not parse
as HCL and the routing block is inside a heredoc, so a repo-sourced
implementation parses an unrendered template.

Worse, the repo source contradicts this ticket's own risk row
(`:384-387`, "enumerating jobs from `deployments/`... Test 15 catches it")
and D4's stated principle at `.loop/plans/D4-cli-cluster-tui.md:53`
("The panel reads the **API**, never the repo tree") and `:131`, `:153`.
The eval encodes the same repo source
(`.loop/evals/D3-cli-read-commands.md:37`, "routed in `haproxy.hcl`"), so
the defect is in both artifacts.

### P2. The `service` three-way join is well defined — BREAKS

Nothing in the plan or the eval names the join key, and the live data has no
usable one. `haproxy.hcl:127-157` addresses backends by literal IP and port
(`server memex1 192.168.2.46:8000`), never by Consul service name or Nomad
job id. Live counts: 10 routed hostnames, 19 Nomad jobs
(`GET /v1/jobs`), 25 Consul services (`GET /v1/catalog/services`, no token).
The mismatch is structural, not incidental:

- `vault`, `nomad` and `consul` route to agent ports 8200/4646/8500. No
  Nomad job backs them at all.
- `minio` and `s3` both route to the one `minio` job, on ports 9001 and 9000.
- `hermes`, `loki`, `nats`, `prometheus`, `promtail`, `acme`,
  `backup-minio`, `backup-postgres`, `node-exporter`, `talat-shim` and
  `talat-consumer` run with no edge route.

The eval demands "a routed hostname with no job must appear rather than
being dropped" (`:37`). Three such rows exist by design, and the plan never
says how an IP:port backend resolves to a job, nor what `service vault`
should render. This is the command's whole reason to exist and it is
unspecified.

### P3. Reading the haproxy jobspec is safe — BREAKS (new hazard, unguarded)

`deployments/infrastructure/services.tf:322` interpolates
`openfang_password = random_password.openfang_basic_auth.result` into the
jobspec. Probed live: the running job's `EmbeddedTmpl` contains
`insecure-password <literal>` with the real value, not the placeholder. Any
`service` implementation that fetches the haproxy job holds a live
credential in memory, and `--json` or a stack trace prints it. The eval's
secret guardrail (`:51`) is scoped to `secret <service>` KV2 values only and
does not cover this path.

### P4. `secret <service>` can resolve KV2 paths from template stanzas via the Nomad API, without reading values — HOLDS

The one new command whose mechanism survives contact. Probed all 19 live
jobs: every Vault reference in every `EmbeddedTmpl` is a static literal
(`{{ with secret "secret/data/default/hermes/github" }}` and so on), with
**zero** computed `secret (...)` calls anywhere. Sample: `hermes` 7 paths,
`bifrost` 6, `memex` 4, `talat-shim` 1. Existence is checkable without a
value: `GET /v1/secret/metadata/default/haproxy/tls` returns 200 with keys
`created_time`, `current_version`, `versions` and no `data`, and a missing
path returns 404.

The mechanism works. The plan never states it: no API call, no code surface
entry, no test. And see P8 for the grant it needs and does not have.

### P5. Live Vault serves the pre-F9 six-block `nomad-workloads` policy (`:120-126`) — BREAKS

Live `GET /v1/sys/policies/acl/nomad-workloads` returns exactly **three**
path blocks, matching
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-11`.
`tmp/HANDOFF-2026-07-31.md:43-52` records the apply: "F9 is applied. The
live `nomad-workloads` policy went from 6 path blocks to 3."

This is load-bearing. Test 1 (`:329-331`) instructs the implementer to
"feed the verbatim live text" for a six-block fixture, and subticket 4
(`:418-420`) says "Write the two policy fixtures from the verbatim texts
first". The verbatim live text is the three-block form. The eval already
carries the correction (`.loop/evals/D3-cli-read-commands.md:45`,
"Corrected 2026-07-31: F9 is now applied"); the plan does not. Plan and eval
contradict each other on the one command the appendix calls "Unchanged".

### P6. The local binaries are a major version ahead of the servers (`:132-141`) — BREAKS

Every number in the table is wrong, and the direction is inverted.

| Component | Plan says server | Live server | Local binary |
| --- | --- | --- | --- |
| Nomad | 1.11.3 | **2.0.4** (`/v1/agent/self`) | 2.0.3 |
| Vault | 1.21.4 | **2.0.3** (`/v1/sys/health`) | 2.0.3 |
| Consul | 1.22.6 | **2.0.2** (`/v1/agent/self`) | 2.0.1 |

`tmp/HANDOFF-2026-07-31.md:11-12` records the upgrade landing on all five
nodes the same day. Vault server and binary are identical; the Nomad server
is now ahead of the binary. The eval repeats the false numbers as its
justification for the no-subprocess row
(`.loop/evals/D3-cli-read-commands.md:41`).

The requirement itself survives on other grounds (the `rtk 0.42.4` shim is
real, and respx needs `httpx`), but its cited evidence is falsified and must
be replaced rather than carried.

### P7. Vault has no human-facing auth method, so D2's ground is soft (`:100-102`, `:390-396`) — BREAKS

Live `GET /v1/sys/auth` returns `jwt-nomad/`, `token/` and **`userpass/`**.
`deployments/infrastructure/auth_userpass.tf:13-15` creates it, `:29` writes
the operator user, `:46-54` binds the identity alias. D2 §12 settled the
human login on userpass
(`.loop/plans/D2-cli-login-broker-tokens.md:632-637`). Live
`sys/policies/acl` also lists `default-ceiling`, which the plan's policy
inventory at `:99` omits.

The risk row's conclusion is stale in a second way: it worries about "the
four `vault` commands", and after the cut only `vault grants` remains.

### P8. The token D2 brokers can read what the four surviving commands need — BREAKS. This is the most dangerous one.

`deployments/infrastructure/auth_userpass.tf:24-36` sets
`token_policies = []` on the operator user, deliberately: "this account
exists to obtain an identity, not standing privilege." So a human token from
`localstack login` carries `default` and nothing else. Live `default` grants
neither `sys/policies/acl/*` nor `secret/metadata/*` (probed: its path list
is self-lookup, cubbyhole, wrapping and renew only).

Consequences for each surviving command, against what exists today:

| Command | Live outcome |
| --- | --- |
| `vault grants <job>` | cannot fetch `sys/policies/acl/nomad-workloads`. The command's only input is denied |
| `secret <service>` | jobspec read works; the `secret/metadata/*` existence check is denied |
| `status` | Vault seal works (`sys/health` is unauthenticated, 200 with no token); Nomad nodes 403 under `deploy`; Consul 2 of 25 |
| `service` | Nomad job read works under `read-job`; Consul health filtered to 2 of 25 |

The plan's Q5 (`:487-496`) raises the grant gap only for the now-cut
`vault` commands and pins the fix on F7, which the ledger confirms is
`blocked` with `unresolved-design-fork`. Nothing re-scoped Q5 onto the two
commands that survived. The appendix's answer, "report that rather than
render a confident, wrong table" (`:562-564`), is exactly the shape D4
rejected: "Reject (c): a panel whose headline widgets say 'denied' is not
worth shipping" (`.loop/plans/D4-cli-cluster-tui.md:384`).

### P9. Q1's option list is complete, and the missing `list-jobs` needs a new policy — BREAKS

A `developer` Nomad ACL policy already exists and is live. `GET
/v1/acl/policies` returns `['deploy', 'developer']`.
`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:4-30` grants
`list-jobs`, `read-job`, plus `node` and `agent` read, applied by Ansible at
`bootstrap/roles/nomad_server/tasks/main.yml:182-184`. Live `LIST
/v1/nomad/role` returns only `['deploy']`, so the gap is one
`vault_nomad_secret_role`, not a new policy.

Q1 (`:434-451`) lists four options and none is "broker the `developer`
policy that already exists". Its recommendation (b) also collides with
`.loop/plans/D4-cli-cluster-tui.md:232-236`, where D4 already claims
`deployments/infrastructure/nomad_read_role.tf` as its own conditional
deliverable. Two sibling tickets propose to author the same file, and
`.loop/plans/G2-nomad-ui-oidc-login.md:109-116` says outright that this
ticket's narrow-surface justification weakens once G2 lands.

### P10. The `api/` purity contract (no typer, no rich) is achievable — HOLDS

Nothing in the four commands forces a CLI framework below the render layer.
`status` needs concurrent `httpx` GETs; `service --open` needs stdlib
`webbrowser` in `commands/`; `--json` serializes dataclasses. The eval's
grep (`.loop/evals/D3-cli-read-commands.md:40`) catches both `import typer`
and `from rich.table import Table`. No finding.

### P11. `GET /v1/jobs` is 403 for the brokered deploy token — HOLDS (one inference)

`deployments/infrastructure/nomad_deploy_role.tf:17-29` grants `submit-job`,
`read-job` and the five `host-volume-*` capabilities, with no `list-jobs`;
the comment at `:4-5` says so explicitly. `:36-41` is the
`vault_nomad_secret_role`. Probed tokenless: `GET /v1/jobs` returns 403,
`GET /v1/job/haproxy` returns 403. I did not mint a `nomad/creds/deploy`
token, since that creates a lease and this review is read-only, so the
deploy-token row rests on the policy text plus Nomad's documented
requirement of `list-jobs` for that endpoint. Sound, and worth labelling as
inferred rather than re-measured.

### P12. The brokered Consul token sees 2 of 25 services — HOLDS

Probed live with no token: `GET /v1/catalog/services` returns 200 and
exactly 25 services. `bootstrap/playbooks/enable_consul_secrets.yml:39-58`
grants `service "minio"` read and `service "postgres-db"` read with no
`service_prefix`, so the 2-of-25 figure follows.
`deployments/infrastructure/consul_deploy_role.tf:19-25` is the Vault role,
anchor resolves. Q2's reasoning stands.

### P13. The `talat-*` trap is real — HOLDS

Live `GET /v1/jobs` returns 19 jobs including `talat-shim` and
`talat-consumer`. The repo holds 17 jobspecs (11 under
`deployments/infrastructure/services/`, 6 under
`deployments/applications/services/`). The live Consul catalog carries
`talat-shim` but not `talat-consumer`, exactly as `:88-94` states.

### P14. `service --open` may absorb D2's `localstack ui consul` (`:538-541`) — UNCERTAIN, and unrelayed

D2 §12 is real and does lock that command
(`.loop/plans/D2-cli-login-broker-tokens.md:718-736`), but D2 is still at
`planning` in the ledger with `ui consul` in its own locked design, and its
requirements include clipboard-or-OSC-52 delivery and printing the token
even when the clipboard write succeeds. D3's appendix drops the clipboard
requirement silently and does not relay the cut to D2. One of the two plans
is wrong about who owns the command, and nothing decides which.

### P15. The repo gate section is discovered, not assumed — HOLDS in the plan, BREAKS in the eval

Plan anchors resolve: `justfile:17-19` is `pre_commit`, `justfile:29-32` is
`worktree_setup`, `.pre-commit-config.yaml:1` excludes `.claude/` and
`.loop/` only, `:7` is `check-ast`, `:11` is `debug-statements`,
`requirements.txt:3,5` are `httpx` and `hvac`. The plan is right that no
ruff, mypy or pytest hook exists (`:159`) and right to defer to D1
(`:318-322`).

The eval's last row demands `just pre_commit` pass "including ruff, mypy and
pytest" (`.loop/evals/D3-cli-read-commands.md:52`). Those hooks do not exist
and this ticket is told not to invent them. As signed, that row cannot pass.

## Most dangerous assumption

**P8**: that the credentials D2 brokers can read what these four commands
need. `token_policies = []` on the only human account, `default` granting
neither `sys/policies/acl/*` nor `secret/metadata/*`, and the `deploy`
Nomad token holding neither `list-jobs` nor node read, mean all four
commands degrade to permission errors on the cluster they were measured
against. The plan's own answer, printing the denial honestly, turns the
flagship `status` view into three error panels. If P8 is wrong, the ticket
ships four commands that render nothing.

## Required fixes before this plan goes ready

1. **Rewrite the body to the four-command scope.** Front matter, title, size,
   requirement 3, code surface, tests and subtickets 3 to 7 must describe
   `status`, `service`, `secret <service>` and `vault grants`. Delete the
   eight-command table at `:196-206` rather than leaving it above an
   appendix that contradicts it.
2. **Give the three new commands a real code surface**: the API calls each
   issues, the `api/` modules and dataclasses, and named tests with their
   files. The eval scores all three at 100% and the plan currently homes no
   test for any of them.
3. **Fix `service`'s data source.** Take the haproxy config from
   `GET /v1/job/haproxy` (`Templates[].EmbeddedTmpl`), not from
   `deployments/infrastructure/services/haproxy.hcl`, and say so, so the
   ticket stops contradicting `.loop/plans/D4-cli-cluster-tui.md:53`.
4. **Specify the join.** State how an `IP:port` backend
   (`haproxy.hcl:127-157`) maps to a Nomad job and a Consul check, and what
   `service vault`, `service nomad`, `service consul`, `service s3` and
   `service hermes` each render. Ten routes, nineteen jobs and
   twenty-five services do not line up.
5. **Add a guardrail for the haproxy jobspec's plaintext password**
   (`services.tf:322`, verified live in `EmbeddedTmpl`). No jobspec field may
   reach stdout, `--json` or an error message unfiltered.
6. **Correct the `nomad-workloads` fact and the fixtures.** Live is three
   blocks (`tmp/HANDOFF-2026-07-31.md:43`). Rewrite `:120-126`, and restate
   tests 1 and 2 as "two shapes, neither privileged" rather than
   "live versus F9".
7. **Correct the version table** at `:132-137` to the live 2.0.x servers, and
   re-ground requirement 1 on the `rtk` shim and respx. Fix the same numbers
   in the eval row at `.loop/evals/D3-cli-read-commands.md:41`.
8. **Correct the Vault inventory**: `userpass/` is live
   (`auth_userpass.tf:13-15`), `default-ceiling` is a live policy, and the
   human login question is settled by D2 §12, not blocked on F7.
9. **Re-scope Q5 onto the surviving commands** and state the exact grants
   `vault grants` and `secret <service>` need
   (`sys/policies/acl/nomad-workloads` read, `secret/metadata/*` read or
   list), given `token_policies = []`. Relay them to D2 and F7 as a
   dependency, not a footnote.
10. **Rewrite Q1** to include the live `developer` policy
    (`nomad_developer_policy.hcl:4-30`, live in `GET /v1/acl/policies`) and
    the fact that only a `vault_nomad_secret_role` is missing. Resolve the
    duplicate claim on `nomad_read_role.tf` with
    `.loop/plans/D4-cli-cluster-tui.md:232`.
11. **Decide and relay who owns `ui consul`** versus `service --open`, and
    carry D2's clipboard and print-anyway requirements if D3 takes it.
12. **Reconcile the eval's gate row** with the repo: either D1 lands ruff,
    mypy and pytest and D3 depends on it explicitly, or the row drops those
    three names. As written, `just pre_commit` cannot pass it.

## Notes on what I could not settle

- I did not mint `nomad/creds/deploy` or `consul/creds/deploy`, since minting
  creates a Vault lease and this review is read-only. The 403 and 2-of-25
  rows are corroborated from policy text plus the tokenless and management
  probes, not re-measured end to end.
- Whether `status` can be worth shipping at all before a `developer`-scoped
  token exists is an operator call, not a review finding. The plan should
  surface it as a fork rather than absorb it in a Consequences bullet.
