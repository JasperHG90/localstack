"""The SQLite layer: no network, no respx.

The eight-concurrent-writes test is the point of this file. A shared
connection passes a read-only concurrency test 20 times out of 20 while
losing rows under writes in 39 of 40, so a read-only variant of that test
certifies the wrong property and is explicitly not what is written here.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from registry_ui import registry_store
from registry_ui.registry_store import RegistryStore


def test_schema_is_created_and_creating_it_twice_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "registry.db"
    RegistryStore(path).create_schema()
    RegistryStore(path).create_schema()
    with sqlite3.connect(path) as conn:
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"repos", "tags", "cards"} <= names


def test_a_card_survives_a_close_and_reopen(tmp_path: Path) -> None:
    path = tmp_path / "registry.db"
    store = RegistryStore(path)
    store.create_schema()
    store.put_card("sha256:one", {"card_html": "<p>hi</p>", "kind": "model"})

    reopened = RegistryStore(path)
    card = reopened.get_card("sha256:one")
    assert card is not None
    assert card["card_html"] == "<p>hi</p>"


def test_a_card_is_evicted_once_no_tag_references_its_digest(tmp_path: Path) -> None:
    path = tmp_path / "registry.db"
    store = RegistryStore(path)
    store.create_schema()
    store.put_card("sha256:keep", {"card_html": "<p>keep</p>"})
    store.put_card("sha256:drop", {"card_html": "<p>drop</p>"})
    store.put_tag("repo", "latest", "sha256:keep")

    store.evict_unreferenced_cards()

    assert store.get_card("sha256:keep") is not None
    assert store.get_card("sha256:drop") is None


def test_a_tag_repointed_to_a_new_digest_updates_rather_than_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "registry.db"
    store = RegistryStore(path)
    store.create_schema()
    store.put_tag("repo", "latest", "sha256:old")
    store.put_tag("repo", "latest", "sha256:new")

    assert store.known_digest("repo", "latest") == "sha256:new"
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM tags WHERE repo='repo'").fetchone()[0]
    assert rows == 1


def test_known_digest_is_none_for_a_tag_never_seen(tmp_path: Path) -> None:
    store = RegistryStore(tmp_path / "registry.db")
    store.create_schema()
    assert store.known_digest("repo", "latest") is None


def test_every_public_call_reaches_sqlite_through_the_thread_offload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No database call may run on the event loop (Requirement 25)."""
    store = RegistryStore(tmp_path / "registry.db")
    store.create_schema()

    calls: list[str] = []
    real = registry_store._to_thread

    async def spy(func: Any, *args: Any) -> Any:
        calls.append(getattr(func, "__name__", repr(func)))
        return await real(func, *args)

    monkeypatch.setattr(registry_store, "_to_thread", spy)

    async def drive() -> None:
        await store.aput_card("sha256:x", {"card_html": "<p>x</p>"})
        await store.aget_card("sha256:x")
        await store.aput_tag("repo", "latest", "sha256:x")
        await store.aknown_digest("repo", "latest")
        await store.areplace_tags([("repo", "latest", "sha256:x")])
        await store.aevict_unreferenced_cards()

    asyncio.run(drive())
    assert calls == [
        "put_card",
        "get_card",
        "put_tag",
        "known_digest",
        "replace_tags",
        "evict_unreferenced_cards",
    ], "every async store call goes through the thread hop"


def test_eight_concurrent_writes_all_land(tmp_path: Path) -> None:
    """The shape the walk actually uses: concurrent WRITES, not reads.

    Asserted on the eight rows read back rather than on the absence of an
    exception, because a shared connection loses rows silently as well as
    loudly.
    """
    store = RegistryStore(tmp_path / "registry.db")
    store.create_schema()

    async def drive() -> None:
        await asyncio.gather(
            *[store.aput_card(f"sha256:{i}", {"card_html": f"<p>{i}</p>"}) for i in range(8)]
        )

    asyncio.run(drive())

    for i in range(8):
        card = store.get_card(f"sha256:{i}")
        assert card is not None, f"row {i} was lost"
        assert card["card_html"] == f"<p>{i}</p>"


def test_the_store_holds_a_path_and_never_a_connection() -> None:
    """A connection reused across threads is the defect this rules out."""
    store = RegistryStore(Path("/tmp/unused.db"))
    held = [value for value in vars(store).values() if isinstance(value, sqlite3.Connection)]
    assert held == []
    assert not hasattr(registry_store, "_CONNECTION")
