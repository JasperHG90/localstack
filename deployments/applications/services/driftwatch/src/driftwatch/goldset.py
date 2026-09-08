"""The canary set: fixed queries, each with one document that answers it.

The file is `{"query": ..., "positive": ..., "negative": ...}` per line, the
shape `embark_forge.goldset` already reads, so the set here and the one
embark's own quantization gate uses are the same artifact in the same format.

The corpus every query is ranked against is the deduplicated union of both
document columns. A negative is therefore not merely ignored: it is a
plausible distractor another query's positive has to outrank.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class GoldsetError(ValueError):
    """The goldset file is missing, empty, or a row is malformed."""


@dataclass(frozen=True)
class Goldset:
    """One canary set, already flattened into the arrays a run needs.

    Attributes
    ----------
    queries :
        Query text, in file order.
    documents :
        The deduplicated corpus, in first-seen order. Order is stable across
        runs because it comes from the file, which is what lets a baseline
        recorded on one run be compared position by position with the next.
    targets :
        For each query, the index in `documents` of the document that answers
        it.
    """

    queries: list[str]
    documents: list[str]
    targets: list[int]


def load(path: Path) -> Goldset:
    """Read and flatten the goldset at `path`.

    Raises
    ------
    GoldsetError
        If the file cannot be read, holds no rows, or a row is missing one of
        the three fields.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as err:
        raise GoldsetError(f"cannot read goldset {path}: {err}") from err

    queries: list[str] = []
    documents: list[str] = []
    index_of: dict[str, int] = {}
    targets: list[int] = []

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            raise GoldsetError(f"{path}:{number} is not JSON: {err}") from err
        try:
            query = str(row["query"])
            positive = str(row["positive"])
            negative = str(row["negative"])
        except (KeyError, TypeError) as err:
            raise GoldsetError(f"{path}:{number} needs query, positive and negative") from err

        for text in (positive, negative):
            if text not in index_of:
                index_of[text] = len(documents)
                documents.append(text)
        queries.append(query)
        targets.append(index_of[positive])

    if not queries:
        raise GoldsetError(f"{path} holds no rows")
    return Goldset(queries=queries, documents=documents, targets=targets)


@dataclass(frozen=True)
class RerankCase:
    """One query, its answer, and the fixed pool the reranker scores.

    Attributes
    ----------
    query :
        The question.
    candidates :
        Ten documents, in the order they are sent. The answer sits at a
        different index in every row of the shipped file, so an off-by-one in
        the rank arithmetic cannot score a perfect run.
    target :
        Index in `candidates` of the document that answers the query.
    """

    query: str
    candidates: list[str]
    target: int


def load_rerank(path: Path) -> list[RerankCase]:
    """Read the rerank gold set at `path`.

    The pool is fixed in the file rather than taken from the embedding stage,
    which is the whole point of this set: a reranker scored on whatever vector
    search shortlisted moves when the EMBEDDER drifts, so the two stages
    cannot say which half regressed. Here the ten documents are the same ten
    every run.

    Raises
    ------
    GoldsetError
        If the file cannot be read, holds no rows, a row is missing a field,
        or a row's answer is absent from its own candidate pool.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as err:
        raise GoldsetError(f"cannot read rerank goldset {path}: {err}") from err

    cases: list[RerankCase] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            raise GoldsetError(f"{path}:{number} is not JSON: {err}") from err
        try:
            query = str(row["query"])
            positive = str(row["positive"])
            candidates = [str(text) for text in row["candidates"]]
        except (KeyError, TypeError) as err:
            raise GoldsetError(f"{path}:{number} needs query, positive and candidates") from err
        if positive not in candidates:
            raise GoldsetError(f"{path}:{number} answer is not in its own candidate pool")
        cases.append(
            RerankCase(query=query, candidates=candidates, target=candidates.index(positive))
        )

    if not cases:
        raise GoldsetError(f"{path} holds no rows")
    return cases
