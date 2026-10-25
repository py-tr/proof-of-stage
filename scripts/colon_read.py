"""Colorectal read test (docs/preregistration/colon-read.md): `--freeze` fetches and freezes (no model); no flag runs once."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import colon_read  # noqa: E402

if __name__ == "__main__":
    if "--freeze" in sys.argv:
        r = colon_read.freeze()
        print(json.dumps({"population": r["population"], "cases": [c["case_id"] for c in r["cases"]]}, indent=1))
    else:
        print(json.dumps(asyncio.run(colon_read.run_colon_read()), indent=2, default=str))
