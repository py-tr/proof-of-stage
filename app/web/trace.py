"""How each value was read: the latest evidence-ladder run of a case, rung by rung.

Read from logs/markovian-chunks.jsonl (one row per rung). The page shows it next to the
stored values, which are first-write and may come from an earlier run. Only metadata and
the guard's verdicts are shown; the model's answer text is not.

Budget check. NVIDIA reports reasoning tokens on direct calls; Nightshift's usage does not,
so through Nightshift the check uses completion tokens: a rung is within budget when its
completion tokens are at most its thinking budget plus an answer allowance (observed answers
were 135-273 tokens; the allowance is about twice the largest).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_LOG = ROOT / "logs" / "markovian-chunks.jsonl"
ANSWER_ALLOWANCE = 600


def budget_check(budget: int, usage: dict[str, Any]) -> dict[str, Any]:
    """{"ok": bool | None, "how": str} for one rung's thinking budget."""
    details = usage.get("completion_tokens_details") or {}
    reasoning = details.get("reasoning_tokens")
    completion = usage.get("completion_tokens")
    if isinstance(reasoning, int):
        return {"ok": reasoning <= max(budget, 0), "how": f"{reasoning} reasoning tokens"}
    if isinstance(completion, int):
        cap = max(budget, 0) + ANSWER_ALLOWANCE
        return {"ok": completion <= cap, "how": f"{completion} completion tokens (cap {cap})"}
    return {"ok": None, "how": "no token count"}


def latest_trace(case_id: str, path: Path = CHUNKS_LOG) -> dict[str, Any] | None:
    """The latest ladder run of a case: one entry per rung, oldest rung first."""
    if not path.exists():
        return None
    runs: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("case") != case_id or not row.get("rung"):
            continue
        run_id = str(row.get("run_id"))
        if run_id not in runs:
            runs[run_id] = []
            order.append(run_id)
        runs[run_id].append(row)
    if not order:
        return None
    run_id = order[-1]
    rungs = []
    for row in sorted(runs[run_id], key=lambda r: r.get("step") or 0):
        usage = row.get("usage") or {}
        budget = int(row.get("budget") or 0)
        rungs.append(
            {
                "rung": row["rung"],
                "thinking": "off" if budget <= 0 else f"{budget} budget",
                "provider": "nightshift" if row.get("receipt_id") else "nvidia direct",
                "model": row.get("model"),
                "receipt_id": row.get("receipt_id"),
                "signature": row.get("signature"),
                "from_cache": row.get("from_cache"),
                "seconds": row.get("seconds"),
                "completion_tokens": usage.get("completion_tokens"),
                "budget": budget_check(budget, usage),
                "fields": {
                    name: {
                        "status": field.get("status"),
                        "value": field.get("value"),
                        # a rejection code only; an accepted field's reason is the model's text
                        "reason": field.get("reason") if field.get("status") != "accepted" else "",
                    }
                    for name, field in (row.get("fields") or {}).items()
                    if name in ("N", "NPOS")
                },
            }
        )
    return {"run_id": run_id, "rungs": rungs}
