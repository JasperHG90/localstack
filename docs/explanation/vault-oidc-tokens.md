# Vault OIDC tokens, and what a relying party has to know

Vault's `lab` provider signs the tokens a service verifies when a person logs
in through Vault. memex was the first service to verify them itself, and what
building it proved applies to every later consumer. The provider itself is
described in [Human login to Vault](../reference/vault-human-auth.md).

## memex: the first branch-2 consumer, and what it proves

memex logs humans in through the `lab` provider with two tiers,
`app-memex-admins` and `app-memex-readers`, both added to
`local.app_user_groups` (branch 2) and named by one assignment. Four rules
came out of building it, and every later consumer needs them.

**A service that verifies the token ITSELF must read the id_token, and accept
the client id as `aud`.** Vault issues an opaque batch token as its
`access_token` and signs only the `id_token`. A relying party that verifies
locally against the JWKS therefore has to be told to send the id_token
(`credential: id_token` for memex), and its server-side `audience` is the
CLIENT ID, not a service name. This is the sharper form of the note in
[The claims, and which one your service reads](../reference/vault-human-auth.md#the-claims-and-which-one-your-service-reads):
it is not just which claim you read, it is which TOKEN you read.

**A client that wants a session longer than 24h brings its OWN
`vault_identity_oidc_key`, and never edits `lab`.** A client's
`id_token_ttl` may not exceed the `verification_ttl` of the key it
references, and `key` is a per-client field. The shared `lab` key rotates
daily on purpose. memex declares `vault_identity_oidc_key.memex_human` at 7d
rotation / 30d verification and points its own client at it, so a 30-day
human session costs the Nomad UI and Grafana nothing. Vault refuses a
`verification_ttl` beyond 10x the `rotation_period`.

**Set `access_token_ttl` to match, even though nobody verifies it.** Vault
returns `access_token_ttl` as `expires_in`, and a client typically caches
`min(now + expires_in, id_token exp)`. A short `access_token_ttl` therefore
truncates a long id_token session silently, and the client falls back to
whatever static credential it still has with every request still returning
`200`.

**Loopback redirect URIs match port-agnostically, but the host literal and
path exactly.** Vault strips the port from both sides when the incoming host
is `localhost`, `127.0.0.1` or `::1`. A CLI binding an ephemeral port is
therefore fine, but `127.0.0.1` and `localhost` are NOT interchangeable, and
the path must match character for character. Register both host literals.

## Revoking a long-lived id_token, and what rotation does not do

A long id_token is a stateless bearer; Vault cannot revoke one once issued.

**This lever works only for a client on its OWN key.** Removing the client
from `local.oidc_provider_client_ids` unpublishes the keys that client
references, and that kills its tokens only if no other allowed client still
references the same key. memex qualifies because `memex-human` is dedicated
to it. **A client on the shared `lab` key does not**: dropping it leaves
`lab` published for every other consumer, so its tokens keep verifying and
the lever does nothing. That is a second reason a long-lived client brings
its own key.

Given that, the complete lever is: **remove the client from
`local.oidc_provider_client_ids` and apply**. The provider's JWKS is built
from the keys its allowed clients reference, so dropping the sole client of
a dedicated key unpublishes that whole key ring and every outstanding token
for it fails verification. One reversible line, no other consumer affected.
For memex, the steps are
[How to revoke memex human tokens](../how-to/revoke-memex-human-tokens.md).

For a client on the shared key, there is no complete lever. Shorten its
`id_token_ttl` and wait the old tokens out, or move it to its own key first.

**Rotating the key is not that lever, though it reads like it.** `rotate`
stamps an expiry on the CURRENT signing key only and then promotes the next
one. Keys rotated out earlier keep the expiry they were given at their own
rotation, and nothing revisits them, so repeating the call never converges:
the second call expires a freshly promoted key that signed nothing. Its real
reach is "tokens issued since the last rotation". Lowering the key's
`verification_ttl` does not help either: it does not re-stamp existing ring
members, and Vault refuses it outright while a client's `id_token_ttl`
exceeds it.

Either lever lands within the relying party's JWKS cache interval, not
instantly.
