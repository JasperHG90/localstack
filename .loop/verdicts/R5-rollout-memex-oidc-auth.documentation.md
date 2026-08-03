---
verdict: pass
tree: 19b0e9c1373ea62fda3e656a5476ea831ec47a4a
---

# Documentation freshness review, R5-rollout-memex-oidc-auth (pass: documentation, cycle 3 of 3)

Pass. My cycle-2 required fix landed and is correct, the three
fallback-semantics rewrites agree with each other and with the code, and no
documented surface this diff touches is left stale. I re-derived the load-
bearing claims from upstream memex v1.1.0 rather than from my own earlier
verdicts, and every one held.

Nothing below is a required fix. Nits are named so a future pass has them.

## The `just` fix is right, measured

`docs/memex-oidc-verification.md:83` now reads `just apply true
nomad_job.memex`. Against `deployments/applications/justfile:13`
(`apply refresh="true" target=""`), on `just 1.46.0`:

```
$ just --dry-run apply true nomad_job.memex
>> Applying target: nomad_job.memex
terraform apply -var-file=./vars/prod.tfvars -refresh=true -target=nomad_job.memex

$ just --dry-run apply target=nomad_job.memex        # the form I got wrong
>> No target specified, applying all resources
terraform apply -var-file=./vars/prod.tfvars -refresh=target=nomad_job.memex
```

