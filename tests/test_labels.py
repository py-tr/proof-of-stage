import json
from pathlib import Path

import pytest

from app.engine import labels as labels_mod


def test_check_labels_names_missing_and_unchosen_cases() -> None:
    record = {
        "labels": {"A": {"field": "node_count"}, "B": {"field": None}, "Z": {"field": "review"}}
    }
    problems = labels_mod.check_labels(record, ["A", "B", "C"])
    assert any("not in the queue: Z" in p for p in problems)
    assert any("no label: C" in p for p in problems)
    assert any("choose no field" in p and "B" in p for p in problems)


def test_freeze_copies_byte_for_byte_and_never_overwrites(monkeypatch, tmp_path: Path) -> None:
    frozen = tmp_path / "ground-truth-labels.json"
    monkeypatch.setattr(labels_mod, "FROZEN", frozen)
    monkeypatch.setattr(labels_mod, "FROZEN_SHA", frozen.with_suffix(".sha16"))
    monkeypatch.setattr(labels_mod, "ROOT", tmp_path)
    src = tmp_path / "labels.json"
    src.write_text(
        json.dumps({"labels": {"TCGA-3C-AAAU": {"field": "pathologic_n"}}}), encoding="utf-8"
    )
    out = labels_mod.freeze(src)
    assert frozen.read_bytes() == src.read_bytes() and out["sha16"]
    assert labels_mod.freeze(src)["already"] is True  # same content: fine
    src.write_text(json.dumps({"labels": {}}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        labels_mod.freeze(src)  # different content: the first freeze stands
