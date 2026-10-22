from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METERLESS_BASE_URL", "https://nightshift.test")
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "test-runtime-token")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")
    monkeypatch.setenv("ZETARIS_REST_URL", "https://zetaris.test")
    monkeypatch.setenv("ZETARIS_ORG_ID", "test-org")
    monkeypatch.setenv("ZETARIS_API_KEY", "test-zetaris-key")
    monkeypatch.setenv("SAMPLE_MODE", "true")


@pytest.fixture
def chat_response() -> dict[str, Any]:
    return load_fixture("nightshift_chat_response.json")


@pytest.fixture
def job_record() -> dict[str, Any]:
    return load_fixture("nightshift_job_record.json")


@pytest.fixture
def job_attempt() -> dict[str, Any]:
    return load_fixture("nightshift_job_attempt.json")


@pytest.fixture
def job_poll_states() -> list[dict[str, Any]]:
    return load_fixture("nightshift_job_poll_states.json")


@pytest.fixture(autouse=True)
def _isolated_description_stamp(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    # setup() records which descriptions were applied; tests must never touch the real stamp.
    monkeypatch.setattr("app.usl.setup.DESCRIPTIONS_STAMP", tmp_path / "usl_descriptions.sha256")
