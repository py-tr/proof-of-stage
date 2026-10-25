"""Monday's regression after a Nightshift update, as one command (roll back rather than debug).

Runs, in order, and stops at nothing: the test suite, the offline receipt check, the README
numbers check, `doctor` (one live signed Super VL call through Nightshift, key fingerprint),
`usl status` and `usl demo` without --write (the live layer answers; nothing written), and the
two image probes from the claims audit (raw POSTs; logged by that script). Prints one line per
step and writes the full output to logs/regression-<UTC time>.txt. Exit code 1 if any step
that must pass failed; the image probes are information only (a refusal is a known limit).

    python scripts/regression.py            # everything
    python scripts/regression.py --offline  # only the three offline checks
"""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
OFFLINE = [
    ("tests", [PY, "-m", "pytest", "-q"], True),
    ("receipts offline", [PY, "-m", "app.verify"], True),
    ("README numbers", [PY, "scripts/check_numbers.py"], True),
]
LIVE = [
    ("doctor (signed Nightshift call)", [PY, "-m", "app.cli", "doctor"], True),
    ("usl status", [PY, "-m", "app.cli", "usl", "status"], True),
    ("usl demo (no write)", [PY, "-m", "app.cli", "usl", "demo"], True),
    ("image probes (information)", [PY, "scripts/capability_retest.py", "images"], False),
]


def main(argv: list[str]) -> int:
    steps = OFFLINE + ([] if "--offline" in argv else LIVE)
    tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = ROOT / "logs" / f"regression-{tag}.txt"
    failed = []
    with out.open("w", encoding="utf-8") as fh:
        for name, cmd, must in steps:
            run = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=900,
            )
            ok = run.returncode == 0
            if must and not ok:
                failed.append(name)
            tail = (run.stdout.strip().splitlines() or [""])[-1][:120]
            print(f"{'ok  ' if ok else ('FAIL' if must else 'info')} {name}: {tail}")
            fh.write(f"===== {name} (exit {run.returncode})\n{run.stdout}\n{run.stderr}\n")
    print(f"{'PASS' if not failed else 'FAIL: ' + ', '.join(failed)} -> {out.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
