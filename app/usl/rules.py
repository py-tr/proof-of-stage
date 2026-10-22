"""Paraphrased staging rules and the reference CSV written from them."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from app.usl.errors import SetupError
from app.usl.model import REPORT_COLUMNS, RULES_CSV

FIELDNAMES = (
    "rule_id",
    "site",
    "element",
    "edition",
    "condition_text",
    "min_value",
    "max_value",
    "output",
    "cite",
)


@dataclass(frozen=True)
class StagingRule:
    rule_id: str
    site: str
    element: str
    edition: str
    condition_text: str
    output: str
    cite: str
    min_value: str = ""
    max_value: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "site": self.site,
            "element": self.element,
            "edition": self.edition,
            "condition_text": self.condition_text,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "output": self.output,
            "cite": self.cite,
        }


def _rule(
    rule_id: str,
    site: str,
    element: str,
    edition: str,
    condition_text: str,
    output: str,
    cite: str,
    min_value: str = "",
    max_value: str = "",
) -> StagingRule:
    return StagingRule(
        rule_id=rule_id,
        site=site,
        element=element,
        edition=edition,
        condition_text=condition_text,
        output=output,
        cite=cite,
        min_value=min_value,
        max_value=max_value,
    )


# Inclusive numeric bounds. A strict size cutoff is stored 0.01 mm past the cutoff.
# Empty min/max means the rule is not a pure count or size window.
# Edition is a comma-separated list of edition numbers. Rows are checked top-down.
RULES: tuple[StagingRule, ...] = (
    _rule(
        "BT1",
        "breast",
        "T",
        "6,7,8",
        "No tumour can be assessed",
        "TX",
        "PDQ-B; NCIt C48972",
    ),
    _rule(
        "BT2",
        "breast",
        "T",
        "6,7,8",
        "No residual or primary tumour was found",
        "T0",
        "PDQ-B; NCIt C48973",
    ),
    _rule(
        "BT3",
        "breast",
        "T",
        "6,7,8",
        "In situ disease only, ductal carcinoma in situ",
        "Tis(DCIS)",
        "PDQ-B; NCIt C48975/C139414",
    ),
    _rule(
        "BT4",
        "breast",
        "T",
        "6,7",
        "In situ disease only, lobular carcinoma in situ",
        "Tis(LCIS)",
        "NCIt C48976, C139414",
    ),
    _rule(
        "BT4-8",
        "breast",
        "T",
        "8",
        "Lobular carcinoma in situ alone is not staged as malignant",
        "not staged",
        "NCIt C48976, C139414",
    ),
    _rule(
        "BT5",
        "breast",
        "T",
        "6,7,8",
        "Paget disease of the nipple without underlying invasive carcinoma or DCIS",
        "Tis(Paget)",
        "PDQ-B; NCIt C48977/C139415",
    ),
    _rule(
        "BT6",
        "breast",
        "T",
        "6,7,8",
        "Clinically diagnosed inflammatory carcinoma",
        "T4d",
        "PDQ-B; NCIt C48989/C139427; SEER-T",
    ),
    _rule(
        "BT7",
        "breast",
        "T",
        "6,7,8",
        "Chest-wall invasion (not pectoralis alone) together with ulceration, "
        "satellite skin nodules, or skin oedema",
        "T4c",
        "NCIt C48988/C139426",
    ),
    _rule(
        "BT8",
        "breast",
        "T",
        "6,7,8",
        "Chest-wall invasion (not pectoralis alone) without ulceration, "
        "satellite skin nodules, or skin oedema",
        "T4a",
        "PDQ-B; NCIt C48986/C139424; SEER-T",
    ),
    _rule(
        "BT9",
        "breast",
        "T",
        "6,7,8",
        "Ulceration, satellite skin nodules, or skin oedema without chest-wall invasion "
        "and not inflammatory. In the 8th edition the nodules must be macroscopic",
        "T4b",
        "NCIt C48987/C139425",
    ),
    _rule(
        "BT10",
        "breast",
        "T",
        "6,7,8",
        "Largest invasive focus is greater than 50 mm",
        "T3",
        "PDQ-B",
        min_value="50.01",
    ),
    _rule(
        "BT11",
        "breast",
        "T",
        "6,7,8",
        "Largest invasive focus is greater than 20 mm and at most 50 mm",
        "T2",
        "PDQ-B",
        min_value="20.01",
        max_value="50",
    ),
    _rule(
        "BT12",
        "breast",
        "T",
        "6,7,8",
        "Largest invasive focus is greater than 10 mm and at most 20 mm",
        "T1c",
        "PDQ-B",
        min_value="10.01",
        max_value="20",
    ),
    _rule(
        "BT13",
        "breast",
        "T",
        "6,7,8",
        "Largest invasive focus is greater than 5 mm and at most 10 mm",
        "T1b",
        "PDQ-B",
        min_value="5.01",
        max_value="10",
    ),
    _rule(
        "BT14",
        "breast",
        "T",
        "6,7,8",
        "Largest invasive focus is greater than 1 mm and at most 5 mm. "
        "A size above 1 mm and below 2 mm is taken as 2 mm",
        "T1a",
        "PDQ-B; SEER-M breast rounding",
        min_value="1.01",
        max_value="5",
    ),
    _rule(
        "BT15-67",
        "breast",
        "T",
        "6,7",
        "Largest invasive focus is 1 mm or smaller (microinvasion)",
        "T1mic",
        "NCIt C139417/C48979",
        max_value="1",
    ),
    _rule(
        "BT15-8",
        "breast",
        "T",
        "8",
        "Largest invasive focus is 1 mm or smaller (microinvasion)",
        "T1mi",
        "NCIt C139417/C48979",
        max_value="1",
    ),
    _rule(
        "BT-NOT",
        "breast",
        "T",
        "6,7,8",
        "Dermal invasion, nipple involvement, Paget disease with underlying invasion, "
        "pectoralis invasion, or dermal lymphatic invasion does not by itself change T",
        "",
        "PDQ-B; NCIt C139423, C139415, C48985",
    ),
    _rule(
        "BN1",
        "breast",
        "N",
        "6,7,8",
        "No regional nodes were removed or examined",
        "pNX",
        "PDQ-B; NCIt C48990",
    ),
    _rule(
        "BN2",
        "breast",
        "N",
        "6,7,8",
        "An ipsilateral supraclavicular node is positive",
        "pN3c",
        "PDQ-B; NCIt C49007",
    ),
    _rule(
        "BN3",
        "breast",
        "N",
        "6,7,8",
        "Ten or more positive axillary nodes with a macrometastasis, "
        "or a positive infraclavicular node",
        "pN3a",
        "PDQ-B; NCIt C49005",
        min_value="10",
    ),
    _rule(
        "BN4",
        "breast",
        "N",
        "6,7,8",
        "Internal mammary nodes are clinically positive and at least one axillary node "
        "is positive, or four or more axillary nodes are positive and an internal "
        "mammary sentinel node is positive",
        "pN3b",
        "NCIt C49006, C88362, C139443",
    ),
    _rule(
        "BN5",
        "breast",
        "N",
        "6,7,8",
        "Four to nine positive axillary nodes with a macrometastasis",
        "pN2a",
        "PDQ-B; NCIt C49002",
        min_value="4",
        max_value="9",
    ),
    _rule(
        "BN6",
        "breast",
        "N",
        "6,7,8",
        "Internal mammary nodes are clinically positive and no axillary node is positive",
        "pN2b",
        "NCIt C49003, C88360, C139440",
    ),
    _rule(
        "BN7",
        "breast",
        "N",
        "6,7,8",
        "One to three positive axillary nodes with a macrometastasis and an internal "
        "mammary sentinel node is positive, excluding isolated tumour cells",
        "pN1c",
        "PDQ-B; NCIt C49000, C139437",
    ),
    _rule(
        "BN8",
        "breast",
        "N",
        "6,7,8",
        "An internal mammary sentinel node is positive and no axillary node is positive",
        "pN1b",
        "PDQ-B; NCIt C48999, C139436",
    ),
    _rule(
        "BN9",
        "breast",
        "N",
        "6,7,8",
        "One to three positive axillary nodes with a macrometastasis",
        "pN1a",
        "PDQ-B; NCIt C48998",
        min_value="1",
        max_value="3",
    ),
    _rule(
        "BN10",
        "breast",
        "N",
        "6,7,8",
        "Every positive deposit is larger than 0.2 mm and at most 2.0 mm",
        "pN1mi",
        "PDQ-B; NCIt C48997, C88353, C139434",
    ),
    _rule(
        "BN11",
        "breast",
        "N",
        "6,7,8",
        "Only isolated tumour cells 0.2 mm or smaller",
        "pN0(i+)",
        "PDQ-B; NCIt C48993, C88351",
    ),
    _rule(
        "BN12",
        "breast",
        "N",
        "6,7,8",
        "Positive by RT-PCR only",
        "pN0(mol+)",
        "PDQ-B; NCIt C48995",
    ),
    _rule(
        "BN13",
        "breast",
        "N",
        "6,7,8",
        "Nodes were examined and all are negative",
        "pN0",
        "PDQ-B",
        min_value="0",
        max_value="0",
    ),
    _rule(
        "BN-REVIEW",
        "breast",
        "N",
        "",
        "Four or more positive nodes without a deposit over 2 mm, a count stated only "
        "as at least, or an unknown internal mammary detection method",
        "UNRESOLVED",
        "gap in public sources",
    ),
    _rule(
        "BN-suffix",
        "breast",
        "N",
        "8",
        "Sentinel-biopsy-only nodes add the (sn) suffix, FNA or core sampling adds (f), "
        "and neoadjuvant therapy adds the yp prefix",
        "suffix/prefix",
        "PDQ-B Table 3 note b, Table 8 note",
    ),
    _rule(
        "CT1-TX",
        "colon",
        "T",
        "6,7,8",
        "The tumour cannot be assessed",
        "TX",
        "PDQ-C",
    ),
    _rule(
        "CT1-T0",
        "colon",
        "T",
        "6,7,8",
        "No tumour was found",
        "T0",
        "PDQ-C",
    ),
    _rule(
        "CT2",
        "colon",
        "T",
        "6,7,8",
        "Confined to the epithelium or lamina propria and not through the muscularis mucosae",
        "Tis",
        "PDQ-C; NCIt C60841, C89944",
    ),
    _rule(
        "CT3-78",
        "colon",
        "T",
        "7,8",
        "Directly invades or adheres to another organ or structure. "
        "An adhesion counts only when microscopy shows tumour in it",
        "T4b",
        "PDQ-C; NCIt C60849, C89947",
    ),
    _rule(
        "CT3-6",
        "colon",
        "T",
        "6",
        "Directly invades or adheres to another organ or structure. "
        "An adhesion counts only when microscopy shows tumour in it",
        "T4",
        "PDQ-C; NCIt C60849",
    ),
    _rule(
        "CT4-78",
        "colon",
        "T",
        "7,8",
        "Through the visceral peritoneum, including perforation or tumour on the serosal surface",
        "T4a",
        "NCIt C134164, C89946; PMC-6",
    ),
    _rule(
        "CT4-6",
        "colon",
        "T",
        "6",
        "Through the visceral peritoneum, including perforation or tumour on the serosal surface",
        "T4",
        "NCIt C134164; PMC-6",
    ),
    _rule(
        "CT5",
        "colon",
        "T",
        "6,7,8",
        "Through the muscularis propria into pericolorectal fat or subserosa",
        "T3",
        "PDQ-C; NCIt C89945",
    ),
    _rule(
        "CT6",
        "colon",
        "T",
        "6,7,8",
        "Into the muscularis propria",
        "T2",
        "PDQ-C",
    ),
    _rule(
        "CT7",
        "colon",
        "T",
        "6,7,8",
        "Into the submucosa but not into the muscularis propria",
        "T1",
        "PDQ-C",
    ),
    _rule(
        "CT-NOTE",
        "colon",
        "T",
        "6",
        "A T4a or T4b letter in a 6th-edition report is ignored and T is derived "
        "from the invaded structure",
        "",
        "NCIt C78695/C78696 vs C89946/C89947",
    ),
    _rule(
        "CN1",
        "colon",
        "N",
        "6,7,8",
        "No nodes were examined",
        "NX",
        "PDQ-C",
    ),
    _rule(
        "CN2-78",
        "colon",
        "N",
        "7,8",
        "Seven or more positive nodes",
        "N2b",
        "PDQ-C; NCIt C89955, C60853",
        min_value="7",
    ),
    _rule(
        "CN2-6",
        "colon",
        "N",
        "6",
        "Seven or more positive nodes",
        "N2",
        "PDQ-C; NCIt C60853",
        min_value="7",
    ),
    _rule(
        "CN3-78",
        "colon",
        "N",
        "7,8",
        "Four to six positive nodes",
        "N2a",
        "PDQ-C; NCIt C89954",
        min_value="4",
        max_value="6",
    ),
    _rule(
        "CN3-6",
        "colon",
        "N",
        "6",
        "Four to six positive nodes",
        "N2",
        "PDQ-C",
        min_value="4",
        max_value="6",
    ),
    _rule(
        "CN4-78",
        "colon",
        "N",
        "7,8",
        "Two or three positive nodes",
        "N1b",
        "PDQ-C; NCIt C89951, C60852",
        min_value="2",
        max_value="3",
    ),
    _rule(
        "CN4-6",
        "colon",
        "N",
        "6",
        "Two or three positive nodes",
        "N1",
        "PDQ-C; NCIt C60852",
        min_value="2",
        max_value="3",
    ),
    _rule(
        "CN5-78",
        "colon",
        "N",
        "7,8",
        "Exactly one positive node",
        "N1a",
        "PDQ-C; NCIt C89950",
        min_value="1",
        max_value="1",
    ),
    _rule(
        "CN5-6",
        "colon",
        "N",
        "6",
        "Exactly one positive node",
        "N1",
        "PDQ-C",
        min_value="1",
        max_value="1",
    ),
    _rule(
        "CN6-78",
        "colon",
        "N",
        "7,8",
        "No positive nodes and tumour deposits are present",
        "N1c",
        "PDQ-C; NCIt C89952; UENO",
    ),
    _rule(
        "CN6-6",
        "colon",
        "N",
        "6",
        "A smooth node-shaped deposit counts as a positive node. An irregular deposit changes T",
        "",
        "PDQ-C; UENO",
    ),
    _rule(
        "CN6-5",
        "colon",
        "N",
        "5",
        "A deposit larger than 3 mm counts as a positive node",
        "",
        "UENO",
    ),
    _rule(
        "CN7",
        "colon",
        "N",
        "6,7,8",
        "No positive nodes and no tumour deposits",
        "N0",
        "PDQ-C",
        min_value="0",
        max_value="0",
    ),
    _rule(
        "CN-FLAG",
        "colon",
        "N",
        "6,7,8",
        "N0 with fewer than 12 nodes examined is a quality flag and does not change the category",
        "flag",
        "PDQ-C",
    ),
    _rule(
        "CN-REVIEW",
        "colon",
        "N",
        "",
        "A count stated only as at least, while more than one category is still possible",
        "UNRESOLVED",
        "SEER-M code 97",
    ),
)


def staging_rule_rows() -> list[dict[str, str]]:
    rows = [rule.as_row() for rule in RULES]
    ids = [row["rule_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate staging rule id")
    return rows


def write_staging_rules(path: Path | None = None) -> Path:
    target = path or RULES_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(FIELDNAMES),
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(staging_rule_rows())
    return target


def require_columns(path: Path, columns: tuple[str, ...] | list[str]) -> None:
    """Accept a header-only CSV. Reject a missing header or a missing column."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SetupError(f"{path.name} is empty") from exc
    missing = [column for column in columns if column not in header]
    if missing:
        raise SetupError(f"{path.name} is missing columns: {', '.join(missing)}")


def ensure_csv(path: Path, columns: tuple[str, ...]) -> None:
    """Create a header-only CSV if it does not exist yet (a filestore table needs the file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(columns) + "\n", encoding="utf-8")


def ensure_path_reports_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(REPORT_COLUMNS) + "\n", encoding="utf-8")
    require_columns(path, REPORT_COLUMNS)
