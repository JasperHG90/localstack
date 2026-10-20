"""A stand-in for the rclone subcommands the ov-carry-over job runs.

`seaweedfs:<bucket>/<path>` maps to `$FAKE_S3/<bucket>/<path>`, any other path
is local. Filters follow rclone for a pattern with no slash: it matches a
file's name in any folder. Two variables make it misbehave on purpose:
FAKE_RCLONE_LOSE drops every copied file whose path holds that text, and
FAKE_RCLONE_NO_EMPTY_DIRS makes a copy leave out empty folders.
"""

import fnmatch
import os
import shutil
import sys
from pathlib import Path

VALUE_FLAGS = {"--config", "--include", "--exclude"}


def resolve(arg: str) -> Path:
    if arg.startswith("seaweedfs:"):
        return Path(os.environ["FAKE_S3"]) / arg.removeprefix("seaweedfs:")
    return Path(arg)


def parse(argv: list[str]) -> tuple[list[str], set[str], list[str], list[str]]:
    positional: list[str] = []
    flags: set[str] = set()
    includes: list[str] = []
    excludes: list[str] = []
    args = iter(argv)
    for arg in args:
        if arg in VALUE_FLAGS:
            value = next(args)
            if arg == "--include":
                includes.append(value)
            elif arg == "--exclude":
                excludes.append(value)
        elif arg.startswith("-"):
            flags.add(arg)
        else:
            positional.append(arg)
    return positional, flags, includes, excludes


def passes(rel: str, includes: list[str], excludes: list[str]) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatchcase(name, p) for p in excludes):
        return False
    return not includes or any(fnmatch.fnmatchcase(name, p) for p in includes)


def files(root: Path, includes: list[str], excludes: list[str]) -> list[str]:
    if not root.is_dir():
        return []
    found = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    return sorted(rel for rel in found if passes(rel, includes, excludes))


def dirs(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() + "/" for p in root.rglob("*") if p.is_dir())


def main() -> int:
    command, *rest = sys.argv[1:]
    positional, flags, includes, excludes = parse(rest)
    if command == "mkdir":
        resolve(positional[0]).mkdir(parents=True, exist_ok=True)
    elif command == "copy":
        src, dst = resolve(positional[0]), resolve(positional[1])
        if not src.is_dir():
            print(f"source {src} not found", file=sys.stderr)
            return 3
        lose = os.environ.get("FAKE_RCLONE_LOSE")
        if "--create-empty-src-dirs" in flags and not os.environ.get("FAKE_RCLONE_NO_EMPTY_DIRS"):
            for rel in dirs(src):
                (dst / rel).mkdir(parents=True, exist_ok=True)
        for rel in files(src, includes, excludes):
            target = dst / rel
            if lose and lose in target.as_posix():
                continue
            if "--ignore-existing" in flags and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / rel, target)
    elif command == "check":
        src, dst = resolve(positional[0]), resolve(positional[1])
        bad = [
            rel
            for rel in files(src, includes, excludes)
            if not (dst / rel).is_file() or (dst / rel).read_bytes() != (src / rel).read_bytes()
        ]
        for rel in bad:
            print(f"ERROR : {rel}: differs or missing", file=sys.stderr)
        return 1 if bad else 0
    elif command == "lsf":
        root = resolve(positional[0])
        listed: list[str] = []
        if "--dirs-only" not in flags:
            listed += files(root, includes, excludes)
        if "--files-only" not in flags:
            listed += dirs(root)
        for rel in sorted(listed):
            print(rel)
    elif command == "cat":
        root = resolve(positional[0])
        for rel in files(root, includes, excludes):
            sys.stdout.buffer.write((root / rel).read_bytes())
    else:
        print(f"fake rclone does not know {command}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
