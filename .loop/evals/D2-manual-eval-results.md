# D2 eval results

Every row was run. The offline rows run in the suite (157 tests, `just check`);
the live rows below were run against the real cluster through the TLS edge on
2026-08-02. Nothing was left behind: no leases at either creds path, and the
accessor count is back to its pre-run value.

## The guards, before any password is collected

```
localstack login --vault-addr http://192.168.2.30:8200
  -> exit 1, stdout EMPTY, no prompt
  -> "refusing to send a password to http://192.168.2.30:8200 in the clear.
      Use the TLS edge: --vault-addr https://vault.lab.orangecluster.nl"

localstack login --method oidc
  -> exit 1, "unsupported method 'oidc'. Only `userpass` is implemented."
```

The refusal fires **before** the prompt, so a refused address never collects a
password. Loopback `http://` is allowed; the parametrized offline test covers
`127.0.0.1`, `localhost` and `[::1]` against four non-loopback forms.

## A real login yields an entity-bearing token

```
localstack login --vault-addr https://vault.lab.orangecluster.nl
  -> exit 0, stdout EMPTY
  -> stderr: logged in as operator (351f302a-ada1-0e79-15d3-e22a4be2e3e4).
```

Non-empty `entity_id`, which is the property F2's userpass backend exists to
provide. The root token's is empty, so a row that only checked "a token came
back" would pass against a token nothing can gate on.

## Three credentials, three independent absolute expiries

```
version 1  method userpass  user operator
  vault   expires 2026-09-03T16:08:29.963478+00:00  renewable=True  lease=''
  nomad   expires 2026-08-02T16:38:30.008289+00:00  renewable=True  lease='nomad/creds/deploy/tXqReFsCcd7OLyR...'
  consul  expires 2026-08-02T16:38:30.055901+00:00  renewable=True  lease='consul/creds/deploy/9L9ykXylhDQF0p...'
distinct expiries: 3
```

A month for the Vault token against thirty minutes for the brokered pair. One
shared expiry would be wrong for at least two of the three. `renewable` is read
from each response, not assumed, and the Vault token carries no `lease_id`
because it is not a lease.

## Modes

```
session file 600   directory 700   ~/.vault-token 600
```

Set at creation through temp-file-plus-rename, not chmod-ed afterwards: a chmod
leaves a window in which the token is world-readable. The offline test asserts
no temp file survives the write.

## The brokered tokens are real and correctly scoped

```
nomad acl token self   -> Type = client
                          Name = vault-deploy-userpass-operator-1785686909996866200
consul acl token read  -> Description: Vault deploy userpass-operator 1785686910042438124
```

`nomad node status` with the brokered token returns 403, which is the `deploy`
policy's scope rather than a broken token — worth stating, because a 403 here
reads like a brokering bug and is not one. A `client`-type token cannot do ACL
management by design (`nomad_deploy_role.tf:39`).

## `env` emits both Consul spellings

```
export VAULT_TOKEN=hvs.CA…
export NOMAD_TOKEN=2d1d12…
export CONSUL_HTTP_TOKEN=6c8c97…
export CONSUL_TOKEN=6c8c97…
```

Both Consul names carry the same value. The binary reads only the first; the
repo's terraform recipes bridge the second by hand, so emitting one would break
half the tooling silently.

## `token <svc>` stdout is exactly the token

```
vault   96 bytes   nomad   37 bytes   consul  37 bytes
```

Token plus one newline, no banner and no styling. The offline tests assert
`result.stdout == expected + "\n"` byte for byte, and that every failure path
exits non-zero with **empty** stdout: no session, an expired session, a denied
broker, and an unknown service name. That is what makes D6's fall-through to
the bare binary safe.

One offline test guards the banner specifically: `main.py`'s callback returns
early for subcommands, and if that ever changed the banner would land on stdout
and every shim would break.

## `~/.vault-token` works, tested WITHOUT the environment token

```
env -u VAULT_TOKEN vault token lookup
  entity_id       351f302a-ada1-0e79-15d3-e22a4be2e3e4
  display_name    userpass-operator
  policies        ['default']
  identity_policies ['developer']
```

