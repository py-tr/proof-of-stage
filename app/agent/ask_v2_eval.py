"""Pre-registered: "Ask the layer" v2 on 12 new questions (docs/preregistration/ask-layer-v2.md).

Same frozen scoring rules as v1 (app/agent/ask_eval.py `right`), same bar. Nine case questions name
cases v1 never asked about; three aggregate questions are new wordings over the same tools.
Expected answers are computed by code from the live layer before the first call. Nothing is stored.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent import ask_v2
from app.agent.ask_eval import right
from app.engine.dial import sha16
from app.web.data import LiveData

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ask-layer-v2.json"
LOG = ROOT / "logs" / "ask-layer-v2.jsonl"
RUNS_LOG = ROOT / "logs" / "ask-layer-v2-runs.jsonl"
FROZEN_FILES = (
    "app/agent/ask.py",
    "app/agent/ask_v2.py",
    "app/agent/ask_eval.py",
    "app/agent/ask_v2_eval.py",
)


async def expected() -> list[dict[str, Any]]:
    data = LiveData()
    np = (await data.cohort()).get("node_positive") or {}
    queue = await data.queue()
    q = {r["case_id"]: r for r in queue}

    def num(v: Any) -> int:
        return int(float(v))

    return [
        {
            "q": "Which field does the report contradict for TCGA-3C-AAAU?",
            "kind": "field",
            "want": q["TCGA-3C-AAAU"]["fault_field"],
        },
        {
            "q": "Which field does the report contradict for TCGA-A7-A26E?",
            "kind": "field",
            "want": q["TCGA-A7-A26E"]["fault_field"],
        },
        {
            "q": "For TCGA-AR-A1AT, which field is wrong according to the layer?",
            "kind": "field",
            "want": q["TCGA-AR-A1AT"]["fault_field"],
        },
        {
            "q": "How many positive lymph nodes does the pathology report state for TCGA-AQ-A1H2?",
            "kind": "number",
            "want": num(q["TCGA-AQ-A1H2"]["report_nodes_positive"]),
        },
        {
            "q": "How many positive lymph nodes does the pathology report state for TCGA-BH-A0BS?",
            "kind": "number",
            "want": num(q["TCGA-BH-A0BS"]["report_nodes_positive"]),
        },
        {
            "q": "How many positive lymph nodes does the registry record for TCGA-AC-A2FK?",
            "kind": "number",
            "want": num(q["TCGA-AC-A2FK"]["lymph_nodes_positive"]),
        },
        {
            "q": "How many positive lymph nodes does the registry record for TCGA-E9-A3X8?",
            "kind": "number",
            "want": num(q["TCGA-E9-A3X8"]["lymph_nodes_positive"]),
        },
        {
            "q": "Which field does the report contradict for TCGA-BH-A0DD?",
            "kind": "field",
            "want": q["TCGA-BH-A0DD"]["fault_field"],
        },
        {
            "q": "Which field does the report contradict for TCGA-EW-A424?",
            "kind": "field",
            "want": q["TCGA-EW-A424"]["fault_field"],
        },
        {
            "q": "On how many records do both the stage field and the count field apply?",
            "kind": "number",
            "want": np["records"],
        },
        {
            "q": "How many records does the layer flag for review?",
            "kind": "number",
            "want": len(queue),
        },
        {
            "q": "Where both fields apply, how many node-positive patients does the layer's checked answer count?",
            "kind": "number",
            "want": np["node_positive_by_verdict"],
        },
    ]


async def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "model": ask_v2.v1.MODEL,
        "questions": await expected(),
        "claim": "at least 10 of 12 shown answers right, and every model response carries a verified signed Nightshift receipt naming Lightning",
        "kill": "fewer than 8 of 12 right, or any response not signed by the pinned key or not answered by Lightning",
        "void": "more than 3 provider failures",
        "prediction": prediction,
    }
    PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def frozen() -> dict[str, Any]:
    record = json.loads(PREREG.read_text(encoding="utf-8"))
    changed = [
        p
        for p, d in record["code_sha256_16"].items()
        if sha16((ROOT / p).read_text(encoding="utf-8")) != d
    ]
    if changed:
        raise RuntimeError("pre-registration does not match: changed " + ", ".join(changed))
    if "[fill]" in str(record.get("prediction")):
        raise RuntimeError("write the prediction before the run")
    if RUNS_LOG.exists():
        raise RuntimeError("already run once; never re-run")
    return record


async def run() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for item in record["questions"]:
        row: dict[str, Any] = {"run": tag, **item}
        try:
            out = await ask_v2.ask(item["q"])
            row.update(
                answer=out["answer"],
                refused=out["refused"],
                unsupported=out["unsupported"],
                missing_case_verdict=out.get("missing_case_verdict"),
                steps=out["steps"],
                right=right(item, out["answer"]),
                signed_lightning=all(
                    s.get("signature") == "verified" and s.get("model") == ask_v2.v1.MODEL
                    for s in out["steps"]
                ),
            )
        except Exception as exc:  # a provider failure or a refused receipt: logged, never re-run
            row["failure"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            row["right"] = False
        rows.append(row)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    failures = sum("failure" in r for r in rows)
    summary = {
        "run": tag,
        "questions": len(rows),
        "right": sum(r["right"] for r in rows),
        "refused": sum(bool(r.get("refused")) for r in rows),
        "failures": failures,
        "all_signed_lightning": all(r.get("signed_lightning") for r in rows if "failure" not in r),
        "tool_calls": sum(len(s.get("tool_calls", [])) for r in rows for s in r.get("steps", [])),
    }
    summary["void"] = failures > 3
    summary["kill"] = summary["right"] < 8 or not summary["all_signed_lightning"]
    summary["claim_met"] = (
        not summary["void"] and summary["right"] >= 10 and summary["all_signed_lightning"]
    )
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    return summary
