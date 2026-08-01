---
verdict: pass-with-required-fixes
tree: 9fe4d5b4cc112c82495d3dffbaaeab5194ab93bd
---

# Documentation review — F2-foundation-vault-oidc-provider (cycle 4, final)

Scope: the docs surface of the F2 diff. `docs/vault-human-auth.md` (new),
`.loop/plans/F2-foundation-vault-oidc-provider.md` close-out (rewritten by
the adversarial pass), `.loop/evals/F2-foundation-vault-oidc-provider.md`
row 5 (same), and the comment surfaces in `oidc.tf`, `auth_userpass.tf`,
`secrets.tf`, `variables.tf`.

Nothing in the Terraform blocks. One narrow doc gap is worth fixing before
the operator hands `docs/vault-human-auth.md` to a consumer ticket.

## Verified since cycle 3

- **Smoke-block deletion note landed.** `oidc.tf:85-90` now carries it:
  "Once a real consumer client exists, this can be deleted -- but remove its
  entry from `local.oidc_provider_client_ids` in the same change, or the
  provider references a client id that no longer exists." Read from the file,
  not taken on report. The prior LOW is closed.
- **The new authorize-scope prose is accurate.** Plan `:287-296` and marker
  `:37` both state that Vault's
  `/identity/oidc/provider/<name>/authorize` takes a space-delimited `scope`
  where only `openid` is required, so `scope=openid` alone yields a signed
  `id_token` with no `groups` claim. That matches Vault: ID-token claims are
  scope-gated, and `groups` is only offered because `oidc.tf:82` sets
  `scopes_supported = [vault_identity_oidc_scope.groups.name]`. The named
  companion params (`client_id`, `redirect_uri`, `response_type=code`,
  `state`, `nonce`) are the ones Vault's authorize endpoint requires. No
  overreach, no invented flag.
- **Marker row 5's Expected is now falsifiable.** It requires decoding the
  payload and asserting `groups` is an ARRAY, which is the only check that
  catches the silent-drop failure described at `oidc.tf:43-53`. Row
  numbering used by the plan close-out (`:266-270`, "marker rows 1, 2, 4, 5
  and 6", and `:322`, "eval row 11") maps correctly onto the marker's data
  rows.
- **No regression in the files touched.** `docs/vault-human-auth.md`
  reconciles against the code: the file table at `:39-43` matches what
  `auth_userpass.tf`, `oidc.tf` and `secrets.tf` actually contain; the KV
  paths at `:47-49` match `secrets.tf` `default/vault/operator` and
  `default/vault/oidc-smoke` under mount `secret` (`vars/prod.tfvars:1`);
  the issuer at `:56` matches `var.vault_issuer_host` plus
  `https_enabled = true`; the `detect-private-key` claim at `:90-92` matches
  `.pre-commit-config.yaml:12`; `jwt-nomad` at `:6` is real
  (`deployments/infrastructure/acme.tf:67`).
- **`CONSUL_TOKEN` is fine, and I withdraw my cycle-3 note.**
  `docs/vault-human-auth.md:110` matches
  `deployments/infrastructure/justfile:8,12,16` and the existing
  `docs/monitoring.md:153,175`. The var-name skew is in
  `.devcontainer/.env.example:6` only, is pre-existing, and F8 already tracks
  it. The doc describes the repo as it works.
- **No index drift.** `README.md:29` points at `docs/` generically; there is
  no docs index needing an entry. `docs/credential-rotation.md` is scoped by
  title to two bootstrap secrets, so the new operator password does not
  belong there.
- **Slop scan on `docs/vault-human-auth.md`** (672 words): 0 em dashes, 0
  ` -- `, 0 semicolon splices, 0 tier-1 slop, 0 self-narration, 0 British
  spellings, 0 smart quotes. Over-80 lines are table rows (`:41-43`) and a
  code-block URL (`:68`), both exempt. Layer 0 clean: every backticked
  identifier and path resolves.

## REQUIRED FIX (MEDIUM, one sentence, no code change)

**`docs/vault-human-auth.md:96-97` omits the very trap the rest of the
ticket exists to guard.**

The doc says:

> The shared `groups` scope emits the entity's Vault group names. oauth2-proxy
> consumes that through `--oidc-groups-claim`.

That is the whole claim contract a consumer ticket reads, and it is silent
on what the adversarial pass just established: the claim appears only if the
client's authorization request asks for the scope. The plan (`:287-296`) and
the marker (`:37`) now both carry the caveat; the one human-facing doc does
not. A reader who follows the section "Adding a service that logs people in
through Vault" (`:71-92`) to the letter, wires up `--oidc-groups-claim`, and
leaves the request scope at their proxy's default gets a signed token with
no `groups` claim and no error. That is the silent failure `oidc.tf:47-53`
warns about.

Fix: one sentence after `:97`, along the lines of "The client must request
the scope as well. An authorization request that sends only `scope=openid`
comes back with a signed token and no `groups` claim, so ask for
`openid groups` (space-delimited) in the service's OIDC scope setting."

This is an omission, not a false statement, and it touches no Terraform. It
does not block committing the branch. With `review_cycles` capped, fold it
into the operator close-out.

## Non-blocking notes

1. **`docs/vault-human-auth.md:106`** still says "Taint the generated
   password" while the command at `:112` uses `-replace` and never taints.
   `terraform taint` is deprecated, so a reader who follows the prose instead
   of the block runs a different command. One word: "Replace".
2. **Two spatial-copula hits**, `:37` "All of it lives in" and `:115` "state
   lives in the Consul backend". Both read as "is" or "is kept in". Cosmetic.
3. **The rotation recipe at `:108-113` applies the whole root.** `-replace`
   scopes the replacement, not the apply, so the operator gets a plan over
   every infrastructure resource. Worth one clause so nobody is surprised by
   the diff.
4. **The scope caveat sits in only one of the plan's two descriptions of the
   same flow.** Plan `:214-228` (section 8, eval 6) still says "drive the
   authorization-code flow ... and exchange the code for an ID token whose
   group claim matches the assignment" with no mention of the scope; the
   close-out at `:287-296` carries the fix and redirects to the marker. A
   reader who stops at section 8 repeats the trap. Internal artifact, so low
   stakes.
5. **Marker `:24-26`** says "rows 6 and 7 exist because the previous marker's
   secret guardrail named `detect-private-key`". Only row 7 is about
   `detect-private-key`; row 6 is the non-member denial guardrail.
   Pre-existing, not introduced by this diff, but it can misdirect a scorer.
6. **`oidc.tf:88`** uses ` -- ` as prose punctuation in a comment. The slop
   rule scopes to markdown, so this is style only.

Nothing is applied and nothing should be: the loop never runs
`terraform apply`, so the absence of these objects in live Vault is expected,
not drift.
