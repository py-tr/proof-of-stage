"""Pre-registered: the local read on the hard cases, thinking off (docs/preregistration/local-off.md).

python scripts/local_off_run.py freeze "<prediction>"
python scripts/local_off_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import local_off  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(
            json.dumps(local_off.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2)
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(local_off.run_local_off()), indent=2, default=str))
    else:
        print(__doc__)
