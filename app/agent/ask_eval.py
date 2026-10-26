"""Pre-registered: "Ask the layer" on 12 frozen questions (docs/preregistration/ask-layer.md).

The questions and their expected answers are frozen in docs/preregistration/ask-layer.json before
the first call; the expected answers are computed by code from the live Zetaris layer (the same
read-only queries the tools run), not by a model. Each question goes once to the agent
(app/agent/ask.py: Nemotron Lightning, thinking off, tool calls through Meterless Nightshift,
every response's signed receipt checked, every number and case id in the answer checked against
the tool results). Scoring is lexical and frozen here: a number question is right when the
expected number appears in the shown answer; a field question when the shown answer names the
expected field. A refused answer is wrong. Nothing is stored.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent import ask as ask_mod
from app.engine.dial import sha16
from app.web.data import LiveData

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "docs" / "preregistration" / "ask-layer.json"
LOG = ROOT / "logs" / "ask-layer.jsonl"
RUNS_LOG = ROOT / "logs" / "ask-layer-runs.jsonl"
FROZEN_FILES = ("app/agent/ask.py", "app/agent/ask_eval.py")
FIELD_PATTERNS = {
    "node_count": r"count",
    "pathologic_n": r"\bN[- ]?stage\b|\bstage field\b|\bN category\b",
    "review": r"\bperson\b",
}


async def expected() -> list[dict[str, Any]]:
    data = LiveData()
    np = (await data.cohort()).get("node_positive") or {}
    groups = (await data.cohort()).get("groups") or []
    queue = await data.queue()
    by_case = {q["case_id"]: q for q in queue}

    def case(cid: str) -> dict[str, Any]:
        return by_case[cid]

    def num(v: Any) -> int:
        return int(float(v))

    return [
        {
            "q": "How many patients are node-positive according to the layer's checked answer?",
            "kind": "number",
            "want": np["node_positive_by_verdict"],
        },
        {
            "q": "How many patients are node-positive by the stage field?",
            "kind": "number",
            "want": np["node_positive_by_n_column"],
        },
        {
            "q": "How many patients are node-positive by the count field?",
            "kind": "number",
            "want": np["node_positive_by_count_column"],
        },
        {
            "q": "How many records does the layer's checked answer leave to a person?",
            "kind": "number",
            "want": np["left_to_a_person"],
        },
        {
            "q": "How many records cannot be true as written?",
            "kind": "number",
            "want": sum(g["n"] for g in groups if g.get("reason_class") == "n_count_contradiction"),
        },
        {"q": "How many records are in the review queue?", "kind": "number", "want": len(queue)},
        {
            "q": "Which field does the report contradict for TCGA-E2-A572?",
            "kind": "field",
            "want": case("TCGA-E2-A572")["fault_field"],
        },
        {
            "q": "How many positive lymph nodes does the pathology report state for TCGA-E2-A572?",
            "kind": "number",
            "want": num(case("TCGA-E2-A572")["report_nodes_positive"]),
        },
        {
            "q": "Which field does the report contradict for TCGA-AN-A0XN?",
            "kind": "field",
            "want": case("TCGA-AN-A0XN")["fault_field"],
        },
        {
            "q": "For TCGA-A2-A0EW, which field is wrong according to the layer?",
            "kind": "field",
            "want": case("TCGA-A2-A0EW")["fault_field"],
        },
        {
            "q": "How many positive lymph nodes does the registry record for TCGA-A2-A0CV?",
            "kind": "number",
            "want": num(case("TCGA-A2-A0CV")["lymph_nodes_positive"]),
        },
        {
            "q": "Which field does the report contradict for TCGA-A7-A26H?",
            "kind": "field",
            "want": case("TCGA-A7-A26H")["fault_field"],
        },
    ]


def right(item: dict[str, Any], answer: str | None) -> bool:
    if not answer:
        return False
    if item["kind"] == "number":
        return str(item["want"]) in re.findall(r"(?<![\w.-])\d+(?![\w-]|\.\d)", answer)
    pattern = FIELD_PATTERNS.get(str(item["want"]))
    return bool(pattern and re.search(pattern, answer, re.I))


async def freeze(prediction: str = "[fill]") -> dict[str, Any]:
    if RUNS_LOG.exists():
        raise RuntimeError("the run has happened; the pre-registration cannot be rewritten")
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in FROZEN_FILES},
        "model": ask_mod.MODEL,
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


async def run_ask_eval() -> dict[str, Any]:
    record = frozen()
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    rows = []
    for item in record["questions"]:
        row: dict[str, Any] = {"run": tag, **item}
        try:
            out = await ask_mod.ask(item["q"])
            row.update(
                answer=out["answer"],
                refused=out["refused"],
                unsupported=out["unsupported"],
                steps=out["steps"],
                right=right(item, out["answer"]),
                signed_lightning=all(
                    s.get("signature") == "verified" and s.get("model") == ask_mod.MODEL
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
