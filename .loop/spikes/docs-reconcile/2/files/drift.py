"""Spike for docs-reconcile risk 4: is docs drift a docs bug or a code bug?

(a) Backticked file-like paths in docs/{how-to,reference,explanation} that do
    not resolve from the repo root or the page folder, classified as
    shorthand (basename/suffix of a tracked file), renamed/deleted (in git
    history), or missing (possible code bug).
(b) `just` recipes and `localstack` subcommands/flags in inline code and
    fenced blocks, checked against every justfile and the CLI's --help.

Exit 0 when no possible-code-bug items are found, 1 otherwise.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
FOLDERS = ["docs/how-to", "docs/reference", "docs/explanation"]
EXTS = {"md", "py", "tf", "hcl", "sh", "yml", "yaml", "toml", "json", "j2",
        "txt", "cfg", "conf", "service", "nomad", "tpl", "lock", "png",
        "drawio", "env", "ini", "pem", "csv", "jsonl"}


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=True).stdout


tracked = git("ls-files").splitlines()
top_dirs = {p.split("/")[0] for p in tracked if "/" in p}

# history: old paths that were renamed or deleted, with the commit
hist = {}
log = git("log", "--diff-filter=RD", "--name-status", "--format=@%h %s")
commit = None
for line in log.splitlines():
    if line.startswith("@"):
        commit = line[1:]
        continue
    parts = line.split("\t")
    if not parts or not parts[0]:
        continue
    if parts[0].startswith("R") and len(parts) == 3:
        hist.setdefault(parts[1], ("renamed to " + parts[2], commit))
    elif parts[0] == "D" and len(parts) == 2:
        hist.setdefault(parts[1], ("deleted", commit))

pages = sorted(p for f in FOLDERS for p in (ROOT / f).glob("*.md")
               if p.name != "README.md")

INLINE = re.compile(r"`([^`\n]+)`")


def file_like(tok):
    if " " in tok or "://" in tok or tok.startswith(("/", "~", "$", "-")):
        return False
    if any(c in tok for c in "<>{}*=:@|"):
        return False
    tok = tok.rstrip("/")
    if tok.split("/")[-1].startswith("."):
        return False
    ext = tok.rsplit(".", 1)[-1] if "." in tok.split("/")[-1] else ""
    if ext in EXTS:
        return True
    return "/" in tok and tok.split("/")[0] in top_dirs


def named_in_code(tok):
    p = subprocess.run(["git", "grep", "-l", "-F", tok, "--", ".",
                        ":!docs", ":!.okf", ":!.loop", ":!*.md"],
                       capture_output=True, text=True)
    return p.stdout.split()


def classify(tok, page):
    t = tok.rstrip("/")
    if (ROOT / t).exists() or (page.parent / t).exists():
        return None
    hits = [p for p in tracked
            if p.endswith("/" + t) or ("/" + p + "/").find("/" + t + "/") >= 0]
    if hits:
        return ("docs-bug:shorthand", ", ".join(sorted(hits)[:3]))
    if t in hist:
        what, c = hist[t]
        return ("docs-bug:renamed", f"{what} in {c}")
    for old, (what, c) in hist.items():
        if old.endswith("/" + t):
            return ("docs-bug:renamed", f"{old} {what} in {c}")
    code = named_in_code(t)
    if code:
        return ("not-drift:runtime-path", "named in " + ", ".join(code[:2]))
    return ("possible-code-bug:missing", "no tracked file, history or code match")


print("== (a) unresolved backticked paths ==")
counts_a = {}
seen = set()
for page in pages:
    text = page.read_text()
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for tok in INLINE.findall(text):
        if not file_like(tok) or (page, tok) in seen:
            continue
        seen.add((page, tok))
        r = classify(tok, page)
        if r:
            counts_a[r[0]] = counts_a.get(r[0], 0) + 1
            print(f"{r[0]:28} {page.relative_to(ROOT)}: `{tok}` -> {r[1]}")
print("counts (a):", counts_a)

# (b) just recipes across every justfile
recipes = {}
for jf in [p for p in tracked if p.endswith("justfile")]:
    out = subprocess.run(["just", "--justfile", jf, "--summary"],
                         capture_output=True, text=True).stdout.split()
    for r in out:
        recipes.setdefault(r, []).append(jf)

env = dict(os.environ, COLUMNS="250", NO_COLOR="1", TERM="dumb")
help_cache = {}


def cli_help(words):
    key = tuple(words)
    if key not in help_cache:
        p = subprocess.run(["uv", "run", "--quiet", "--directory", "cli",
                            "localstack", *words, "--help"],
                           capture_output=True, text=True, env=env)
        help_cache[key] = (p.returncode, p.stdout + p.stderr)
    return help_cache[key]


def commands_in(page):
    text = page.read_text()
    lines = []
    for block in re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S):
        lines += block.splitlines()
    lines += INLINE.findall(re.sub(r"```.*?```", "", text, flags=re.S))
    for ln in lines:
        ln = ln.strip().lstrip("$ ").strip()
        for seg in re.split(r"\s*(?:&&|\|\||;|\||\$\()\s*", ln):
            seg = seg.strip()
            m = re.match(r"(?:uv run (?:--directory cli )?)?(just|localstack)(\s.*)?$", seg)
            if m:
                yield m.group(1), [a.strip(")\"'") for a in (m.group(2) or "").split()]


print("\n== (b) just recipes and localstack commands ==")
counts_b = {}
checked_pages = set()
for page in pages:
    for tool, args in commands_in(page):
        checked_pages.add(page)
        rel = page.relative_to(ROOT)
        if tool == "just":
            pos = [a for a in args if not a.startswith("-")]
            if not pos:
                continue
            r = pos[0]
            if r in recipes:
                counts_b["ok"] = counts_b.get("ok", 0) + 1
            else:
                counts_b["just-missing"] = counts_b.get("just-missing", 0) + 1
                print(f"just-missing   {rel}: just {' '.join(args)}")
            continue
        words = []
        for a in args:
            if a.startswith("-") or a.startswith("<") or not re.match(r"^[a-z][a-z-]*$", a):
                break
            rc, _ = cli_help(words + [a])
            if rc != 0:
                break
            # an argument also yields rc 0 at a leaf; check it is a listed command
            _, parent = cli_help(words)
            if not re.search(r"│\s+" + re.escape(a) + r"\s", parent):
                break
            words.append(a)
        rc, h = cli_help(words)
        bad = [a.split("=")[0] for a in args
               if a.startswith("--") and a.split("=")[0] not in h]
        if args and not words and args[0][0].isalpha() and not args[0].startswith("<"):
            counts_b["localstack-bad-cmd"] = counts_b.get("localstack-bad-cmd", 0) + 1
            print(f"localstack-bad-cmd {rel}: localstack {' '.join(args)}")
        elif bad:
            counts_b["localstack-bad-flag"] = counts_b.get("localstack-bad-flag", 0) + 1
            print(f"localstack-bad-flag {rel}: localstack {' '.join(args)} {bad}")
        else:
            counts_b["ok"] = counts_b.get("ok", 0) + 1
print(f"pages with commands: {len(checked_pages)}")
print("counts (b):", counts_b)

code_bugs = counts_a.get("possible-code-bug:missing", 0)
cli_bad = sum(v for k, v in counts_b.items() if k != "ok")
drift = sum(v for k, v in counts_a.items() if k.startswith("docs-bug")) + cli_bad
print(f"\nsummary: docs-bug {drift - cli_bad} paths + {cli_bad} commands, "
      f"possible-code-bug {code_bugs}")
# risk holds when code-side candidates are more than a handful of the drift
sys.exit(1 if code_bugs > max(3, drift // 5) else 0)
