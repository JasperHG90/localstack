# skills-prompt-decisions-via-qa

**Status: BACKLOG.** Planned and registered now, implemented later. Frame
every estimate and dependency accordingly; nothing here is picked up until
the operator advances it out of `ready`. This ticket also has a hard
sequencing dependency on `reconcile-registers-orphan-plans` (see §9, §10).

## 1. Title

Retrofit the repo's skills so operator DECISION POINTS use the
`AskUserQuestion` tool (structured, multiple-choice, recommended-option-first)
instead of easy-to-miss soft prose questions, so a decision that needs
operator input is unmistakable and cannot slip by silently. Free-form,
iterative co-authoring stays prose; only genuine discrete forks become Q&A.

## 2. Size / Effort

**M.** The edits are prose-only across two SKILL.md files (plus one small
convention doc and a `DECISIONS.md` entry), so there is no code and no unit
test surface. What keeps it off S: the change is judgment-heavy at exactly
the boundary the operator warned about (discrete fork to Q&A vs iterative
authoring stays prose), it must not conflict with a sibling ticket that
rewrites the same `create-ticket` region, and it needs an operator decision
on whether the convention gets a durable shared home (§11 Q2).

## 3. Triggered by

Operator directive, recorded as a project convention in Memex KV
`project:github.com/JasperHG90/loop-engineering-harness:skills:decision-prompts`:
"skills should surface operator decision points using the Claude Q&A feature
(the `AskUserQuestion` tool) rather than soft prose, so it is unmistakable
that a decision is required." This session hit the exact failure the
convention prevents: orphan plans and missing eval markers went unnoticed
because the skills asked about them in prose the operator missed.

## 4. Context

Today's skills surface operator decisions as prose "do you want to...?"
questions the reader can skim past. The load-bearing anchors:

