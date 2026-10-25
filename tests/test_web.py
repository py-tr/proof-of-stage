from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.web import data as data_mod
from app.web.api import create_app
from app.web.data import SAMPLE_FILE, LiveData, SampleData, order_queue
from app.web.evidence import challenge, count_rules, headline, main_n, n_range, recheck
from app.web.sample import MODEL_COLUMNS
from app.zetaris import ZetarisError


def _client(data: SampleData | None = None) -> TestClient:
    return TestClient(create_app(data or SampleData()))


def test_sample_file_holds_no_model_outputs() -> None:
    payload = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    assert payload["cases"] and "MIT" in payload["source"]
    for case in payload["cases"]:
        assert set(case) == {"check", "report_text"}
        for column in MODEL_COLUMNS:
            assert case["check"].get(column) is None


def test_queue_case_and_cohort_in_sample_mode() -> None:
    client = _client()
    assert client.get("/api/mode").json()["mode"] == "sample"
    queue = client.get("/api/queue").json()
    assert {row["case_id"] for row in queue} >= {"TCGA-A2-A0CV", "TCGA-AN-A0XO"}
    # Sample mode must not say a real contradiction agrees (no reader output here).
    a0cv = next(row for row in queue if row["case_id"] == "TCGA-A2-A0CV")
    assert "cannot both be true" in a0cv["headline"] and "agree" not in a0cv["headline"]
    case = client.get("/api/case/TCGA-A2-A0CV").json()
    assert case["extractions"] == [] and case["flags"] == [] and case["accepted"] == []
    assert [r["output"] for r in case["rules"]["registry_count"]] == ["pN2a"]
    cohort = client.get("/api/cohort").json()
    assert cohort["sample"] is True and sum(g["n"] for g in cohort["groups"]) == len(queue)
    assert client.get("/api/case/not-a-case").status_code == 400
    assert client.get("/api/case/TCGA-ZZ-ZZZZ").status_code == 404


def test_try_to_fool_it_uses_the_real_guards() -> None:
    client = _client()
    report = client.get("/api/case/TCGA-A2-A0CV").json()["report_text"]
    fake = client.post(
        "/api/case/TCGA-A2-A0CV/challenge",
        json={"field": "NPOS", "value": "4", "quote": "four lymph nodes were positive"},
    ).json()
    assert fake["status"] == "rejected" and fake["reason"] == "quote_not_in_report"
    start = report.index("(2/18)")
    sentence = report[start - 20 : start + 16]
    wrong = client.post(
        "/api/case/TCGA-A2-A0CV/challenge",
        json={"field": "NPOS", "value": "4", "quote": sentence},
    ).json()
    assert wrong["status"] == "rejected" and wrong["reason"] == "count_not_in_quote"
    real = client.post(
        "/api/case/TCGA-A2-A0CV/challenge",
        json={"field": "NPOS", "value": "2", "quote": sentence, "known": {"report_n_main": "N1"}},
    ).json()
    # With the earlier accepted N1 and this count, the USL rule names the count field.
    assert real["status"] == "accepted" and real["fault_field_if_accepted"] == "node_count"
    bad = client.post(
        "/api/case/TCGA-A2-A0CV/challenge", json={"field": "X", "value": "1", "quote": "abcd"}
    )
    assert bad.status_code == 400


