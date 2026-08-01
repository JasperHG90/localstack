---
verdict: fail
---

# Plan review — D2-cli-login-broker-tokens (pass `plan-validator`)

Reviewed plan: `.loop/plans/D2-cli-login-broker-tokens.md`
(sha256 `f4ed8d390210da6854f1e290d6649333441de97b038592a103c22f3f89ee5d4c`,
792 lines). No `plan:` line is written, because this is a `fail`.

## Premise verdict: PARTIALLY SOUND

The old body (sections 1 to 11) is well grounded: I re-ran its cluster
measurements and nearly all of them still hold. The damage is in the parts
written today. Section 12's credential-inheritance table has two rows that are
false in this repo's actual devcontainer, section 4's F2 narrative is now
stale in the opposite direction from the eval marker, and the two commands
section 12 adds never reached sections 7, 8 or 10, so the plan cannot be built
to its own eval.

## Per assumption

### P1 — `nomad` has no credential file, so a PATH shim is the only way a bare `nomad` inherits a session (§12 lines 563-568, 684-688). HOLDS

Measured, not taken on trust. `strings /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE`
returns `0`; the same probe against `/usr/bin/consul` for `CONSUL_HTTP_TOKEN_FILE`
returns `2`. The binary's `NOMAD_*` string table carries `NOMAD_TOKEN` and no
file variant. `nomad login -h` (Nomad v2.0.3) lists no sink flag. The plan's
numbers are exact.

Two caveats, neither fatal:

- An exported bash function (`export -f nomad`) would cover interactive shells
  and `bash` children without a PATH shim. It does not cover non-bash
  processes, `just`, or `exec`-style callers, so the shim is still the more
  general answer. The plan's word "only" is slightly strong; its conclusion is
  right.
- The measurement is against CLI 2.0.3, and `D6-cli-deps-and-shims` will
  replace it with the cluster's pinned 2.0.4
  (`.loop/plans/D6-cli-deps-and-shims.md:28-31`). Nothing here says 2.0.4 still
  lacks `NOMAD_TOKEN_FILE`. UNCERTAIN, low severity: a shim works either way.

### P2 — Writing `~/.vault-token` makes the stock `vault` CLI inherit the session, so `vault` needs no shim (Q4 lines 575-590; §12 table line 686). BREAKS

`VAULT_TOKEN` in the environment outranks `~/.vault-token`. Measured: with
`HOME` pointed at a directory whose `.vault-token` held garbage,
`vault token lookup` still succeeded, because it used the environment's token.

`VAULT_TOKEN` is not incidental here. `.devcontainer/devcontainer.json:37-39`
passes `--env-file .devcontainer/.env` to the container, and
`.devcontainer/.env:10` sets `VAULT_TOKEN` to the bootstrap root token. I
confirmed it live: `VAULT_TOKEN` is present in this shell and
`vault token lookup` reports `policies ["root"], ttl 0, entity_id "",
path auth/token/root`. Every shell and every child process in the devcontainer
inherits it.

So on the machine this ticket targets, `localstack login` writing
`~/.vault-token` changes nothing: `vault kv get` keeps running as root. Worse,
it fails silently in the dangerous direction. The developer believes their
`vault` commands run as the `operator` entity under `default` policy when they
still run as root, and `localstack logout` (which per Q4 and eval row 16
deletes the file) leaves `vault` fully working as root, so logout looks like it
did nothing.

Two smaller facts in the same area: `~/.vault-token` already exists in this
container (8 bytes, invalid: `env -u VAULT_TOKEN vault token lookup` returns
403), so `logout` deletes a file the CLI did not create; and D2's own non-goals
(§5 lines 177-179) forbid touching `.devcontainer/.env.example`, while the file
that actually sets `VAULT_TOKEN` is the gitignored `.devcontainer/.env`.
Removing the static token is F8's story, and F8 is `blocked`
(`loopctl ledger`). Q4's stated benefit therefore does not arrive within this
ticket, and no section says so.

Q4's other claim, that the value written is the value `vault login` would have
written, holds. The mechanism is right. The environment it lands in is what
the plan did not check.

### P3 — `consul` needs no shim because `CONSUL_HTTP_TOKEN_FILE` can be exported statically, and it "names a path, never changes, and holds no secret" (§12 lines 687, 690-692). BREAKS

Two measured failures.

