"""Pre-registered: Nano Omni vs Super VL reading the scanned pages (docs/preregistration/scan-witness.md).

python scripts/scan_witness_run.py freeze "<prediction>"
python scripts/scan_witness_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import scan_witness  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(
            json.dumps(
                scan_witness.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2
            )
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(scan_witness.run_scan_witness()), indent=2, default=str))
    else:
        print(__doc__)
