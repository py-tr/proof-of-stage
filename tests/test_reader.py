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


@pytest.mark.asyncio
async def test_one_failed_case_does_not_stop_the_batch(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from app.reader import commands
    from app.reports.ingest import Report

    reports = {
        "TCGA-AA-0001": Report("r1", "TCGA-AA-0001", REPORT),
        "TCGA-AA-0002": Report("r2", "TCGA-AA-0002", REPORT),
    }
    monkeypatch.setattr(commands, "read_reports_csv", lambda: reports)
    calls: list[str] = []

    async def flaky(case_id, report, provider="nvidia"):  # type: ignore[no-untyped-def]
        calls.append(case_id)
        if case_id == "TCGA-AA-0001":
            raise RuntimeError("timeout")
        return await read_report_stub(case_id)

    async def read_report_stub(case_id):  # type: ignore[no-untyped-def]
        from app.reader.reader import FieldResult, ReadResult

        r = ReadResult(case_id=case_id, model="m", receipt_id=None, provider="nvidia")
        r.fields["T"] = FieldResult("T", "abstained", reason="model_abstained")
        return r

    monkeypatch.setattr(commands, "read_report", flaky)
    code = await commands.read_cases(
        case_ids=list(reports), rule=None, limit=5, provider="nvidia", store=False
    )
    out = capsys.readouterr().out
    assert code == 0 and calls == ["TCGA-AA-0001", "TCGA-AA-0002"]
    assert "ERROR RuntimeError" in out and "errors=1" in out and "read=1" in out


COUNT_REPORT = (
    "LYMPH NODES: Two of fourteen (2/14) axillary lymph nodes positive for metastatic "
    "carcinoma. Sentinel node: no tumor seen (0/1)."
)


def test_count_accepted_when_its_digits_are_in_the_quote() -> None:
    fr = reader_mod.judge_count(
        {"N_positive": 2, "N_positive_quote": "Two of fourteen (2/14) axillary lymph nodes"},
        COUNT_REPORT,
    )
    assert fr.status == "accepted" and fr.value == "2"
    assert fr.span is not None and "2/14" in fr.quote


def test_count_accepted_as_a_number_word() -> None:
    fr = reader_mod.judge_count(
        {"N_positive": "2", "N_positive_quote": "Two of fourteen"}, COUNT_REPORT
    )
    assert fr.status == "accepted"


def test_count_rejected_when_the_quote_does_not_contain_it() -> None:
    # A real quote, but it states 2 positive nodes, not 4.
    fr = reader_mod.judge_count(
        {"N_positive": 4, "N_positive_quote": "Two of fourteen (2/14) axillary lymph nodes"},
        COUNT_REPORT,
    )
    assert fr.status == "rejected" and fr.reason == "count_not_in_quote"


def test_count_digit_match_is_not_a_substring_match() -> None:
    # "1" must not match inside "14".
    fr = reader_mod.judge_count(
        {"N_positive": 1, "N_positive_quote": "Two of fourteen (2/14) axillary"}, COUNT_REPORT
    )
    assert fr.status == "rejected" and fr.reason == "count_not_in_quote"


def test_count_invented_quote_and_bad_values() -> None:
    invented = reader_mod.judge_count(
        {"N_positive": 2, "N_positive_quote": "two nodes were involved"}, COUNT_REPORT
    )
    assert invented.reason == "quote_not_in_report"
    assert reader_mod.judge_count({"N_positive": -1}, COUNT_REPORT).reason == "invalid_count"
    assert reader_mod.judge_count({"N_positive": True}, COUNT_REPORT).reason == "invalid_count"
    assert reader_mod.judge_count({"N_positive": None}, COUNT_REPORT).status == "abstained"
    assert reader_mod.judge_count(None, COUNT_REPORT).reason == "answer_not_json"


@pytest.mark.asyncio
async def test_store_keeps_reason_rows_and_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.reader import store as store_mod
    from app.reader.quotes import Span

    rows: list[dict[str, object]] = []
    flags: list[dict[str, object]] = []

    async def fake_insert(**kwargs):  # type: ignore[no-untyped-def]
        rows.append(kwargs)

    async def fake_flag(**kwargs):  # type: ignore[no-untyped-def]
        flags.append(kwargs)

    monkeypatch.setattr(store_mod, "insert_extraction", fake_insert)
    monkeypatch.setattr(store_mod, "insert_flag", fake_flag)
    result = reader_mod.ReadResult(case_id="C1", model="m", receipt_id=None, provider="nvidia")
    span = Span(0, 10)
    result.fields["N"] = reader_mod.FieldResult("N", "accepted", "N1A", "q", span, "2 of 14 -> N1a")
    result.fields["NPOS"] = reader_mod.FieldResult("NPOS", "accepted", "2", "q", span)
    result.fields["T"] = reader_mod.FieldResult(
        "T", "rejected", "T2", "x", reason="quote_too_short"
    )
    counts = await store_mod.store_result(result, created_at="2026-10-22 00:00:00")
    assert [r["field"] for r in rows] == ["N", "N_REASON", "NPOS"]
    assert rows[1]["value"] == "2 of 14 -> N1a"
    assert counts == {"extractions": 3, "review_flags": 1}
    assert flags[0]["reason"] == "quote_too_short"


@pytest.mark.parametrize(
    ("count", "span", "expected"),
    [
        (14, "Two of fourteen (2/14) axillary lymph nodes positive", False),  # tested count
        (2, "Two of fourteen (2/14) axillary lymph nodes positive", True),
        (2, "focus 2.4 cm, 0/14 nodes", False),
        (0, "focus 2.4 cm, 0/14 nodes", True),
        (0, "3 of 5 nodes positive, no extranodal extension", False),
        (0, "no metastatic carcinoma in lymph nodes", True),
        (0, "None of the lymph nodes", True),
        (3, "three lymph nodes with metastatic carcinoma", True),
        (1, "16 nodes, one of which contains metastatic carcinoma", True),
    ],
)
def test_count_in_span_reads_the_positive_number(count: int, span: str, expected: bool) -> None:
    assert reader_mod.count_in_span(count, span) is expected


def test_reason_row_requires_the_value_row_of_the_same_read() -> None:
    from app.usl.client import insert_extraction_sql

    sql = insert_extraction_sql(
        case_id="C1",
        method="nemotron_reader",
        field="N_REASON",
        value="r",
        created_at="2026-10-22 00:00:00",
        requires=("N", "2026-10-22 00:00:00"),
    )
    assert "WHERE NOT EXISTS" in sql
    assert "AND EXISTS" in sql and "sibling.field = 'N'" in sql
    assert "sibling.created_at = '2026-10-22 00:00:00'" in sql


def test_thinking_args_off_and_budget() -> None:
    off, off_max = reader_mod.thinking_args(0)
    assert off == {"chat_template_kwargs": {"enable_thinking": False}} and off_max == 1500
    on, on_max = reader_mod.thinking_args(4000)
    assert on["chat_template_kwargs"] == {"enable_thinking": True, "reasoning_budget": 4000}
    assert on_max == 7000


@pytest.mark.asyncio
async def test_nightshift_read_is_pinned_signed_fresh_and_run_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.providers.receipts import Receipt

    calls: list[dict[str, object]] = []

    async def fake_chat(messages, model, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"model": model, **kwargs})
        receipt = Receipt(
            receipt_id="rcpt_1",
            winning_model=model,
            winning_kind="cloud",
            usage={"prompt_tokens": 900, "completion_tokens": 19},
            from_cache=False,
            signature="verified",
        )
        return '{"T": "UNKNOWN", "N": "UNKNOWN", "N_positive": null}', receipt

    monkeypatch.setattr(reader_mod.nightshift, "chat", fake_chat)
    first = await read_report("C1", REPORT, provider="nightshift", budget=0, run_id="runA")
    await read_report("C1", REPORT, provider="nightshift", budget=4000, run_id="runA")
    await read_report("C1", REPORT, provider="nightshift", budget=0, run_id="runB")
    item_ids = [call["item_id"] for call in calls]
    assert len(set(item_ids)) == 3  # never reused across runs or rungs
    assert all(call["require_model"] == call["model"] for call in calls)
    assert all(call["retry_on_mismatch"] and call["require_signature"] for call in calls)
    assert all(call["allow_cache"] is False for call in calls)
    assert calls[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert first.budget == 0 and first.usage["completion_tokens"] == 19
    assert first.signature == "verified" and first.from_cache is False
