from __future__ import annotations

from app.reader.quotes import locate

REPORT = (
    "LYMPH NODES: Two of fourteen (2/14) axillary lymph nodes are positive for\n"
    "metastatic carcinoma.  Tumor size: 2.4 cm; the tumor does NOT involve skeletal muscle."
)


def test_exact_quote_maps_to_original_offsets() -> None:
    span = locate("Tumor size: 2.4 cm", REPORT)
    assert span is not None
    assert span.text(REPORT) == "Tumor size: 2.4 cm"


def test_punctuation_case_and_line_breaks_are_ignored() -> None:
    span = locate("two of fourteen 2 14 axillary lymph nodes are positive for metastatic", REPORT)
    assert span is not None
    assert span.text(REPORT).startswith("Two of fourteen (2/14)")
    assert span.text(REPORT).endswith("metastatic")


def test_paraphrase_is_rejected() -> None:
    assert locate("two positive lymph nodes out of fourteen", REPORT) is None


def test_stitched_quote_is_rejected() -> None:
    # Two real fragments joined with an ellipsis are not one verbatim passage.
    assert locate("Two of fourteen ... skeletal muscle", REPORT) is None


def test_too_short_or_empty_quote_is_rejected() -> None:
    assert locate("", REPORT) is None
    assert locate(None, REPORT) is None
    assert locate("N1", REPORT) is None


def test_negation_is_part_of_the_span() -> None:
    span = locate("does NOT involve skeletal muscle", REPORT)
    assert span is not None
    assert "NOT" in span.text(REPORT)


def test_ocr_split_tokens_still_match() -> None:
    text = "Regional lymph nodes: pN x (cannot be assessed)"
    span = locate("pNx (cannot be assessed)", text)
    assert span is not None
    assert span.text(text) == "pN x (cannot be assessed"
