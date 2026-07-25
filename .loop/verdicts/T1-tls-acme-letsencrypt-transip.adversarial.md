---
verdict: pass
tree: c18202df99c20213e6436ad672c7912bacfaa0e6
---

# Adversarial review — T1-tls-acme-letsencrypt-transip (cycle 4, final)

Supersedes my cycle-3 verdict, bound to the now-stale
`57af9e1d67ec0e78a4178a1371bf7c6982f39278`. This one is bound to
`c18202df99c20213e6436ad672c7912bacfaa0e6`, matching `.loop/stamp.json`.
`docs/tls-certificates.md` (21:58:25) and the eval marker (21:58:33) both
predate the stamp (21:59:23). `acme.hcl`, `acme.tf` and `variables.tf` did not
move at all: their mtimes are still 21:53:22, 21:39:08 and 21:08:38, unchanged
since the cycles that last touched them.

Both required fixes are in and both are correct. I found one further doc
inaccuracy, described below. It is not blocking, and I am flagging it because
you asked to be told rather than have it deferred, not because it should hold
the commit. Verdict is pass.

## "No behavior changed" — the strongest form of this check yet

Cycle 3 gave me a jobspec that differed by comment lines. This cycle gives me
nothing at all. Comparing the full plan JSON against the one I saved in cycle
3, resource by resource:

```
addresses identical: True
resources differing from cycle 3: NONE
non-no-op: [acme_state volume, nomad_job.acme, jwt role, acme_tls_write]
```

Not one resource differs, `nomad_job.acme` included, so the jobspec string
itself is unchanged. `diff` on the two renderings confirms it byte-for-byte,
and the parsed job JSON is identical not only to cycle 3 but back to cycle 2:

```
rendered jobspec: IDENTICAL to cycle 3 (byte-for-byte)
parsed job JSON identical to cycle 3: True
parsed job JSON identical to cycle 2: True
```

That matters beyond this cycle. Cycle 2 is where I did the behavioral work:
running the rendered env and args in the pinned image, measuring exit codes,
proving the store shell cannot cross-read between environments, reproducing
the KV2 write under the real policy. Because the scheduled job has not moved a
byte since, all of that still stands without re-verification. `nomad job
validate`: successful. Plan is still 4 to add, 0 to change, 0 to destroy, with
`nomad_job.haproxy` and every `pki` resource `no-op`.

Gates: `just pre_commit` all Passed, plus a separate run over the three
untracked files, which rewrote nothing. Doc mechanics clean: 0 em-dashes, 0
lines over 80 characters, 0 ` -- `, no tier-1 slop, no British spellings, no
stubs. All three URLs in the doc are well-formed.

## Required Fix A — corrected, and the doc now agrees with the comment

`docs/tls-certificates.md:17-28`. "Does nothing" is gone, replaced by "skips
issuance", and the paragraph I asked for is there:

> It does still contact the CA on a night when nothing is due. lego fetches
> the ACME directory before it checks the expiry date, so if DNS or Let's
> Encrypt is unreachable the allocation fails even though no renewal was
> needed. **A red run therefore does not mean a renewal problem.** Check the
> certificate's dates before treating it as one. A failed directory fetch is
> not rate-limited issuance, so nothing is consumed by these failures.

Every clause matches what I measured in cycle 2: with an 89-day certificate
already in state, lego still dialed the directory and exited 1 offline, and
because `issue` is a non-sidecar prestart task that failure takes the
allocation with it.

I checked the two artifacts against each other rather than each against my
notes. The jobspec comment at `acme.hcl:48-62` and this paragraph now make the
same four claims in the same order, and neither overstates. I also checked the
new paragraph against the recovery section, which says a failed challenge
"consumes a rate-limit slot" (`:130`). That is not a contradiction: a failed
directory fetch happens before any order exists, while a failed DNS-01
challenge consumes failed-validation budget. The doc gets both right and keeps
them in separate sections, which is the harder thing to do.

The one claim I still cannot verify myself is "skips issuance when the
certificate still has more than 30 days left". That needs a live ACME
endpoint. It is correctly scoped now (issuance, not network), it matches
lego's documented semantics and the existence of `--renew-force`, and the
marker gates production on proving it. That is the right place for it.

## Required Fix B — corrected, and the class is closed

The guard now reads:

> BLOCKED until **the row titled "re-running the job does not burn Let's
> Encrypt rate-limit budget"** passes against
> `https://acme-staging-v02.api.letsencrypt.org/directory`

