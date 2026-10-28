---
name: manifesto
description: |
  Create and maintain a MANIFESTO.md at a project's root — a living document capturing the project's vision, architecture, architectural rules, and design rules, where every hard "invariant" is anchored to the code that enforces it. Use this whenever the user wants to "write/set up a manifesto", "document the architecture and design rules", "create a vision/design doc", "capture our architectural invariants", or asks how a project is *supposed* to be built. ALSO use it proactively to keep the doc honest: whenever the user makes or describes an architecturally significant change — a new module or package, a changed/added invariant, a refactor of a core boundary, a dependency added or removed, a schema change — offer to reconcile MANIFESTO.md, even if they don't mention the manifesto. Three modes: init (interactive Q&A + codebase mining to bootstrap the doc), sync (reconcile the doc with changed code), and verify (read-only audit that every enforcer still resolves).
---

# Manifesto

Maintains a `MANIFESTO.md` at a project root: the project's **vision, architecture,
architectural rules, and design rules**. Its distinguishing feature is rigor — every
**invariant** (a rule the project must never violate) cites an **enforcer**: the exact
schema field, type, test, or class in the code that makes the rule real. Aspirational
**values** are kept separate. A machine-readable lock plus an optional `Stop` hook keep
the doc from rotting as the code evolves.

This skill is self-contained and project-agnostic. It discovers each project's language,
layout, and conventions at runtime — it makes no assumptions about stack or tooling.

## Why this exists

Architecture docs rot because they're prose with no link to the code. This skill fixes
that two ways: (1) invariants are **symbol-anchored** to enforcing code, so drift is
detectable, never a bare line number that silently goes stale; (2) vision and the *why*
behind rules — the parts you can't read out of the code — are captured through a short
interview, so the doc holds knowledge the repo itself doesn't.

## Pick a mode

- **No `MANIFESTO.md` at the repo root?** → **init** (§ Mode A).
- **It exists and code has changed / the user made an architectural change?** → **sync** (§ Mode B).
- **Just want to know if it's still accurate, no edits?** → **verify** (§ Mode C).

Two helpers (`scripts/` — pure stdlib, run with `python3`):
- `manifesto_state.py` — the drift bookkeeper. `resolve` / `write` / `diff` / `verify` / `tracked`.
- `install_hook.py` — wire/repair/remove the optional `Stop` drift hook.

### The lock (`.manifesto/lock.json`)

The machine-readable companion to the prose doc. **You author the spec**, the script
fills in the computed fields:

- You write: `enforcers[]` as `{id, title, path, anchor}` and `tracked_globs[]`.
- `manifesto_state.py write` computes: each enforcer's `resolved_line` + `file_sha256`,
  and the `tracked_files` hash map (from the globs + enforcer paths).

`anchor` is a **literal symbol or short code snippet** that is unique and stable within
its file (a class/function name, a distinctive constraint line) — **never a bare line
number**. The line is resolved by searching for the anchor, so it survives edits above it.

---

## Mode A — init (interactive)

Bootstrap a new `MANIFESTO.md`. This is a collaboration: you mine the code, the user
supplies vision and rationale.

1. **Mine the codebase.** Spawn `Explore` agents (in parallel) to map layout, entry
   points, core modules, the dependency graph, and tests — for whatever stack this is.
   → verify: you can write a short architecture sketch and a candidate list of principles.
2. **Interview the user**, following `references/init-interview.md`. Capture the vision,
   and for each candidate principle confirm whether it's an **invariant** (something in
   code enforces it) or a **value** (taste), plus the **rationale** behind it. Infer
   from code first; ask only the gaps via `AskUserQuestion`, in small batches.
   → verify: the user confirms the principle list and the invariant-vs-value split.
3. **Locate + anchor enforcers.** For each invariant, find the enforcing code and pick a
   stable `path` + `anchor`. Confirm each resolves:
   ```bash
   python3 scripts/manifesto_state.py resolve <path> "<anchor>"
   ```
   If an invariant has no enforcer, take it back to the user — downgrade it to a value or
   note a test worth adding. **Never fabricate an enforcer.**
   → verify: every invariant's anchor prints `ok` (a single match), or is explicitly
   recorded as enforcer-less.
