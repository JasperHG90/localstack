---
verdict: pass
tree: cae4315c2e5f8c12e00b2bb73ab17a32c62f3380
---

# Documentation freshness — G1-grafana-native-oidc-login, cycle 4 (final)

**Verdict: pass.** All three cycle-4 fixes landed and every claim in them is
true. The cite sweep the briefing asked for is complete and turned up one
more stale cite, which predates this ticket and which this diff did not
shift. Nothing required. Six advisory items: four source comments, one
pre-existing doc table row, and one falsified premise in another ticket's
plan.

## Scope binding: omitted deliberately, same as cycle 3

My briefing gave a tree fingerprint and a verdict path. It gave no 64-hex
scope digest and no `verdict_binding_inputs`. The contract says to write the
digest I was given and never one I computed for a different set, so I omit
`bound_paths`, `scope` and `citations` and let the verdict fall back to
whole-tree binding, which is stricter. The `tree:` line above is the
fingerprint I was given, and `.loop/stamp.json` carries the same value.

The reviewed path set, for the record. Working files:
`deployments/infrastructure/auth_userpass.tf`,
`deployments/infrastructure/nomad_oidc.tf`,
`deployments/infrastructure/oidc.tf`,
`deployments/infrastructure/secrets.tf`,
`deployments/infrastructure/services.tf`,
`deployments/infrastructure/services/grafana.hcl`,
`deployments/infrastructure/services/oauth2-proxy.hcl`,
`deployments/infrastructure/variables.tf`, `docs/dash-landing-page.md`,
`docs/haproxy_reverse_proxy.md`, `docs/monitoring.md`,
`docs/postgres-vault-dynamic-creds-spike.md`, `docs/vault-human-auth.md`.
Harness state also modified: `.loop/evals/G1-grafana-native-oidc-login.md`,
`.loop/ledger.json`.

`nomad_oidc.tf` is new to the path set this cycle. Cycle 3 raised DOC-G1-14
against a file the diff did not touch; the diff touches it now.

## The three cycle-4 fixes: all landed, all true

### 1. DOC-G1-16 fixed — `oidc.tf:72-77`

The overreaching clause is gone and the replacement is bounded and correct.
`deployments/infrastructure/oidc.tf:73-77`:

    ### empty and offers no setting to disable that check, so Grafana cannot work
    ### without this scope. Most consumers can: memex and the Nomad client both
    ### speak OIDC with no proxy and log people in on `groups` alone. R4 (Phoenix)
    ### is the other that needs it; G1 created it, and R4 consumes it rather than
    ### declaring a second one.

Checked against all three sources the briefing named.

**memex.** `deployments/infrastructure/memex_oidc.tf:70-83` is a public
`vault_identity_oidc_client` with a loopback callback and PKCE. Nothing
proxies it: `docs/memex-oidc-verification.md:4` says humans arrive "via
`memex auth login` against the Vault `lab` provider". Its scopes are
`docs/memex-oidc-verification.md:246`, `scopes: ["openid", "groups"]`, and
the V3 probe at `:312` sends `scope=openid groups`. So memex speaks OIDC
with no proxy and logs people in on `groups` alone. True.

**The Nomad client.** `deployments/infrastructure/nomad_oidc.tf:136` is a
`nomad_acl_auth_method` pointed straight at the Vault provider, with
`nomad_oidc.tf:151` `oidc_scopes = [vault_identity_oidc_scope.groups.name]`.
No proxy, `groups` alone. True.

**R4/Phoenix.** `.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:146-148`:
"Phoenix always requests `openid email profile` and **hard-requires an
`email` claim**". True.

**"Most consumers can."** Of the five clients in
`oidc.tf:99-107` (smoke, nomad, memex, oauth2-proxy, grafana), only grafana
needs `email`. True on the current set, and R4 makes it two of six.

No wrong claim swapped in for the old one.

### 2. DOC-G1-14 fixed — `nomad_oidc.tf:159-162`

`deployments/infrastructure/nomad_oidc.tf:159-160`:

    # No `claim_mappings`. `preferred_username` is a `profile`-scope claim, and
    # this provider does not advertise `profile`, so mapping it

