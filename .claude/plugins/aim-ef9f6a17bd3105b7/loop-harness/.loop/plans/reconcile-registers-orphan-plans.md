# reconcile-registers-orphan-plans

**Status: BACKLOG.** Planned and registered now, implemented later. Frame
every estimate and dependency accordingly; nothing here is picked up until
the operator advances it out of `ready`.

## 1. Title

Extend reconcile so the ledger is a re-derivable index of the plans on
disk: a plan file with no ledger entry is auto-registered, a non-terminal
entry whose plan vanished is flagged, and a `loopctl drop` command retires
an unwanted auto-registered draft as a reversible state that reconcile never
resurrects, closing the seam where tickets fall between "file written" and
"registered" and giving the auto-register pass a removal counterpart.

## 2. Size / Effort

**M.** The core is one new reconcile pass over `plans_dir` plus a
plans-dir resolver, wired into two call sites (`loopctl reconcile` and the
SessionStart hook) and covered by real-temp-repo tests. Folding in drop adds
one `loopctl drop` command, one small ledger representation change (a field
or an enum member per the §11 fork), a reverse (un-drop) path, and a
reconcile suppression so a dropped ticket never warns or resurrects. What
pushes it past S: the plans-dir resolution has a genuine cross-repo hazard
(the default `plans_dir` is a shared home directory), the reverse-orphan
direction needs noise-scoping against the real ledger, the drop
representation collides with the closed `Stage` enum (a load-bearing fork,
§11), and there are prompt/manifesto/decision-record edits to keep the
invariant honest.

## 3. Triggered by

Operator report, settled in conversation: creating a ticket writes a plan
file but registering it in the ledger is a separate, easy-to-miss step, so
orphan plans accumulate invisibly until someone greps the filesystem. It
happened this session (`init-loop-scaffold-skill` had a plan but sat
unregistered; eval-less plans had to be found by hand), and it is visible in
the repo right now: three plan files under `.loop/plans/` have no ledger
entry (see §4).

Folding in drop (operator decision, this session): auto-register creates
draft entries the operator did not hand-author, and today there is NO way to
remove or retire a registered ticket. Without a removal counterpart an
auto-registered draft can never be taken back, and worse, deleting its
ledger row would not help: the surviving plan file would just be
re-registered on the next reconcile pass. Auto-register and a durable
removal mechanism must therefore ship together. Drop is that counterpart.

## 4. Context

**How a ticket becomes registered today.** There is no registration at
plan-authoring time. `create-ticket`/`ticket-planner` write the plan file
and stop; the `ticket-planner` agent is explicitly barred from touching the
ledger (`agents/ticket-planner.md:80`). Registration happens only later,
inside the `implement-ticket` perceive step, which runs `loopctl register
<slug>` (`skills/implement-ticket/SKILL.md:38`). A plan nobody has begun
implementing therefore has no ledger row and is invisible to `loopctl
ledger` and the SessionStart briefing.

**Reconcile today is git-only.** `reconcile.reconcile` (`reconcile.py:52`)
iterates existing `ledger.entries` and corrects each against git history
(downgrade a `done`/`commit` entry with no matching commit, upgrade a slug a
commit carries). It never looks at `plans_dir`, so it can only correct
entries that already exist. `reconcile.main` (`reconcile.py:82`) loads the
ledger, reconciles, saves on change, prints corrections. It is invoked by
`loopctl reconcile` (`cli.py:165`) and in the perceive step
(`skills/implement-ticket/SKILL.md:35`).

**SessionStart only prints.** `hooks._session_start` (`hooks.py:436`) loads
the ledger and prints one row per entry (`hooks.py:443-450`) plus HALT and
config state. It does NOT reconcile, so an orphan plan never surfaces at
session start.

**`plans_dir` is currently inert in the core.** `config.py` stores
`plans_dir` as a raw string documented "informational, used by the skill"
(`config.py:157`, default `~/.claude/plans` at `config.py:190`, parsed at
`config.py:257`). Nothing in `src/loop_harness/` resolves it, expands `~`,
or enumerates its files. This repo overrides it to the repo-local
`.loop/plans` (`.loop/config.json`).

