"""The README's headline numbers follow from the committed logs (scripts/check_numbers.py)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_numbers.py"


def test_every_headline_number_is_stated_as_the_logs_give_it() -> None:
    spec = importlib.util.spec_from_file_location("check_numbers", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = [
        (name, phrase) for name, phrase in module.checks(False) if phrase not in module.README
    ]
    assert not missing, missing
