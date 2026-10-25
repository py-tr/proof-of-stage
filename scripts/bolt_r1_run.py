"""Pre-registered: Nemotron 3.5 Bolt at the first read (docs/preregistration/bolt-r1.md).

python scripts/bolt_r1_run.py freeze "<prediction>"
python scripts/bolt_r1_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import bolt_r1  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        print(json.dumps(bolt_r1.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"), indent=2))
    elif cmd == "run":
        print(json.dumps(asyncio.run(bolt_r1.run_bolt_r1()), indent=2, default=str))
    else:
        print(__doc__)
