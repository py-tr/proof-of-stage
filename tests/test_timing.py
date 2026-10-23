from app.engine.timing import order, summarise


def _row(model, trial, seconds, settled, agreement):
    return {
        "model_key": model,
        "trial": trial,
        "seconds": seconds,
        "tokens": 100,
        "settled": settled,
        "agreement": agreement,
    }


def test_order_alternates_by_trial() -> None:
    assert order(1) == ("lightning", "super") and order(2) == ("super", "lightning")


def test_summary_reports_settled_per_trial_and_the_kill_lines() -> None:
    rows = [
        _row("lightning", 1, 1.0, True, {"N": "agree", "NPOS": "agree"}),
        _row("super", 1, 3.0, False, {"N": "agree"}),
        _row("lightning", 2, 1.5, True, {"N": "disagree", "NPOS": "agree"}),
        _row("super", 2, 2.0, True, {"N": "agree", "NPOS": "agree"}),
        {"model_key": "super", "trial": 3, "error": "x"},
    ]
    out = summarise(rows)
    assert out["lightning"]["settled_per_trial"] == [1, 1, 0]
    assert out["lightning_faster"] and out["failed_reads"] == 1
    assert out["lightning"]["unsafe"]  # 1 of 4 closings contradicted > 10%
