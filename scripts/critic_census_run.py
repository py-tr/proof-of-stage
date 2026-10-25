"""Pre-registered: Ultra (the shipped second reader) on the census-2 hits (docs/preregistration/critic-census.md).

python scripts/critic_census_run.py freeze "<prediction>"
python scripts/critic_census_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import critic_census  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        rec = critic_census.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]")
        print(json.dumps({k: v for k, v in rec.items() if k != "fields"}, indent=2))
    elif cmd == "run":
        print(json.dumps(asyncio.run(critic_census.run_critic_census()), indent=2, default=str))
    else:
        print(__doc__)