The replacement premise is true. `oidc.tf:122-125` reads
`scopes_supported = [groups, email]` and nothing else, so `profile` is
genuinely absent. The conclusion survives unchanged, because it was always
resting on `profile`'s absence rather than on the list's length.

The fix is better than the minimum. Asserting an absence instead of an
exhaustive list makes the comment robust to the next scope anyone adds,
which is the failure that produced DOC-G1-14 in the first place.

### 3. DOC-G1-19 (adversarial) fixed — `postgres-vault-dynamic-creds-spike.md:35`

Verified both directions. `git show HEAD:deployments/infrastructure/secrets.tf`
lines 74-88 are exactly `resource "vault_kv_secret_v2"
"postgres_root_credentials" { ... }`, brace to brace, so the old cite was
right at HEAD. The working tree has that same block at `secrets.tf:98-112`,
brace to brace, so +24 is the exact shift and `:98-112` is exact.

The failure the adversarial pass described was live: current `:74-88` spans
the tail of the `grafana_oidc_client` comment and that resource's body, a
`vault_kv_secret_v2` like the one being cited. A reader would have landed on
a plausible wrong answer with nothing to signal it.

## The sweep the briefing asked for: complete, one more found

Six `path:line` cites into shifted files exist outside `.loop/`, across
`docs/`, `README.md`, `deployments/`, `cli/`, `bootstrap/` and `ansible/`.
Five are correct in the current tree:

- `oidc.tf:215` cites `vault-human-auth.md:288-292`. That range is branch 3
  verbatim, opening on "**No group and no assignment**: set
  `assignments = ["allow_all"]`". Correct.
- `secrets.tf:74` cites `vault-human-auth.md:315-318`, the
  `detect-private-key` paragraph, ending on "`hvo_secret_...` is not one of
  them." Correct.
- `dash-landing-page.md:30` cites `vault-human-auth.md:329-336`, opening on
  the bold lead and closing on "Observed 2026-08-02, not yet root-caused."
  Correct.
- `postgres-vault-dynamic-creds-spike.md:35`, above. Correct.
- `memex-oidc-verification.md:57` cites
  `deployments/applications/secrets.tf:79-86`, a different file this diff
  never touches. Out of scope and unaffected.

The sixth is new, and is DOC-G1-21 below.

I also swept for cites written without the `path:` form ("lines 74-88",
"L74") across `docs/`, `README.md` and `bootstrap/`. The only regex hits are
the two SSH port-forward commands at `monitoring.md:180` and `:196`, both
false positives.

Four docs name a shifted file and had never been checked in any cycle:
`gcs-backups.md:79-83`, `nats.md:204` and `:213`, `observability-python.md:96`
and `:180`, `riscv-integration.md:185` and `:211`. All are file-name-only
references with no line anchors and no claim this diff falsifies.
`gcs-backups.md`'s "Two variables" list is scoped to its own `## Configuration`
section for the GCS backup job, so `vault_operator_email` does not stale it.

Two more absence checks worth naming, because both looked like likely hits:

- `docs/credential-rotation.md` covers `TAILSCALE_AUTH_KEY` and `GITHUB_PAT`
  only. The new KV2 path `default/grafana/oidc` strands nothing there.
- `docs/vault-human-auth.md:65-69` gives the discovery `curl` with **no**
  expected output, so adding `email` to `scopes_supported` does not stale a
  printed scope list anywhere in the repo.

## The two judgment calls the briefing asked me to record

### DOC-G1-15 — stays advisory. The third instance does not tip it.

`docs/vault-human-auth.md:43` still reads "Two KV2 writes: the operator
password, and the smoke client's credentials", and `:45-49` repeats the count
as prose. `secrets.tf` holds eleven `vault_kv_secret_v2` resources (`:15`,
`:37`, `:52`, `:76`, `:98`, `:123`, `:153`, `:170`, `:189`, `:210`, `:236`),
of which five belong to this doc's story.

Why it stays advisory:

- **It was already wrong by two.** Under its own scoped reading, the row
  omitted `oauth2_proxy_oidc_client` (`:210`) and `oauth2_proxy_cookie_secret`
  (`:236`) at HEAD. This diff deepens an existing staleness rather than
  opening a new way for a reader to be wrong.
