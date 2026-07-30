# Plan premise sweep, 2026-07

Thirteen loop tickets had never had a plan-level review. Each was reviewed
by the loop's `loop-plan-reviewer` agent against the repo and the live
cluster. This page records what each review found, what was corrected, and
what a later ticket still has to decide.

## What a verdict here means, and what it does not

Read this before trusting a row.

- The verdicts come from a real premise-falsification pass, not a checklist.
  Each reviewer enumerated the plan's load-bearing assumptions, attacked each
  one against the running system, and returned `SOUND`, `PARTIALLY SOUND`, or
  `BROKEN` with evidence anchors. The full verdict for each slug is at
  `.loop/verdicts/<slug>.plan-validator.md`, and that file, not this table, is
  the authority.
- A `SOUND` verdict means no load-bearing assumption broke under attack. It is
  not a guarantee the plan is correct, and it is not a design review: whether
  the approach is the right one, given true premises, was never asked.
- **A ticket marked `needs deep review` has NOT been fixed by this audit.**
  A1 applied mechanical corrections only. Structural findings were recorded and
  handed on, per A1's requirement 4.
- A1 decided no fork on its own. Every fork the reviews surfaced appears under
  "Open forks for the operator". Five carry a recommendation and stay open.
  Fork 1 was put to the operator, who resolved it and directed the action A1
  then took; it is marked RESOLVED and records what was decided.

## Ground truth, read from the live cluster 2026-07-30

Three of the four findings that mattered in the 2026-07-25 reviews were
invisible from the repo alone, so every review was briefed to query the running
system. All reads, no mutation. This is the picture the thirteen reviews were
checked against.

**Nomad OIDC discovery is disabled, JWKS is served.**

```
$ curl -s http://192.168.2.30:4646/.well-known/openid-configuration
OIDC Discovery endpoint disabled
$ curl -s http://192.168.2.30:4646/.well-known/jwks.json
{"keys":[{"use":"sig","kty":"RSA","kid":"00d87b20-...","alg":"RS256",...}]}
```

Any plan needing an OIDC **discovery document** from Nomad rests on something
the cluster does not currently serve. A plan needing only a **JWKS URL** is
fine. This distinction is the root of the M1 finding.

**Vault auth and JWT trust.** `vault auth list` shows only `jwt-nomad/` and
`token/`. Under `jwt-nomad/`, `vault list auth/jwt-nomad/role` returns exactly
two roles:

| Role | `token_policies` | `bound_audiences` | `user_claim` |
| --- | --- | --- | --- |
| `nomad-workloads` (default role) | `nomad-workloads` | `vault.io` | `/nomad_job_id` |
| `acme` | `nomad-workloads`, `acme-tls-write` | `vault.io` | `/nomad_job_id` |

`vault read auth/jwt-nomad/config` confirms trust is by JWKS, not discovery:
`jwks_url=http://127.0.0.1:4646/.well-known/jwks.json`, `oidc_discovery_url`
unset, `default_role=nomad-workloads`, `jwt_supported_algs=[RS256 EdDSA]`.

**The `nomad-workloads` policy is job-scoped in part only.** The file is 24
lines and grants five things, not one:

1. Read on `secret/data/{{nomad_namespace}}/{{nomad_job_id}}` and `/*`. Job
   scoped, as commonly described.
2. List on `secret/metadata/{{nomad_namespace}}/*`. Namespace scoped.
3. **List on `secret/metadata/*`.** Not scoped at all.
4. **Read, create, and update on `bootstrap/data/*`,** commented "for rotation
   jobs," granted to every workload rather than to the rotation jobs.
5. **List on `bootstrap/metadata/*`.** Also unscoped.

Items 3, 4 and 5 are the lines an earlier plan omitted when it described this
policy as job-scoped by citing 11 of the 24 lines. F9 exists to narrow this.
Read back with `vault policy read nomad-workloads`, which renders six `path`
blocks.

**Vault mounts and OIDC provider state.** `vault secrets list`: `bootstrap/`
(kv), `consul/`, `cubbyhole/`, `identity/`, `nomad/`, `secret/` (kv v2),
`sys/`. Note there is **no `database/` engine mounted**. `vault policy list`:
`acme-tls-write`, `default`, `nomad-workloads`, `root`. Under `identity/oidc/`
a provider named `default` and a client named `test` already exist, so F2 is
not working from nothing.

