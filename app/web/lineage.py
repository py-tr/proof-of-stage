"""Which USL data-quality rules flag a case, and the rule text itself (the lineage panel).

Live mode asks Zetaris (SHOW DQ INVALID RECORD per rule, cached). Sample mode has no
Zetaris, so it evaluates the Python mirror in app/usl/dq.py and says so.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.usl import dq
from app.usl.client import invalid_records
from app.usl.model import table_fqn
from app.usl.sqltext import load_statements

# The rules shown on the page, with the file that registers each one.
PAGE_RULES = {
    "nodes_consistent": "060_dq_nodes_consistent.sql",
    "stage_derivable_but_missing": "061_dq_stage_derivable_but_missing.sql",
    "fault_named": "065_dq_fault_named.sql",
    "fault_unresolved": "066_dq_fault_unresolved.sql",
}
_MIRROR = {
    "nodes_consistent": dq.nodes_consistent_valid,
    "stage_derivable_but_missing": dq.stage_derivable_but_missing_valid,
    "fault_named": dq.fault_named_valid,
    "fault_unresolved": dq.fault_unresolved_valid,
}
# Sample mode has no Zetaris; live mode reads the same lineage from the USL contract.
SOURCES = (
    ("tumour_case", "GDC_REST.brca_cases_raw", "REST API (NCI GDC), cached"),
    ("recorded_stage", "GDC_REST.brca_cases_raw", "REST API (NCI GDC), cached"),
    ("staging_rule", "REG_FILES staging_rules.csv", "file store, paraphrased rules"),
    ("path_report", "REG_FILES path_reports.csv", "file store, report text"),
    ("derived_stage", "oa_pg.derived_extraction", "Postgres, append-only reader output"),
    ("flag", "oa_pg.flag_log", "Postgres, append-only review log"),
    ("parse_block", "REG_FILES parse_blocks.csv", "file store, Nemotron Parse blocks"),
)
_SOURCE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)
_KINDS = (
    ("GDC_REST.", "REST API (NCI GDC), cached"),
    ("REG_FILES.", "file store"),
    ("oa_pg.", "Postgres, append-only"),
    ("lightning.metastore.", "USL table"),
)


def _kind(source: str) -> str:
    return next((kind for prefix, kind in _KINDS if source.startswith(prefix)), "source")


def contract_lineage(contract: Any) -> list[dict[str, str]]:
    """Each USL table's inputs, read from its activation query in the LOAD USL contract."""
    rows = []
    tables = contract.get("tables") if isinstance(contract, dict) else None
    for table in tables or []:
        if not isinstance(table, dict):
            continue
        query = str(table.get("activateQuery") or "")
        for source in sorted(set(_SOURCE.findall(query))):
            short = source.rsplit(".", 1)[-1] if source.startswith("lightning.") else source
            rows.append(
                {"usl_table": str(table.get("name")), "source": short, "kind": _kind(source)}
            )
    return rows


_CACHE_S = 300.0
_MIN_REFRESH_S = 30.0  # a lasting SQL/mirror difference must not refetch every load


def rule_expression(rule: str) -> str:
    statement = load_statements(PAGE_RULES[rule])[0]
    return re.split(r"\bAS\b", statement, maxsplit=1)[1].strip()


class LiveLineage:
    source = "Zetaris RUN DQ (SHOW DQ INVALID RECORD)"
    sources_from = "LOAD USL contract (activation queries)"

    def __init__(self) -> None:
        self._hits: dict[str, set[str]] = {}
        self._at = 0.0
        self._lineage: list[dict[str, str]] | None = None

    async def sources(self) -> list[dict[str, str]]:
        if self._lineage is None:
            from app.usl.client import load_contract

            self._lineage = contract_lineage(await load_contract()) or None
        return self._lineage or _static_sources()

    async def _refresh(self) -> None:
        if self._hits and time.monotonic() - self._at < _CACHE_S:
            return
        hits = {}
        for rule in PAGE_RULES:
            result = await invalid_records(rule, limit=2000)
            index = result.columns.index("case_id") if "case_id" in result.columns else 0
            hits[rule] = {str(row[index]).upper() for row in result.rows if row}
        self._hits, self._at = hits, time.monotonic()

    def forget(self) -> None:
        self._at = 0.0

    async def warm(self) -> None:
        """Fill the cache at startup so the first case does not wait for four DQ calls."""
        try:
            await self._refresh()
        except Exception:  # the page reports Zetaris errors when a case is opened
            return

    async def failed_rules(self, case_id: str, check: dict[str, Any]) -> list[str]:
        await self._refresh()
        hits = [rule for rule in PAGE_RULES if case_id in self._hits.get(rule, set())]
        if hits != _mirror(check) and time.monotonic() - self._at > _MIN_REFRESH_S:
            # The reader may have written since the cache was filled: ask Zetaris again once.
            self.forget()
            await self._refresh()
            hits = [rule for rule in PAGE_RULES if case_id in self._hits.get(rule, set())]
        return hits


def _mirror(check: dict[str, Any]) -> list[str]:
    return [rule for rule, valid in _MIRROR.items() if not valid(check)]


def _static_sources() -> list[dict[str, str]]:
    return [{"usl_table": t, "source": origin, "kind": kind} for t, origin, kind in SOURCES]


class MirrorLineage:
    source = "Python mirror of the USL rules (sample mode: no Zetaris)"
    sources_from = "static list (sample mode: no Zetaris)"

    async def sources(self) -> list[dict[str, str]]:
        return _static_sources()

    def forget(self) -> None:
        return None

    async def warm(self) -> None:
        return None

    async def failed_rules(self, case_id: str, check: dict[str, Any]) -> list[str]:
        return _mirror(check)


async def lineage(source: LiveLineage | MirrorLineage, check: dict[str, Any]) -> dict[str, Any]:
    case_id = str(check.get("case_id"))
    failed = await source.failed_rules(case_id, check)
    mirror = _mirror(check)
    return {
        "evaluated_by": source.source,
        # differs only if Zetaris and the Python mirror disagree even after a refresh
        "mirror_disagrees": failed != mirror,
        "table": table_fqn("stage_check"),
        "failed": [{"rule": rule, "expression": rule_expression(rule)} for rule in failed],
        "sources": await source.sources(),
        "sources_from": source.sources_from,
    }
