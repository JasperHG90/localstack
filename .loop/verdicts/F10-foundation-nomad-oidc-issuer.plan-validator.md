---
verdict: pass
plan: c91021659000e85b5d1633e682e23b4aa1447df568bbdb109280bb8f57d53811
---

# Plan review: F10-foundation-nomad-oidc-issuer (fifth pass — contract restructure)

Fingerprint confirmed locally: `sha256sum .loop/plans/F10-foundation-nomad-oidc-issuer.md`
= `c91021659000e85b5d1633e682e23b4aa1447df568bbdb109280bb8f57d53811`, matching
the coordinator's message.

`loopctl verify-plan` now exists (it did not two passes ago; `loopctl --help`
now lists it alongside a new `verify-eval-substance`). Ran it directly:
`loopctl verify-plan F10-foundation-nomad-oidc-issuer` → `valid`, exit 0, no
warnings. That is the mechanical floor the coordinator described; it is
clean. The rest of this pass is the independent falsification the floor
doesn't replace: confirming the restructuring changed nothing but headings
and anchors, and sanity-checking the new Premises section against the
content it claims to restate, rather than taking the coordinator's "purely
mechanical" characterization on trust.

## Structural changes: verified as claimed, nothing else moved

- **Title line** (`plan:9`): now `# Ticket: F10-foundation-nomad-oidc-issuer
  — Make Nomad a full OIDC issuer, not just a JWT signer`. Matches claim 1.
- **Section numbering** (`grep -n "^## "`): `## 1. Title` through `## 11.
  Open questions`, sequential, no gaps, no reordering — confirmed by listing
  every `## ` heading in the file. Body text under each heading is
  byte-identical to the version I last passed clean (fingerprint
  `50a10a2b...`), re-checked line by line: `§4 Context`, `§5 Non-goals`, `§6
  Requirements`, `§9 Risk`, `§10 Subtickets`, and `§11 Open questions` all
  read the same prose, same corrections, same dates, same claims — only the
  heading prefixes (`## 4.` etc.) and a handful of anchor strings changed.
- **New `## Premises / assumptions` section** (`plan:315-356`, unnumbered in
  the file itself — the coordinator's "§12" is my numbering convention for
  it, not literal heading text; `loopctl verify-plan` accepts it as written
  and reports `valid`, so the heading text itself satisfies the checker).
- **Anchor disambiguation** (claim 4): every previously-bare
  `nomad_client/tasks/main.yml` and `nomad_server/tasks/main.yml` citation
  now carries its `bootstrap/roles/.../` prefix. Confirmed by `grep -n
  "nomad_client/tasks/main.yml\|nomad_server/tasks/main.yml"
  .loop/plans/...md`: all 6 matches now read
  `bootstrap/roles/nomad_server/tasks/main.yml:...` or
  `bootstrap/roles/nomad_client/tasks/main.yml:...`, none bare. Same check
  for `nomad.hcl.j2`: every citation carrying a line number now carries the
  full `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` path (`plan:47,
  70, 101, 131, 227, 235, 328`); the remaining bare `nomad.hcl.j2` mentions
  (`plan:41, 83, 227`) carry no line number and are plain-prose references
  to the file, not anchors — not something the disambiguation fix needed to
  touch, and `loopctl verify-plan` agrees (`valid`).

No content was dropped: I re-read the full file top to bottom and compared
it against the version bound to my last "pass" verdict (fingerprint
`50a10a2b...`), and every claim, correction, date, and evidentiary detail
from that version is present here in the same place, under the
correspondingly-numbered heading.

## New Premises section: sanity-checked against the plan's own body, not new claims

Each of P1-P8 is a restatement of a claim already verified elsewhere in the
plan, and I checked each one against both its cited source-of-truth inside
the plan and (where practical) against live state again this pass, not
against the coordinator's description of them:

- **P1 — `oidc_issuer` absent, repo and live.** Matches `§4 Context` bullet
  1 verbatim (same grep, same anchor). Re-verified live this pass:
  `GET /v1/agent/self` (with a valid ACL token) → `config.Server.OIDCIssuer:
  ""`.