Tested with `env -u`, not with a bare `vault`, which would have passed against
the injected root token and proven nothing.

**This output is also why R8 reads `identity_policies`.** F11 binds through a
group, so `policies` holds only `default` while the actual grant sits in
`identity_policies`. An error message reporting `policies` would tell a
developer they have no grants at the moment they do.

## The developer is told they are still root

Fires on `login`, `whoami` and `logout`, on stderr, naming the other token's
policies:

```
WARNING: VAULT_TOKEN is set in this shell and is NOT this session's token.
  A bare `vault` command runs as that token, not as operator. It carries: root.
  Fix it for this shell:  eval "$(localstack env)"
  Or use the `vault` shim on PATH (installed by D6).
```

`whoami` also answers the question directly: `bare vault uses NOT this session`.
Offline tests cover the two silent cases, `VAULT_TOKEN` unset and equal to the
session token, because a warning on every healthy session trains people to
ignore it.

## No token value reaches stdout except through `env` and `token`

`whoami` prints accessors, entity and TTLs and no token value, grepped for all
three live token values: zero matches. `config` in both text and JSON: no
`hvs.` and no accessor-shaped material. Offline tests assert the same over
`login`, `logout` and the error paths, and that the password never reaches the
session file.

## `logout` revokes before it deletes, and the revoke cascades

```
localstack logout -> exit 0
session file gone      yes
~/.vault-token gone    yes
vault accessor         revoked
nomad ACL token        gone (cascaded)
```

Revoking the parent Vault token killed the child Nomad lease without the CLI
touching Nomad. Deleting the file alone would have left both brokered tokens
live for up to half an hour, which is the failure this ordering exists to
prevent. The offline tests cover the failure branch: when revocation fails the
files still go, the accessors print to stderr, and the exit is non-zero.

## Guardrails

- **No Terraform, no policy.** The branch diff touches `cli/`, `docs/` and
  `.loop/` only. No `deployments/**` and no `.tf`.
- **Nothing sets `CONSUL_HTTP_TOKEN_FILE`.** `grep -r` over the diff: no match.
  The file outranks `CONSUL_HTTP_TOKEN` and a missing one makes `consul` fail
  outright, so an unowned export would break the tool for everyone. Consul gets
  a shim instead.

## Cluster left clean

```
sys/leases/lookup/nomad/creds/deploy    No value found
sys/leases/lookup/consul/creds/deploy   No value found
accessors: 14 jwt-nomad, 10 userpass/operator, 1 root
```

Same counts as before the run: the login added one session and the logout
revoked it. Two probe leases minted earlier while measuring the response shapes
were revoked at the time.

## Fixes applied after review, and what proved them

Five defects were found after the first stamp: three by my own audit of the
failure paths, two by the documentation review. All five are fixed and the
tree was re-stamped.

### Three orphaned-credential defects, one class

**`login` orphaned the session it replaced.** It overwrote `session.json`
without revoking, so logging in twice left the first Vault token live for its
full TTL with nothing holding a reference. Not hypothetical: the live cluster
carries ten sessions at `auth/userpass/login/operator`, spanning three days,
three of them minted inside the same minute, each carrying `developer` with
about a month left. Now `login` revokes the previous session first. Proven:

```
first session accessor:  KIu9tvcztD9Pt0APVUWkXgkP
  -> "revoked the previous session for operator."
second session accessor: eZhyzUw9W9fSmVQXEVsDPp2J
first accessor still live?  no, revoked
accessors after logout:     25   (same as before the run)
```

Before the fix that sequence left one orphan behind. It now nets to zero.

**`login` orphaned its own token when brokering failed.** It minted a real
Vault token, then exited non-zero without saving the session or writing
`~/.vault-token`, so every retry against a missing grant added another
untracked credential. It now revokes on the way out and says so.

