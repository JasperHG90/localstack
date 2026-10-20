#!/usr/bin/env python3
"""Re-index what the ov-carry-over job copied into the new OpenViking, copy the
old image rows, then check the outcome.

Run it by hand after `nomad job dispatch ov-carry-over` exits 0, with a token
from docs/how-to/call-openviking-from-the-cli.md in OV_URL and OV_TOKEN:

    python3 scripts/ov_carry_over.py --old-listing openviking.lsf \\
        --psql "psql postgresql://openviking@192.168.2.30:5432/openviking"

`--old-listing` is the `rclone lsf -R` listing of the old bucket from the
cutover baseline. `--psql` is the command that runs SQL as the `openviking`
role, with the password in PGPASSWORD.

In order:

    1. regenerate the summaries of each directory both blog trees held,
       deepest first and blogs/ last, because their kept sidecars describe
       only the blogs half (semantic_and_vectors, recursive=false)
    2. vectors_only on clips, blogs and leo, which reuses the copied
       summaries and makes no VLM call
    3. copy each image's level-2 row from the old schema, which no re-index
       can rebuild in 0.4.17.1 (spike:ov-carry-over/4)
    4. check the outcome, exiting non-zero on the first miss

`--check-only` skips 1 to 3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESOURCES = "viking://user/jasper/resources"
OLD_PREFIX = "lab/user/jasper/resources/"
ACCOUNT = "lab"
TREES = ("clips", "blogs", "leo")
SIDECARS = (".abstract.md", ".overview.md")
# The save-to-openviking skill's map of roots (ADR 0023).
SAVE_MAP = ".map.md"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
OLD_TABLE = "openviking.ov_context"
NEW_TABLE = "openviking_v2.ov_context"
TITLES_PER_TREE = 10
POLL_SECONDS = 5


class CheckFailure(Exception):
    """A step or an outcome check that did not hold. The message is the report."""


def carried_key(key: str) -> str | None:
    """Where a key relative to the old resources folder lands, or None."""
    tree, _, rest = key.partition("/")
    if tree in TREES:
        return key
    if tree == "blog-scraper":
        return f"blogs/{rest}"
    return None


def read_listing(path: Path) -> set[str]:
    """Keys under the resources folder from an `rclone lsf -R` listing.

    Takes plain lsf output or `--format pst`, whose path is the first field.
    """
    keys = set()
    for line in path.read_text().splitlines():
        key = line.split(";", 1)[0].strip()
        if key.startswith(OLD_PREFIX) and key != OLD_PREFIX:
            keys.add(key[len(OLD_PREFIX) :])
    return keys


def is_file(key: str) -> bool:
    return not key.endswith("/") and key.rsplit("/", 1)[-1] not in SIDECARS


def directories(keys: Iterable[str]) -> set[str]:
    """Every directory a key sits in, from its markers and its parents."""
    found = set()
    for key in keys:
        parts = key.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            found.add("/".join(parts[:depth]) + "/")
    return found


def holds_files(old_keys: set[str], prefix: str) -> bool:
    return any(k.startswith(prefix) and is_file(k) for k in old_keys)


def merged_directories(old_keys: set[str]) -> list[str]:
    """Directories where both blog trees hold files, deepest first, blogs/ last.

    A directory with no file on one side has nothing there for its overview to
    name, so its kept sidecars stay. In the old listing every such directory
    held sidecars from only the side with files.
    """
    old_dirs = directories(old_keys)
    merged = [
        d
        for d in old_dirs
        if d.startswith("blogs/")
        and holds_files(old_keys, d)
        and holds_files(old_keys, f"blog-scraper/{d.removeprefix('blogs/')}")
    ]
    return sorted(merged, key=lambda d: (-d.count("/"), d))


def expected_files(old_keys: set[str]) -> dict[str, set[str]]:
    """The files each tree must hold, at their new keys."""
    expected: dict[str, set[str]] = {tree: set() for tree in TREES}
    for key in old_keys:
        new = carried_key(key)
        if new is not None and is_file(key):
            expected[new.split("/", 1)[0]].add(new)
    return expected


def image_keys(old_keys: set[str]) -> list[str]:
    """Old keys of the carried images, which only a row copy makes findable."""
    return sorted(
        k
        for k in old_keys
        if carried_key(k) and is_file(k) and k.lower().endswith(IMAGE_SUFFIXES)
    )


@dataclass(frozen=True)
class Step:
    action: str
    uri: str = ""


def plan(old_keys: set[str]) -> list[Step]:
    steps = [
        Step("regenerate", f"{RESOURCES}/{d.rstrip('/')}")
        for d in merged_directories(old_keys)
    ]
    steps += [Step("vectors", f"{RESOURCES}/{tree}") for tree in TREES]
    steps.append(Step("image-rows"))
    return steps


def row_uri(key: str) -> str:
    """The `uri` column for a key: the adapter stores it without `viking:/`."""
    return f"/user/jasper/resources/{key}"


def row_id(uri: str) -> str:
    """The id OpenViking derives for a level-2 row, from the `viking://` URI.

    `_seed_uri_for_id` and `update_uri_mapping` hash `<account>:<uri>`, so a
    later re-ingest at the same URI updates this row instead of adding one.
    """
    return hashlib.md5(f"{ACCOUNT}:viking:/{uri}".encode()).hexdigest()


def image_rows_sql(old_uris: list[str], columns: list[str]) -> str:
    """Copy the old level-2 rows of these URIs into the new schema.

    Each row lands at its carried URI with the id OpenViking would give it
    there. `columns` are every other column, copied as they are.
    """

    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    mapping = []
    for uri in old_uris:
        new = row_uri(str(carried_key(uri.removeprefix("/user/jasper/resources/"))))
        mapping.append(f"({quote(uri)}, {quote(new)}, {quote(row_id(new))})")
    names = ", ".join(f'"{c}"' for c in columns)
    copied = ", ".join(f'o."{c}"' for c in columns)
    return (
        f"INSERT INTO {NEW_TABLE} (id, uri, {names})\n"
        f"SELECT m.new_id, m.new_uri, {copied}\n"
        f"FROM {OLD_TABLE} o\n"
        f"JOIN (VALUES {', '.join(mapping)}) AS m(old_uri, new_uri, new_id)"
        f" ON o.uri = m.old_uri\n"
        f"WHERE o.level = 2 AND o.account_id = '{ACCOUNT}'\n"
        "ON CONFLICT (id) DO NOTHING;\n"
    )


def compare(
    old_keys: set[str],
    new_files: dict[str, set[str]],
    top_level: set[str],
    allowed: set[str],
) -> tuple[list[str], list[str]]:
    """Problems with what the new instance holds, and files written since.

    clips and leo must hold exactly the old files. blogs must hold every file
    of both blog trees; a file beyond those was saved after the cutover and is
    named, not failed. Under the resources folder only the three trees, their
    root sidecars, the save skill's map and the names in `allowed` may
    exist.
    """
    problems: list[str] = []
    since: list[str] = []
    for tree, want in expected_files(old_keys).items():
        got = new_files.get(tree, set())
        problems += [f"missing {key}" for key in sorted(want - got)]
        extra = sorted(got - want)
        if tree == "blogs":
            since += extra
        elif extra or len(got) != len(want):
            problems.append(
                f"{tree} holds {len(got)} files, the old bucket {len(want)}: "
                + ", ".join(extra or ["(none extra)"])
            )
    for name in sorted(top_level - set(TREES) - set(SIDECARS) - {SAVE_MAP} - allowed):
        if name == "blog-scraper":
            problems.append(
                "blog-scraper/ exists in the new instance: move its keys to blogs/"
            )
        else:
            problems.append(f"unexpected top-level entry {name} under {RESOURCES}/")
    return problems, since


def tree_files(entries: list[dict[str, Any]], tree: str) -> set[str]:
    """Keys relative to the resources folder, from an `fs/tree` listing."""
    keys = set()
    for entry in entries:
        key = f"{tree}/{entry['rel_path']}"
        if not entry.get("isDir") and is_file(key):
            keys.add(key)
    return keys


def collect_uris(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        found = [payload["uri"]] if isinstance(payload.get("uri"), str) else []
        return found + [u for v in payload.values() for u in collect_uris(v)]
    if isinstance(payload, list):
        return [u for v in payload for u in collect_uris(v)]
    return []


class OpenViking:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read()).get("result")
        except urllib.error.HTTPError as error:
            raise CheckFailure(
                f"{method} {path}: HTTP {error.code} {error.read()[:500]!r}"
            )
        except OSError as error:
            raise CheckFailure(f"{method} {path}: {error}") from error

    def get(self, path: str, **params: Any) -> Any:
        return self.call("GET", f"{path}?{urllib.parse.urlencode(params)}")

    def reindex(self, uri: str, mode: str, recursive: bool) -> dict[str, Any]:
        """Run a re-index in the background and wait for it.

        Waiting in the request would outlast HAProxy's 300 s server timeout.
        """
        body = {"uri": uri, "mode": mode, "recursive": recursive, "wait": False}
        task_id = self.call("POST", "/api/v1/content/reindex", body)["task_id"]
        while True:
            task = self.get(f"/api/v1/tasks/{task_id}")
            if task["status"] not in ("pending", "running"):
                break
            time.sleep(POLL_SECONDS)
        result: dict[str, Any] = task.get("result") or {}
        if task["status"] != "completed" or result.get("failed_records"):
            raise CheckFailure(
                f"re-index {mode} {uri}: {task['status']} {json.dumps(result)}"
            )
        return result

    def tree(self, uri: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = self.get(
            "/api/v1/fs/tree",
            uri=uri,
            output="original",
            show_all_hidden="true",
            node_limit=100000,
            level_limit=100,
        )
        return entries

    def finds(self, query: str, uri: str, within: str) -> bool:
        body = {"query": query, "target_uri": within, "limit": 10}
        return uri in collect_uris(self.call("POST", "/api/v1/search/find", body))


def psql(command: list[str], sql: str) -> list[list[str]]:
    done = subprocess.run(
        [
            *command,
            "-X",
            "-q",
            "-A",
            "-t",
            "-F",
            "\t",
            "-v",
            "ON_ERROR_STOP=1",
            "-f",
            "-",
        ],
        input=sql,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise CheckFailure(f"psql failed: {done.stderr.strip()}")
    return [line.split("\t") for line in done.stdout.splitlines() if line]


def columns_sql(table: str) -> str:
    schema, name = table.split(".")
    return (
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{name}' "
        "AND is_generated = 'NEVER' ORDER BY ordinal_position;"
    )


def rows_at(command: list[str], table: str, uris: list[str]) -> set[str]:
    if not uris:
        return set()
    listed = ", ".join("'" + u.replace("'", "''") + "'" for u in uris)
    sql = f"SELECT uri FROM {table} WHERE level = 2 AND uri IN ({listed});"
    return {row[0] for row in psql(command, sql)}


def copy_image_rows(command: list[str], old_keys: set[str]) -> None:
    old_uris = sorted(
        rows_at(command, OLD_TABLE, [row_uri(k) for k in image_keys(old_keys)])
    )
    new_columns = [row[0] for row in psql(command, columns_sql(NEW_TABLE))]
    old_columns = {row[0] for row in psql(command, columns_sql(OLD_TABLE))}
    shared = [c for c in new_columns if c in old_columns and c not in ("id", "uri")]
    if old_uris:
        psql(command, image_rows_sql(old_uris, shared))
    print(f"copied rows for {len(old_uris)} of {len(image_keys(old_keys))} images")


def title_of(text: str, key: str) -> str:
    """A file's first heading, or its name when it has none."""
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return Path(key).stem.replace("_", " ").replace("-", " ")


