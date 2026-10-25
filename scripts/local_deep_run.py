"""Pre-registered: the deep read on this PC (local Lightning, 4k budget) (docs/preregistration/local-deep.md).

python scripts/local_deep_run.py freeze "<prediction>"
python scripts/local_deep_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import local_deep  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(
            json.dumps(local_deep.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2)
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(local_deep.run_local_deep()), indent=2, default=str))
    else:
        print(__doc__)
