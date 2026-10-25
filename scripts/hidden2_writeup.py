"""Write docs/evidence/hidden-2-results.md from the census log and the builder's lay reads.

Read-only over logs/hidden-2.jsonl, logs/hidden-2-runs.jsonl (the run's own summary),
docs/preregistration/hidden-2.json (prediction, population) and
docs/evidence/hidden-2-lay-reads.json (case -> {"read": "stands" | "falls" | "unsure", "note"}).
Only standing hits are called contradictions; the 95% Wilson interval over both censuses is
stated only if at least 240 records were scored, as pre-registered. Re-run it after each change
to the lay reads; it overwrites the results file.

    python scripts/hidden2_writeup.py
"""

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine.hidden2 import MIN_SCORED_FOR_RATE, summarise  # noqa: E402

LOG = ROOT / "logs" / "hidden-2.jsonl"
RUNS = ROOT / "logs" / "hidden-2-runs.jsonl"
PREREG = ROOT / "docs" / "preregistration" / "hidden-2.json"
READS = ROOT / "docs" / "evidence" / "hidden-2-lay-reads.json"
OUT = ROOT / "docs" / "evidence" / "hidden-2-results.md"
FIRST = {"scored": 60, "standing": 1, "case": "TCGA-A2-A25D"}
FIELD = {"N": "N category", "NPOS": "count"}


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def main() -> int:
    rows = [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    finished = RUNS.exists()
    s = summarise(rows)
    data = json.loads(READS.read_text(encoding="utf-8")) if READS.exists() else {}
    reads = data.get("reads", data)
    provenance = data.get("provenance", "the builder's lay read")
    hits = [r for r in rows if r.get("contradicts_registry")]
    verdict = Counter((reads.get(r["case"]) or {}).get("read", "not yet read") for r in hits)
    standing = verdict.get("stands", 0)
    lines = [
        "# Hidden errors, second census: results (pre-registered, run 2026-10-25)",
        "",
        "Pre-registration: `docs/preregistration/hidden-2.md` + `hidden-2.json` (commit 361f334, "
        "frozen before the first call). Log `logs/hidden-2.jsonl`, summary "
        "`logs/hidden-2-runs.jsonl`, envelopes `docs/evidence/attest/hidden-2-envelopes.jsonl` "
        "(every signature checkable on `/receipts`). Lay reads "
        "`docs/evidence/hidden-2-lay-reads.json`.",
        "",
    ]
    if not finished:
        so_far = f"{len(rows)} of {len(prereg['cases'])}"
        lines += [f"**RUN NOT FINISHED: {so_far} records so far.**", ""]
    lines += [
        "## Validity",
        "",
        f"{s['records']} of {len(prereg['cases'])} records run; {s['provider_failures']} provider "
        f"failures (void above 100): **{'void' if s['void'] else 'not void'}**. "
        f"{s['scored']} scored.",
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Records with a closed value that differs from the registry (a hit) | **{len(hits)} of "
        f"{s['scored']}** |",
        f"| Fields | {s['fields_contradicting_registry']['N']} N, "
        f"{s['fields_contradicting_registry']['NPOS']} count |",
        f"| Records fully settled (both fields closed) | {s['records_fully_settled']} of "
        f"{s['scored']} |",
        f"| The read of each hit (provenance below) | stands {standing}, falls "
        f"{verdict.get('falls', 0)}, unsure {verdict.get('unsure', 0)}, not yet read "
        f"{verdict.get('not yet read', 0)} |",
        "",
        f'Prediction (before the run): "{prereg["prediction"]}"',
        "",
        "Against the prediction: hits "
        + ("within" if 1 <= len(hits) <= 6 else "outside")
        + f" 1-6 ({len(hits)}: {'held' if 1 <= len(hits) <= 6 else 'did not hold'}); provider "
        f"failures {s['provider_failures']} ({'held' if s['provider_failures'] <= 5 else 'did not hold'}"
        f" against 0-5); standing hits {standing} of {len(hits)} "
        f"({'held' if standing * 2 >= len(hits) else 'did not hold'} against at least half).",
        "",
        f"**How each hit was read:** {provenance}. A hit is called a contradiction only when "
        "this read stands.",
        "",
    ]
    notes = [(reads.get(r["case"]) or {}).get("note", "") for r in hits]
    falls = [n for r, n in zip(hits, notes) if (reads.get(r["case"]) or {}).get("read") == "falls"]
    lines += [
        "**Why the readings that fall, fall:** "
        f"{sum('per-part' in n for n in falls)} took one part's node count for the total "
        "(a separately submitted sentinel node left out); "
        f"{sum('wrong breast' in n for n in falls)} read the other breast in a bilateral case. "
        "Both are reader limits, now listed in Limits.",
        "",
    ]
    if s["scored"] >= MIN_SCORED_FOR_RATE and not verdict.get("not yet read"):
        n = FIRST["scored"] + s["scored"]
        k = FIRST["standing"] + standing
        lo, hi = wilson(k, n)
        lines += [
            "## Both censuses together",
            "",
            f"Standing contradictions: {k} of {n} consistent records read ({FIRST['standing']} of "
            f"{FIRST['scored']} in the first census, {FIRST['case']}; {standing} of {s['scored']} "
            f"here). 95% Wilson interval **{lo:.1%} to {hi:.1%}**. This is the share of records "
            "the cross-field rule calls consistent whose report, read by this reader and one lay "
            "person, gives a different value; it is not the registry's error rate (one reader, "
            "one lay check, no pathologist; unsure hits are not counted; the first census's "
            "read was the builder's own, this census's was AI-drafted and builder-confirmed).",
            "",
        ]
    elif s["scored"] < MIN_SCORED_FOR_RATE:
        lines += [f"No interval: fewer than {MIN_SCORED_FOR_RATE} records scored.", ""]
    else:
        lines += ["No interval yet: some hits are not lay-read.", ""]
    lines += ["## Every hit, with its quote and the lay read", ""]
    for r in hits:
        read = reads.get(r["case"]) or {}
        for field, c in r["contradicts_registry"].items():
            lines.append(
                f"- **{r['case']}** ({FIELD.get(field, field)}): registry {c['registry']}, "
                f"reading {c['report']} (step {c['rung']}), quote “{c['quote']}”. "
                f"Read (whole record): **{read.get('read', 'not yet read')}**"
                + (f": {read['note']}" if read.get("note") else "")
            )
    lines += [
        "",
        "## What it means, and what it does not",
        "",
        "- A hit is the reader's value against the registry's; it is called a contradiction "
        "only when the lay read stands. Hits that fall are the reader's errors and are counted "
        "against it, not the registry.",
        "- Nothing was stored and no record was changed; these records are not in the review "
        "queue, because the queue comes from the cross-field rule.",
        "- One reader, one lay person, no pathologist. No re-run.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"{len(hits)} hits of {s['scored']} scored; stands {standing}; "
        f"finished={finished} -> {OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