**What the live jobs actually use.** Nineteen jobs run. Read back with
`nomad job inspect` on every one of them, not by grepping the repo:

- **Fifteen hold the default `nomad-workloads` role** (`Role: ""`):
  `backup-minio`, `backup-postgres`, `bifrost`, `grafana`, `haproxy`,
  `hermes`, `loki`, `memex`, `minio`, `mlflow`, `phoenix`, `postgres`,
  `prometheus`, `talat-consumer`, `talat-shim`.
- **One, `acme`, has a dedicated JWT role** (`Role: acme`), adding
  `acme-tls-write` (create and update on `secret/data/default/haproxy/tls`).
- **Three carry no `vault` block and hold nothing:** `nats`, `node-exporter`,
  `promtail`.

`talat-consumer` and `talat-shim` are the ones that matter here. They run on
the cluster and hold the shared policy, but **no job file for either exists in
this repository** (`grep -rl talat . --include=*.hcl` returns nothing). Any
ticket that reasons about who holds the policy by grepping `deployments/` will
miss two live holders. F9 is the ticket most exposed to this, and its reviewer
caught it independently.

*(This paragraph was corrected on 2026-07-30 during A1's own adversarial
review. It previously claimed fourteen jobs, listed `acme` inside the
default-role set, and omitted both talat jobs. That list was derived from a
repo-side grep and published under a live-readback heading, which is the exact
defect A1's requirement 3 exists to prevent. Recorded rather than quietly
replaced, because it is the most instructive error in this ticket.)*

**No job uses JWKS or OIDC for its own authentication.** `grep -rln
'jwks\|openid\|oidc' deployments/ --include=*.hcl` returns nothing. Workload
Identity is used to authenticate jobs *to Vault*, and nowhere else.

## The epic brief's memex claim is false

The shared epic context states that memex already verifies Nomad Workload
Identity JWTs against JWKS. It does not.
`deployments/applications/services/memex.hcl:138-140` sets
`MEMEX_SERVER__AUTH__ENABLED=true` and a static
`MEMEX_SERVER__AUTH__KEYS` list of API keys with policies. There is no JWKS
URL, no OIDC issuer, and no JWT verification anywhere in the job.

This claim sits above the ticket layer, and it is worth naming because
anything downstream resting on "keyless machine auth is already proven here"
inherits the error. The brief is not a file in this repository: the archived
S3 plan calls it "the shared epic context," and a search finds no owning
document. Nothing in `.loop/` can correct it, which is why A1 records it here
instead. This confirms A1's own Q3.

## Systemic findings, established independently of the reviews

These four hold across the set and were verified directly, not inferred from
any single verdict.

### 1. Every one of the thirteen is currently unpickable

`require_eval` is on in `.loop/config.json`. Running `loopctl eval <slug>` on
each in-scope slug returns:

- **F9: `absent`.** It has no eval marker at all.
- **The other twelve: `unsigned`.** Each marker exists but carries no
  `signed-off-by: <who> <when>` line.

So the loop would refuse to advance any of these thirteen into `implementing`
today, exactly as it refused A1 until its own marker was signed. This is not a
defect in any one plan, and A1 has deliberately not fixed it: signing is an
operator act, and an agent writing that line on the operator's behalf is
precisely what the gate exists to prevent. See the open forks below.

*(Challenged and upheld, 2026-07-30. A1's own documentation review pass called
this paragraph false, on the grounds that `unsigned` is not a status the
harness defines and that `require_eval` is content-blind. The operator
directed that the claim stand, on this evidence. **The `evals.py` and `ctl.py`
anchors below are in the `loop-harness` package that provides `loopctl`, not
in this repository, so they will not resolve from the repo root** (the plugin
lives under `.claude/plugins/`, whose directory name is hashed and not stable
enough to cite).
`src/loop_harness/evals.py:48` defines `UNSIGNED = "unsigned"`;
`evals.py:88-95` implements the `signed-off-by:` check; the `verify_eval`
docstring states "Only `VALID` clears the `require_eval` gate";
`eval_marker_present` returns `verify_eval(...).ok`; and `ctl.py:185-186`
passes that into the advance whenever the target stage is `IMPLEMENTING`.
Live, `loopctl eval F2-foundation-vault-oidc-provider` prints `unsigned: eval
marker has no 'signed-off-by: <who> <when>' line`. The reviewer's
"content-blind" quote is from the same docstring and refers to the eval's
substance never being graded, not to the sign-off being ignored. Recorded
rather than quietly kept, so a later reader sees the disagreement and its
evidence.)*

