"""The routing ledger: which Nemotron did what on each review-queue case, from committed logs only.

For each of the 25 review-queue cases, the latest logged evidence-chain run
(`logs/markovian-chunks.jsonl`): every step's seat (first read, deep read, scan read), model,
thinking budget, what it accepted, completion tokens and signed receipt; and the second reader's
verdict on the stored values (`logs/ultra-critic-v2.jsonl`, the shipped run). Writes
docs/evidence/route-ledger.md and docs/evidence/route-ledger.json (for the /how card). No model
call.

    python scripts/route_ledger.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
OUT_MD = ROOT / "docs" / "evidence" / "route-ledger.md"
OUT_JSON = ROOT / "docs" / "evidence" / "route-ledger.json"
SEAT = {"R1": "first read", "R2": "deep read", "R3": "scan read"}


def _lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _tokens(usage) -> int:
    if isinstance(usage, str):
        try:
            usage = json.loads(usage.replace("'", '"'))
        except ValueError:
            return 0
    return int((usage or {}).get("completion_tokens") or 0)


def shipped_section() -> list[str]:
    """The chain as shipped (Lightning first read, Super deep read) on the shipped-cost run."""
    if not (LOGS / "shipped-cost-runs.jsonl").exists():
        return []
    tag = _lines(LOGS / "shipped-cost-runs.jsonl")[-1]["run"]
    rows = [
        r
        for r in _lines(LOGS / "markovian-chunks.jsonl")
        if str(r.get("run_id", "")).startswith(f"dial-shipped-{tag}") and r.get("rung")
    ]
    steps, tokens, models = Counter(), Counter(), defaultdict(set)
    for r in rows:
        seat = SEAT.get(r["rung"], r["rung"])
        steps[seat] += 1
        tokens[seat] += _tokens(r.get("usage"))
        models[seat].add(str(r.get("model")).split("/")[-1])
    cases = sorted({r["case"] for r in rows})
    alone = sum(
        {SEAT.get(r["rung"]) for r in rows if r["case"] == c} == {"first read"} for c in cases
    )
    per_seat = "; ".join(
        f"{k}: {steps[k]} steps, {tokens[k]:,} completion tokens ({', '.join(sorted(models[k]))})"
        for k in steps
    )
    return [
        "## As shipped: the shipped-cost run (pre-registered, 2026-10-25, the dial test's 30 records)",
        "",
        f"{len(cases)} records: {alone} settled by the first read alone, {len(cases) - alone} went on "
        f"to the deep read. {per_seat}. Per-record rows: `logs/shipped-cost.jsonl`; envelopes "
        "`docs/evidence/attest/shipped-cost-envelopes.jsonl`.",
        "",
    ]


def main() -> None:
    queue = sorted(
        json.loads(
            (ROOT / "docs/preregistration/ground-truth-labels.json").read_text(encoding="utf-8")
        )["labels"]
    )
    chunks = [
        r
        for r in _lines(LOGS / "markovian-chunks.jsonl")
        if r.get("case") in queue and r.get("rung")
    ]
    latest_run = {}
    for r in chunks:
        latest_run[r["case"]] = r["run_id"]
    runs = _lines(LOGS / "ultra-critic-v2-runs.jsonl")
    tag = runs[0]["run"] if runs else None
    critic = defaultdict(dict)
    for r in _lines(LOGS / "ultra-critic-v2.jsonl"):
        if r.get("run") == tag and str(r.get("planted")) != "True":
            objected = r.get("verdict") == "contradiction" and (r.get("check") or {}).get(
                "verified"
            )
            critic[r["case"]][r["field"]] = "objects" if objected else r.get("verdict")
    cases, seat_steps, seat_tokens, closed_by = [], Counter(), Counter(), Counter()
    for case in queue:
        steps = [r for r in chunks if r["case"] == case and r["run_id"] == latest_run.get(case)]
        rows = []
        for r in steps:
            fields = r.get("fields") if isinstance(r.get("fields"), dict) else {}
            accepted = {
                f: v.get("value")
                for f, v in fields.items()
                if f in ("N", "NPOS") and v.get("status") == "accepted"
            }
            seat = SEAT.get(r["rung"], r["rung"])
            tok = _tokens(r.get("usage"))
            seat_steps[seat] += 1
            seat_tokens[seat] += tok
            for f in accepted:
                closed_by[(seat, f)] += 1
            rows.append(
                {
                    "seat": seat,
                    "model": r.get("model"),
                    "budget": r.get("budget"),
                    "accepted": accepted,
                    "tokens": tok,
                    "receipt_id": r.get("receipt_id"),
                    "signature": r.get("signature"),
                }
            )
        cases.append(
            {
                "case": case,
                "run_id": latest_run.get(case),
                "steps": rows,
                "second_reader": critic.get(case, {}),
            }
        )
    objections = sum(v == "objects" for c in critic.values() for v in c.values())
    summary = {
        "cases": len(cases),
        "steps_per_seat": dict(seat_steps),
        "tokens_per_seat": dict(seat_tokens),
        "second_reader_values": sum(len(c) for c in critic.values()),
        "second_reader_objections": objections,
    }
    OUT_JSON.write_text(
        json.dumps({"summary": summary, "cases": cases}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    lines = [
        "# Routing ledger: which Nemotron did what, per review-queue case (from committed logs, no model call)",
        "",
        "Generated by `scripts/route_ledger.py`: the latest logged evidence-chain run per case (`logs/markovian-chunks.jsonl`) and the shipped second reader's run (`logs/ultra-critic-v2.jsonl`). Every step's receipt id can be checked on `/receipts` where its envelope is in a committed bundle.",
        "",
        f"**{summary['cases']} cases.** Steps per seat: "
        + ", ".join(f"{k} {v}" for k, v in seat_steps.items())
        + ". Completion tokens per seat: "
        + ", ".join(f"{k} {v:,}" for k, v in seat_tokens.items())
        + f". Second reader: {summary['second_reader_values']} stored values re-read, {objections} objections.",
        "",
        "| Case | Steps (seat · model · budget · accepted · tokens · receipt) | Second reader |",
        "|---|---|---|",
    ]
    for c in cases:
        steps = "<br>".join(
            f"{s['seat']} · {str(s['model']).split('/')[-1]} · {s['budget']} · "
            + (", ".join(f"{k} {v}" for k, v in s["accepted"].items()) or "nothing accepted")
            + f" · {s['tokens']:,} · `{s['receipt_id']}`"
            for s in c["steps"]
        )
        sr = ", ".join(f"{k}: {v}" for k, v in c["second_reader"].items()) or "-"
        lines.append(f"| {c['case']} | {steps} | {sr} |")
    shipped = shipped_section()
    queue_head = [
        "## The review queue (25 hard cases), latest logged runs, 2026-10-23: the first read was "
        "still Super VL then (Lightning took that seat that evening)",
        "",
    ]
    lines = lines[:2] + shipped + queue_head + lines[2:]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
