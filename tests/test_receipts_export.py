"""The static receipt explorer (docs/receipts/) serves the committed bundles unchanged."""

import json
from pathlib import Path

import pytest

from app.web.receiptsbundle import bundle

OUT = Path(__file__).resolve().parents[1] / "docs" / "receipts"


@pytest.mark.skipif(not OUT.exists(), reason="not exported yet")
def test_exported_frozen_bundles_equal_the_committed_ones() -> None:
    for key in ("attest", "agent-probe-4"):
        exported = json.loads((OUT / "data" / f"{key}.json").read_text(encoding="utf-8"))
        assert exported == bundle(key)
    html = (OUT / "index.html").read_text(encoding="utf-8")
    assert 'data-static="1"' in html and "/static/" not in html
