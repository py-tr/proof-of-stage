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
            "Evidence on the original scan",
            "the block Nemotron Parse read, with its box, for the hero case",
            "SELECT case_id, page_no, block_text, xmin, ymin, xmax, ymax "
            f"FROM {table_fqn('parse_block')} "
            "WHERE case_id = 'TCGA-A2-A0CV' AND block_text LIKE '%2/18%'",
        ),
    ]
    return out


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
