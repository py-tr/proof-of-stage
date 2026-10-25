"""Run pre-registered agent probe 4 once (docs/preregistration/agent-probe-4.md)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.agent_probe4 import run_probe4  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_probe4()), indent=2, default=str))