def children(old_keys: set[str], directory: str) -> set[str]:
    """Names of what sits directly in a directory with a file at or under it.

    An empty folder has no summary for the overview to draw on, so the model
    need not name it.
    """
    names = set()
    for key in old_keys:
        rest = key.removeprefix(directory)
        if key.startswith(directory) and is_file(key) and rest:
            names.add(rest.split("/", 1)[0])
    return names


def check_files(
    ov: OpenViking, old_keys: set[str], allowed: set[str]
) -> dict[str, set[str]]:
    new_files = {
        tree: tree_files(ov.tree(f"{RESOURCES}/{tree}"), tree) for tree in TREES
    }
    listed = ov.get(
        "/api/v1/fs/ls", uri=RESOURCES, output="original", show_all_hidden="true"
    )
    problems, since = compare(old_keys, new_files, {e["name"] for e in listed}, allowed)
    for key in since:
        print(f"note  written since the cutover: {key}")
    if problems:
        raise CheckFailure("\n".join(problems))
    print("pass  every old file is at its new key")
    return new_files


def check_overviews(ov: OpenViking, old_keys: set[str]) -> None:
    for directory in merged_directories(old_keys):
        rest = directory.removeprefix("blogs/")
        blogs = children(old_keys, directory)
        scraper = children(old_keys, f"blog-scraper/{rest}")
        overview = str(
            ov.get("/api/v1/content/overview", uri=f"{RESOURCES}/{directory}")
        )
        for half, names in (
            ("blogs", blogs - scraper),
            ("blog-scraper", scraper - blogs),
        ):
            if names and not any(name in overview for name in names):
                raise CheckFailure(
                    f"the overview of {directory} names nothing from {half}"
                )
    print("pass  each merged overview names files from both halves")


