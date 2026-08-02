---
verdict: pass
tree: 66ca9f173e71fb6f170085ddce6abb7b79838a4c
---

# Documentation review: G2-nomad-ui-oidc-login (final re-bind)

Both advisories from the pass at `60b98bec4d4b1727f98ffb329922a6431da6a29e`
are applied and correct. Nothing outside `.loop/` moved except the doc that
carried the first fix. Binding at
`66ca9f173e71fb6f170085ddce6abb7b79838a4c`.

Scope, per the briefing: the `-json` passage, the redaction note, and the set
of changed files. The ticket's substance stands from the earlier passes and
was not re-reviewed. Read-only throughout: no `nomad login`, no `terraform
apply`, no repo file edited, no mutating git command.

Fingerprint recomputed with `tree_fingerprint()` from `loop_harness.stamp`
against the worktree root: `66ca9f173e71fb6f170085ddce6abb7b79838a4c`,
matching both the briefing and `.loop/stamp.json`, which also records `just
pre_commit` exit 0.

---

## 1. The `-json` passage is now explicitly unverified, and the leak still lands

`docs/vault-human-auth.md:291-299` reads:

> From a terminal, `nomad login -method=vault` needs `xdg-open` to launch a
> browser. Without it the command prints the URL and waits, which works fine —
> paste it into any browser. **Its default output prints the issued token's
> Secret ID in full**, so treat that output as a secret. A script can select
> fields instead, with `nomad login -method=vault -t '{{ .AccessorID }}'`.
> `nomad login` also takes `-json`, but that marshals the whole token object
> and has not been checked here for whether it includes the Secret ID, so
> prefer `-t`. Note `nomad acl token self` takes neither flag; both fail there
> before any network call.

Checks against the installed CLI at `/usr/bin/nomad`:

- **`-json` and `-t` both exist on `nomad login`.** `nomad login -h` lists
  them under `Login Options:` as "Output the ACL token in JSON format" and
  "Format and display the ACL token using a Go template". The doc's existence
  claim is the only claim it makes about `-json`, and it is true.
- **The passage asserts nothing about `-json` and the Secret ID in either
  direction.** "has not been checked here for whether it includes the Secret
  ID" is a statement about this repo's verification, not about the CLI. It
  cannot be falsified by whatever `nomad login -json` turns out to emit. My
  earlier suggested parenthetical would have asserted more than either of us
  verified; not adopting it was the right call.
- **The reader still comes away knowing the default leaks.** The bold clause
  "Its default output prints the issued token's Secret ID in full" precedes
  both flags and is unqualified, and "so treat that output as a secret"
  follows it. The skimmer risk I raised is closed by "so prefer `-t`", which
  gives a single default action instead of two flags of equal standing.
- **The `nomad acl token self` claim is unchanged and still holds.** Verified
  in the prior pass: both `-t` and `-json` return `flag provided but not
  defined` with no server round trip.

No doc drift. Resolved.

## 2. The redaction note reads honestly

`.loop/evals/G2-manual-eval-results.md:83-86`, directly under the Row 3
transcript at `:72-81`:

> **Transcript abridged: the real output also carries `Accessor ID` and
> `Secret ID` lines.** They are cut here deliberately, which is the point the
> paragraph below makes — the token from this run had to be revoked because
> its Secret ID reached a session transcript.

It says the command emitted those lines and that this file cut them. It
attributes the removal to the author ("cut here deliberately"), not to
`nomad login`, so it cannot be read as the command withholding them. The
apparent contradiction with the prose seven lines down at `:93` ("**`nomad
login` prints the Secret ID in full** by default") is gone, and the note adds
the consequence: the token from that run was revoked. The revocation is
corroborated in the same file at `:147-151`, which shows a delete-by-accessor
against a G2 probe token.

The eval file sits outside the fingerprint, so this could not have blocked a
bind either way. It is now consistent rather than merely non-blocking.

## 3. Nothing else outside `.loop/` moved

`git status --porcelain` lists exactly four paths outside `.loop/`, the same
four as the last pass: `deployments/infrastructure/developer_group.tf`,
`deployments/infrastructure/nomad_oidc.tf`,
`deployments/infrastructure/oidc.tf`, `docs/vault-human-auth.md`. No new
untracked file.

Mtimes confirm only the doc moved in this pass. The three Terraform files sit
at 08:30, 09:21 and 09:22, unchanged from the timestamps recorded in the
`60b98bec…` verdict. `docs/vault-human-auth.md` moved 12:42 to 12:47 and
`.loop/evals/G2-manual-eval-results.md` 12:43 to 12:48, matching the two
advisories and nothing else.

---

## Still non-blocking, unactioned by agreement

Carried forward unchanged from the previous verdict. None makes a reader
wrong, so none blocks the bind.

1. **`## Logging in` (`docs/vault-human-auth.md:9`) covers only `vault
   login`.** The Nomad UI button and terminal `nomad login` live at
   `:275-299`. Navigation gap, not misinformation.
2. **"What Terraform creates" (`:35-43`) lists three of five files.** Omits
   `developer_group.tf` and `nomad_oidc.tf`, both named and explained
   elsewhere in the same doc.
3. **The `alloc-node-exec` back-reference (`:301-304`).** Points at "What the
   operator can do"; the pointer resolves to `:96-101`.
4. **`ROADMAP.md:23` still says the auth method "moved to Ansible".**
   Genuinely stale: `nomad_acl_auth_method.oidc` and
   `nomad_acl_binding_rule.developer` are in Terraform at
   `deployments/infrastructure/nomad_oidc.tf:136` and `:185`. The ROADMAP is
   maintained in its own `build:` commits, so it belongs in one. Should be
   picked up there.

## One new informational note

- **`docs/vault-human-auth.md:292` gained an em dash** ("which works fine —
  paste it into any browser") where the previous revision used a period. The
  house style targets zero em dashes in generated docs
  (`.claude/rules/slop-scan-for-docs.md`). Style only, no reader is misled.
  Severity: informational. The same applies to the em dash at
  `.loop/evals/G2-manual-eval-results.md:85`, which is outside the
  fingerprint.

---

## Verdict

**pass** at tree `66ca9f173e71fb6f170085ddce6abb7b79838a4c`. The `-json`
passage now claims only what was checked and still puts the default leak in
front of the reader, the redaction note credits the cut to the author rather
than the command, and no file outside `.loop/` moved beyond the doc that
carried the fix.