def test_sample_decision_is_not_written() -> None:
    data = SampleData()
    client = _client(data)
    saved = client.post("/api/case/TCGA-A2-A0CV/decision", json={"claim": "node_count"}).json()
    assert saved["saved"] is False and data.decisions[0]["claim"] == "node_count"
    assert client.post("/api/case/TCGA-A2-A0CV/decision", json={"claim": "x"}).status_code == 400
    assert (
        client.post(
            "/api/case/TCGA-A2-A0CV/decision", json={"claim": "neither", "reason_code": "zzz"}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/case/TCGA-ZZ-ZZZZ/decision", json={"claim": "unsure"}).status_code == 404
    )


@pytest.mark.asyncio
async def test_live_decision_records_the_claimed_field_and_its_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[dict[str, object]] = []

    async def fake_insert(**kwargs):  # type: ignore[no-untyped-def]
        written.append(kwargs)

    live = LiveData()

    async def fake_case(case_id: str, fresh: bool = True):  # type: ignore[no-untyped-def]
        return {
            "check": {
                "case_id": case_id,
                "lymph_nodes_positive": "4.0",
                "fault_field": "node_count",
            },
            "extractions": [
                {
                    "method": "nemotron_reader",
                    "field": "NPOS",
                    "quote": "(2/18) POSITIVE",
                    "model": "m",
                }
            ],
        }

    monkeypatch.setattr(data_mod, "insert_flag", fake_insert)
    monkeypatch.setattr(live, "case", fake_case)
    first = await live.decide("TCGA-A2-A0CV", "node_count", None, None)
    second = await live.decide("TCGA-A2-A0CV", "node_count", None, None)
    row = written[0]
    assert row["field"] == "NODES_POSITIVE" and row["recorded_value"] == "4.0"
    assert row["quote"] == "(2/18) POSITIVE" and row["derived_value"] == "node_count"
    assert row["reason"] == "claim=node_count" and row["model"] == "m"
    assert first["flag_id"] != second["flag_id"]  # append-only: a second click is a second row


def test_zetaris_down_is_a_503() -> None:
    class Down(SampleData):
        async def queue(self):  # type: ignore[no-untyped-def]
            raise ZetarisError("boom")

    response = _client(Down()).get("/api/queue")
    assert (
        response.status_code == 503 and "nothing was read or written" in response.json()["detail"]
    )


def test_count_rules_mirror_the_usl() -> None:
    # Breast rules only (the CN rules are the colon table).
    assert [r["rule_id"] for r in count_rules("4.0", "18", "7")] == ["BN5"]
    assert [r["output"] for r in count_rules("2", "18", "6")] == ["pN1a"]
    assert [r["rule_id"] for r in count_rules("26", None, "6")] == ["BN1"]  # none examined
    assert [r["output"] for r in count_rules("0", True, "7")] == ["pN0"]
    assert count_rules(None, "5", "7") == []


def test_n_range_only_for_count_defined_categories() -> None:
    assert n_range("N1A", "7") == "1-3 positive nodes"
    assert n_range("pN2a", "7") == "4-9 positive nodes"
    assert n_range("N2", "6") == "4-9 positive nodes"  # bare category
    assert n_range("N0", "7") == "0 positive nodes"
    assert n_range("NX", "7") == "nodes not assessed"
    for located in ("N1B", "N1C", "N2B", "N3B", "N3C"):
        assert n_range(located, "7") is None


def test_headlines_lead_with_the_named_field_and_do_not_overclaim() -> None:
    assert main_n("pN2a") == "N2" and main_n("N0(I+)") == "N0" and main_n(None) is None
    count_case = {
        "edition_code": "6",
        "recorded_n": "N1A",
        "lymph_nodes_positive": "4.0",
        "lymph_nodes_tested": "18",
        "derived_n": "pN2a",
        "report_n": "N1A",
        "report_nodes_positive": "2",
        "fault_field": "node_count",
        "reason_class": "n_count_contradiction",
    }
    text = headline(count_case)
    assert text.startswith("The evidence names the count field.")
    assert "1-3 positive nodes" in text and "counts 2" in text and "is wrong" not in text
    review = {
        **count_case,
        "fault_field": "review",
        "report_n": None,
        "report_nodes_positive": None,
    }
    assert "No verified reading settles it" in headline(review)
    untested = {
        **review,
        "recorded_n": "N3A",
        "lymph_nodes_positive": "26.0",
        "lymph_nodes_tested": None,
        "derived_n": "pNX",
    }
    assert "tested count is missing" in headline(untested)
    assert queue_order_ok()


def queue_order_ok() -> bool:
    rows = [
        {"case_id": "B", "fault_field": "review"},
        {"case_id": "C", "fault_field": "node_count"},
        {"case_id": "A", "fault_field": "pathologic_n"},
    ]
    ordered = order_queue(rows, {"A": "2026-10-22 10:00:00"})
    return [row["case_id"] for row in ordered] == ["C", "B", "A"]


def test_recheck_and_challenge_what_if() -> None:
    report = "LYMPH NODES: Two of fourteen (2/14) axillary lymph nodes positive."
    checks = recheck("NPOS", "2", "Two of fourteen (2/14) axillary", report)
    assert all(check["ok"] for check in checks)
    assert not recheck("NPOS", "14", "Two of fourteen (2/14) axillary", report)[-1]["ok"]
    check = {
        "reason_class": "n_count_contradiction",
        "recorded_n_main": "N1",
        "derived_n_main": "N2",
        "lymph_nodes_positive": "4",
    }
    only_n = challenge(check, report, "N", "N1a", "(2/14) axillary lymph nodes positive")
    assert only_n["fault_field_if_accepted"] == "review"  # no count yet: not enough
    both = challenge(check, report, "NPOS", "2", "Two of fourteen (2/14)", {"report_n_main": "N1"})
    assert both["fault_field_if_accepted"] == "node_count"


def test_unread_cases_are_not_shown_as_unresolved() -> None:
    rows = [
        {"case_id": "A", "fault_field": "review"},
        {"case_id": "B", "fault_field": "review"},
        {"case_id": "C", "fault_field": "node_count"},
    ]
    ordered = order_queue(rows, {}, read={"A", "C"})
    assert [row["case_id"] for row in ordered] == ["C", "A", "B"]  # unread last
    assert [row["read"] for row in ordered] == [True, True, False]
    unread = {
        "edition_code": "7",
        "recorded_n": "N2",
        "lymph_nodes_positive": "1.0",
        "derived_n": "pN1a",
        "fault_field": "review",
        "reason_class": "n_count_contradiction",
        "read": False,
    }
    assert headline(unread).startswith("Not read yet.")
    assert headline({**unread, "read": True}).startswith("Needs a person.")
    # sample mode cannot know (read is None): never claims "not read"
    assert order_queue([{"case_id": "A", "fault_field": None}], {})[0]["read"] is None


def test_lineage_is_read_from_the_usl_contract() -> None:
    from app.web.lineage import contract_lineage

    contract = {
        "tables": [
            {"name": "flag", "activateQuery": "SELECT a FROM oa_pg.flag_log"},
            {
                "name": "stage_check",
                "activateQuery": "SELECT * FROM lightning.metastore.registry_audit.stage_audit"
                ".recorded_stage rec LEFT JOIN lightning.metastore.registry_audit.stage_audit"
                ".tumour_case tc ON tc.case_id = rec.case_id",
            },
        ]
    }
    rows = contract_lineage(contract)
    assert {
        "usl_table": "flag",
        "source": "oa_pg.flag_log",
        "kind": "Postgres, append-only",
    } in rows
    assert {"usl_table": "stage_check", "source": "tumour_case", "kind": "USL table"} in rows
    assert contract_lineage({}) == []


def test_the_how_it_works_page_is_served() -> None:
    client = _client()
    page = client.get("/how")
    assert page.status_code == 200 and 'id="steps"' in page.text and "/static/how.js" in page.text
    assert client.get("/static/how.js").status_code == 200
    assert 'href="/how"' in client.get("/").text


def test_live_reads_are_cached_until_any_write() -> None:
    from app.web.lineage import MirrorLineage

    class CountingLive(SampleData):
        mode = "live"
        calls = 0

        async def cohort(self):  # type: ignore[no-untyped-def]
            CountingLive.calls += 1
            return await super().cohort()

    client = TestClient(create_app(CountingLive(), MirrorLineage()))
    client.get("/api/cohort")
    client.get("/api/cohort")
    assert CountingLive.calls == 1
    client.post("/api/case/TCGA-E2-A572/decision", json={"claim": "not-a-claim"})
    client.get("/api/cohort")
    assert CountingLive.calls == 2


def test_sample_mode_hero_example_names_the_count_field() -> None:
    client = _client()
    first = client.post(
        "/api/case/TCGA-E2-A572/challenge",
        json={"field": "N", "value": "N2", "quote": "Pathological staging (pTN): pT 2 N 2", "known": {}},
    ).json()
    assert first["status"] == "accepted"
    out = client.post(
        "/api/case/TCGA-E2-A572/challenge",
        json={
            "field": "NPOS",
            "value": "8",
            "quote": "Lymph node status: Positive 8 / 13",
            "known": {"report_n_main": first["used"]["report_n_main"]},
        },
    ).json()
    assert out["status"] == "accepted" and out["fault_field_if_accepted"] == "node_count"
