from __future__ import annotations

import csv
import re

import pytest

from app.usl.errors import SetupError
from app.usl.model import REPORT_COLUMNS, RULES_CSV
from app.usl.rules import (
    ensure_path_reports_file,
    require_columns,
    staging_rule_rows,
    write_staging_rules,
)


def _by_id() -> dict[str, dict[str, str]]:
    return {row["rule_id"]: row for row in staging_rule_rows()}


def test_staging_rules_encode_the_paraphrased_thresholds() -> None:
    rows = staging_rule_rows()
    assert [row["rule_id"] for row in rows] == list(dict.fromkeys(row["rule_id"] for row in rows))
    ids = {row["rule_id"] for row in rows}
    for prefix in ("BT", "BN", "CT", "CN"):
        assert any(rule_id.startswith(prefix) for rule_id in ids)
    rules = _by_id()
    bn5 = rules["BN5"]
    assert bn5["site"] == "breast"
    assert bn5["element"] == "N"
    assert bn5["min_value"] == "4"
    assert bn5["max_value"] == "9"
    assert bn5["output"] == "pN2a"
    assert float(rules["BT10"]["min_value"]) > 50
    assert rules["BT10"]["max_value"] == ""
    assert rules["BT10"]["output"] == "T3"
    assert float(rules["BT11"]["min_value"]) > 20
    assert float(rules["BT11"]["max_value"]) == 50
    assert rules["BT11"]["output"] == "T2"
    assert rules["BT4"]["output"] == "Tis(LCIS)"
    assert rules["BT4"]["edition"] == "6,7"
    assert rules["BT4-8"]["output"] == "not staged"
    assert rules["BT4-8"]["edition"] == "8"
    assert rules["CN2-6"]["output"] == "N2"
    assert rules["CN2-6"]["edition"] == "6"
    assert rules["CN2-6"]["min_value"] == "7"
    assert rules["CN2-78"]["output"] == "N2b"
    assert rules["CN2-78"]["edition"] == "7,8"
    assert rules["BN13"]["min_value"] == "0"
    assert rules["BN13"]["max_value"] == "0"
    assert rules["CN7"]["output"] == "N0"
    assert rules["BN1"]["output"] == "pNX"
    assert rules["CN1"]["output"] == "NX"
    for row in rows:
        assert row["site"] in {"breast", "colon"}
        assert row["element"] in {"T", "N"}
        assert row["condition_text"].strip()
        assert row["cite"].strip()
        assert len(row["condition_text"]) < 400
        assert re.fullmatch(r"[0-9,]*", row["edition"])
        for bound in ("min_value", "max_value"):
            if row[bound]:
                float(row[bound])
        assert "AJCC Cancer Staging Manual" not in row["condition_text"]
        assert "All Rights Reserved" not in row["condition_text"]


def test_committed_csv_matches_generator() -> None:
    with RULES_CSV.open(encoding="utf-8", newline="") as handle:
        committed = list(csv.DictReader(handle))
    assert committed == staging_rule_rows()


def test_write_roundtrip(tmp_path) -> None:
    path = write_staging_rules(tmp_path / "staging_rules.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written == staging_rule_rows()
    assert list(written[0]) == [
        "rule_id",
        "site",
        "element",
        "edition",
        "condition_text",
        "min_value",
        "max_value",
        "output",
        "cite",
    ]


def test_header_only_report_file_is_accepted(tmp_path) -> None:
    path = tmp_path / "path_reports.csv"
    path.write_text("report_id,case_id,report_text\n", encoding="utf-8")
    require_columns(path, REPORT_COLUMNS)
    missing = tmp_path / "missing"
    ensure_path_reports_file(missing / "path_reports.csv")
    require_columns(missing / "path_reports.csv", REPORT_COLUMNS)
    bad = tmp_path / "bad.csv"
    bad.write_text("report_id\n", encoding="utf-8")
    with pytest.raises(SetupError, match="missing columns"):
        require_columns(bad, REPORT_COLUMNS)
