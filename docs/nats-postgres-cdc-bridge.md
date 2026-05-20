# PostgreSQL CDC → NATS bridge

Capture row-level changes from PostgreSQL tables and publish them as NATS JetStream messages — without modifying the application that writes to the database. Uses PostgreSQL's built-in `LISTEN/NOTIFY` mechanism as the change-data-capture (CDC) source.

## Why

Services like Memex write to PostgreSQL but don't emit events. Other services (ingestion workers, reflection agents, dashboards) want to react when data changes. Instead of polling or patching the application, we tap PostgreSQL's trigger system and bridge notifications into NATS, where any number of consumers can subscribe.

```
App writes to Postgres
  → PG trigger fires NOTIFY with row metadata
    → Python bridge receives notification (push, not poll)
      → Publishes to NATS JetStream subject
        → Durable consumers react
```

## Prerequisites

- PostgreSQL database accessible from the bridge service
- NATS + JetStream running (`nats://nats.service.localstack.consul:4222`)
- Python 3.12+ with `psycopg[binary]` and `nats-py`

---

## 1. PostgreSQL trigger

A single PL/pgSQL function works across multiple tables. Install it once per database.

```sql
CREATE OR REPLACE FUNCTION notify_change() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify(
        TG_ARGV[0],
        json_build_object(
            'op',        TG_OP,
            'id',        NEW.id,
            'table',     TG_TABLE_NAME,
            'schema',    TG_TABLE_SCHEMA,
            'timestamp', current_timestamp,
            'db_user',   current_user
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Payload fields

| Field | Source | Notes |
|---|---|---|
| `op` | `TG_OP` | `INSERT`, `UPDATE`, or `DELETE` |
| `id` | `NEW.id` | Primary key of the affected row (adjust column name to match schema) |
| `table` | `TG_TABLE_NAME` | Table the trigger fired on |
| `schema` | `TG_TABLE_SCHEMA` | Schema name (e.g. `public`) |
| `timestamp` | `current_timestamp` | When the trigger fired |
| `db_user` | `current_user` | DB role that made the write |

You can add application-specific columns from `NEW.*` (e.g. `NEW.title`, `NEW.vault_id`) as long as the total payload stays under PostgreSQL's **8 KB `pg_notify` limit**. Keep payloads minimal — downstream consumers should fetch the full record by `id` if they need more.

For `UPDATE` triggers, `OLD.*` gives you the previous row values if you need to detect which columns changed.

### Other available trigger variables

| Variable | Description |
|---|---|
| `NEW.*` / `OLD.*` | New/previous row (availability depends on `INSERT`/`UPDATE`/`DELETE`) |
| `TG_WHEN` | `BEFORE` or `AFTER` |
| `TG_NARGS` | Number of arguments passed to the trigger |
| `TG_ARGV[]` | String arguments from the trigger definition |
| `session_user` | Original authenticated role (vs `current_user` which may be changed by `SET ROLE`) |

### Attach to tables

The channel name is passed as a trigger argument (`TG_ARGV[0]`), so you can reuse the same function with different channel names per table.

```sql
-- Example: Memex tables (adjust table names to match actual schema)
CREATE TRIGGER trg_notes_notify
    AFTER INSERT OR UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION notify_change('memex_notes');

CREATE TRIGGER trg_memories_notify
    AFTER INSERT OR UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION notify_change('memex_memories');
