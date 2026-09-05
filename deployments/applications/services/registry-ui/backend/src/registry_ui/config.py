"""Runtime config: the registry address, its credential, and the store path.

Same shape as `dash`'s `Config` (naming every missing variable at once
rather than failing on the first), narrowed to what this service needs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REGISTRY_ADDR = "REGISTRY_ADDR"
REGISTRY_CREDENTIAL_FILE = "REGISTRY_CREDENTIAL_FILE"
REGISTRY_DB_PATH = "REGISTRY_DB_PATH"


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


@dataclass(frozen=True)
class Config:
    registry_addr: str
    registry_credential_file: Path
    registry_db_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        names = (REGISTRY_ADDR, REGISTRY_CREDENTIAL_FILE, REGISTRY_DB_PATH)
        values = {name: os.environ.get(name) for name in names}
        missing = sorted(name for name, value in values.items() if not value)
        if missing:
            raise ConfigError("missing environment variable(s): " + ", ".join(missing))
        return cls(
            registry_addr=values[REGISTRY_ADDR] or "",
            registry_credential_file=Path(values[REGISTRY_CREDENTIAL_FILE] or ""),
            registry_db_path=Path(values[REGISTRY_DB_PATH] or ""),
        )

    def read_registry_credential(self) -> tuple[str, str] | None:
        """The registry's username and password, or None if unrendered.

        Never raises: a Vault template that has not rendered on a fresh
        deployment reads as "no credential", which the route turns into an
        error payload rather than a 500.
        """
        try:
            raw = self.registry_credential_file.read_text()
        except OSError:
            return None
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        username = str(parsed.get("username") or "")
        password = str(parsed.get("password") or "")
        if not username or not password:
            return None
        return username, password
