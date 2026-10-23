"""The red-team chain on the /how page: one pre-registered v3 chain, step by step, from the logs.

Read from logs/adversary-runs.jsonl and logs/adversary-steps.jsonl (written by
app/engine/adversary.py); the cases come from docs/preregistration/adversary-cases-v3.json.
For each v3 case, the latest completed Nightshift run is shown: per step the attack (a wrong
count and its quote), the real guard's verdict, whether it repeated an earlier attack, and the
receipt. Measured evidence only, no model call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CASES_V3 = ROOT / "docs" / "preregistration" / "adversary-cases-v3.json"
RUNS = ROOT / "logs" / "adversary-runs.jsonl"
STEPS = ROOT / "logs" / "adversary-steps.jsonl"
QUOTE_CHARS = 120


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def v3_chains(cases: Path = CASES_V3, runs: Path = RUNS, steps: Path = STEPS) -> list[dict]:
    frozen = json.loads(cases.read_text(encoding="utf-8"))
    truth = {c["case_id"]: c["true_count"] for c in frozen["cases"]}
    latest: dict[str, dict[str, Any]] = {}
    for run in _rows(runs):
        if (
            run.get("case") in truth
            and run.get("provider") == frozen["provider"]
            and run.get("engine_status") == "completed"
        ):
            latest[run["case"]] = run
    by_run: dict[str, list[dict[str, Any]]] = {}
    for step in _rows(steps):
        by_run.setdefault(str(step.get("run_id")), []).append(step)
    chains = []
    for case_id in truth:
        run = latest.get(case_id)
        if run is None:
            continue
        rows = sorted(by_run.get(run["run_id"], []), key=lambda s: s.get("step") or 0)
        chains.append(
            {
                "case": case_id,
                "run_id": run["run_id"],
                "true_count": truth[case_id],
                "thinking_budget": frozen["thinking_budget"],
                "verdicts": run.get("verdicts") or {},
                "accepts_wrong": run.get("accepts_wrong"),
                "repeats": run.get("carryover_failures"),
                "prompt_tokens_measured": run.get("markovian_prompt_tokens_measured"),
                "tokens_saved_est": run.get("tokens_saved_est"),
                "engine_tokens_saved": run.get("engine_tokens_saved_estimate"),
                "steps": [
                    {
                        "step": s.get("step"),
                        "value": s.get("value"),
                        "quote": (s.get("quote") or "")[:QUOTE_CHARS],
                        "verdict": s.get("verdict"),
                        "repeat": s.get("repeat"),
                        "signature": s.get("signature"),
                        "seconds": s.get("seconds"),
                        "ledger_est_tokens": s.get("ledger_est_tokens"),
                        "history_est_tokens": s.get("history_est_tokens"),
                    }
                    for s in rows
                ],
            }
        )
    return chains
