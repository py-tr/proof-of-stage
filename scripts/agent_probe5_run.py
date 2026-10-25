"""Pre-registered agent probe 5 (docs/preregistration/agent-probe-5.md).

python scripts/agent_probe5_run.py check    # the agent account can read the view, and only it
python scripts/agent_probe5_run.py freeze "<prediction>"
python scripts/agent_probe5_run.py run      # once
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.engine import agent_probe5 as p5  # noqa: E402
from app.engine.agent_probe import PROMPT, QUESTION  # noqa: E402
from app.engine.dial import sha16  # noqa: E402
from app.usl.model import table_fqn  # noqa: E402


async def check() -> None:
    """Read-only: what the agent account can and cannot read (no model call)."""
    for sql in (
        "SELECT count(*) FROM agent_view.node_status",
        "SELECT count(*) FROM agent_view.node_status "
        "WHERE CAST(positive_nodes_checked AS DOUBLE) > 0",
        f"SELECT count(*) FROM {table_fqn('recorded_stage')}",
        f"SELECT count(*) FROM {table_fqn('stage_check')}",
    ):
        try:
            print("READ   ", sql[-60:], "->", p5.number(await p5.run_as_agent(sql)))
        except Exception as exc:
            print("REFUSED", sql[-60:], "->", str(exc)[:160])


def freeze(prediction: str) -> None:
    record = {
        "written": datetime.now(UTC).strftime("%Y-%m-%d"),
        "code_sha256_16": {
            p: sha16((ROOT / p).read_text(encoding="utf-8")) for p in p5.FROZEN_FILES
        },
        "schema_control_sha256_16": sha16(p5.SCHEMA_CONTROL.read_text(encoding="utf-8")),
        "schema_agent_sha256_16": sha16(p5.SCHEMA_AGENT.read_text(encoding="utf-8")),
        "prompt_sha256_16": sha16(PROMPT + QUESTION),
        "calls_per_arm": p5.CALLS,
        "correct": p5.CORRECT,
        "raw": p5.RAW,
        "claim": "agent arm: >= 4 of 5 return 479",
        "prediction": prediction,
    }
    p5.PREREG.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        asyncio.run(check())
    elif cmd == "freeze":
        freeze(sys.argv[2] if len(sys.argv) > 2 else "[fill]")
    elif cmd == "run":
        print(json.dumps(asyncio.run(p5.run_probe5()), indent=2, default=str))
    else:
        print(__doc__)
