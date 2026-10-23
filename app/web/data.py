"""Where the case page gets its data: the live Zetaris USL, or bundled sample data.

Live mode reads only USL tables (stage_check, path_report, derived_stage, flag) through
the guarded SELECT client, and appends reviewer decisions to the Postgres source behind the
USL `flag` table (oa_pg.flag_log), which the USL serves on the next read.
SAMPLE_MODE reads app/web/sample/cases.json: registry facts and report text only, with
no model outputs (the reader's answers are never replayed).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.usl.client import insert_flag, select
from app.usl.model import table_fqn
from app.usl.sqltext import sql_string
from app.zetaris import SqlResult

SAMPLE_FILE = Path(__file__).parent / "sample" / "cases.json"
DECISION_RULE = "human_review"
READER_METHOD = "nemotron_reader"
READER_REVIEW_RULE = "reader_review"
# What a reviewer can claim, and the registry field each claim is about.
CLAIMS = {
    "node_count": "NODES_POSITIVE",
    "pathologic_n": "N",
    "neither": "N",
    "unsure": "N",
}
REASON_CODES = ("addendum", "misread", "rule", "other")
_CASE_ID = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}$")
_CASE_CACHE_S = 60.0

CHECK_COLUMNS = (
    "case_id",
    "site_key",
    "edition_code",
    "recorded_t",
    "recorded_n",
    "recorded_stage",
    "recorded_n_main",
    "lymph_nodes_positive",
    "lymph_nodes_tested",
    "derived_n",
    "derived_n_main",
    "report_t",
    "report_n",
    "report_n_main",
    "report_nodes_positive",
    "reason_class",
    "fault_field",
    "year_of_diagnosis",
)
_QUEUE_REASONS = ("n_count_contradiction", "n_missing_derivable")


def valid_case_id(case_id: str) -> str:
    text = (case_id or "").strip().upper()
    if not _CASE_ID.fullmatch(text):
        raise ValueError("not a TCGA case id")
    return text


def _rows(result: SqlResult) -> list[dict[str, Any]]:
    columns = [column.lower() for column in result.columns]
    out = []
    for row in result.rows:
        if isinstance(row, dict):
            out.append({str(key).lower(): value for key, value in row.items()})
        else:
            out.append(dict(zip(columns, row, strict=False)))
    return out


def order_queue(
    rows: list[dict[str, Any]], decided: dict[str, str], read: set[str] | None = None
) -> list[dict[str, Any]]:
    """Undecided first; a named field, then 'needs a person', then 'not read yet'; then case id.

    read=None means the mode cannot know (sample mode has no reader output at all).
    """
    rank = {"node_count": 0, "pathologic_n": 0, "review": 1}
    for row in rows:
        case_id = str(row.get("case_id"))
        row["decided_at"] = decided.get(case_id)
        row["read"] = None if read is None else case_id in read
    return sorted(
        rows,
        key=lambda row: (
            row["decided_at"] is not None,
            3 if row["read"] is False else rank.get(str(row.get("fault_field")), 2),
            str(row.get("case_id")),
        ),
    )


def _evidence_for(claim: str, case: dict[str, Any]) -> tuple[str | None, str | None, Any, Any]:
    """recorded value, quote, model, receipt for the field a claim is about."""
    check = case["check"]
    field = "NPOS" if claim == "node_count" else "N"
    recorded = check.get("lymph_nodes_positive") if field == "NPOS" else check.get("recorded_n")
    row = next(
        (
            x
            for x in case.get("extractions", [])
            if x.get("field") == field and x.get("method") != "sql_node_count"
        ),
        {},
    )
    return recorded, row.get("quote"), row.get("model"), row.get("receipt_id")


def _decision_reason(claim: str, reason_code: str | None, note: str | None) -> str:
    if reason_code is not None and reason_code not in REASON_CODES:
        raise ValueError("unknown reason code")
    reason = f"claim={claim}" + (f" reason={reason_code}" if reason_code else "")
    if note:
        reason += f" note={note.strip()[:300]}"
    return reason


class LiveData:
    mode = "live"

    def __init__(self) -> None:
        self._cases: dict[str, tuple[float, dict[str, Any]]] = {}

    async def queue(self) -> list[dict[str, Any]]:
        reasons = ", ".join(sql_string(reason) for reason in _QUEUE_REASONS)
        checks, decisions, extracted, reviewed = await asyncio.gather(
            select(
                f"SELECT {', '.join(CHECK_COLUMNS)} FROM {table_fqn('stage_check')} "
                f"WHERE reason_class IN ({reasons})",
                limit=500,
            ),
            select(
                "SELECT case_id, MAX(created_at) AS decided_at "
                f"FROM {table_fqn('flag')} "
                f"WHERE rule_id = {sql_string(DECISION_RULE)} GROUP BY case_id",
                limit=2000,
            ),
            select(
                f"SELECT DISTINCT case_id FROM {table_fqn('derived_stage')} "
                f"WHERE method = {sql_string(READER_METHOD)}",
                limit=5000,
            ),
            select(
                f"SELECT DISTINCT case_id FROM {table_fqn('flag')} "
                f"WHERE rule_id = {sql_string(READER_REVIEW_RULE)}",
                limit=5000,
            ),
        )
        decided = {str(r["case_id"]): str(r["decided_at"]) for r in _rows(decisions)}
        read = {str(r["case_id"]) for r in _rows(extracted) + _rows(reviewed)}
        return order_queue(_rows(checks), decided, read)

    async def cohort(self) -> dict[str, Any]:
        from app.usl.demo import node_positive_sql

        classes, reports, node_positive = await asyncio.gather(
            select(
                "SELECT reason_class, fault_field, count(*) AS n "
                f"FROM {table_fqn('stage_check')} GROUP BY reason_class, fault_field",
                limit=100,
            ),
            select(f"SELECT count(*) AS n FROM {table_fqn('path_report')}", limit=1),
            select(node_positive_sql(), limit=1),
        )
        groups = [
            {"reason_class": r["reason_class"], "fault_field": r["fault_field"], "n": int(r["n"])}
            for r in _rows(classes)
        ]
        scoreboard = _rows(node_positive)
        return {
            "groups": groups,
            "reports": int(_rows(reports)[0]["n"]),
            # "how many patients are node-positive?" by the N column, the count and the verdict
            "node_positive": {k: int(v) for k, v in scoreboard[0].items()} if scoreboard else None,
        }

    async def case(self, case_id: str, fresh: bool = True) -> dict[str, Any] | None:
        cid_text = valid_case_id(case_id)
        cached = self._cases.get(cid_text)
        if not fresh and cached and time.monotonic() - cached[0] < _CASE_CACHE_S:
            return cached[1]
        cid = sql_string(cid_text)
        check, report, extractions, flags = await asyncio.gather(
            select(
                f"SELECT {', '.join(CHECK_COLUMNS)} FROM {table_fqn('stage_check')} "
                f"WHERE case_id = {cid}",
                limit=1,
            ),
            select(
                f"SELECT report_text FROM {table_fqn('path_report')} WHERE case_id = {cid}",
                limit=1,
            ),
            select(
                "SELECT method, field, value, quote, quote_start, quote_end, model, receipt_id, "
                f"created_at FROM {table_fqn('derived_stage')} WHERE case_id = {cid}",
                limit=100,
            ),
            select(
                "SELECT flag_id, rule_id, field, recorded_value, derived_value, quote, reason, "
                f"severity, model, receipt_id, created_at FROM {table_fqn('flag')} "
                f"WHERE case_id = {cid}",
                limit=200,
            ),
        )
        check_rows = _rows(check)
        if not check_rows:
            return None
        extraction_rows, flag_rows = _rows(extractions), _rows(flags)
        check_rows[0]["read"] = any(
            x.get("method") == READER_METHOD for x in extraction_rows
        ) or any(f.get("rule_id") == READER_REVIEW_RULE for f in flag_rows)
        report_rows = _rows(report)
        found = {
            "check": check_rows[0],
            "report_text": report_rows[0]["report_text"] if report_rows else None,
            "extractions": extraction_rows,
            "flags": sorted(flag_rows, key=lambda f: str(f.get("created_at"))),
        }
        self._cases[cid_text] = (time.monotonic(), found)
        return found

    async def decide(
        self, case_id: str, claim: str, reason_code: str | None, note: str | None
    ) -> dict[str, Any]:
        cid = valid_case_id(case_id)
        if claim not in CLAIMS:
            raise ValueError("unknown claim")
        reason = _decision_reason(claim, reason_code, note)
        case = await self.case(cid, fresh=False)
        if case is None:
            raise LookupError("case not found")
        recorded, quote, model, receipt = _evidence_for(claim, case)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        flag_id = f"{cid}:{DECISION_RULE}:{stamp}:{uuid.uuid4().hex[:8]}"  # unique per click
        await insert_flag(
            flag_id=flag_id,
            case_id=cid,
            rule_id=DECISION_RULE,
            field=CLAIMS[claim],
            recorded_value=None if recorded is None else str(recorded),
            derived_value=case["check"].get("fault_field"),
            quote=quote,
            reason=reason,
            severity=claim,
            model=model,
            receipt_id=receipt,
            created_at=stamp,
        )
        self._cases.pop(cid, None)
        return {"flag_id": flag_id, "created_at": stamp, "saved": True}


class SampleData:
    """Bundled cases for SAMPLE_MODE: no network, no model outputs, no write-back."""

    mode = "sample"

    def __init__(self, path: Path = SAMPLE_FILE) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.source_note = payload["source"]
        self._cases = {case["check"]["case_id"]: case for case in payload["cases"]}
        self.decisions: list[dict[str, Any]] = []

    async def queue(self) -> list[dict[str, Any]]:
        return order_queue([dict(case["check"]) for case in self._cases.values()], {})

    async def cohort(self) -> dict[str, Any]:
        groups: dict[tuple[Any, Any], int] = {}
        for case in self._cases.values():
            key = (case["check"].get("reason_class"), case["check"].get("fault_field"))
            groups[key] = groups.get(key, 0) + 1
        return {
            "groups": [
                {"reason_class": r, "fault_field": f, "n": n} for (r, f), n in groups.items()
            ],
            "reports": len(self._cases),
            "sample": True,
        }

    async def case(self, case_id: str, fresh: bool = True) -> dict[str, Any] | None:
        case = self._cases.get(valid_case_id(case_id))
        if case is None:
            return None
        return {**case, "extractions": [], "flags": []}

    async def decide(
        self, case_id: str, claim: str, reason_code: str | None, note: str | None
    ) -> dict[str, Any]:
        cid = valid_case_id(case_id)
        if claim not in CLAIMS:
            raise ValueError("unknown claim")
        _decision_reason(claim, reason_code, note)
        if cid not in self._cases:
            raise LookupError("case not found")
        self.decisions.append({"case_id": cid, "claim": claim, "reason": reason_code})
        return {"flag_id": None, "created_at": None, "saved": False}
