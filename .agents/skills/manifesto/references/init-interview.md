# Init interview — question bank

The vision behind a project and the *rationale* behind its rules cannot be read out
of the code. They live in the maintainer's head. `init` mode extracts them through a
short interview, then fuses them with what you mined from the codebase.

**How to run it:** prefer `AskUserQuestion` in small batches (one theme at a time).
Always **infer from the code first** and ask only the gaps — show the user what you
already concluded and let them correct it. A good interview is mostly the user saying
"yes, except…", not answering from a blank slate. Don't dump all questions at once.

Use this as a checklist of what you need, not a rigid script.

---

## Batch 1 — Vision
- **Problem:** What problem does this exist to solve? What's painful without it?
- **Audience:** Who/what uses it — humans, agents, other services, all three?
- **One-liner:** If you had one sentence to say what this is, what is it?
- **Non-goals:** What is this deliberately *not* trying to do? (Sharpens scope.)

## Batch 2 — Principles (the heart of it)
Surface candidate principles yourself from the architecture, then for **each one**
confirm with the user:
- **Statement:** the rule, in one line.
- **Invariant or value?** Is there something in the code that *enforces* this
  (a schema constraint, a type, a test, an assertion, a CI check)? If yes →
  **invariant**, and find the enforcer. If it's taste/positioning with no mechanical
  check → **value**.
- **What breaks if violated?** The concrete failure. (If "nothing really" — it may
  be a value, or not worth stating.)
- **Why does it exist?** The incident, constraint, or belief that motivated it. This
  is the part you can't get from code and the part future maintainers need most.

Ask explicitly: *"Are there rules you'd consider non-negotiable that I haven't
listed?"* Maintainers often hold invariants that aren't obvious from a code skim.

## Batch 3 — Architecture framing
- **Boundaries:** What are the major layers/components, and where are the seams that
  must not be crossed casually?
- **Architecturally-significant paths:** Which files/dirs, if changed, most likely
  affect the architecture or an invariant? (These become the lock's `tracked_globs`
  — they drive the drift hook. Aim for the load-bearing 10–20%, not everything.)
- **Entry points:** Where does execution start (CLI, server, library API)?

## Batch 4 — Scope & rigor
- **Sections:** Which template sections apply? (Small projects usually skip §2 and
  §4.) Confirm before generating so you don't write empty headers.
- **Baseline label:** What version/commit/milestone should the doc say it describes?
- **Caveats:** Any known unknowns or unverified assumptions worth flagging up top?

---

## After the interview
1. For every claimed **invariant**, locate the enforcer in the code and capture a
   stable `path` + `anchor` (symbol/snippet). If you can't find one, take it back to
   the user: downgrade to a value, or note a test worth adding. **Never fabricate.**
2. Draft `MANIFESTO.md` from the template; show the user before finalizing.
3. Record enforcers + `tracked_globs` in `.manifesto/lock.json` and run
   `manifesto_state.py write`.
