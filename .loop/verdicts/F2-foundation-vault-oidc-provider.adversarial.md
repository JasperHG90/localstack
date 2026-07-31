---
verdict: pass
tree: 9fe4d5b4cc112c82495d3dffbaaeab5194ab93bd
---

# F2 — adversarial implementation review, cycle 4 (final)

Nothing blocks. Both cycle-3 findings are applied and verified by reading the
files, not the hand-off. The gate is green when I run it myself. Every eval row
the loop can reach passes; the post-apply rows are now written so they can
actually fail against a broken build, which was the whole point of MEDIUM-1.

## Cycle-3 findings: both confirmed applied

**MEDIUM-1 (authorize request must ask for the `groups` scope) — FIXED, and the
fix is complete in both places.**

- Plan close-out, `.loop/plans/F2-foundation-vault-oidc-provider.md:291-307`:
  states the request MUST send the groups scope, shows `scope=openid groups`,
  names the other params (`client_id`, `redirect_uri`, `response_type=code`,
  `state`, `nonce`), and explains that `openid` alone yields a signed token with
  no `groups` claim "even when the scope template is perfect". The follow-on
  paragraph requires decoding the payload and asserting `groups` is an ARRAY,
  and names the silent-drop behavior as the trap that hid the `jsonencode`
  defect.
- Marker row 5, `.loop/evals/F2-foundation-vault-oidc-provider.md:37`: Input
  now carries **`scope=openid groups`** with the same warning inline; Expected
  now requires the claim "is an ARRAY, not a string" and says "do not treat a
  returned token as evidence, since Vault drops a malformed claim silently and
  still signs".

**Does row 5 now discriminate?** Yes. Against the correct template at
`oidc.tf:53` the operator gets `"groups":["oidc-smoke"]` and the row passes.
Against the quoted/`jsonencode` form the row was written to catch, Vault merges
nothing, still signs, and the payload has no `groups` key at all — the array
assertion fails. Two different builds now produce two different row outcomes,
which was not true in cycle 3.