### 2. There were three world-moving events, not two

A1's own plan named two (F3 on 2026-07-24, the T1/T2/T3 re-plan on
2026-07-25). A third was found during the sweep and corrected into A1's plan:

**The bifrost work**, which is three commits, not one:

| Commit | Date | Insertions into the three `.tf` files |
| --- | --- | --- |
| `ac3267b` B1 | 2026-07-29 | 76 (10 providers, 12 secrets, 54 services) |
| `e17d8d0` fix: bifrost keys | 2026-07-30 | 67 (8, 23, 36) |
| `64f4adb` chore: fix bifrost | 2026-07-30 | 9 (services) |

**`e17d8d0`, not `ac3267b`, added the sixth Postgres role `bifrost`** to
`deployments/applications/database.tf`: `git log -S'"bifrost"' --
deployments/applications/database.tf` names only `e17d8d0`, and `ac3267b` does
not touch that file at all. Two of the three landed on 2026-07-30, the day of
this audit.

Seven in-scope plans cite those three `.tf` files: F8 (13 citations), R3 (9),
R1 (5), M2 (3), M1 (2), R4 (2), F7 (1).

*(Corrected 2026-07-30 during A1's own review, twice. This first claimed
"101 lines" for the three files, which was the whole-tree figure. It then
credited all drift and the `bifrost` role to `ac3267b` alone. A1's own F7 and
F8 reviewers named `e17d8d0` explicitly, so the summary lost a finding its own
evidence carried, which is the defect eval row 13 exists to catch.)*

This is the worst version of the pattern. The anchors still resolve, but to
different content, so a check that only asks "does this line exist" passes.
R3's review found `database.tf:88-96`, cited four times as "the reader
grants", now resolves to the body of a `postgresql_extension` resource.

### 3. The dropped ticket F4 gated two plans, in prose only

L2 and M2 each carried a prose completion block: the ticket "must not be
marked done until" F4 delivers network-wide `.localstack` DNS. F4 is dropped.
N2 is done and published public DNS records, so the need is met by other
means. **Both blocks were removed by this ticket** as mechanical corrections.
See the corrections at `L2-landing-homepage.md` and
`M2-minio-poc-human-tiers.md`, each quoting what it replaced.

The lesson outlasts the fix. Neither block appeared in front-matter, so
`loopctl graph` could not see it: every `depends_on` edge across all thirteen
plans resolves to a real slug and none names a dropped ticket. A gate written
in prose is invisible to the harness, which is why both survived F4's drop.

### 4. T3's hostname sweep is effectively complete

A1's non-goal 1 keeps this ticket off hostname renames because T3 owns them.
T3 has since closed. Seventeen files under `.loop/plans/` and `.loop/evals/`
still match `localstack`, but on inspection every live hit is one of: a Vault
KV path
(`default/minio/localstack`), the epic's own name, or deliberate historical
prose describing what was wrong before the cutover. No stale routed hostname
was found in an in-scope plan. Nothing to hand on.

## Triage

One row per in-scope plan. "Premise" is the reviewer's own finding, and "Triage"
is A1's disposition. The full verdict is at
`.loop/verdicts/<slug>.plan-validator.md`.

