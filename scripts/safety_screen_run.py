"""Pre-registered: Nemotron Content Safety screening report text (docs/preregistration/safety-screen.md).

python scripts/safety_screen_run.py freeze "<prediction>"
python scripts/safety_screen_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import safety_screen  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        rec = safety_screen.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]")
        print(json.dumps({k: v for k, v in rec.items() if k != "items"}, indent=2))
    elif cmd == "run":
        print(json.dumps(asyncio.run(safety_screen.run_safety_screen()), indent=2, default=str))
    else:
        print(__doc__)
