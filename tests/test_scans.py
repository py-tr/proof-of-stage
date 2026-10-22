from __future__ import annotations

import json

import httpx
import pytest
import respx

from app import config
from app.providers import nvidia
from app.reader.quotes import locate
from app.scans.scans import blocks_for_span, case_dir, join_pages

PAGES = [
    [
        {"text": "SURGICAL PATHOLOGY REPORT", "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.12},
        {"text": "LYMPH NODES: METASTASIS IN TWO OF EIGHTEEN (2/18) EXAMINED"},
    ],
    [{"text": "PATHOLOGIC STAGE: pT2N1aMX"}],
]


def test_join_pages_maps_every_block_back() -> None:
    text, refs = join_pages(PAGES)
    assert text.startswith("[page 1]\n") and "[page 2]\n" in text
    for ref in refs:
        assert text[ref.start : ref.end] == PAGES[ref.page][ref.block]["text"]


def test_a_located_quote_lands_on_its_block() -> None:
    text, refs = join_pages(PAGES)
    span = locate("TWO OF EIGHTEEN (2/18) EXAMINED", text)
    assert span is not None
    hits = blocks_for_span(span, refs)
    assert [(h.page, h.block) for h in hits] == [(0, 1)]
    stage = blocks_for_span(locate("PATHOLOGIC STAGE: pT2N1aMX", text), refs)
    assert [(h.page, h.block) for h in stage] == [(1, 0)]


def test_case_dir_rejects_paths() -> None:
    with pytest.raises(ValueError):
        case_dir("../../etc")


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_parse_page_reads_the_markdown_bbox_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    args = [
        [
            {
                "bbox": {"xmin": 0.1, "ymin": 0.2, "xmax": 0.6, "ymax": 0.25},
                "text": "N Stage: 1",
                "type": "Text",
            }
        ]
    ]
    reply = {
        "model": config.NV_PARSE,
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": "markdown_bbox", "arguments": json.dumps(args)},
                        }
                    ]
                }
            }
        ],
    }
    with respx.mock:
        route = respx.post(nvidia.NVIDIA_CHAT_URL).mock(
            return_value=httpx.Response(200, json=reply)
        )
        blocks, served = await nvidia.parse_page(b"\xff\xd8jpeg")
    sent = json.loads(route.calls[0].request.content)
    assert (
        sent["model"] == config.NV_PARSE
        and sent["tool_choice"]["function"]["name"] == "markdown_bbox"
    )
    assert sent["messages"][0]["content"].startswith('<img src="data:image/jpeg;base64,')
    assert served == config.NV_PARSE
    assert blocks == [
        {"x0": 0.1, "y0": 0.2, "x1": 0.6, "y1": 0.25, "text": "N Stage: 1", "kind": "Text"}
    ]


@pytest.mark.usefixtures("env")
@pytest.mark.asyncio
async def test_parse_page_rejects_a_substituted_model() -> None:
    reply = {"model": "nvidia/other", "choices": [{"message": {"tool_calls": []}}]}
    with respx.mock:
        respx.post(nvidia.NVIDIA_CHAT_URL).mock(return_value=httpx.Response(200, json=reply))
        with pytest.raises(nvidia.ModelMismatch):
            await nvidia.parse_page(b"x")
