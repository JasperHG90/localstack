"""The registry view's persisted store, on the dash_data volume.

Traps this file exists to absorb:

- A `cards` row is keyed by a content digest, so its content cannot change.
  It is never invalidated, only evicted once no `tags` row references it.
- `sqlite3` blocks the event loop, so no call here runs without the thread
  hop in `_to_thread`.
- One connection shared across those threads breaks under concurrent
  writes: measured as a raise, as a silently lost row, and as a SIGSEGV.
  That is why this class holds a PATH and never a connection, and why
  `check_same_thread=False` is absent rather than set: it silences the
  thread guard without making the connection concurrency-safe.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS repos (
        name         TEXT PRIMARY KEY,
        first_seen   TEXT,
        last_seen    TEXT,
        last_changed TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tags (
        repo       TEXT NOT NULL,
        tag        TEXT NOT NULL,
        digest     TEXT NOT NULL,
        checked_at TEXT,
        PRIMARY KEY (repo, tag)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cards (
        digest     TEXT PRIMARY KEY,
        entry_json TEXT,
        fetched_at TEXT
    )
    """,
)


async def _to_thread(func: Callable[..., T], *args: Any) -> T:
    """Run one blocking database call off the event loop."""
    return await asyncio.to_thread(func, *args)


class RegistryStore:
    """Owns the database path. Every call opens and closes its own connection."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def create_schema(self) -> None:
        conn = self._connect()
        try:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()

    def put_card(self, digest: str, entry: dict[str, Any]) -> None:
        """Everything about a digest that does not vary by tag.

        Layers ride along deliberately: without them a warm sweep would
        still GET a manifest per digest just to redraw the layer table.
        """
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cards (digest, entry_json, fetched_at)"
                " VALUES (?, ?, datetime('now'))",
                (digest, json.dumps(entry)),
            )
            conn.commit()
        finally:
            conn.close()

    def get_card(self, digest: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT entry_json FROM cards WHERE digest = ?", (digest,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return dict(json.loads(row[0]))

    def put_tag(self, repo: str, tag: str, digest: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO tags (repo, tag, digest, checked_at)"
                " VALUES (?, ?, ?, datetime('now'))",
                (repo, tag, digest),
            )
            conn.execute(
                "INSERT INTO repos (name, first_seen, last_seen) VALUES (?, datetime('now'),"
                " datetime('now')) ON CONFLICT(name) DO UPDATE SET last_seen = datetime('now')",
                (repo,),
            )
            conn.commit()
        finally:
            conn.close()

    def known_digest(self, repo: str, tag: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT digest FROM tags WHERE repo = ? AND tag = ?", (repo, tag)
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else str(row[0])

    def replace_tags(self, seen: list[tuple[str, str, str]]) -> None:
        """Make `tags` hold exactly what this sweep saw.

        A tag the sweep no longer returns is gone from the registry, so its
        row goes too; `evict_unreferenced_cards` then drops any card left
        with nothing pointing at it.
        """
        conn = self._connect()
        try:
            conn.execute("DELETE FROM tags")
            conn.executemany(
                "INSERT OR REPLACE INTO tags (repo, tag, digest, checked_at)"
                " VALUES (?, ?, ?, datetime('now'))",
                seen,
            )
            conn.commit()
        finally:
            conn.close()

    def evict_unreferenced_cards(self) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM cards WHERE digest NOT IN (SELECT digest FROM tags)")
            conn.commit()
        finally:
            conn.close()

    async def aput_card(self, digest: str, entry: dict[str, Any]) -> None:
        await _to_thread(self.put_card, digest, entry)

    async def aget_card(self, digest: str) -> dict[str, Any] | None:
        return await _to_thread(self.get_card, digest)

    async def aput_tag(self, repo: str, tag: str, digest: str) -> None:
        await _to_thread(self.put_tag, repo, tag, digest)

    async def aknown_digest(self, repo: str, tag: str) -> str | None:
        return await _to_thread(self.known_digest, repo, tag)

    async def aevict_unreferenced_cards(self) -> None:
        await _to_thread(self.evict_unreferenced_cards)

    async def areplace_tags(self, seen: list[tuple[str, str, str]]) -> None:
        await _to_thread(self.replace_tags, seen)