- **The wrong belief drives no wrong action.** Someone hunting Grafana's OIDC
  client secret would read `:45-49` and conclude only two KV2 secrets exist.
  But no operator procedure needs that path: it is Terraform-managed and read
  only by the job template, through `services.tf:431` passing
  `vault_kv_secret_v2.grafana_oidc_client.path` into `grafana.hcl`. The doc
  that an operator actually reaches for, `docs/monitoring.md`, gives the path
  they do need (`default/grafana/admin`) in its new "If Vault is down"
  section.
- **The asymmetry with cycle 3 is principled.** Cycle 3 made the row above
  (`:42`, `oidc.tf`) exhaustive because that row's staleness was caused by
  this diff, which added the grafana client to `oidc.tf`. `:43` was stale
  before the ticket existed. The repo's surgical-changes rule draws the line
  in exactly that place.

Fix on the next touch, one row and one list:

    | `secrets.tf` | The KV2 writes for this story: the operator password, the
    smoke client's credentials, and each consumer client's credentials
    (oauth2-proxy, grafana) |

and either drop the "Two secrets land in KV2" count at `:45` or scope it to
the two the walkthrough below it actually uses.

### DOC-G1-03 — stays advisory, but this is the closer call.

The header is now wrong in three places, not one. `oidc.tf:4` still says "ONE
throwaway smoke-test client". `:7` lists the consumer tickets as "dash/L1,
mlflow/R1, phoenix/R4, the MinIO tiers/M2" and omits grafana. `:8` says those
clients "are NOT created here", while `:159`, `:192` and `:232` create three
clients in this file.

Why it stays advisory:

- **The operative instruction is unchanged and correct.** The header tells a
  consumer ticket to create its own `vault_identity_oidc_client` and its own
  `vault_identity_oidc_key_allowed_client_id`. G1 did exactly that
  (`oidc.tf:232` and `:246`). The stale part is a claim about file layout.
- **The file refutes itself in view.** `oidc.tf:213` opens
  `### --- G1: Grafana (native generic OAuth client) ---`, directly below
  `### --- L1: oauth2-proxy (landing page gate) ---` at `:176`. And `:94`
  says `>>> CONSUMER TICKETS: APPEND YOUR CLIENT HERE. <<<`, which
  contradicts `:8` outright. A reader is misled for the length of one scroll,
  not into a wrong action.
- **It is a source comment.** Nothing under `docs/` repeats it. Two of the
  three client instances predate this ticket.

The one point that weakens the surgical-changes defense, and I want it on the
record: this diff edited that very sentence, changing "the shared scope" to
"the shared scopes" at `:4`, and left "ONE" standing one clause away. The
next touch is a three-line rewrite of `:4-10`, not a one-word one. It should
be the first thing done the next time anyone opens `oidc.tf`.

## Findings

### Advisory — DOC-G1-04 (low): held a third time, on a sharper reason

`docs/monitoring.md:58` still writes the KV2 path without its mount:

    in as `admin` with the password from Vault KV2 at `default/grafana/admin`.

`secrets.tf:53-54` sets `mount = vault_mount.kvv2.path` and
`name = "default/grafana/admin"`, and `vars/prod.tfvars:1` sets
`secret_mount = "secret"`, so the working path is
`secret/default/grafana/admin`.

Re-attacked and held, with a better reason than "the repo is inconsistent".
The page gives **no command** at `:56-58`. It names a location in prose.
There is nothing here to fail, only a path missing its mount that four
sibling docs supply. The break-glass framing cuts the same way: `:60` tells
the reader to fetch the path *before* the emergency, so the moment of use is
a calm one. Still the top item for the next touch of this page.

### Advisory — DOC-G1-21 (low, NEW): `oidc.tf:178` cites branch 2 for branch 3

`deployments/infrastructure/oidc.tf:177-178`:

    ### Flat access: anyone who completes Vault login is let through. Branch 3 of
    ### the documented procedure (docs/vault-human-auth.md:282-290) — the built-in

Branch 3 is `vault-human-auth.md:288-292`. The range `:282-290` opens on
branch 2's body ("**A new entry in `local.app_user_groups`**") and truncates
branch 3 before its last line.

