from app import config
from app.engine import local_r1 as lr

JOB = {
    "id": "job_1",
    "privacy": "local-only",
    "lanes_resolved": [config.NS_LOCAL_LANE],
    "policy": {"egress_honored": True},
}
ATTEMPT = {
    "lane": config.NS_LOCAL_LANE,
    "model": {"resolved": "local-runtime/nemotron-3.5-lightning-30b-a3b", "honored": True},
    "finish_reason": "stop",
}


def test_checklist_passes_a_local_job():
    assert all(lr.checklist(JOB, ATTEMPT).values())


def test_checklist_fails_on_any_cloud_sign_or_missing_field():
    assert not lr.checklist({**JOB, "privacy": "cloud-ok"}, ATTEMPT)["privacy_local_only"]
    assert not lr.checklist({**JOB, "lanes_resolved": ["cloud"]}, ATTEMPT)["lanes_resolved_local"]
    cloud = {**ATTEMPT, "model": {"resolved": "nvidia/nemotron-3.5-lightning-30b-a3b"}}
    checks = lr.checklist(JOB, cloud)
    assert not checks["model_resolved_local_nemotron"] and not checks["model_honored"]
    assert not lr.checklist({k: v for k, v in JOB.items() if k != "policy"}, ATTEMPT)[
        "egress_honored"
    ]
    assert not lr.checklist(JOB, {**ATTEMPT, "finish_reason": "length"})["not_truncated"]
    assert not lr.checklist(JOB, {k: v for k, v in ATTEMPT.items() if k != "finish_reason"})[
        "not_truncated"
    ]


def _row(settled, agreement, ok=True):
    checks = {"a": ok}
    return {
        "settled": settled,
        "agreement": agreement,
        "seconds": 1.0,
        "attempts": [{"checks": checks}],
    }


def test_summarise_claim_needs_floor_zero_contradictions_and_local_checks():
    good = [_row(True, {"N": "agree", "NPOS": "agree"})] * 15 + [_row(False, {})] * 13
    assert lr.summarise(good, {})["claim_met"] is True
    low = [_row(True, {"N": "agree"})] * 14 + [_row(False, {})] * 14
    assert lr.summarise(low, {})["claim_met"] is False
    bad = good[:-1] + [_row(True, {"N": "disagree"})]
    assert lr.summarise(bad, {})["claim_met"] is False
    leak = good[:-1] + [_row(False, {}, ok=False)]
    out = lr.summarise(leak, {})
    assert out["every_record_local"] is False and out["claim_met"] is False