**Registration is already idempotent and file-keyed-friendly.**
`ctl.register` (`ctl.py:38`) is a no-op when the slug is already present, so
running a registration twice never duplicates. `loopctl register <slug>`
already exists as the explicit path (`cli.py:132`, `cli.py:169`).

**There is no way to remove or retire a ticket today.** The `loopctl`
command table exposes `register`, `advance`, `block`, `done`, `finish`,
`reconcile`, and the kill switch (`cli.py:127-155`); the blessed transitions
in `ctl.py` are `register` (`ctl.py:38`), `advance` (`ctl.py:48`), `block`
(`ctl.py:96`), and `done` (`ctl.py:109`). None of them removes a ticket, and
`reconcile` never deletes an entry. A registered slug is permanent unless
someone hand-edits `ledger.json`, which the state-guard hook blocks. Drop is
the missing verb.

**The `Stage` enum is closed and the entry shape is narrow.** `Stage`
(`ledger.py:22-32`) has exactly eight members: the seven-stage forward path
plus `blocked`. `done` (`ledger.py:31`) is the one terminal stage in the
forward `_ORDER` (`lifecycle.py:22-30`); `blocked` (`ledger.py:32`) is NOT
in `_ORDER` — it is reachable from anywhere and returns only to `ready`
(`lifecycle.py:71-76`). `TicketEntry` (`ledger.py:55`) serializes through
`to_dict`/`from_dict` (`ledger.py:67`, `ledger.py:83`), the latter tolerant
of absent fields, so adding an orthogonal field is backward-compatible with
existing ledgers. This is the surface the drop-representation fork (§11) sits
on: a new field on the entry versus a new member of the enum.

**The bug, concretely, in this repo right now:**

- Plan files on disk (`.loop/plans/*.md`): `commit-gate-false-positive-on-
  strings`, `commit-gate-git-hook-backstop`, `commit-gate-targets-the-
  committed-repo`, `fingerprint-binds-loop-config`, `init-loop-scaffold-
  skill`, `reflection-derives-mechanical-facts`.
- Forward orphans (plan file, NO ledger entry): `commit-gate-git-hook-
  backstop`, `fingerprint-binds-loop-config`, `reflection-derives-
  mechanical-facts`. These three are exactly the invisible tickets.
- Reverse orphans (ledger entry, NO plan file): roughly ten entries, ALL at
  stage `done` (`reflection`, `parallel-review-passes`, `stamp-fingerprint-
  ignore-list`, and so on). Their plans were relocated or removed after
  completion. This is the load-bearing fact for the reverse direction: a
  naive "warn on every entry whose plan is missing" would emit ten
  session-start warnings of pure noise. Reverse-orphan warning must be
  scoped to non-terminal stages (and, once drop lands, must also skip
  dropped entries — see R5).

## 5. Non-goals / out of scope

- **No `loopctl new` / atomic creation command.** A ticket stays a plan
  file plus a ledger entry; creation is not collapsed into one command, and
  free-writing plan files stays legal (settled decision).
- **No PostToolUse (or any write-time) hook that registers on the plan-file
  write.** Explicitly rejected: a one-shot that, on failure or fail-open,
  orphans the plan forever with nothing to retry. Enforcement is RECONCILE.
- **No eval-forcing hook.** An unregistered or eval-less ticket surfaces as
  a visible ledger row every session, and the existing `require_eval` gate
  (`lifecycle.py:86`) already blocks it from `implementing`. Hooks cannot
  compel a forward action anyway (allow/block/inject only).
- **Drop is NOT deletion of the ledger entry, and reconcile still never
  deletes any entry.** Drop retires a ticket by marking it dropped, leaving
  the row in place. Keeping the row is exactly what stops the auto-register
  pass from resurrecting a dropped ticket from its surviving plan file. A
  command that removes rows, purges the ledger, or garbage-collects plan
  files is out of scope.
- **No full reverse-orphan handling.** This ticket WARNS on a non-terminal,
  non-dropped entry with a missing plan and never deletes the entry;
  deciding what else to do (rename detection, operator prompt) is a
  follow-up (Q1).
