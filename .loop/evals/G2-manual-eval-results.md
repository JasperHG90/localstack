# G2 manual eval rows — the half that needs a browser

Five rows in `.loop/evals/G2-nomad-ui-oidc-login.md` cannot run headless. This
file records them, next to the marker it belongs to.

Cluster state when these were run: auth method `vault` (OIDC, global, 8h),
one binding rule `g2-nomad-ui` binding `"developer" in list.groups` to Nomad's
`developer` policy. It was registered `default = true` at the time; that was
removed afterwards as untraceable to the ticket. No result here depends on
it: the UI lists methods either way, and `nomad login -method=vault` names it.

---

## Row 1 — UI login yields a token carrying `developer` — **PASS**

Signed in at `https://nomad.lab.orangecluster.nl/ui/settings/tokens`.

Confirmed server-side, not just in the UI:

```
$ nomad acl token list -json
OIDC-vault | client | ['developer'] | expires 2026-08-02T14:47:31Z
```

8h expiry matches `max_token_ttl`. Token type `client`, not management.

### Known wrinkle: the first attempt fails

**Observed 2026-08-02: the first sign-in returned "Failed to sign in with
SSO — Your OIDC provider has failed on sign in", leaving an Anonymous
Token. An immediate retry succeeded with no configuration change.**

Not yet root-caused. The likeliest explanation is the Vault UI session: the
`lab` provider's authorize endpoint is a Vault **UI** path, so the browser must
already hold a Vault UI session. Without one you are bounced to Vault's login
screen, and the OIDC state or nonce generated for the first attempt is stale by
the time you get back. The second attempt starts with the session in place and
completes.

If that is the cause it is a first-login-only papercut, not a defect, but it is
the first thing a new developer will hit. **Do not close G2 claiming a clean
login without either reproducing this from a fresh browser profile or writing
it into the docs.**

---

## Row 2 — the `groups` claim arrives — **PASS, by inference**

Not decoded directly. Recorded honestly rather than marked green.

The binding rule selector is `"developer" in list.groups`, and
`list_claim_mappings` maps `{groups = "groups"}`. If the claim had not arrived,
or the pair were crossed, the login returns `400 no role or policy bindings
matched` and issues **no token** — measured on Nomad 2.0.4, guarded in both
the OIDC and JWT paths of `acl_endpoint.go`. A green login with an empty policy
list is unreachable here.

Row 1 produced a token whose `Policies` is `['developer']`. That is only
possible if the selector matched, which is only possible if the claim arrived
as a real list.

To decode it properly you would run a direct Vault authorize/token exchange
with the `nomad` client and base64-decode the id_token's payload, checking
`groups` is a JSON array and not the string `"null"`. Nomad consumes the
id_token internally and never surfaces one, so this cannot be done through
Nomad.

---

## Row 3 — `nomad login` from a terminal — **PASS**

```
$ export NOMAD_ADDR=https://nomad.lab.orangecluster.nl
$ nomad login -method=vault
Successfully logged in via OIDC and vault
Name     = OIDC-vault
Type     = client
Global   = true
Expiry   = 2026-08-02 14:52:11 UTC
Policies = [developer]
```

**Transcript abridged: the real output also carries `Accessor ID` and
`Secret ID` lines.** They are cut here deliberately, which is the point the
paragraph below makes — the token from this run had to be revoked because its
Secret ID reached a session transcript.

The CLI callback round trip works, so `http://localhost:4649/oidc/callback` is
correctly registered on both the Vault client and the Nomad auth method.

### Two papercuts worth documenting

**`nomad login` prints the Secret ID in full** by default. A script can select
fields with
`-t '{{ .AccessorID }}'`; the bare invocation used above does not. `-json`
also exists but marshals the whole token object and was not checked for
whether it carries the Secret ID.
`nomad acl token self` is the command with neither flag. Anyone pasting
terminal output into a ticket,
a chat or a transcript leaks a live `developer` token, which carries
`alloc-exec`, `alloc-node-exec` and write on every host volume. Treat login
output as a secret and revoke if it escapes:

```sh
nomad acl token delete <accessor id>
```

**`xdg-open` is missing in the devcontainer**, so the automatic browser launch
fails:

```
Error opening OIDC provider URL: exec: "xdg-open": executable file not found in
$PATH
```

Not fatal. Nomad prints the URL and waits, so pasting it into any browser
completes the flow. Worth a docs line so the error is not read as a broken
login.

A near miss to note: `-method=vaul` (typo) returns `method vaul not found in
the state store`, which is a clear failure rather than a silent fallback.

