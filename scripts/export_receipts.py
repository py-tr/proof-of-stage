"""Export the receipt explorer as static files for GitHub Pages (docs/receipts/; no server).

Copies the page, its script and styles with relative paths, and writes each committed receipt
bundle as JSON exactly as the app serves it (app.web.receiptsbundle). The browser then checks
every signature itself. Re-run after a bundle changes; tests/test_receipts_export.py checks the
export matches the bundles.

    python scripts/export_receipts.py
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.web.receiptsbundle import bundle, bundle_list  # noqa: E402

STATIC = ROOT / "app" / "web" / "static"
OUT = ROOT / "docs" / "receipts"


def main() -> int:
    data = OUT / "data"
    data.mkdir(parents=True, exist_ok=True)
    present = [b for b in bundle_list() if b["present"]]
    (data / "index.json").write_text(json.dumps({"bundles": present}, indent=1), encoding="utf-8")
    for b in present:
        (data / f"{b['id']}.json").write_text(json.dumps(bundle(b["id"])), encoding="utf-8")
    for name in ("style.css", "how.css", "receipts.css", "receipts.js"):
        shutil.copyfile(STATIC / name, OUT / name)
    html = (STATIC / "receipts.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/', 'href="./').replace('src="/static/', 'src="./')
    html = html.replace("<body>", '<body data-static="1">')
    html = html.replace(
        '<a class="howlink" href="/how">How it works</a>',
        '<a class="howlink" href="https://github.com/py-tr/proof-of-stage">The repository</a>',
    )
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"{len(present)} bundles -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
