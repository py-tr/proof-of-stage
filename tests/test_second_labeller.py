import json
from pathlib import Path

import pytest

from app.engine import second_labeller as sl


def test_kappa_perfect_and_chance() -> None:
    a = {"A": "node_count", "B": "pathologic_n", "C": "review", "D": "node_count"}
    assert sl.kappa(a, dict(a)) == {"cases": 4, "agree": 4, "kappa": 1.0}
    flipped = {"A": "pathologic_n", "B": "node_count", "C": "node_count", "D": "pathologic_n"}
    out = sl.kappa(a, flipped)
    assert out["agree"] == 0 and out["kappa"] < 0


def test_score_with_uses_recorded_answers_and_both_agree_subset() -> None:
    per_case = {
        "A": {"A0": "node_count", "M0_off": "pathologic_n", "M0_4k": "node_count"},
        "B": {"A0": "pathologic_n", "M0_off": "pathologic_n", "M0_4k": "node_count"},
        "C": {"A0": "review", "M0_off": "pathologic_n", "M0_4k": "review"},
    }
    first = {"A": {"field": "node_count"}, "B": {"field": "pathologic_n"}, "C": {"field": "review"}}
    second = {"A": {"field": "node_count"}, "B": {"field": "node_count"}, "C": {"field": "review"}}
    out = sl.score_with(first, second, per_case, [])
    assert out["labellers"]["agree"] == 2
    assert out["vs_second"]["product_A0"] == {"agree": 2, "of": 3}
    assert out["vs_second"]["super_alone_4k"] == {"agree": 3, "of": 3}
    assert out["vs_second"]["rule_alone_B0"] == {"agree": 0, "of": 3}
    assert out["vs_both_agree"]["labelled"] == 2
    assert out["vs_both_agree"]["product_A0"] == {"agree": 2, "of": 2}


def test_freeze_never_overwrites(monkeypatch, tmp_path: Path) -> None:
    frozen = tmp_path / "second-labeller-labels.json"
    monkeypatch.setattr(sl, "FROZEN", frozen)
    monkeypatch.setattr(sl, "FROZEN_SHA", frozen.with_suffix(".sha16"))
    monkeypatch.setattr(sl, "ROOT", tmp_path)
    src = tmp_path / "labels.json"
    src.write_text(json.dumps({"labels": {"TCGA-3C-AAAU": {"field": "review"}}}), encoding="utf-8")
    out = sl.freeze(src)
    assert frozen.read_bytes() == src.read_bytes() and out["sha16"]
    assert sl.freeze(src)["already"] is True
    src.write_text(json.dumps({"labels": {}}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        sl.freeze(src)