1. **The file outranks the variable.** With a valid token in
   `CONSUL_HTTP_TOKEN` and a garbage token in the file, `consul acl token read
   -self` returned `403 (token does not exist: ACL not found)`. The file won.
   That collides head-on with this plan's own R5 (lines 254-260), which emits
   `CONSUL_HTTP_TOKEN` for `eval "$(localstack env)"`, and with the repo's
   `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` bridge in
   `deployments/infrastructure/justfile:8,12,16`. Once the variable is exported
   statically, a stale or wrong file silently beats every fresh token the CLI
   emits.
2. **A missing file is fatal, not inert.** With `CONSUL_HTTP_TOKEN_FILE`
   pointing at a path that does not exist and a valid `CONSUL_HTTP_TOKEN` set,
   `consul members` returned `Error connecting to Consul agent: Error loading
   token file ...: no such file or directory`. So exporting the variable in the
   devcontainer before anything writes the file breaks the `consul` CLI for
   everyone, including before a first `localstack login`. That is a regression
   from today's behavior, not a no-op.

And nobody owns the write. §12 line 692 says "`localstack login` just writes
the file it points at", but no requirement in §6 (R1 to R9) mentions a Consul
token file, §7 lists no such path, and `D6-cli-deps-and-shims` explicitly
disclaims it (`.loop/plans/D6-cli-deps-and-shims.md:107`: "No session or token
logic"). D6 nonetheless plans to export the variable
(`.loop/plans/D6-cli-deps-and-shims.md:153-155`). If D6 lands first, `consul`
breaks.

### P4 — Every broker call 403s today because the operator entity carries no policy, and that is still true at implementation time (§4 lines 95-110, R8, eval row 4). HOLDS

Verified against the live cluster, and verified that nothing else sneaks a
policy in:

- `vault read auth/userpass/users/operator` returns `token_policies []`,
  `token_ttl 0s`, `token_max_ttl 0s`.
- `vault read identity/entity/name/operator` returns `policies []` and
  `id 351f302a-ada1-0e79-15d3-e22a4be2e3e4`, matching the eval marker.
- The entity's one group, `oidc-smoke`, also carries `policies []`, so no
  policy arrives by group inheritance either.
- `vault policy read default` grants `auth/token/lookup-self`,
  `auth/token/renew-self`, `auth/token/revoke-self`, `sys/capabilities-self`,
  `sys/leases/renew`, `sys/leases/lookup`, `cubbyhole/*` and the entity
  self-read. No `nomad/creds/*`, no `consul/creds/*`, no KV, no
  `sys/leases/revoke`. §4's list and R4's and §9 item 4's conclusions all hold.
- It stays true: the only ticket that grants the creds reads,
  `F7-foundation-deployer-vault-oidc-login`, is `blocked` on a `BROKEN` plan
  verdict (`loopctl ledger`).

I could not run a real `userpass` login end to end (the probe was refused by
the permission layer), so the 403 is inferred from the policy set rather than
observed. Given `token_policies = []` on both the user and the entity and the
contents of `default`, the inference is tight.

### P5 — "F2 is committed on branch, not merged and not applied; `vault auth list` returns only `jwt-nomad/` and `token/`" (§4 lines 80-82, §5 line 182, §8 lines 455-459). BREAKS

`vault auth list` now returns `jwt-nomad/`, `token/` **and** `userpass/`
(accessor `auth_userpass_ca653bd3`, description "Human logins. Entities created
here are what OIDC assignments gate on."). `vault list auth/userpass/users`
returns `operator`. `secret/default/vault/operator` exists and holds `password`
and `username`. The ledger has `F2-foundation-vault-oidc-provider: done`.

The eval marker already corrects this. The plan body does not, and it is not a
harmless stale line: §8 lines 455-459 instruct the implementer that "None of
these can pass until F2 is merged and applied ... `auth/userpass/login/operator`
404s. Do not fake a green run. Record the blocked state." Live rows 16, 17 and
19 are runnable **today**, and an implementer following §8 will record them as
blocked instead of running them. R8's second half (the 404 message being "the
expected state of the world") is stale for the same reason. §11 Q7 line 791
already says `docs/vault-human-auth.md` "is now merged on `main`", so the plan
contradicts itself.

### P6 — The 32-day Vault token TTL is correct by design, so the `whoami` warning and F7's `token_ttl` task can both be dropped (Q6 lines 598-620). PARTIALLY SOUND

The mechanical claims check out. `vault read sys/config/state/sanitized`
reports `default_lease_ttl 0` and `max_lease_ttl 0`, so Vault's built-in 768h
default governs, and `auth/userpass/users/operator` sets neither `token_ttl`
nor `token_max_ttl`. D2 genuinely cannot lower it from the client, and the
non-goal against touching `auth_userpass.tf` is consistent. The withdrawal was
recorded where Q6 says it was:
`.loop/plans/F7-foundation-deployer-vault-oidc-login.md:538-540` ("Do NOT set
`token_ttl` on the operator login") and `:733` ("Q2 (TTLs) → CLOSED").
Dropping a warning that would fire on every healthy session is defensible.

Two problems remain, and they are why this is not a clean HOLDS.

1. **The plan contradicts its own resolution.** §"How this ticket informs F7's
   replan" item 3 (line 649) still reads "**The operator login needs a
   `token_ttl`.** See Q6." Q6 says the opposite, and F7 has already closed it
   the other way. That line is precisely the hand-off F7's replan will read.
2. **The residual risk is never stated as a security fact.** Once F7 grants the
   creds reads, `session.json` holds a bearer credential that mints
   deploy-capable Nomad and Consul tokens on demand for up to 32 days, with no
   client-side bound and no rotation. §9 "What lands on disk" (lines 473-480)
   describes the file's contents and its mode but never names that blast
   radius, and never records the recovery move (revoke by accessor, which needs
   a token the operator does not hold, per `default`'s lack of
   `sys/leases/revoke`). The `gcloud` analogy the plan leans on understates
   this: a Google refresh token is scoped and centrally revocable, this one is
   a key to the cluster's deploy path. The decision is the operator's to make
   and I am not overturning it; the plan must carry the consequence in writing
   rather than only the reassurance.

### P7 — The ticket's guardrail (no Terraform, no Vault policy, nothing under `deployments/`) is compatible with everything §12 now asks. PARTIALLY SOUND

The Terraform and policy half holds cleanly: nothing in §12 needs a `.tf` file
or a policy document, and the shim, PATH and pinned-binary work is D6's
(`.loop/plans/D6-cli-deps-and-shims.md:5-15,147-155`). Eval row 13 enforces it.

The guardrail is not what strains. Three §12 items strain the ticket's *stated
scope* instead:

- `localstack ui consul` (lines 718-736) arrives with real implementation
  guidance (OSC 52 clipboard, browser open, print-the-token-anyway) but appears
  in no requirement, no code-surface entry, no test, no subticket, and not in
  the eval's Definition of Done. An implementer cannot tell whether to build
  it. Its supporting claim about Consul CE is plausible and I did not falsify
  it, but `consul version` here reports `Consul v2.0.1` with no `+ent`, which
  matches.
- `~/.vault-token` writing and removal (§12 line 765, Q4) is in no requirement
  either, though eval row 16 scores it at 100%.
- The devcontainer's `CONSUL_HTTP_TOKEN_FILE` export sits between D2 and D6
  with neither owning the write (see P3).

### P8 — Terraform recipes read `CONSUL_HTTP_TOKEN` while the shell exports `CONSUL_TOKEN`, and emitting one name breaks half the repo (§4 lines 130-139, R5, §9 item 2, eval row 7). HOLDS

Every anchor resolves. `deployments/infrastructure/justfile:8,12,16` and
`deployments/applications/justfile:10,18,22,27,31` all carry
`CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}`; `docs/monitoring.md:153,175` the same;
`.devcontainer/.env.example:6` says `CONSUL_HTTP_TOKEN` while
`.devcontainer/.env:5` says `CONSUL_TOKEN`. `CONSUL_TOKEN` is in this shell,
`CONSUL_HTTP_TOKEN` is not.

The "breaks half the repo" claim is stronger than the plan even argues, and in
its favor: the `consul` CLI does not read `CONSUL_TOKEN` at all (the binary
carries `CONSUL_HTTP_TOKEN` and `CONSUL_HTTP_TOKEN_FILE`), and I confirmed
`CONSUL_HTTP_TOKEN=$CONSUL_TOKEN consul acl token read -self` succeeds where
the bare shell would not. Emitting only `CONSUL_HTTP_TOKEN` would leave the
justfile bridge substituting a stale `CONSUL_TOKEN` over the fresh one. Both
names are needed. Test 10 and eval row 7 are correctly the highest-value rows
here.

### P9 — The addresses §4 states are current, and `N4-netsec-edge-only-service-access` does not invalidate the plan. HOLDS, with a note

`VAULT_ADDR=http://192.168.2.30:8200`, `NOMAD_ADDR=http://192.168.2.30:4646`,
`CONSUL_HTTP_ADDR=http://192.168.2.30:8500` are all as stated. The Vault
listener is `tls_disable: true` on `0.0.0.0:8200`, so R2's premise holds. The
edge is live: `https://vault.lab.orangecluster.nl/v1/sys/health`,
`https://nomad.lab.orangecluster.nl/v1/agent/health` and
`https://consul.lab.orangecluster.nl/v1/status/leader` all returned 200 today,
and `deployments/infrastructure/services/haproxy.hcl:96,100-102,111-113,133,136,139`
resolve to exactly the binds, ACLs, `use_backend` lines and backends cited.

N4 will move `.devcontainer/.env` and `.env.example` to the edge hostnames
(`.loop/plans/N4-netsec-edge-only-service-access.md:124-125,172,197`), and it
is `planning` at priority 50 against D2's 46. This does not sink D2: every
address D2 uses comes from the environment or a flag, so the cutover is
absorbed. Two consequences are worth a line in the plan rather than a rewrite.
Today R2 forces `--insecure` on every single login, since the default
`VAULT_ADDR` is non-loopback plaintext; after N4 that flag becomes unnecessary.
And §4's address facts go stale on N4's landing, so they should be written as
"as of today" rather than as fixtures.

### P10 — The rest of §4 and §7's factual base. HOLDS

Re-measured or re-opened, all correct: `vault list nomad/role` → `deploy`;
`nomad/role/deploy` is `type: client` with `policies ["deploy"]`
(`deployments/infrastructure/nomad_deploy_role.tf:36-41` resolves to exactly
that block, `type = "client"` on `:39`); `consul/roles/deploy` is `ttl 1800`,
`max_ttl 3600`, `token_type client` (`consul_deploy_role.tf:19-25` resolves,
`max_ttl` on `:24`); `vault read nomad/config/lease` returns `ttl 30m`,
`max_ttl 1h`, set at `bootstrap/roles/nomad_server/tasks/main.yml:309`.

§7's warning that the two engines' response shapes differ is exactly right, and
I resolved it so the implementer need not: `nomad/creds/deploy` returns
`accessor_id` and `secret_id`; `consul/creds/deploy` returns `accessor`,
`token`, `local`, `partition`, `consul_namespace`. Both return
`lease_duration: 1800, renewable: true`.

Repo-state anchors also hold: no `pyproject.toml` and no `cli/` in the tree;
`.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, `:7` is `check-ast`,
`:11` is `debug-statements`, and there is no ruff, mypy or pytest hook;
`justfile:18-19` is `pre_commit`; `just worktree_setup` exists at
`justfile:30`; `.loop/config.json` sets the `just pre_commit` gate,
`require_review` and `require_eval`; `requirements.txt:3,5` are `httpx` and
`hvac`; `.github/workflows/` holds no Python job. Q1's resolution matches
D1's plan (`cli/`, src layout, `cli/pyproject.toml`, `typer`, and D1 adds the
ruff/mypy/pytest hooks: `.loop/plans/D1-cli-package-skeleton.md:110,121-123,
133,161-165`). Every F7 verdict anchor cited (`:36-73`, `:118-138`, `:250-260`)
resolves to the passage claimed.

Minor anchor slips, all cosmetic: `bootstrap/roles/nomad_server/tasks/main.yml:241`
is `VAULT_ADDR`, not `VAULT_TOKEN` (`:202,211,224` are correct); §6 cites
`.claude/rules/python-testing.md:99-103` for "Where tests live", which actually
lives at `:43-48`, while §8 test 8 cites `:44-48` for the precise-negative-
assertion rule, which actually lives at `:101-103` — the two anchors are
swapped.

## Most dangerous assumption

**P2.** If `~/.vault-token` does not in fact hand the stock `vault` CLI the
session, then §12's whole "which CLIs need a shim" table loses its first row,
`D6-cli-deps-and-shims` has already copied that row verbatim
(`.loop/plans/D6-cli-deps-and-shims.md:71-75`), and the failure mode is silent:
a developer who has "logged in" and sees `vault kv get` working is still root.
It is the one wrong assumption here that produces confident, wrong behavior
rather than a visible error. P3 is a close second and fails in the same
direction, one layer down.

## Contract hygiene

Checked against `skills/create-ticket/SKILL.md` "The contract" only where the
premise permits; two items fail outright.

- **Real code surface with resolved anchors.** Mostly clean (see P10), but
  incomplete. §7 lists `commands/auth.py` with `login, logout, whoami, env` and
  nothing else. Grepping §7 through §10 (lines 326-533) for `localstack token`,
  `localstack config`, `ui consul` or `vault-token` returns nothing. The two
  commands §12 declares "land in this ticket" (line 748) have no file, and
  neither does the `~/.vault-token` write.
- **Tests homed in the code surface.** FAILS. The eval marker binds four rows
  at 100% that the plan tests nowhere: `token <svc>` stdout purity, `token
  <svc>` failing closed, `login` writing and `logout` removing `~/.vault-token`,
  and `config` never printing a secret. §8's list stops at test 15, all of
  which predate the amendment.
- **Decomposition.** §10's seven subtickets never build `token` or `config`,
  yet D6's shim depends on `localstack token` existing and behaving exactly as
  eval row 14 requires. §2 still says "Four commands". The frontmatter
  `summary` (line 6) still lists `login|logout|whoami|env`.
- **Discovered, not assumed, gates.** HOLDS. §8's gate list matches the repo:
  `just pre_commit`, no Python hook today, `uv run pytest` run by hand, no CI.
  One drift: §7 and §8 say `@pytest.mark.integration` while D1 names the marker
  `cluster` (`.loop/plans/D1-cli-package-skeleton.md:163-164`) and the eval says
  `cluster`. §7 hedges with "or D1's marker", so this is a tidy-up.
- **Explicit non-goals.** HOLDS, except that "Not applying or merging F2"
  (line 182) is now vacuous.
- **Forks surfaced, not silently decided.** HOLDS for Q1 to Q7. Not for
  `localstack ui consul`, which is a new command decided inside a design
  section with no question, no requirement and no eval row.

## Required fixes before this plan can leave PLANNING

1. **Fix the `~/.vault-token` premise (P2).** State that `VAULT_TOKEN` in the
   environment outranks the file, that
   `.devcontainer/devcontainer.json:37-39` plus `.devcontainer/.env:10` put the
   root token in every shell, and that the Q4 mechanism therefore does nothing
   until F8 removes it. Then pick a response and write it down: have `login`
   and `whoami` warn to stderr when `VAULT_TOKEN` is set and differs from the
   session token, or keep `vault` on the shim list alongside `nomad`. Correct
   the §12 table row and tell D6, which has copied it.
2. **Fix the `CONSUL_HTTP_TOKEN_FILE` premise (P3).** Record both measured
   behaviors: the file outranks `CONSUL_HTTP_TOKEN`, and a missing file makes
   the `consul` CLI fail outright rather than fall back. Then assign the write
   to a requirement in §6 with a path, a mode and a `logout` removal, or drop
   the "consul needs no shim" row. Say explicitly how it interacts with R5's
   `CONSUL_HTTP_TOKEN` output and the justfile bridge, and sequence it against
   D6's static export so the variable is never exported before something writes
   the file.
3. **Rewrite the F2 status (P5).** F2 is `done` and applied: `vault auth list`
   returns `userpass/`, `auth/userpass/users/operator` exists, and the password
   is at `secret/default/vault/operator`. Update §4 lines 80-82, delete the
   §5 non-goal at line 182, and rewrite §8 lines 455-459 so live rows 16, 17 and
   19 are run rather than recorded as blocked. Keep row 18's 403 expectation:
   that one is still correct.
4. **Land `token`, `config` and the `~/.vault-token` write in the plan proper.**
   Add requirements (R10 onward) carrying the strict stdout contract for
   `token`, the no-secrets contract for `config`, and the write/remove contract
   for `~/.vault-token`; add their files to §7; add the offline tests the eval's
   four new rows demand to §8; add them to §10's ordering; update §2 and the
   frontmatter `summary`.
5. **Settle `localstack ui consul`.** Either give it a requirement, a file, a
   test and an eval row, or move it to its own ticket and say so in §12. It
   cannot stay as design prose with no home.
6. **Resolve the Q6 contradiction and record the residual risk.** Delete or
   invert line 649 ("The operator login needs a `token_ttl`"), which contradicts
   Q6 and F7's already-closed Q2
   (`.loop/plans/F7-foundation-deployer-vault-oidc-login.md:538-540,733`). In
   §9, state plainly what a stolen `session.json` buys once F7 lands (up to 32
   days of deploy-capable brokering, no client-side bound) and name the
   revocation path, since `default` grants no `sys/leases/revoke`.
7. **Small anchor repairs.** Swap the two `.claude/rules/python-testing.md`
   citations (§6's "Where tests live" is `:43-48`; §8 test 8's
   negative-assertion rule is `:101-103`); change
   `bootstrap/roles/nomad_server/tasks/main.yml:241` to `:224` or drop it;
   align the marker name with D1's `cluster`; mark §4's addresses as current-as-
   of-today given N4 will move them.

Fixes 1, 2 and 3 are the ones that change what gets built. The rest are the
amendment finishing the journey into the sections that govern implementation.
