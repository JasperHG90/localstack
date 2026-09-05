---
verdict: pass-with-required-fixes
plan: dffd1acac3d38375956d13e669cae460da393cb549e5d7fe84c59db31a74644a
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: ca7e87b6f893eaf9d213b66e003907f72116168753e1e93049cd332a74e45d96
fix_sections: 6, 7, 10
citations: deployments/applications/services/dash.hcl:40 =       resources {
  deployments/applications/services/dash.hcl:41 =         cpu    = 50
  deployments/applications/services/dash.hcl:42 =         memory = 32
  deployments/applications/services/dash.hcl:132 =       resources {
  deployments/applications/services/dash.hcl:133 =         cpu    = 200
  deployments/applications/services/dash.hcl:134 =         memory = 128
  deployments/applications/services/dash/backend/src/dash_app/_http.py:20 = class FetchError(Exception):
  assets/registry-mockup.html:533 =   var KITS = [
  .loop/plans/L5-landing-registry-tab.md:1251 =     `cpu = 50` and `memory = 32`; the `backend` task's (`:132-135`)
  .loop/plans/L5-landing-registry-tab.md:1289 =     128 MB. **The registry client must cap the bytes it reads from any
  .loop/plans/L5-landing-registry-tab.md:1290 =     single blob response and fail loudly past that cap**, counting as
  .loop/plans/L5-landing-registry-tab.md:1295 =     `Content-Length` header is not the check: it can be absent, and
  .loop/plans/L5-landing-registry-tab.md:1299 =     **The cap is 1 MiB, 1_048_576 bytes, and the number is argued
  .loop/plans/L5-landing-registry-tab.md:1307 =     one `model.onnx` layer is 309,664,768 bytes (§4 P4), 295x the cap,
  .loop/plans/L5-landing-registry-tab.md:1418 =   `get_layer_file` (blob to `tarfile.open(fileobj=..., mode="r")` to
  .loop/plans/L5-landing-registry-tab.md:1801 =   - `test_registry_client.py`, the blob byte cap (Requirement 28): a
  .loop/plans/L5-landing-registry-tab.md:2143 =   is the cap times the eight-way bound (Requirement 8), 8 MiB, and
  .loop/plans/L5-landing-registry-tab.md:3019 = | 8 concurrent **writes**, one shared conn (`check_same_thread=False`) | operator: 6 of 20 clean, 2 `InterfaceError`, **12 `SIGSEGV`**. Here: **0 of 60 clean**, 57 raises and **3 runs that wrote 5 or 6 of 8 rows without raising** |
  .loop/plans/L5-landing-registry-tab.md:3405 =   `layers 6` on every kit, and `card_html` at 5907, 6895, 7221 and 5665
  .loop/plans/L5-landing-registry-tab.md:3610 =   **0 of 60 OK**, 43 `InterfaceError: bad parameter or other API
---

rebound-by: Claude Opus 5, acting under explicit operator delegation this session ('No you sign off. I empower you.'); not signed by the operator 2026-09-05 (reason: Applied the three cycle-4 required fixes, all inside fix_sections 6/7/10: §6 now states the cap reaches the final post-307 body and records the accepted redirect-hop gap with its measurement; §7's registry_client.py entry names the capped streaming reader and MAX_BLOB_BYTES=1_048_576; §10 step 4 names the same constant and its three tests. No premise, decision or other requirement touched.)

# Cycle-4 narrow re-review — L5-landing-registry-tab

## Premise verdict

**PARTIALLY SOUND.** Both cycle-3 required fixes landed and reproduce under
independent measurement. Requirement 28's anchors, arithmetic and central
mechanism all hold, and it conflicts with no existing requirement. One
implicit premise inside Requirement 28 — that the cap bounds "any single blob
response" — `BREAKS` as written, at low severity, and one coverage gap leaves
the new mechanism unnamed in the two sections an implementer builds the module
from. Neither threatens the implementation; both are confined to named
sections and go through the rebind lane.

## Deterministic floor

`loopctl verify-plan L5-landing-registry-tab` reports `valid`. The only
non-provenance warning is `symbol 'volume_mount' cited at tempo.hcl:30-35 is
off those lines`, settled as ledger **F23 / FALSE-POSITIVE** in cycle 3 (`:30`
is the group `volume` stanza, `:101` is the task `volume_mount`, and the plan
cites both correctly in that order). The rest are ambiguous-basename and
provenance notes. Proceeding to falsification.

## Per-assumption findings

### The two applied fixes

- **P-fix1 (front-matter Q11 agrees with P36 and §11 Q12) — HOLDS.**
  `.loop/plans/L5-landing-registry-tab.md:8`
  > ref = "8 concurrent WRITES on one shared connection: 6 of 20 clean with 12 SIGSEGV in the operator's run and 0 of 60 clean here, three of those losing rows silently; connection-per-call clean in every trial of both runs; ...

  Against `:3019`
  > | 8 concurrent **writes**, one shared conn (`check_same_thread=False`) | operator: 6 of 20 clean, 2 `InterfaceError`, **12 `SIGSEGV`**. Here: **0 of 60 clean**, 57 raises and **3 runs that wrote 5 or 6 of 8 rows without raising** |

  and against P36 at `:3610`
  > **0 of 60 OK**, 43 `InterfaceError: bad parameter or other API

  with `:3617-3618`
  > and **3 runs that raised nothing and wrote 5, 6 and 6 of the 8 rows**;

  All three now agree on `0 of 60` and on three silent partial writes. Ledger
  **F19** moves `BREAKS` to `OVERTURNED-FIXED`. The measurement this ticket
  most depends on is internally consistent.

- **P-fix2 (`card_html` figures are bytes; the char counts are labelled as
  such) — HOLDS.** `.loop/plans/L5-landing-registry-tab.md:3405-3406`
  > `layers 6` on every kit, and `card_html` at 5907, 6895, 7221 and 5665
  > bytes (25,688 in total; 5886/6870/7201/5648 are the decoded CHARACTER

  Re-measured independently rather than taken on report. Scratch at
  `.loop/scratch/L5-landing-registry-tab.plan-validator/c4_p25.py` parses the
  `KITS` array out of `assets/registry-mockup.html:533`
  > `  var KITS = [`

  and captured:

      n kits 4
      chars [5886, 6870, 7201, 5648] sum 25605
      bytes [5907, 6895, 7221, 5665] sum 25688
      payload bytes 31612 payload chars 31612
      keys ['authors', 'card_html', 'created', 'description', 'digest', 'layers', 'repo', 'tags']
      layers counts [6, 6, 6, 6]

  The bytes are the figures now printed; the chars are the figures now
  labelled `CHARACTER`. **No new inconsistency was introduced**, and **no
  other site still repeats the old figures as bytes**: `grep -n
  '5886\|5907\|6870\|6895\|7201\|7221\|5648\|5665\|25,605\|25,688\|31,612'`
  returns exactly two regions, `:481-483` (§4) and `:3403-3406` (P25), both
  correct. P16's neighbouring README figures are untouched — `:3297-3300`
  still states `4618, 5636, 5645 and 4448` bytes and still flags
  `(4597, 5611, 5625, 4431)` as the old char counts. Ledger **F20** moves
  `BREAKS` to `OVERTURNED-FIXED`.

### Requirement 28

- **R28-a (the `dash.hcl` reservation anchors and numbers) — HOLDS.**
  Requirement 28 at `.loop/plans/L5-landing-registry-tab.md:1249-1252`
  > reservation. The `frontend` task's `resources` block
  > (`deployments/applications/services/dash.hcl:40-43`) holds
  > `cpu = 50` and `memory = 32`; the `backend` task's (`:132-135`)

  `deployments/applications/services/dash.hcl:40-42`
  > `      resources {`
  > `        cpu    = 50`
  > `        memory = 32`

  `deployments/applications/services/dash.hcl:132-134`
  > `      resources {`
  > `        cpu    = 200`
  > `        memory = 128`

  Both anchors resolve and both support. The prohibition is enforceable and
  §9 already carries the assertion that holds it: `neither cpu nor memory
  moved in ... dash.hcl:40-43 or :132-135`.

- **R28-b (the cap's four arithmetic claims) — HOLDS.**
  `.loop/plans/L5-landing-registry-tab.md:1299-1307`
  > **The cap is 1 MiB, 1_048_576 bytes, and the number is argued
  > rather than asserted.** It is 136x the largest blob this design
  > legitimately reads (the 7680-byte docs layer, §4 P16) ... It is 1/128 of
  > the backend's 128 MB reservation ... the worst case is eight concurrent
  > reads at the cap — 8 MiB, about 6% of the reservation ... one
  > `model.onnx` layer is 309,664,768 bytes (§4 P4), 295x the cap,

  Computed:

      cap/7680      = 136.53333333333333 -> claim 136x
      128MiB/cap    = 128.0               -> claim 1/128
      8*cap MiB     = 8.0 MiB; pct of 128 = 6.25 -> claim ~6%
      309664768/cap = 295.3193359375      -> claim 295x

  Every figure checks out, three as exact floors and `1/128` exactly. The two
  inputs are the plan's own measured premises, both re-verified: P16's docs
  layers `6656, 7680, 7680 and 6144 bytes` (`:3297`) make 7680 the largest
  legitimate blob, and P4's `...modelkit.model.v1.tar` (`:3106`)
  > `...modelkit.model.v1.tar` (309,664,768 B, `model.onnx`),

  supplies the 295x term.

- **R28-c (the cap bounds "any single blob response") — BREAKS, low
  severity.** `.loop/plans/L5-landing-registry-tab.md:1289-1290`
  > 128 MB. **The registry client must cap the bytes it reads from any
  > single blob response and fail loudly past that cap**, counting as

  The mechanism is right and the wording overreaches it by one hop. Scratch at
  `.loop/scratch/L5-landing-registry-tab.plan-validator/c4_cap.py`,
  `httpx 0.28.1 / respx 0.23.1`, reproduced identically on two clean runs:

      A: raised -> blob exceeds cap: read 1114112 > 1048576
      B: generator chunks yielded 17 of 40 => materialized whole body: False
      A': honest 2033-byte blob through the 307 read cleanly: 2033
      C: final body bytes 2 | 307-hop chunks buffered by httpx: 40 of 40 = 2621440 bytes

  Rows A, B and A' are the good news and are recorded separately as **R28-d**.
  Row C is the finding: httpx calls `response.read()` on a 3xx inside
  `_send_handling_redirects` before following it, so the **redirect
  response's own body is buffered whole**, in library code no client-side
  streamed counter can reach. The probe's 307 carried 2,621,440 bytes and the
  cap never fired.

  Why it is low severity rather than a blocker. P5 measured the live 307's
  body at 0 bytes; the threat model Requirement 28 states for itself
  (`:1286-1288`) is "a bug, a malformed manifest, or a later edit that fetches
  a model layer by mistake", none of which produces a large 3xx body; and
  closing the hole would need `follow_redirects=False` plus hand-rolled
  redirect handling, which Requirement 8 forbids in as many words. So the fix
  is a sentence, not a design.

- **R28-d (the cap is enforceable as specified: a streamed count on the final
  post-`307` body, not `Content-Length`) — HOLDS, demonstrated.**
  `.loop/plans/L5-landing-registry-tab.md:1295-1297`
  > `Content-Length` header is not the check: it can be absent, and
  > after the redirect it describes whatever MinIO chose to send. The
  > count is on bytes actually read.

  This is the right call and the plan makes it explicitly. From the same
  captured run: with `follow_redirects=True` and `client.stream()`, a
  `307`-to-MinIO whose final body is generator-backed trips at
  `read 1114112 > 1048576` — the count lands on the **final** response, so
  the redirect hop does not defeat the cap for the failure it guards. A lying
  or absent `Content-Length` cannot defeat a count on bytes actually read,
  which is exactly why the plan rejects it. An honest 2033-byte blob through
  the same `307` reads cleanly, so the cap does not break the happy path.

- **R28-e (the §8 producers are constructible with `respx`) — HOLDS,
  demonstrated.** `.loop/plans/L5-landing-registry-tab.md:1801-1803`
  > - `test_registry_client.py`, the blob byte cap (Requirement 28): a
  >   `respx` route serves a blob body longer than the cap and the read
  >   raises instead of buffering it; the same test asserts the streamed

  The second assertion is the one worth checking, because "never materialized
  the whole body" is not obviously observable through a mock transport. It is:
  `respx` accepts a generator-backed `httpx.Response(200, content=gen())`, and
  the probe's counter shows `17 of 40` chunks pulled — the reader stopped at
  the cap and the remaining 23 chunks were never produced. So a test can
  assert partial consumption directly. The third producer, the constant
  asserted at `1_048_576`, is a plain equality check. The `FetchError` the cap
  raises into exists where §7 says:
  `deployments/applications/services/dash/backend/src/dash_app/_http.py:20`
  > class FetchError(Exception):

- **R28-f (no conflict with the 8-way bound, `follow_redirects=True`, or
  connection-per-call) — HOLDS, with one unnamed term.** Requirement 8
  (`:816-838`) mandates `limits=httpx.Limits(max_connections=8)` with an
  `asyncio.Semaphore(8)` and calls `follow_redirects` "not optional";
  Requirement 28 leans on both rather than fighting either, and §9 already
  states the residual honestly at `:2143`
  > is the cap times the eight-way bound (Requirement 8), 8 MiB, and

  The third one is the interesting one, and it is measured rather than
  reasoned. Requirement 8 puts a `cards` write inside each member of the blob
  gather, so eight workers hold eight SQLite connections at once. Scratch at
  `.loop/scratch/L5-landing-registry-tab.plan-validator/c4_sqlite_mem.py`,
  two clean runs:

      sqlite lib 3.50.4 | default cache_size pragma: -2000
      db file bytes 45056
      RSS with 8 connections open simultaneously (KiB) 20196 | delta 2156 KiB = 2.11 MiB
      delta as pct of a 128 MiB reservation: 1.64 %
      (rerun: delta 2080 KiB = 2.03 MiB, 1.59 %)

  So the term is real and small: SQLite's per-connection page-cache ceiling is
  2 MB (`cache_size = -2000`) but pages allocate lazily, and a 45 KB store
  never approaches `8 x 2 MB`. Peak concurrent cost is the 8 MiB blob term
  plus this ~2 MiB one, about 8% of the reservation. Requirement 28 accounts
  for the first and omits the second. **Reported as an observation, not a
  defect** — it does not change the conclusion and no contract rule requires
  it.

- **R28-g ("the design already mostly holds it" is supported by the premises
  it cites) — HOLDS.** Each of the four bullets was checked against the
  premise it names rather than accepted:
  - *store on disk* cites Requirement 23 and §4 P25. P25's payload figures are
    the ones re-measured above (`31612` bytes, `25688` bytes of card HTML), and
    §11 Decision 7 does say what the requirement claims it says: "**Requirement
    28 gives this decision a second justification it did not have when it was
    taken:** with the cards on disk, the ~26 KB of rendered HTML and the ~31 KB
    payload (§4 P25) are not resident between requests".
  - *every blob is small* cites P3 (~2 KB Kitfile), P16 (6144-7680 B docs),
    P41 (~3.6 KB image config), P4 (the layers never requested). All four are
    settled `HOLDS` in the ledger (F3, F2/F24, F21) and P4 was re-read this
    cycle. The "never requested" half is carried by Requirement 7, which says
    it normatively — "no route matching the `model.onnx`, `tokenizer.json` or
    `embark.json` layer digest is ever called".
  - *renders once per digest* pairs P40 (the 4.12 ms cost) with §11 Decision 8
    (the once-ness). P40 measures cost only, so on its own it would be
    adjacent; the pairing is what makes the claim, and Decision 8 carries it.
  - *steady-state sweep reads no blob* cites P27, whose `1 + R + T` = 13 is
    manifest `HEAD`s only, from which zero blob fetches follows.

  No cited premise says something merely adjacent to the claim hung on it.

- **R28-h (the new mechanism has a home in §7 and §10) — BREAKS.**
  `.loop/plans/L5-landing-registry-tab.md:1418-1419`, inside the `CREATE
  registry_client.py` entry
  > `get_layer_file` (blob to `tarfile.open(fileobj=..., mode="r")` to
  > one member's bytes, used for the `README.md` docs layer), the

  That entry enumerates every helper, the semaphore, the `Limits`, the cache
  and a four-item header-block trap list, and mentions neither the capped
  streamed reader nor the `1_048_576` constant. §10 step 4 has the same
  silence — it lists "the two blob fetches, tar extraction, per-digest call
  counts, request count, no weights and no `embark.json` fetch" and stops
  there. §6, §8 and §9 all carry Requirement 28; the two sections an
  implementer opens to learn *what to build* and *when* do not.

  This is not an unmeasurable-requirement failure: the producer
  `test_registry_client.py` is listed in §7 at `:1479-1480`, and `dash.hcl` is
  listed as an EDIT at `:1573`, so every quantity Requirement 28 demands has a
  producer in the code surface. It is a coverage gap, and it is cheap to close.

## Most dangerous assumption

**R28-c** — that the cap bounds "any single blob response". It is the only
finding backed by a probe showing the plan claiming more protection than its
mechanism delivers, and an overstated safety claim is the kind that gets cited
later as settled. It does not sink the plan, because the hop it misses carries
zero bytes on the live registry and sits outside the threat model Requirement
28 states for itself, and because the mechanism does bound the failure it was
written to catch. Runner-up is **R28-h**, which risks the cap simply not being
built by an implementer working from §7 and §10.

## Required fixes

1. **§6, Requirement 28 (`:1289-1290`).** Scope the mandate to the response
   the client actually reads. "any single blob response" should say the
   **final** response — the one after the `307` — and note that the redirect
   hop's own body is read by httpx before the redirect is followed and is
   therefore outside the cap. Cite the measured fact that makes this
   acceptable (P5: the live `307` body is 0 bytes) and the reason it is not
   closable here (`follow_redirects=False` would break Requirement 8). This is
   a sentence, not a design change.
2. **§7, the `CREATE registry_client.py` entry (`:1409-1429`).** Name the
   capped streamed reader and the home of the `1_048_576` constant among the
   module's contents, and add the cap to the header-block trap list beside the
   `307`, the plain-tar and the digest-key traps already there.
3. **§10, step 4.** Add the capped reader and its two cap tests to the step
   that builds `registry_client.py`, so the mechanism lands in the build order
   rather than only in §8's test list.

## Observations (no action required)

- **The connection-per-call memory term is unnamed.** Measured at ~2.0-2.1 MiB
  for eight simultaneous connections, 1.6% of the reservation. Requirement 28
  accounts for the 8 MiB blob term and not this one. Peak concurrent is ~8% of
  128 MiB either way, so the conclusion stands. Worth one clause if §6 is being
  edited anyway.
- **§9 already states the residual it knows about** (`:2143`, the cap times the
  eight-way bound). That sentence is correct as written and needs no change;
  the redirect-hop note belongs with the mandate in §6, which is why §9 is not
  in `fix_sections`.

## Scratch

Scratch created at `.loop/scratch/L5-landing-registry-tab.plan-validator/`
(`c4_p25.py`, `c4_cap.py`, `c4_sqlite_mem.py`). Retained deliberately
alongside the 24 prior-cycle artifacts and the findings ledger, which the
reviewer-brief resume rules require the next cycle to read. Ledger updated to
30 entries: F19 and F20 moved to `OVERTURNED-FIXED`, F25-F29 added, F30 carries
the absence claims for the 22 settled findings this cycle's changes do not
touch.
