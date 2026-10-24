"""Pull the FEC Senate committee reports for one cycle (OpenFEC /reports/house-senate/), page by page.

Public data (api.open.fec.gov). Uses FEC_API_KEY from the environment, else DEMO_KEY (30 calls an
hour, so calls are paced). Each page is saved as data/fec/raw/page-<n>.json (not committed);
pages already saved are skipped, so the pull can be resumed. Usage: python scripts/fec_pull.py 2018
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "fec" / "raw"
URL = "https://api.open.fec.gov/v1/reports/house-senate/"


def main(cycle: str) -> None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("FEC_API_KEY") or "DEMO_KEY"
    pause = 125.0 if key == "DEMO_KEY" else 4.0  # DEMO_KEY allows 30 calls an hour
    RAW.mkdir(parents=True, exist_ok=True)
    page, pages = 1, None
    while pages is None or page <= pages:
        target = RAW / f"cycle-{cycle}-page-{page}.json"
        if target.exists():
            data = json.loads(target.read_text(encoding="utf-8"))
        else:
            params = {"api_key": key, "committee_type": "S", "cycle": cycle, "per_page": 100,
                      "page": page, "sort": "committee_id"}
            response = httpx.get(URL, params=params, timeout=60)
            if response.status_code == 429:
                time.sleep(600)
                continue
            response.raise_for_status()
            data = response.json()
            target.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(pause)
        pages = data["pagination"]["pages"]
        print(f"page {page}/{pages}", flush=True)
        page += 1


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2018")
