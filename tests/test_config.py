from __future__ import annotations

import json

import pytest

from app.config import NS_LOCAL_LANE, describe, is_local_nemotron_lane


def test_describe_never_contains_secret_value(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = "secret-value-must-not-leak-9f3c"
    monkeypatch.setenv("NVIDIA_API_KEY", sentinel)
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", sentinel)
    monkeypatch.setenv("ZETARIS_API_KEY", sentinel)
    report = describe()
    blob = json.dumps(report)
    assert sentinel not in blob
    assert report["NVIDIA_API_KEY"] in {"set", "unset"}
    assert "set" in report.values() or "unset" in report.values()
    assert all(value in {"set", "unset"} for value in report.values())
    assert sentinel not in str(report)


def test_local_lane_helper_accepts_runtime_and_lane_id() -> None:
    assert is_local_nemotron_lane("local-runtime/nemotron-3.5-lightning-30b-a3b")
    assert is_local_nemotron_lane(NS_LOCAL_LANE)
    assert not is_local_nemotron_lane("nvidia/nemotron-3.5-super-vl-120b-a12b")
