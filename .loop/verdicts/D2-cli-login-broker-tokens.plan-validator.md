---
verdict: fail
---

# Plan review — D2-cli-login-broker-tokens (pass `plan-validator`)

Reviewed `.loop/plans/D2-cli-login-broker-tokens.md`, 1250 lines, sha256
`1ff76f5e…d27f6fadf` (matches the fingerprint I was given). No `plan:` line,
because this is a `fail`.

The prior verdict of 2026-07-31 is treated as history. I checked its seven
required fixes first (all but one are genuinely done, see P11), then attacked
the current text fresh. The damage is new, and it comes from today's F7 to F11
swap plus one part of the world this plan has never looked at.

## Premise verdict: PARTIALLY SOUND

The measured core still holds. I re-ran every cluster and binary measurement in
§4 and they are all correct. What breaks is downstream of them: the F7 to F11
swap stopped four references short of the ones that govern implementation, the
blast-radius paragraph is still sized for the retired policy rather than the one
that will actually land, and the Consul half of the ticket rests on a premise
nobody measured — on this cluster Consul does not gate catalog reads at all, so
`ui consul` brokers a token that makes the UI show *less*.

Method note: everything below marked "measured" I ran today. Everything marked
"read" I only opened. Two claims are inferences from live policy text and are
labelled as such, because confirming them would have required minting a token,
which is a cluster write.

## Per assumption

### P1 — F7 is retired and all four references were moved to F11. BREAKS

`loopctl ledger` confirms F7 is `blocked` and `[dropped]`, and F11 is `ready`
with a `pass-with-required-fixes` verdict and an eval signed 2026-08-01
(`.loop/evals/F11-foundation-human-read-role.md:61`). Four references were
indeed updated: §3 (`:42-45`), §4 consequence 1 (`:144-147`), §5 non-goal
(`:242-247`) and R8 (`:385-389`).

Eighteen were not, and they are not decoration:

- **§8 test 9 (`:689`)**: "Asserts the message names the path and points at
  F7." R8 (`:387`) now says the message names F11. The plan's own test asserts
  the opposite of its own requirement.
