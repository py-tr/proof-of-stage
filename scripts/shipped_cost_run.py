"""Pre-registered: the shipped evidence chain's cost against always-4k (docs/preregistration/shipped-cost.md).

python scripts/shipped_cost_run.py freeze "<prediction>"
python scripts/shipped_cost_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import shipped_cost  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(
            json.dumps(
                shipped_cost.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2
            )
        )
    elif cmd == "run":
        print(json.dumps(asyncio.run(shipped_cost.run_shipped_cost()), indent=2, default=str))
    else:
        print(__doc__)
