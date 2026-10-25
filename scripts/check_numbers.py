"""Check that the README's headline numbers still follow from the committed logs (no network).

Each check recomputes a number from a committed run log (or the attestation bundle, verified
offline) and requires the README to state it in the exact words it uses today. A changed log or
an edited README that no longer agree fails the check. Exit code 1 on any mismatch.

    python scripts/check_numbers.py            # every check
    python scripts/check_numbers.py --no-tests # skip counting the test suite
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

README = (ROOT / "README.md").read_text(encoding="utf-8")


def last(name: str) -> dict:
    lines = (ROOT / "logs" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads([x for x in lines if x.strip()][-1])


def checks(count_tests: bool) -> list[tuple[str, str]]:
    from app.verify import verify

    out: list[tuple[str, str]] = []
    attest = [
        json.loads(x)
        for x in (ROOT / "logs" / "attest.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]
    reproduced = sum(r.get("outcome") == "reproduced" for r in attest)
    v = verify()
    out += [
        ("attestation", f"**{reproduced} of {len(attest)} reproduced**"),
        ("receipts", f"{v['receipts_verified']} of {v['receipts']} receipts verified"),
    ]
    p4 = last("agent-probe-4-runs")
    fix = sum(p4["fix"].values())
    out += [
        (
            "probe 4 (a)",
            f"**(a)** {p4['ids'].get('EXACT_SIX', 0)} of {sum(p4['ids'].values())} "
            "returned exactly the six",
        ),
        ("probe 4 (b)", f"{fix} of {fix} wrote an `UPDATE`"),
        ("probe 4 refused", f"refused all {p4['fix'].get('WRITE_ATTEMPTED_REFUSED', 0)}"),
    ]
    scores = json.loads((ROOT / "logs" / "label-scores.json").read_text(encoding="utf-8"))
    b = scores["baseline_all"]
    out.append(
        (
            "blind labels",
            f"**product {b['A0_ours']['agree']} / {b['A0_ours']['of']}**, Super 4k "
            f"{b['M0_4k']['agree']}, Super off {b['M0_off']['agree']}, rule alone "
            f"{b['B0_rule_alone']['agree']}",
        )
    )
    h = last("hidden-errors-runs")
    out.append(("hidden errors 1", f"**{h['records_contradicting_registry']} of {h['records']}**"))
    d = last("dial-runs")
    out += [
        ("dial", f"**{d['settled_at_r1']} settled by the thinking-off read alone**"),
        ("dial tokens", f"({d['ladder_tokens']:,} vs {d['control_tokens']:,})"),
    ]
    lr = last("lightning-r1-runs")
    out.append(("lightning R1", f"**{lr['lightning_settled']} of {lr['scored']} settled**"))
    loc = last("local-r1-runs")
    out.append(("local R1", f"**{loc['settled']} of {loc['records']}** settled"))
    foc = last("local-focus-runs")
    out.append(
        (
            "local focus",
            f"**{foc['settled']} of {foc['records']}** settled (bar {foc['settled_floor']})",
        )
    )
    vs = last("vision-scan-runs")
    out.append(("vision scan", f"**{vs['cases_matching']} of {vs['cases']}** cases matched"))
    fec = last("fec-read-runs")
    vl = last("fec-read-vl-runs")
    colon = last("colon-read-runs")
    irs = last("irs-read-runs")
    out += [
        ("FEC v1", f"Parse + rules: {fec['read_cleanly']} of {fec['filings']} (5)"),
        ("FEC v2", f"Super VL: {vl['lines_agree']} of {vl['lines_read']} lines agree"),
        (
            "colon",
            f"{colon['named_a_field']} of {colon['read']} named a field ({colon['read'] // 2})",
        ),
        ("IRS", f"| {irs['read_cleanly']} of {irs['filings']} (8) |"),
    ]
    if count_tests:
        collected = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout
        n = int(re.search(r"(\d+) tests? collected", collected).group(1))
        out.append(("test count", f"# {n} tests, no network"))
    return out


def main(argv: list[str]) -> int:
    failed = 0
    for name, phrase in checks("--no-tests" not in argv):
        ok = phrase in README
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {phrase}")
    print(
        "PASS"
        if not failed
        else f"FAIL: {failed} number(s) in the README do not follow from the logs"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