```

To also capture deletes, add `OR DELETE` and handle `OLD` instead of `NEW`:

```sql
CREATE OR REPLACE FUNCTION notify_change() RETURNS trigger AS $$
DECLARE
    row_id text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        row_id := OLD.id::text;
    ELSE
        row_id := NEW.id::text;
    END IF;

    PERFORM pg_notify(
        TG_ARGV[0],
        json_build_object(
            'op',        TG_OP,
            'id',        row_id,
            'table',     TG_TABLE_NAME,
            'schema',    TG_TABLE_SCHEMA,
            'timestamp', current_timestamp,
            'db_user',   current_user
        )::text
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 2. Python bridge service

The bridge holds two long-lived connections — one to PostgreSQL (receives `NOTIFY`), one to NATS (publishes to JetStream). Both are push-based: no polling loops.

```python
"""pg-nats-bridge: PostgreSQL LISTEN/NOTIFY → NATS JetStream."""

import asyncio
import json
import logging

import nats
import psycopg

logger = logging.getLogger("pg-nats-bridge")

# Channels to listen on → NATS subject prefix mapping
CHANNELS = {
    "memex_notes": "memex.events.notes",
    "memex_memories": "memex.events.memories",
}


async def bridge(pg_dsn: str, nats_url: str, stream: str) -> None:
    # --- NATS ---
    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    await js.add_stream(
        name=stream,
        subjects=["memex.events.>"],
        storage="file",
        max_age=7 * 24 * 3600,  # 7-day retention
    )
    logger.info("NATS stream '%s' ready", stream)

    # --- PostgreSQL ---
    pg = await psycopg.AsyncConnection.connect(pg_dsn, autocommit=True)
    for channel in CHANNELS:
        await pg.execute(f"LISTEN {channel}")
        logger.info("Listening on PG channel '%s'", channel)

    # --- Event loop ---
    # pg.notifies() is an async generator that yields only when a NOTIFY
    # arrives — it blocks on the PG socket, zero CPU while idle.
    async for notify in pg.notifies():
        subject = CHANNELS.get(notify.channel, f"memex.events.{notify.channel}")
        payload = notify.payload.encode() if notify.payload else b"{}"

        await js.publish(subject, payload)
        logger.info("→ %s: %s", subject, notify.payload)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-dsn", required=True, help="PostgreSQL connection string")
    parser.add_argument(
        "--nats-url",
        default="nats://nats.service.localstack.consul:4222",
    )
    parser.add_argument("--stream", default="memex-events")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    asyncio.run(bridge(args.pg_dsn, args.nats_url, args.stream))


if __name__ == "__main__":
    main()
```

### Dependencies

```
# pyproject.toml or requirements.txt
psycopg[binary] >= 3.1
nats-py >= 2.7
```

---

## 3. Nomad job

Deploy the bridge as a Nomad service job on the same node as NATS (radxa-dragon-q6a). PostgreSQL credentials come from Vault.

```hcl
job "pg-nats-bridge" {
  datacenters = ["dc1"]
  type        = "service"

  constraint {
    attribute = "${attr.unique.hostname}"
    value     = "radxa-dragon-q6a"
  }

  group "bridge" {
    count = 1

    restart {
      attempts = 5
      interval = "5m"
      delay    = "15s"
      mode     = "delay"
    }

    task "bridge" {
      driver = "podman"

      config {
        # Build and push to the private registry, or use a generic python image
        # with the script mounted via artifact or template.
        image   = "registry.localstack:5000/pg-nats-bridge:latest"
        command = "python"
        args    = [
          "bridge.py",
          "--pg-dsn", "${PG_DSN}",
          "--nats-url", "${NATS_URL}",
          "--stream", "memex-events",
        ]
      }

      vault {
        policies = ["memex-reader"]
      }

      template {
        data = <<EOF
{{ with secret "kv/data/infrastructure/postgres" }}
PG_DSN=postgresql://{{ .Data.data.memex_role }}:{{ .Data.data.memex_password }}@192.168.2.30:5432/memex
{{ end }}
NATS_URL=nats://nats.service.localstack.consul:4222
EOF
        destination = "secrets/file.env"
        env         = true
      }

      resources {
        cpu    = 100
        memory = 128
      }
    }
  }
}
```

Resource footprint is tiny — the bridge is idle most of the time, just holding two open sockets.

---

## 4. Consuming events

Once the bridge is running, any service can subscribe to the JetStream stream. See [nats.md](nats.md) for the full consumer patterns.

### Quick example: react to new Memex notes

```python
import asyncio
import json

import nats


async def main():
    nc = await nats.connect("nats://nats.service.localstack.consul:4222")
    js = nc.jetstream()

    sub = await js.pull_subscribe(
        "memex.events.notes",
        durable="note-reactor",
        stream="memex-events",
    )

    while True:
        try:
            msgs = await sub.fetch(batch=10, timeout=30)
        except nats.errors.TimeoutError:
            continue
        for msg in msgs:
            event = json.loads(msg.data)
            print(f"{event['op']} on {event['table']} id={event['id']}")
            # Fetch full record from Memex API or Postgres if needed
            await msg.ack()


asyncio.run(main())
```

---

## 5. Limitations and trade-offs

| Concern | Detail |
|---|---|
| **8 KB payload limit** | `pg_notify` payloads are capped at 8 KB. Keep trigger payloads minimal; fetch full records downstream. |
| **No durability in PG layer** | `NOTIFY` is in-memory. If the bridge is down when a write happens, that notification is lost. JetStream durability only applies *after* the message reaches NATS. |
| **Reconnection gap** | If the bridge's PG connection drops, notifications during the gap are missed. For critical use cases, supplement with a periodic reconciliation query. |
| **Single-node JetStream** | No replication. If radxa-dragon-q6a is down, the stream is unavailable. Acceptable for homelab. |
| **Trigger overhead** | `pg_notify` is lightweight but not free. Avoid attaching triggers to high-write-throughput tables unless you need the events. |

For guaranteed CDC with no gaps, you'd need PostgreSQL logical replication (`wal2json` or `pgoutput`), which is significantly more complex. `LISTEN/NOTIFY` is the right trade-off for a homelab where occasional missed events during restarts are acceptable.

---

## See also

- [NATS + JetStream usage](nats.md) — CLI, Python, conventions
- [PostgreSQL NOTIFY docs](https://www.postgresql.org/docs/current/sql-notify.html)
- [psycopg async notifications](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
- NATS job spec — `deployments/infrastructure/services/nats.hcl`