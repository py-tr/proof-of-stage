"""Write docs/evidence/local-whole-results.md and local-deep-results.md from each run's own logs.

python scripts/write_local_results.py   # writes whichever of the two has run
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
    lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return json.loads(lines[-1]) if lines else None


def _pre(name: str) -> dict:
    return json.loads((ROOT / "docs" / "preregistration" / name).read_text(encoding="utf-8"))


def local_whole() -> None:
    s = _last("local-whole-runs.jsonl")
    if not s:
        return
    pre = _pre("local-whole.json")
    g = s.get("gate", {})
    lines = [
        "# The local first read on whole reports (pre-registered, run 2026-10-26)",
        "",
        f"Pre-registration: `docs/preregistration/local-whole.md` + `local-whole.json` (frozen before the first call). Run {s['run']}, log `logs/local-whole.jsonl`. After the Nightshift 2026-10-26 release the local Lightning lane holds long prompts, so this repeats the local-mode test with no cut, on 20 new census-2 records (6 longer than 7,000 characters).",
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Gate (~13,000-token local job) | {'passed' if g.get('passed') else 'FAILED'}: {g.get('model_resolved')}, {g.get('seconds')} s |",
    ]
    if s.get("void") and "records" not in s:
        lines += ["| **Claim** | **void: the gate failed** |"]
    else:
        lines += [
            f"| Records | {s['records']} ({s['failures']} failures) |",
            f"| First reads local by the frozen checklist and answered by local Lightning | **{s['first_read_local']} of {s['records']}** |",
            f"| Reports sent whole | **{s['whole_reports']} of {s['records']}** (longest {s['longest_report_chars']:,} characters) |",
            f"| Local first-read closings vs the census's cloud closings | {s['vs_cloud']['agree']} agree, **{s['vs_cloud']['disagree']} disagree**, {s['vs_cloud']['unconfirmed']} unconfirmed |",
            f"| Records settled by the local first read (report only) | {s['settled_by_local_first_read']} of {s['records']} |",
            f"| **Claim** | **{'met' if s['claim_met'] else 'not met'}**{'; void' if s.get('void') else ''} |",
        ]
    lines += [
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## What it means, and what it does not",
        "",
        "- Only the first read is local; what it does not settle goes to the cloud deep read as shipped.",
        "- The window grew after the sponsor's release and a lane restart; we did not change any setting (`logs/probe-nightshift-update-2026-10-26.txt`).",
        "- The referee is the census's cloud chain on the same records, not a fresh paired run. One run, no re-run.",
        "- The Bolt lane was removed before the run; with it on, local jobs resolved two lanes and the frozen checklist failed.",
        "- Lengths are in characters; token counts in the probes were estimates (characters / 5).",
        "- What \"local\" rests on: Nightshift's own job record (privacy, lanes, model, egress). Local reads carry no Ed25519 signature, and the local checklist does not check context sources.",
        "- Correction to the pre-registration's wording: it cites rising GPU memory in the probe log; that sample was observed in the session and saved afterwards to `logs/probe-gpu-sample-2026-10-26.txt`, not tied to a job id.",
    ]
    (EV / "local-whole-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ok local-whole")


def local_deep() -> None:
    s = _last("local-deep-runs.jsonl")
    if not s:
        return
    pre = _pre("local-deep.json")
    g = s.get("gate", {})
    lines = [
        "# The deep read on this PC (pre-registered, run 2026-10-26)",
        "",
        f"Pre-registration: `docs/preregistration/local-deep.md` + `local-deep.json` (frozen before the first call). Run {s['run']}, log `logs/local-deep.jsonl`. Local Lightning through Nightshift's Jobs API (local-only), thinking on at the bench's 4k budget, the same 25 queue reports, prompt and guard as the cloud deep-read bench, scored by the bench's rules against both blind labellers.",
        "",
        "## Result",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Gate (~13,000-token local job) | {'passed' if g.get('passed') else 'FAILED'}: {g.get('model_resolved')}, {g.get('seconds')} s |",
    ]
    if s.get("void") and "cases" not in s:
        lines += ["| **Claim** | **void: the gate failed** |"]
    else:
        b, sec, c = s["vs_builder"], s["vs_second"], s["cloud_rows"]
        lines += [
            f"| Reads | {s['cases']} ({s['failures']} failures); local and local Lightning on {s['reads_local']} |",
            f"| Against the builder's labels: correct / wrong accepts | **local Lightning {b['correct']} / {b['wrong']}**; cloud Lightning {c['builder']['cloud_lightning'][0]} / {c['builder']['cloud_lightning'][1]}, Super {c['builder']['super'][0]} / {c['builder']['super'][1]}, Ultra {c['builder']['ultra'][0]} / {c['builder']['ultra'][1]} |",
            f"| Against the second labeller | **local Lightning {sec['correct']} / {sec['wrong']}**; cloud Lightning {c['second']['cloud_lightning'][0]} / {c['second']['cloud_lightning'][1]}, Super {c['second']['super'][0]} / {c['second']['super'][1]}, Ultra {c['second']['ultra'][0]} / {c['second']['ultra'][1]} |",
            f"| Median seconds per read (local) | {s['median_seconds']} |",
            f"| **Claim** (wrong accepts no more than cloud Lightning's, both labellers) | **{'met' if s['claim_met'] else 'not met'}**{'; kill fired' if s.get('kill') else ''}{'; void' if s.get('void') else ''} |",
        ]
    lines += [
        "",
        f'Prediction (before the run): "{pre["prediction"]}"',
        "",
        "## What it means, and what it does not",
        "",
        "- Super VL keeps the shipped deep read; this measures what moving the deep read onto a 16 GB PC costs. Parse (scans) and Ultra (the second reader) were not part of it.",
        "- Whether a larger local machine would close the gap to Super is an inference we did not test.",
        "- One run, no re-run.",
    ]
    (EV / "local-deep-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("ok local-deep")


if __name__ == "__main__":
    local_whole()
    local_deep()
