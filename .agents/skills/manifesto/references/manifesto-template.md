# MANIFESTO template

This is the skeleton for a project's `MANIFESTO.md`. It is **language-agnostic** —
it works for a Python service, a TypeScript library, a Go CLI, a monorepo, anything.
Copy the structure below into `MANIFESTO.md` at the repo root and fill it in.

Scale the document to the project. A 500-line CLI does not need §2 or §4; a large
system warrants all of it. **Never invent content to fill a section** — drop sections
that don't apply rather than padding them.

---

## How to write each part

### Enforcers — the load-bearing idea

An **invariant** is a structural rule the project must never violate. What makes it
real (not just aspirational prose) is an **enforcer**: the specific schema field,
type signature, test, assertion, or class in the code that would break/fail if the
rule were violated. Every invariant cites one.

**Anchor enforcers to a symbol or a short code snippet, never a bare line number.**
Line numbers rot the instant any line above them shifts; a quoted symbol survives
refactors and can be re-located by search. Write enforcers like:

> *Enforcer:* `src/models/note.py` — the `status` field's `CheckConstraint(... in ('active','superseded'))` makes the 2-value lifecycle structural, not application-level.

The cited path + snippet (`CheckConstraint(...`) is what goes in the lock's `anchor`.
Pick an anchor string that is **unique within the file** and **stable** (a class/
function name or a distinctive line — not `return None` or `import os`).

If a stated rule has **no** mechanical enforcer, it is not an invariant — list it as
a **Value** instead, or note a test worth adding. Do not fabricate an enforcer.

### Invariants vs. Values
- **Invariants:** structural, mechanically checkable, each with an *Enforcer:* line.
- **Values:** positioning/taste the project believes in but cannot mechanically
  prove (e.g. "prefer composition over inheritance", "optimize for read latency").
  No enforcer. Be honest about which bucket a principle belongs in.

### Current-state discipline (the house rule)
§1–§4 describe what the project **is right now**. Anything that reads as "we used
to…", "before the X migration", "an earlier design said…" belongs in §5, not in body
prose. This keeps the body trustworthy as a current-state reference.

---

## Skeleton (copy below this line into MANIFESTO.md)

```markdown
# <Project> — Manifesto

**Version / baseline:** <commit, tag, or milestone this describes>
**Status:** Current-state reference — describes what <Project> *is* at this baseline.
Historical decisions live in §5.
**Scope:** <vision · architecture · rules — trim to what this doc covers>
**Caveat (optional):** <known unknowns, unverified assumptions, empirical gaps>

---

## 1. Vision

<2–4 paragraphs: what this project is, who it serves (humans? agents? both?), and
the one-sentence reason it exists. What problem does it solve that off-the-shelf
tools don't?>

### 1.1 Why it was built
<The motivating problem / pain. Keep it concrete.>

### 1.2 Design philosophy

Principles that govern the architecture, split into Invariants (enforced) and
Values (taste). Most choices elsewhere in this doc derive from these.

**Invariants — structural properties with an enforcer:**

- **<P1 — short name>.** <One-line statement of the rule.> <Why it matters / what
  breaks if violated.>
  - *Enforcer:* `<path>` — <the symbol/snippet that enforces it and how>.
- **<P2 — short name>.** <…>
  - *Enforcer:* `<path>` — <…>.

**Values — positioning that shapes taste but isn't mechanically checked:**

- **<V1 — short name>.** <Statement + rationale. No enforcer.>
- **<V2 — short name>.** <…>

---

## 2. Theoretical background (optional)

<Only if the project rests on non-obvious ideas, papers, or prior art. Map each
influence to where it shows up in the code. Drop this section entirely for most
projects.>

---

## 3. Architecture

### 3.1 System layers / components
<The major moving parts and how a request/operation flows through them. A Mermaid
`flowchart` is encouraged.>

### 3.2 Module / package layout
| Module / package | Path | Responsibility |
|---|---|---|
| <name> | `<path>` | <what it owns> |

### 3.3 Data / schema (if applicable)
<Key tables, types, or data structures and their invariants.>

### 3.4 Component deep-dives (as needed)
<One subsection per component that carries real complexity. Cite the files.>

### 3.5 Dependency graph (optional)
<Mermaid graph of build-time vs. runtime dependencies between modules.>

---

## 4. Operational characteristics (optional)

<Configuration surface, failure modes / graceful degradation, observability,
performance envelope — whatever a maintainer needs to operate the system. Drop if
not applicable.>

---

## 5. Notable historical decisions

Reverse-chronological. The home for rationale that body prose would otherwise
litigate ("we used to…", "before the X rollback"). Each entry: what changed, why,
and which §1–§4 sections it affected.

**House rule:** §1–§4 are the current-state reference. Anything historical lives here.

### 5.x <Decision name> (<date>)
- **Why:** <rationale / incident / constraint>
- **Affected:** <sections or invariants touched>
```