**Pre-existing, and not shifted by this diff.** `git show HEAD` confirms
`vault-human-auth.md:282-292` is byte-identical at HEAD and now: the only
shift this diff makes in that file is +1, starting at `:306`. So the cite was
already wrong before the ticket.

It surfaces now only because cycle 2's DOC-G1-10 fixed the identical defect
in the new grafana comment at `oidc.tf:215`. The file now carries two
comments making the same branch-3 claim against two different ranges, one
right and one wrong. Advisory: pre-existing, source comment, and the
surgical-changes rule tells the implementer not to touch it. It is a
one-character fix (282 to 288) whenever `oidc.tf` is next opened.

### Advisory — DOC-G1-22 (low, NEW): R4's plan premise is falsified

`.loop/plans/R4-rollout-phoenix-oauth2-proxy.md:127-130`:

    - **The provider advertises exactly one scope, and it is not `email`.**
      `oidc.tf:100` is `scopes_supported = [vault_identity_oidc_scope.groups.name]`,
      and `oidc.tf:55-70` defines that sole `groups` scope. There is no `email`
      scope and no entity carries an email

G1 falsifies both halves: `oidc.tf:85-90` is the `email` scope,
`oidc.tf:122-125` puts it in `scopes_supported`, and `auth_userpass.tf:47`
gives the operator entity an `email`. R4's anchors moved too: `oidc.tf:100`
is now `:122`, and `oidc.tf:80-84` (`local.oidc_provider_client_ids`) is now
`:99-107`. Worse, `R4:316-324` instructs its implementer to create the
`email` scope and add the `email` metadata key, work G1 has already done.

This is the strongest advisory of the pass and the only place a reader is
told to do work already done. It stays advisory for four reasons:

1. `.loop/plans/` is loop-harness state with its own gate. The plan-validator
   pass runs before a plan flips to `ready`, and R4 already has a
   plan-validator verdict on file that will be re-run.
2. The repo has a named process for this exact drift class,
   `A1-audit-plan-premise-sweep`, and R4's own front matter already lists A1
   in `depends_on`.
3. The failure is loud, not silent. An implementer following `R4:316-319` to
   add a second `vault_identity_oidc_scope` named `email` gets a Terraform
   duplicate-resource error on the first plan.
4. Editing another ticket's plan is outside an implementer's remit and would
   collide with the plan-validator's own authorship.

The diff does hand off in-repo, at `oidc.tf:76-77`: "G1 created it, and R4
consumes it rather than declaring a second one." That is the right signal in
the right place. **Recommend the operator re-run R4's plan-validator before
dispatching R4.**

### Advisory — DOC-G1-23 (trivial, NEW): a count off by one

`docs/vault-human-auth.md:291`: "Four of the six known consumers declare flat
access and want this." Grafana is a seventh, and it declares flat access
(`oidc.tf:240`, `assignments = ["allow_all"]`).

Same class as DOC-G1-15, and trivial. The sentence is a rationale for why
branch 3 is the common answer, not an instruction. The stale count
understates its own point and steers nobody to the wrong branch. Roll it into
the DOC-G1-15 fix when that row is next touched.

### Advisory — DOC-G1-15, DOC-G1-03: judged above, both stay advisory.

## Re-attack of the settled ledger

Absence claims for the findings the cycle-4 edits do not touch:

- DOC-G1-01 — no change in scope, still holds; `monitoring.md` is untouched
  by the cycle-4 delta.
- DOC-G1-01b — no change in scope, still holds; trivial.
- DOC-G1-02 — no change in scope, still resolved; `vault-human-auth.md` is
  untouched by the cycle-4 delta.
- DOC-G1-05 — no change in scope, still holds. Re-ran the URL sweep anyway:
  `monitoring.md:231`, `:233`, `:314`, `:494`, `:501`, `:526` and
  `haproxy_reverse_proxy.md:22` are HAProxy-backend, firewall-probe and
  history contexts, all still true; `tiles.json:22`,
  `tls-certificates.md:125` and `dns.md:91` already used the edge hostname.
  HAProxy does route it: `haproxy.hcl:105` matches
  `grafana.lab.orangecluster.nl` and `:152` dials `192.168.2.47:3000`, so
  `monitoring.md:34`'s new instruction reaches a real front door.