- **§8 live row 26 (`:751-753`)**: "the operator user ships `token_policies =
  []` and F7 is `blocked`, so a 403 is the true state of the cluster… If
  brokering ever succeeds here, F7 landed." The reason given for the row no
  longer exists. See P7 for why this matters more than a name swap.
- **§9 (`:779`, `:798`)**: "Once F7 grants the creds reads…", "Shortening the
  TTL is F7's lever". See P4.
- **§9 failure mode 7 (`:845`)**: "That is F7's ticket and the subject of a
  `fail` verdict."
- **§7 (`:617`)**: `docs/cli-login.md` documents "the F2/F7 preconditions".
- **§11 Q6 (`:1028-1030`)** and the whole **"How this ticket informs F7's
  replan"** section (`:1044-1074`), which is a hand-off to a ticket that no
  longer exists.

Four anchors in that hand-off section point at files that are not there. F7's
artifacts were moved to `.loop/archive/F7-foundation-deployer-vault-oidc-login/`
(measured, `git status --porcelain .loop/`), so
`.loop/plans/F7-…md:538-540`, `:733` and
`.loop/verdicts/F7-…plan-validator.md:118-138`, `:250-260` all resolve to
nothing. The content is intact at the archive path (I read `plan.md:536-542`
and `:731-735`; both say what the plan claims), so this is a path repair, not
a content error.

### P2 — F11 binds through an identity group, so a granted policy lands in `identity_policies` and not `policies`; an error message reading `policies` would tell a developer they have no grants when they do. HOLDS

This is the claim you asked me to check, and it is right. Two independent
confirmations:

1. **F11 says so.** Requirement 2 (`.loop/plans/F11-foundation-human-read-role.md:190-195`):
   "Bind through the group, not by setting `token_policies` on the auth mount
   and not on the entity." Q2 (`:258-261`) settles it as group. Its DoD
   (`:270-272`) independently reaches the same conclusion: "checked by
   asserting `identity_policies` rather than `policies`, since group binding
   puts it in the former."
2. **Measured, on the same Vault binary the cluster runs (v2.0.3).** I stood up
   a throwaway `vault server -dev`, enabled `userpass`, created a user with
   `token_policies=[]`, an entity, an alias, and an internal group carrying a
   `developer` policy granting read on the two creds paths, then logged in.
   `auth/token/lookup-self` returned:

   ```
   policies          = ['default']
   identity_policies = ['developer']
   ttl               = 2764799
   ```

   and `sys/capabilities-self` on `nomad/creds/deploy` returned `['read']`. So
   a token that *can* broker reports `policies: ["default"]`. R8's warning is
   exactly correct, and the failure it prevents is real.

Side benefit: `ttl = 2764799` is 768h, which independently confirms §4's and
§9's 32-day claim on the same code path.

Two refinements worth folding in, neither a defect: the field is only present
in the lookup response, and `sys/capabilities-self` (granted by `default`, read
live) answers "can I broker this path" directly and is a better diagnostic than
either policy list. R8 could say "report `identity_policies` and, when it is
empty, `sys/capabilities-self` on the denied path".

As pre-approved, the dev server overwrote `~/.vault-token`; it now holds the
dev root token, not a cluster credential. The dev server is stopped.

### P3 — F11 grants exactly `nomad/creds/deploy` and `consul/creds/deploy` as read, the two paths this client brokers. HOLDS

Read at `.loop/plans/F11-foundation-human-read-role.md:120-122`: exact paths,
`read` only, no wildcard. §5's non-goal note that a client brokering any other
role name will 403 by design is correct.

### P4 — §9's blast radius: a stolen `session.json` buys deploy-capable Nomad and Consul tokens for up to 32 days. BREAKS, and in the unsafe direction

§9 (`:777-799`) is still sized for the retired F7 policy. F11's policy is much
larger. Read at `.loop/plans/F11-foundation-human-read-role.md:102-122`, the
same `developer` group also carries:

- `identity/*` create/update/delete and `sys/policies/acl/*` create/update —
  so the holder can write a policy and attach it to their own group;
- `secret/data/default/*` and `secret/metadata/default/*` read/write — every
  application secret this repo owns;
- `auth/userpass/users/*`, `sys/auth/userpass` with `sudo`, `nomad/role/*`,
  `consul/roles/*`, `auth/token/create`, and enough `sys/mounts` to apply both
  Terraform roots.

F11 states the consequence itself (`:145-162`): "A `developer` can write
`identity/*` and `sys/policies/acl/*`, so they can grant themselves anything
short of `root`… **Everything else is reachable, in three commands**", and
forbids any doc calling it least privilege. It also records
(`:164-170`) that **no audit device is enabled on this cluster**, measured, so
there is no attribution for any of it.

So the file D2 writes at `0600` becomes, once F11 lands, a 32-day bearer
credential for full cluster administration short of `root`, with no attribution
— not "deploy-capable Nomad and Consul tokens". D2 owns `docs/cli-login.md`
(§7 `:616-617`), which is exactly the surface F11 forbids from overstating the
boundary. §9 as written would produce a doc that understates it.

### P5 — The Consul story: brokering a Consul token is what gets a developer access, and "pasting a token is the only route into the Consul UI" (R14 `:490-494`, §12 `:1164-1178`). BREAKS

Measured today, read-only:

- `bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32` sets
  `tokens { agent = …, default = … }` to the agent token. Anchor confirmed.
- An HTTP request carrying **no token** to `192.168.2.30:8500` resolves to
  accessor `4c042bbf-0d8d-24b4-5a17-98e1e36819a1`, description "Consul agent
  token", policy `agent_policy` (`/v1/acl/token/self`, no header). Read live,
  `agent_policy` grants `node_prefix ""`, `service_prefix ""`, `agent_prefix ""`
  and `session_prefix ""` at **`policy = "write"`**.
- Untokened results: `/v1/catalog/services` → 25 services, `/v1/catalog/nodes`
  → 5 nodes, `/v1/health/state/any` → 41 checks, `/v1/agent/members` → 200,
  `/ui/` → 200. `env -u CONSUL_HTTP_TOKEN consul catalog services` lists 21.
- Only KV and ACL are gated: a single-key GET on `/v1/kv/terraform/infrastructure`
  with no token returns **403** naming accessor `4c042bbf…` and `key:read`; the
  recursive key list returns `[]` rather than an error, which matches your note
  that Consul filters rather than denies.
- Nomad and Vault are **not** like this: untokened `/v1/jobs` → 403,
  untokened `/v1/sys/mounts` → 403. Consul is the outlier, and the plan treats
  all three symmetrically.

Now the brokered token. The live `deploy` Consul policy (read with
`consul acl policy read -name deploy`, and matching
`bootstrap/playbooks/enable_consul_secrets.yml:39-58`) is:
`key_prefix "terraform/"` write, `session_prefix "terraform/"` write,
`service "minio"` read, `service "postgres-db"` read, `node_prefix ""` read.
No `service_prefix ""`, no `key_prefix ""`, no agent.

And an explicit token **replaces** the agent default rather than merging with
it — measured: with a garbage token in `CONSUL_HTTP_TOKEN_FILE`,
`consul acl token read -self` returned `403 (token does not exist: ACL not
found)` instead of falling back to the default.

Three consequences the plan does not carry:

1. **R14's justification is false.** The Consul UI needs no token at all here;
   it already renders every service, node and check. §12 `:1173-1174` ("Pasting
   a token is the only route, and no amount of design removes that") is wrong
   on this cluster.
2. **R14 as specified makes the UI worse.** Pasting the brokered `deploy` token
   narrows the UI from 25 services to 2 and hides nothing that was hidden
   before, since KV stays out of reach except under `terraform/`. That is a
   regression dressed as a feature. (Inference from the two measurements above,
   not a live mint.)
3. **The R12 `consul` shim inherits it.** Exporting `CONSUL_HTTP_TOKEN=<deploy>`
   on every `consul` invocation silently narrows `consul catalog services` and
   every KV read outside `terraform/`, and Consul filters rather than erroring,
   so the developer sees a short list and no message.

`grep -iE "default_policy|anonymous|agent token|consul.hcl"` over the plan
returns nothing. This entire area is unexamined.

What survives: brokering a Consul token is still genuinely required for
Terraform, because both roots keep state in Consul KV under `terraform/`
(`F11:35-41`) and KV is the one thing the anonymous default token cannot read.
R5's two-name emission is still right. The UI command is what does not survive.

### P6 — "The static tokens keep working the whole time… a broken `localstack login` costs a developer nothing but the new command" (§9 `:811-815`), and R5's `eval` is a pure win. BREAKS in one direction the plan never states

R5 overwrites `NOMAD_TOKEN`, `CONSUL_TOKEN` and `CONSUL_HTTP_TOKEN` in the
developer's shell. §5 `:353` frames this as the move that "demotes the shell
from root to `operator`", which is true and desirable for Vault. For the other
two it is a demotion the plan never prices:

- The shell's current `CONSUL_TOKEN` is the **Bootstrap Token (Global
  Management)**, measured via `consul acl token read -self`. (Your briefing put
  the dev shell on the agent token with accessor `4c042bbf…`; measured, that
  accessor is the *server's default* token, and the shell holds the
  global-management bootstrap token. The substance — a god-mode static token —
  is unchanged and §4 `:59-60` states it correctly.)
- The live Nomad `deploy` policy (`nomad acl policy info deploy`) is
  `namespace "default"` with `submit-job`, `read-job` and the `host-volume-*`
  capabilities. No `node:read`, no `agent:read`, no `read-logs`. So after
  `eval "$(localstack env)"`, `nomad node status`, `nomad server members` and
  `nomad alloc logs` stop working in that shell, where they work today.
  (Inference from the policy text against Nomad's capability model; I did not
  mint a token to confirm, since that is a cluster write.)

This does not sink the design — short-lived least-privilege tokens are the
point — but "costs a developer nothing" is false, and `docs/cli-login.md`
should say what a demoted shell loses.

### P7 — Ordering: D2 can be picked up and scored while F11 has not landed. UNCERTAIN, and the plan has no answer either way

§8 live row 26 (`:749-753`) asserts brokering **fails** with R8's message. The
eval marker's rows 11 and 12 require brokering to **succeed** (three cache
entries with distinct absolute expiries; a stale entry re-brokered), at 100%
and 4/5. Both cannot be true of the same run.

Which one is true at pickup is unsettled. `loopctl ledger` reports
`next (deps satisfied, pick one): D1-cli-package-skeleton,
F11-foundation-human-read-role` — F11 is one of exactly two tickets ready to
go. D2's `depends_on` is `["D1", "F2"]` and does not include F11. So D2 may be
implemented before or after F11 with no ticket-level control, and the plan
carries no conditional for either state. The plan's own hedge ("If brokering
ever succeeds here, F7 landed and this row needs rewriting") names the wrong
ticket and is buried in a test description rather than in §10's ordering.

### P8 — §4's three measured CLI precedence facts. HOLDS, re-measured

1. **`vault`: environment beats the file.** With `HOME` pointed at a temp dir
   whose `.vault-token` held garbage, `vault token lookup` still succeeded and
   reported `policies ['root']`, `path auth/token/root`, `entity_id ''`.
   Confirmed. `.devcontainer/devcontainer.json:38-39` is the `--env-file`
   pair and `.devcontainer/.env:8` is `VAULT_TOKEN`; both anchors resolve.
2. **`consul`: the file beats the environment, and a missing file is fatal.**
   Re-measured both: garbage in `CONSUL_HTTP_TOKEN_FILE` with a valid
   `CONSUL_HTTP_TOKEN` → `403 (token does not exist: ACL not found)`; a
   nonexistent path → `Error connecting to Consul agent: Error loading token
   file …: no such file or directory`. R12 and eval row 20 are well grounded.
3. **`nomad`: no file.** `strings /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE`
   → `0`; the same probe on `/usr/bin/consul` for `CONSUL_HTTP_TOKEN_FILE` → `2`.
   `NOMAD_TOKEN` is present in the binary's string table.

One stale detail: §4 `:196` says the container's stray `~/.vault-token` is "8
bytes". It was 95 bytes when I started (and 7 now, from my dev server). It is
still invalid against the cluster — `env -u VAULT_TOKEN vault token lookup`
errors — so the conclusion holds and only the byte count is wrong.

### P9 — §4's Vault, role and lease facts. HOLDS, re-measured

`vault auth list` → `jwt-nomad/`, `token/`, `userpass/` (accessor
`auth_userpass_ca653bd3`, description as quoted). `vault list
auth/userpass/users` → `operator`. `auth/userpass/users/operator` →
`token_policies []`, `token_ttl 0s`, `token_max_ttl 0s`.
`identity/entity/name/operator` → id `351f302a-ada1-0e79-15d3-e22a4be2e3e4`,
`policies []`, one group. `vault list identity/group/name` → `oidc-smoke` only.
`vault policy read default` grants exactly the set §4 `:132-138` lists, with no
`nomad/creds/*`, no `consul/creds/*`, no KV and no `sys/leases/revoke`.
`nomad/role/deploy` → `type client`, `policies [deploy]`.
`consul/roles/deploy` → `ttl 30m`, `max_ttl 1h`, `token_type client`.
`nomad/config/lease` → `ttl 30m`, `max_ttl 1h`.
`sys/config/state/sanitized` → `default_lease_ttl 0`, `max_lease_ttl 0`,
listener `tls_disable true` on `0.0.0.0:8200`. Addresses are as §4 states.

### P10 — The plan's `path:line` anchors. HOLDS but for two, both new

Resolved and correct: `auth_userpass.tf:13-17`, `:24-27`, `:28-36` (with
`token_policies = []` on `:34`), `:38-53`; `variables.tf:58`;
`secrets.tf:121-123`; `nomad_deploy_role.tf` `type = "client"`;
`consul_deploy_role.tf:19-25` with `max_ttl` on `:24`;
`bootstrap/roles/nomad_server/tasks/main.yml:189-196`, `:202,211,224`, `:309`;
`haproxy.hcl:96,100-102,111-113,133,136,139`; `.devcontainer/.env.example:2,6,10-11`;
`.gitignore:2`; `.pre-commit-config.yaml:1,7,11`; `justfile:18-19`;
`.loop/config.json:2-3`; `requirements.txt:3,5`; `docs/vault-human-auth.md:20`;
`D1:137-140,172` (`cluster` marker); `D6:84-88` (three shims, all "yes").
No `pyproject.toml` and no `cli/` in the tree, as §4 says. The two anchors the
last verdict flagged as swapped in `.claude/rules/python-testing.md` are fixed
(`:43-48` is "Where tests live", `:101-103` is the precise-negative rule).

Broken:

- **R12 `:452-453`** cites `.loop/plans/D6-cli-deps-and-shims.md:169` for "No
  session or token logic". That line is unrelated prose; the quoted text is at
  **`:188`**.
- **§4 `:74`** cites `.loop/plans/N4-netsec-edge-only-service-access.md:224,231,321-322`
  for N4 moving `.devcontainer/.env` and `.env.example` to edge hostnames.
  `:231` is about haproxy returning 503 and `:321-322` is about firewall rules.
  The real references are **`:239`, `:246`, `:354-355`, `:413-414`**.

Also minor: §11 Q1 `:903` says "D1 is `planning`". D1 is `ready`.

### P11 — The prior verdict's seven required fixes were addressed. HOLDS, with one exception

1. `~/.vault-token` premise → done (R11 `:418-446`, §4 result 1, §12 table
   `:1118`, Q4 `:950-1004`).
2. `CONSUL_HTTP_TOKEN_FILE` → done (R12 `:448-479`, §4 result 2, eval row 20).
3. F2 status → done (§4 `:106-128`, §8 `:737-743` now runs rows 24, 25, 27).
4. `token`, `config`, `~/.vault-token` in the plan proper → done (R10, R13,
   R11; `commands/token.py`, `commands/config.py`, `vault_token_file.py` in §7;
   tests 16-22; subtickets 8 and 9; §2 and the frontmatter `summary` updated).
5. `ui consul` → given R14, a file, test 23 and an eval row. The *homing* fix
   is done; the *premise* under it is what P5 breaks.
6. Q6 contradiction → fixed (`:1063` now says the operator login does **not**
   need a `token_ttl`). The residual-risk paragraph was added but is sized for
   F7 — see P4.
7. Anchor repairs → the two `python-testing.md` citations are corrected, the
   marker is `cluster` throughout, `main.yml:241` is gone, and §4's addresses
   are dated. Two new broken anchors appeared (P10).

## Most dangerous assumption

**P5.** Every other finding is a paragraph to rewrite. P5 changes what gets
built. `localstack ui consul` exists solely because "pasting a token is the only
route into the Consul UI", and on this cluster that is false: the UI already
works with no token and shows all 25 services, while the token the command
pastes cuts that to 2. An implementer following R14 and eval row 18 to the
letter ships a command that degrades the thing it claims to enable, and both
the plan and the signed eval certify it green. P4 is a close second, because it
is the sentence `docs/cli-login.md` will be written from and it understates a
credential that F11 explicitly refuses to call a boundary.

## Eval marker review

`.loop/evals/D2-cli-login-broker-tokens.md`, signed 2026-07-31 — before today's
F7 to F11 swap. Its own signature history (`:77-83`) shows it is cleared and
re-signed whenever scope moves; this move did not clear it.

**Does any row contradict a requirement? Yes, row 4.** It requires the 403
message carry "(b) the login token's actual policies as read from
`auth/token/lookup-self`, and (c) that the grant is F7's ticket". R8 `:385-389`
now requires the message read `identity_policies` and name F11. An
implementation that satisfies R8 fails row 4 as written; one that satisfies row
4 literally prints the field that, measured in P2, reads `["default"]` for a
token that can broker — the precise failure R8 exists to prevent. The eval's
preamble (`:35-43`) and row 13's rationale (`:65`) also still say F7.

**Can every row fail? Yes — but two cannot pass.** Rows 11 and 12 require
successful brokering of both creds paths, which 403s until F11 is applied
(P9: `token_policies []`, entity `policies []`, one group `oidc-smoke`, and
`default` grants neither creds path). They are 100% and 4/5 rows that are
unachievable in the current cluster state, and D2 does not depend on F11 (P7).
Row 18's success case has the same dependency. Row 21 asserts `just pre_commit`
runs "the ruff, mypy and pytest hooks D1 added"; none exist today
(`.pre-commit-config.yaml` has `check-ast` and `debug-statements` only), which
is fine because D1 is a hard dependency, but the row is scoring D1's work.

**Is any guardrail self-certifying? No, but row 20 is over-broad.** Rows 13
(`git diff --stat` over `deployments/**` and `.tf`) and 20 (`grep -r
CONSUL_HTTP_TOKEN_FILE` over the branch diff) are both checks an implementer
can genuinely fail. Row 20 forbids the *string* anywhere in the diff, so a code
comment or a line in `docs/cli-login.md` explaining why the file variant is
deliberately not used would fail a correct implementation. Scope it to an
export or assignment of the variable, and to writing the file it names.

**One row rests on a falsified premise.** Row 18's rationale ("Pasting a token
is the only route into the Consul UI here") is wrong per P5.

## Contract hygiene

Checked against `skills/create-ticket/SKILL.md` "The contract". Better than last
pass; the amendment reached the sections that govern implementation.

- **Real code surface with resolved anchors.** Nearly clean. Two broken anchors
  and four archived-path anchors (P1, P10).
- **Discovered, not assumed, gates.** HOLDS. §8's gate list matches the repo:
  `just pre_commit` (`justfile:18-19`, `.loop/config.json:2-3`), `check-ast`
  and `debug-statements` as the only Python hooks, `uv run pytest` run by hand,
  `-m cluster` for the live run, no CI Python job. All verified.
- **Explicit non-goals.** HOLDS. §5 is specific and correctly scoped.
- **Tests homed in the code surface.** HOLDS. Every one of tests 1 to 28 names
  a file listed in §7. Test 9 contradicts R8 on content (P1), which is a
  correctness problem, not a homing one.
- **Forks surfaced, not silently decided.** HOLDS for Q1 to Q7. The Consul ACL
  posture (P5) is a fork the plan never noticed, so it is neither surfaced nor
  decided.

## Required fixes before this plan can leave PLANNING

1. **Fix the Consul premise (P5), then decide what survives it.** State in §4
   that `bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32` sets the
   server's `default` token to the agent token, that an untokened request
   therefore resolves to accessor `4c042bbf…` under `agent_policy`
   (`node/service/agent/session_prefix ""` write), and that measured today this
   returns 25 services, 5 nodes, 41 health checks and a 200 on `/ui/`, while KV
   is the one gated surface (single-key GET → 403; a recursive list filters to
   `[]` rather than erroring). Note that Nomad and Vault both 403 untokened, so
   Consul is the outlier. Then: **drop `localstack ui consul` or re-justify
   it**, since the brokered `deploy` policy grants read on two services only and
   an explicit token replaces the agent default rather than merging with it, so
   pasting it narrows the UI. If it survives, R14 must say what the token buys
   that no token does not (KV under `terraform/`, and nothing else). Add the
   same caveat to R12's `consul` shim: exporting the brokered token narrows
   every `consul` read outside `terraform/`, silently, because Consul filters.
2. **Finish the F7 to F11 swap (P1).** Eighteen references remain. The ones
   that change behavior are §8 test 9 `:689` (currently asserts the opposite of
   R8), §8 live row 26 `:751-753`, §9 `:779` and `:798`, §9 failure mode 7
   `:845`, §7 `:617`. Repoint or delete the "How this ticket informs F7's
   replan" section `:1044-1074` and Q6's `:1028-1030`; their four anchors now
   live under `.loop/archive/F7-foundation-deployer-vault-oidc-login/`.
3. **Re-size §9's blast radius for F11 (P4).** The same `session.json` will
   carry `identity/*` and `sys/policies/acl/*` write, `secret/data/default/*`,
   `auth/token/create` and both Terraform roots
   (`.loop/plans/F11-foundation-human-read-role.md:102-122`), which F11 itself
   describes as reachable-to-anything-short-of-root in three commands
   (`:145-162`) with no audit device enabled (`:164-170`). Say that plainly in
   §9 and require `docs/cli-login.md` to say it, since F11 R6 forbids the
   opposite claim.
4. **Settle the F11 ordering (P7).** Either add
   `F11-foundation-human-read-role` to `depends_on`, or make §8 row 26 and eval
   rows 11, 12 and 18 explicitly conditional on F11's ledger state and say
   which assertion applies in which case. F11 is one of two tickets `loopctl`
   currently offers as next, so the coin is live.
5. **Correct eval row 4 and re-sign (eval review).** It must name F11, not F7,
   and must require `identity_policies` rather than "actual policies", or it
   scores an implementation against the misleading field. Fix the preamble
   `:35-43` and row 13's rationale `:65` too. Narrow row 20's grep from the bare
   string to an export or assignment plus a write of the named file. Fix row
   18's rationale or drop the row with the command.
6. **Two anchor repairs (P10).** `.loop/plans/D6-cli-deps-and-shims.md:169`
   should be `:188`. `.loop/plans/N4-netsec-edge-only-service-access.md:224,231,321-322`
   should be `:239,246,354-355,413-414`. Also `:903` calls D1 `planning`; it is
   `ready`, and §4 `:196` says the stray `~/.vault-token` is 8 bytes; it is not
   (and I overwrote it with a dev-server token, as pre-approved).
7. **State what `eval "$(localstack env)"` costs (P6).** The Nomad `deploy`
   policy is `namespace "default"` with `submit-job`, `read-job` and
   `host-volume-*` and no `node:read` or `agent:read`, so a demoted shell loses
   `nomad node status` and `nomad server members`. §9 `:813-815` currently says
   a developer loses nothing.

Fixes 1, 2, 3 and 4 change what gets built or what the docs assert. Fix 5 is
the gate scoring the wrong thing. Fixes 6 and 7 are repairs.
