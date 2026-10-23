"""Meterless Nightshift (OpenAI-compatible) client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app import config
from app.providers.errors import EmptyAnswer
from app.providers.receipts import Kind, Receipt, ReceiptMismatch, parse_receipt, verify
from app.providers.text import strip_think

_TIMEOUT_S = 180.0
_MAX_RETRIES = 2
_RATE_LIMIT_WAITS_S = (2.0, 4.0, 8.0)
_POLL_INTERVAL_S = 2.0
_THINK_OFF = {"role": "assistant", "content": "<think></think>"}
_DONE_STATUSES = {"completed", "succeeded", "success", "done"}
_FAIL_STATUSES = {"errored", "failed", "error", "cancelled", "canceled"}
_PENDING_STATUSES = {"queued", "running", "pending", "starting", "scheduled", "waiting"}
_log = logging.getLogger(__name__)


class LocalOnlyViolation(Exception):
    """A local-only job resolved a lane other than the configured local lane."""


class NightshiftError(Exception):
    """Retry-exhausted or otherwise failed Nightshift call."""


def _base_url() -> str:
    return (config.getenv("METERLESS_BASE_URL") or "").rstrip("/")


def _headers(item_id: str) -> dict[str, str]:
    headers = {
        "meterless-app": config.METERLESS_APP,
        "meterless-scope": f"item-{item_id}",
        "Content-Type": "application/json",
    }
    token = config.getenv("METERLESS_RUNTIME_TOKEN")
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        if isinstance(choices[0], dict) and isinstance(choices[0].get("text"), str):
            return choices[0]["text"]
    for key in ("text", "output", "content"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return value["text"]
    return ""


def _is_blank(text: str) -> bool:
    return not text.strip()


async def _backoff(attempt: int) -> None:
    await asyncio.sleep(0.25 * (2**attempt))


def _response_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    if isinstance(payload, dict):
        for key in ("error", "message", "detail", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("message") or value.get("error")
                if nested:
                    return str(nested)
            if value is not None:
                return str(value)
    return response.text


def _server_fix(response: httpx.Response) -> list[str]:
    """The runtime's own fix[] (in its meterless block or the error), if it sent one."""
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    for block in (payload.get("meterless"), payload.get("error"), payload):
        if isinstance(block, dict) and isinstance(block.get("fix"), list):
            return [str(item) for item in block["fix"] if item]
    return []


def _raise_http(response: httpx.Response, what: str) -> None:
    """The server's message first, then its fix[] (Meterless provider contract v4)."""
    message = f"{what} HTTP {response.status_code}: {_response_error_message(response)}"
    fix = _server_fix(response)
    if fix:
        message += " | fix: " + "; ".join(fix)
    elif response.status_code in {401, 403}:
        message += " | paste the runtime's access token into METERLESS_RUNTIME_TOKEN"
    raise NightshiftError(message)


def _raise_for_jobs(response: httpx.Response, what: str) -> None:
    if 200 <= response.status_code < 300:
        return
    _raise_http(response, what)


async def _get_job(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    what: str,
) -> httpx.Response:
    last: httpx.Response | None = None
    for attempt in range(1 + _MAX_RETRIES):
        try:
            last = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            if attempt < _MAX_RETRIES:
                await _backoff(attempt)
                continue
            raise NightshiftError(f"{what} transport error: {type(exc).__name__}") from exc
        if 200 <= last.status_code < 300:
            return last
        if last.status_code >= 500 and attempt < _MAX_RETRIES:
            await _backoff(attempt)
            continue
        _raise_for_jobs(last, what)
    if last is not None:
        _raise_for_jobs(last, what)
    raise NightshiftError(f"{what} failed")


def _job_error_text(job_record: dict[str, Any], status: str) -> str:
    for key in ("error", "progress", "message"):
        value = job_record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return status


