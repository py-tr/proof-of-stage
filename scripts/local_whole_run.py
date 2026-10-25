"""Pre-registered: the local first read on whole reports, no cut (docs/preregistration/local-whole.md).

python scripts/local_whole_run.py freeze "<prediction>"
python scripts/local_whole_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import local_whole  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(
            json.dumps(local_whole.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2)
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(local_whole.run_local_whole()), indent=2, default=str))
    else:
        print(__doc__)
