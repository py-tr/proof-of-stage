"""Run the pre-registered attestation census (docs/preregistration/attest.md) and print the summary."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.attest import run_attest  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_attest()), indent=2, default=str))
