"""Write input_examples/ and output_examples/ from the running case page (live Zetaris USL).

python -m app.cli serve --port 8765   # live mode, in another terminal
python scripts/make_examples.py      # no model call: it reads what the layer already holds

One example per verdict: the report contradicts the count, the report contradicts the stage
field, a person decides, and a case the second reader (Ultra) objects to. Each output is the
case page's own API answer, without the report text (it is in the public TCGA corpus).
"""

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
CASES = {
    "TCGA-E2-A572": "the report contradicts the count field",
    "TCGA-AN-A0XN": "the report contradicts the stage field",
    "TCGA-A2-A0EW": "a person decides (the report does not settle it)",
    "TCGA-A1-A0SN": "the second reader (Ultra) objects, so a person decides",
}


def main() -> None:
    (ROOT / "input_examples").mkdir(exist_ok=True)
    (ROOT / "output_examples").mkdir(exist_ok=True)
    captured = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    for i, (case_id, what) in enumerate(CASES.items(), 1):
        inp = {
            "case_id": case_id,
            "shows": what,
            "run": f"open http://127.0.0.1:8000/?case={case_id}  (or: python -m app.cli run --case {case_id})",
        }
        (ROOT / "input_examples" / f"example_{i}.json").write_text(
            json.dumps(inp, indent=2) + "\n", encoding="utf-8"
        )
        with urllib.request.urlopen(f"{BASE}/api/case/{case_id}", timeout=60) as r:
            data = json.loads(r.read())
        data.pop("report_text", None)
        out = {
            "case_id": case_id,
            "captured_at": captured,
            "source": "live Zetaris USL through the case page API (/api/case); no model was called to write this file",
            **data,
        }
        (ROOT / "output_examples" / f"example_{i}.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(case_id, out.get("headline", "")[:90])


if __name__ == "__main__":
    main()