- **P2 — discovery disabled, JWKS not.** Matches `§4` bullet 2. Re-verified
  live in the prior pass (404 `OIDC Discovery endpoint disabled`; JWKS 200
  with 3 keys); not re-run this pass since nothing touched it.
- **P3 — firebat is the only server, also a client, also the edge node.**
  Matches `§4` bullet 3 and the `nomad.hcl.j2:38-39` / `haproxy.hcl:6-9`
  anchors, both re-confirmed byte-exact in the prior two passes.
- **P4 — `jwks_uri` derives from the configured issuer, not the request
  host.** Matches `§11` Q1's SETTLED paragraph, same probe (throwaway
  `nomad agent -dev` at 2.0.3). This is the plan's central technical claim;
  I did not re-run the probe myself this pass (nor last pass — see prior
  verdict's "Most dangerous assumption" note), relying on the concrete,
  falsifiable prior measurement rather than re-deriving it against a
  one-line structural diff that didn't touch it.
- **P5 — `iss` change safe, `bound_issuer` empty.** Matches `§4` bullet 5.
  Re-verified live in the prior pass (`vault read auth/jwt-nomad/config` →
  `bound_issuer: ""`).
- **P6 — a Nomad hostname is routed at the edge over HTTPS.** Matches `§11`
  Q1's evidence paragraph and the `haproxy.hcl:101,136-137` anchors,
  re-confirmed byte-exact in the prior pass.
- **P7 — `just bootstrap` restarts all five agents; only the targeted
  playbook restarts firebat alone.** Matches `§4`'s "How to apply it" bullet
  and the `§9 Risk` bullet on the same subject, both citing
  `bootstrap/justfile:40-49` (recipe lines 40-48, confirmed byte-exact) and
  `bootstrap/roles/nomad_client/tasks/main.yml:56,65` (confirmed byte-exact
  in the prior pass).
- **P8 — the `c744b92` advertise block's deployment status is UNCERTAIN.**
  Matches `§4`'s "Check for a second pending change" bullet and the `§9
  Risk` bullet on the same subject. This is my own finding from an earlier
  pass (SSH to `192.168.2.30` returns `Permission denied (publickey)`), and
  the plan states it as genuinely unresolved rather than asserting it away
  — correctly.

No premise introduces a claim absent from the rest of the plan; each carries
either a `path:line` anchor or an explicit probe/uncertainty marker, as
described.

## Premise verdict: SOUND

Unchanged from the prior pass. This round changed structure and citation
precision, not substance, and I found no regression: no anchor that
previously resolved now fails to, and no claim changed meaning.

**Most dangerous assumption, unchanged:** P4 (jwks_uri/iss derive from the
configured issuer, not the request host) — the plan's whole reason for
existing rests on it, and it is backed by a concrete empirical test rather
than documentation, but that test was run in an earlier pass, not this one.

## Contract hygiene: clean

- **Real code surface with resolved anchors:** confirmed above; every
  anchor with a line number now carries an unambiguous full path.
- **Discovered, not assumed, gates:** unchanged, still accurate.
- **Explicit non-goals:** present, unchanged, still strong (`§5`).
- **Tests homed in the code surface:** unchanged, the eval still names real
  paths and commands.
- **Forks surfaced, not silently decided:** Q1 settled and matching the
  signed eval; Q2 an honest recommendation (`§11`).
- **Ticket-contract structure:** now satisfied — numbered `## 1.`-`## 11.`
  sections, a `# Ticket: <slug> — ...` title line, and a `## Premises /
  assumptions` section — confirmed both by direct inspection and by
  `loopctl verify-plan` returning `valid`.

## Method

Read-only throughout. Commands run: `sha256sum` on the plan file; `loopctl
verify-plan F10-foundation-nomad-oidc-issuer` (now available; returned
`valid`); `grep -n "^## "` to enumerate headings; `grep -n` for
`nomad_client/tasks/main.yml`, `nomad_server/tasks/main.yml`, and
`nomad.hcl.j2` to check anchor disambiguation; a full re-read of the plan
file compared section-by-section against the version bound to my last "pass"
verdict; live `curl` with an ACL token against `/v1/agent/self` to
re-confirm `OIDCIssuer: ""`. No mutating command was run against the
cluster or the repo.
