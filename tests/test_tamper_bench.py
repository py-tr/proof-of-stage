import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tamper_bench", ROOT / "scripts" / "tamper_bench.py")
tb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tb)


def test_changed_always_differs() -> None:
    for v in ("abc", "a", "", 3, 2.5, True, False, None):
        assert tb.changed(v) != v


def test_every_leaf_change_breaks_a_real_signature() -> None:
    from app.providers.receipts import _signed_receipt

    env = json.loads(tb.BUNDLE.read_text(encoding="utf-8").splitlines()[0])["envelope"]
    assert _signed_receipt(env)[0] == "verified"
    import copy

    for path in tb.leaves(env["body"])[:40]:
        forged = copy.deepcopy(env)
        tb.set_at(forged["body"], path, tb.changed(tb.get_at(env["body"], path)))
        assert _signed_receipt(forged)[0] != "verified"
