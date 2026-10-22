from __future__ import annotations

import copy
from typing import Any

import pytest

from app.config import NS_LIGHTNING_CLOUD, NS_LOCAL_LANE, is_local_nemotron_lane
from app.providers.receipts import Receipt, ReceiptMismatch, parse_receipt, verify


def test_parse_prefers_meterless_top_level(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["model"] = "local-runtime/nemotron-top"
    payload["meterless"]["receipt"]["winning_route"]["model"] = "nested-should-be-ignored"
    payload["meterless"]["receipt_id"] = "rcpt-top"
    payload["meterless"]["receipt"]["receipt_id"] = "rcpt-nested"
    receipt = parse_receipt(payload)
    assert receipt.winning_model == "local-runtime/nemotron-top"
    assert receipt.receipt_id == "rcpt-top"
    assert receipt.winning_kind == "local"
    assert receipt.egress_destination == "none"
    assert receipt.context_sources == ["messages"]


def test_real_fixture_verifies_as_local_nemotron(chat_response: dict[str, Any]) -> None:
    receipt = parse_receipt(chat_response)
    verified = verify(receipt, require_kind="local")
    assert verified.winning_kind == "local"
    assert verified.context_sources == ["messages"]


def test_matching_model_passes(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["model"] = NS_LIGHTNING_CLOUD
    payload["meterless"]["winning_route"]["kind"] = "cloud"
    payload["meterless"]["egress"]["destination"] = "nvidia"
    receipt = parse_receipt(payload)
    verified = verify(receipt, require_model=NS_LIGHTNING_CLOUD, require_kind="cloud")
    assert verified.winning_model == NS_LIGHTNING_CLOUD


def test_mismatched_model_raises(chat_response: dict[str, Any]) -> None:
    receipt = parse_receipt(chat_response)
    with pytest.raises(ReceiptMismatch):
        verify(receipt, require_model=NS_LIGHTNING_CLOUD)


def test_extra_context_source_raises(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["egress"]["sent"]["context_sources"] = ["messages", "hmem:3 records"]
    receipt = parse_receipt(payload)
    with pytest.raises(ReceiptMismatch, match="context_sources"):
        verify(receipt)


def test_empty_context_sources_rejected(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["egress"]["sent"]["context_sources"] = []
    receipt = parse_receipt(payload)
    with pytest.raises(ReceiptMismatch, match="context_sources"):
        verify(receipt)


def test_family_pass_for_any_nemotron(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["model"] = "nvidia/nemotron-3-ultra-550b-a55b"
    payload["meterless"]["winning_route"]["kind"] = "cloud"
    payload["meterless"]["egress"]["destination"] = "nvidia"
    receipt = parse_receipt(payload)
    verified = verify(receipt)
    assert verified.winning_model == "nvidia/nemotron-3-ultra-550b-a55b"


def test_family_pass_for_local_runtime_nemotron(chat_response: dict[str, Any]) -> None:
    receipt = parse_receipt(chat_response)
    verified = verify(receipt)
    assert verified.winning_model.startswith("local-runtime/nemotron")
    assert verified.winning_kind == "local"


def test_family_fail_for_non_nemotron(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["model"] = "openai/gpt-4"
    payload["meterless"]["winning_route"]["kind"] = "cloud"
    receipt = parse_receipt(payload)
    with pytest.raises(ReceiptMismatch, match="family"):
        verify(receipt)


def test_local_kind_rejects_cloud_egress(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["kind"] = "cloud"
    payload["meterless"]["winning_route"]["model"] = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    payload["meterless"]["egress"]["destination"] = "nvidia"
    receipt = parse_receipt(payload)
    with pytest.raises(ReceiptMismatch):
        verify(receipt, require_kind="local")


def test_missing_receipt_id_is_rejected() -> None:
    receipt = Receipt(
        receipt_id=None,
        winning_model="nvidia/nemotron-3-ultra-550b-a55b",
        winning_kind="cloud",
        context_sources=["messages"],
    )
    with pytest.raises(ReceiptMismatch, match="receipt_id"):
        verify(receipt)


def test_local_lane_helper_never_treats_cloud_ids_as_local() -> None:
    assert is_local_nemotron_lane("local-runtime/nemotron-3.5-lightning-30b-a3b")
    assert is_local_nemotron_lane(NS_LOCAL_LANE)
    assert not is_local_nemotron_lane("nvidia/nemotron-3.5-super-vl-120b-a12b")
    assert not is_local_nemotron_lane("nvidia/nemotron-3.5-lightning-30b-a3b")


# --- signed receipts (Ed25519 over the sorted compact UTF-8 JSON body) ---


def test_the_captured_receipt_signature_verifies(chat_response: dict[str, Any]) -> None:
    receipt = parse_receipt(copy.deepcopy(chat_response))
    assert receipt.signature == "verified" and receipt.signer_key
    verify(receipt, require_signature=True, pinned_key=receipt.signer_key)


def test_a_changed_signed_body_fails_the_signature(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["receipt_envelope"]["body"]["ts_ms"] = 1
    receipt = parse_receipt(payload)
    assert receipt.signature == "invalid"
    with pytest.raises(ReceiptMismatch, match="signature"):
        verify(receipt, require_signature=True)


def test_an_unsigned_field_that_disagrees_with_the_signed_one_is_invalid(
    chat_response: dict[str, Any],
) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["winning_route"]["model"] = "nvidia/some-other-model"
    assert parse_receipt(payload).signature == "invalid"


def test_missing_envelope_and_pinned_key_and_cache(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"].pop("receipt_envelope")
    unsigned = parse_receipt(payload)
    assert unsigned.signature == "absent"
    with pytest.raises(ReceiptMismatch, match="signature absent"):
        verify(unsigned, require_signature=True)
    signed = parse_receipt(copy.deepcopy(chat_response))
    with pytest.raises(ReceiptMismatch, match="unexpected key"):
        verify(signed, pinned_key="AAAA")
    cached = signed.model_copy(update={"from_cache": True})
    with pytest.raises(ReceiptMismatch, match="cache"):
        verify(cached, allow_cache=False)
    verify(cached)  # allowed unless the caller forbids it


def test_js_number_format() -> None:
    from app.providers.receipts import _js_json, _js_number

    assert _js_number(1.0) == "1" and _js_number(5e-05) == "0.00005"
    assert (
        _js_number(45.3) == "45.3"
        and _js_number(1e21) == "1e+21"
        and _js_number(1.5e-7) == "1.5e-7"
    )
    assert _js_json({"b": 1.0, "a": [0.1, "x"]}) == '{"a":[0.1,"x"],"b":1}'


def test_cache_status_is_read_from_the_signed_copy(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["from_cache"] = True  # an unsigned claim
    receipt = parse_receipt(payload)
    if receipt.signature == "verified" and receipt.cache_status is not None:
        assert receipt.from_cache == (receipt.cache_status == "hit")


def test_an_absent_unsigned_sent_block_is_not_tampering(chat_response: dict[str, Any]) -> None:
    payload = copy.deepcopy(chat_response)
    payload["meterless"]["egress"].pop("sent", None)
    raw = payload["meterless"].get("receipt") or {}
    (raw.get("egress") or {}).pop("sent", None)
    receipt = parse_receipt(payload)
    assert receipt.signature == "verified"
    assert receipt.context_sources == ["messages"]  # read from the signed copy
