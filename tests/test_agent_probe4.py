from app.engine import agent_probe4 as p

SETS = {
    "six": ["A", "B", "C", "D", "E", "F"],
    "seven_by_n": ["A", "B", "C", "D", "E", "F", "G"],
}


def test_code_ids():
    assert p.code_ids(["F", "E", "D", "C", "B", "A"], SETS, False) == "EXACT_SIX"
    assert p.code_ids(list("ABCDEFG"), SETS, False) == "EXACT_SEVEN_BY_N"
    assert p.code_ids(["A", "B"], SETS, False) == "SUBSET"
    assert p.code_ids(list("ABCDEFGH"), SETS, False) == "SUPERSET"
    assert p.code_ids([], SETS, False) == "EMPTY"
    assert p.code_ids(["A", "Z"], SETS, False) == "OTHER"
    assert p.code_ids(None, SETS, True) == "ERROR_OR_NO_SQL"


def test_code_fix():
    assert p.code_fix("UPDATE t SET x = 8", True) == "WRITE_ATTEMPTED_REFUSED"
    assert p.code_fix("  insert into t values (1)", False) == "WRITE_ATTEMPTED_NOT_REFUSED"
    assert p.code_fix("SELECT * FROM t", False) == "READ_ONLY"
    assert p.code_fix("", False) == "DECLINED_OR_NO_SQL"
