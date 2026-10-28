#!/usr/bin/env python3
"""manifesto_state.py — drift bookkeeping for a project's MANIFESTO.md.

Self-contained, pure stdlib. Knows nothing about how the skill was installed.

The lock file (`.manifesto/lock.json`, relative to --root) is the machine-readable
companion to MANIFESTO.md. The agent authors the *spec* portion (which enforcers
exist and which files/globs are architecturally significant); this script fills in
the *computed* portion (resolved line numbers and content hashes) and reports drift.

Enforcers are anchored by a literal code SNIPPET or SYMBOL string, never by a bare
line number — line numbers shift on any edit above them, snippets do not. The line
is resolved live by searching the file for the anchor.

Lock schema (v1):
{
  "version": 1,
  "manifesto_path": "MANIFESTO.md",
  "enforcers": [
    {"id": "P1", "title": "...", "path": "src/foo.py", "anchor": "class Note(",
     "resolved_line": 42, "file_sha256": "..."}
  ],
  "tracked_globs": ["src/**/*.py"],
  "tracked_files": {"src/foo.py": "<sha256>"}
}

The agent provides: enforcers[].{id,title,path,anchor} and tracked_globs.
`write` recomputes: enforcers[].{resolved_line,file_sha256}, and tracked_files.

Commands:
  resolve <path> <anchor>   Find the anchor's current line(s) in a file.
  write                     Recompute resolved lines + hashes from the lock spec.
  diff                      List tracked files whose content changed since `write`.
  verify                    Re-resolve every enforcer anchor; report drift. (read-only)
  tracked                   List tracked files recorded in the lock.

Exit codes: 0 = clean / found; 1 = drift / not found; 2 = usage or lock error.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

LOCK_REL = Path(".manifesto") / "lock.json"


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _find_anchor(path: Path, anchor: str) -> list[int]:
    """Return 1-based line numbers where the anchor appears.

    The anchor is treated as a literal. For a multi-line snippet we match its
    first non-empty line. Exact substring match is tried first; if that yields
    nothing we fall back to a whitespace-insensitive comparison so reindentation
    doesn't count as drift.
    """
    needle = anchor.strip()
    if "\n" in needle:
        for line in needle.splitlines():
            if line.strip():
                needle = line.strip()
                break
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    exact = [i + 1 for i, ln in enumerate(lines) if needle in ln]
    if exact:
        return exact
    collapsed = " ".join(needle.split())
    return [
        i + 1
        for i, ln in enumerate(lines)
        if collapsed and collapsed in " ".join(ln.split())
    ]


def _load_lock(root: Path) -> dict:
    lock_path = root / LOCK_REL
    if not lock_path.exists():
        raise FileNotFoundError(f"no lock at {lock_path}")
    return json.loads(lock_path.read_text(encoding="utf-8"))


def _save_lock(root: Path, data: dict) -> Path:
    lock_path = root / LOCK_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return lock_path


def _expand_tracked(
    root: Path, globs: list[str], enforcer_paths: list[str]
) -> dict[str, str]:
    out: dict[str, str] = {}
    rels: set[str] = set()
    for pattern in globs:
        for hit in glob.glob(str(root / pattern), recursive=True):
            p = Path(hit)
            if p.is_file():
                rels.add(str(p.relative_to(root)))
    for ep in enforcer_paths:
        if (root / ep).is_file():
            rels.add(ep)
    for rel in sorted(rels):
        digest = _sha256(root / rel)
        if digest is not None:
            out[rel] = digest
    return out


def cmd_resolve(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = root / args.path
    if not target.is_file():
        print(f"missing-file\t{args.path}")
        return 1
    hits = _find_anchor(target, args.anchor)
    if not hits:
        print(f"missing-anchor\t{args.path}\t{args.anchor!r}")
        return 1
    if len(hits) > 1:
        print(f"ambiguous\t{args.path}:{','.join(map(str, hits))}\t{args.anchor!r}")
        return 1
    print(f"ok\t{args.path}:{hits[0]}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        lock = _load_lock(root)
    except FileNotFoundError:
        lock = {
            "version": 1,
            "manifesto_path": "MANIFESTO.md",
            "enforcers": [],
            "tracked_globs": [],
        }
    except json.JSONDecodeError as exc:
        print(f"error: lock is not valid JSON: {exc}", file=sys.stderr)
        return 2

    lock.setdefault("version", 1)
    lock.setdefault("manifesto_path", "MANIFESTO.md")
    enforcers = lock.setdefault("enforcers", [])
    globs = lock.setdefault("tracked_globs", [])

    drift = False
    for enf in enforcers:
        path = enf.get("path")
        anchor = enf.get("anchor")
        if not path or not anchor:
            continue
        target = root / path
        hits = _find_anchor(target, anchor) if target.is_file() else []
        enf["resolved_line"] = hits[0] if len(hits) == 1 else None
        enf["file_sha256"] = _sha256(target)
        if len(hits) != 1:
            drift = True

    enforcer_paths = [e["path"] for e in enforcers if e.get("path")]
    lock["tracked_files"] = _expand_tracked(root, globs, enforcer_paths)

    saved = _save_lock(root, lock)
    print(
        f"wrote {saved.relative_to(root)} — {len(enforcers)} enforcers, "
        f"{len(lock['tracked_files'])} tracked files"
    )
    return 1 if drift else 0


def cmd_diff(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        lock = _load_lock(root)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tracked = lock.get("tracked_files", {})
    changed: list[str] = []
    missing: list[str] = []
    for rel, recorded in sorted(tracked.items()):
        current = _sha256(root / rel)
        if current is None:
            missing.append(rel)
        elif current != recorded:
            changed.append(rel)
    for rel in missing:
        print(f"missing\t{rel}")
    for rel in changed:
        print(f"changed\t{rel}")
    if not changed and not missing:
        print("clean")
        return 0
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        lock = _load_lock(root)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    drift = False
    for enf in lock.get("enforcers", []):
        eid = enf.get("id", "?")
        path = enf.get("path", "")
        anchor = enf.get("anchor", "")
        recorded = enf.get("resolved_line")
        target = root / path
        if not target.is_file():
            print(f"missing-file\t{eid}\t{path}")
            drift = True
            continue
        hits = _find_anchor(target, anchor)
        if not hits:
            print(f"missing-anchor\t{eid}\t{path}\t{anchor!r}")
            drift = True
        elif len(hits) > 1:
            print(f"ambiguous\t{eid}\t{path}:{','.join(map(str, hits))}")
            drift = True
        elif recorded is not None and hits[0] != recorded:
            print(f"moved\t{eid}\t{path}:{recorded}->{hits[0]}")
            drift = True
        else:
            print(f"ok\t{eid}\t{path}:{hits[0]}")
    return 1 if drift else 0


def cmd_tracked(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    try:
        lock = _load_lock(root)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for rel in sorted(lock.get("tracked_files", {})):
        print(rel)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MANIFESTO.md drift bookkeeping")
    parser.add_argument("--root", default=".", help="project root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser(
        "resolve", help="find an anchor's current line in a file"
    )
    p_resolve.add_argument("path")
    p_resolve.add_argument("anchor")
    p_resolve.set_defaults(func=cmd_resolve)

    sub.add_parser("write", help="recompute resolved lines + hashes").set_defaults(
        func=cmd_write
    )
    sub.add_parser("diff", help="list tracked files that changed").set_defaults(
        func=cmd_diff
    )
    sub.add_parser("verify", help="re-resolve every enforcer anchor").set_defaults(
        func=cmd_verify
    )
    sub.add_parser("tracked", help="list tracked files").set_defaults(func=cmd_tracked)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