I verified the reference resolves and resolves uniquely: exactly one row
carries that title (line 30), and the only other occurrence in the file is the
reference itself. Grepping for any remaining positional reference returns one
hit, inside the explanation paragraph, exactly as you said.

**The precondition is now satisfiable on staging.** The named row asks for the
certificate serial to be unchanged across two consecutive runs against the
staging endpoint. Nothing in it requires public trust, so staging's "(STAGING)
Pretend Pear" issuer is irrelevant to it. The previous reference pointed at
the publicly-trusted-issuer check, which could never pass on staging; that
contradiction is gone.

Recording why in the marker is the part I did not ask for and the part that
matters most. A positional reference that silently retargets is invisible
precisely because both the old and new targets read like plausible
preconditions. The note tells the next person inserting a row what the failure
mode was, which is the only thing that stops it recurring.

## The marker was not weakened

I checked this the way I said I would, and more thoroughly since this is the
last cycle. Ten rows, unchanged in count. Every one of the ten carries a 100%
threshold (I extracted the final column of each row and the only value present
is `100%`). The idempotency row is untouched this cycle: its tail still reads
"compare the serials. **This must pass on staging before the production
endpoint is configured at all** | deterministic check (cert serial identical
across two consecutive runs) | 100% |", identical to what I approved in cycle
3. Diffing the marker against the committed baseline shows the only regions
touched across all four cycles are the guard preamble and rows 2, 3 and 5, and
rows 2, 3 and 5 are unchanged since cycle 3.

Across the whole ticket the marker has moved in one direction: one factually
wrong row corrected, one guardrail added, one command name fixed with an
anti-loophole clause attached, and a fragile cross-reference replaced. No pass
criterion, scorer or threshold was ever loosened.

## New finding, non-blocking: the doc describes a future state in present tense

This is new from me and it is late, which is my fault. I reviewed this doc in
cycle 2 and caught the field-shape error but not this, and it has been present
since the doc was written.

Three passages describe the system as it will be after later tickets, not as
it is when this one applies:

- `:46` "The edge proxy templates these into a single PEM file and reloads
  when they change." Nothing consumes the KV entry yet. The plan's non-goals
  put the edge cutover in a later ticket, marker row 10 requires HAProxy to be
  untouched, and my plan run confirms `nomad_job.haproxy` is `no-op`.
- `:56` "Names resolve on the LAN only, from the local resolver." The local
  resolver is a later ticket.
- `:110` `curl -sS ... https://grafana.lab.orangecluster.nl/` offered as a
  check to run. I confirmed that name has no resolution and the zone has no
  public A record at all (`lab.orangecluster.nl`, `grafana.lab.orangecluster.nl`
  and the apex all fail to resolve), which also independently confirms the
  doc's own "no public A record" claim at `:56`.

The risk is small but real and it lands on the operator: someone reading this
after the apply runs the curl, gets nothing, and starts debugging a
certificate that is fine. One sentence under "How it works" fixes it, along
the lines of: nothing consumes these fields yet, the edge keeps serving its
current certificate, and the client-side check below applies once the cutover
lands.

I would not hold the commit for this. The shipped behavior is correct, the
acceptance contract already encodes the truth in row 10, and the fix is
additive prose that can ride with the ticket that makes the statements true.

## Carried forward for the record

The implementation uses `vault kv put key=@file` where plan requirement 7
mandates `vault write ... data=@file`. I have raised this in every cycle and
my position is unchanged: the implementation is right and the requirement is
wrong, because `data=@file` would store the whole PEM under a single field
named `data` and could not produce the three-field contract the marker
requires. I verified the actual behavior against a throwaway dev Vault in
cycle 1. The deviation is still not written down anywhere. This is
bookkeeping, not a defect, and the doc's field-shape section is now the
natural home for one sentence about it.

## Standing on the ticket as a whole

Four cycles, and the substance is sound. The blocking finding in cycle 1 was a
job that could never issue a certificate; that was fixed by restructuring
rather than patching. Every finding since has been confirmed and acted on, and
two of the fixes came back better than what I asked for: the account-key-
unchanged clause in the state guardrail, and the anti-loophole sentence in the
idempotency row.

What remains unproven is what cannot be proven from here: that `run
--renew-days 30` genuinely skips issuance against a live CA. The marker blocks
production issuance until two consecutive staging runs show an unchanged
serial, and the guard now points at that row and only that row. That is the
right gate in the right place, and it is the thing to actually run before the
flip.

Scope is clean. `acme.tf`, `acme.hcl` and `variables.tf` are untouched this
cycle, the ledger diff is harness bookkeeping, and every changed line across
all four cycles traces to the ticket or to a finding I raised.
