# Pickup order

**Today: F11, then D1.** Both are `ready` with signed eval markers and passing
verdicts. Everything else is blocked, and the reasons are below.
Updated 2026-08-01.

A ticket is implementable only when BOTH hold:
1. stage is `ready` — which needs a **passing** `plan-validator` verdict bound
   to the plan's current sha256 (`lifecycle.py:127`), and
2. its eval marker is **signed** (`lifecycle.py`, "implementing entry needs a
   signed eval marker").

`pass-with-required-fixes` counts as passing. Where a ticket carries one, the
fixes are listed in its verdict and are **implementation work, not optional**.

## State, end of 2026-08-01

| Ticket | Where it is |
|---|---|
| **F11-foundation-human-read-role** | **`done`.** The `developer` Vault policy and identity group are live and merged. `vault login -method=userpass username=operator` now covers both Terraform roots, brokered Nomad and Consul tokens, and user/group management |
| **D1-cli-package-skeleton** | Built and green — `cli/` package, `localstack` entrypoint, 8 tests, four new pre-commit hooks. All 14 hooks pass. Commit gate holds pending two tree-bound review verdicts |
| **F14-foundation-role-taxonomy** | `ready`, eval signed. Depends on F11, which is now done — so it is next after D1 |
| **G2-nomad-ui-oidc-login** | Premise confirmed sound. Auth method and binding rule moved to Ansible; re-reviewing |
| **D2-cli-login-broker-tokens** | `ui consul` cut per the locked surface; re-reviewing |

## Two cluster findings that own no ticket

**A stolen `localstack` session file: run `localstack logout` first.**
That alone ends all three credentials, by cascade, and needs no root. If the file is gone, a revoke by accessor does the same — also without root, since `developer` can grant itself `auth/token/revoke-accessor`. Rotating the operator password does nothing: `secret/default/vault/operator` is
the KV *record*, while the credential lives at `auth/userpass/users/operator`
(`auth_userpass.tf:29`). And the holder of a stolen session has `developer`,
which grants `auth/userpass/users/*` and `identity/*` — so they rotate it back
or mint a second identity. Measured 2026-08-01.

**Consul's catalog is readable with no credential**, on 8500 directly and
through the TLS edge: 25 services, 5 nodes, 41 health checks, and `/ui/`
answers 200. `consul_server/templates/consul.hcl.j2:29-32` puts the agent
token on `tokens.default`, so `default_policy = "deny"` never applies. Closing
the port is the only control Consul has, and there are two paths to close.

## Ready, waiting only on F11

| Ticket | State |
|---|---|
| **F14-foundation-role-taxonomy** | `ready`, eval **signed**, passing verdict bound to its current plan. The `admin` group and the app-user scaffold. Its only unmet dependency is F11 |

## In plan review, 2026-08-01

| Ticket | Note |
|---|---|
| **D2-cli-login-broker-tokens** | Rewritten after its failing verdict and never re-reviewed. Also re-pointed off the retired F7 onto F11, which grants exactly the two creds paths D2 brokers |
| **G2-nomad-ui-oidc-login** | Same. Plus a new non-goal: F14 owns the group convention, G2 consumes a name rather than defining one |
| **N4-netsec-edge-only-service-access** | Same. Highest blast radius on the board |
| **N3-netsec-converging-firewall-provisioner** | First review it has ever had. N4 cannot be implemented without it |

## Blocked: never reviewed

These sat at `ready` because they were advanced before the planning-review pass
was wired in, so **no plan-validator verdict has ever run against them**. Their
premises have never been attacked.

Every plan that *was* reviewed on 2026-08-01 carried a defect and several were
fatal — a wrong Vault endpoint, an eval row that failed correct work, a policy
that could escalate to root in two steps. On that record, "ready but never
reviewed" is weaker than "ready with a passing verdict", not stronger.

| Ticket | Why it matters that nobody checked |
|---|---|
| **N3-netsec-converging-firewall-provisioner** | Rewrites ufw rules on five nodes over the same SSH it runs on. Highest cost of a wrong premise on the board |
| **G1-grafana-native-oidc-login** | Two problems. It has **no eval marker at all** — needs authoring, not signing. And a hole found 2026-08-01 while reviewing G2: it creates no `vault_identity_oidc_assignment`, and Vault admits no entity through a client by default, so **G1 as planned admits nobody**. |
| **S2-spike-postgres-vault-creds** | R3 and S1 both depend on its conclusion |
| **T5-tls-certificate-expiry-alert** | Low blast radius; cheapest of the five to clear |
| **C1-cicd-tailscale-github-actions-deploy** | Gives CI cluster access. Worth a premise check before it exists |

Unblock each by running the plan reviewer against it.

## Done but not closed in the ledger

`U1` to `U4` shipped in `547cab0 build: upgrade HashiStack to 2.x and pin the
versions`. All four services run 2.x and the versions are pinned in
`bootstrap/inventory/group_vars/all.yml:9-13`. `loopctl done` cannot close them
because it matches on a commit subject starting with the slug, and that commit
does not carry one.

**Pinned is ahead of live**: Nomad pins `2.0.4-1` and runs 2.0.3; Consul pins
`2.0.2-1` and runs 2.0.1. The next `just bootstrap` upgrades both.

## Waiting on one re-review round

All eight were rewritten against their failing verdicts. The rewrites fixed the
content; they did not produce a passing verdict, and the verdict is what the
gate reads.

| Ticket | What it does |
|---|---|
| **N4-netsec-edge-only-service-access** | Closes direct LAN access so the edge is the only route in. Also closes a live auth bypass: mlflow and phoenix answer 200 with no credentials. Needs N3 first |
| **D2-cli-login-broker-tokens** | `login/logout/whoami/env/token/config`; brokers Nomad and Consul tokens from one Vault session |
| **D6-cli-deps-and-shims** | Installs the CLIs at the versions the cluster pins, plus the PATH shims that let a bare `nomad` use your session |
| **G2-nomad-ui-oidc-login** | Nomad web UI and `nomad login` sign in through Vault |
| **D3-cli-read-commands** | `status`, `service`, `secret <svc>`, `vault grants` — the synthesis commands |
| **D4-cli-cluster-tui** | `localstack monitor`, the live Textual panel |
| **D5-cli-breakglass** | `localstack breakglass`, the recovery runbook |
| **F8-foundation-deployer-provider-cutover** | Points Terraform's providers at brokered tokens, drops the static ones |

## The critical path

```
N3  ->  N4                        closes the live auth bypass
F11 ->  D2 -> D6                  per-person sessions, then the shims
F11 ->  F8                        retires the root token: providers off the
                                  static tokens
F11 ->  F14 -> G1/G2/M2           application users, per app
D1  ->  D2 -> D3/D4/D5
```

`F11` and `D1` are independent of `N3` and of each other, so all three can run
in parallel.

`F11` is the unblocker for almost everything else. It is small, and every
capability in it has been run against the live cluster.

## Why not the CLI first

`localstack login` authenticates against `userpass` and then returns 403 on
every broker call, because the `operator` entity carries no policy. Verified
live 2026-07-31 with the operator's own token:

```
secret/data/default/grafana/admin   ["deny"]
sys/policy                          ["deny"]
identity/entity/id                  ["deny"]
auth/userpass/users                 ["deny"]
```

`D2`'s own plan states the same conclusion: *"`login` will authenticate but
every broker call returns 403 until a policy binds the operator entity to the
creds paths."* That policy is now `F11`'s deliverable; `D2` names `F7`, which
is retired, so re-read that line against `F11` when `D2` comes up. `D2` and
`D4` also broker `nomad/creds/deploy` and `consul/creds/deploy` by name, which
`F11` grants.

Built first, `D2` is four commands that log in successfully and do nothing.

If "CLI first" means `D1`, that is fine and it is item 2. If it means `D2`, it
is premature by exactly one ticket.

## The role model, settled 2026-08-01

The operator's taxonomy, and where each part lives:

| Role | What it is | Ticket |
| --- | --- | --- |
| **Application user** | Uses MinIO, MLflow, Memex. No Vault or Nomad access at all | scaffold in `F14`; the groups themselves come with each app |
| **Developer** | Everything: infra and apps, Nomad jobs, Vault user and group management, and deploying the Terraform | `F11` |
| **Admin** | Full control, via a breakglass procedure rather than a daily credential | group in `F14`, procedure in `D5` |
| **Service account** | A workload reaching another service, e.g. Memex to a MinIO bucket | `F1`, `M1`, `R3` |

**Developer and Deployer are one group.** The operator collapsed them on
2026-08-01. A `developer` can write `identity/*` and `sys/policies/acl/*`, so
they can grant themselves anything short of `root` — Vault refuses to attach
`root` and refuses nothing else, measured. That is a deliberate choice for a
one-person cluster, not an oversight, and `F11` forbids any doc calling the
policy least privilege.

What the credential does buy over the root token: it is per-person, revocable
without re-keying Vault, attributable in the audit log, and it cannot reach the
`bootstrap` KV mount, `sys/raw`, audit devices or unseal.

**The group name is the contract.** `F2` already emits
`identity.entity.groups.names` as a `groups` array in the OIDC token
(`oidc.tf:36-49`). That one string is what a relying party maps to its own
role, and nothing else crosses service boundaries.

**A group needs an OIDC assignment before it grants anything.** Live, the
provider has one client whose assignment is `group_ids = [<oidc-smoke>]`,
`entity_ids = []` — membership in an unassigned group gets you nowhere. `F14`
builds that extension point; each app ticket adds its own groups to its own
assignment.

Consumers are not uniform and `F14` deliberately does not decide for them:
`M2` gates on the per-client assignment and ignores the claim entirely
(`oidc.tf:36-38`), and oauth2-proxy can only allow or deny, so the *level* half
of a tier cannot reach a proxied app through it. Each app ticket picks its own
mechanism.

### F7, F12 and F13 are retired

`F7` split one policy across a human and a deployer and failed plan review
twice on the same fault: it was root-equivalent while presented as least
privilege, and its own eval guardrail certified the escalation green. `F12` and
`F13` were the second attempt at that split. All three died when the operator
collapsed the two roles.

Three measurements survive them and are folded into `F11`:

- **The Vault provider calls `auth/token/create` at configure time**, before it
  reads a single resource, and the live `default` policy does not grant it. It
  appears in no `vault_*` resource block. This killed `F7`'s policy twice.
- **`GET sys/mounts/auth/<path>` is required** for auth-mount tuning. Also in no
  resource block.
- **Narrowing `sys/policies/acl/*` to exact names does not stop escalation.**
  Vault resolves identity-group policies at request time, so any writable
  policy name plus group write is root in two steps. And `nomad/role/*` write
  is a second route entirely: flip a role to `type = management`, broker its
  creds, run a job that mounts `/opt/vault`. Both verified. This is why the
  collapse is the right call — the boundary was never enforceable while
  Terraform owned the privileged resources.

## Decisions locked, do not reopen without cause

Settled by the operator on 2026-07-31. Full reasoning in
`.loop/plans/D2-cli-login-broker-tokens.md` §12.

- **Token surface: a PATH shim**, not `env` and not `exec`. Forced by a
  measured constraint: `nomad` has no credential file. `NOMAD_TOKEN_FILE` does
  not exist, `nomad login` has no sink flag, and a child process cannot set
  its parent shell's environment.
- **`localstack login` writes `~/.vault-token`** at 0600. That file is inert
  while `VAULT_TOKEN` is set, and this devcontainer sets it for everyone, so
  `vault` gets a shim too. All three CLIs are shimmed, by `localstack deps
  --with-shims`. Removing the injected token is F8's job; until then the shim
  is what works.
- **The 32-day Vault token TTL is the design, not a defect.** It is the
  refresh token; the 30-minute brokered creds are the access tokens the shim
  refreshes. This withdraws the `token_ttl` task previously handed to the retired `F7` and
  drops `D2`'s `whoami` warning above 24 hours.
- **`localstack ui consul` is CUT, and the reasoning above it was wrong.**
  Consul's OIDC auth method is indeed Enterprise-only, but the conclusion
  "pasting a token is the only route" does not follow — measured 2026-08-01,
  the Consul UI needs **no** token: `consul.hcl.j2:29-32` puts the agent token
  on `tokens.default`, so unauthenticated requests return all 25 services and
  `/ui/` answers 200, directly and through the TLS edge. And an explicit token
  *replaces* that default rather than merging, so the brokered `deploy` token
  would cut the UI from 25 services to 2. The command degraded what it claimed
  to enable. `service consul --open` (D3) opens the URL and brokers nothing.

## The CLI's command surface, settled 2026-07-31

The rule: **the cockpit does what no native CLI can. It does not restate what
`vault kv list` and `nomad job status` already do.** A command earns its place
by spanning tools, by knowing something about this cluster the tools do not,
or by making the native tools work.

```
login | logout | whoami | env | token <svc> | config          D2
deps [--with-shims|--remove-shims]                            D6
status | service [<name>] | secret <service> | vault grants   D3
monitor                                                       D4
breakglass                                                    D5
```

Cut by that rule: `nomad jobs`, `nomad job <id>`, `vault mounts`,
`vault policies`, `vault policy <name>`, `vault kv`, `consul services`. Each
was a native command under a new name. `D6` puts the real CLIs on PATH, so
they are not even a fallback.

Also cut: `secret list|view|put`. Beyond duplicating `vault kv`, writing a
secret by hand creates drift that the next `terraform apply` reverts, because
every secret in this repo is a `vault_kv_secret_v2` resource. `secret
<service>` survives in a different form: which paths a job's templates read,
and whether each exists. Vault cannot say which job wants a path; Nomad cannot
say whether it is there.

`localstack ui consul` is folded into `service consul --open`. One verb.

Deliberately absent: anything that deploys, restarts, stops or edits. The
cockpit shows and authenticates. Changing the cluster stays in Terraform,
where it is reviewable.

This decision re-opened three eval markers (`D2`, `D3`, `D4`) and created two
(`G2`, `D6`). All five were re-signed on 2026-07-31.

Signing them surfaced two claims that the same day's applies had made false,
both about to ship under a signature. `D2` said F2 was unmerged and unapplied
and that `auth/userpass` did not exist; it is applied, so the rows marked
*needs F2 applied* are runnable. `D3` said F9 was unapplied and live Vault
served six policy blocks; it serves three. Both corrected. The 403 that `D2`
turns on is unchanged: the operator entity still carries no policy.

## Why N3 and N4 sit before the CLI

Measured 2026-07-31: Nomad, Vault, Consul and MinIO all answer 200 on
plaintext to any host on `192.168.0.0/16`, and haproxy's stats page serves an
unauthenticated map of every backend to the tailnet. The edge hostname is a
convention today, not a boundary.

`N4` closes that. It sits before `D2` because it changes every address this
repo uses: `.devcontainer/.env` and the Consul provider both point at raw IPs
over plaintext, and both move to the HTTPS edge. `D2`'s eval already demands
the CLI refuse to send a password in the clear and name the HTTPS edge, so
the CLI was designed for the post-`N4` world. Building it first would mean
building against addresses that are about to change.

`N3` comes first because neither provisioner removes a firewall rule.
Narrowing one adds a narrow rule beside the broad one, `ufw` matches the
broad one, and nothing closes. Without `N3`, `N4`'s Terraform half is a no-op
on the host while every config file reads correctly.

`N4` also creates a failure mode worth knowing before it exists: haproxy is a
Nomad job, and afterwards the only route to Nomad's API is haproxy. A dead
edge cannot be restarted through the edge. The escape is SSH to firebat and
`NOMAD_ADDR=http://127.0.0.1:4646`, which is why the ticket ships a runbook
and proves it by killing the edge and recovering from it.

### N4's decisions, settled 2026-07-31

- **The Ansible firewall role learns to reconcile**, deleting rules it no
  longer declares, mirroring what `N3` does for Terraform. A one-off
  `ufw delete` was rejected: it fixes today's rules and leaves the
  accumulate-only role intact, so the next narrowing hits the same bug.
  `ufw --force reset` was rejected outright, because it drops port 22 for the
  window between reset and re-apply, over the SSH connection doing the work.
- **haproxy's 8404 stats page is restricted to the Prometheus host** and the
  human stats UI is dropped. Prometheus scrapes it and Grafana renders it, so
  a second unauthenticated view of the same data is not worth an exposure.
  It must still answer **from** `192.168.2.47`: closing it to everything looks
  like success and breaks scraping, and the only symptom is an empty panel
  found days later.
- **No exception for the devcontainer.** It moves to the edge like everything
  else. An allowance for "the developer's machine" rests on a DHCP lease that
  will move to someone else.
- **haproxy keeps its ten explicit host ACLs.** No wildcard, no default
  backend. That list is the allowlist, and a wildcard plus a default backend
  would route unknown names somewhere instead of refusing them, inverting the
  point of the ticket. An unknown Host returns 503 today and must keep doing
  so.

The marker carries **30 rows** and none of the closures may be scored by
reading a config file, because neither provisioner removes a rule: the config
can read perfectly while the host is untouched. Every closure is proven from a
socket, from a host that is not a cluster node, against a response recorded
before the change.

## Known gaps this order does not close

- **The Consul UI never gets SSO.** Licensing, not design.
- **`F8` carries its own broken premise**: a brokered `client`-type Nomad
  token cannot manage the ACL policy that defines it. `F11` does not fix this,
  because `F11` grants Vault capabilities and this is a Nomad ACL limit.
  `F8`'s dependency now points at `F11`, but its body still argues from `F7` in
  27 places, so it needs a replan of its own, not an edit.
- **Consul's ACLs do not gate reads at all.** Measured 2026-08-01: raw HTTP
  with no token to `192.168.2.30:8500` returns all 25 services, all 5 nodes and
  all 41 health checks. `consul.hcl.j2:29-32` sets `tokens { default = <agent
  token> }`, so every unauthenticated request runs as the agent, and
  `default_policy = "deny"` never applies. Any Consul read role is therefore a
  subset of what anonymous already has. **This needs its own ticket** and is
  not covered anywhere below.
- **The `developer` Nomad ACL policy grants `alloc-exec` and
  `alloc-node-exec`**, and `G2` hands it to everyone in the bound Vault group.
  Ansible owns the policy (`nomad_server/tasks/main.yml:182-184`), so `G2`
  consumes it by name. Whether `alloc-node-exec`, which is exec on the node
  rather than an allocation, should be in it at all is undecided.
- **`D3`'s scope was justified by the `deploy` token's 403s.** Once `G2` lets
  a human hold a `developer`-scoped token, that justification weakens. Re-read
  `D3` after `G2` lands rather than implementing it as written.

## Superseding this file

Change the order here and say why. An order that drifts from the ledger
without a note is worse than no file, because the next reader cannot tell
which one is stale.
