"""Hidden errors, second census (docs/preregistration/hidden-2.md): `--freeze` draws (no model); no flag runs once."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import hidden2  # noqa: E402

if __name__ == "__main__":
    if "--freeze" in sys.argv:
        r = asyncio.run(hidden2.freeze())
        print(json.dumps({"population": r["population"], "cases": len(r["cases"])}, indent=2))
    else:
        print(json.dumps(asyncio.run(hidden2.run_hidden2()), indent=2, default=str))