- **No new stage for auto-registered orphans (reuse `ready`).** Orphans
  register at the existing `ready` default; the closed enum stays closed on
  the auto-register path. Whether drop itself needs a stage is a live fork,
  not a settled non-goal — see §11.

## 6. Requirements & restrictions

R1. **Invariant to establish: plan file on disk ⟺ ledger entry referencing
    it (by slug).** Reconcile is the guarantor. The ledger becomes a
    re-derivable index of `plans_dir`, not a precious artifact.

R2. **Auto-register forward orphans at an existing early stage.** A plan
    file whose slug is absent from the ledger is registered via the existing
    `TicketEntry(slug=...)` default stage `ready` (`ledger.py:60`). Reuse
    `ready`; do NOT add a stage. Recommended: register through the existing
    `ctl.register` path (`ctl.py:38`) or its exact equivalent, so the no-op-
    on-present idempotency (`ctl.py:41`) is inherited.

R3. **Register off the durable file, never a creation event.** The trigger
    is "a plan file exists and its slug is not in the ledger", making
    recovery automatic on the next reconcile and `loopctl register <slug>`
    always available after a failed registration. This satisfies the
    operator's hard constraint: a plan that failed to register can ALWAYS be
    registered later.

R4. **Never resurrect an existing entry, whatever its state.** The
    auto-register condition is keyed on slug ABSENCE from the ledger. Any
    slug already present — including a `dropped`, `blocked`, or `done` entry
    — is left untouched by the plans pass, so keeping an entry is how a drop
    survives reconcile. A dropped entry with a surviving plan file is NOT
    re-registered; that is the whole reason drop retires rather than deletes.

R5. **Reverse orphans are FLAGGED, never auto-deleted, and only when
    non-terminal and not dropped.** An entry whose plan file is missing AND
    whose stage is not terminal (`done`) AND which is not dropped yields a
    WARNING; the entry is not modified. A `done` entry, or a dropped entry,
    with a missing plan is silent (its plan is legitimately archived or the
    ticket was intentionally retired). Grounded in §4: ten of this repo's
    entries are done-with-no-plan and must not warn; a dropped ticket whose
    plan the operator also removed must be equally silent.

R6. **Resolve `plans_dir` safely and repo-locally.** Expand `~` and, when
    relative, resolve against the repo root. Auto-registration must consider
    ONLY plan files located under the repo tree. A `plans_dir` that resolves
    outside the repo (the shared-home default `~/.claude/plans`) must NOT
    pull other repos' plans into this ledger. See Q5. An absent or empty
    `plans_dir` is not an error (no plans, no orphans).

R7. **Ordering: plans pass before the git pass.** Register orphans first,
    then run the existing git reconcile, so an orphan whose work is already
    committed is registered and then upgraded to `done` in the same run
    (self-healing in one pass).

R8. **Fire at both enforcement points.** `loopctl reconcile`
    (`reconcile.py:82` / `cli.py:165`) and the SessionStart hook
    (`hooks._session_start`, `hooks.py:436`; wired at `hooks/hooks.json:3`).
    SessionStart is where the invariant is enforced every session and where
    orphans become visible rows.

R9. **Kill the soft question: registration becomes a MANDATORY create-ticket
    step, with reconcile as the code-level backstop.** "Code must, prompts
    may": the skill instruction is the courtesy, reconcile is the guarantee.
    Insert the mandatory step in `create-ticket` alongside the existing
    "always offer the eval" section (`skills/create-ticket/SKILL.md:102`),
    respecting the `ticket-planner` boundary (the planner returns a path;
    the driver registers, per `agents/ticket-planner.md:80`).

R10. **Honor the closed-state-machine grain (MANIFESTO I1; decisions R1/S1,
    `MANIFESTO.md:225-233`).** Reflection and selectable review both enforced
    at an existing point rather than growing `Stage`/`_ORDER`. This ticket
    does the same on the auto-register path: reconcile is an existing
    mechanism extended, not a new stage. Drop's representation must be judged
    against this same grain — the §11 fork picks the shape that respects it.

