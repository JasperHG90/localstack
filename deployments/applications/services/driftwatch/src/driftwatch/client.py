"""The two embark calls one evaluation run makes.

embark is dialed directly rather than through Bifrost, deliberately. The
gateway drops `input_type`, and that field selects the model's query prefix
against its document prefix -- embedding a query with the document prefix
costs recall on a bi-encoder trained with asymmetric prefixes, and nothing
reports it. Measuring the model means talking to the model.

The gateway path is not unmeasured as a result: OpenViking's own
`openviking_embedding_call_duration_seconds` is the same call through Bifrost,
and the gap between the two dashboards is the gateway's contribution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np
from numpy.typing import NDArray


class EmbarkError(RuntimeError):
    """embark refused a request or answered in a shape this client cannot read."""


@dataclass(frozen=True)
class RerankHit:
    """One reranked candidate.

    Attributes
    ----------
    index :
        Position in the `documents` list that was sent, not a corpus index.
    score :
        The relevance score embark assigned.
    """

    index: int
    score: float


class EmbarkClient:
    """A thin OpenAI-shaped client over embark's two model routes."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EmbarkClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def embed(self, texts: list[str], *, model: str, input_type: str) -> NDArray[np.float32]:
        """Embed `texts`, returning one row per input in request order.

        Parameters
        ----------
        input_type :
            ``"query"`` or ``"document"``. embark uses it to pick the prefix
            the model was trained with; the two are not interchangeable.

        Returns
        -------
        NDArray[np.float32]
            Shape ``(len(texts), width)``.

        Raises
        ------
        EmbarkError
            On a non-2xx response, or when the response holds a different
            number of vectors than were asked for.
        """
        body: dict[str, Any] = {"model": model, "input": texts, "input_type": input_type}
        data = self._post("/v1/embeddings", body).get("data", [])
        if len(data) != len(texts):
            raise EmbarkError(f"asked for {len(texts)} vectors, got {len(data)}")
        # embark answers in request order and also stamps an index. Sorting on
        # the index rather than trusting the order costs nothing and survives a
        # gateway that reorders.
        rows = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors = np.asarray([row["embedding"] for row in rows], dtype=np.float32)
        if vectors.ndim != 2:
            raise EmbarkError(f"expected a matrix of vectors, got shape {vectors.shape}")
        return vectors

    def rerank(self, query: str, documents: list[str], *, model: str) -> list[RerankHit]:
        """Score `documents` against `query`, best first.

        `top_n` is left unset so every candidate comes back: the run needs the
        rank of one specific document, which a truncated response can hide.
        """
        body: dict[str, Any] = {"model": model, "query": query, "documents": documents}
        results = self._post("/v1/rerank", body).get("results", [])
        return [
            RerankHit(index=int(item["index"]), score=float(item["relevance_score"]))
            for item in results
        ]

    def _post(self, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=dict(body))
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload
        except httpx.HTTPStatusError as err:
            raise EmbarkError(
                f"{path} answered {err.response.status_code}: {err.response.text[:200]}"
            ) from err
        except (httpx.HTTPError, ValueError) as err:
            raise EmbarkError(f"{path} failed: {err}") from err
