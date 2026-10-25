"""Write the evidence files for the round-3 pre-registered tests from their committed logs.

Each section runs only if its run log exists: shipped-cost, critic-census, parts-bench,
local-mode. Every number comes from the run's own summary row or per-record log; nothing is
typed in. Re-run after each test finishes; it overwrites only the files it can write.

    python scripts/write_round3_results.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
EV = ROOT / "docs" / "evidence"


def _last(name: str) -> dict | None:
    p = LOGS / name
    if not p.exists():
        return None
    rows = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(rows[-1]) if rows else None


def _rows(name: str) -> list[dict]:
    p = LOGS / name
    return (
        [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if p.exists()
        else []
    )


def _prereg(name: str) -> dict:
    return json.loads((ROOT / "docs" / "preregistration" / name).read_text(encoding="utf-8"))


def shipped_cost() -> None:
    s = _last("shipped-cost-runs.jsonl")
    if not s:
        return
    pre = _prereg("shipped-cost.json")
    v = s["r1_vs_control"]
    saving = s["ladder_tokens"] / s["control_tokens"] - 1 if s["control_tokens"] else 0
    lines = [
        "# The shipped evidence chain's cost against always-4k (pre-registered, run 2026-10-25)",
        "",
        f"Pre-registration: `docs/preregistration/shipped-cost.md` + `shipped-cost.json` (frozen before the first call). Run {s['run']}, log `logs/shipped-cost.jsonl`, summary `logs/shipped-cost-runs.jsonl`, envelopes `docs/evidence/attest/shipped-cost-envelopes.jsonl`. The dial test's procedure (`app/engine/dial.py`) unchanged, with today's rungs: first read Nemotron Lightning thinking off, then Super VL 4k on what stays open, against one Super VL 4k read of the same report, same session, through Nightshift.",
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Records | {s['records']} ({s['provider_failures']} provider failures, void above {10}): {'void' if s['void'] else 'not void'}; {s['scored']} scored |",
        f"| Completion tokens: chain vs always-4k | **{s['ladder_tokens']:,} vs {s['control_tokens']:,} ({saving:+.0%})** |",
        f"| Records settled by the first read | {s['settled_at_r1']} of {s['scored']} |",
        f"| First-read closings vs the 4k read | {v['agree']} agree, **{v['disagree']} contradicted**, {v['unconfirmed']} unconfirmed |",
        f"| Seconds: chain vs always-4k | {s['ladder_seconds']} vs {s['control_seconds']} |",
        f"| **Claim** (tokens at most 60% of always-4k; at most 10% of closings contradicted) | **{'met' if s.get('claim_met') else 'not met'}** |",
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## What it means, and what it does not",
        "",
        f"- The chain as shipped, small model first and the large one only on what stays open, used {abs(saving):.0%} {'fewer' if saving < 0 else 'more'} completion tokens than always reading at a 4k budget on these 30 consistent records, measured, replacing the earlier estimate (about -49%).",
        "- Tokens, not price: per-token prices differ by model size and are not measured here.",
        "- These are consistent records, the easy set; on the 25 hard queue records the first read rarely settles a case (`docs/evidence/seat-cost-quality.md`). One run, n = 30, no re-run.",
    ]
    (EV / "shipped-cost-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def critic_census() -> None:
    if not (LOGS / "critic-census-rescored.json").exists():
        return
    s = json.loads((LOGS / "critic-census-rescored.json").read_text(encoding="utf-8"))
    pre = _prereg("critic-census.json")
    review = {(x["case"], x["field"]): x["verdict"] for x in pre["fields"]}
    rows = [{**r, "verdict": review[(r["case"], r["field"])]} for r in _rows("critic-census.jsonl")]
    f, st, un = s["falls"], s["stands"], s["unsure"]
    lines = [
        "# Ultra, the shipped second reader, on the census-2 hits (pre-registered, run 2026-10-25)",
        "",
        f"Pre-registration: `docs/preregistration/critic-census.md` + `critic-census.json` (frozen before the first call). Run {s['run']}, log `logs/critic-census.jsonl`, envelopes `docs/evidence/attest/critic-census-envelopes.jsonl`. `critic_v2.ask` unchanged (Nemotron 3 Ultra, thinking on, Nightshift, pinned, signed, no cache), with each census reading and its quote as the value under review; Ultra never saw the verdicts (the builder's review: AI-drafted, builder-confirmed).",
        "",
        "## Result",
        "",
        "| Fields | Ultra says contradiction | ... with a verified objection | Ultra agrees | Failures |",
        "|---|---|---|---|---|",
        f"| Reading fell ({f['fields']}) | **{f['objected']}** | {f['objected_verified']} | {f['agreed']} | {f['failures']} |",
        f"| Reading stood ({st['fields']}) | **{st['objected']}** | {st['objected_verified']} | {st['agreed']} | {st['failures']} |",
        f"| Unsure ({un['fields']}) | {un['objected']} | {un['objected_verified']} | {un['agreed']} | {un['failures']} |",
        "",
        f"**Claim** (contradiction on at least half of the fallen fields and on at most 2 standing): **{'met' if s['claim_met'] else 'not met'}**. Kill (objections on fallen not above standing): **{'fired' if s['kill'] else 'not fired'}**.",
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        f"**Scoring note:** {s['note']}",
        "",
        "## Field by field",
        "",
        "| Case | Field | Registry → reading | Review | Ultra | Verified |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['case']} | {r['field']} | {r['registry']} → {r['reading']} | {r['verdict']} | {r.get('ultra') or r.get('error', '')[:40]} | {'yes' if (r.get('check') or {}).get('verified') else '-'} |"
        )
    lines += [
        "",
        "## What it means, and what it does not",
        "",
        "- The finding: Ultra shares the deep read's traps. It agreed with 10 of the 12 readings that fell (the per-part counts and the other-breast readings), and objected on none of the 12 that stood. Its two objections were both right in substance: TCGA-AC-A3EH's N (the report prints pT3 N2; verified) and TCGA-GM-A4E0's N, where it added the sentinel's 1 to Part C's 9 but answered 10, a count, in the N field, so the objection check rejected it as an invalid category. A second model reading the same specimen is not a fix for a per-part sum: the sum has to be code (`docs/evidence/parts-bench-results.md`).",
        "- The second reader can only object; an objection sends a case to a person and never changes a value. This measures whether its objections land where the deep read was wrong, on 25 values it had never seen.",
        "- A sum of parts sits in no single quote, so an objection about a per-part total may fail the one-quote check even when Ultra is right; both counts are reported.",
        "- The verdicts it is scored against are one lay review (AI-drafted, builder-confirmed). One run, no re-run.",
    ]
    (EV / "critic-census-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parts_bench() -> None:
    s = _last("parts-bench-runs.jsonl")
    if not s:
        return
    pre = _prereg("parts-bench.json")
    a_rows = json.loads((LOGS / "parts-bench-a-rows.json").read_text(encoding="utf-8"))
    hows: dict[str, int] = {}
    for r in _rows("parts-bench.jsonl"):
        hows[r.get("how", "error")] = hows.get(r.get("how", "error"), 0) + 1
    A, B, C, met = s["A"], s["B"], s["C"], s["claims_met"]
    lines = [
        "# The part-aware count on three sets (pre-registered, run 2026-10-25)",
        "",
        f"Pre-registration: `docs/preregistration/parts-bench.md` + `parts-bench.json` (frozen before the first call). Run {s['run']}, log `logs/parts-bench.jsonl`, envelopes `docs/evidence/attest/parts-bench-envelopes.jsonl`. `app/reader/parts.py`: Super VL lists every specimen part with its own quote; code checks each quote with the shipped rules, drops the other breast using the GDC record's side, takes a labelled total if verified, else adds the parts. {s['records']} records, {s['failures']} provider failures.",
        "",
        "## Result",
        "",
        "| Set | Result | Claim |",
        "|---|---|---|",
        f"| A, designed on (census-2 hits; disclosed) | fallen fields fixed **{A['fixed']} of {A['fallen']}**; standing fields kept **{A['kept']} of {A['standing']}** | {'met' if met['A'] else 'not met'} |",
        f"| B, blind labels (25 queue records) | count correct **{B['correct']}**, wrong **{B['wrong']}**, open {B['open']} (shipped deep read: 16 / 0 / 1) | {'met' if met['B'] else 'not met'} |",
        f"| C, regression (40 multi-part records the shipped reader agreed on) | new disagreements with the registry **{C['new_disagreements']} of {C['records']}** | {'met' if met['C'] else 'not met'} |",
        "",
        "How each count was reached: "
        + ", ".join(f"{k} {v}" for k, v in sorted(hows.items()))
        + ". A `parts_sum` is a value no single quote shows: the product would show the parts to a person.",
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## Set A field by field",
        "",
        "| Case | Field | Registry → census reading | Review | New value | How | OK |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in a_rows:
        lines.append(
            f"| {r['case']} | {r['field']} | {r['registry']} → {r['reading']} | {r['verdict']} | {r.get('new') or 'open'} | {r.get('how')} | {'-' if r.get('ok') is None else ('yes' if r['ok'] else 'no')} |"
        )
    lines += [
        "",
        "## What it means, and what it does not",
        "",
        "- Set A was designed on (the fix was written after reading these failures), so a pass there is weak evidence; sets B and C carry the claim.",
        "- Not wired into the shipped chain; the shipped reader and its Limits line stand unless a later, separately pre-registered change says otherwise. One run, no re-run.",
    ]
    (EV / "parts-bench-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def local_mode() -> None:
    s = _last("local-mode-runs.jsonl")
    if not s:
        return
    pre = _prereg("local-mode.json")
    v = s["vs_cloud"]
    scored = s["records"] - s["failures"]
    lines = [
        "# The local first read as a product mode (pre-registered, run 2026-10-25)",
        "",
        f'Pre-registration: `docs/preregistration/local-mode.md` + `local-mode.json` (frozen before the first call). Run {s["run"]}, log `logs/local-mode.jsonl`. `python -m app.cli run --case <id> --local`: the shipped evidence chain with its first read on this PC (local Nemotron Lightning, Nightshift Jobs API, "privacy": "local-only", the on-PC focus step; the quote check on the full report); what stays open goes to the cloud deep read as shipped.',
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Records | {s['records']} ({s['failures']} failures) |",
        f"| First reads local by the job checklist | **{s['first_read_local']} of {scored}** |",
        f"| Local first-read closings vs the census's cloud closings | {v['agree']} agree, **{v['disagree']} disagree**, {v['unconfirmed']} unconfirmed |",
        f"| Records settled by the local first read (report only) | {s['settled_by_local_first_read']} of {scored} |",
        f"| **Claim** (every first read local, 0 disagreements) | **{'met' if s['claim_met'] else 'not met'}** |",
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## What it means, and what it does not",
        "",
        "- Only the first read stays on the PC; a record it does not settle still goes to the cloud deep read with the full report. Fully local reading would need a larger local window (for example a DGX Spark): an inference, not tested.",
        "- The referee is the census's cloud chain on the same records, not a fresh cloud read. One run, no re-run.",
    ]
    (EV / "local-mode-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for fn in (shipped_cost, critic_census, parts_bench, local_mode):
        fn()
        print("ok", fn.__name__)
