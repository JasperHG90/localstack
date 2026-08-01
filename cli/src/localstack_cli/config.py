"""Cluster addresses, read from the environment.

The dev shell already exports these (`.devcontainer/.env`), so the CLI reads
them rather than inventing a second source of truth. Later tickets add the
session file; this is addresses only.
"""

import os
from dataclasses import dataclass

VAULT_ADDR = "VAULT_ADDR"
NOMAD_ADDR = "NOMAD_ADDR"
CONSUL_HTTP_ADDR = "CONSUL_HTTP_ADDR"


class ConfigError(RuntimeError):
    """A required cluster address is missing from the environment."""


@dataclass(frozen=True)
class Config:
    """The three addresses every later command needs."""

    vault_addr: str
    nomad_addr: str
    consul_addr: str

    @classmethod
    def from_env(cls) -> "Config":
        """Build from the environment, naming every missing variable at once.

        Reporting them one at a time makes a developer re-run three times to
        discover three problems.
        """
        names = (VAULT_ADDR, NOMAD_ADDR, CONSUL_HTTP_ADDR)
        values = {name: os.environ.get(name) for name in names}
        missing = sorted(name for name, value in values.items() if not value)
        if missing:
            raise ConfigError(
                "missing cluster address(es): "
                + ", ".join(missing)
                + ". These come from .devcontainer/.env; see .env.example."
            )
        return cls(
            vault_addr=values[VAULT_ADDR] or "",
            nomad_addr=values[NOMAD_ADDR] or "",
            consul_addr=values[CONSUL_HTTP_ADDR] or "",
        )