R11. **Drop is a reversible retirement, not a deletion.** `loopctl drop
    <slug>` marks an existing entry dropped; the entry stays in the ledger.
    The mark is reversible: re-registering (un-dropping) a dropped slug
    returns it to an active ticket. Model the command on the existing blessed
    transitions in `ctl.py` (`register` `ctl.py:38`, `block` `ctl.py:96`,
    `done` `ctl.py:109`) and expose it in the `loopctl` table alongside them
    (`cli.py:127-155`). Recommended reverse path: `loopctl register <slug>`
    on a dropped entry clears the dropped mark (a "re-register" flip),
    preserving the existing no-op-on-present behavior for entries that are
    NOT dropped so the idempotency in R2/R3 is unchanged. The exact
    representation (a field versus a stage) is the §11 fork; whichever shape
    the operator picks, drop MUST be reversible and reconcile MUST treat a
    dropped entry as "registered, do not resurrect" (R4) and "not a
    reverse-orphan warning" (R5).

R12. **Strengthen MANIFESTO I11** ("git is ground truth; the ledger is
    corrected from it", `MANIFESTO.md:158-163`) and add a new invariant for
    the plan⟺entry relationship. Add a DECISIONS.md section recording the
    settled forks (auto-register not deletion, reconcile not a write-time
    hook, reuse `ready`, drop-as-reversible-retirement) AND the drop
    representation chosen from the §11 fork. See §8.

R13. **Repo rules.** Stdlib-only core (MANIFESTO value, `MANIFESTO.md:197`);
    numpy docstrings on every new object (`.claude/rules/python-docstrings.
    md`); a test per behavior with real temp repos, never mock git/FS
    (`.claude/rules/python-testing.md`); surgical scope, every changed line
    traces to this ticket (AGENTS.md §3). Address any pre-existing gate
    failure encountered rather than working around it
    (`.claude/rules/pre-existing-issues.md`).

## 7. Code surface

The drop-representation fork (§11) has two shapes. Anchors below are labeled
**(shape A: field)** or **(shape B: stage)** where they differ; the operator
settles the fork in DECISIONS.md before pickup, and only the chosen shape's
anchors apply. Everything unlabeled applies either way.

- `src/loop_harness/reconcile.py:52` — extend or precede `reconcile` with a
  plans pass: enumerate resolved-`plans_dir` `*.md` files, register each
  slug absent from the ledger at `ready`, collect a warning for each
  non-terminal, non-dropped entry whose plan file is missing. A registration
  and a warning do not fit the current `Correction` shape (it carries
  `before`/`after: Stage`, `reconcile.py:21-28`); add a small result type or
  extend the return so `main` can print both (implementation choice, keep it
  minimal).
- `src/loop_harness/reconcile.py:68` — the reverse-orphan / warning
  condition already excludes terminal (`_DONE_STAGES`) and `blocked`
  entries; extend the exclusion so a dropped entry is also skipped (shape A:
  test `entry.dropped`; shape B: add `Stage.DROPPED` to the terminal-skip
  set). This is the R5 suppression.
- `src/loop_harness/reconcile.py:82` — `main`: call the plans pass before
  the git pass (R7), save the ledger when it changed, print registrations
  and warnings alongside git corrections.
- `src/loop_harness/reconcile.py` (new helper) — resolve `plans_dir`:
  expanduser, repo-relative when relative, and a repo-containment check for
  R6/Q5. May live here or beside `plans_dir` in `config.py`; keep it one
  function, single-sourced.
- `src/loop_harness/ledger.py:55` **(shape A: field)** — add an orthogonal
  field to `TicketEntry` (e.g. `dropped: bool = False`, or `abandoned_at:
  str | None = None`), independent of `stage`. Serialize it in `to_dict`
  (`ledger.py:67`) and read it, tolerant of absence, in `from_dict`
  (`ledger.py:83`) so existing ledgers load unchanged. No enum change; the
  closed `Stage` stays closed.
- `src/loop_harness/ledger.py:22` **(shape B: stage)** — add a terminal
  `DROPPED = "dropped"` member to `Stage`, symmetric with `done`. This grows
  the closed enum; see the §11 fork and R10 before choosing it.
- `src/loop_harness/lifecycle.py:71` **(shape B: stage only)** — add a
  `DROPPED` branch symmetric to the `BLOCKED` handling: reachable from
  anywhere, and reversible back to `ready` (the un-drop / re-register flip).
  `DROPPED` stays OUT of `_ORDER` (`lifecycle.py:22-30`), like `blocked`.
  **(shape A needs no lifecycle change** — the stage is untouched by drop.)
- `src/loop_harness/ctl.py:38` — add a `drop(repo, slug)` transition modeled
  on `block`/`done`: load the ledger, mark the existing entry dropped (shape
  A: set the field; shape B: `validate_transition(entry.stage,
  Stage.DROPPED)` then set the stage), save. Raise a clear error when the
  slug is absent (nothing to drop). Extend `register` (`ctl.py:38`) so that
  when the slug is present AND dropped it clears the dropped mark
  (re-register / un-drop) instead of the plain no-op; a present, non-dropped
  slug keeps the exact existing no-op (`ctl.py:41`) so R2/R3 idempotency is
  unchanged.
- `src/loop_harness/cli.py:143` — add a `drop` subcommand to the `loopctl`
  argument table (next to `done`, `cli.py:143-146`) taking a `slug`, and a
  dispatch arm (next to `cli.py:178`) calling `ctl.drop(repo, args.slug)`.
  Update the module docstring's transition list (`cli.py:1-9`) to name
  `drop`.
- `src/loop_harness/hooks.py:436` — `_session_start`: run the plans
  reconcile (and, per R7 ordering, it composes with the git reconcile) so
  orphans register and surface as rows. Stays best-effort/fail-open (the
  body is already wrapped, `hooks.py:466`). Note it now writes `ledger.json`
  via `save_ledger`; that is harness-written state and acceptable (Q6).
- `src/loop_harness/config.py:190` — `plans_dir` default and its docstring
  (`config.py:157`) may need a one-line update if resolution semantics are
  documented here; no schema change required.
- `skills/create-ticket/SKILL.md:102` — add the mandatory "register the
  plan" step next to the eval offer (R9).
- `MANIFESTO.md:158` (strengthen I11) and `MANIFESTO.md:86` (add the new
  plan⟺entry invariant in §3) — keep each invariant's "Enforcer:" line
  pointing at real code.
- `DECISIONS.md` (new top-level section for this ticket) — record the
  settled forks AND the chosen drop representation (§11 A vs B).
- `tests/test_reconcile.py:1` — new reconcile-side tests (§8), using the
  `repo` fixture (`tests/conftest.py:17`).
- `tests/test_ctl.py:1` — new drop/un-drop transition tests (§8): the
  declared home for the `ctl.drop` and re-register-clears-dropped tests,
  mirroring the existing `ctl` transition coverage.
- `tests/test_hooks.py` — one test that SessionStart reconciles an orphan
  plan into the ledger (the wiring test for R8). This file is the declared
  home for the named SessionStart test.

## 8. Tests & validation gates

**Gates (this repo, from `.loop/config.json` and the `justfile`):**
`just check` runs `git add --intent-to-add -A . && uv run pytest` then `uvx
prek run --all-files` (ruff + mypy per `.pre-commit-config.yaml`). Evidence
via `uv run loopctl stamp`. Two review passes are enabled (`adversarial`
loop-reviewer, `architectural` loop-architect against `MANIFESTO.md`), and
`require_eval: true` is set, so this ticket cannot enter `implementing`
until its eval marker exists.

**Tests to add (all real temp git repos, never mock git or the FS):**

1. `tests/test_reconcile.py` — orphan plan file (write `<plans>/<slug>.md`,
   empty ledger) then reconcile: assert the slug is registered at `ready`.
2. `tests/test_reconcile.py` — pre-existing entry is never resurrected or
   duplicated: an entry already present (test both a non-terminal stage and
   a `blocked` entry) with its plan file present, reconcile leaves the stage
   and the entry set unchanged.
3. `tests/test_reconcile.py` — reverse orphan, non-terminal: entry at
   `ready`/`implementing` with no plan file yields a warning and the entry
   is NOT deleted.
4. `tests/test_reconcile.py` — reverse orphan, terminal is silent: a `done`
   entry with no plan file yields NO warning (the §4 noise case).
5. `tests/test_reconcile.py` — idempotency: two consecutive reconcile runs;
   the second registers nothing new and duplicates nothing.
6. `tests/test_reconcile.py` — recovery + explicit path: after a plans pass
   that (simulated) did not persist, a second reconcile registers the
   orphan, and `ctl.register(repo, slug)` on the same slug is a clean no-op
   (`ctl.py:41`), proving the explicit `register` path works after a failure.
7. `tests/test_reconcile.py` — plans-dir resolution and containment: a
   repo-local relative `plans_dir` is enumerated; a `plans_dir` resolving
   OUTSIDE the repo yields NO auto-registration (R6/Q5); an absent
   `plans_dir` is a clean no-op.
8. `tests/test_reconcile.py` — ordering/self-heal: an orphan plan whose
   slug-anchored commit already exists lands at `done` after one reconcile
   (plans pass registers, git pass upgrades; R7).
9. `tests/test_reconcile.py` — **drop survives reconcile (anti-
   resurrection):** register a slug, `ctl.drop` it, keep its plan file on
   disk, then reconcile: assert the entry is still present, still dropped,
   its stage unchanged, and it was NOT re-registered or re-activated. This
   is the load-bearing R4 test that justifies retire-not-delete.
10. `tests/test_reconcile.py` — **dropped entry with a missing plan is
    silent:** a dropped entry whose plan file is absent yields NO reverse-
    orphan warning (R5), symmetric with the `done` case in test 4.
11. `tests/test_ctl.py` — **drop marks an existing ticket dropped:**
    `ctl.drop(repo, slug)` on a registered entry marks it dropped (shape A:
    field set; shape B: stage is `dropped`) and dropping an absent slug
    raises a clear error.
12. `tests/test_ctl.py` — **drop is reversible (un-drop round-trip):** drop
    a ticket, then re-register it (`ctl.register` on the dropped slug clears
    the dropped mark), and assert it is active again. A drop→undrop→state
    round-trip leaves the ticket registered and not dropped; under shape A,
    assert the pre-drop stage is preserved across the round-trip.
13. `tests/test_ctl.py` — **re-register does not disturb a non-dropped
    entry:** `ctl.register` on a present, non-dropped slug is the exact
    existing no-op (`ctl.py:41`), proving R2/R3 idempotency is unchanged by
    the un-drop path.
14. `tests/test_hooks.py` — SessionStart on a repo with an orphan plan
    registers it (ledger gains the entry) and prints its row; fail-open
    preserved.

Every test above names a file listed in §7.

## 9. Risk assessment

- **Blast radius.** `reconcile` and `_session_start` are on every wake and
  every session start. A bug that over-registers would inject spurious
  `ready` rows; a bug in plans-dir resolution could, at worst, register
  another repo's plans (the shared-home hazard, R6/Q5) — the single most
  important thing to get right and to test (test 7). Drop adds a new write
  path (`ctl.drop`) but it is operator-invoked, not on the wake path, so its
  blast radius is small.
- **Anti-resurrection is the load-bearing property.** If drop deleted the
  ledger row instead of marking it, the surviving plan file would re-register
  on the next reconcile and the drop would silently undo itself. Retire-not-
  delete (R4, R11) is what makes drop stick; test 9 pins it. This is also why
  the enum-vs-field fork (§11) must land reconcile-side suppression whichever
  shape wins.
- **Reversibility.** High for the code (an additive reconcile pass plus one
  transition, revert cleanly). Drop closes the "auto-registered draft cannot
  be removed" gap that the prior revision of this ticket left open: an
  unwanted `ready` row is now `loopctl drop`-able and, being reversible, a
  wrongly-dropped ticket is a `loopctl register` flip away from returning.
- **Representation migration (the §11 fork).** Shape A adds a field to
  `TicketEntry`; `from_dict` must default it so pre-existing ledgers (this
  repo's live `ledger.json`) load unchanged — test the load of a
  field-absent entry. Shape B adds an enum member; every place that switches
  on `Stage` (reconcile terminal set, lifecycle branches, the `advance`
  choice list at `cli.py:137` and `ctl.py:148`) must account for it or a
  dropped ticket leaks into an unexpected code path. Shape B's surface is
  wider; that asymmetry feeds the §11 recommendation.
- **SessionStart now mutates `ledger.json`.** It will leave the tracked
  ledger dirty in the working tree until committed. Expected (the ledger is
  committed with its ticket), but note the interaction with the stop-check's
  dirty detection (`hooks.py:509`); the stop-check only blocks when a ticket
  is mid-flight, and a fresh `ready` registration is not, so no new wedge is
  expected. Confirm in review.
- **Likeliest failure modes.** (a) plans-dir resolution wrong for the
  home-default case, pulling cross-repo plans; (b) reverse-orphan warning not
  scoped to non-terminal/non-dropped, flooding the briefing with noise; (c)
  ordering reversed so a self-healed orphan is reported as `ready` then
  separately as `done`; (d) drop deleting the row (resurrection) or the
  un-drop path breaking register's idempotency. Tests 7, 4/10, 8, and 9/13
  pin these.

## 10. Subtickets

Ordered, dependency-aware. Each is a single loop iteration. Auto-register
(2) and drop (3) ship together — drop is the removal counterpart the
operator required alongside auto-register — but land as adjacent iterations
so each is independently reviewable.

1. **Plans-dir resolver + containment.** Add the one resolver function
   (expanduser, repo-relative, repo-containment) with tests (test 7). No
   behavior wired yet. Foundation for the rest.
2. **Reconcile plans pass (auto-register + reverse warn).** Extend
   `reconcile` with the plans pass and the result/warning shape; order it
   before the git pass in `main`; print both. Tests 1-8.
3. **Drop as reversible retirement.** Apply the §11-chosen representation
   (field or stage) in `ledger.py` (and `lifecycle.py` if shape B); add
   `ctl.drop` and the re-register-clears-dropped un-drop path in `ctl.py`;
   add the `loopctl drop` subcommand in `cli.py`; wire the reconcile
   suppression (`reconcile.py:68`) so a dropped entry never warns or
   resurrects. Tests 9-13. Depends on 2 (shares the reconcile suppression
   point and the anti-resurrection guarantee).
4. **Wire SessionStart.** Call the plans reconcile from `_session_start`,
   keeping fail-open. Test 14.
5. **Kill the soft question.** Make registration a mandatory create-ticket
   step (`skills/create-ticket/SKILL.md:102`), honoring the planner
   boundary. Prose only.
6. **Manifesto + decision record.** Strengthen I11, add the plan⟺entry
   invariant with its enforcer line, and add the DECISIONS.md section
   recording the settled forks and the chosen drop representation. Docs
   only; run the doc slop gates.

## 11. Open questions

Q1. **Does this ticket own both orphan directions, or just auto-register?**
    RECOMMEND: this ticket owns auto-register (plan→entry) AND emits a
    non-terminal, non-dropped WARNING for the reverse (entry→missing plan);
    full reverse-orphan handling (rename detection, operator prompt, any
    state change beyond drop) is a follow-up. Rationale: the warning is cheap
    and makes the reverse case visible without committing to a policy that
    could destroy ledger history over a transient missing file.

Q2. **Which early stage for auto-registered orphans?** RECOMMEND: reuse
    `ready` (the `TicketEntry` default, `ledger.py:60`). With
    `require_eval: true`, a `ready` orphan still cannot advance to
    `implementing` without an eval marker (`lifecycle.py:86`), so "registered
    but not yet implementable" is already expressible without a new stage.

Q3. **Store the plan path on the entry, or derive it from the slug?**
    RECOMMEND: derive (slug→path is deterministic via the resolved
    `plans_dir`). Storing a path duplicates state that can drift; add a field
    only if a concrete reader needs it. No `TicketEntry` schema change on
    this account.

Q4. **Drop mechanism — RESOLVED: folded into this ticket.** The prior
    revision deferred drop to a follow-up. The operator has decided
    (this session) to fold it in, because auto-register without a removal
    counterpart leaves an auto-registered draft un-removable, and deleting
    its row would not help (the surviving plan file re-registers). Drop is
    therefore in scope as a reversible retirement (R11, subticket 3). The
    remaining sub-decision — how "dropped" is represented — is Q7 below, the
    one fork the operator must settle before pickup.

Q5. **Shared-home `plans_dir` hazard.** The default `plans_dir` is
    `~/.claude/plans` (`config.py:190`), shared across every repo on the
    machine. Auto-registering from it would pull unrelated repos' plans into
    this ledger. RECOMMEND: auto-register ONLY plan files under the repo
    tree; a `plans_dir` resolving outside the repo yields no
    auto-registration (optionally a one-line "plans_dir is outside the repo;
    auto-register skipped" note). Grounded in the operator's own move of
    plans into the repo-local `.loop/plans` (commit `1690b2d`). The operator
    should confirm this is the intended containment rule.

Q6. **SessionStart writing `ledger.json`.** Reconcile at session start means
    `_session_start` now persists the ledger and leaves it dirty in the
    working tree. RECOMMEND: accept it (harness-written state, best-effort,
    already fail-open-wrapped). Confirm no adverse interaction with the
    stop-check dirty detection (`hooks.py:509`); none expected for a fresh
    `ready` row (not mid-flight).

Q7. **How is "dropped" represented — a field orthogonal to `stage`, or a new
    terminal `Stage` member? (LOAD-BEARING; route to DECISIONS.md.)** Drop
    must record a retired state without letting reconcile resurrect it, and
    it must be reversible. Two shapes:
    - **(A) A flag/field on `TicketEntry`** (e.g. `dropped: bool` or
      `abandoned_at`, `ledger.py:55`), orthogonal to `stage`. Reconcile asks
      "does an entry exist at all (dropped or not)" and skips resurrection
      (R4 already keys on absence); the field only gates the reverse-orphan
      warning (R5) and is the drop toggle. The closed `Stage` enum stays
      closed. Un-drop clears the field and the ticket resumes at the stage it
      held when dropped (the pre-drop lifecycle position is preserved).
    - **(B) A single terminal `dropped` stage** added to `Stage`
      (`ledger.py:22`), symmetric with the existing terminal `done`. Drop is
      a `→dropped` transition; un-drop is `dropped→ready` (BLOCKED-shaped, a
      reachable-anywhere reversible stage). This grows the enum and adds a
      lifecycle branch (`lifecycle.py:71`) plus terminal-set membership in
      several `Stage`-switching call sites.

    RECOMMEND (A), the orthogonal field. Reasons: (1) "dropped" is genuinely
    orthogonal to lifecycle position — you can drop a `ready`, `implementing`,
    or `blocked` ticket — and modeling an orthogonal fact as an enum member
    conflates two axes; (2) it keeps the closed `Stage` enum closed, honoring
    the MANIFESTO I1 / R1 / S1 grain of "enforce at an existing point, do not
    grow the state machine" (`MANIFESTO.md:225-233`), the same grain R10
    binds the auto-register path to; (3) it is the narrower diff — shape B
    touches every `Stage`-switching site (reconcile terminal set, lifecycle,
    the `advance` choice lists at `cli.py:137`/`ctl.py:148`), while shape A
    touches `TicketEntry` serialization and one reconcile condition; (4) it
    preserves the pre-drop stage, so un-drop restores the ticket exactly,
    whereas B would collapse the prior stage into `dropped` and lose it.
    COUNTERPOINT the operator should weigh: `done` already establishes a
    terminal-stage precedent, and `blocked` establishes the reachable-
    anywhere-reversible precedent, so B is not without grounding and reads as
    consistent with the existing enum; if the operator judges B materially
    simpler or more consistent in practice, it is a defensible choice. Either
    way, reconcile MUST treat a dropped entry as "registered, do not
    resurrect" (R4) and "no reverse-orphan warning" (R5), and drop MUST be
    reversible (R11). Record the chosen shape in the DECISIONS.md section this
    ticket adds (R12, subticket 6).
