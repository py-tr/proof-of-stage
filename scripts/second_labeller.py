"""The second, independent blind labeller (docs/preregistration/second-labeller.md).

python scripts/second_labeller.py freeze <labels.json>   # before any scoring reads it
python scripts/second_labeller.py score                  # offline, no model calls
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import second_labeller  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze" and len(sys.argv) > 2:
        print(json.dumps(second_labeller.freeze(Path(sys.argv[2])), indent=2))
    elif cmd == "score":
        result = second_labeller.score()
        print(json.dumps({k: v for k, v in result.items() if k != "per_case"}, indent=2))
    else:
        print(__doc__)
