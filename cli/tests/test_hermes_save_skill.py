"""The save-to-openviking skill and the SOUL.md line that sends Hermes to it.

Hermes picks the skill from `skills_list` because SOUL.md points at it
(spike:ov-save-skill/9). These tests read both files from the repo and pin the
instructions the plan relies on, so an edit that drops one fails here rather
than in a live chat.
"""

import re
from pathlib import Path

import yaml

# cli/tests/<this file> -> repo root is two up.
REPO_ROOT = Path(__file__).resolve().parents[2]
HERMES = REPO_ROOT / "deployments" / "applications" / "services" / "hermes"
SKILL = HERMES / "skills" / "productivity" / "save-to-openviking" / "SKILL.md"

RESOURCES = "viking://user/jasper/resources/"
MAP_URI = RESOURCES + ".map.md"
SEED_ROOTS = ["projects/<repo>/", "leo/", "blogs/<source>/", "clips/<slug>/"]


def split_skill() -> tuple[dict[str, object], str]:
    match = re.match(r"---\n(.*?)\n---\n(.*)", SKILL.read_text(), re.S)
    assert match, "SKILL.md needs a front matter block"
    front = yaml.safe_load(match.group(1))
    assert isinstance(front, dict)
    return front, match.group(2)


def body() -> str:
    return split_skill()[1]


def prose() -> str:
    """The body with line breaks folded, so a phrase may wrap."""
    return " ".join(body().split())


def seed_block() -> str:
    match = re.search(r"^## Seed map\n(.*?)(?=^## |\Z)", body(), re.S | re.M)
    assert match, "the skill holds the seed map under '## Seed map'"
    return match.group(1)


def test_front_matter_loads_in_hermes() -> None:
    front, _ = split_skill()

    assert front["name"] == "save-to-openviking"
    assert isinstance(front["description"], str) and "OpenViking" in front["description"]
    metadata = front["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["hermes"]["category"] == "productivity"
    assert "## When to Use" in body()


def test_reads_the_map_before_saving() -> None:
    text = body()
    read = f'viking_read(uri="{MAP_URI}", level="full")'

    assert read in text
    assert text.index(read) < text.index("viking_add_resource(")


def test_asks_when_no_place_was_given_and_waits() -> None:
    text = prose()

    assert "If the operator named a place" in text
    assert "save there without asking" in text
    assert "ask the operator to confirm or name another" in text
    assert "Do not save before the answer." in text


def test_appends_a_new_root_to_the_map_before_the_save() -> None:
    text = prose()

    assert f'viking_write(uri="{MAP_URI}", mode="append"' in text
    assert 'owner "hand saves"' in text
    assert "ask them for a one-line description" in text
    assert "before the save" in text


def test_falls_back_to_exactly_one_list_of_the_resources_root() -> None:
    browses = re.findall(r"viking_browse\([^)]*\)", body())

    assert browses == [f'viking_browse(action="list", path="{RESOURCES}")']
    assert "tree" not in body()


def test_seeds_the_four_roots() -> None:
    seed = seed_block()
    # Unindented, so the model does not copy leading spaces into the map.
    roots = re.findall(r"^- (\S+/):", seed, re.M)

    assert roots == SEED_ROOTS
    assert f'viking_write(uri="{MAP_URI}", mode="create"' in body()


def test_writes_the_map_only_with_viking_write() -> None:
    text = body()

    # Spike 9's draft wrote the map with curl through the terminal.
    assert not re.search(r"curl\s+-|OPENVIKING_ENDPOINT|content/write", text)
    for call in re.findall(r"viking_add_resource\([^)]*\)", text):
        assert ".map.md" not in call


def folder_references(text: str) -> list[str]:
    under_root = re.findall(re.escape(RESOURCES) + r"([^\s\"`)]+/)", text)
    relative = re.findall(r"`((?:[\w<>-]+/)+)`", text)
    return under_root + relative


def test_names_no_folder_beyond_the_seed_roots() -> None:
    placeholder = re.compile(r"<[\w-]+>")
    seed_roots = {r.split("/")[0] for r in SEED_ROOTS}
    refs = folder_references(body())
    assert refs

    for ref in refs:
        root, *rest = ref.rstrip("/").split("/")
        assert root in seed_roots or placeholder.fullmatch(root), ref
        assert all(placeholder.fullmatch(part) for part in rest), ref


def test_saves_a_voice_transcript_as_a_dated_markdown_file() -> None:
    text = prose()

    assert "transcript" in text
    assert "`YYYY-MM-DD-<short-title>.md`" in text
    assert re.search(r"viking_add_resource\(url=<that path>, parent=", text)


def test_sends_sync_owned_roots_only_after_the_operator_names_them() -> None:
    text = prose()

    assert "`projects/` and `leo/` are written by syncs" in text
    assert "confirms that root by name" in text


def test_trusts_the_returned_uri() -> None:
    text = prose()

    # In spike:ov-save-skill/9 every run that saved went on to check the save
    # with curl through the terminal.
    assert "root_uri" in text
    assert "Do not check it by hand: no curl, no terminal" in text


def test_soul_points_at_the_skill() -> None:
    soul = (HERMES / "SOUL.md").read_text()
    section = re.search(r"^# OpenViking Integration\n(.*?)(?=^# )", soul, re.S | re.M)
    assert section
    text = section.group(1)

    assert "load the `save-to-openviking` skill first and follow it" in text
    assert "If the operator did not say where, ask before saving." in text
    assert "| `viking_write(uri, content, mode)` | `uri`, `content`, `mode` |" in text
    assert "Do not shell out to curl." in text
    assert "Seven tools" in text
