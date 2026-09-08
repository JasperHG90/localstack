"""Runtime config, read from the environment.

Same shape as `dash_app.config.Config`: every missing variable is named at
once rather than one per restart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

EMBARK_URL = "DRIFTWATCH_EMBARK_URL"
EMBARK_KEY_FILE = "DRIFTWATCH_EMBARK_KEY_FILE"
EMBEDDING_MODEL = "DRIFTWATCH_EMBEDDING_MODEL"
RERANK_MODEL = "DRIFTWATCH_RERANK_MODEL"
GOLDSET_PATH = "DRIFTWATCH_GOLDSET_PATH"
RERANK_GOLDSET_PATH = "DRIFTWATCH_RERANK_GOLDSET_PATH"
BASELINE_PATH = "DRIFTWATCH_BASELINE_PATH"
INTERVAL_SECONDS = "DRIFTWATCH_INTERVAL_SECONDS"
RERANK_POOL = "DRIFTWATCH_RERANK_POOL"
REQUEST_TIMEOUT = "DRIFTWATCH_REQUEST_TIMEOUT"

_REQUIRED = (
    EMBARK_URL,
    EMBARK_KEY_FILE,
    EMBEDDING_MODEL,
    RERANK_MODEL,
    GOLDSET_PATH,
    RERANK_GOLDSET_PATH,
    BASELINE_PATH,
)


class ConfigError(RuntimeError):
    """A required environment variable is missing, or one holds a bad value."""


@dataclass(frozen=True)
class Config:
    """Everything one evaluation run needs to reach embark and score itself."""

    embark_url: str
    embark_key_file: Path
    embedding_model: str
    rerank_model: str
    goldset_path: Path
    rerank_goldset_path: Path
    baseline_path: Path
    interval_seconds: float
    rerank_pool: int
    request_timeout: float

    @classmethod
    def from_env(cls) -> "Config":
        values = {name: os.environ.get(name) for name in _REQUIRED}
        missing = sorted(name for name, value in values.items() if not value)
        if missing:
            raise ConfigError("missing environment variable(s): " + ", ".join(missing))
        return cls(
            embark_url=(values[EMBARK_URL] or "").rstrip("/"),
            embark_key_file=Path(values[EMBARK_KEY_FILE] or ""),
            embedding_model=values[EMBEDDING_MODEL] or "",
            rerank_model=values[RERANK_MODEL] or "",
            goldset_path=Path(values[GOLDSET_PATH] or ""),
            rerank_goldset_path=Path(values[RERANK_GOLDSET_PATH] or ""),
            baseline_path=Path(values[BASELINE_PATH] or ""),
            interval_seconds=_positive_float(INTERVAL_SECONDS, "86400"),
            rerank_pool=int(_positive_float(RERANK_POOL, "10")),
            request_timeout=_positive_float(REQUEST_TIMEOUT, "120"),
        )

    def read_embark_key(self) -> str:
        """The embark `read` key, from the file Nomad renders it into.

        Raises
        ------
        ConfigError
            If the file is missing or empty. Unlike dash's brokered Nomad
            token, there is nothing useful to do without it: every route this
            service calls needs the credential.
        """
        try:
            key = self.embark_key_file.read_text().strip()
        except OSError as err:
            raise ConfigError(f"cannot read {self.embark_key_file}: {err}") from err
        if not key:
            raise ConfigError(f"{self.embark_key_file} is empty")
        return key


def _positive_float(name: str, default: str) -> float:
    raw = os.environ.get(name) or default
    try:
        value = float(raw)
    except ValueError as err:
        raise ConfigError(f"{name} is not a number: {raw!r}") from err
    if value <= 0:
        raise ConfigError(f"{name} must be positive, got {value}")
    return value
