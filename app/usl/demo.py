"""`python -m app.cli usl demo [--write]`: a reproducible, timed query pack for the USL.

Follows the Zetaris demo template (what you built, what data, how to run it, cleanup): the
same SQL in the same order, each with its wall-clock time and a sample of its output.
--write saves the run as docs/zetaris-demo.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.usl.client import load_contract, select
from app.usl.model import ROOT, USL_FQN, USL_TABLES, table_fqn

DEMO_DOC = ROOT / "docs" / "zetaris-demo.md"
# Sample mode's copy of "one question, three answers": the aggregate numbers and the registry
# columns of the disagreeing records only (no report reading, quote or verdict text).
SNAPSHOT = ROOT / "app" / "web" / "sample" / "node_positive_snapshot.json"
_SNAPSHOT_COLUMNS = ("case_id", "recorded_n", "lymph_nodes_positive")
SQL_DIR = ROOT / "app" / "usl" / "sql"
SAMPLE_ROWS = 5
# the setup files that identify and onboard each source, in the order `usl setup` runs them
ONBOARDING = (
    ("Postgres (our append-only results)", ("002", "003", "004", "005")),
    ("File store REG_FILES (rules, report text, Parse blocks)", ("010", "011", "012", "015")),
    ("NCI GDC REST API (cases, recorded stage, node counts)", ("020", "021", "022")),
)


@dataclass
class Step:
    title: str
    why: str
    sql: str
    sample: int = SAMPLE_ROWS  # rows shown in the doc


def steps() -> list[Step]:
    check = table_fqn("stage_check")
    out = [
        Step(
            "Row count of every USL table",
            "the layer is live over all three source types",
            " UNION ALL ".join(
                f"SELECT '{t}' AS usl_table, count(*) AS rows FROM {table_fqn(t)}"
                for t in USL_TABLES
            ),
            sample=len(USL_TABLES),
        ),
        Step(
            "Every rule registered on the layer",
            "our custom rules and the key rules Zetaris generated from the DDL",
            f"LIST DQ USL {USL_FQN}",
            sample=50,
        ),
        Step(
            "A plain question to the layer",
            "how many records in each edition cannot be true as written, and which field the "
            "evidence names",
            f"SELECT edition_code, fault_field, count(*) AS cases FROM {check} "
            "WHERE reason_class IN ('n_count_contradiction', 'n_missing_derivable') "
            "GROUP BY edition_code, fault_field "
            "ORDER BY edition_code, fault_field",
            sample=50,
        ),
        Step(
            "The cross-source verdict",
            "one USL table joins the REST registry record, the file-store rules and the "
            "Postgres reader output, and names the field the evidence points to",
            "SELECT case_id, recorded_n, lymph_nodes_positive, derived_n, report_n, "
            f"report_nodes_positive, fault_field FROM {check} "
            "WHERE fault_field IS NOT NULL ORDER BY fault_field, case_id",
        ),
        Step(
            "The basic data-quality rule (source level)",
            "positive nodes cannot exceed the nodes examined, checked on the recorded values",
            f"RUN DQ nodes_within_tested TABLE {table_fqn('recorded_stage')}",
        ),
        Step(
            "The contradiction rule",
            "records whose recorded N and node count cannot both be true",
            f"RUN DQ nodes_consistent TABLE {check}",
        ),
        Step(
            "The records the contradiction rule flags",
            "the review queue, straight from the rule",
            f"SHOW DQ INVALID RECORD nodes_consistent TABLE {check}",
        ),
        Step(
            "A key rule Zetaris generated from the DDL",
            "every scanned-report block belongs to a known case",
            f"RUN DQ case_id TABLE {table_fqn('parse_block')}",
        ),
        Step(
            "The composite keys hold (no output rows means no duplicates)",
            "Zetaris runs a composite-key rule only through its first column, so we check the "
            "full keys of derived_stage (case_id, method, field) and parse_block (case_id, "
            "page_no, block_index) directly",
            f"SELECT 'derived_stage' AS usl_table, case_id, count(*) AS n FROM "
            f"{table_fqn('derived_stage')} GROUP BY case_id, method, field HAVING count(*) > 1 "
            f"UNION ALL SELECT 'parse_block' AS usl_table, case_id, count(*) AS n FROM "
            f"{table_fqn('parse_block')} GROUP BY case_id, page_no, block_index "
            "HAVING count(*) > 1",
        ),
        Step(
            "Evidence on the original scan",
            "the block Nemotron Parse read, with its box, for the hero case",
            "SELECT case_id, page_no, block_text, xmin, ymin, xmax, ymax "
            f"FROM {table_fqn('parse_block')} "
            "WHERE case_id = 'TCGA-A2-A0CV' AND block_text LIKE '%2/18%'",
        ),
        Step(
            "One question, three answers",
            "'is this patient node-positive?' asked of the N column and of the count column, on "
            "the records where both apply (6th/7th edition, N and count recorded, no "
            "micrometastasis or isolated tumour cells): the columns disagree on some records, "
            "and the contradictions that keep the same answer still change the N category",
            node_positive_sql(check),
        ),
        Step(
            "Which answer the report supports",
            "the records where the two columns disagree, with the quote-verified reading of the "
            "report and the field the layer names; node_positive_by_report is empty where the "
            "layer leaves the case to a person",
            "SELECT case_id, recorded_n, lymph_nodes_positive, report_n, report_nodes_positive, "
            "fault_field, CASE WHEN fault_field = 'review' OR report_n_main IS NULL THEN NULL "
            "WHEN report_n_main <> 'N0' THEN 'yes' ELSE 'no' END AS node_positive_by_report "
            f"FROM {check} WHERE {_BOTH_APPLY} AND {_DISAGREE} ORDER BY fault_field, case_id",
            sample=20,
        ),
    ]
    return out


# "Is this patient node-positive?" by each registry column, where both columns apply.
_BOTH_APPLY = (
    "coalesce(edition_code, '') IN ('6', '7') "
    "AND reason_class IN ('consistent', 'n_count_contradiction')"
)
_BY_N = "recorded_n_main <> 'N0'"
_BY_COUNT = "CAST(lymph_nodes_positive AS DOUBLE) > 0"
_BY_N_SUM = f"sum(CASE WHEN {_BY_N} THEN 1 ELSE 0 END)"
_BY_COUNT_SUM = f"sum(CASE WHEN {_BY_COUNT} THEN 1 ELSE 0 END)"
_DISAGREE = f"({_BY_N}) <> ({_BY_COUNT})"


@dataclass
class StepResult:
    step: Step
    seconds: float
    columns: list[str]
    rows: list[list[Any]]
    total_rows: int
    error: str | None = None


async def run_demo() -> tuple[list[StepResult], dict[str, Any]]:
    results = []
    started = time.monotonic()
    contract = await load_contract()
    contract_seconds = round(time.monotonic() - started, 2)
    for step in steps():
        t0 = time.monotonic()
        try:
            result = await select(step.sql, limit=500)
            rows = [list(r) if not isinstance(r, dict) else list(r.values()) for r in result.rows]
            results.append(
                StepResult(
                    step,
                    round(time.monotonic() - t0, 2),
                    list(result.columns),
                    rows[: step.sample],
                    len(rows),
                )
            )
        except Exception as exc:  # a failed step is reported, never hidden
            results.append(
                StepResult(step, round(time.monotonic() - t0, 2), [], [], 0, str(exc)[:200])
            )
    tables = contract.get("tables") if isinstance(contract, dict) else []
    meta = {
        "run_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "contract_tables": len(tables or []),
        "contract_seconds": contract_seconds,
        "total_seconds": round(time.monotonic() - started, 2),
    }
    return results, meta


def _onboarding() -> list[str]:
    lines = []
    for source, prefixes in ONBOARDING:
        files = sorted(f.name for f in SQL_DIR.glob("*.sql") if f.name[:3] in prefixes)
        lines.append(f"- {source}: " + ", ".join(f"`app/usl/sql/{name}`" for name in files))
    return lines


def _table(columns: list[str], rows: list[list[Any]]) -> str:
    if not columns:
        return "_(no rows)_"
    head = "| " + " | ".join(columns) + " |\n|" + "---|" * len(columns) + "\n"
    body = "".join("| " + " | ".join(str(v)[:60] for v in row) + " |\n" for row in rows)
    return head + body


def render(results: list[StepResult], meta: dict[str, Any]) -> str:
    lines = [
        "# Zetaris demo: the `stage_audit` Unified Semantic Layer",
        "",
        f"Run {meta['run_at']} with `python -m app.cli usl demo --write` (live Zetaris). "
        f"LOAD USL: {meta['contract_tables']} tables ({meta['contract_seconds']} s). "
        f"Whole pack: {meta['total_seconds']} s wall-clock.",
        "",
        "## What we built",
        f"`{USL_FQN}`: one Unified Semantic Layer that joins a public registry API, file-store "
        "CSVs and our own append-only Postgres results, and names which registry field the "
        "verified evidence points to. Data-quality rules run inside Zetaris (`RUN DQ`).",
        "",
        "## What data",
        "- NCI GDC REST API, project TCGA-BRCA (open access): cases, recorded stage, node "
        "counts (`GDC_REST.brca_cases_raw`, cached).",
        "- File store `REG_FILES`: paraphrased staging rules, pathology report text "
        "(TCGA-Reports, MIT) and Nemotron Parse blocks of the original scanned reports.",
        "- Postgres `oa_pg`: the reader's quote-verified values and the review log "
        "(INSERT only, append-only).",
        "",
        "## How the sources were onboarded (`usl setup` runs these files in order)",
        "",
        *_onboarding(),
        "",
        "## How to run it (the SQL in order, with output)",
    ]
    for i, r in enumerate(results, 1):
        lines += [
            "",
            f"### {i}. {r.step.title} ({r.seconds} s)",
            f"Why: {r.step.why}.",
            "```sql",
            r.step.sql,
            "```",
        ]
        if r.error:
            lines.append(f"**Failed:** {r.error}")
        else:
            shown = (
                f" (first {len(r.rows)} of {r.total_rows})" if r.total_rows > len(r.rows) else ""
            )
            lines += [f"Output{shown}:", "", _table(r.columns, r.rows)]
    lines += [
        "",
        "## What was checked",
        "Every number above came from this run; a failed step would be shown, not skipped.",
        "",
        "## Cleanup",
        "`python -m app.cli usl teardown --yes` removes the namespace, the two Lightning "
        "databases and our two Postgres tables (and nothing else).",
        "",
    ]
    return "\n".join(lines)


def summary(results: list[StepResult], meta: dict[str, Any]) -> str:
    out = [f"usl demo {meta['run_at']}: {meta['total_seconds']} s total"]
    for i, r in enumerate(results, 1):
        state = f"FAILED {r.error}" if r.error else f"{r.total_rows} row(s)"
        out.append(f"  {i}. {r.step.title}: {r.seconds} s, {state}")
    return "\n".join(out) + "\n"


def write_doc(results: list[StepResult], meta: dict[str, Any], path: Path = DEMO_DOC) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(results, meta), encoding="utf-8")
    return path


def node_positive_sql(check: str | None = None) -> str:
    """'How many patients are node-positive?' by the N column, the count column and the verdict
    (usl demo step 11; the case page and /how show the same row, live)."""
    check = check or table_fqn("stage_check")
    return (
        f"SELECT count(*) AS records, {_BY_N_SUM} AS node_positive_by_n_column, "
        f"{_BY_COUNT_SUM} AS node_positive_by_count_column, "
        f"sum(CASE WHEN {_DISAGREE} THEN 1 ELSE 0 END) AS columns_disagree, "
        # the third answer: where the columns disagree, trust the field the verdict did not
        # name; a case left to a person is not counted as node-positive
        f"sum(CASE WHEN NOT ({_DISAGREE}) AND {_BY_N} THEN 1 "
        f"WHEN {_DISAGREE} AND fault_field = 'node_count' AND {_BY_N} THEN 1 "
        f"WHEN {_DISAGREE} AND fault_field = 'pathologic_n' AND {_BY_COUNT} THEN 1 "
        "ELSE 0 END) AS node_positive_by_verdict, "
        # the checked count (stage_check.positive_nodes_checked) is empty for every case left
        # to a person, even where both registry columns agree the patient is node-positive
        "sum(CASE WHEN CAST(positive_nodes_checked AS INT) > 0 THEN 1 ELSE 0 END) "
        "AS node_positive_by_checked_count, "
        f"sum(CASE WHEN {_DISAGREE} AND fault_field = 'review' THEN 1 ELSE 0 END) "
        "AS left_to_a_person, "
        "sum(CASE WHEN reason_class = 'n_count_contradiction' AND NOT "
        f"({_DISAGREE}) THEN 1 ELSE 0 END) AS same_answer_other_category, "
        # the fourth answer: a person's latest decision (flag, rule human_review) wins over the
        # verdict; "neither" or "unsure" keeps the case with a person
        f"sum(CASE WHEN NOT ({_DISAGREE}) AND {_BY_N} THEN 1 "
        f"WHEN {_DISAGREE} AND {_DECIDED_FIELD} = 'node_count' AND {_BY_N} THEN 1 "
        f"WHEN {_DISAGREE} AND {_DECIDED_FIELD} = 'pathologic_n' AND {_BY_COUNT} THEN 1 "
        "ELSE 0 END) AS node_positive_after_decisions, "
        f"sum(CASE WHEN {_DISAGREE} AND {_DECIDED_FIELD} NOT IN ('node_count', 'pathologic_n') "
        "THEN 1 ELSE 0 END) AS left_after_decisions, "
        f"sum(CASE WHEN {_DISAGREE} AND d.claim IS NOT NULL THEN 1 ELSE 0 END) "
        "AS decided_by_a_person "
        f"FROM {check} s LEFT JOIN {_latest_decisions()} ON s.case_id = d.case_id "
        f"WHERE {_BOTH_APPLY}"
    )


_DECIDED_FIELD = "coalesce(d.claim, fault_field)"


def _latest_decisions() -> str:
    """Each case's latest reviewer decision, as a subquery aliased d (append-only rows)."""
    flag = table_fqn("flag")
    return (
        f"(SELECT f.case_id AS case_id, f.severity AS claim FROM {flag} f JOIN "
        f"(SELECT case_id, max(created_at) AS latest FROM {flag} "
        "WHERE rule_id = 'human_review' GROUP BY case_id) m "
        "ON f.case_id = m.case_id AND f.created_at = m.latest "
        "WHERE f.rule_id = 'human_review') d"
    )


def write_snapshot(
    results: list[StepResult], meta: dict[str, Any], path: Path = SNAPSHOT
) -> Path | None:
    """Save steps 11-12 for sample mode, dated to this run; None if either step failed."""
    import json

    by_title = {r.step.title: r for r in results}
    board = by_title.get("One question, three answers")
    rows = by_title.get("Which answer the report supports")
    if not board or not rows or board.error or rows.error or not board.rows:
        return None
    numbers = {c: int(v) for c, v in zip(board.columns, board.rows[0], strict=True)}
    keep = [rows.columns.index(c) for c in _SNAPSHOT_COLUMNS]
    record = {
        "snapshot_of": f"usl demo {meta['run_at']} (docs/zetaris-demo.md steps 11-12)",
        "node_positive": numbers,
        "disagreeing_records": [
            dict(zip(_SNAPSHOT_COLUMNS, (row[i] for i in keep), strict=True)) for row in rows.rows
        ],
    }
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path
