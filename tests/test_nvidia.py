from __future__ import annotations

import asyncio
import threading
from collections import deque
from typing import Any

import httpx
import pytest
import respx

from app.config import NV_SUPER
from app.providers import nvidia
from app.providers.nvidia import ModelMismatch, RateLimiter


@pytest.fixture(autouse=True)
def _reset_shared_window():
    nvidia._WINDOW_TIMES.clear()
    yield
    nvidia._WINDOW_TIMES.clear()


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_known_alias_is_accepted() -> None:
    served = "private/nvidia/nemotron-3.5-super-120b-a12b"
    with respx.mock:
        respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": served,
                    "choices": [{"message": {"content": "ready"}}],
                },
            )
        )
        text, served_name = await nvidia.chat(
            [{"role": "user", "content": "ping"}],
            NV_SUPER,
        )
    assert text == "ready"
    assert served_name == served


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_unknown_model_is_rejected() -> None:
    with respx.mock:
        respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "someone-else/not-the-requested-model",
                    "choices": [{"message": {"content": "ready"}}],
                },
            )
        )
        with pytest.raises(ModelMismatch):
            await nvidia.chat(
                [{"role": "user", "content": "ping"}],
                NV_SUPER,
            )


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_429_retries_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _sleep(delay: float, *_args: Any, **_kwargs: Any) -> None:
        slept.append(delay)

    monkeypatch.setattr(nvidia.asyncio, "sleep", _sleep)
    ok = {
        "model": NV_SUPER,
        "choices": [{"message": {"content": "ready"}}],
    }
    with respx.mock:
        route = respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "12"}, json={"error": "slow down"}),
                httpx.Response(200, json=ok),
            ]
        )
        text, served = await nvidia.chat(
            [{"role": "user", "content": "ping"}],
            NV_SUPER,
        )
    assert text == "ready"
    assert served == NV_SUPER
    assert route.call_count == 2
    assert slept == [12.0]


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_5xx_retries_then_200(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _sleep(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(nvidia.asyncio, "sleep", _sleep)
    ok = {
        "model": NV_SUPER,
        "choices": [{"message": {"content": "ready"}}],
    }
    with respx.mock:
        route = respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            side_effect=[
                httpx.Response(503, json={"error": "busy"}),
                httpx.Response(200, json=ok),
            ]
        )
        text, _served = await nvidia.chat(
            [{"role": "user", "content": "ping"}],
            NV_SUPER,
        )
    assert text == "ready"
    assert route.call_count == 2


def test_limiter_on_fresh_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    now = {"t": 0.0}
    sleeps: list[float] = []

    def clock() -> float:
        return now["t"]

    async def fake_sleep(delay: float, *_args: Any, **_kwargs: Any) -> None:
        sleeps.append(delay)
        now["t"] += delay

    monkeypatch.setattr(nvidia.asyncio, "sleep", fake_sleep)
    limiter = RateLimiter(
        max_per_minute=20,
        times=deque(),
        thread_lock=threading.Lock(),
        clock=clock,
    )

    async def burst(count: int) -> None:
        for _ in range(count):
            await limiter.acquire()

    asyncio.run(burst(20))
    asyncio.run(burst(1))
    assert sleeps, "21st acquire across event loops must block"
    assert sleeps[0] == pytest.approx(60.0)


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_5xx_without_retry_after_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _sleep(delay: float, *_args: Any, **_kwargs: Any) -> None:
        slept.append(delay)

    monkeypatch.setattr(nvidia.asyncio, "sleep", _sleep)
    busy = {"error": {"message": "Failed to generate completions"}}
    ok = {"model": NV_SUPER, "choices": [{"message": {"content": "ready"}}]}
    with respx.mock:
        respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            side_effect=[
                httpx.Response(500, json=busy),
                httpx.Response(500, json=busy),
                httpx.Response(500, json=busy),
                httpx.Response(200, json=ok),
            ]
        )
        text, _served = await nvidia.chat([{"role": "user", "content": "ping"}], NV_SUPER)
    assert text == "ready"
    assert slept == list(nvidia._BACKOFF_S)
