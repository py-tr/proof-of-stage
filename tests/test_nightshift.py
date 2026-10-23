from __future__ import annotations

import copy
import json
from typing import Any

import httpx
import pytest
import respx

from app.config import LOCAL_RUNTIME_PREFIX, NS_LIGHTNING_CLOUD, NS_LOCAL_LANE
from app.providers import nightshift
from app.providers.errors import EmptyAnswer
from app.providers.nightshift import LocalOnlyViolation, NightshiftError
from app.providers.receipts import ReceiptMismatch


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _sleep(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(nightshift.asyncio, "sleep", _sleep)
    monkeypatch.setattr(nightshift, "_POLL_INTERVAL_S", 0)


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_chat_sends_unique_scope_per_item(chat_response: dict[str, Any]) -> None:
    with respx.mock:
        route = respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=chat_response)
        )
        await nightshift.chat(
            [{"role": "user", "content": "ping"}],
            NS_LIGHTNING_CLOUD,
            item_id="alpha",
        )
        await nightshift.chat(
            [{"role": "user", "content": "ping"}],
            NS_LIGHTNING_CLOUD,
            item_id="beta",
        )
    scopes = [call.request.headers["meterless-scope"] for call in route.calls]
    assert scopes == ["item-alpha", "item-beta"]
    assert scopes[0] != scopes[1]
    assert route.calls[0].request.headers["meterless-app"] == "genai-nvidia"


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_cloud_answer_for_local_id_is_rejected(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"] = {
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "kind": "cloud",
        "provider": "nvidia",
    }
    payload["meterless"]["egress"]["destination"] = "nvidia"
    with respx.mock:
        respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        with pytest.raises(ReceiptMismatch, match="kind|egress"):
            await nightshift.chat(
                [{"role": "user", "content": "ping"}],
                f"{LOCAL_RUNTIME_PREFIX}nemotron-3.5-lightning-30b-a3b",
                item_id="local-id",
            )


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_chat_4xx_raises_nightshift_error_and_is_not_retried() -> None:
    message = "model not allowed"
    with respx.mock:
        route = respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(400, json={"error": message})
        )
        with pytest.raises(NightshiftError, match=message):
            await nightshift.chat(
                [{"role": "user", "content": "ping"}],
                NS_LIGHTNING_CLOUD,
                item_id="bad-request",
            )
        assert route.call_count == 1


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_chat_empty_answer_retries_once_then_raises(
    chat_response: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _sleep(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(nightshift.asyncio, "sleep", _sleep)
    empty = copy.deepcopy(chat_response)
    empty["choices"][0]["message"]["content"] = "   "
    with respx.mock:
        route = respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=empty)
        )
        with pytest.raises(EmptyAnswer):
            await nightshift.chat(
                [{"role": "user", "content": "ping"}],
                NS_LIGHTNING_CLOUD,
                item_id="empty",
            )
        assert route.call_count == 2


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_local_job_happy_path_from_fixtures(
    job_record: dict[str, Any],
    job_attempt: dict[str, Any],
    job_poll_states: list[dict[str, Any]],
) -> None:
    job_id = job_record["id"]
    polls = [{**job_record, **state} for state in job_poll_states]
    with respx.mock:
        create = respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(200, json={"id": job_id})
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}").mock(
            side_effect=[httpx.Response(200, json=poll) for poll in polls]
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}/attempts/1").mock(
            return_value=httpx.Response(200, json=job_attempt)
        )
        text, attempt = await nightshift.local_job(
            [{"role": "user", "content": "Reply with one word: ready"}],
            item_id="happy",
        )
    assert text == "ready"
    assert attempt["text"] == "ready"
    assert attempt["lane"] == NS_LOCAL_LANE
    body = json.loads(create.calls[0].request.content)
    assert body["auto_synthesize"] == "off"
    assert body["privacy"] == "local-only"
    assert body["messages"][-1] == {"role": "assistant", "content": "<think></think>"}
    assert "max_tokens" not in body
    assert "model" not in body


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_local_job_errored_is_terminal(job_record: dict[str, Any]) -> None:
    job_id = job_record["id"]
    errored = {
        **job_record,
        "status": "errored",
        "error": "lane crashed",
        "progress": "generated 0 of a planned 1 attempts",
    }
    with respx.mock:
        respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(200, json={"id": job_id})
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}").mock(
            return_value=httpx.Response(200, json=errored)
        )
        with pytest.raises(NightshiftError, match="lane crashed"):
            await nightshift.local_job(
                [{"role": "user", "content": "ping"}],
                item_id="errored",
            )


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_local_job_lanes_null_while_queued_then_filled(
    job_record: dict[str, Any], job_attempt: dict[str, Any]
) -> None:
    job_id = job_record["id"]
    queued = {**job_record, "status": "queued", "lanes_resolved": None}
    completed = {**job_record, "status": "completed"}
    with respx.mock:
        respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(200, json={"id": job_id})
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}").mock(
            side_effect=[
                httpx.Response(200, json=queued),
                httpx.Response(200, json=completed),
            ]
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}/attempts/1").mock(
            return_value=httpx.Response(200, json=job_attempt)
        )
        text, _attempt = await nightshift.local_job(
            [{"role": "user", "content": "ping"}],
            item_id="queued",
        )
    assert text == "ready"


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_local_job_rejects_cloud_lane(job_record: dict[str, Any]) -> None:
    job_id = job_record["id"]
    clouded = {
        **job_record,
        "status": "completed",
        "lanes_resolved": [NS_LOCAL_LANE, "nvidia/nemotron-cloud"],
    }
    with respx.mock:
        respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(200, json={"id": job_id})
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}").mock(
            return_value=httpx.Response(200, json=clouded)
        )
        with pytest.raises(LocalOnlyViolation):
            await nightshift.local_job(
                [{"role": "user", "content": "ping"}],
                item_id="lane-check",
            )


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_local_job_includes_400_error_body() -> None:
    message = "auto_synthesize must be an object or a mode word"
    with respx.mock:
        route = respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(400, json={"error": message})
        )
        with pytest.raises(NightshiftError, match=message):
            await nightshift.local_job(
                [{"role": "user", "content": "ping"}],
                item_id="bad-synth",
            )
        body = json.loads(route.calls[0].request.content)
        assert body["auto_synthesize"] == "off"
        assert body["privacy"] == "local-only"
        assert "model" not in body


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_chat_retries_5xx_then_200(
    chat_response: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _sleep(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(nightshift.asyncio, "sleep", _sleep)
    with respx.mock:
        route = respx.post("https://nightshift.test/chat/completions").mock(
            side_effect=[
                httpx.Response(503, json={"error": "busy"}),
                httpx.Response(200, json=chat_response),
            ]
        )
        text, receipt = await nightshift.chat(
            [{"role": "user", "content": "ping"}],
            NS_LIGHTNING_CLOUD,
            item_id="retry-5xx",
        )
    assert text == "ready"
    assert receipt.receipt_id
    assert route.call_count == 2


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_receiptless_200_is_rejected() -> None:
    payload = {"choices": [{"message": {"role": "assistant", "content": "ready"}}]}
    with respx.mock:
        respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        with pytest.raises(ReceiptMismatch, match="receipt_id"):
            await nightshift.chat(
                [{"role": "user", "content": "ping"}],
                NS_LIGHTNING_CLOUD,
                item_id="no-receipt",
            )


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_local_job_retries_attempt_5xx(
    job_record: dict[str, Any], job_attempt: dict[str, Any]
) -> None:
    job_id = job_record["id"]
    completed = {**job_record, "status": "completed"}
    with respx.mock:
        respx.post("https://nightshift.test/jobs").mock(
            return_value=httpx.Response(200, json={"id": job_id})
        )
        respx.get(f"https://nightshift.test/jobs/{job_id}").mock(
            return_value=httpx.Response(200, json=completed)
        )
        route = respx.get(f"https://nightshift.test/jobs/{job_id}/attempts/1").mock(
            side_effect=[
                httpx.Response(502, json={"error": "blip"}),
                httpx.Response(200, json=job_attempt),
            ]
        )
        text, _attempt = await nightshift.local_job(
            [{"role": "user", "content": "ping"}],
            item_id="attempt-5xx",
        )
    assert text == "ready"
    assert route.call_count == 2


@pytest.mark.usefixtures("env", "fast_poll")
@pytest.mark.asyncio
async def test_chat_429_waits_2_4_8_then_surfaces_with_the_servers_fix() -> None:
    waits: list[float] = []

    async def _sleep(seconds: float) -> None:
        waits.append(seconds)

    body = {"error": {"message": "rate limited"}, "meterless": {"fix": ["wait for the lane"]}}
    with respx.mock:
        respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(429, json=body)
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(nightshift.asyncio, "sleep", _sleep)
            with pytest.raises(NightshiftError) as err:
                await nightshift.chat(
                    [{"role": "user", "content": "x"}], NS_LIGHTNING_CLOUD, item_id="r"
                )
    assert waits[:3] == [2.0, 4.0, 8.0]
    assert "rate limited" in str(err.value) and "fix: wait for the lane" in str(err.value)


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_discover_reads_models_and_the_text_class_in_both_shapes() -> None:
    models = {"data": [{"id": "meterless/text"}, {"id": "meterless/new-mode"}, {"id": "nvidia/x"}]}
    text = {"class": "text", "availability": "ready", "ready": ["l1"], "cloud": ["nvidia/x"]}
    for classes in ({"classes": {"text": text}}, {"classes": [text]}):
        with respx.mock:
            respx.get("https://nightshift.test/models").mock(
                return_value=httpx.Response(200, json=models)
            )
            respx.get("https://nightshift.test/meterless/classes").mock(
                return_value=httpx.Response(200, json=classes)
            )
            found = await nightshift.discover()
        assert found["modes"] == ["meterless/text", "meterless/new-mode"]  # unknown ids kept
        assert found["text"]["cloud"] == ["nvidia/x"] and found["text"]["availability"] == "ready"
    with respx.mock:
        respx.get("https://nightshift.test/models").mock(return_value=httpx.Response(401))
        assert (await nightshift.discover())["state"] == "unauthorized"
