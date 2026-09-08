from __future__ import annotations

import json
from pathlib import Path

import pytest

from driftwatch import goldset


def write_rows(path: Path, rows: list[dict[str, str]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_corpus_is_deduplicated_across_both_columns(tmp_path: Path) -> None:
    path = write_rows(
        tmp_path / "goldset.jsonl",
        [
            {"query": "q1", "positive": "a", "negative": "b"},
            {"query": "q2", "positive": "b", "negative": "a"},
        ],
    )

    loaded = goldset.load(path)

    assert loaded.queries == ["q1", "q2"]
    assert loaded.documents == ["a", "b"]
    assert loaded.targets == [0, 1]


def test_document_order_follows_the_file(tmp_path: Path) -> None:
    """The baseline compares row by row, so the corpus order has to be stable."""
    rows = [{"query": f"q{n}", "positive": f"p{n}", "negative": f"n{n}"} for n in range(5)]
    path = write_rows(tmp_path / "goldset.jsonl", rows)

    first = goldset.load(path)
    second = goldset.load(path)

    assert first.documents == second.documents
    assert first.documents[:4] == ["p0", "n0", "p1", "n1"]


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "goldset.jsonl"
    path.write_text(
        json.dumps({"query": "q", "positive": "p", "negative": "n"}) + "\n\n\n",
        encoding="utf-8",
    )

    assert goldset.load(path).queries == ["q"]


def test_an_empty_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "goldset.jsonl"
    path.write_text("\n", encoding="utf-8")

    with pytest.raises(goldset.GoldsetError, match="holds no rows"):
        goldset.load(path)


def test_a_missing_field_names_the_line(tmp_path: Path) -> None:
    path = write_rows(tmp_path / "goldset.jsonl", [{"query": "q", "positive": "p"}])

    with pytest.raises(goldset.GoldsetError, match="goldset.jsonl:1"):
        goldset.load(path)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(goldset.GoldsetError, match="cannot read"):
        goldset.load(tmp_path / "absent.jsonl")


def test_the_shipped_goldset_loads() -> None:
    """The file services.tf renders into the job has to be one this can read."""
    shipped = Path(__file__).resolve().parents[1] / "goldset.jsonl"

    loaded = goldset.load(shipped)

    assert len(loaded.queries) == 30
    assert len(loaded.documents) == 60
    assert all(0 <= target < len(loaded.documents) for target in loaded.targets)


def test_the_shipped_goldset_carries_no_template_syntax() -> None:
    """services.tf folds this file into a Nomad template heredoc.

    Consul-template parses `{{ }}` and Nomad's HCL2 parses `${ }` and `%{ }`
    in what it is handed, so a row containing one of them would render as
    something other than itself -- or fail the job at deploy time, long after
    this file was edited.
    """
    shipped = (Path(__file__).resolve().parents[1] / "goldset.jsonl").read_text(encoding="utf-8")

    for token in ("{{", "${", "%{"):
        assert token not in shipped, f"goldset.jsonl carries {token!r}"


def write_rerank(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_rerank_rows_carry_the_answer_index(tmp_path: Path) -> None:
    path = write_rerank(
        tmp_path / "rerank.jsonl",
        [{"query": "q", "positive": "b", "candidates": ["a", "b", "c"]}],
    )

    cases = goldset.load_rerank(path)

    assert cases[0].query == "q"
    assert cases[0].candidates == ["a", "b", "c"]
    assert cases[0].target == 1


def test_an_answer_outside_its_own_pool_is_refused(tmp_path: Path) -> None:
    """The pool is what gets sent; an answer that is not in it can never be
    ranked, so every run would silently score that row as a miss."""
    path = write_rerank(
        tmp_path / "rerank.jsonl",
        [{"query": "q", "positive": "z", "candidates": ["a", "b"]}],
    )

    with pytest.raises(goldset.GoldsetError, match="not in its own candidate pool"):
        goldset.load_rerank(path)


def test_a_missing_rerank_field_names_the_line(tmp_path: Path) -> None:
    path = write_rerank(tmp_path / "rerank.jsonl", [{"query": "q", "positive": "a"}])

    with pytest.raises(goldset.GoldsetError, match="rerank.jsonl:1"):
        goldset.load_rerank(path)


def test_an_empty_rerank_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "rerank.jsonl"
    path.write_text("\n", encoding="utf-8")

    with pytest.raises(goldset.GoldsetError, match="holds no rows"):
        goldset.load_rerank(path)


def test_the_shipped_rerank_goldset_loads() -> None:
    shipped = Path(__file__).resolve().parents[1] / "rerank-goldset.jsonl"

    cases = goldset.load_rerank(shipped)

    assert len(cases) == 30
    assert all(len(case.candidates) == 10 for case in cases)
    assert all(len(set(case.candidates)) == 10 for case in cases)
    # The answer sits at a different index across the file. If it were always
    # at 0, an off-by-one in the rank arithmetic would score a perfect run.
    assert len({case.target for case in cases}) == 10


def test_the_rerank_pool_holds_the_hard_negative_for_its_query() -> None:
    """Each pool carries the adjacent, plausible, wrong answer embark's gold set
    hand-authored for that query. That is the input a cross-encoder exists to
    reject, and what a pool of other rows' answers does not supply."""
    root = Path(__file__).resolve().parents[1]
    triplets = {
        json.loads(line)["query"]: json.loads(line)
        for line in (root / "goldset.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    cases = {case.query: case for case in goldset.load_rerank(root / "rerank-goldset.jsonl")}

    assert set(cases) == set(triplets)
    for query, case in cases.items():
        assert triplets[query]["positive"] in case.candidates
        assert triplets[query]["negative"] in case.candidates


def test_the_shipped_rerank_goldset_carries_no_template_syntax() -> None:
    """services.tf folds this file into a Nomad template heredoc, same as the
    embedding gold set."""
    shipped = (Path(__file__).resolve().parents[1] / "rerank-goldset.jsonl").read_text(
        encoding="utf-8"
    )

    for token in ("{{", "${", "%{"):
        assert token not in shipped, f"rerank-goldset.jsonl carries {token!r}"