| Slug | Premise | Gate | Triage | Headline defect |
| --- | --- | --- | --- | --- |
| F2 | PARTIALLY SOUND | fail | needs deep review | The client set is four different numbers (body says 4, its own addendum 6, eval DoD 5, eval row 3 four). Decides what artifact exists, and L1/R1/R4/G1 all consume it |
| F7 | BROKEN | fail | needs deep review | The `deployer` policy forbids the `sys/*` and `auth/*` writes that `terraform apply` of its own root performs. Eval row 3 asserts that denial as proof of correctness, so the guardrail certifies the broken result green |
| F8 | BROKEN | fail | needs deep review | Acceptance is unachievable under the grant F7 declares. The brokered token cannot manage the Nomad ACL policy that defines it. Two eval rows are `git grep` guardrails that pass against wrong content |
| F9 | PARTIALLY SOUND | pass-with-required-fixes | **fixed** (mechanical) plus follow-ups | Claimed the bare-`vault {}` set was "every job except haproxy". Inverted: haproxy is bare, `acme` is the exception. Corrected inline. Remaining: no eval marker exists, and no edge to F1 |
| L1 | PARTIALLY SOUND | fail | needs deep review | The eval's redirect and cookie expectations are wrong for oauth2-proxy, so a correct implementation fails a 100%-threshold row. Also an L1 to L2 dependency cycle |
| L2 | BROKEN | fail | needs deep review | Body, code surface and subticket 6 mandate a `dash` backend pointing straight at Homepage, contradicting the plan's own resolved fork. Its security eval row passes today against a cluster with no Homepage at all |
| M1 | BROKEN | fail | needs deep review | MinIO `RELEASE.2025-09-07` **removed** `jwks_url`; only `config_url` works, and Nomad's discovery endpoint is disabled. No ticket owns setting `oidc_issuer`. Separately, the unnamed `identity` stanza writes no JWT to the alloc |
| R1 | BROKEN | fail | needs deep review | `mlflow/mlflow#10922` was closed `not_planned` 19 days before R1 was authored, "confirmed by the S3 spike finding" refers to a spike that never ran, and MLflow now ships a documented SSO plugin. Eval row 6 passes with basic auth fully intact |
| R2 | BROKEN | fail | needs deep review | `nats-server#5692` is an open documentation request, not the capability claim cited. `nats --creds` cannot carry a WI JWT. The target registry at `firebat:5000` does not exist |
| R3 | BROKEN | fail | needs deep review | Inlines S2's conclusion as settled, but S2 never ran and now forbids the mechanism R3 is built on. F9 owns the same policy and is narrowing it. `database.tf:88-96`, cited four times as the reader grants, resolves to a different resource |
| R4 | PARTIALLY SOUND | fail | needs deep review | Phoenix hard-requires an `email` claim. Vault emits none and silently drops the scope, so the callback dies after a successful login. Redirect URI literal is wrong. Two eval rows fail a correct implementation |
| S1 | BROKEN | fail | needs deep review | Its deliverable path `docs/notes/` was deleted after authoring, the operator's own fork chose `docs/rfcs/`, and the eval hardcodes the dead path into five 100%-threshold rows. The spike is unexecutable to a passing DoD |
| M2 | PARTIALLY SOUND | fail | **fixed** (mechanical) plus deep review | MinIO's per-target `redirect_uri` is deprecated and its replacement is server-global, so three tiers cannot have three callbacks, and HAProxy sets no `X-Forwarded-Proto`, so the derived callback is `http://` and cannot match. Dead F4 block corrected inline |

### The count

Twelve of thirteen returned a failing gate verdict. One, F9, returned
`pass-with-required-fixes`. **Not one plan passed clean.**

Eight premises came back `BROKEN`, five `PARTIALLY SOUND`. Every
`PARTIALLY SOUND` except F9 still failed on severity, because the surviving
core did not make the plan safe to hand to an implementer.

The 2026-07-25 reviews hit four for four on this pattern. Thirteen for
thirteen now. The rate is not evidence that the reviewer is harsh: the
findings are specific, cited, and in several cases verified against upstream
source at the exact release tag the cluster runs. It is evidence that plans
written against a moving system go stale faster than anyone re-reads them.

### Where the defects concentrated

Counting across all thirteen verdicts:

- **Stale premise**: found in nearly every plan. Three events moved the world
  (F3, the T1/T2/T3 re-plan, B1) and the plans were written before them.
- **Inlined conclusion**: R1, R2, R3, M2, F8, and softly L1 and F7. The
  dropped spike S3 is cited as authority by two plans that never saw it run.
- **Broken dependency edge**: M1 (the template case, confirmed and worse than
  recorded), F8 on F7, R4 on F2, M2 on F2, L1 in a cycle with L2.
- **Shape-check eval**: F2 (`detect-private-key` cannot see a client secret),
  F8 (two `git grep` guardrails), R1 (row 6 passes with basic auth intact),
  L2 (security row passes against an empty cluster), S1 (a `grep -Eq` with a
  backslash-escaped alternation that never matches). A related and more common
  defect: rows whose *shape* is fine but whose *expectation* is wrong, so a
  correct implementation fails. L1, R4 and M2 each carry two.
