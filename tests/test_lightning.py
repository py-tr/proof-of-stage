from app.engine.lightning import r1_closings
from app.engine.rungs import CaseEvidence
from app.reader.reader import FieldResult, ReadResult


def _read(n: str, count: str) -> ReadResult:
    r = ReadResult(case_id="C", model="m", receipt_id=None, provider="nightshift")
    r.fields["N"] = FieldResult("N", "accepted", value=n)
    r.fields["NPOS"] = FieldResult("NPOS", "accepted", value=count)
    return r


def test_r1_rule_closes_only_agreeing_self_consistent_fields() -> None:
    case = CaseEvidence("C", "report", recorded_n="N1A", registry_count=2.0, edition="7")
    assert r1_closings(_read("N1A", "2"), case) == {"N": "N1A", "NPOS": "2"}
    assert r1_closings(_read("N1A", "3"), case) == {"N": "N1A"}  # count disagrees
    assert r1_closings(_read("N1A", "5"), case) == {}  # not self-consistent: nothing closes
