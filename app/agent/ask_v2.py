"""Ask the layer, v2: two code checks added after v1's pre-registered miss (9 of 12, bar 10).

v1 (app/agent/ask.py, result in docs/evidence/ask-layer-results.md, which stands) missed two case
questions because Lightning called the cohort tool instead of the case tool, and one of those
answers ("333", a real number from the wrong tool) passed v1's guard. v2 reuses v1's model, prompt,
tools and receipt check unchanged and adds two checks in code:
1. When the question names a case, the first round forces the `case_verdict` tool (a named
   tool_choice); the answer is refused unless `case_verdict` ran for that case.
2. The numbers in a case answer must appear in that case's own `case_verdict` result (or the
   question), not merely in any tool result.
Designed after v1's miss and disclosed; measured on new questions. Nothing is stored.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from app import config
from app.agent import ask as v1
from app.providers import nightshift
from app.providers.receipts import parse_receipt, verify
from app.web.data import LiveData

CASE_ID = re.compile(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}")


async def ask(question: str, data: LiveData | None = None) -> dict[str, Any]:
    data = data or LiveData()
    asked = CASE_ID.findall(question.translate(v1.HYPHENS).upper())
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": v1.SYSTEM},
        {"role": "user", "content": question},
    ]
    steps: list[dict[str, Any]] = []
    evidence = question
    case_evidence: dict[str, str] = {}
    base = nightshift._base_url()
    async with httpx.AsyncClient(timeout=v1.TIMEOUT_S) as client:
        for round_no in range(v1.MAX_ROUNDS):
            if round_no == 0:
                choice: Any = (
                    {"type": "function", "function": {"name": "case_verdict"}}
                    if asked
                    else "required"
                )
            else:
                choice = "auto"
            body = {
                "model": v1.MODEL,
                "messages": messages,
                "tools": v1.TOOLS,
                "tool_choice": choice,
                "max_tokens": 600,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            r = await client.post(
                f"{base}/chat/completions",
                headers=nightshift._headers(f"askv2-{uuid.uuid4().hex[:10]}"),
                json=body,
            )
            r.raise_for_status()
            payload = r.json()
            receipt = verify(
                parse_receipt(payload),
                require_model=v1.MODEL,
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
                "tool_choice": choice if isinstance(choice, str) else "case_verdict (forced)",
                "tool_calls": [],
            }
            if not calls:
                answer = str(msg.get("content") or "").strip().translate(v1.HYPHENS)
                step["answer"] = answer
                steps.append(step)
                read_layer = any(s["tool_calls"] for s in steps)
                missing_case = [c for c in asked if c not in case_evidence]
                pool = (
                    "\n".join([question, *[case_evidence[c] for c in asked if c in case_evidence]])
                    if asked
                    else evidence
                )
                bad = v1.unsupported(answer, pool)
                placeholder = bool(re.search(r"\[(insert|placeholder)", answer, re.I))
                ok = (
                    bool(answer) and read_layer and not missing_case and not bad and not placeholder
                )
                return {
                    "question": question,
                    "answer": answer if ok else None,
                    "refused": not ok,
                    "unsupported": bad,
                    "missing_case_verdict": missing_case,
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
                result = await v1.run_tool(str(fn.get("name")), args, data)
                text = json.dumps(result, ensure_ascii=False)
                evidence += "\n" + text
                if fn.get("name") == "case_verdict" and result.get("case_id"):
                    case_evidence[str(result["case_id"])] = text
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
