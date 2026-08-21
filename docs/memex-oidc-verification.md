# Verifying memex OIDC (workloads and humans)

memex authenticates two kinds of caller without a static key: WORKLOADS
(hermes, via a Nomad Workload Identity JWT) and HUMANS (via `memex auth
login` against the Vault `lab` provider). This runbook holds the checks that
prove both, including the denials. Run them after a deploy that touches the
memex auth config, the hermes `identity` stanza, the hermes image, or the
Vault OIDC client.

Checks are grouped: S* server-wide, W*/D*/H* the workload path, V* the human
path, G* guardrails.

Most failure modes here are **silent**: the request still returns `200`
because hermes falls back to its API key, which is deliberately still
present. So several checks below assert on a log line, or on the absence of
one, rather than on a status code.

That fallback is narrower than it looks. It applies only when the bearer
fails to resolve at all (no token file, or config that will not validate).
Once a bearer resolves, the client sends it and nothing else, so a token
memex rejects is a hard failure with no second credential behind it.

Addresses: memex is `http://192.168.2.46:8000`. The workload issuer is
`https://nomad.lab.orangecluster.nl`; the human issuer is
`https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`.

## S1: the server loaded both providers

```
nomad alloc logs <memex-alloc> memex | grep -i 'authentication enabled'
```

Expect both lines, and expect the count to be `2`:

```
OIDC bearer-token authentication enabled (2 provider(s)).
API key authentication enabled (3 key(s) configured, 3 exempt path(s)).
```

`2`, not `1`: element 1 is the Nomad issuer for workloads, element 2 the
Vault `lab` issuer for humans. BOTH must be present. A count of `1` means one
element failed to parse and was dropped. A **missing** OIDC line means the JSON in
`MEMEX_SERVER__AUTH__OIDC` failed to parse and the provider was dropped
silently. That is the cheapest failure to catch, which is why this check
runs first.

## S2: API-key access still works

```
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.2.46:8000/api/v1/vaults
curl -s -o /dev/null -w '%{http_code}\n' -H 'Authorization: Bearer garbage' http://192.168.2.46:8000/api/v1/vaults
curl -s -o /dev/null -w '%{http_code}\n' -H "X-API-Key: $MEMEX_ADMIN_KEY" http://192.168.2.46:8000/api/v1/vaults
```

`MEMEX_ADMIN_KEY` is the `admin_key` field of the memex auth secret in Vault
(written by `vault_kv_secret_v2.memex_auth_keys`,
`deployments/applications/secrets.tf:79-86`):

```
export MEMEX_ADMIN_KEY=$(vault kv get -field=admin_key secret/default/memex/auth)
```

(`secret` here is `var.secret_mount`. The real `vars/prod.tfvars` is
gitignored; `deployments/applications/vars/prod.tfvars.example:1` shows the
value. Substitute if yours differs.)

Expect `401` / `403` / `200`, unchanged from before the rollout. Run this
again at the end: it is the regression check, and the static keys are meant
to keep working.

## W1: a hermes token is accepted

W1 decodes the JWT Nomad wrote and presents it to memex by hand. It proves
the token itself is good, independently of whether the hermes client is
wired up.

**There is no "before the client config" window, so do not look for one.**
The `identity` stanza and the three `MEMEX_OIDC__*` vars all render from one
`templatefile` into one `nomad_job.hermes`, so any apply that touches hermes
lands them together. `-target` separates memex from hermes; it cannot
separate hermes from itself.

That changes what a W1 failure costs. Once the bearer **resolves**, the
client sends only `Authorization` and never falls back to `X-API-Key`, so a
403 here is an outage, not a free probe. (The fallback survives only where
the bearer does NOT resolve at all, which is precisely what H2 hunts for.)
Two consequences:

- **Apply memex first and let it come up**, then hermes:
  `just apply true nomad_job.memex` (the two arguments are positional,
  `refresh` then `target`; the recipe wraps the tfvars and Consul token that
  a bare `terraform apply` here lacks), then a full
  `just apply`. The two jobs share no Terraform dependency edge, so an
  untargeted apply sends them in parallel, and hermes will 403 against the
  old memex alloc until the new one is healthy.
