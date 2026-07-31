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
| 1 | `F7-foundation-deployer-vault-oidc-login` | The only ticket that retires the root token. Everything else waits on its policy or is unrelated to it | Replan + plan review. Currently `blocked` |
| 2 | `D1-cli-package-skeleton` | Parallel track. Zero deps, touches no file `F7` touches | None. `planning`, eval signed |
| 3 | `D2-cli-login-broker-tokens` | Needs `F7`'s policy to do anything | `D1`, and `F7` in practice |
| 4 | `G2-nomad-ui-oidc-login` | Browser SSO for the one surface with no alternative | Eval marker needs sign-off |
| 5 | `G1-grafana-native-oidc-login` | Browser SSO where a working login already exists | None. `ready` |
| 6 | `F8-foundation-deployer-provider-cutover` | Terraform's Nomad and Consul providers onto brokered tokens | Replan. Currently `blocked` |
| 7 | `D3` / `D4` / `D5` | CLI surface on top of `D2` | `D2` |

`D1` can run concurrently with `F7`. Nothing else in this list should.

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