**`logout` left `~/.vault-token` behind when the session file was already
gone.** The first attempt at this deleted the file, which was wrong twice
over: with no session there is no token to revoke it WITH, so deleting drops
the only local reference to a credential that stays live on the cluster, and
`vault login` writes that same path so the file may not be this CLI's at all.
It now reports the file, refuses to delete it, and prints the command that
ends it properly.

### `whoami` reported the misleading policy list

It printed `token_policies`, so the live run showed `policies  default` for a
token that resolves `developer`. That is the exact misreading R8 forbids in
the 403 message, reproduced in the command a developer runs to check their own
grants.

Measured what a login actually returns rather than guessing, and the fix
needed no extra request:

```
policies         : ['default', 'developer']    <- the union Vault resolves
token_policies   : ['default']                 <- what was being stored
identity_policies: ['developer']               <- what was missing
```

The test fixture was wrong in the same way and now carries all three keys.

### The doc's headline command did not run

`docs/cli-login.md` opened with a bare `localstack login`, which exits 1
against the current default `VAULT_ADDR` because R2 refuses plaintext, and the
page never mentioned the refusal, `--vault-addr` or `--insecure`. Written from
memory rather than from the command actually run in the live rows above, which
used the `--vault-addr` form throughout. Same defect class as F14's
runbook-command-never-run.

Also corrected: `README.md` still described the CLI as "skeleton only today";
`docs/vault-human-auth.md` hardcoded "all 14 workload tokens", the drift class
already fixed for the accessor count; and `cli-login.md` billed itself as the
whole revocation runbook while omitting the ACL cache lag.

### The cache lag, measured off the live agents

```
Nomad  ACL.TokenTTL                          30000000000 ns  = 30s
Consul ACLResolverSettings.ACLTokenTTL       30s
Consul ACLResolverSettings.ACLDownPolicy     extend-cache
```

A deleted Nomad or Consul token keeps working for up to 30 seconds, and under
`extend-cache` Consul honors it for as long as the ACL servers stay
unreachable, which is the condition an incident tends to produce. Now in the
revocation section.

### The tests constrain the code

Mutation-tested the two contracts claimed load-bearing. Prefixing `token`'s
stdout with `token: ` killed four tests; dropping the equality check from the
`VAULT_TOKEN` shadowing warning killed two. Six deaths, in the right places,
sources restored afterwards.


## A second review round, and what it caught

The adversarial pass found that fix 1 had regressed the failed-login path.
`login` revoked the previous session BEFORE attempting the new one, so a
mistyped password destroyed a working session and left the cache holding a
dead token. The next command then reported a missing F11 grant on a cluster
where the grant is fine, which is the misdiagnosis R8 exists to prevent.
`_revoke_previous()` now runs only after both the login and the brokering
succeed, so a failure at either step leaves the existing session untouched.

It also found three surviving mutants where the tests did not constrain the
code. All three are now covered, and the fourth case above with them:

| Mutation | Now killed by |
| --- | --- |
| `session.save` opens 0644 then chmods | `test_save_sets_the_mode_at_creation_not_afterwards` |
| `vault_token_file.write` opens 0644 then chmods | `test_write_sets_the_mode_at_creation_not_afterwards` |
| `logout` deletes before revoking | `test_logout_revokes_BEFORE_it_deletes` |
| `login` revokes the old session before the new login | `test_a_failed_login_leaves_the_existing_session_untouched` |

The two mode mutations matter because the FINAL mode is `0600` either way, so
no assertion on the finished file can tell them apart. The tests observe the
creation call instead. A test named
`test_write_never_leaves_a_world_readable_window` claimed to check exactly
this and did not; it is renamed to what it actually does and the real check
sits beside it.

Planted all four at once and re-ran: five failures, in the right places.

The `cluster`-marked live tests the plan asked for now exist, in
`cli/tests/auth/test_live_login.py`: seven rows covering the entity-bearing
token, the three distinct expiries, the brokered tokens against real Nomad and
Consul, `token`'s stdout, the plaintext refusal, the revoke cascade, and the
second-login revoke. They are excluded from the default run and each uses a
throwaway `HOME`, so a live run never touches the developer's own session and
adds no accessors to the cluster.