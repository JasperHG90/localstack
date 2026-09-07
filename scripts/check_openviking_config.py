#!/usr/bin/env python3
"""Assert the parts of OpenViking's config that must not drift.

The config is `services/openviking/ov.conf.json`, a real JSON document that
Terraform round-trips into the jobspec. These fifteen settings each fail in a way a
healthy-looking service would hide:

    dimension        a wrong value corrupts the collection silently
    backend          the vectordb one, not agfs's, which is declared first
    custom_params    ov-postgres forbids unknown keys; a typo fails at startup
    rerank target    pointing past Bifrost loses gateway governance
    auth_mode        anything but oidc means Vault stopped being the identity
    oidc.issuer      a wrong value starts fine and 401s every request after
    oidc.audience    must equal the identity-token role's client_id
    oidc.account_id  read from the entity-name claim; `sub` is the entity UUID
    oidc.user_id     the same claim, because account id equals user id here
    oidc.fallback    null, or an unmapped caller pools into the real `default`
    vlm model        one that cannot see embeds an error string per image
    vlm api_base     past Bifrost loses gateway governance, as rerank does
    metrics          off, /metrics 404s and the Prometheus job scrapes nothing
    traces           off or unpointed, and Tempo receives nothing, silently
    query_planner    past Bifrost, or unset and it silently falls back to vlm

Two settings this file used to assert are gone, and their mutants with them.
Under `oidc` the auth plugin never consults `server.root_api_key`, so its
absence no longer stops the server starting. Nothing on the request path issues
or verifies a per-user API key either, so `encryption.api_key_hashing` governs
nothing reachable. The `auth_mode` assertion above is what keeps both safe: a
flip back to `api_key` is caught here before either matters again.

Reading the document as JSON rather than as text is what makes the backend
check honest: `agfs` declares its own `backend` first, so a textual search finds
the blob store's value and passes whatever the vector store is set to.

This is the STATIC half. It does not measure whether the service accepts a key,
whether one user's data is isolated from another's, or whether any call reaches
embark. Those need a deployed service and no gate here runs one.

Run with `--self-test` to check the checker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CONFIG = Path("deployments/applications/services/openviking/ov.conf.json")

EXPECTED_DIMENSION = 768
EXPECTED_AUTH_MODE = "oidc"
EXPECTED_BACKEND = "ov_postgres.adapter.PgVectorCollectionAdapter"

# Vault appends `/v1/<namespace>/identity/oidc` to whatever `identity/oidc/config`
# holds, and refuses an issuer carrying a path, so Terraform writes the bare host
# and this is the string that comes back in `iss`. Upstream compares it exactly.
EXPECTED_ISSUER = "https://vault.lab.orangecluster.nl/v1/identity/oidc"

# The identity-token role's `client_id`, set explicitly in oidc.tf so this stays
# a literal both sides can be checked against.
EXPECTED_AUDIENCE = "openviking"

# Vault reserves `sub` for the entity UUID, so the entity NAME has to travel as
# a claim the role's template adds.
OV_ACCOUNT_CLAIM = "ov_account"
BIFROST_PORT = "8080"
# Tempo's OTLP gRPC receiver, on ubuntu beside Prometheus and Loki.
TEMPO_OTLP = "192.168.2.47:4317"

# Models MEASURED to accept an image through Bifrost, by POSTing a PNG to
# /v1/chat/completions and reading the answer back. Being in Bifrost's catalog
# is not enough and is the trap this set exists to close: glm-5.3, glm-5.2,
# glm-5.1 and both deepseek-v4 variants all answer text and refuse an image
# with "this model does not support image input".
#
# A model that cannot see returns HTTP 200 for the ingest anyway. OpenViking
# catches the error and returns {"summary": "Image summary generation failed"}
# (parse/parsers/media/utils.py:325), which is then embedded as the image's
# content, so every image lands with the same junk vector and nothing reports
# a failure. Add a model here only after measuring it.
VISION_MODELS = frozenset(
    {
        "ollama/glm-5.3-flash",
        "ollama/gemma4:31b",
        "ollama/kimi-k3",
        "ollama/minimax-m3",
        "ollama/qwen3.5:397b",
    }
)

# Every field PgVectorParams declares at the pinned tag, plus `schema`, which
# is `db_schema`'s alias. Read off the model rather than from prose: a key this
# set omits is reported as forbidden while ov-postgres accepts it.
ALLOWED_CUSTOM_PARAMS = frozenset(
    {
        "dsn",
        "schema",
        "db_schema",
        "table_prefix",
        "index_method",
        "index_options",
        "create_extension",
        "iterative_scan",
        "distance",
        "keyword_fields",
        "text_search_config",
        "tz_policy",
        "min_pool_size",
        "max_pool_size",
        "connect_timeout",
        "application_name",
    }
)


def failures(config: dict[str, Any]) -> list[str]:
    found: list[str] = []

    vectordb = config.get("storage", {}).get("vectordb", {})
    server = config.get("server", {})

    dimension = config.get("embedding", {}).get("dense", {}).get("dimension")
    if dimension != EXPECTED_DIMENSION:
        found.append(
            f"embedding.dense.dimension is {dimension!r}, expected "
            f"{EXPECTED_DIMENSION}. Measured against embark through Bifrost; a "
            "wrong value corrupts the collection without erroring."
        )

    backend = vectordb.get("backend")
    if backend != EXPECTED_BACKEND:
        found.append(
            f"storage.vectordb.backend is {backend!r}, expected {EXPECTED_BACKEND!r}"
        )

    unknown = set(vectordb.get("custom_params", {})) - ALLOWED_CUSTOM_PARAMS
    if unknown:
        found.append(
            f"custom_params carries {sorted(unknown)}, which ov-postgres forbids "
            "(its config model is extra=forbid, so this fails at startup)"
        )

    rerank_base = config.get("rerank", {}).get("api_base", "")
    if BIFROST_PORT not in rerank_base:
        found.append(
            f"rerank.api_base is {rerank_base!r}, which is not Bifrost's port. "
            "Rerank must traverse the gateway; a direct embark target loses its "
            "logging, governance and virtual-key accounting."
        )

    auth_mode = server.get("auth_mode")
    if auth_mode != EXPECTED_AUTH_MODE:
        found.append(
            f"server.auth_mode is {auth_mode!r}, expected {EXPECTED_AUTH_MODE!r}. "
            "Vault is the identity provider; another mode resolves callers from "
            "OpenViking's own key store instead."
        )

    found.extend(_oidc_failures(server.get("oidc")))

    vlm = config.get("vlm", {})
    vlm_model = vlm.get("model")
    if vlm_model not in VISION_MODELS:
        found.append(
            f"vlm.model is {vlm_model!r}, which is not in VISION_MODELS. Only a "
            "model measured to accept an image belongs here: one that cannot "
            "makes every image ingest as the string 'Image summary generation "
            "failed' with no error reported."
        )

    vlm_base = vlm.get("api_base", "")
    if BIFROST_PORT not in vlm_base:
        found.append(
            f"vlm.api_base is {vlm_base!r}, which is not Bifrost's port. The VLM "
            "must traverse the gateway for the same reason rerank does."
        )

    # Unset, query_planner falls back to the vlm block, so planning would run
    # on the vision model at vision cost. Absence is legal and silent, which is
    # why this asserts presence rather than only shape.
    planner = config.get("query_planner") or {}
    if not planner.get("model"):
        found.append(
            "query_planner.model is unset, so retrieval planning falls back to "
            "the vlm block and runs on the vision model."
        )
    if BIFROST_PORT not in planner.get("api_base", ""):
        found.append(
            f"query_planner.api_base is {planner.get('api_base')!r}, which is "
            "not Bifrost's port, so planning calls bypass the gateway."
        )

    observability = server.get("observability", {})

    if observability.get("metrics", {}).get("enabled") is not True:
        found.append(
            "server.observability.metrics.enabled is not True. Off, /metrics "
            "returns 404 and prometheus.hcl's openviking job scrapes a dead "
            "target without failing anything."
        )

    prometheus = (
        observability.get("metrics", {}).get("exporters", {}).get("prometheus", {})
    )
    if prometheus.get("enabled") is not True:
        found.append(
            "server.observability.metrics.exporters.prometheus.enabled is not "
            "True. metrics.enabled alone builds no exporter, so /metrics still "
            "404s."
        )

    traces = observability.get("traces", {})
    if traces.get("enabled") is not True:
        found.append(
            "server.observability.traces.enabled is not True, so Tempo gets nothing"
        )

    if TEMPO_OTLP not in traces.get("endpoint", ""):
        found.append(
            f"server.observability.traces.endpoint is {traces.get('endpoint')!r}, "
            f"expected Tempo's OTLP gRPC receiver at {TEMPO_OTLP}. A wrong or "
            "empty endpoint logs one warning at startup and then exports "
            "nothing for the life of the process."
        )

    return found


def _oidc_failures(oidc: Any) -> list[str]:
    """Assert the four `server.oidc` values that fail quietly when wrong."""
    if not isinstance(oidc, dict) or not oidc:
        return [
            (
                "server.oidc is absent. Under auth_mode='oidc' OIDCAuthPlugin "
                "raises at startup, so the job crash-loops instead of serving."
            )
        ]

    found: list[str] = []

    issuer = oidc.get("issuer")
    if issuer != EXPECTED_ISSUER:
        found.append(
            f"server.oidc.issuer is {issuer!r}, expected {EXPECTED_ISSUER!r}. "
            "Upstream verifies iss exactly; a near-miss starts cleanly and then "
            "refuses every request with an invalid-claims error."
        )

    audience = oidc.get("audience")
    if audience != EXPECTED_AUDIENCE:
        found.append(
            f"server.oidc.audience is {audience!r}, expected {EXPECTED_AUDIENCE!r}, "
            "the identity-token role's client_id. Audience verification is never "
            "skipped, so a stale value refuses every token."
        )

    identity = oidc.get("identity") or {}
    for field in ("account_id", "user_id"):
        mapping = identity.get(field) or {}
        if mapping.get("source") != "claim" or mapping.get("claim") != OV_ACCOUNT_CLAIM:
            found.append(
                f"server.oidc.identity.{field} does not read the "
                f"{OV_ACCOUNT_CLAIM!r} claim. Vault's sub is the entity UUID, so "
                "mapping to it yields one account per UUID and still returns 200."
            )

    if "fallback" not in (identity.get("account_id") or {}):
        found.append(
            "server.oidc.identity.account_id.fallback is absent. Upstream defaults "
            "it to 'default', which is a real account on this server, so a token "
            "missing the claim would pool into it instead of being refused."
        )
    elif (identity.get("account_id") or {}).get("fallback") is not None:
        fallback = identity["account_id"]["fallback"]
        found.append(
            f"server.oidc.identity.account_id.fallback is {fallback!r}, expected "
            "null. Any value pools unmapped callers into one shared account."
        )

    return found


# Mirrors the real document's nesting, including agfs declaring its own
# `backend` BEFORE vectordb. A fixture with one `backend` would let a textual
# lookup pass while reading the wrong one.
CLEAN: dict[str, Any] = {
    "storage": {
        "agfs": {"backend": "s3", "s3": {"bucket": "openviking"}},
        "vectordb": {
            "backend": EXPECTED_BACKEND,
            "custom_params": {
                "dsn": "postgresql://u:p@h:5432/openviking",
                "schema": "openviking",
            },
        },
    },
    "embedding": {"dense": {"dimension": 768}},
    "rerank": {"api_base": "http://192.168.2.50:8080/v1"},
    "vlm": {"model": "ollama/glm-5.3-flash", "api_base": "http://192.168.2.50:8080/v1"},
    "query_planner": {
        "model": "ollama/gemma4:31b",
        "api_base": "http://192.168.2.50:8080/v1",
    },
    "encryption": {"api_key_hashing": {"enabled": True}},
    "server": {
        "auth_mode": EXPECTED_AUTH_MODE,
        "oidc": {
            "issuer": EXPECTED_ISSUER,
            "audience": EXPECTED_AUDIENCE,
            "identity": {
                "account_id": {
                    "source": "claim",
                    "claim": OV_ACCOUNT_CLAIM,
                    "fallback": None,
                },
                "user_id": {"source": "claim", "claim": OV_ACCOUNT_CLAIM},
            },
        },
        "observability": {
            "metrics": {
                "enabled": True,
                "exporters": {"prometheus": {"enabled": True}},
            },
            "traces": {"enabled": True, "endpoint": TEMPO_OTLP},
        },
    },
}


def _mutate(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(json.dumps(CLEAN))
    target = config
    for key in path[:-1]:
        target = target[key]
    if value is None:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return config


def _self_test() -> int:
    if failures(CLEAN):
        print(
            f"self-test: clean config was flagged: {failures(CLEAN)}", file=sys.stderr
        )
        return 1

    mutants: dict[str, tuple[dict[str, Any], str]] = {
        "dimension": (_mutate(("embedding", "dense", "dimension"), 512), "dimension"),
        # The one a textual checker gets wrong: agfs.backend stays correct
        # while the vector store is broken.
        "backend": (_mutate(("storage", "vectordb", "backend"), "local"), "backend"),
        "custom_params": (
            _mutate(("storage", "vectordb", "custom_params"), {"schemaa": "x"}),
            "custom_params",
        ),
        "rerank": (
            _mutate(("rerank", "api_base"), "http://192.168.2.46:8000/v1"),
            "rerank",
        ),
        "auth_mode": (_mutate(("server", "auth_mode"), "api_key"), "auth_mode"),
        # Upstream exits the process on this, so the guard has to catch it here.
        "oidc_absent": (_mutate(("server", "oidc"), None), "server.oidc is absent"),
        "oidc_issuer": (
            _mutate(
                ("server", "oidc", "issuer"),
                "https://vault.lab.orangecluster.nl/v1/identity/oidc/",
            ),
            "oidc.issuer",
        ),
        "oidc_audience": (
            _mutate(("server", "oidc", "audience"), "openviking-api"),
            "oidc.audience",
        ),
        # `sub` is the entity UUID, so this yields one account per UUID and
        # every request still returns 200.
        "oidc_claim_sub": (
            _mutate(
                ("server", "oidc", "identity", "account_id"),
                {"source": "claim", "claim": "sub", "fallback": None},
            ),
            "identity.account_id",
        ),
        "oidc_user_claim_sub": (
            _mutate(
                ("server", "oidc", "identity", "user_id"),
                {"source": "claim", "claim": "sub"},
            ),
            "identity.user_id",
        ),
        # `default` is a real account on the live server with zero users.
        "oidc_fallback_default": (
            _mutate(
                ("server", "oidc", "identity", "account_id"),
                {
                    "source": "claim",
                    "claim": OV_ACCOUNT_CLAIM,
                    "fallback": "default",
                },
            ),
            "fallback",
        ),
        "oidc_fallback_absent": (
            _mutate(
                ("server", "oidc", "identity", "account_id"),
                {"source": "claim", "claim": OV_ACCOUNT_CLAIM},
            ),
            "fallback is absent",
        ),
        # The model that started this: catalogued, answers text, refuses images.
        "vlm_model": (
            _mutate(("vlm", "model"), "ollama/deepseek-v4-flash:0731"),
            "vlm.model",
        ),
        "vlm_api_base": (
            _mutate(("vlm", "api_base"), "http://192.168.2.46:8000/v1"),
            "vlm.api_base",
        ),
        "planner_absent": (_mutate(("query_planner",), None), "query_planner.model"),
        "planner_api_base": (
            _mutate(("query_planner", "api_base"), "http://192.168.2.46:8000/v1"),
            "query_planner.api_base",
        ),
        "metrics_off": (
            _mutate(("server", "observability", "metrics", "enabled"), False),
            "metrics.enabled",
        ),
        # metrics.enabled True but no exporter: /metrics still 404s.
        "prometheus_off": (
            _mutate(
                (
                    "server",
                    "observability",
                    "metrics",
                    "exporters",
                    "prometheus",
                    "enabled",
                ),
                False,
            ),
            "prometheus.enabled",
        ),
        "traces_off": (
            _mutate(("server", "observability", "traces", "enabled"), False),
            "traces.enabled",
        ),
        "traces_endpoint": (
            _mutate(
                ("server", "observability", "traces", "endpoint"), "localhost:4317"
            ),
            "traces.endpoint",
        ),
    }
    for name, (config, marker) in mutants.items():
        hits = failures(config)
        if not any(marker in hit for hit in hits):
            print(
                f"self-test: the {name} mutant was not detected: {hits}",
                file=sys.stderr,
            )
            return 1

    print("self-test: ok")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()

    if not CONFIG.exists():
        print(f"{CONFIG}: not found", file=sys.stderr)
        return 1

    try:
        config = json.loads(CONFIG.read_text())
    except json.JSONDecodeError as error:
        print(f"{CONFIG}: not valid JSON: {error}", file=sys.stderr)
        return 1

    found = failures(config)
    for failure in found:
        print(f"{CONFIG}: {failure}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
