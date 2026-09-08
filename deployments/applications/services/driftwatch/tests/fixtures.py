"""A stand-in embark, wired through respx.

The HTTP boundary is the only thing faked: the real `EmbarkClient` builds the
requests and parses the responses, so a change to either shape fails a test
here rather than on the Jetson.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx

Scorer = Callable[[str, list[str]], list[float]]


def one_hot(texts: list[str]) -> dict[str, list[float]]:
    """Give every text its own axis, so cosine separates them perfectly."""
    width = len(texts)
    return {
        text: [1.0 if position == index else 0.0 for position in range(width)]
        for index, text in enumerate(texts)
    }


def install(
    respx_mock: Any,
    *,
    base_url: str,
    vectors: dict[str, list[float]],
    query_vectors: dict[str, list[float]] | None = None,
    scorer: Scorer | None = None,
) -> None:
    """Route `/v1/embeddings` and `/v1/rerank` at `base_url` to canned answers.

    Parameters
    ----------
    vectors :
        Text to vector, used when the request asks for `input_type=document`.
    query_vectors :
        The same for `input_type=query`. Defaults to `vectors`, which is what
        makes a query retrieve the document whose text it shares an axis with.
    scorer :
        Given the query and the candidate documents, the relevance score of
        each. Defaults to scoring candidates in the order they were sent.
    """
    documents = vectors
    queries = query_vectors if query_vectors is not None else vectors
    score = scorer if scorer is not None else _descending

    def embeddings(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        table = queries if body.get("input_type") == "query" else documents
        data = [
            {"object": "embedding", "index": index, "embedding": table[text]}
            for index, text in enumerate(body["input"])
        ]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": body["model"],
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            },
        )

    def rerank(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        candidates = list(body["documents"])
        scores = score(body["query"], candidates)
        ranked = sorted(enumerate(scores), key=lambda pair: -pair[1])
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "results": [{"index": index, "relevance_score": value} for index, value in ranked],
            },
        )

    respx_mock.post(f"{base_url}/v1/embeddings").mock(side_effect=embeddings)
    respx_mock.post(f"{base_url}/v1/rerank").mock(side_effect=rerank)


def _descending(query: str, candidates: list[str]) -> list[float]:  # noqa: ARG001
    return [float(len(candidates) - index) for index in range(len(candidates))]
