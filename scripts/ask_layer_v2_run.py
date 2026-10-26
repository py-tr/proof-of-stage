"""Pre-registered: "Ask the layer" v2 on 12 new questions (docs/preregistration/ask-layer-v2.md).

python scripts/ask_layer_v2_run.py freeze "<prediction>"
python scripts/ask_layer_v2_run.py run   # once
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import ask_v2_eval as ask_eval  # noqa: E402

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "freeze":
        rec = asyncio.run(ask_eval.freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]"))
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    elif cmd == "run":
        print(json.dumps(asyncio.run(ask_eval.run()), indent=2, default=str))
    else:
        print(__doc__)
