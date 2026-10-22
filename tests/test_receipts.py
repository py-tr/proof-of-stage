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
