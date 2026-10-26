"""Ask the layer: Nemotron Lightning answers questions about the audit by calling tools.

The tools are read-only queries our code runs on the Zetaris semantic layer (the checked values,
the verdict and its quote, the review queue). Lightning, thinking off, through Meterless Nightshift
chooses which tool to call (NVIDIA's own description of Lightning's job: tool calls and result
validation). Every response must carry a signed Nightshift receipt naming Lightning, from our
pinned key, not cached. The answer is shown only if every number and every case id in it appears
in a tool result or in the question: an unsupported number is refused, the same principle as the
quote check. Nothing is stored.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from app import config
from app.providers import nightshift
from app.providers.receipts import parse_receipt, verify
from app.web.data import LiveData

MODEL = config.NS_LIGHTNING_CLOUD
MAX_ROUNDS = 4
TIMEOUT_S = 180.0
SYSTEM = (
    "You answer questions about an audit of NCI's TCGA-BRCA cancer registry. Use only the tools; "
    "they read the Zetaris semantic layer's checked values. Every number and every case id in "
    "your answer must come from a tool result. Answer in one or two plain sentences. If the "
    "tools cannot answer, say so."
)
FIELD_WORDS = {
    "node_count": "the positive lymph node count",
    "pathologic_n": "the N stage",
    "review": "a person decides (the report does not settle it)",
}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "node_positive_answers",
            "description": "How many patients are node-positive, by the stage field, by the count field, and the layer's checked answer (on the records where both fields apply), and how many it leaves to a person.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_queue",
            "description": "The records the layer flags for review: each case id, why it is flagged, and which field the report contradicts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "case_verdict",
            "description": "For one case id: the registry's values, the values the report states, the field the report contradicts, and the verbatim quotes the code check accepted.",
            "parameters": {
                "type": "object",
                "properties": {"case_id": {"type": "string", "description": "e.g. TCGA-E2-A572"}},
                "required": ["case_id"],
            },
        },
    },
]


def _num(value: Any) -> Any:
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return value


async def run_tool(name: str, args: dict[str, Any], data: LiveData | None = None) -> dict[str, Any]:
    data = data or LiveData()
    if name == "node_positive_answers":
        np = (await data.cohort()).get("node_positive") or {}
        return {
            "records_where_both_fields_apply": np.get("records"),
            "node_positive_by_stage_field": np.get("node_positive_by_n_column"),
            "node_positive_by_count_field": np.get("node_positive_by_count_column"),
            "node_positive_checked_answer": np.get("node_positive_by_verdict"),
            "left_to_a_person": np.get("left_to_a_person"),
        }
    if name == "review_queue":
        queue = await data.queue()
        groups = (await data.cohort()).get("groups") or []
        return {
            "records_that_cannot_be_true_as_written": sum(
                g["n"] for g in groups if g.get("reason_class") == "n_count_contradiction"
            ),
            "records_in_review_queue": len(queue),
            "cases": [
                {
                    "case_id": q["case_id"],
                    "why_flagged": q.get("reason_class"),
                    "field_the_report_contradicts": FIELD_WORDS.get(
                        q.get("fault_field"), q.get("fault_field")
                    ),
                }
                for q in queue
            ],
        }
    if name == "case_verdict":
        case_id = str(args.get("case_id") or "").strip().upper()
        case = (
            await data.case(case_id)
            if re.fullmatch(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}", case_id)
            else None
        )
        if not case:
            return {"error": f"no such case in the layer: {case_id or '(none)'}"}
        c = case["check"]
        quotes = [
            {"field": e.get("field"), "value": e.get("value"), "quote": e.get("quote")}
            for e in case.get("extractions") or []
            if e.get("method") == "nemotron_reader" and e.get("quote")
        ]
        return {
            "case_id": case_id,
            "registry_n_stage": c.get("recorded_n"),
            "registry_positive_nodes": _num(c.get("lymph_nodes_positive")),
            "report_n_stage": c.get("report_n"),
            "report_positive_nodes": _num(c.get("report_nodes_positive")),
            "field_the_report_contradicts": FIELD_WORDS.get(
                c.get("fault_field"), c.get("fault_field")
            ),
            "accepted_quotes": quotes,
        }
    return {"error": f"unknown tool {name}"}


HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", " ": " ", " ": " "})


def unsupported(answer: str, evidence: str) -> list[str]:
    """Numbers and case ids in the answer that appear in no tool result or the question."""
    answer = answer.translate(HYPHENS)
    found = re.findall(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}", answer) + re.findall(
        r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-]|\.\d)", answer
    )
    pool = set(re.findall(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}", evidence)) | set(
        re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-]|\.\d)", evidence)
    )
    return [x for x in found if x not in pool]


async def ask(question: str, data: LiveData | None = None) -> dict[str, Any]:
    data = data or LiveData()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    steps: list[dict[str, Any]] = []
    evidence = question
    base = nightshift._base_url()
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for round_no in range(MAX_ROUNDS):
            item = f"ask-{uuid.uuid4().hex[:10]}"
            body = {
                "model": MODEL,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "required" if round_no == 0 else "auto",
                "max_tokens": 600,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            r = await client.post(
                f"{base}/chat/completions", headers=nightshift._headers(item), json=body
            )
            r.raise_for_status()
            payload = r.json()
            receipt = verify(
                parse_receipt(payload),
                require_model=MODEL,
                require_signature=True,
                pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
                allow_cache=False,
            )
            msg = (payload.get("choices") or [{}])[0].get("message") or {}
            calls = msg.get("tool_calls") or []
            step = {
                "receipt_id": receipt.receipt_id,
                "model": receipt.winning_model,
                "signature": receipt.signature,
                "tool_calls": [],
            }
            if not calls:
                answer = str(msg.get("content") or "").strip().translate(HYPHENS)
                step["answer"] = answer
                steps.append(step)
                bad = unsupported(answer, evidence)
                read_layer = any(s["tool_calls"] for s in steps)
                placeholder = bool(re.search(r"\[(insert|placeholder)", answer, re.I))
                ok = bool(answer) and not bad and read_layer and not placeholder
                return {
                    "question": question,
                    "answer": answer if ok else None,
                    "refused": not ok,
                    "unsupported": bad,
                    "read_layer": read_layer,
                    "steps": steps,
                }
            messages.append(
                {"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls}
            )
            for call in calls:
                fn = call.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await run_tool(str(fn.get("name")), args, data)
                text = json.dumps(result, ensure_ascii=False)
                evidence += "\n" + text
                step["tool_calls"].append(
                    {"name": fn.get("name"), "arguments": args, "result": result}
                )
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": text})
            steps.append(step)
    return {
        "question": question,
        "answer": None,
        "refused": True,
        "unsupported": [],
        "steps": steps,
        "note": "no answer within the tool-call rounds",
    }
