"""Upload reference CSVs into the Zetaris file store."""

from __future__ import annotations

import uuid

import httpx

from app import config
from app.usl.errors import SetupError
from app.usl.model import FILE_STORE_DIR

_TIMEOUT_S = 60.0


def require_zetaris_config() -> None:
    missing = [
        name
        for name in ("ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY")
        if not config.is_set(name)
    ]
    if missing:
        raise SetupError("unset: " + ", ".join(missing))


def _base_url() -> str:
    base = config.getenv("ZETARIS_REST_URL")
    if not base:
        raise SetupError("ZETARIS_REST_URL is unset")
    return base.rstrip("/")


def _auth_headers() -> dict[str, str]:
    headers = {"X-Request-ID": str(uuid.uuid4())}
    org_id = config.getenv("ZETARIS_ORG_ID")
    api_key = config.getenv("ZETARIS_API_KEY")
    if org_id is not None:
        headers["X-Org-ID"] = org_id
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def upload_csvs(files: list[tuple[str, bytes]]) -> None:
    """Create file-store/<dir> if needed, then save each CSV into it."""
    require_zetaris_config()
    store_path = f"file-store/{FILE_STORE_DIR}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        await _create_dir(client, store_path)
        for name, content in files:
            await _save(client, store_path, name, content)


async def _create_dir(client: httpx.AsyncClient, store_path: str) -> None:
    headers = _auth_headers()
    headers["Content-Type"] = "application/json"
    try:
        response = await client.post(
            f"{_base_url()}/ndp-files/createdir",
            headers=headers,
            json={"path": store_path},
        )
    except httpx.HTTPError as exc:
        raise SetupError(f"file directory request failed: {type(exc).__name__}") from exc
    if response.status_code >= 500:
        raise SetupError(f"file directory request failed: HTTP {response.status_code}")


async def _save(client: httpx.AsyncClient, store_path: str, name: str, content: bytes) -> None:
    try:
        response = await client.post(
            f"{_base_url()}/ndp-files/save",
            headers=_auth_headers(),
            data={"path": store_path},
            files={"files": (name, content, "text/csv")},
        )
    except httpx.HTTPError as exc:
        raise SetupError(f"file save failed: {type(exc).__name__}") from exc
    if not 200 <= response.status_code < 300:
        raise SetupError(f"file save failed: HTTP {response.status_code}")