**create-ticket asks about the eval handoff in prose.**
`skills/create-ticket/SKILL.md:101-115` ("After the ticket: always offer the
eval") instructs the skill to "offer to co-author its eval with the
`create-eval` skill" (`SKILL.md:103`). Whether to author it is called the
operator's decision (`SKILL.md:112`), but it is surfaced as prose, so the
operator can miss it. This is one of the two failures the operator named
(missing eval markers).

**create-eval's interview mixes discrete forks into iterative prose.**
`skills/create-eval/SKILL.md:80-107` ("Working with the operator") is a
five-step interview. Some steps are genuine discrete forks:
- Step 2 (`SKILL.md:87`): "Propose a count, with reasoning" then "The
  operator adjusts" - the scenario count is a discrete choice.
- Step 3 (`SKILL.md:89-96`): "Draft every column, then refine together" folds
  two discrete forks into prose: keep/cut a proposed row, and which Scorer
  (the three named kinds at `SKILL.md:48-54`: deterministic check / model +
  rubric / human + rubric) and which Threshold (the named bars at
  `SKILL.md:57-60`: 100% / N/5 / % of cases / baseline) each row carries.

But the same Step 3 is dominated by free-form authoring: writing each row's
Behavior, Input, and Expected prose is iterative collaboration
(`SKILL.md:90-96`, and the discipline "This is a collaboration, not a
generation" at `SKILL.md:111-113`). That drafting must stay prose.

**The eval offer also lives in the ticket-planner agent, which does not ask
the operator directly.** `agents/ticket-planner.md:66-75` tells the planner
to "hand back the eval step" in its FINAL MESSAGE to the caller; the planner
is a read-only subagent that returns a path (`ticket-planner.md:79`), not the
party in a conversation with the operator. The interactive Q&A therefore
belongs in the driver context (the `create-ticket` skill), not in the
subagent. This mirrors the boundary the sibling ticket already draws ("the
planner returns a path; the driver registers",
`.loop/plans/reconcile-registers-orphan-plans.md:169`).

**implement-ticket is mostly unattended and surfaces forks as block codes,
not prompts.** `skills/implement-ticket/SKILL.md` hands design forks to the
operator via `loopctl block <slug> <code>` (`SKILL.md:26-29`,
`SKILL.md:149-155`), an asynchronous ledger action, precisely because the
loop can run with no operator present (the "Unattended" mode,
`SKILL.md:44-48`, `SKILL.md:139-147`). `AskUserQuestion` needs a live
operator, so it does not fit this skill's autonomous path. See §5 and Q3.

**No AskUserQuestion usage exists in the repo yet** (grep across
`skills/`, `agents/`, `src/`: zero matches), so this ticket establishes the
pattern, which is why a shared convention home is worth deciding (Q2).

**No shared skill-authoring convention doc exists.** The convention lives
only in Memex KV (§3). The repo's per-project conventions otherwise live as
constraint files under `.claude/rules/` (e.g.
`.claude/rules/adversarial-reviews.md`, `.claude/rules/prek-code-quality.md`),
which is the natural durable home for this one (Q2).

## 5. Non-goals / out of scope

- **Not a Q&A-everywhere retrofit.** `AskUserQuestion` is for DISCRETE
  decisions with distinct options. It is NOT for open-ended authoring,
  free-text elicitation, or iterative co-authoring. The create-eval drafting
  of Behavior/Input/Expected prose (`skills/create-eval/SKILL.md:90-96`) stays
  prose. The failure mode to avoid is a gimmicky multiple-choice skill that
  forces free-form work into buttons. State the boundary in every edit.
- **Does NOT re-introduce or touch the create-ticket registration question.**
  The sibling ticket `reconcile-registers-orphan-plans` (R9,
  `.loop/plans/reconcile-registers-orphan-plans.md:163-169`, subticket 4 at
  `:307-309`) is KILLING that soft question by making registration a mandatory
  create-ticket step backstopped by reconcile. Registration must stay
  mandatory-and-silent, never a Q&A. This ticket only converts the decision
  points that REMAIN after that lands (the eval handoff, and create-eval's
  forks).
- **Does NOT convert implement-ticket's block-code forks to Q&A.** Those are
  asynchronous ledger actions for an often-unattended loop
  (`skills/implement-ticket/SKILL.md:149-155`); `AskUserQuestion` needs a live
  operator. Left as-is (Q3 surfaces the one supervised branch worth a second
  look).
- **No change to the `loopctl` CLI, the lifecycle, the ledger, or any hook.**
  This is a behavioral-layer (skill instruction) change only.
- **No change to what `AskUserQuestion` is or how it renders.** This ticket
  only instructs skills to call it; it is a Claude Code tool, not something
  this repo implements.

## 6. Requirements & restrictions

R1. **Discrete forks become `AskUserQuestion`, with the recommended option
    first.** For each converted point, the skill instruction must name the
    concrete options and put the recommended one first, so the operator sees
    a decision is required and sees the default. This is the KV convention
    (§3) applied.

R2. **Iterative/free-form authoring stays prose.** The create-eval drafting
    of each row's Behavior/Input/Expected text
    (`skills/create-eval/SKILL.md:90-96`) and its "collaboration, not
    generation" discipline (`SKILL.md:111-113`) are NOT converted. Every edit
    must state this boundary so a future editor does not over-apply it.

R3. **Scope the create-eval conversions to the named discrete forks only:**
    the scenario count (`skills/create-eval/SKILL.md:87`), keep/cut a proposed
    row, the Scorer choice (the three kinds, `SKILL.md:48-54`), and the
    Threshold choice (the named bars, `SKILL.md:57-60`). Each becomes an
    `AskUserQuestion` with the recommended option first (for a guardrail row,
    the recommended Scorer is deterministic and the recommended Threshold is
    100%, per the existing discipline at `SKILL.md:119-122`).

R4. **Convert the create-ticket eval handoff, not the registration.** The
    "co-author the eval now?" decision at
    `skills/create-ticket/SKILL.md:101-115` becomes an `AskUserQuestion`
    (options, recommended first, e.g. "Author the eval now / Defer / Skip").
    Preserve the existing rule that when `require_eval` is set the eval is
    REQUIRED, not offered (`SKILL.md:113-115`): in that case the skill states
    it is mandatory rather than asking. Do not add, move, or soften the
    mandatory registration step the sibling ticket introduces here.

R5. **The Q&A fires in the driver, not the planner subagent.** Keep
    `agents/ticket-planner.md:66-75` as a return-to-caller instruction; the
    interactive prompt lives in the `create-ticket` skill's driver context.
    If the planner's prose needs a one-line note that the driver asks via
    `AskUserQuestion`, keep it to that (see Q4).

R6. **Respect "the operator owns decisions."** The convention strengthens,
    not replaces, MANIFESTO's principle that the loop surfaces forks and the
    operator settles them (`MANIFESTO.md:216-218`, "No silent judgment calls"
    `MANIFESTO.md:27-29`). Making a fork unmissable is the point; the operator
    still decides.

R7. **Doc discipline for every edited `.md`.** Run the doc slop scan
    (`.claude/rules/slop-scan-for-docs.md`) on each changed markdown file:
    P0 patterns, document economy, sentence-level slop, 80-char prose wrap,
    American spelling. Any hallucinated skill name, tool name, or `path:line`
    is a P0 fail.

R8. **Surgical scope.** Every changed line traces to this ticket (AGENTS.md
    §3). Do not "improve" adjacent prose in the edited skills. Address any
    pre-existing gate failure encountered rather than working around it
    (`.claude/rules/pre-existing-issues.md`).

## 7. Code surface

No `src/` code changes. All edits are behavioral-layer markdown.

- `skills/create-eval/SKILL.md:87` (Step 2) - instruct the skill to ask the
  scenario count via `AskUserQuestion`, recommended count first (per the
  sizing guidance at `SKILL.md:60-62`), with a custom/other option. Keep the
  reasoning prose.
- `skills/create-eval/SKILL.md:89-96` (Step 3) - instruct the skill to ask
  keep/cut on a proposed row, the Scorer (three kinds, `SKILL.md:48-54`), and
  the Threshold (named bars, `SKILL.md:57-60`) via `AskUserQuestion`,
  recommended option first; explicitly keep the Behavior/Input/Expected
  drafting as prose collaboration (R2). Add a one-line boundary note.
- `skills/create-ticket/SKILL.md:101-115` ("After the ticket: always offer
  the eval") - convert the eval-handoff decision to `AskUserQuestion`
  (recommended: author now), preserving the `require_eval`-makes-it-mandatory
  branch (`SKILL.md:113-115`). Must be reconciled with the sibling ticket's
  edit to this same region (§9); do NOT touch its registration step.
- `agents/ticket-planner.md:66-75` - OPTIONAL one-line note that the driver
  asks via `AskUserQuestion` (gated on Q4); the planner still only returns a
  path.
- `.claude/rules/decision-prompts.md` (NEW, gated on Q2) - the shared
  convention doc: discrete forks use `AskUserQuestion` with the recommended
  option first; iterative authoring stays prose. This is the durable home so
  future skills inherit the convention.
- `DECISIONS.md` (new top-level section) - record the settled forks from §11
  (which points convert, iterative-stays-prose boundary, shared-doc decision,
  implement-ticket left as-is), so a future implementer treats an unanswered
  variant as `blocked`, not a judgment call.

## 8. Tests & validation gates

**Be honest about the surface: this is a prose-only skill-authoring change,
so there is no pytest surface and no unit test to add.**

- **pytest** (`git add --intent-to-add -A . && uv run pytest`, per
  `.loop/config.json` and the `justfile`): the only skill-touching test is
  `tests/test_manifest.py:33-54`, which checks that each skill dir has a
  `SKILL.md` and that create-ticket/create-eval exist. Editing SKILL.md
  CONTENT does not change file existence, so these keep passing and no new
  test is warranted. Do not invent a content-assertion test; the manifest
  test's contract is presence, not prose.
- **prek** (`uvx prek run --all-files`): the configured hooks
  (`.pre-commit-config.yaml`) are ruff-lint, ruff-format, and mypy, all scoped
  to Python (`types_or: [python, pyi]` / `types: [python]`). They do not run
  over `.md` files, so this change is a no-op for them; the gate must still be
  green (fix any pre-existing failure per R8).
- **Doc slop scan** (`.claude/rules/slop-scan-for-docs.md`): this is the real
  validation gate for this ticket. Run all three layers on every edited/new
  `.md` (`skills/create-eval/SKILL.md`, `skills/create-ticket/SKILL.md`, and
  `.claude/rules/decision-prompts.md` / `DECISIONS.md` if added). A
  hallucinated tool or skill name is a P0 fail.
- **Review passes** (enabled in `.loop/config.json`): `adversarial`
  (loop-reviewer) and `architectural` (loop-architect against `MANIFESTO.md`).
  Both must return a passing, tree-bound verdict. NOTE: the `documentation`
  review pass and the `loop-doc-reviewer` agent exist
  (`agents/loop-doc-reviewer.md`) but are NOT enabled in this repo's config,
  so they do not gate this change even though it edits documented behavior.
  Flagging in case the operator wants that pass enabled for this ticket (Q5).
- **`require_eval: true`** is set, so this ticket cannot advance into
  `implementing` until its own eval marker exists at
  `.loop/evals/skills-prompt-decisions-via-qa.md`. That eval is the primary
  acceptance layer here: its scenarios pin behaviors like "a discrete fork is
  asked via AskUserQuestion with the recommended option first" and the
  guardrail "free-form authoring is NOT converted to multiple-choice". Author
  it with `create-eval` before pickup (see the eval next-step below).

## 9. Risk assessment

- **Blast radius.** Small and prose-only: no code, no CLI, no lifecycle. The
  behavior change is in how two skills prompt. Worst case is a skill that
  prompts awkwardly, corrected in a follow-up edit, not a broken loop.
- **Reversibility.** High. Revert the markdown.
- **Likeliest failure modes.**
  1. **Over-application (the operator's explicit warning).** Converting
     free-form authoring into multiple-choice, producing a gimmicky
     Q&A-everywhere skill. Guarded by R2 and the §11 Q1 boundary; the eval
     guardrail row pins it.
  2. **Conflict with the sibling ticket.** `reconcile-registers-orphan-plans`
     rewrites `skills/create-ticket/SKILL.md:101-115` (its subticket 4) to add
     the mandatory registration step. If this ticket lands first or edits
     blindly, the two collide and one may re-introduce the soft registration
     question. Mitigation: sequence this AFTER reconcile lands (§10), then
     edit the create-ticket region against its post-reconcile state.
  3. **Instructing a tool the operator cannot answer.** Adding
     `AskUserQuestion` to an unattended path (implement-ticket) would wedge the
     autonomous loop. Guarded by the §5 non-goal; implement-ticket is not
     touched.

## 10. Subtickets

Ordered, dependency-aware. A single loop iteration each. The whole ticket is
BLOCKED on `reconcile-registers-orphan-plans` reaching `done` first (it owns
the create-ticket region this ticket also edits).

1. **Convention doc + DECISIONS.md entry** (gated on Q2 answered YES).
   Write `.claude/rules/decision-prompts.md` stating the discrete-fork-to-Q&A
   convention with recommended-option-first, and the iterative-stays-prose
   boundary. Add the `DECISIONS.md` section recording the settled forks. Docs
   only; run the slop scan. Foundation the skill edits cite.
2. **create-eval forks to Q&A.** Convert the scenario count
   (`skills/create-eval/SKILL.md:87`) and the keep/cut, Scorer, and Threshold
   forks (`SKILL.md:89-96`) to `AskUserQuestion`, recommended option first;
   keep the row drafting as prose with an explicit boundary note (R2, R3).
3. **create-ticket eval handoff to Q&A** (after reconcile lands). Convert the
   eval-handoff decision (`skills/create-ticket/SKILL.md:101-115`) to
   `AskUserQuestion`, preserving the `require_eval`-mandatory branch and NOT
   touching the mandatory registration step (R4).
4. **ticket-planner note** (optional, gated on Q4). One-line note that the
   driver asks via `AskUserQuestion`; the planner still returns a path.

## 11. Open questions

Route these to `DECISIONS.md` for the operator to settle before pickup. Each
carries a recommendation; an unresolved one is a `blocked`
(`unresolved-design-fork`), not a silent judgment call.

Q1. **Exactly which points convert, and where is the iterative/discrete
    line drawn?** RECOMMEND the enumeration in §7: convert create-eval's
    scenario count, keep/cut-row, Scorer, and Threshold forks, and
    create-ticket's eval handoff; keep create-eval's Behavior/Input/Expected
    drafting and all open-ended elicitation as prose. Rationale: those four
    plus the handoff are genuine discrete choices with distinct options; the
    drafting is iterative co-authoring the operator explicitly said must not
    become multiple-choice.

Q2. **Is there a shared skill-authoring convention doc, or per-skill edits
    only?** RECOMMEND a new lightweight `.claude/rules/decision-prompts.md`
    (the repo's established home for project conventions, alongside
    `adversarial-reviews.md` and `prek-code-quality.md`) PLUS the per-skill
    edits, so future skills inherit the convention rather than re-deriving it.
    The convention currently lives only in Memex KV (§3), invisible to a
    future skill author working from the repo.

Q3. **Does implement-ticket have any decision point worth a Q&A?** RECOMMEND
    NO. Its forks are `loopctl block` codes for an often-unattended loop
    (`skills/implement-ticket/SKILL.md:149-155`), where `AskUserQuestion` has
    no operator to answer. The one supervised branch (eval-missing recovery,
    `SKILL.md:44-48`) already routes to `create-eval`; it is a mode detection,
    not a fork to ask. FLAG for the operator to confirm implement-ticket stays
    out of scope.

Q4. **Does the ticket-planner agent get a one-line edit?** RECOMMEND a single
    clarifying line that the DRIVER (the create-ticket skill) is where the
    `AskUserQuestion` fires, keeping the planner a return-a-path subagent
    (`agents/ticket-planner.md:79`). Optional; skip if it adds noise.

Q5. **Enable the `documentation` review pass for this ticket?** This change
    edits documented behavior (skill instructions), and the repo ships a
    `loop-doc-reviewer` agent (`agents/loop-doc-reviewer.md`) that is not
    enabled in `.loop/config.json`. RECOMMEND NOT enabling it just for this
    ticket: the slop-scan rule (R7) already covers `.md` freshness, and
    enabling a review pass is a config change that stales the stamp and widens
    scope. Operator may override.

Q6. **Sequencing vs `reconcile-registers-orphan-plans`.** RECOMMEND this
    ticket is BLOCKED until reconcile reaches `done`, because reconcile
    rewrites the same `create-ticket` region (its subticket 4). Landing this
    first risks re-introducing the soft registration question reconcile is
    removing. Operator confirms the order.
