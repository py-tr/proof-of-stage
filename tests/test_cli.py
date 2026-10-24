from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app import config
from app.cli import _doctor, _sanitize
from app.providers.nightshift import NightshiftError
from app.providers.receipts import Receipt
from app.zetaris import SqlResult


def test_sanitize_keeps_http_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZETARIS_ORG_ID", "1")
    monkeypatch.setenv("SAMPLE_MODE", "true")
    assert _sanitize("HTTP 401") == "HTTP 401"
    assert _sanitize("hmem:1 records") == "hmem:1 records"


def test_sanitize_redacts_secret_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "abcdefghijklmnop"
    monkeypatch.setenv("NVIDIA_API_KEY", token)
    monkeypatch.setenv("ZETARIS_ORG_ID", "1")
    cleaned = _sanitize(f"NVIDIA said HTTP 401 token={token}")
    assert token not in cleaned
    assert "<redacted>" in cleaned
    assert "HTTP 401" in cleaned
    bearer = _sanitize("Authorization: Bearer super-secret-token-value")
    assert "super-secret-token-value" not in bearer
    assert "Bearer <redacted>" in bearer


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_doctor_pass_lines(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    receipt = Receipt(
        receipt_id="rcpt_doc",
        winning_model="nvidia/nemotron-3-ultra-550b-a55b",
        winning_kind="cloud",
        egress_destination="nvidia",
        context_sources=["messages"],
    )
    chat = AsyncMock(return_value=("ready", receipt))
    local = AsyncMock(return_value=("ready", {}))
    found = {
        "state": "online",
        "models": ["meterless/text", "nvidia/nemotron-3.5-super-vl-120b-a12b"],
        "modes": ["meterless/text"],
        "text": {"availability": "ready", "ready": [], "cloud": [config.NS_SUPER_VL]},
    }
    monkeypatch.setattr("app.cli.nightshift.health", AsyncMock(return_value="online"))
    monkeypatch.setattr("app.cli.nightshift.discover", AsyncMock(return_value=found))
    monkeypatch.setattr("app.cli.nightshift.chat", chat)
    monkeypatch.setattr("app.cli.nightshift.local_job", local)
    monkeypatch.setattr("app.cli.nvidia.chat", AsyncMock(return_value=("ready", "served")))
    monkeypatch.setattr("app.cli.zetaris.ping", AsyncMock(return_value=SqlResult([[1]], ["one"])))
    code = await _doctor()
    out = capsys.readouterr().out
    assert code == 0, out
    assert "PASS  nightshift discovery:" in out and "PASS  nightshift meterless/text:" in out
    assert chat.call_args_list[1].args[1] == "meterless/text"
    lines = [line for line in out.splitlines() if line.strip()]
    assert all(line.startswith("PASS  ") for line in lines)
    assert any(line.startswith("PASS  config:") for line in lines)
    assert any(line.startswith("PASS  nightshift chat:") for line in lines)
    chat_id = chat.call_args_list[0].kwargs["item_id"]
    local_id = local.call_args.kwargs["item_id"]
    assert chat_id.startswith("doctor-chat-")
    assert local_id.startswith("doctor-local-")
    assert chat_id != "doctor-chat"
    assert local_id != "doctor-local"


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_doctor_fail_has_no_urls_or_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "test-nvidia-key"
    monkeypatch.setenv("NVIDIA_API_KEY", token)

    async def boom(*_args: Any, **_kwargs: Any) -> None:
        raise NightshiftError(f"GET https://evil.example/v1 failed Bearer {token} HTTP 401")

    monkeypatch.setattr("app.cli.nightshift.health", AsyncMock(return_value="online"))
    monkeypatch.setattr("app.cli.nightshift.chat", boom)
    monkeypatch.setattr("app.cli.nightshift.local_job", AsyncMock(return_value=("ready", {})))
    monkeypatch.setattr("app.cli.nvidia.chat", AsyncMock(return_value=("ready", "served")))
    monkeypatch.setattr("app.cli.zetaris.ping", AsyncMock(return_value=SqlResult([[1]], ["one"])))
    code = await _doctor()
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL  nightshift chat:" in out
    assert "://" not in out
    assert "evil.example" not in out
    assert token not in out
    assert "Bearer <redacted>" in out or "<redacted>" in out


def test_a_clean_clone_without_zetaris_settings_runs_in_sample_mode(monkeypatch) -> None:
    from app import config

    monkeypatch.delenv("SAMPLE_MODE", raising=False)
    for name in ("ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert config.sample_mode() is True
    for name in ("ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY"):
        monkeypatch.setenv(name, "x")
    assert config.sample_mode() is False  # configured: live, unless SAMPLE_MODE says otherwise
    monkeypatch.setenv("SAMPLE_MODE", "true")
    assert config.sample_mode() is True
