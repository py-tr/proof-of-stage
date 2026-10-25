from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from app.config import NS_LIGHTNING_CLOUD
from app.providers import envelope_tap, nightshift


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_capture_keeps_the_envelope_and_both_hashes(chat_response: dict[str, Any]) -> None:
    messages = [{"role": "user", "content": "ping"}]
    with respx.mock:
        respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=chat_response)
        )
        with envelope_tap.capture() as calls:
            await nightshift.chat(messages, NS_LIGHTNING_CLOUD, item_id="tap-1")
    assert len(calls) == 1
    call = calls[0]
    assert call["envelope"] == chat_response["meterless"]["receipt_envelope"]
    assert call["item_id"] == "tap-1"
    assert call["messages_sha256"] == envelope_tap.messages_sha256(messages)
    answer = chat_response["choices"][0]["message"]["content"]
    assert call["answer_sha256"] == envelope_tap.sha256_text(answer)


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_outside_the_block_nothing_is_recorded_and_the_client_is_restored(
    chat_response: dict[str, Any],
) -> None:
    original_chat, original_parse = nightshift.chat, nightshift.parse_receipt
    with envelope_tap.capture():
        pass
    assert nightshift.chat is original_chat and nightshift.parse_receipt is original_parse
    with respx.mock:
        respx.post("https://nightshift.test/chat/completions").mock(
            return_value=httpx.Response(200, json=chat_response)
        )
        text, _ = await nightshift.chat(
            [{"role": "user", "content": "x"}], NS_LIGHTNING_CLOUD, item_id="t"
        )
    assert text
