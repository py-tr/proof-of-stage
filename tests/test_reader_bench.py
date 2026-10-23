from app.engine.reader_bench import score


def _row(model: str, case: str, n: str | None, count: str | None) -> dict:
    fields = {
        "N": {"status": "accepted" if n else "rejected", "value": n},
        "NPOS": {"status": "accepted" if count else "rejected", "value": count},
    }
    return {"model_key": model, "case": case, "tokens": 100, "fields": fields}


LABELS = {"A": {"count": "2", "n": "pN1a"}, "B": {"count": "", "n": "N2"}}


def test_scoring_by_main_category_and_count() -> None:
    rows = [
        _row("super", "A", "N1", "2"),  # both correct (N1 = N1A main)
        _row("super", "B", "N2A", None),  # N correct, count unscored (label empty)
        _row("lightning", "A", "N2", "3"),  # both wrong
        _row("lightning", "B", None, None),
        _row("ultra", "A", "N1A", "2"),
        _row("ultra", "B", "N2", "5"),  # count unscored: the label states none
    ]
    out = score(rows, LABELS)
    assert out["super"]["correct"] == 3 and out["super"]["wrong"] == 0
    assert out["lightning"]["wrong"] == 2 and out["lightning"]["fields"]["N"]["not_accepted"] == 1
    assert out["deep_read_seat"] == "super"  # a tie on correct keeps the seat with Super


def test_a_model_needs_more_correct_and_no_more_wrong_to_take_the_seat() -> None:
    rows = [_row("super", "A", "N1", None), _row("super", "B", None, None)]
    rows += [_row("ultra", "A", "N1", "2"), _row("ultra", "B", "N2", None)]
    rows += [_row("lightning", "A", None, None), _row("lightning", "B", None, None)]
    assert score(rows, LABELS)["deep_read_seat"] == "ultra"