def _verify_local_attempt(job_record: dict[str, Any], attempt_payload: dict[str, Any]) -> None:
    if job_record.get("privacy") != "local-only":
        raise LocalOnlyViolation(f"job privacy {job_record.get('privacy')!r} is not 'local-only'")
    if attempt_payload.get("lane") != config.NS_LOCAL_LANE:
        raise LocalOnlyViolation(
            f"attempt lane {attempt_payload.get('lane')!r} != {config.NS_LOCAL_LANE!r}"
        )
    model = attempt_payload.get("model")
    resolved = model.get("resolved") if isinstance(model, dict) else None
    if not isinstance(resolved, str) or not resolved.startswith(
        config.LOCAL_RUNTIME_NEMOTRON_PREFIX
    ):
        raise LocalOnlyViolation(
            f"attempt model.resolved {resolved!r} is not a local Nemotron runtime"
        )


async def _cancel_job(
    client: httpx.AsyncClient, base: str, job_id: str, headers: dict[str, str]
) -> None:
    try:
        response = await client.post(f"{base}/jobs/{job_id}/cancel", headers=headers)
    except httpx.HTTPError:
        _log.info("job cancel failed")
        return
    if response.status_code == 404:
        _log.info("job cancel returned 404")
        return
    if not (200 <= response.status_code < 300):
        _log.info("job cancel returned %s", response.status_code)


async def chat(
    messages: list[dict[str, Any]],
    model: str,
    *,
    item_id: str,
    require_model: str | None = None,
    require_kind: Kind | None = None,
    require_family: str | None = "nvidia/nemotron",
    max_tokens: int = 2000,
    retry_on_mismatch: bool = False,
    require_signature: bool = False,
    pinned_key: str | None = None,
    allow_cache: bool = True,
    **extra: Any,
) -> tuple[str, Receipt]:
    """Chat completion with per-item scope and verified receipt."""
    if require_kind is None and config.is_local_runtime_id(model):
        require_kind = "local"
    url = f"{_base_url()}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        **extra,
    }
    last_error: Exception | None = None
    mismatch: ReceiptMismatch | None = None
    empty_retries_left = 1
    attempts = 1 + _MAX_RETRIES
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(url, headers=_headers(item_id), json=body)
            except httpx.HTTPError as exc:
                last_error = NightshiftError(
                    f"Nightshift chat transport error: {type(exc).__name__}"
                )
                if attempt < attempts - 1:
                    await _backoff(attempt)
                    continue
                raise last_error from exc
            for wait in _RATE_LIMIT_WAITS_S:
                if response.status_code != 429:
                    break
                # contract v4: a 429 retries after 2 s, 4 s and 8 s, then surfaces
                await asyncio.sleep(wait)
                response = await client.post(url, headers=_headers(item_id), json=body)
            if 400 <= response.status_code < 500:
                _raise_http(response, "Nightshift chat")
            if response.status_code >= 500 or not response.content:
                last_error = NightshiftError(
                    f"Nightshift chat retryable status {response.status_code}"
                )
                if attempt < attempts - 1:
                    await _backoff(attempt)
                    continue
                raise last_error
            payload = response.json()
            receipt = parse_receipt(payload)
            try:
                verify(
                    receipt,
                    require_model=require_model,
                    require_kind=require_kind,
                    require_family=require_family,
                    require_signature=require_signature,
                    pinned_key=pinned_key,
                    allow_cache=allow_cache,
                )
            except ReceiptMismatch as exc:
                mismatch = exc
                if retry_on_mismatch and attempt < attempts - 1:
                    await _backoff(attempt)
                    continue
                raise
            text = strip_think(_extract_text(payload))
            if _is_blank(text):
                last_error = EmptyAnswer("Nightshift chat returned an empty answer")
                if empty_retries_left > 0:
                    empty_retries_left -= 1
                    await _backoff(attempt)
                    continue
                raise last_error
            return text, receipt
    if mismatch is not None:
        raise mismatch
    raise last_error or NightshiftError("Nightshift chat failed")


