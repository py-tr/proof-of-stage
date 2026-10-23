from app.engine.vision import compare_paths, summarise


def _f(status: str, value: str | None = None) -> dict:
    return {"status": status, "value": value}


def test_compare_paths_per_field() -> None:
    a = {"N": _f("accepted", "N1A"), "NPOS": _f("accepted", "2")}
    b = {"N": _f("accepted", "n1a"), "NPOS": _f("accepted", "3")}
    assert compare_paths(a, b) == {"N": "same", "NPOS": "contradicts"}
    assert compare_paths({"N": _f("rejected")}, {"N": _f("accepted", "N1")})["N"] == "only_b"


def _row(compare: dict) -> dict:
    return {"compare": compare, "a_seconds": 1, "b_seconds": 2, "a_tokens": 10, "b_tokens": 20}


def test_the_image_read_passes_only_on_four_matching_cases_and_no_contradiction() -> None:
    match = _row({"N": "same", "NPOS": "same"})
    miss = _row({"N": "only_a", "NPOS": "same"})
    assert summarise([match] * 4 + [miss] * 2)["image_read_passes"]
    assert not summarise([match] * 3 + [miss] * 3)["image_read_passes"]
    bad = _row({"N": "same", "NPOS": "contradicts"})
    assert not summarise([match] * 5 + [bad])["image_read_passes"]
