"""Record Nemotron Super's scratchpad (its reasoning text) on one case, as evidence.

One call with the reader's own prompt and the deep rung's 4k thinking budget, on NVIDIA
directly (its response carries the reasoning in `reasoning_content`; the product's clients
drop it). The full response is saved to docs/evidence/scratchpads/<case>.json. The page
shows short excerpts from it, labelled as one recorded call: the proof of a value stays its
quote and the guard; the scratchpad shows how the model got there.

Usage: python scripts/record_scratchpad.py TCGA-A2-A0CV
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app import config
from app.providers import nvidia
from app.reader.reader import (
    REPORT_CHARS,
    SYSTEM_PROMPT,
    THINKING_BUDGET,
    judge_count,
    judge_field,
    parse_answer,
    thinking_args,
)
from app.reports.ingest import read_reports_csv

OUT = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "scratchpads"


async def record(case_id: str) -> Path:
    report = read_reports_csv()[case_id].report_text
    extra, max_tokens = thinking_args(THINKING_BUDGET)
    body = {
        "model": config.NV_SUPER,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Pathology report:\n\n" + report[:REPORT_CHARS]},
        ],
        "max_tokens": max_tokens,
        **extra,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers["Authorization"] = f"Bearer {config.getenv('NVIDIA_API_KEY')}"
    payload = await nvidia._post(headers, body)
    message = payload["choices"][0]["message"]
    answer = parse_answer(message.get("content") or "")
    record = {
        "case_id": case_id,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": "nvidia direct",
        "requested_model": config.NV_SUPER,
        "served_model": payload.get("model"),
        "thinking_budget": THINKING_BUDGET,
        "usage": payload.get("usage"),
        "answer": message.get("content"),
        "guard": {
            "N": judge_field("N", answer, report).status,
            "NPOS": judge_count(answer, report).status,
        },
        "reasoning": message.get("reasoning_content"),
        "excerpts": [],  # [start, end] offsets into "reasoning", chosen by a person after reading
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{case_id}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(asyncio.run(record(sys.argv[1].strip().upper())))
