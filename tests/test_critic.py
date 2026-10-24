from app.engine.critic import (
    build_planted,
    first_completed_run,
    interleave,
    score,
    verify_objection,
)
from app.engine.second_reader import score as second_score

REPORT = (
    "FINAL DIAGNOSIS: Metastatic carcinoma in two of fourteen axillary lymph nodes (2/14). pT2 N1a."
)
Q = "Metastatic carcinoma in two of fourteen axillary lymph nodes (2/14)"


def test_an_objection_counts_only_when_its_quote_shows_a_different_value() -> None:
    assert verify_objection("NPOS", 2, Q, "4", REPORT)["verified"]
    assert verify_objection("NPOS", 2, Q, "2.0", REPORT)["reason"] == "same_value"
    assert not verify_objection("NPOS", 3, "three of fourteen nodes", "4", REPORT)["verified"]


def _obj(case, field, stored, planted=False, original=None):
    row = {
        "case": case,
        "field": field,
        "stored": stored,
        "verdict": "contradiction",
        "check": {"verified": True, "value": "2"},
        "planted": planted,
    }
    if original is not None:
        row["original"] = original
    return row


def _plants(n_detected):
    return [_obj(f"P{i}", "NPOS", "9", planted=True, original="2") for i in range(n_detected)] + [
        {"case": f"Q{i}", "field": "NPOS", "stored": "9", "verdict": "agree", "planted": True}
        for i in range(5 - n_detected)
    ]


def test_one_right_one_wrong_does_not_ship_and_zero_objections_needs_the_plants() -> None:
    labels = {"A": {"count": "2"}, "B": {"count": "4"}}
    rows = [_obj("A", "NPOS", "4"), _obj("B", "NPOS", "4")] + _plants(5)
    out = score(rows, labels)
    assert out["right"] == 1 and out["wrong"] == 1 and not out["ships"]  # right must exceed wrong
    quiet = [{"case": "A", "field": "NPOS", "stored": "4", "verdict": "agree"}] + _plants(2)
    assert not score(quiet, labels)["ships"]  # 0 objections but the control failed
    good = [_obj("A", "NPOS", "4")] + _plants(4)
    assert score(good, labels)["ships"] and score(good, labels)["plants"]["detected"] == 4


def test_only_the_first_completed_run_counts_and_plants_are_deterministic() -> None:
    rows = [{"run": "r1", "x": 1}, {"run": "r2", "x": 2}]
    assert first_completed_run(rows, [{"run": "r1"}, {"run": "r2"}]) == [rows[0]]
    real = [
        {"case": f"C{i}", "field": f, "stored": s, "quote": "q"}
        for i, (f, s) in enumerate(
            [
                ("NPOS", "1"),
                ("NPOS", "4"),
                ("NPOS", "8"),
                ("NPOS", "0"),
                ("N", "N1A"),
                ("N", "N2"),
                ("N", "N0"),
            ]
        )
    ]
    a, b = build_planted(real, seed=7), build_planted(real, seed=7)
    assert a == b and len(a) == 5 and all(p["stored"] != p["original"] for p in a)
    assert sum(1 for r in interleave(real, a) if r.get("planted")) == 5


def test_the_second_reader_scores_blind_disagreements_against_labels() -> None:
    bench = [
        {
            "model_key": "ultra",
            "case": "A",
            "fields": {"NPOS": {"status": "accepted", "value": "2"}},
        }
    ]
    out = second_score(bench, {"A": {"NPOS": "4.0"}}, {"A": {"count": "2"}})
    assert out["ultra"]["disagreements"] == 1 and out["ultra"]["right"] == 1
    assert out["lightning"]["disagreements"] == 0


def test_v2_gives_every_call_its_own_scope() -> None:
    from app.engine.critic_v2 import item_id

    ids = {item_id("TCGA-A7-A26H", "NPOS", n, "t") for n in range(46)}
    assert len(ids) == 46  # the v1 bug: a planted control and its real row shared one scope
    assert len({item_id("TCGA-A7-A26H", "NPOS", 3, "t") for _ in range(5)}) == 5
