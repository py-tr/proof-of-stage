from app.engine import local_focus as lf


def test_short_report_goes_whole():
    text = "Breast, left. Lymph nodes: 0 of 3 positive."
    assert lf.focus(text) == (text, False)


def test_long_report_keeps_cue_sentences_with_neighbours_in_order():
    filler = " ".join(f"Filler sentence {i}." for i in range(800))
    text = filler + " Neighbour before. Lymph nodes: 2 of 14 positive. Neighbour after. " + filler
    out, focused = lf.focus(text)
    assert focused and len(out) <= lf.FOCUS_BUDGET
    assert "Neighbour before. Lymph nodes: 2 of 14 positive. Neighbour after." in out
    assert "Filler sentence 5." not in out


def test_compare_against_the_cloud_ladder():
    control = lf.referee({"closed": {"N": {"rung": "R1", "value": "N1a"}}})
    assert lf.compare({"N": "N1A", "NPOS": "2"}, control) == {"N": "agree", "NPOS": "unconfirmed"}
    assert lf.compare({"N": "N2"}, control) == {"N": "disagree"}


def _row(settled, agreement, ok=True, focused=False):
    return {
        "settled": settled,
        "agreement": agreement,
        "seconds": 1.0,
        "focused": focused,
        "attempts": [{"checks": {"a": ok}}],
    }


def test_summarise_floor_scales_with_the_set():
    rows = [_row(True, {"N": "agree"})] * 33 + [_row(False, {})] * 27
    out = lf.summarise(rows, {})
    assert out["settled_floor"] == 33 and out["claim_met"] is True
    rows = [_row(True, {"N": "agree"})] * 32 + [_row(False, {})] * 28
    assert lf.summarise(rows, {})["claim_met"] is False
    rows = [_row(True, {"N": "agree"})] * 40 + [_row(False, {})] * 19 + [{"error": "x"}]
    assert lf.summarise(rows, {})["claim_met"] is False