async def local_job(
    messages: list[dict[str, Any]],
    *,
    item_id: str,
    _empty_retries: int = 1,
) -> tuple[str, dict[str, Any]]:
    """Run a local-only Jobs API work item and return attempt 1."""
    base = _base_url()
    headers = _headers(item_id)
    job_messages = [*messages, dict(_THINK_OFF)]
    create_body = {
        "kind": "best_of_n",
        "n": 1,
        "window": "now",
        "privacy": "local-only",
        "auto_synthesize": "off",
        "messages": job_messages,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        created = await client.post(f"{base}/jobs", headers=headers, json=create_body)
        _raise_for_jobs(created, "POST /jobs")
        created_payload = created.json()
        job_id = created_payload.get("id") or created_payload.get("job_id")
        if not job_id:
            raise NightshiftError("Nightshift job create response missing id")
        deadline = asyncio.get_running_loop().time() + _TIMEOUT_S
        job_record: dict[str, Any] = created_payload if isinstance(created_payload, dict) else {}
        logged_unknown: set[str] = set()
        while True:
            polled = await _get_job(client, f"{base}/jobs/{job_id}", headers, "GET /jobs")
            job_record = polled.json()
            lanes = job_record.get("lanes_resolved")
            if isinstance(lanes, list) and lanes and lanes != [config.NS_LOCAL_LANE]:
                raise LocalOnlyViolation(
                    f"lanes_resolved {lanes!r} is not [{config.NS_LOCAL_LANE!r}]"
                )
            status = str(job_record.get("status") or "").lower()
            if status in _DONE_STATUSES:
                break
            if status in _FAIL_STATUSES:
                raise NightshiftError(
                    f"Nightshift local job {status}: {_job_error_text(job_record, status)}"
                )
            if status not in _PENDING_STATUSES and status not in logged_unknown:
                _log.info("unknown job status %s", status)
                logged_unknown.add(status)
            if asyncio.get_running_loop().time() >= deadline:
                await _cancel_job(client, base, str(job_id), headers)
                raise NightshiftError("Nightshift local job timed out")
            await asyncio.sleep(_POLL_INTERVAL_S)
        attempt = await _get_job(
            client,
            f"{base}/jobs/{job_id}/attempts/1",
            headers,
            "GET /jobs/attempts",
        )
        attempt_payload = attempt.json()
        _verify_local_attempt(job_record, attempt_payload)
        text = strip_think(_extract_text(attempt_payload))
        if _is_blank(text):
            if _empty_retries > 0:
                return await local_job(messages, item_id=item_id, _empty_retries=_empty_retries - 1)
            raise EmptyAnswer("Nightshift local job returned an empty answer")
        return text, attempt_payload


async def discover() -> dict[str, Any]:
    """What the runtime serves now: GET /models (every id, unknown meterless/* modes kept)
    and GET /meterless/classes (live state of the text class)."""
    base = _base_url()
    async with httpx.AsyncClient(timeout=15.0) as client:
        models = await client.get(f"{base}/models", headers=_headers("discover"))
        if models.status_code in {401, 403}:
            return {"state": "unauthorized"}
        models.raise_for_status()
        classes = await client.get(f"{base}/meterless/classes", headers=_headers("discover"))
    ids = [str(m.get("id")) for m in models.json().get("data", []) if m.get("id")]
    text: dict[str, Any] = {}
    if classes.status_code == 200:
        payload = classes.json()
        found = payload.get("classes") if isinstance(payload, dict) else None
        if isinstance(found, dict):
            text = found.get("text") or {}
        elif isinstance(found, list):  # the other shape the contract mentions
            text = next((c for c in found if isinstance(c, dict) and c.get("class") == "text"), {})
    return {
        "state": "online",
        "models": ids,
        "modes": [i for i in ids if i.startswith("meterless/")],
        "text": {
            "availability": text.get("availability"),
            "ready": text.get("ready") or [],
            "cloud": text.get("cloud") or [],
            "dispositions": text.get("dispositions") or [],
        },
    }


async def health() -> str:
    """GET /models → online / unauthorized / offline."""
    url = f"{_base_url()}/models"
    if not _base_url():
        return "offline"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=_headers("health"))
    except httpx.HTTPError:
        return "offline"
    if response.status_code in {401, 403}:
        return "unauthorized"
    if 200 <= response.status_code < 300:
        return "online"
    return "offline"
