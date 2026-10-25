"""Pre-registered: the ClinicalTrials.gov read, a second domain with clean text (docs/preregistration/ctgov-read.md).

python scripts/ctgov_read_run.py freeze "<prediction>"
python scripts/ctgov_read_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import ctgov_read  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        rec = ctgov_read.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]")
        print(
            json.dumps(
                {k: v for k, v in rec.items() if k not in ("one_arm", "multi_arm")}, indent=2
            )
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(ctgov_read.run_ctgov_read()), indent=2, default=str))
    else:
        print(__doc__)