- DOC-G1-06 — extended this cycle; see the sweep section.
- DOC-G1-08, DOC-G1-09, DOC-G1-10 — re-opened and re-verified in the current
  tree; see the sweep section. All three still land.
- DOC-G1-11 — no change in scope, still resolved; `oauth2-proxy.hcl` is
  untouched by the cycle-4 delta.
- DOC-G1-12 — no change in scope, still resolved, and its source-comment twin
  DOC-G1-16 is now fixed as well, so the universal is gone from both sites.
- DOC-G1-13 — no change in scope, stays overturned.
- DOC-G1-17 — no change in scope, still clean.
- DOC-G1-18 — re-swept, still no drift.

## Slop scan, all four cycles' added prose

65 added lines across `docs/monitoring.md`, `docs/vault-human-auth.md`,
`docs/haproxy_reverse_proxy.md`, `docs/dash-landing-page.md` and
`docs/postgres-vault-dynamic-creds-spike.md`. Layers 0, 1 and 2 pass.

Zero em dashes. Zero ` -- `. Zero smart quotes. Zero semicolon splices. Zero
tier-1 slop. Zero British spellings (the two `behaviou?r` regex hits are the
American "behavior" and "behaviors"). Zero `TODO`/`FIXME`. Zero
throat-clearing openers, participial tails, spatial copula, three-fragment
bursts or emphasis crutches. Every backticked identifier, path and URL in the
added prose resolves, including `vault_operator_email` (`variables.tf:64`),
`default/grafana/admin` (`secrets.tf:54`), the Editor role
(`grafana.hcl:110`, `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH = "'Editor'"`)
and the "Sign in with Vault" button label (`grafana.hcl:104`,
`GF_AUTH_GENERIC_OAUTH_NAME = "Vault"`). Two added lines exceed 80
characters, both table rows at `vault-human-auth.md:41` and `:42`, matching
the rows they replaced.

Four negative-parallelism hits, unchanged from cycle 3 and none required:
`monitoring.md:45-46` ("a configuration or claim fault, not a permission
one"), `vault-human-auth.md:306` ("not just read it", pre-existing wording),
`:465` ("an empty string, not an error"), and `:471` ("depends on the
service, not on a rule"), the one low-confidence hit, which is load-bearing
because it is the correction DOC-G1-12 asked for.

Cycle 4 added no markdown prose. Its one `.md` edit is the DOC-G1-19 cite
correction, so the markdown scan is unchanged.

It did add source-comment prose at `oidc.tf:72-77`, which carries one
low-confidence semicolon splice at `:76`: "R4 (Phoenix) is the other that
needs it; G1 created it, and R4 consumes it rather than declaring a second
one." Surfaced, not demanded. The slop rule scopes Layer 2 to markdown docs,
it marks semicolon splices low-confidence and surface-only, and both
semicolons and em dashes are established house style in these `.tf` comments
at HEAD (7 em dashes in `oidc.tf`, 3 in `nomad_oidc.tf`, all pre-existing).

## Why pass, with the cap exhausted

The test is whether a reader following the current docs would now be wrong.
Under `docs/`, they would not. Every user-facing surface this diff changes is
documented in step: the sign-in flow and the `email` requirement in
`monitoring.md:32-52`, the break-glass admin path in `:54-65`, Grafana's
proxy-free SSO in `haproxy_reverse_proxy.md:26-31`, the second scope and the
entity metadata key in `vault-human-auth.md:41-42`, `:306-308` and
`:458-480`, and the shifted cite in
`postgres-vault-dynamic-creds-spike.md:35`.

What remains is four source comments, one doc table row that was already
stale by two before this ticket, and one plan belonging to a different ticket
that has its own gate and its own audit process. None of them is worth
holding the ticket for while the operator sleeps. The one item I would put in
front of the next person to touch this code is DOC-G1-22: re-run R4's
plan-validator before R4 is dispatched, because G1 has done a third of R4's
work and R4's plan does not know it.

Ledger updated:
`.loop/scratch/G1-grafana-native-oidc-login.documentation/findings.json`,
25 entries.
