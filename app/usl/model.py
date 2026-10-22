"""Names and columns for the stage_audit semantic layer."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = Path(__file__).resolve().parent / "sql"
RULES_CSV = ROOT / "data" / "reference" / "staging_rules.csv"
REPORTS_CSV = ROOT / "data" / "reports" / "path_reports.csv"

NAMESPACE = "lightning.metastore.registry_audit"
USL_NAME = "stage_audit"
USL_FQN = f"{NAMESPACE}.{USL_NAME}"
FILE_DB = "REG_FILES"
REST_DB = "GDC_REST"
PG_SOURCE = "oa_pg"
FILE_STORE_DIR = "stage_audit"
PG_CONTAINER = "oa-pg"
PG_DATABASE = "oa"
SQL_NODE_COUNT = "sql_node_count"

USL_TABLES = (
    "tumour_case",
    "path_report",
    "recorded_stage",
    "staging_rule",
    "derived_stage",
    "stage_check",
    "flag",
)

DQ_RULES = (
    "nodes_consistent",
    "stage_derivable_but_missing",
    "report_agrees",
    "edition_supported",
    "edition_matches_year",
)

ALLOWED_ROOTS = (
    "lightning.metastore.registry_audit",
    "REG_FILES",
    "GDC_REST",
    "oa_pg.flag_log",
    "oa_pg.derived_extraction",
)

EXTRACTION_COLUMNS = (
    "case_id",
    "method",
    "field",
    "value",
    "quote",
    "quote_start",
    "quote_end",
    "model",
    "receipt_id",
    "created_at",
)

FLAG_COLUMNS = (
    "flag_id",
    "case_id",
    "rule_id",
    "field",
    "recorded_value",
    "derived_value",
    "quote",
    "reason",
    "severity",
    "model",
    "receipt_id",
    "created_at",
)

REPORT_COLUMNS = ("report_id", "case_id", "report_text")


def table_fqn(table: str) -> str:
    return f"{USL_FQN}.{table}"


def allowed_name(name: str) -> bool:
    """True when a SQL name is the metastore namespace or one of our databases."""
    lowered = name.strip("`").lower()
    for root in ALLOWED_ROOTS:
        root_lower = root.lower()
        if lowered == root_lower or lowered.startswith(root_lower + "."):
            return True
    return False
