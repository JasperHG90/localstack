"""Seed openviking_v2.ov_context with ov-postgres 0.6.0 on OpenViking 0.4.17.1.

Run with the old-stack interpreter. argv[1] is JSON: dsn, schema, rows, dim.
Layout per directory: an L0 row, an L1 row and three L2 files, account "lab".
"""

import json
import random
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class _Embedding:
    dimension: int


@dataclass(frozen=True)
class _Config:
    embedding: _Embedding


def main() -> None:
    args = json.loads(sys.argv[1])
    dim, rows = int(args["dim"]), int(args["rows"])
    from openviking.storage.collection_schemas import CollectionSchemas
    from openviking.storage.vectordb_adapters import base
    from openviking_cli.utils.config.vectordb_config import VectorDBBackendConfig

    from ov_postgres.adapter import PgVectorCollectionAdapter

    base.get_openviking_config = lambda: _Config(_Embedding(dim))
    adapter = PgVectorCollectionAdapter.from_config(
        VectorDBBackendConfig(
            backend="ov_postgres.adapter.PgVectorCollectionAdapter",
            name="context",
            index_name="default",
            distance_metric="cosine",
            custom_params={"dsn": args["dsn"], "schema": args["schema"]},
        )
    )
    adapter.create_collection(
        "context",
        CollectionSchemas.context_collection("context", dim),
        distance="cosine",
        sparse_weight=0.0,
        index_name="default",
    )
    rng = random.Random(7)
    text = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do ".split()
    t0 = time.monotonic()
    batch = []
    n = 0
    d = 0
    while n < rows:
        base_uri = f"viking://resources/spike/d{d:05d}"
        recs = [(f"d{d}-L0", base_uri, 0), (f"d{d}-L1", base_uri, 1)]
        recs += [(f"d{d}-f{j}", f"{base_uri}/f{j}.md", 2) for j in range(3)]
        for rid, uri, level in recs:
            if n >= rows:
                break
            batch.append(
                {
                    "id": rid,
                    "uri": uri,
                    "account_id": "lab",
                    "owner_user_id": "jasper",
                    "level": level,
                    "context_type": "resource",
                    "name": uri.rsplit("/", 1)[-1],
                    "abstract": " ".join(rng.choice(text) for _ in range(60)),
                    "vector": [rng.uniform(-1, 1) for _ in range(dim)],
                }
            )
            n += 1
            if len(batch) == 500:
                adapter.upsert(batch)
                batch = []
        d += 1
    if batch:
        adapter.upsert(batch)
    count = adapter.count()
    adapter.close()
    print(json.dumps({"seeded": count, "dirs": d, "seed_s": round(time.monotonic() - t0, 1)}))


if __name__ == "__main__":
    main()
