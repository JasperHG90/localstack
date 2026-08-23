"""Runtime config: cluster addresses and file paths, read from the environment.

Same shape as `localstack_cli.config.Config` (naming every missing variable
at once rather than failing on the first), extended with the two paths this
app needs that the CLI does not: where its brokered Nomad token lands, and
where the tile config is mounted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

NOMAD_ADDR = "NOMAD_ADDR"
CONSUL_HTTP_ADDR = "CONSUL_HTTP_ADDR"
NOMAD_TOKEN_FILE = "NOMAD_TOKEN_FILE"
DASH_TILES_PATH = "DASH_TILES_PATH"


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


@dataclass(frozen=True)
class Config:
    nomad_addr: str
    consul_addr: str
    nomad_token_file: Path
    tiles_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        names = (NOMAD_ADDR, CONSUL_HTTP_ADDR, NOMAD_TOKEN_FILE, DASH_TILES_PATH)
        values = {name: os.environ.get(name) for name in names}
        missing = sorted(name for name, value in values.items() if not value)
        if missing:
            raise ConfigError("missing environment variable(s): " + ", ".join(missing))
        return cls(
            nomad_addr=values[NOMAD_ADDR] or "",
            consul_addr=values[CONSUL_HTTP_ADDR] or "",
            nomad_token_file=Path(values[NOMAD_TOKEN_FILE] or ""),
            tiles_path=Path(values[DASH_TILES_PATH] or ""),
        )

    def read_nomad_token(self) -> str | None:
        """The brokered Nomad token, or None if it hasn't rendered yet.

        Never raises: a template that hasn't rendered on a fresh
        deployment should read as "no token yet" (every job read comes
        back UNKNOWN), not crash the whole endpoint.
        """
        try:
            token = self.nomad_token_file.read_text().strip()
        except OSError:
            return None
        return token or None
