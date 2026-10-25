"""Every pre-registered file still matches its frozen hash, unless a later commit superseded it
after the run (listed below with the commit and the run, so a reader can check the order)."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs" / "preregistration"

# prereg json -> (files changed after its run, the commit that changed them, the run it froze)
SUPERSEDED = {
    "adversary-cases.json": (
        {"app/reader/reader.py", "app/engine/adversary.py"},
        "0cc0325 (2026-10-23 03:22 +02:00)",
        "adv-20261023T004318..T005401 (02:43-02:54 +02:00)",
    ),
    "dial-cases.json": (
        {"app/engine/rungs.py", "app/reader/reader.py"},
        "b70255f (2026-10-23 17:01 +02:00)",
        "20261023T123122 (14:31 +02:00)",
    ),
    "adversary-cases-v3.json": (
        {"app/reader/reader.py"},
        "c7121dc (2026-10-23 19:32 +02:00)",
        "adv-20261023T150141..T153459 (17:01-17:35 +02:00)",
    ),
    "lightning-cases.json": (
        {"app/engine/rungs.py", "app/reader/reader.py"},
        "c7121dc (2026-10-23 19:32 +02:00)",
        "20261023T172640 (19:26 +02:00)",
    ),
}


def _sha16(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _code_map(record: dict) -> dict[str, str]:
    return record.get("code_sha256_16") or record.get("guard_sha256_16") or {}


def test_every_frozen_file_matches_or_is_listed_as_superseded():
    checked = 0
    for path in sorted(PREREG.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            continue
        changed = {f for f, digest in _code_map(record).items() if _sha16(f) != digest}
        expected = SUPERSEDED.get(path.name, (set(), "", ""))[0]
        assert changed == expected, f"{path.name}: changed {sorted(changed)}"
        checked += 1
    assert checked >= 15


def test_frozen_labels_hash():
    data = (PREREG / "ground-truth-labels.json").read_bytes()
    frozen = (PREREG / "ground-truth-labels.sha16").read_text(encoding="utf-8").strip()
    assert hashlib.sha256(data).hexdigest()[:16] == frozen
