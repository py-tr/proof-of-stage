"""FEC v2 (docs/preregistration/fec-read-vl.md): `--freeze` draws and downloads (no model); no flag runs once."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fec import read_vl  # noqa: E402

if __name__ == "__main__":
    if "--freeze" in sys.argv:
        record = read_vl.freeze()
        print(json.dumps({k: record[k] for k in ("seed", "sample_size", "download_failures")}))
    else:
        print(json.dumps(asyncio.run(read_vl.run_fec_read_vl()), indent=2, default=str))