Both reproduced. The parenthetical the fix carries ("the two arguments are
positional, `refresh` then `target`") is accurate and is the part that stops
the next reader from re-deriving my mistake. The second half of that
parenthetical also holds: `justfile:19` and `:23` add
`-var-file=./vars/prod.tfvars` under `CONSUL_HTTP_TOKEN`, and
`var.secret_mount` has no default, so a bare `terraform apply` here would
fail.

## The three fallback passages are correct and mutually consistent

I checked them against the upstream code rather than against each other.
`memex_common/auth_client.py` at tag `v1.1.0`, lines 196-200:

```python
bearer = await _resolve_bearer(config, client=client)
if bearer is not None:
    return {'Authorization': bearer}
...
    return {'X-API-Key': config.api_key.get_secret_value()}
```

The `X-API-Key` branch is reachable only when `_resolve_bearer` returns
`None`. That is the whole rule, and all three passages now state it:

- **Intro, `docs/memex-oidc-verification.md:13-16`.** "It applies only when
  the bearer fails to resolve at all ... Once a bearer resolves, the client
  sends it and nothing else." Correct.
- **W1, `:76-79`.** "Once the bearer **resolves** ... never falls back to
  `X-API-Key`, so a 403 here is an outage." Correct, and it no longer says
  the thing that would have made H2 vacuous.
- **Close, `:210-216`.** Separates a misconfiguration (bearer never
  resolves, recoverable on the key) from a resolved-but-rejected bearer (not
  recoverable), and calls S2 a regression check on the keys. Correct.

The parenthetical at `:78-79` ("the fallback survives only where the bearer
does NOT resolve at all, which is precisely what H2 hunts for") is the
sentence the adversarial pass asked for, and it is sound. See nit 2 on
"precisely".

## D2's discriminator still holds, re-derived from upstream

I fetched `memex_core/server/oidc.py` and `auth.py` at tag `v1.1.0` rather
than trusting cycle 1.

- **D1 (wrong `aud`)** resolves a provider by `iss`, then fails
  `claims.validate()` on the `aud` claims option and hits
  `logger.info('OIDC token rejected for issuer %s: %s', ...)` (`oidc.py:209`).
  Log line present, exactly as `docs/memex-oidc-verification.md:152` says.
- **D2 (valid token, no matching rule)** passes verification and reaches
  `_claims_to_context` (`oidc.py:83-97`), whose `for/else` returns `None`
  when no `grant_rule` matches and `default_policy` is `None`. **No logger
  call on that path.** Silence is the pass, as `:153-155` says.
- Both render `403 {'detail': 'Invalid API key or bearer token.'}`
  (`auth.py:242-243`, `:377`), so the response genuinely cannot tell them
  apart. The runbook's insistence on asserting against the server log
  (`:147`) is the right call, not a stylistic preference.

The two startup lines S1 greps for are verbatim upstream: `'OIDC
bearer-token authentication enabled (%d provider(s)).'` (`oidc.py:289-292`)
and `'API key authentication enabled (%d key(s) configured, %d exempt
path(s)).'` (`auth.py:185`).

H2's two detector strings are verbatim too: `'Could not read workload token
file %s: %s'` (`auth_client.py:258`) and `'Falling back to X-API-Key client
(shared memex config unusable): %s'` (`memex_hermes_plugin/memex/provider.py:280`,
inside a bare `except Exception` around `MemexConfig()` /
`MemexClientAuth`, which is what makes the runbook's gloss "the OIDC config
is present but fails validation" accurate).

## Every command is runnable

- W1's decoder (`:96-99`). I generated JWT payloads at all four base64url
  padding remainders and ran the exact one-liner against each. All four
  decoded. The `base64 -d` warning at `:102-104` is the reason it is written
  this way and is correct.
- S1's grep (`:24`), S2's three curls (`:43-45`) and the `vault kv get`
  (`:53`), W1's bearer curl (`:111-113`), D1's stanza (`:123-128`), H1's
  resolver (`:165-169`), H2's two greps (`:185-186`).
- `/opt/hermes/.venv/bin/python` exists
  (`deployments/applications/services/hermes/Dockerfile:26`).
- Cited anchors resolve: `deployments/applications/secrets.tf:79-86` is the
  `memex_auth_keys` resource with `admin_key` in `data_json`;
  `deployments/applications/vars/prod.tfvars.example:1` is
  `secret_mount = "secret"`; `git check-ignore -v` confirms the real
  `prod.tfvars` is ignored (`.gitignore:12`).
- Addresses match the tree: `services.tf:177` (`memex_host = "192.168.2.46"`),
  `memex.hcl:20` (`static = 8000`), `services.tf:25`
  (`nomad_oidc_issuer = "https://nomad.lab.orangecluster.nl"`), consumed at
  `:135` and `:178`.

## No documented surface drifted

The diff's user-facing surfaces are the memex server's OIDC provider
(`memex.hcl:146`), hermes's three `MEMEX_OIDC__*` vars in four places plus
the `identity` stanza, and the image tag `services.tf:131`.
`docs/workload-identity.md` covers the stanza conventions, the `filepath`
rule, the `change_mode` rule, the `user =` hazard and the audience registry;
`docs/memex-oidc-verification.md` covers the checks. Both were updated in
this diff.

Outside those two files, no `.md` under `docs/` or `README.md` names
`MEMEX_OIDC__*`, `env_passthrough`, `MEMEX_API_KEY` or the hermes image tag.
`docs/credential-rotation.md:138`'s only memex mention is an image pull,
untouched. `docs/vault-human-auth.md` is untouched, as §5 requires.
`README.md:29` points at `docs/` with an "etc.", so there is no index to add
the runbook to.

The F10 discovery correction in `docs/workload-identity.md:228-250` is
right: the doc previously said discovery was disabled cluster-wide, and
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42` plus
`bootstrap/playbooks/configure_hashistack_server.yml:45` now set
`oidc_issuer = "https://nomad.lab.orangecluster.nl"`.

Slop scan, both files: 0 tier-1 terms, 0 identity leaks, 0 `TODO`/`FIXME`,
0 smart quotes, 0 ` -- `, 0 British spellings, no self-narration. No added
line in either file exceeds 80 columns outside fenced code (the four
over-length lines in the runbook, `:44`, `:45`, `:53`, `:99`, are all inside
fences; the five in `workload-identity.md` are pre-existing).

## Nits, none required

**1. `docs/workload-identity.md:192` has an em dash, and it is an added
line.** "breaks its ability to read its own identity file — and the failure
is silent". `git show HEAD:docs/workload-identity.md | grep '—'` returns
nothing, so this diff introduced it. **My cycle-2 verdict said the file's one
em dash sat in a line the diff did not touch. That was wrong.** Correcting it
here so the record is straight. One em dash over 1952 words is 0.5 per 1000,
inside the 0-2 bar, so no fix demanded. The runbook is at 0 over 1248 words.

**2. H2 misses a third downgrade string.** `_read_workload_token`
(`auth_client.py:268-271`) has a path the runbook's two greps do not match:

```python
token = raw.strip()
if not token:
    logger.warning('Workload token source is empty (grant=%s).', oidc.grant)
    return None
```

A present-but-empty token file downgrades to the API key and logs neither
`workload token file` nor `Falling back to X-API-Key`. This does not mislead
an operator, because H1 (`docs/memex-oidc-verification.md:162-176`) is the
positive check and catches it outright: `resolve_client_headers` would
return `{'X-API-Key': ...}`, which `:172-173` names as the failure. It does
soften "precisely what H2 hunts for" at `:79` to "most of what H2 hunts
for". A third grep on `'Workload token source is empty'` would close it if
anyone touches this file again.

**3. Advisory A from cycle 2 is now mostly resolved, and not worsened.** You
asked specifically. `:8-11` still opens with "Most failure modes here are
silent: the request still returns `200`", which is true of H1/H2/H3 and not
of W1/S1/D1/D2. The new paragraph at `:13-16` bounds it correctly in the
very next breath, so a reader who reads the section gets the precise rule
before reaching any check. The residue is one over-reaching sentence with a
"Most" hedge in front of it, sitting three lines above its own correction.
That is better than cycle 2, not worse.

**4. Semicolon splices, low confidence, surfacing not rewriting.** Runbook
`:57`, `:73`, `:203`. Added lines in `docs/workload-identity.md`: `:177`,
`:231`, `:248` (the file's other six are pre-existing). A period reads the
same in each. The slop rule marks these low confidence and says to surface
for a human.

**5. Heading reference still misquotes by two characters.** Carried from
cycles 1 and 2. `docs/workload-identity.md:150` points at "Prefer
`change_mode = noop` for a file identity"; the heading at `:180` is "Prefer
`change_mode = "noop"` for a file identity". A reader finds it regardless.

**6. Contrastive negation, twice, in prose the cycle rewrote.** `:77` ("an
outage, not a free probe") and `:216` ("not a safety net for the checks
above"). Both are on the tier-5 list. Both are also load-bearing corrections
where the discarded half is the reading the doc is trying to kill, which is
the case the rule says to keep. Named, not asked for.

**7. The plan and the eval still carry the stale W1 premise.**
`.loop/plans/R5-rollout-memex-oidc-auth.md:344-356` and
`.loop/evals/R5-rollout-memex-oidc-auth.md:16` both still say W1 runs
"BEFORE any `MEMEX_OIDC__*` var is set", which the runbook now shows is
impossible (one `templatefile`, one `nomad_job.hermes`). §8 at `:415-416`
claims the runbook holds every check "verbatim"; it no longer does, and the
runbook is the correct one. These are harness artifacts, not docs, and the
adversarial verdict already flagged the eval row at
`.loop/verdicts/R5-rollout-memex-oidc-auth.adversarial.md:187`. Recording it
so nobody reconciles the two in the wrong direction later.

**8. Carried from cycles 1 and 2, still not this ticket's.**
`docs/notes/audit/plan-premise-sweep-2026-07.md:121-134` says "No job uses
JWKS or OIDC for its own authentication" and that memex has "no JWKS URL, no
OIDC issuer, and no JWT verification anywhere in the job". This diff
falsifies both. It reads as a dated snapshot under "Ground truth, read from
the live cluster 2026-07-30" and sets its own convention of appending
corrections rather than replacing text, so no fix demanded.

## On the fingerprint

Bound to `19b0e9c1373ea62fda3e656a5476ea831ec47a4a` as briefed, and
confirmed it is the tree I read: `.loop/stamp.json` carries the same value
with `just pre_commit` at exit 0, and `loopctl verify` returns `ok` against
this working tree. As in cycles 1 and 2, a plain `git write-tree` over this
index gives a different hash (`90a5140a...`) because the harness computes its
fingerprint over repo content excluding `.loop/`. The docs and Terraform I
reviewed are byte-identical either way. Recorded so the commit gate's
comparison is not mistaken for a content mismatch.
