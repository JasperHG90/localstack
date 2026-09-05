"""The registry-ui backend: serves the registry view only.

`create_app` takes its config as an argument rather than reading the
environment itself, so tests build a real Starlette app without an env var
in sight. `main()` is the only place that reads the environment.

The frontend's static files are served by a separate task
(`deployments/applications/services/registry-ui/frontend/`), the same
two-task split `dash` uses.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from registry_ui.config import Config
from registry_ui.registry_client import RegistryClient, RegistrySweep
from registry_ui.registry_store import RegistryStore


def _build_sweep(config: Config) -> RegistrySweep | None:
    """None when the credential template has not rendered yet."""
    credential = config.read_registry_credential()
    if credential is None:
        return None
    store = RegistryStore(config.registry_db_path)
    store.create_schema()
    username, password = credential
    return RegistrySweep(RegistryClient(config.registry_addr, username, password), store)


def create_app(config: Config) -> Starlette:
    sweep = _build_sweep(config)

    async def registry_endpoint(request: Any) -> JSONResponse:
        if sweep is None:
            return JSONResponse(
                {"models": [], "images": [], "error": "registry credential not rendered yet"}
            )
        force = request.query_params.get("refresh") == "1"
        try:
            payload: dict[str, Any] = dict(await sweep.payload(force=force))
        except Exception as err:  # noqa: BLE001
            # An unreachable registry degrades the view rather than taking
            # the page down. The sweep returns its last good payload when it
            # has one, so this branch is only reached when there never was.
            payload = {"models": [], "images": [], "error": str(err)}
        payload["generated_at"] = datetime.now(UTC).isoformat()
        return JSONResponse(payload)

    return Starlette(routes=[Route("/api/registry", registry_endpoint)])


def main() -> None:
    import uvicorn

    app = create_app(Config.from_env())
    port = int(os.environ.get("PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()