- **Unresolvable anchor**: found in most plans, and B1 is the main cause. The
  dangerous ones resolve to real but different content.

### What A1 changed, and what it deliberately did not

Three mechanical corrections were applied inline, each dated and each
recording what it replaced:

1. **F9**, the inverted haproxy/acme claim. One sentence, factual, verified
   live.
2. **L2**, the dead F4 completion block. F4 is dropped and N2 met the need.
3. **M2**, the same dead F4 block, false in all three of its clauses.

A fourth correction was applied to **A1's own plan**: it named two
world-moving events where there are three. B1 is now recorded there, with the
seven in-scope plans it affects.

No other plan's *substance* was touched. The other ten need structural rework,
not one-line repair: their required-fix lists run from five to eighteen items
and several reverse a design decision. Patching a false sentence inside a plan
that is going back for a rewrite adds churn and buys nothing, so per A1's
requirement 4 those findings stay in the verdict files. **No plan was
rewritten wholesale.**

**Then, on operator instruction (2026-07-30), all thirteen plans gained a
pointer.** Each now ends with a `## Plan review, 2026-07-30 (A1 premise
sweep)` section, roughly eighteen lines, carrying the premise verdict, the
gate verdict, the path to its verdict file, the headline defect, and an
instruction not to implement from the plan as written. The operator asked for
the findings to be reachable from the plan a future agent actually opens,
rather than only from a verdict file it has no reason to look for. The section
states in its own text that it is a pointer, not the record.

**Consequence, recorded rather than hidden:** those edits changed all thirteen
plan files, so **every `plan-validator` verdict is now bound to a stale plan
sha256.** That is correct behavior, not breakage. A verdict authorizes the
exact content it reviewed, and the content moved. Re-dispatch the reviewer
against the current plan before acting on any verdict as though it were fresh.

## Open forks for the operator

Five recorded and still open. Fork 1 was resolved by the operator on
2026-07-30 and is kept here with its resolution rather than deleted.

### Fork 1: RESOLVED by the operator, 2026-07-30. All thirteen are blocked

The fork was: all thirteen carry `A1-audit-plan-premise-sweep` in
`depends_on`, and A1's resolved Q1 said the edges stay after A1 closes because
"a satisfied dependency is harmless." That assumed the audit would return
mostly clean. It did not, so A1 closing would have made twelve plans with
failing premises actionable, inverting the gate's purpose.

**The operator directed A1 to perform the blocks.** All thirteen are now
`blocked` in the ledger:

- Twelve under `unresolved-design-fork`, each with a one-line reason naming
  the headline defect and pointing at its verdict file.
- **F9 under `eval-missing`**, deliberately not `unresolved-design-fork`. F9
  is the one plan that passed (`pass-with-required-fixes`), so blocking it as
  a design fork would state something false. Its real barrier is that it has
  no eval marker at all (`loopctl eval` returns `absent`), plus three required
  fixes.

`loopctl next` no longer offers any of the thirteen. The actionable set is now
C1, F1, N3, S2 and T5.

