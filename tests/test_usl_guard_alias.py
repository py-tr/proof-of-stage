import pytest

from app.usl.client import SqlGuardError, guard_select
from app.usl.model import table_fqn

T = table_fqn("recorded_stage")


def test_a_declared_alias_of_our_table_is_a_column_not_a_source() -> None:
    guard_select(
        f"SELECT COUNT(DISTINCT r.case_id) FROM {T} r WHERE CAST(r.lymph_nodes_positive AS INT) > 0"
    )
    guard_select(f"SELECT x.case_id FROM {T} AS x")
    guard_select(f"SELECT s.n FROM (SELECT count(*) AS n FROM {T}) s")


def test_an_alias_cannot_smuggle_another_source() -> None:
    with pytest.raises(SqlGuardError):
        guard_select("SELECT r.secret FROM other.db.table r")  # the table itself is still checked
    with pytest.raises(SqlGuardError):
        guard_select(f"SELECT q.case_id FROM {T} r")  # q was never declared
    with pytest.raises(SqlGuardError):
        guard_select(f"SELECT r.a.b FROM {T} r")  # alias.column only, not a deeper name
