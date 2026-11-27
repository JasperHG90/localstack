"""Boot ov-postgres 0.7.0 on OpenViking 0.5.6 over a table 0.6.0 seeded.

argv[1] is JSON: dsn, schema, dim, dirs, workspace. Prints one JSON report.
1. writes the files the rows index into a local VikingFS (untimed),
2. times create_collection, the reconcile a first boot runs,
3. runs ov-ext 0.8.0's maintenance pass (the md5 backfill) while a vector
   query and an event-loop lag probe run beside it in the same process.
"""

import asyncio
import json
import statistics
import sys
import time
from types import SimpleNamespace


def pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))], 4) if xs else None


async def write_files(viking_fs, dirs):
    from openviking.server.identity import RequestContext, Role, UserIdentifier

    ctx = RequestContext(user=UserIdentifier("lab", "default"), role=Role.ROOT)
    body = ("# Note\n\n" + "Some markdown text for hashing. " * 60).encode()

    async def one(d):
        base = f"viking://resources/spike/d{d:05d}"
        for j in range(3):
            await viking_fs.write_file_bytes(f"{base}/f{j}.md", body + str(d * 3 + j).encode(), ctx=ctx)
        await viking_fs.write_file(f"{base}/.abstract.md", f"Directory {d}, three notes.", ctx=ctx)
        await viking_fs.write_file(f"{base}/.overview.md", f"## Files\n\n- f0.md\n- f1.md\n- f2.md\n({d})\n", ctx=ctx)

    for start in range(0, dirs, 100):
        await asyncio.gather(*(one(d) for d in range(start, min(dirs, start + 100))))


async def backfill(adapter, viking_fs, dim):
    import random

    from ov_ext import maintenance

    rng = random.Random(3)
    qv = [rng.uniform(-1, 1) for _ in range(dim)]
    lat = {"base": [], "during": []}
    lag = {"base": [], "during": []}
    phase = ["base"]
    stop = asyncio.Event()

    async def query_probe():
        while not stop.is_set():
            t = time.monotonic()
            await asyncio.to_thread(adapter.query, query_vector=qv, limit=10)
            lat[phase[0]].append(time.monotonic() - t)
            await asyncio.sleep(0.2)

    async def lag_probe():
        while not stop.is_set():
            t = time.monotonic()
            await asyncio.sleep(0.05)
            lag[phase[0]].append(time.monotonic() - t - 0.05)

    probes = [asyncio.create_task(query_probe()), asyncio.create_task(lag_probe())]
    await asyncio.sleep(15)
    phase[0] = "during"
    t0 = time.monotonic()
    filled = await maintenance.run_once(SimpleNamespace(_shared_adapter=adapter), viking_fs)
    elapsed = time.monotonic() - t0
    stop.set()
    await asyncio.gather(*probes)
    out = {"backfill_filled": filled, "backfill_s": round(elapsed, 1)}
    for k in ("base", "during"):
        out[f"query_{k}"] = {"n": len(lat[k]), "p50": pct(lat[k], 0.5), "p95": pct(lat[k], 0.95), "max": pct(lat[k], 1.0)}
        out[f"loop_lag_{k}"] = {"p99": pct(lag[k], 0.99), "max": pct(lag[k], 1.0)}
    return out


def main():
    args = json.loads(sys.argv[1])
    dim, dirs = int(args["dim"]), int(args["dirs"])
    from openviking.storage.collection_schemas import CollectionSchemas
    from openviking.storage.viking_fs import VikingFS
    from openviking.utils.agfs_utils import RagfsBindingConfig, create_agfs_client
    from openviking_cli.utils.config.agfs_config import AGFSConfig
    from openviking_cli.utils.config.vectordb_config import VectorDBBackendConfig

    from ov_postgres.adapter import PgVectorCollectionAdapter
    from ov_postgres.md5_backfill import BATCH_SIZE

    viking_fs = VikingFS(agfs=create_agfs_client(RagfsBindingConfig(agfs=AGFSConfig(backend="local", path=args["workspace"]))))
    t = time.monotonic()
    asyncio.run(write_files(viking_fs, dirs))
    report = {"files_written_s": round(time.monotonic() - t, 1)}

    adapter = PgVectorCollectionAdapter.from_config(
        VectorDBBackendConfig(
            backend="ov_postgres.adapter.PgVectorCollectionAdapter",
            name="context",
            index_name="default",
            distance_metric="cosine",
            custom_params={"dsn": args["dsn"], "schema": args["schema"]},
        )
    )
    t = time.monotonic()
    created = adapter.create_collection(
        "context", CollectionSchemas.context_collection("context", dim),
        distance="cosine", sparse_weight=0.0, index_name="default",
    )
    report["reconcile_s"] = round(time.monotonic() - t, 2)
    report["created"] = created
    adapter.get_collection()  # raises if the reconcile failed closed
    inner = adapter._pg_collection
    report["backfill_pending_after_reconcile"] = inner.md5_backfill_pending()
    report["rows"] = adapter.count()
    report["batch_size"] = BATCH_SIZE
    report.update(asyncio.run(backfill(adapter, viking_fs, dim)))
    report["batches"] = -(-report["rows"] // BATCH_SIZE)
    report["s_per_batch"] = round(report["backfill_s"] / report["batches"], 3)
    report["backfill_pending_after"] = inner.md5_backfill_pending()
    adapter.close()
    print("REPORT " + json.dumps(report))


if __name__ == "__main__":
    main()