def check_images(ov: OpenViking, command: list[str], old_keys: set[str]) -> None:
    old_rows = rows_at(command, OLD_TABLE, [row_uri(k) for k in image_keys(old_keys)])
    carried = sorted(
        str(carried_key(u.removeprefix("/user/jasper/resources/"))) for u in old_rows
    )
    missing = {row_uri(k) for k in carried} - rows_at(
        command, NEW_TABLE, [row_uri(k) for k in carried]
    )
    if missing:
        raise CheckFailure(
            "image rows missing in the new schema: " + ", ".join(sorted(missing))
        )
    for key in carried:
        tree = key.split("/", 1)[0]
        if not ov.finds(Path(key).name, f"{RESOURCES}/{key}", f"{RESOURCES}/{tree}"):
            raise CheckFailure(f"find for {Path(key).name} does not return {key}")
    print(
        f"pass  {len(carried)} images have a row at their new URI and are found by name"
    )


def check_titles(ov: OpenViking, new_files: dict[str, set[str]]) -> None:
    rng = random.Random()
    for tree, files in new_files.items():
        texts = sorted(k for k in files if not k.lower().endswith(IMAGE_SUFFIXES))
        for key in rng.sample(texts, min(TITLES_PER_TREE, len(texts))):
            uri = f"{RESOURCES}/{key}"
            query = title_of(str(ov.get("/api/v1/content/read", uri=uri)), key)
            if not ov.finds(query, uri, f"{RESOURCES}/{tree}"):
                raise CheckFailure(f"find for {query!r} does not return {key}")
    print(f"pass  a title search finds each of {TITLES_PER_TREE} random files per tree")


def run(ov: OpenViking, command: list[str], old_keys: set[str]) -> None:
    for step in plan(old_keys):
        if step.action == "regenerate":
            ov.reindex(step.uri, "semantic_and_vectors", recursive=False)
            print(f"done  regenerated {step.uri}")
        elif step.action == "vectors":
            result = ov.reindex(step.uri, "vectors_only", recursive=True)
            print(f"done  vectors_only {step.uri}: {json.dumps(result)}")
        else:
            copy_image_rows(command, old_keys)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--old-listing", type=Path, required=True)
    parser.add_argument(
        "--psql", required=True, help="command that runs psql as openviking"
    )
    parser.add_argument("--url", default=None, help="defaults to $OV_URL")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="another name allowed under resources/",
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)

    ov = OpenViking(args.url or os.environ["OV_URL"], os.environ["OV_TOKEN"])
    command = shlex.split(args.psql)
    old_keys = read_listing(args.old_listing)
    try:
        if not args.check_only:
            run(ov, command, old_keys)
        new_files = check_files(ov, old_keys, set(args.allow))
        check_overviews(ov, old_keys)
        check_images(ov, command, old_keys)
        check_titles(ov, new_files)
    except CheckFailure as failure:
        print(f"FAIL  {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