---

## Row 4 — a non-member is denied — **PASS**

A `g2probe` userpass user with its own entity, in **no** group, attempted the
Nomad UI sign-in. Nomad issued an Anonymous Token and the callback carried:

```
error=access_denied
error_description=identity entity not authorized by client assignment
```

**Vault refused at the assignment**, before Nomad ever saw an authorization
code. That is the intended layer: the gate is
`vault_identity_oidc_assignment.nomad`, which lists only F11's `developer`
group. No token was issued.

The error is specific and names the mechanism, which also distinguishes a real
denial from row 1's generic "Failed to sign in with SSO". The two failures are
not confusable.

### The teardown found a live orphan, as predicted

Logging into the Vault UI as `g2probe` minted a Vault token before Nomad
refused the OIDC step. Revoking by accessor first caught it:

```
revoking RETSqW2znrRkBF4q7VFa6jO9  userpass-g2probe  0190c271-...
revoked: 1
```

Had the user and entity been deleted first, that token would have outlived both
— which is exactly the failure a previous run left behind for 30.6 days. The
order is not ceremony.

Cleanup verified: `operator` is the only userpass user, the entity resolves to
"No value found", accessors back to 22.

---

## Row 5 — the exec grant is real — **PASS**

```
$ nomad alloc exec -task prometheus 32c9bf00 /bin/sh -c 'hostname; id'
ubuntu
uid=0(root) gid=0(root) groups=10(wheel)
```

**Root inside a running container, from a token obtained by signing in.**

`ubuntu` is the Nomad **node** name (`nomad node status`), inherited by the
container. This is root in the container, not on the host. Do not report it as
host root without measuring that separately.

### What the grant actually reaches

The demonstration matters more than the shell. `developer` combines
`submit-job`, `alloc-exec`, `alloc-node-exec` and
`host_volume "*" { policy = "write" }`. A signed-in developer can submit a job
mounting any host volume read-write and exec into it as root. Measured on this
cluster, those volumes are:

```
postgres, minio_data, grafana_data, loki_data, memex_data,
hermes_data, nats_data, prometheus_data, acme_lego_state
```

That is the cluster's persistent state: the Postgres data directory, the MinIO
object store, the ACME account key. "A shell in a container" understates it.

**None of this is new.** The `developer` policy predates G2 and is Ansible's
(`bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl`). What G2
changes is the route: reaching that policy used to mean someone handing you a
token, and now it means signing in. That is the widening the plan requires
stated plainly. **Fixed**: `docs/vault-human-auth.md` now names all three
grants and the volumes they reach, under "What the operator can do".

---

## Found while applying the review fixes: a two-phase apply hazard

Not an eval row, recorded here because it will cost someone an hour otherwise.

**Changing `vault_policy.developer` makes the next full apply fail:**

```
Error: error checking for ACL Auth Method "vault": ... 403 Forbidden
```

**Fixed during this ticket by removing the `depends_on`; the account below is
what it did while present.** It sat on the `vault_nomad_access_token.manage`
data source and deferred its read to apply time whenever the policy had a
pending change. But Terraform refreshes the existing
`nomad_acl_auth_method` first, and configures the aliased provider from state,
which holds the previous run's token — already expired at the mount's 30m
lease. The refresh then authenticates with a dead credential.

Workaround, measured 2026-08-02:

```sh
terraform apply -target=vault_policy.developer
terraform apply
```

It does not appear on a first apply against empty state, because there is
nothing to refresh. An earlier review measured exactly that case and reported
"no two-phase apply" in good faith; both findings are true of the case each was
measured in. Documented at length in `nomad_oidc.tf`.

---

## Summary

| Row | Result |
|---|---|
| 1 — UI login yields `developer` | pass, confirmed server-side |
| 2 — `groups` claim arrives | pass, by inference from row 1 |
| 3 — `nomad login` from a terminal | pass |
| 4 — non-member denied | pass, refused at the assignment |
| 5 — the exec grant is real | pass |

All five pass. Members get in and non-members are refused at the Vault
assignment, so the gate is real rather than open. What remains before commit is
the reviewer's fix list, not the evidence.

---

## A note on running these

Do not run bare `nomad acl token self` — it prints the Secret ID in full. Read
only what you need:

```sh
nomad acl token self | grep -E '^(Type|Global|Policies|Expiry)'
```

`nomad acl token self` has no `-t` and no `-json` flag; both fail with `flag
provided but not defined` before any network call.