*(This section previously read: "before closing A1, `loopctl block` each
ticket whose gate verdict is `fail` ... A1 must not perform the blocks itself:
this is a lifecycle decision over twelve tickets and belongs to the operator."
The operator made that decision and directed A1 to carry it out, so the
recommendation is replaced by what happened. The reasoning that blocking is
the operator's call stands; the operator exercised it.)*

### Fork 2: none of the thirteen can be picked up anyway

F9 has no eval marker, and the other twelve are unsigned. Under `require_eval`
every one is refused at `implementing`. This is now a second layer under the
blocks from Fork 1, not the primary guard. *Recommendation:* do not rely on it
alone, and sign markers only alongside the rework each plan needs, never in a
batch, or signing becomes the formality the gate exists to prevent.

### Fork 3: `oidc_issuer` is unowned, and two tickets need it

M1 cannot work without a Nomad OIDC discovery document, and R1's machine
bearer path needs the same setting. Enabling it is an irreversible change to
a Nomad server config in an Ansible template, requiring a restart of a
single-server cluster. F1's Q7 records the fork, but no ticket owns the work.
*Recommendation:* decide `oidc_issuer` as its own foundation ticket before
either M1 or R1 is re-planned, since both plans' shape depends on the answer.

### Fork 4: two repo-level documents carry false premises

Neither is in A1's code surface, and nothing in `.loop/` owns either.

- **The epic brief** claims memex verifies Nomad WI JWTs against JWKS. It
  does not (see above). This confirms A1's Q3.
- **The agent instructions file claimed a private Docker registry, and
  `main` has ALREADY fixed it.** At this ticket's branch point (`64f4adb`),
  `AGENTS.md:74` and `:114` said the cluster deploys a private Docker
  registry. It does not: no registry job exists or runs, and every image
  comes from `docker.io` or `ghcr.io`. R2 inherited that claim and targeted
  its build at `firebat:5000`, which is nothing. Commit **`27dd367`** on
  `main`, landed after this branch point, rewrote the line to "Private docker
  registry: we use the GitHub registry" (`AGENTS.md:120`). Note `CLAUDE.md`
  is a symlink to `AGENTS.md`, so grepping `CLAUDE.md` through git reads the
  link target, not the content.

*Recommendation:* **no action on the instructions file; it is already
correct on `main`.** R2's plan still carries the inherited error, and that is
covered by R2's own required-fix list. The epic brief has no file to correct,
so carry that one into whatever replaces it.

*(Corrected 2026-07-30. This fork previously asserted the claim was live and
recommended a fix commit. That was true at the branch point and false by the
time it was written, because `main` moved two commits ahead during this
ticket. A stale premise in the audit that exists to catch stale premises,
caught by A1's own documentation review.)*

### Fork 5: A1 may recommend a drop, and does not make one

Per A1's Q2, no ticket is dropped by this audit. S1 is the only candidate a
reader might reach for, and its reviewer explicitly checked and found it is
**not** redundant, unlike the dropped S3: no other ticket pre-decides the
Boundary keep-or-drop question. *Recommendation:* fix S1's premise and its
eval path, and do not drop it.

### Fork 6: this document sits in the directory it calls S1's headline defect

S1's row above says its deliverable path `docs/notes/` was deleted after
authoring. This file is `docs/notes/audit/plan-premise-sweep-2026-07.md`, so
it recreates that directory. `git ls-tree -r HEAD --name-only | grep -c
'^docs/notes/'` returns 0 at HEAD; commit `cc22050` (2026-07-26) removed the
contents.

A1's plan and its eval marker both hardcode this path, so moving it is not a
mechanical fix and was correctly out of scope. Walking past it silently was
not an option either. Note `docs/rfcs/`, the home S1's operator fork chose,
does not exist yet. *Recommendation:* decide where audit and RFC output lives
before the next such document, and retarget S1's eval in the same pass.

## Method and limits

Thirteen `loop-plan-reviewer` agents, dispatched concurrently, each briefed
with the repo root, the plan path and slug, the pass id `plan-validator`, the
plan's sha256, and its verdict path, plus A1's five defect classes as required
attack surface. Each verified the fingerprint itself before binding it. All
cluster access was read-only by instruction. **Nine of the thirteen verdicts
record what they ran** (F2, L1, L2, M1, M2, R1, R2, R3, S1), under varying
headings: `## Method note`, `## Cluster commands run (all read-only)`,
`## Read-only compliance`. **Three record nothing** (F7, F8, R4), and F9
asserts it was read-only without saying what it ran. For those four, the
read-only claim rests on the briefing rather than on the verdict's own record.

*(Corrected twice, 2026-07-30. This first said "all but one (R4's)", then
"six do not (F7, F8, F9, L1, R2, R4)". The second count was produced by
grepping for the literal heading `## Method note`, which is a formatting
property, not the substantive one this sentence asserts: L1 and R2 both
enumerate every command run and state no mutation was issued, under different
headings. Counting the wrong attribute and reporting it as the right one is
this audit's own defect class, committed twice in the sentence that describes
the audit's limits.)*

The limits worth stating:

- **This audit judges premises, not designs.** A plan can have every premise
  hold and still be the wrong approach. No reviewer was asked that question.
- **A reviewer can be wrong.** Where one could not settle a claim it returned
  `UNCERTAIN` rather than guessing, and those are visible in the verdicts.
  Treat a required fix as a strong finding to check, not an instruction to
  apply unread.
- **The verdicts bind the plans as of 2026-07-30.** Each `plan:` fingerprint
  is the sha256 reviewed. Editing a plan stales its verdict, which is the
  intended behavior: the fix and the re-review travel together.
