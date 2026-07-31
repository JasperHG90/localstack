# Pickup order

**F7 first, D1 alongside it. Not the CLI.** Settled 2026-07-31.

The goal driving this order is retiring the Vault root token. `F7` delivers
that on its own, without any CLI. The `localstack` CLI is convenience layered
on top of the policy `F7` writes, and it is inert until that policy exists.

This file records the order and the reasoning behind it so neither gets
re-litigated. The ledger (`loopctl ledger`) remains the source of truth for
ticket **state**; this file is only about **sequence**.

## The order

| # | Ticket | Why here | Gate before pickup |
|---|--------|----------|--------------------|
| 1 | `F7-foundation-deployer-vault-oidc-login` | The only ticket that retires the root token. Everything else waits on its policy or is unrelated to it | **Replan + plan review.** `blocked` |
| 2 | `D1-cli-package-skeleton` | Parallel track. Zero deps, touches no file `F7` touches | Clear |
| 3 | `N3-netsec-converging-firewall-provisioner` | Prerequisite for `N4`: without it, narrowing a firewall rule leaves the broad one live | Clear. `ready` |
| 4 | `N4-netsec-edge-only-service-access` | Closes direct LAN access to every service. Lands before `D2` so the CLI is built against edge addresses | `N3` done. **Eval unsigned** |
| 5 | `D2-cli-login-broker-tokens` | Needs `F7`'s policy to do anything | `D1`, and `F7` in practice |
| 6 | `D6-cli-deps-and-shims` | Without the shims a bare `nomad` cannot see the session, so `D2` is half-delivered | `D1` |
| 7 | `G2-nomad-ui-oidc-login` | Browser SSO for the one surface with no alternative | Clear |
| 8 | `G1-grafana-native-oidc-login` | Browser SSO where a working login already exists | Clear. `ready` |
| 9 | `F8-foundation-deployer-provider-cutover` | Terraform's Nomad and Consul providers onto brokered tokens | **Replan.** `blocked` |
| 10 | `D3` / `D4` / `D5` | CLI surface on top of `D2` | `D2` |

Eval markers: D1 to D6, G1, G2 all signed and reporting `valid` as of
2026-07-31. **`N4` is the only unsigned one.** The two real gates left are
that signature and F7's replan.

`D1` can run concurrently with `F7`. Nothing else in this list should.

`D6` sits directly after `D2` because the two only work together: `D2` brokers
the tokens and `D6` installs the shims that let a bare `nomad` command use
them. Shipping `D2` alone leaves the developer typing `eval` by hand, which is
the option the operator rejected.

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
creds paths. That policy is F7's deliverable, not D2's."*

Built first, `D2` is four commands that log in successfully and do nothing.

If "CLI first" means `D1`, that is fine and it is item 2. If it means `D2`, it
is premature by exactly one ticket.

## Why F7 is smaller than it looks

Its plan describes building a `vault_jwt_auth_backend` in OIDC mode plus a
role. **That half is dead.** The operator chose `userpass`, and `F2` shipped
it on 2026-07-31. What remains is one scoped `vault_policy` and a binding to
the operator entity or a group.

Three of its seven required fixes are already answered:

- Which `sys/*` paths need `sudo`. Measured, not assumed: only `sys/auth/*`.
  `sys/mounts/*` needs an ordinary grant on Vault 2.0.3. Recorded in F7's
  `## Measured evidence, 2026-07-31`.
- The login-method fork. Settled as `userpass`.
- The `token_ttl` task. Withdrawn, see below.

What the replan still owes: the eval marker. Its row 3 asserts that
`vault write sys/policies/acl/xyz` returning 403 proves correctness, when the
deployer must be able to write that path. The marker certifies the broken
result green, so fixing the plan without fixing the marker fixes nothing.

## Decisions locked, do not reopen without cause

Settled by the operator on 2026-07-31. Full reasoning in
`.loop/plans/D2-cli-login-broker-tokens.md` §12.

- **Token surface: a PATH shim**, not `env` and not `exec`. Forced by a
  measured constraint: `nomad` has no credential file. `NOMAD_TOKEN_FILE` does
  not exist, `nomad login` has no sink flag, and a child process cannot set
  its parent shell's environment.
- **`localstack login` writes `~/.vault-token`** at 0600. It is why the stock
  `vault` CLI needs no shim.
- **The 32-day Vault token TTL is the design, not a defect.** It is the
  refresh token; the 30-minute brokered creds are the access tokens the shim
  refreshes. This withdraws the `token_ttl` task previously handed to `F7` and
  drops `D2`'s `whoami` warning above 24 hours.
- **Consul UI gets `localstack ui consul`**, which brokers a token, copies it
  to the clipboard, prints it as a fallback, and opens the UI. Consul's OIDC
  auth method is Enterprise-only and this cluster is Community Edition, so
  pasting a token is the only route. No design removes that.

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
  token cannot manage the ACL policy that defines it. Replanning `F7` does not
  fix `F8`.
- **A live `developer` Nomad ACL policy is owned by no `.tf` file.** It grants
  `alloc-exec` and `alloc-node-exec`. `G2` Q1 makes resolving it part of that
  ticket.
- **`D3`'s scope was justified by the `deploy` token's 403s.** Once `G2` lets
  a human hold a `developer`-scoped token, that justification weakens. Re-read
  `D3` after `G2` lands rather than implementing it as written.

## Superseding this file

Change the order here and say why. An order that drifts from the ledger
without a note is worse than no file, because the next reader cannot tell
which one is stale.