**LOW (hand-off overclaimed the smoke-block deletion note) — FIXED, verified
first-hand.** `oidc.tf:85-90` now reads: "this can be deleted -- but remove its
entry from `local.oidc_provider_client_ids` in the same change, or the provider
references a client id that no longer exists." `grep -c oidc_provider_client_ids
deployments/infrastructure/oidc.tf` returns **4** (was 3). I did not take the
hand-off's word for it.

## HIGH-1 re-confirmed

`oidc.tf:53`:

    template = "{\"groups\":{{identity.entity.groups.names}}}"

HCL renders this to `{"groups":{{identity.entity.groups.names}}}` — `{{` is not
a Terraform interpolation sequence (`${` and `%{` are), so the braces pass
through literally. That is Vault's own canonical scope-template shape: the
placeholder is unquoted and the string is not built with `jsonencode`, because
Vault's identity templating substitutes fully-formed JSON (`["a","b"]`,
brackets included). Vault accepts a raw-JSON template (it tries base64 first,
falls back to the literal), and this string is not valid base64, so the literal
is what lands. No regression.

## Independent gate run

`just pre_commit` from the worktree root: all hooks **Passed**, including
`Terraform Format (fmt -check -recursive)` and `Terraform Validate (per root)`.
The worktree already carries the `.ssh` symlink and copied `prod.tfvars`, so
`terraform-validate` ran for real rather than dying early. Provider resolved is
`hashicorp/vault 5.3.0` under constraint `~> 5.3.0`
(`deployments/infrastructure/.terraform.lock.hcl:84-86`), so every
`vault_identity_oidc_*` attribute in the diff — including
`vault_identity_oidc_key_allowed_client_id` and the provider's `issuer_host` /
`https_enabled` — resolves against the pinned schema.

## Eval marker: all 11 rows re-scored

Rows 1, 2, 4, 5, 6 and 11 need `terraform apply`, which the loop never runs.
They are scored on whether the config can satisfy them and whether the close-out
procedure is executable and falsifiable.

| # | Row | Score | Evidence |
|---|-----|-------|----------|
| 1 | Discovery over HTTPS | READY (post-apply) | `oidc.tf:77-83` sets `https_enabled = true` and `issuer_host = var.vault_issuer_host`, default `vault.lab.orangecluster.nl` (`variables.tf`), so the advertised issuer carries the required prefix |
| 2 | JWKS non-empty | READY (post-apply) | `vault_identity_oidc_key.lab` RS256 with `rotation_period`/`verification_ttl` 86400 (`oidc.tf:26-31`); `id_token_ttl = 3600` is well under `verification_ttl`, so Vault will not reject the client |
| 3 | Resource graph COUNTED, not grepped | PASS at config level | Exactly **9** `resource "vault_identity*"` blocks: key, scope, provider, client, assignment, key_allowed_client_id (`oidc.tf`), group (`oidc.tf:92`), entity and entity_alias (`auth_userpass.tf:38,48`). Matches the row's per-resource enumeration one-for-one, no extras |
| 4 | Login yields entity-bearing token | READY (post-apply) | `auth_userpass.tf:13-54` creates the mount, the user via `vault_generic_endpoint` with `ignore_absent_fields = true` (the correct idiom — `password` is never returned on read, so no perpetual diff), the entity, and the alias whose `name` equals the username, which is what binds a userpass login to the entity. Live check: no `userpass` mount and no `operator` entity exist, so no create-time collision |
| 5 | Auth-code flow carries the group claim | PASS (rubric 5/5) | The row now specifies `scope=openid groups` and asserts the claim is an array. Combined with the correct template at `oidc.tf:53` and `member_entity_ids = [vault_identity_entity.operator.id]` at `oidc.tf:97`, a working build yields `["oidc-smoke"]` and a broken one yields no claim. The row separates them |
| 6 | Non-member denied | READY (post-apply) | Close-out step 1 supplies the full second-entity recipe (plan `:275-287`) and states why the row exists. `vault_identity_oidc_assignment.smoke` gates on the group only (`entity_ids = []`), so a scratch entity outside `oidc-smoke` is genuinely refused |
| 7 | No client secret in the diff | PASS | `git diff HEAD -- '*.tf' '*.tfvars'` plus a scan of the untracked `oidc.tf` / `auth_userpass.tf` matches neither `client_secret\s*=\s*"` nor `hvo_secret_`. `secrets.tf` writes `client_secret = vault_identity_oidc_client.smoke.client_secret` — a reference, not a literal — into KV2 at `default/vault/oidc-smoke` |
| 8 | No consumer client created here | PASS | Exactly one `vault_identity_oidc_client`, named `oidc-smoke` (`oidc.tf:106`). No `dash`, `mlflow`, `phoenix` or MinIO-tier client anywhere in the root |
| 9 | Registration does not edit the key | PASS | `grep -n allowed_client_ids` over the root shows the only assignment is on the **provider** (`oidc.tf:81`), which has no standalone resource. The key (`oidc.tf:26-31`) has no inline list; the smoke client registers through `vault_identity_oidc_key_allowed_client_id` (`oidc.tf:118-121`), and the header comment tells consumer tickets to copy that pattern |
| 10 | `just pre_commit` green | PASS | Re-run independently; every hook Passed |
| 11 | Drifting `test` client resolved | PASS (rubric 4/5) | Q7 is answered (delete, not import) and carried into an executable close-out step with both `vault delete` commands, a confirm step, and a "leave `default`/`allow_all` alone" boundary (plan `:308-321`). Docked one point only because execution is necessarily post-apply; live Vault still shows `test` under both `identity/oidc/client` and `identity/oidc/assignment`, exactly as the plan describes |

## Scope

Every changed line traces to the ticket. `oidc.tf` and `auth_userpass.tf` are
the two new files §7 names; `secrets.tf` (+37) adds only the two KV2 writes §7
asks for, in the existing `random_password` to `vault_kv_secret_v2` plus
`custom_metadata managed_by = "terraform"` style; `variables.tf` (+18) adds only
the three variables §7 names. `docs/vault-human-auth.md` is the documentation
pass's output, not implementation scope; I spot-checked it for hallucinations
and found none — the KV paths (`secret/default/vault/operator`) match
`secret_mount = "secret"` in `vars/prod.tfvars`, the `CONSUL_HTTP_TOKEN` claim
matches every recipe in `deployments/infrastructure/justfile`, and `jwt-nomad`
matches live `vault auth list`. Zero em dashes, 672 words.

## Non-blocking notes (no cycle left; do not fix now)

1. **Confidential-client token exchange needs client auth.** The smoke client is
   `client_type = "confidential"` (`oidc.tf:111`), so the code-for-token POST at
   the token endpoint must present the client id and secret (read from KV2 at
   `default/vault/oidc-smoke`). Neither the close-out nor marker row 5 says so.
   Unlike the scope trap, this fails **loudly** with a 401 rather than passing
   with a hollow token, so it costs the operator a minute, not a false green.
   Worth a sentence next time the close-out is touched.
2. **Smoke redirect URI default is Vault's own UI callback path**
   (`variables.tf`, `https://vault.lab.orangecluster.nl/ui/vault/auth/oidc/oidc/callback`).
   Harmless — the row-5 procedure drives the API and reads the `Location` header
   — but it reads as if Vault were the relying party. A neutral placeholder
   would be clearer. The variable's own description already warns that the
   default hardcodes the issuer host because Terraform forbids interpolation in
   a default.
3. **One prose double-dash in a comment.** `oidc.tf:88` uses ` -- ` where the
   rest of the file uses a real em dash (`:19`, `:75`). The repo's plain-language
   rule calls that out. Cosmetic.

## Bottom line

Commit it. The implementation is correct against pinned 5.3.0, the gate is green
under my own hand, the resource set is exactly the nine the marker enumerates
with no consumer-client creep, no secret reaches the diff, and the post-apply
rows are now written so a broken claim template fails them instead of sliding
through on a signed-but-empty token.
