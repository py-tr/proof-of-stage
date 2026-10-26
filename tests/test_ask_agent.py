from app.agent.ask import unsupported
from app.agent.ask_eval import right


def test_unsupported_flags_numbers_and_ids_not_in_evidence() -> None:
    evidence = '{"case_id": "TCGA-E2-A572", "report_positive_nodes": 8}'
    assert unsupported("TCGA-E2-A572 has 8 positive nodes", evidence) == []
    assert unsupported("TCGA-E2-A572 has 9 positive nodes", evidence) == ["9"]
    assert unsupported("TCGA-XX-0000 is flagged", evidence) == ["TCGA-XX-0000"]
    assert unsupported("TCGA\u2011E2\u2011A572 has 8", evidence) == []  # non-breaking hyphens


def test_right_scores_numbers_and_fields_lexically() -> None:
    assert right({"kind": "number", "want": 333}, "The checked answer is 333.")
    assert not right({"kind": "number", "want": 333}, "It is 3333.")
    assert right({"kind": "field", "want": "node_count"}, "It contradicts the positive lymph node count.")
    assert right({"kind": "field", "want": "pathologic_n"}, "The report contradicts the N stage.")
    assert right({"kind": "field", "want": "review"}, "A person decides.")
    assert not right({"kind": "number", "want": 2}, None)


def test_numbers_at_sentence_end_are_checked() -> None:
    assert unsupported("It has 9.", '{"n": 8}') == ["9"]
    assert unsupported("It has 8.", '{"n": 8}') == []
