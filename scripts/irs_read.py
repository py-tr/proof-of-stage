"""IRS 990-EZ read test (docs/preregistration/irs-read.md): `--freeze` draws and downloads (no
model); no flag runs once."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.irs import read  # noqa: E402

if __name__ == "__main__":
    if "--freeze" in sys.argv:
        record = read.freeze()
        keys = ("seed", "sample_size", "missing_documents", "stop")
        print(json.dumps({k: record[k] for k in keys}))
    else:
        print(json.dumps(asyncio.run(read.run_irs_read()), indent=2, default=str))
