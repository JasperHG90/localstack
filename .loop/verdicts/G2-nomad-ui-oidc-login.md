---
verdict: pass
tree: 66ca9f173e71fb6f170085ddce6abb7b79838a4c
---

# G2-nomad-ui-oidc-login — re-bind pass (one sentence)

Scope: re-bind only. The ticket passed clean at `6a426823…` and again at
`60b98bec…`; neither review is repeated. I checked the three points the delta
requires, plus the `.loop/` security-shaped edit I was asked to eye.

`.loop/stamp.json` records `tree: 66ca9f173e71fb6f170085ddce6abb7b79838a4c`,
matching the fingerprint I was given, and `gates: [{just pre_commit, exit 0}]`.

## 1. The `-json` passage no longer asserts either way — confirmed

`docs/vault-human-auth.md:293-299` now reads:

> **Its default output prints the issued token's Secret ID in full**, so treat
> that output as a secret. A script can select fields instead, with `nomad
> login -method=vault -t '{{ .AccessorID }}'`. `nomad login` also takes
> `-json`, but that marshals the whole token object and has not been checked
> here for whether it includes the Secret ID, so prefer `-t`. Note `nomad acl
> token self` takes neither flag; both fail there before any network call.

That is the shape asked for. `-t` is no longer grouped with `-json` under a
shared "without the secret" claim: `-t` is stated as field selection, `-json`
carries an explicit "has not been checked here" and a recommendation to avoid
it. It does not swing to the opposite error either — it does not claim `-json`
leaks the secret, only that nobody verified. The default-output warning and the
"treat that output as a secret" instruction are untouched, so a reader who
stops early still lands safe.

No stale copy of the retired wording survives. A grep across `docs/` and
`.loop/evals/` for `without the secret`, `format the token object` and
``does take `-t` `` returns nothing.

The three surrounding claims still hold against the installed CLI. `nomad login
-help` lists both `-json` ("Output the ACL token in JSON format") and `-t`
("Format and display the ACL token using a Go template"). With
`NOMAD_ADDR=http://127.0.0.1:1`, so no endpoint could answer:

```
$ nomad acl token self -json
flag provided but not defined: -json
$ nomad acl token self -t '{{ .AccessorID }}'
flag provided but not defined: -t
```

Both fail at flag parse, instantly. Per instruction I did not run `nomad
login`; `-help` only.

## 2. Nothing else outside `.loop/` moved — confirmed

The previous version of the file survives in the object store as blob
`e00d095a4931d2f831fc67cdef7eb5520b7f1376` (the only blob carrying the old
wording that is otherwise this document). `git cat-file blob e00d095a | diff -
docs/vault-human-auth.md` returns exactly one hunk, `294,297c294,299` — the
passage above and nothing else. The rest of the file is byte-identical.

The three Terraform files did not move:

- `git status --porcelain` shows a blank second column for every entry, so the
  index matches the working tree.
- `find` for non-`.loop/` files modified after 10:00 today returns only
  `docs/vault-human-auth.md`. The tf mtimes are 09:21 and 09:22, hours before
  both the `60b98bec…` docs edit and this one.
- The line anchor from the last pass still resolves:
  `deployments/infrastructure/nomad_oidc.tf:81` is `### NO depends_on HERE,
  DELIBERATELY`, so the file has not even shifted by a line.
- No untracked or ignored files exist outside `.loop/`
  (`git status --porcelain --untracked-files=all`).

## 3. Gate — passes

`just pre_commit`, run in this worktree, exit 0:

```
check json...............................................................Passed
check for merge conflicts................................................Passed
check yaml...............................................................Passed
detect private key.......................................................Passed
fix end of files.........................................................Passed
Nomad Format (fmt -recursive)............................................Passed
Terraform Format (fmt -check -recursive).................................Passed
Terraform Validate (per root)............................................Passed
```

Matches the recorded gate in `.loop/stamp.json`.

## 4. The abridged transcript note reads honestly — confirmed (advisory, inside `.loop/`)

`.loop/evals/G2-manual-eval-results.md:83-86`:

> **Transcript abridged: the real output also carries `Accessor ID` and
> `Secret ID` lines.** They are cut here deliberately, which is the point the
> paragraph below makes — the token from this run had to be revoked because its
> Secret ID reached a session transcript.

This is the honest reading, not the evasive one. It states the command did
print both lines, says the cut was the author's, and gives the reason. It
cannot be misread as "the command did not print them", which is what the silent
redaction seven lines above `…:93` ("**`nomad login` prints the Secret ID in
full** by default") risked. The eval file and the docs now hedge `-json`
identically (`…:95-97`, "was not checked for whether it carries the Secret
ID"), so the two documents still agree, and `…:259-260` repeats the flag-parse
detail consistently.

## Findings

### Nit (non-blocking, `.loop/`) — "the paragraph below" points one paragraph short

`.loop/evals/G2-manual-eval-results.md:84-85` says the cut "is the point the
paragraph below makes". The paragraph immediately below (`…:88-89`) is about
the callback round trip; the Secret ID point is two paragraphs down, at
`…:93`. A reader following the pointer lands on the wrong paragraph and finds
it a moment later. Cosmetic, outside the fingerprint, not worth a cycle.

### Nit (non-blocking, carried) — semicolon splice

`docs/vault-human-auth.md:297-299`: "Note `nomad acl token self` takes neither
flag; both fail there before any network call." Two independent clauses joined
by a semicolon. The repo rule marks this low confidence and says to surface
rather than auto-rewrite, so I am surfacing it again, not requiring it.

### Resolved since the last pass

The `-json` nit I raised at `60b98bec…` is fixed, and fixed the right way: by
narrowing the claim to what was measured rather than by guessing. The em-dash
count also dropped from 16 to 15 over 2538 words (about 5.9 per 1000, still
over the 0-2 target in `.claude/rules/slop-scan-for-docs.md`, but the bulk is
pre-existing and this delta removes one rather than adding).

## Verdict

Pass. The one changed passage says only what was verified, marks the `-json`
gap as unchecked instead of guessing in either direction, and keeps the
load-bearing warning intact. The delta outside `.loop/` is exactly that
passage — one hunk in one file, proven against the prior blob. The gate is
green. Bound to tree `66ca9f173e71fb6f170085ddce6abb7b79838a4c`.
