from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.reader import reader as reader_mod
from app.reader.reader import judge_field, normalise_category, parse_answer, read_report
from app.reports.ingest import case_id_of, iter_corpus, select_reports

REPORT = (
    "FINAL DIAGNOSIS: Invasive ductal carcinoma, left breast. Tumor size 2.4 cm in greatest "
    "dimension. Two of fourteen axillary lymph nodes positive for metastatic carcinoma (2/14)."
)


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("T", "pT2", "T2"),
        ("T", "ypT1c", "T1C"),
        ("T", "T1mi", "T1MI"),
        ("T", "Tis", "TIS"),
        ("N", "pN1a", "N1A"),
        ("N", "N0 (i+)", "N0(I+)"),
        ("N", "N1mi", "N1MI"),
        ("T", "T5", None),
        ("N", "stage II", None),
        ("T", None, None),
    ],
)
def test_normalise_category(field: str, raw: object, expected: str | None) -> None:
    assert normalise_category(field, raw) == expected  # type: ignore[arg-type]


def test_parse_answer_tolerates_fences_and_prose() -> None:
    text = 'Here you go:\n```json\n{"T": "T2", "T_quote": "x"}\n```'
    assert parse_answer(text) == {"T": "T2", "T_quote": "x"}
    assert parse_answer("no json here") is None
    assert parse_answer("{broken") is None


def test_accepts_only_with_verbatim_quote() -> None:
    answer = {
        "T": "pT2",
        "T_quote": "Tumor size 2.4 cm in greatest dimension",
        "T_reason": "2.4 cm",
    }
    fr = judge_field("T", answer, REPORT)
    assert fr.status == "accepted" and fr.value == "T2"
    assert fr.span is not None and REPORT[fr.span.start : fr.span.end] == fr.quote


def test_fluent_answer_with_invented_quote_is_rejected() -> None:
    answer = {"N": "N1a", "N_quote": "two positive nodes were found in the axilla"}
    fr = judge_field("N", answer, REPORT)
    assert fr.status == "rejected" and fr.reason == "quote_not_in_report"
    assert fr.span is None


def test_unknown_is_an_abstention_not_a_value() -> None:
    fr = judge_field("T", {"T": "UNKNOWN", "T_quote": ""}, REPORT)
    assert fr.status == "abstained" and fr.value is None


def test_invalid_category_is_rejected() -> None:
    fr = judge_field("T", {"T": "Stage IIA", "T_quote": "Tumor size 2.4 cm"}, REPORT)
    assert fr.status == "rejected" and fr.reason == "invalid_category"


@pytest.mark.asyncio
async def test_read_report_uses_super_with_thinking_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def fake_chat(messages, model, max_tokens=2000, **extra):  # type: ignore[no-untyped-def]
        seen.update(model=model, extra=extra, max_tokens=max_tokens)
        return (
            json.dumps(
                {
                    "T": "pT2",
                    "T_quote": "Tumor size 2.4 cm",
                    "N": "pN1a",
                    "N_quote": "Two of fourteen axillary lymph nodes positive",
                }
            ),
            "private/nvidia/nemotron-3.5-super-120b-a12b",
        )

    monkeypatch.setattr(reader_mod.nvidia, "chat", fake_chat)
    result = await read_report("TCGA-XX-0001", REPORT)
    assert seen["extra"] == {
        "chat_template_kwargs": {"enable_thinking": True, "reasoning_budget": 4000}
    }
    assert result.fields["T"].status == "accepted" and result.fields["N"].value == "N1A"


def test_case_id_and_corpus_selection(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert case_id_of("TCGA-A2-A0CV.1234-uuid") == "TCGA-A2-A0CV"
    csv_text = (
        "patient_filename,text\n"
        'TCGA-A2-A0CV.aaa,"report one"\n'
        'TCGA-A2-A0CV.bbb,"second report same case"\n'
        'TCGA-ZZ-9999.ccc,"other cohort"\n'
        'TCGA-B6-A0WV.ddd,""\n'
    )
    path = tmp_path / "c.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("TCGA_Reports.csv", csv_text)
        archive.writestr("__MACOSX/._TCGA_Reports.csv", "junk")
    rows = list(iter_corpus(path))
    chosen = select_reports(rows, {"TCGA-A2-A0CV", "TCGA-B6-A0WV"})
    assert [r.case_id for r in chosen] == ["TCGA-A2-A0CV"]
    assert chosen[0].report_text == "report one"
    assert io  # keep the import used for clarity of intent