- **Run W1 immediately after the hermes apply**, as the first thing you
  check. It isolates "is the token good" from "is the client wired up",
  which is what makes H1 and H2 readable afterwards. If W1 fails, hermes has
  already lost memex access, so treat it as a rollback signal rather than a
  diagnostic step.

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import base64,json,pathlib;\
p=pathlib.Path('/secrets/nomad_memex.jwt').read_text().split('.')[1];\
print(json.dumps(json.loads(base64.urlsafe_b64decode(p + '=' * (-len(p) % 4))), indent=2))"
```

(Decode in python, not `base64 -d`. A JWT segment is unpadded base64url, so
`base64 -d` errors with `invalid input` for three of every four payload
lengths.)

Decode, do not assume. Assert `iss` is `https://nomad.lab.orangecluster.nl`,
`aud` contains `memex`, and `nomad_job_id` is `hermes`. Then, from the same
alloc:

```
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $(cat /secrets/nomad_memex.jwt)" \
  http://192.168.2.46:8000/api/v1/vaults
```

Expect `200`.

## D1: a token for another audience is refused

Register a throwaway job carrying a second identity:

```hcl
identity {
  name     = "vault_default"
  aud      = ["vault.io"]
  file     = true
  filepath = "secrets/nomad_vault_default.jwt"
}
```

Present that token to memex. Expect `403`, **and** the memex log to carry:

```
OIDC token rejected for issuer ...
```

Match on the message text, not the level word: this line moved from `info` to
`warning` at v1.2.0, where every refusal logs at `warning`.

