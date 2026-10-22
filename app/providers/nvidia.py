"""NVIDIA Integrate API client with a shared per-minute limiter."""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any

import httpx

from app import config
from app.providers.errors import EmptyAnswer
from app.providers.text import strip_think

NVIDIA_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_MAX_PER_MINUTE = 20
_TIMEOUT_S = 300.0  # Super with a thinking budget can take minutes
_MAX_RETRIES = 3
# Waits before each retry of a 429/5xx without a Retry-After header. The free tier
# answers overload with "Failed to generate completions" (HTTP 5xx); instant retries
# land in the same overload, so back off.
_BACKOFF_S = (5.0, 20.0, 60.0)
_WINDOW_S = 60.0
_MAX_RETRY_AFTER_S = 60.0

_WINDOW_TIMES: deque[float] = deque()
_WINDOW_THREAD_LOCK = threading.Lock()


class ModelMismatch(Exception):
    """The response model field did not match the requested model."""


class NvidiaError(Exception):
    """NVIDIA Integrate call failed."""


class RateLimiter:
    """Client-side limiter: at most max_per_minute acquisitions per 60s window."""

    def __init__(
        self,
        max_per_minute: int = _MAX_PER_MINUTE,
        *,
        times: deque[float] | None = None,
        thread_lock: threading.Lock | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_per_minute = max_per_minute
        self._times = times if times is not None else _WINDOW_TIMES
        self._thread_lock = thread_lock if thread_lock is not None else _WINDOW_THREAD_LOCK
        self._clock = clock
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock is None or self._loop is not loop:
            self._lock = asyncio.Lock()
            self._loop = loop
        return self._lock

    async def acquire(self) -> None:
        lock = self._get_lock()
        async with lock:
            while True:
                with self._thread_lock:
                    now = self._clock()
                    while self._times and now - self._times[0] >= _WINDOW_S:
                        self._times.popleft()
                    if len(self._times) < self.max_per_minute:
                        self._times.append(now)
                        return
                    wait = _WINDOW_S - (now - self._times[0])
                await asyncio.sleep(max(wait, 0.01))


limiter = RateLimiter()


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict):
        for key in ("error", "message", "detail", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict) and value.get("message"):
                return str(value["message"])
    return f"HTTP {response.status_code}"


def _retry_after_seconds(response: httpx.Response, attempt: int = 0) -> float:
    fallback = _BACKOFF_S[min(attempt, len(_BACKOFF_S) - 1)]
    raw = response.headers.get("Retry-After")
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return min(_MAX_RETRY_AFTER_S, max(0.0, float(raw)))
    except ValueError:
        return fallback


async def chat(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 2000,
    **extra: Any,
) -> tuple[str, str]:
    """Chat completion against NVIDIA Integrate; verify the served model."""
    text, served, _usage = await chat_with_usage(messages, model, max_tokens, **extra)
    return text, served


async def chat_with_usage(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 2000,
    **extra: Any,
) -> tuple[str, str, dict[str, Any]]:
    """As chat(), plus the response's token usage (incl. reasoning tokens when reported)."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = config.getenv("NVIDIA_API_KEY")
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        **extra,
    }
    empty_retries_left = 1
    while True:
        payload = await _post(headers, body)
        served = payload.get("model")
        served_name = served if isinstance(served, str) else ""
        if served_name not in config.allowed_served_models(model):
            raise ModelMismatch(f"response model {served_name!r} != requested {model!r}")
        text = strip_think(_extract_text(payload))
        if not text.strip():
            if empty_retries_left > 0:
                empty_retries_left -= 1
                continue
            raise EmptyAnswer("NVIDIA chat returned an empty answer")
        usage = payload.get("usage")
        return text, served_name, usage if isinstance(usage, dict) else {}


async def _post(headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    """POST one chat completion via the shared limiter; retry 429/5xx and transport errors."""
    retries_left = _MAX_RETRIES
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        while True:
            await limiter.acquire()
            try:
                response = await client.post(NVIDIA_CHAT_URL, headers=headers, json=body)
            except httpx.HTTPError as exc:
                if retries_left > 0:
                    retries_left -= 1
                    await asyncio.sleep(2.0)
                    continue
                raise NvidiaError(f"NVIDIA transport error: {type(exc).__name__}") from exc
            if response.status_code == 429 or response.status_code >= 500:
                if retries_left > 0:
                    attempt = _MAX_RETRIES - retries_left
                    retries_left -= 1
                    await asyncio.sleep(_retry_after_seconds(response, attempt))
                    continue
                raise NvidiaError(_error_message(response))
            if not (200 <= response.status_code < 300):
                raise NvidiaError(_error_message(response))
            return response.json()


async def parse_page(jpeg: bytes) -> tuple[list[dict[str, Any]], str]:
    """Nemotron Parse on one page image: every block's text, class and 0-1 box (top-left origin).

    Returns (blocks, served model). The v1 API takes the image as an <img> data URI and
    answers through the markdown_bbox tool.
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = config.getenv("NVIDIA_API_KEY")
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    image = base64.b64encode(jpeg).decode()
    tool = {"type": "function", "function": {"name": "markdown_bbox"}}
    body = {
        "model": config.NV_PARSE,
        "messages": [{"role": "user", "content": f'<img src="data:image/jpeg;base64,{image}" />'}],
        "tools": [tool],
        "tool_choice": tool,
        "max_tokens": 3500,
    }
    payload = await _post(headers, body)
    served = payload.get("model")
    served_name = served if isinstance(served, str) else ""
    if served_name not in config.allowed_served_models(config.NV_PARSE):
        raise ModelMismatch(f"response model {served_name!r} != requested {config.NV_PARSE!r}")
    calls = payload["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        return [], served_name
    parsed = json.loads(calls[0]["function"]["arguments"])
    items = parsed[0] if parsed and isinstance(parsed[0], list) else parsed
    blocks = [
        {
            "x0": float(item["bbox"]["xmin"]),
            "y0": float(item["bbox"]["ymin"]),
            "x1": float(item["bbox"]["xmax"]),
            "y1": float(item["bbox"]["ymax"]),
            "text": str(item.get("text", "")),
            "kind": str(item.get("type", "")),
        }
        for item in items
    ]
    return blocks, served_name