4. **Write `MANIFESTO.md`** at the repo root from `references/manifesto-template.md`,
   scaling sections to the project (drop §2/§4 for small projects). Show the user before
   finalizing. → verify: the doc exists at the root and reads as current-state.
5. **Write the lock.** Create `.manifesto/lock.json` with the `enforcers` spec
   (`{id, title, path, anchor}` each) and `tracked_globs` (the architecturally
   significant paths from the interview — the load-bearing 10–20%, not everything), then:
   ```bash
   python3 scripts/manifesto_state.py write
   ```
   → verify: command reports the enforcer + tracked-file counts and exits 0 (exit 1 means
   an anchor didn't resolve uniquely — fix it).
6. **Offer the drift hook.** Ask the user if they want the optional `Stop` hook that
   nudges when tracked files change. Only if they agree:
   ```bash
   python3 scripts/install_hook.py
   ```
   → verify: it prints the installed command pointing at this skill's `manifesto_hook.py`;
   re-running is a harmless no-op.

---

## Mode B — sync (reconcile)

The doc exists; reconcile it with the current code.

1. **Find what moved.**
   ```bash
   python3 scripts/manifesto_state.py diff     # tracked files whose content changed
   python3 scripts/manifesto_state.py verify   # enforcer anchors: ok / moved / missing
   ```
2. **Reconcile.** For each changed file and each non-`ok` enforcer, re-read the code and
   update the affected claims in `MANIFESTO.md`. A `moved` anchor usually just needs a
   re-`write` (the prose is still true); a `missing-anchor` / `missing-file` means the
   enforcer changed — find the new enforcing code and update the `anchor`, or escalate
   (next step).
3. **Invariant violations escalate — do not silently weaken the doc.** If a change
   appears to break a *stated invariant* (the enforcer is gone and nothing replaced it),
   stop and ask the user: is the code wrong, or is the rule no longer an invariant?
   Editing the manifesto to match broken code without asking defeats the point.
4. **Preserve history.** When a rule genuinely changes, move its old rationale into
   §5 *Notable historical decisions* rather than deleting it. Keep §1–§4 current-state.
5. **Re-validate the hook** (it may have been relocated) and refresh the lock:
   ```bash
   python3 scripts/install_hook.py --validate   # repairs a drifted path; exit 1 if absent
   python3 scripts/manifesto_state.py write
   ```
   → verify: `python3 scripts/manifesto_state.py verify` now exits 0 (all anchors `ok`).

---

## Mode C — verify (read-only)

Audit accuracy without editing anything.

```bash
python3 scripts/manifesto_state.py verify
```

Each enforcer reports `ok` / `moved` (line differs — auto-fixable by `sync`) /
`missing-anchor` / `missing-file` / `ambiguous` (anchor matches multiple lines — make it
more specific). Summarize the drift for the user and recommend `sync` if anything is off.
**Make no edits in this mode.** → verify: you reported a pass/fail summary and changed no files.

---

## The drift hook

`manifesto_hook.py` is an optional Claude Code **`Stop` hook**. When a turn ends, it
hashes the tracked files; if any changed since the last `write`, it surfaces a one-time,
per-session reminder to run `sync`. It is a deliberately cheap, language-agnostic
*advisory* signal — the authoritative check is `manifesto_state.py verify`. It **fails
open**: a missing lock or any error means it does nothing and never blocks a turn.

- Install: `python3 scripts/install_hook.py`
- Repair a drifted path (run by `sync`): `python3 scripts/install_hook.py --validate`
- Remove: `python3 scripts/install_hook.py --uninstall`

It edits `<project>/.claude/settings.json`, preserving any existing hooks and settings.
The hook command is written as an absolute path resolved at install time, so it's correct
regardless of where the skill lives.

## Notes

- Keep `MANIFESTO.md` current-state; everything historical goes in §5 (the house rule).
- An invariant without a mechanical enforcer is a **value** — be honest about the split;
  it's what makes the "invariant" label trustworthy.
- `tracked_globs` should target the architecturally load-bearing files, not the whole
  tree — too broad and the hook nags on every cosmetic edit.