(`nomad job validate` warns "identity called vault_default but no vault
block" on this shape. Expected and harmless.)

## D2: a token from another job is refused

From the same throwaway job, present its `aud = ["memex"]` token.

Expect `403`, but from the **authorization** path, not the signature path.
The token verifies, matches no `grant_rule`, and `default_policy` is unset.

**Assert this on the server log, not the response.** memex renders "bad
signature" and "valid token that maps to no policy" as the identical
`403 {"detail": "Invalid API key or bearer token."}`, so the response cannot
tell you which one you got. The discriminator:

- D1 emits `OIDC token rejected for issuer ...`
- D2 emits `OIDC token verified for issuer ... but matched no grant_rule and
  the provider has no default_policy, so it authorizes nothing.`

**This polarity flipped at memex v1.2.0, and the old rule is now backwards.**
On v1.1.0 this path returned `None` with no log call, so SILENCE was the
pass. v1.2.0 logs it explicitly. Against a v1.2.0 server, silence here is a
FAILURE: it means the request never reached the authorization path, so you
are looking at a signature or issuer problem wearing the same 403.

This is the check that proves every other job in the cluster is not
implicitly a memex admin, so do not skip it.

Tear the throwaway job down afterward.

## H1: the client sends the bearer, not the key

```
nomad alloc exec -task hermes <hermes-alloc> \
  /opt/hermes/.venv/bin/python -c "import asyncio;\
from memex_common.config import MemexConfig;\
from memex_common.auth_client import resolve_client_headers;\
print(asyncio.run(resolve_client_headers(MemexConfig())))"
```

Expect `{'Authorization': 'Bearer eyJ...'}`. An `X-API-Key` key in that dict
means the bearer did not resolve and hermes silently stayed on the key.

Use the venv interpreter, not a bare `python`. The memex wheels install into
`/opt/hermes/.venv`.

## H2: no silent downgrade

Two greps, kept separate on purpose (a single alternation written with an
escaped pipe matches nothing under `grep -E`, which would make this check
vacuous):

```
nomad alloc logs <hermes-alloc> hermes | grep -i 'workload token file'
nomad alloc logs <hermes-alloc> hermes | grep -i 'Falling back to X-API-Key'
```

Expect **no output from either**. They come from different faults:

- `Could not read workload token file ...`: `MEMEX_OIDC__TOKEN_FILE` points
  somewhere the file is not.
- `Falling back to X-API-Key client (shared memex config unusable): ...`:
  the OIDC config is present but fails validation.

Either line means hermes is back on the API key while requests still return
`200`.

## H3: both sandboxes get the credential

Through the hermes agent, run the H1 one-liner twice: once via the terminal
tool, once via code_execution. Both `env_passthrough` lists must carry the
three `MEMEX_OIDC__*` names; updating only one is silent.

Expect `{'Authorization': 'Bearer ...'}` in **both**. Checking `env | grep
MEMEX_OIDC` is necessary but not sufficient. The vars can be present while
the token file is unreadable to that subprocess, which is the same silent
shape as H2.

## Then re-run S2

The static keys must still work. They are what makes a *misconfiguration*
recoverable: if the bearer never resolves, hermes keeps running on the key.
They do not rescue a bearer that resolves and is then rejected, so S2 is a
regression check on the keys themselves, not a safety net for the checks
above.

## V1: a human in the reader tier can read, and cannot write

Run on your LAPTOP, not in the devcontainer: `memex auth login` binds an
ephemeral loopback port, and a host browser cannot reach a container's
`127.0.0.1`.

Config lives at `~/.config/memex/config.yaml`:

```yaml
oidc:
  issuer: "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
  client_id: "<the memex client_id>"
  credential: "id_token"
  scopes: ["openid", "groups"]
```

**Log into the Vault UI first, in the same browser.** Vault's
`authorization_endpoint` is the UI path, so an unauthenticated browser lands
on the login screen and never redirects back. The CLI does not error: it
waits out its 300s callback timeout and reports something that names no
cause.

```
memex auth login
memex auth status
```

Then decode the cached id_token from `token.json` in the memex user config
dir and assert `iss` matches the issuer above, `aud` equals the client id
(NOT `memex` — an id_token's `aud` carries the client id), `groups` contains
`app-memex-readers`, and **`groups` does NOT contain `app-memex-admins`**.

That last clause is the precondition for the write assertion below, and it
is easy to lose. The resting state after this ticket puts the operator in
BOTH tiers, so re-running V1 later — as this runbook's header tells you to
after any memex auth deploy — will correctly resolve to `admin` and the
write will NOT be refused. Check the claim before reading the result.

- READ `GET /api/v1/vaults` returns `200`.
- WRITE `PATCH /api/v1/notes/<random-uuid>/title` returns **`403`**, and the
  `403` is the whole point. That route is guarded by `require_write`, which
  `reader` does not hold, so the gate fires before the handler and the
  fabricated uuid mutates nothing. **Given a reader-only token, anything
  else means the tier resolved ABOVE `reader`**: a `404` or `422` says the
  handler ran, so the write gate let you through and the grant is wrong. Do
  not read a non-403 as "the write failed, good". If the token carries
  `app-memex-admins`, this is V5, not V1.

## V2: the opaque access token is refused

From the same `token.json`, present the `access_token` field as the bearer
instead of the id_token.

Expect `403` and:

```
OIDC bearer rejected: not a parseable JWT (2 dot-separated segments).
```

Two, not one: Vault's batch token is `hvb.` + base64url, and memex logs
`token.count('.') + 1`. Confirm the count against the token you actually got.

This is the one-line diagnosis of a client that forgot `credential:
id_token`, and it is the exact failure that made the human path impossible
before memex v1.2.0.

## V3: the Vault-side gate is live

Read-only, no login needed, but **use a token with NO identity entity (a root
token)**. The expected `access_denied` fires only where the request carries
no entity. With your own operator token both the entity and assignment checks
pass and Vault returns a `code=` redirect instead, which is a false alarm and
also mints an auth-code entry, so the probe stops being read-only.

```
curl -sk -H "X-Vault-Token: $VAULT_ROOT_TOKEN" -G \
  "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab/authorize" \
  --data-urlencode "client_id=<the memex client_id>" \
  --data-urlencode "redirect_uri=http://127.0.0.1:44444/callback" \
  --data-urlencode "response_type=code" --data-urlencode "scope=openid groups" \
  --data-urlencode "state=abcdefghij" --data-urlencode "nonce=abcdefghij" \
  --data-urlencode "code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM" \
  --data-urlencode "code_challenge_method=S256"
```

Expect `{"error":"access_denied","error_description":"identity entity must be
associated with the request"}`. Reaching that error proves the client, the
redirect, the provider list and the scope all resolved: Vault checks those
before it checks the entity.

## V4: a human token with NO `groups` claim is refused

Log in a second time with `scopes: ["openid"]` only, dropping `groups`.

**Login SUCCEEDS.** Vault ignores an unsupported scope rather than erroring,
so you get a perfectly valid signed token that simply carries no `groups`
claim. That is this design's likeliest silent failure, and nothing else
detects it: D2 presents a Nomad workload token, so no Vault id_token ever
travels that path.

Present that id_token. Expect `403`, and confirm on the D2 log line that it
came from the authorization path, not a signature failure.

Restore `scopes: ["openid", "groups"]` and re-run V1 afterwards, so the
working config is what is left in place.

## V5: a member of BOTH tiers lands on admin

Add your entity to `app-memex-admins` in `local.app_user_group_members` (a
reviewed Terraform edit) and apply, so you are in both tiers. Log in again
and perform an admin-only operation.

Assert all three:

- the decoded `groups` claim contains BOTH `app-memex-admins` and
  `app-memex-readers`;
- `PATCH /api/v1/notes/<random-uuid>/title` returns something OTHER than
  `403` (a `404` or `422` from the handler, since the uuid is fabricated).
  **A `403` here means the reader rule matched first**, the two rules are the
  wrong way round in `MEMEX_SERVER__AUTH__OIDC`, and every admin who is also
  a reader has been silently downgraded;
- `GET /api/v1/vaults` returns `200`.

memex takes the first matching `grant_rule` and stops, and
`app-memex-admins` is listed first, which is the only reason dual membership
resolves to `admin`.

## V6: the session really lasts 30 days

Immediately after login, read `expires_at` from `token.json`.

Expect roughly 30 days out, NOT roughly one hour. The client caches
`min(now + expires_in, id_token exp)`, and Vault returns `access_token_ttl`
as `expires_in` — so a short `access_token_ttl` silently truncates the
session and drops you back to the API key, with every request still `200`.
Both TTLs are 30 days for this reason.

## G1-G5: guardrails

- **G1 — static keys survive.** `MEMEX_SERVER__AUTH__KEYS` in `memex.hcl`,
  `MEMEX_API_KEY` in `hermes.hcl` at both sites. Removal is a follow-up.
- **G2 — hermes's own grant is unchanged.** As of the auth-config extraction
  (`deployments/applications/services/memex/auth_oidc.json`, parsed and
  re-injected by a `services.tf` local), Terraform's `jsonencode` sorts
  object keys, so a byte/substring match against the rendered
  `MEMEX_SERVER__AUTH__OIDC` no longer holds even when nothing changed.
  Assert JSON equality instead: element 0 still carries the Nomad issuer and
  `"audience":["memex"]`, and its `grant_rules` still contains
  `{"claim":"nomad_job_id","policy":"admin","value":"hermes"}` (key order
  aside) as one of its entries.
- **G2b — element 0 now also grants `leo-consumer`.** A second `grant_rule`,
  `{"claim":"nomad_job_id","policy":"writer","value":"leo-consumer"}`, was
  added alongside hermes's. No `vault_ids` field: per memex's own config
  schema, that means unrestricted, i.e. `writer` on every vault. `writer`
  bundles read with write (`POLICY_PERMISSIONS` in memex's
  `memex_common/config.py` has no write-only policy, and `vault_ids` /
  `read_vault_ids` only scope *which* vaults a policy's permission bundle
  applies to, never *which* permissions apply) — so this grant can also
  **read** every vault, not just write. That's a deliberate tradeoff: a
  scoped, write-only grant isn't expressible in memex 1.2.0's policy model.
  **No W-series check exists for this yet** — the leo-consumer Nomad job
  doesn't exist in this repo or cluster today. Before relying on this
  grant: confirm the actual job id matches the `value` here (a mismatch
  fails safe — D2's silent-403 path — but is easy to miss without a check),
  and once the job's `identity` stanza lands, add a W-series check
  mirroring W1 against its token.
- **G3 — the provider list was appended, not replaced.** Every pre-existing
  client id is still in `local.oidc_provider_client_ids`. A replace silently
  unpublishes other consumers' keys from the provider JWKS.
- **G4 — the shared `lab` key is untouched.** `vault_identity_oidc_key.lab`
  shows no diff and still reads `rotation_period`/`verification_ttl` of
  `86400`. Editing it would change rotation for the Nomad UI, Grafana and the
  smoke client.
- **G5 — the scaffold edit landed where it should, and only there.** Expect
  the members map, the two tiers, and `vault_identity_oidc_assignment.smoke`
  `group_ids` growing from 1 to 3. That growth is EXPECTED, not a mistake:
  the smoke assignment binds `local.all_app_user_group_ids` by design, and
  effective access does not change. Nothing else in `roles.tf` or `oidc.tf`
  should move.

## Revoking a long-lived human token

A 30-day id_token is a stateless bearer. Vault cannot revoke one once issued,
so know which lever actually works before you need it.

**The complete lever: remove the memex client from
`local.oidc_provider_client_ids` and apply.** That drops the `memex-human`
key from the provider's JWKS, so every outstanding memex human token fails
verification at once. One reversible line, and it touches no other consumer.

**Rotating the key is NOT the complete lever, despite how it reads.**
`rotate` stamps an expiry on the CURRENT signing key only, then promotes the
next one. Keys rotated out earlier keep the expiry they were given at their
own rotation, and nothing revisits them. So repeating the call never
converges: the second call expires a freshly promoted key that signed
nothing. Its real reach is "tokens issued since the last rotation". Lowering
the key's `verification_ttl` does not help either: it does not re-stamp
existing ring members, and Vault refuses it outright while the client's
`id_token_ttl` exceeds it.

Either way the change lands within memex's JWKS cache interval (about an
hour), not instantly.
