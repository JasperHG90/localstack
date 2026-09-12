#!/usr/bin/env python3
"""Assert the parts of OpenViking's config that must not drift.

The config is `services/openviking/ov.conf.json`, a real JSON document that
Terraform round-trips into the jobspec. These sixteen settings each fail in a way
a healthy-looking service would hide:

    dimension        a wrong value corrupts the collection silently
    backend          the vectordb one, not agfs's, which is declared first
    custom_params    ov-postgres forbids unknown keys; a typo fails at startup
    keyword_fields   unset, ov-postgres adds `content` and the index expression
                     stops matching the one the collection already carries
    rerank target    pointing past Bifrost loses gateway governance
    auth_mode        anything but oidc means Vault stopped being the identity
    oidc.issuer      a wrong value starts fine and 401s every request after
    oidc.audience    must equal the identity-token role's client_id
    oidc.account_id  read from ov_account; `sub` is the entity UUID
    oidc.user_id     read from ov_user, a DIFFERENT claim: the operator is
                     user jasper inside account lab, and lab/user/lab is empty
    oidc.fallback    null on both, or a caller with no claim pools into a
                     shared tree. Note this does NOT make the mapping fail
                     closed: Vault renders an absent metadata key as an empty
                     string and upstream applies fallback only to a null, so an
                     entity without the metadata resolves to account `""`. The
                     ACL on the identity-token role is what prevents that, not
                     this check.
    vlm model        one that cannot see embeds an error string per image
    vlm api_base     past Bifrost loses gateway governance, as rerank does
    metrics          off, /metrics 404s and the Prometheus job scrapes nothing
    traces           off or unpointed, and Tempo receives nothing, silently
    query_planner    past Bifrost, or unset and it silently falls back to vlm

Two more live in the jobspec rather than in that document, and are asserted here
for the same reason.

`OPENVIKING_WEB_STUDIO_DIR`: upstream mounts Web Studio whenever it finds an
index.html and offers no config switch, so naming a path that does not exist is
the only way to turn it off. Studio answers without a token, so dropping that
line republishes the UI and every other gate stays green.

`command` and `args`: the job starts `python -m ov_retrieval`, a wrapper that
adds a keyword leg and a diversity pass before handing over to the ordinary
server. Drop either line and the image entrypoint runs the stock server, which
comes up healthy and answers every search without them.

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
import re
import sys
from pathlib import Path
from typing import Any

CONFIG = Path("deployments/applications/services/openviking/ov.conf.json")

# The jobspec, checked for one env var only. See STUDIO_ENV below.
JOBSPEC = Path("deployments/applications/services/openviking.hcl")
STUDIO_ENV = "OPENVIKING_WEB_STUDIO_DIR"

# The one blessed value. Upstream `.strip()`s the variable and treats the empty
# result as unset, so "" and "   " REMOUNT Studio while reading as disabled.
# Pinning one sentinel rather than "any non-empty path" also means a deliberate
# remount has to edit this file, where the reason gets written down.
STUDIO_DIR_OFF = "/nonexistent"

_STUDIO_ASSIGNMENT = re.compile(rf'^\s*{STUDIO_ENV}\s*=\s*"([^"]*)"')

# The hybrid retrieval entry point. `ov_retrieval.__main__` patches OpenViking's
# HierarchicalRetriever and then hands over to the ordinary server, so dropping
# these two lines falls back to the image's own entrypoint, `openviking-server`,
# and retrieval goes back to vector-only. The wrapper's fatal-on-failure check
# never fires, because the wrapper is what stopped running.
RETRIEVAL_COMMAND = "/app/.venv/bin/python"
RETRIEVAL_MODULE = "ov_retrieval"

_COMMAND_ASSIGNMENT = re.compile(r'^\s*command\s*=\s*"([^"]*)"')
_ARGS_ASSIGNMENT = re.compile(r"^\s*args\s*=\s*\[(.*)\]")

EXPECTED_DIMENSION = 384
EXPECTED_AUTH_MODE = "oidc"
EXPECTED_BACKEND = "ov_postgres.adapter.PgVectorCollectionAdapter"

# Vault appends `/v1/<namespace>/identity/oidc` to whatever `identity/oidc/config`
# holds, and refuses an issuer carrying a path, so Terraform writes the bare host
# and this is the string that comes back in `iss`. Upstream compares it exactly.
EXPECTED_ISSUER = "https://vault.lab.orangecluster.nl/v1/identity/oidc"

# The identity-token role's `client_id`, set explicitly in oidc.tf so this stays
# a literal both sides can be checked against.
EXPECTED_AUDIENCE = "openviking"

# Vault reserves `sub` for the entity UUID, so both identifiers travel as claims
# the role's template adds. They are SEPARATE because they differ: the operator
# is user `jasper` inside account `lab`, and there is no `lab/user/lab`.
OV_ACCOUNT_CLAIM = "ov_account"
OV_USER_CLAIM = "ov_user"
IDENTITY_CLAIMS = {"account_id": OV_ACCOUNT_CLAIM, "user_id": OV_USER_CLAIM}
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
        # Measured 2026-09-12, the way this set requires: a 64x64 red PNG to
        # /v1/chat/completions answered "Red". ov.conf.json picked it in
        # 66bed3c and this set was not updated with it, so the check was red.
        "gemini/gemini-3.5-flash-lite",
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
        # Added at ov-postgres-v0.6.0 (config.py:184), the tag
        # Dockerfile.openviking pins. This set omitted it, so a config that
        # enables it was reported as forbidden.
        "keep_deltas",
        "keyword_query_mode",
        "keyword_rank",
        "store_content",
        "text_search_config",
        "tz_policy",
        "min_pool_size",
        "max_pool_size",
        "connect_timeout",
        "application_name",
    }
)

# Written out rather than left to the default. From ov-postgres 0.3.0
# `resolved_keyword_fields` appends `content` whenever `store_content` is on and
# this key is unset, which changes the full-text index expression. The live
# index carries the five below, `create_index` never re-runs on a collection
# that already exists, and `ensure_indexes` is a manual call, so the drift shows
# up as keyword search seq-scanning rather than as an error.
EXPECTED_KEYWORD_FIELDS = [
    "name",
    "description",
    "abstract",
    "tags",
    "search_tags",
]


def jobspec_failures(text: str) -> list[str]:
    """Assert the two things the jobspec carries that fail silently.

    The second is the hybrid retrieval entry point, checked by
    `_retrieval_failures` below. The first is Web Studio:

    Upstream mounts the SPA whenever it finds an index.html, and offers no
    config switch: `OPENVIKING_WEB_STUDIO_DIR` naming a path that does not
    exist is the only lever. Studio answers without a token and HAProxy
    forwards every path to 1933, so dropping this one line republishes the UI
    with every other gate still green.

    Reads the VALUE, not the name. Presence alone would pass on `= ""`, which
    upstream strips and treats as unset, and on the variable appearing in a
    comment. Commented lines are skipped for the same reason.

    It does NOT check which task's `env` block the assignment sits in. One
    task exists today; a second one carrying the variable would satisfy this.
    """
    values = [
        match.group(1)
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
        for match in [_STUDIO_ASSIGNMENT.match(line)]
        if match
    ]

    if not values:
        found = [
            (
                f"{STUDIO_ENV} is not assigned, so upstream mounts Web Studio "
                "at /studio. It answers without a token and nothing else in "
                "this repo refuses that request."
            )
        ]
    else:
        found = [
            (
                f"{STUDIO_ENV} is {value!r}, expected {STUDIO_DIR_OFF!r}. Upstream "
                "strips the value and falls back to the packaged bundle when the "
                "result is empty, so a blank path remounts Studio while reading "
                "as disabled."
            )
            for value in values
            if value != STUDIO_DIR_OFF
        ]

    return found + _retrieval_failures(text)


def _retrieval_failures(text: str) -> list[str]:
    """Assert the jobspec starts OpenViking through the ov-retrieval wrapper.

    Both lines are load-bearing and neither errors when removed. Without
    `command`, podman runs the image's own entrypoint, which starts
    `openviking-server` directly; the server comes up, `/ready` passes, and
    every search silently loses its keyword leg and its diversity pass.

    Reads values, and skips commented lines, for the reasons the Studio check
    above gives. `args` is matched on the module rather than on the whole list
    so the host, port and bot flags stay editable without touching this file.
    """
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]

    commands = [
        m.group(1) for line in lines for m in [_COMMAND_ASSIGNMENT.match(line)] if m
    ]
    if RETRIEVAL_COMMAND not in commands:
        return [
            (
                f"the jobspec does not set command = {RETRIEVAL_COMMAND!r}, so "
                "the image entrypoint runs openviking-server and retrieval "
                "falls back to vector-only with every other gate still green."
            )
        ]

    args = [m.group(1) for line in lines for m in [_ARGS_ASSIGNMENT.match(line)] if m]
    if not any(f'"{RETRIEVAL_MODULE}"' in arg and '"-m"' in arg for arg in args):
        return [
            (
                f"the jobspec's args do not carry -m {RETRIEVAL_MODULE}, so the "
                "python named by command starts something other than the "
                "hybrid retrieval wrapper."
            )
        ]

    return []


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

    custom_params = vectordb.get("custom_params", {})

    unknown = set(custom_params) - ALLOWED_CUSTOM_PARAMS
    if unknown:
        found.append(
            f"custom_params carries {sorted(unknown)}, which ov-postgres forbids "
            "(its config model is extra=forbid, so this fails at startup)"
        )

    keyword_fields = custom_params.get("keyword_fields")
    if keyword_fields != EXPECTED_KEYWORD_FIELDS:
        found.append(
            f"custom_params.keyword_fields is {keyword_fields!r}, expected "
            f"{EXPECTED_KEYWORD_FIELDS!r}. Unset, ov-postgres appends 'content' "
            "because store_content is on, and the six-column expression no "
            "longer matches the index the collection already carries."
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
    for field, claim in IDENTITY_CLAIMS.items():
        mapping = identity.get(field) or {}
        if mapping.get("source") != "claim" or mapping.get("claim") != claim:
            found.append(
                f"server.oidc.identity.{field} does not read the {claim!r} claim. "
                "Vault's sub is the entity UUID, so mapping to it yields one "
                "account per UUID and still returns 200. Mapping user_id to the "
                "ACCOUNT claim is the same class of error: it resolves to "
                "lab/user/lab, which does not exist."
            )

    # The two fields differ and the difference is the whole point.
    # AccountMappingConfig defaults `fallback` to "default", a real account on
    # this server, so account_id must set it EXPLICITLY null. UserMappingConfig
    # defaults it to None, so absent is already safe there and only a non-null
    # value is a defect.
    account = identity.get("account_id") or {}
    if "fallback" not in account:
        found.append(
            "server.oidc.identity.account_id.fallback is absent. Upstream "
            "defaults it to 'default', a real account on this server, so a "
            "caller whose claim is missing pools into it. Set it to null."
        )
    for field in ("account_id", "user_id"):
        fallback = (identity.get(field) or {}).get("fallback")
        if fallback is not None:
            found.append(
                f"server.oidc.identity.{field}.fallback is {fallback!r}, "
                "expected null. Any value pools callers whose claim is missing "
                "into one shared tree."
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
                "store_content": True,
                "keyword_fields": list(EXPECTED_KEYWORD_FIELDS),
            },
        },
    },
    "embedding": {"dense": {"dimension": 384}},
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
                "user_id": {"source": "claim", "claim": OV_USER_CLAIM},
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
        # Dropping the key is the silent one: ov-postgres then appends
        # `content` on its own and the index expression stops matching.
        "keyword_fields_absent": (
            _mutate(
                ("storage", "vectordb", "custom_params"),
                {"dsn": "postgresql://u:p@h:5432/openviking", "store_content": True},
            ),
            "keyword_fields",
        ),
        "keyword_fields_with_content": (
            _mutate(
                ("storage", "vectordb", "custom_params", "keyword_fields"),
                [*EXPECTED_KEYWORD_FIELDS, "content"],
            ),
            "keyword_fields",
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
        # The trap this split exists to stop: both fields reading the account
        # claim resolves to lab/user/lab, which does not exist, so the caller
        # gets a 200 and an empty tree.
        "oidc_user_claim_is_account": (
            _mutate(
                ("server", "oidc", "identity", "user_id"),
                {"source": "claim", "claim": OV_ACCOUNT_CLAIM},
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
        "oidc_user_fallback_set": (
            _mutate(
                ("server", "oidc", "identity", "user_id"),
                {"source": "claim", "claim": OV_USER_CLAIM, "fallback": "lab"},
            ),
            "identity.user_id.fallback",
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

    good_args = (
        f'args = ["-m", "{RETRIEVAL_MODULE}", "--host", "0.0.0.0", '
        '"--port", "1933", "--with-bot"]'
    )

    def config_block(*lines: str) -> str:
        body = "".join(f"    {line}\n" for line in lines)
        return "  config {\n" + body + "  }\n"

    good_launch = config_block(f'command = "{RETRIEVAL_COMMAND}"', good_args)

    def env_block(*lines: str) -> str:
        body = "".join(f"    {line}\n" for line in lines)
        return good_launch + "  env {\n" + body + "  }\n"

    clean_jobspec = env_block(
        'OPENVIKING_CONFIG_FILE = "/secrets/ov.conf"',
        f'{STUDIO_ENV} = "{STUDIO_DIR_OFF}"',
    )
    if jobspec_failures(clean_jobspec):
        print("self-test: a clean jobspec was flagged", file=sys.stderr)
        return 1

    good_env = "  env {\n" + f'    {STUDIO_ENV} = "{STUDIO_DIR_OFF}"\n' + "  }\n"

    # The first five keep Studio mounted while reading as if it did not. The
    # last three start the stock server while reading as if hybrid retrieval
    # were installed.
    jobspec_mutants = {
        "absent": env_block('OPENVIKING_CONFIG_FILE = "/secrets/ov.conf"'),
        "commented": env_block(f'# {STUDIO_ENV} = "{STUDIO_DIR_OFF}"'),
        "empty": env_block(f'{STUDIO_ENV} = ""'),
        "whitespace": env_block(f'{STUDIO_ENV} = "   "'),
        "real_bundle": env_block(f'{STUDIO_ENV} = "/app/web_studio/dist"'),
        "command_absent": config_block(good_args) + good_env,
        "command_commented": (
            config_block(f'# command = "{RETRIEVAL_COMMAND}"', good_args) + good_env
        ),
        "args_without_module": (
            config_block(
                f'command = "{RETRIEVAL_COMMAND}"',
                'args = ["-m", "openviking_cli.server_bootstrap"]',
            )
            + good_env
        ),
    }
    for name, jobspec in jobspec_mutants.items():
        if not jobspec_failures(jobspec):
            print(f"self-test: the {name} jobspec mutant passed", file=sys.stderr)
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

    if not JOBSPEC.exists():
        print(f"{JOBSPEC}: not found", file=sys.stderr)
        return 1

    jobspec_found = jobspec_failures(JOBSPEC.read_text())
    for failure in jobspec_found:
        print(f"{JOBSPEC}: {failure}", file=sys.stderr)

    return 1 if found or jobspec_found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
