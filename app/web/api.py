"""FastAPI app for the one-case-at-a-time page."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
from app.reader.reader import FIELDS, NODES_POSITIVE, THINKING_BUDGET
from app.web.data import LiveData, SampleData
from app.web.evidence import challenge, count_rules, headline, recheck, why_chain
from app.web.lineage import LiveLineage, MirrorLineage, lineage
from app.zetaris import ZetarisError

LIVE_CACHE_S = 300.0
ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"


class Decision(BaseModel):
    claim: str = Field(max_length=32)
    reason_code: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=300)


class Challenge(BaseModel):
    field: str = Field(max_length=8)
    value: Any = None
    quote: str = Field(default="", max_length=2000)
    known: dict[str, Any] | None = None


def _rechecked(found: dict[str, Any]) -> list[dict[str, Any]]:
    """Each accepted reader value, re-checked now by the same guard that accepted it."""
    report = found.get("report_text") or ""
    out = []
    for row in found["extractions"]:
        # only text-reader rows: their offsets point into the report text the page shows
        if row.get("method") != "nemotron_reader" or row.get("field") not in (
            *FIELDS,
            NODES_POSITIVE,
        ):
            continue
        checks = recheck(row["field"], row.get("value"), row.get("quote"), report)
        out.append({**row, "checks": checks})
    return out


def create_app(
    data: LiveData | SampleData | None = None,
    rules: LiveLineage | MirrorLineage | None = None,
) -> FastAPI:
    source = data or (SampleData() if config.sample_mode() else LiveData())
    rule_source = rules or (MirrorLineage() if source.mode == "sample" else LiveLineage())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        loop = asyncio.get_running_loop()
        warming = loop.create_task(rule_source.warm())
        prewarm = loop.create_task(_prewarm())
        yield
        warming.cancel()
        prewarm.cancel()

    async def _prewarm() -> None:
        """Live mode: fill the cache for the first page view (cohort, queue, the demo case)."""
        if source.mode == "sample":
            return
        try:
            await _cached("cohort", lambda: _guarded(source.cohort()))
            await _cached("queue", lambda: _guarded(source.queue()))
            await _cached("case:TCGA-E2-A572", lambda: _build_case("TCGA-E2-A572"))
        except Exception:  # Zetaris not answering: the page reads live as before
            return

    app = FastAPI(title="Proof of Stage", docs_url=None, redoc_url=None, lifespan=lifespan)

    # Live reads of the activated layer take about 3.5 s each, so the page's three reads (case,
    # cohort, queue) are kept for a few minutes. Any write through this app clears them at once,
    # so a decision shows on the next read. Sample mode is local and is never cached.
    cache: dict[str, tuple[float, Any]] = {}

    async def _cached(key: str, call):  # type: ignore[no-untyped-def]
        if source.mode == "sample":
            return await call()
        hit = cache.get(key)
        if hit and time.monotonic() - hit[0] < LIVE_CACHE_S:
            return hit[1]
        value = await call()
        cache[key] = (time.monotonic(), value)
        return value

    @app.middleware("http")
    async def _clear_on_write(request, call_next):  # type: ignore[no-untyped-def]
        if request.method != "GET":
            cache.clear()
        response = await call_next(request)
        if request.method != "GET":
            cache.clear()
        return response

    async def _guarded(call):  # type: ignore[no-untyped-def]
        try:
            return await call
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ZetarisError as exc:
            raise HTTPException(
                status_code=503, detail="Zetaris did not answer; nothing was read or written"
            ) from exc

    @app.get("/api/mode")
    async def mode() -> dict[str, Any]:
        return {
            "mode": source.mode,
            "reader": (
                "first read: Nemotron Lightning, thinking off; deep and scan reads: "
                f"Nemotron Super, thinking budget {THINKING_BUDGET}"
            ),
            "source_note": getattr(source, "source_note", None),
        }

    @app.get("/api/cohort")
    async def cohort() -> dict[str, Any]:
        return await _cached("cohort", lambda: _guarded(source.cohort()))

    @app.get("/api/queue")
    async def queue() -> list[dict[str, Any]]:
        rows = await _cached("queue", lambda: _guarded(source.queue()))
        objecting: set[str] = set()
        if source.mode != "sample":  # the second reader is model output: live mode only
            from app.web.secondreader import objecting_cases

            objecting = objecting_cases()
        return [
            {
                **row,
                "headline": headline(row),
                "second_reader_objects": str(row.get("case_id")) in objecting,
            }
            for row in rows
        ]

    async def _case(case_id: str, fresh: bool = True) -> dict[str, Any]:
        found = await _guarded(source.case(case_id, fresh=fresh))
        if found is None:
            raise HTTPException(status_code=404, detail="case not found")
        return found

    @app.get("/api/case/{case_id}")
    async def case(case_id: str) -> dict[str, Any]:
        return await _cached(f"case:{case_id.upper()}", lambda: _build_case(case_id))

    async def _build_case(case_id: str) -> dict[str, Any]:
        found = await _case(case_id)
        check = found["check"]
        edition, site = check.get("edition_code"), check.get("site_key")
        accepted = _rechecked(found)
        objects = False
        if source.mode != "sample":  # the second reader is model output: live mode only
            from app.web.secondreader import objecting_cases

            objects = str(check.get("case_id")) in objecting_cases()
        top = headline(check)
        if objects:  # display only: the layer's verdict and the values stay as they are
            top = "Second reader objects: a person decides. " + top
        return {
            **found,
            "accepted": accepted,
            "second_reader_objects": objects,
            "headline": top,
            "why": why_chain(check, accepted),
            "lineage": await _guarded(lineage(rule_source, check)),
            "rules": {
                "registry_count": count_rules(
                    check.get("lymph_nodes_positive"),
                    check.get("lymph_nodes_tested"),
                    edition,
                    site,
                ),
                # a count the report states implies nodes were examined
                "report_count": count_rules(
                    check.get("report_nodes_positive"), True, edition, site
                ),
            },
        }

    @app.post("/api/case/{case_id}/challenge")
    async def try_to_fool_it(case_id: str, body: Challenge) -> dict[str, Any]:
        found = await _case(case_id, fresh=False)
        if not found.get("report_text"):
            raise HTTPException(status_code=409, detail="this case has no public report text")
        try:
            return challenge(
                found["check"], found["report_text"], body.field, body.value, body.quote, body.known
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/case/{case_id}/scanbox")
    async def case_scanbox(case_id: str) -> dict[str, Any]:
        """The Parse box on the original scan that holds the scan rung's accepted quote."""
        from app.web.data import valid_case_id
        from app.web.scanbox import scan_box

        if source.mode == "sample":
            return {"scanbox": None}  # scans are local files, not part of the sample
        return {"scanbox": scan_box(valid_case_id(case_id))}

    @app.get("/api/case/{case_id}/scan/{page}.png")
    async def case_scan_page(case_id: str, page: int) -> FileResponse:
        from app.web.data import valid_case_id
        from app.web.scanbox import page_image

        found = None if source.mode == "sample" else page_image(valid_case_id(case_id), page)
        if found is None:
            raise HTTPException(status_code=404, detail="no scan page for this case")
        return FileResponse(found, media_type="image/png")

    @app.get("/api/case/{case_id}/scratchpad")
    async def case_scratchpad(case_id: str) -> dict[str, Any]:
        """Excerpts of Nemotron's reasoning text from one recorded call, if one was recorded."""
        from app.web.data import valid_case_id
        from app.web.scratchpad import scratchpad

        if source.mode == "sample":
            return {"scratchpad": None}
        return {"scratchpad": scratchpad(valid_case_id(case_id))}

    @app.get("/api/case/{case_id}/trace")
    async def case_trace(case_id: str) -> dict[str, Any]:
        """How the latest ladder run read this case (metadata and verdicts only)."""
        from app.web.data import valid_case_id
        from app.web.trace import latest_trace

        if source.mode == "sample":
            return {"trace": None}  # sample mode shows no model output, not even its metadata
        return {"trace": latest_trace(valid_case_id(case_id))}

    @app.get("/api/case/{case_id}/note")
    async def last_case_note(case_id: str) -> dict[str, Any]:
        from app.notes.note import latest_note
        from app.web.data import valid_case_id

        if source.mode == "sample":
            return {"note": None}
        return {"note": latest_note(valid_case_id(case_id))}

    @app.post("/api/case/{case_id}/note")
    async def case_note(case_id: str) -> dict[str, Any]:
        if source.mode == "sample":
            raise HTTPException(
                status_code=409, detail="the case note needs Nightshift (live mode)"
            )
        from app.notes.note import write_note

        found = await _case(case_id, fresh=False)
        try:
            return await write_note({**found, "accepted": _rechecked(found)})
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Nightshift did not return a verified note: {type(exc).__name__}",
            ) from exc

    @app.post("/api/case/{case_id}/decision")
    async def decide(case_id: str, body: Decision) -> dict[str, Any]:
        return await _guarded(source.decide(case_id, body.claim, body.reason_code, body.note))

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/case/{case_id}/second-reader")
    async def case_second_reader(case_id: str) -> dict[str, Any]:
        """Ultra's pre-registered second reading of this case (read-only, from the log)."""
        from app.web.data import valid_case_id
        from app.web.secondreader import case_reading

        return {"second_reader": case_reading(valid_case_id(case_id))}

    @app.get("/api/second-reader")
    async def second_reader_summary() -> dict[str, Any]:
        from app.web.secondreader import summary

        return {"summary": summary()}

    @app.get("/api/labels")
    async def labels() -> dict[str, Any]:
        """The scores against the frozen blind labels, from the committed log (no model call)."""
        from app.web.labelscard import labels_summary

        return {"labels": labels_summary()}

    @app.get("/api/agent-probe")
    async def agent_probe() -> dict[str, Any]:
        """The two pre-registered agent probes, from the committed logs (no model call)."""
        from app.web.agentprobe import probe_story

        return {"probe": probe_story()}

    @app.get("/api/budget-flip")
    async def budget_flip() -> dict[str, Any]:
        """One record, Super alone thinking off vs 4k, from the committed baseline log (no model
        call). Shown in both modes, like the other logged-run cards, labelled as a logged run."""
        case_id = "TCGA-E2-A572"
        path = ROOT_DIR / "logs" / "baseline-m0.jsonl"
        row = next(
            (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and json.loads(x).get("case") == case_id),
            None,
        )
        if not row:
            return {"flip": None}

        def arm(a: dict[str, Any]) -> dict[str, Any]:
            return {k: a.get(k) for k in ("fault", "quote", "completion_tokens", "seconds", "model", "signature")}

        return {"flip": {"case": case_id, "run": row.get("run"), "off": arm(row.get("off") or {}), "budget_4k": arm(row.get("4k") or {})}}

    @app.get("/api/attest")
    async def attest() -> dict[str, Any]:
        """The attestation census, its signatures checked offline here (no key, no model)."""
        from app.web.attestcard import attest_summary

        return {"attest": attest_summary()}

    @app.get("/api/redteam")
    async def redteam() -> dict[str, Any]:
        """The pre-registered v3 red-team chains, from the committed logs (no model call)."""
        from app.web.redteam import v3_chains

        return {"chains": v3_chains()}

    @app.get("/api/route-ledger")
    async def route_ledger() -> dict[str, Any]:
        """Which Nemotron did what (scripts/route_ledger.py output, committed; no model call)."""
        path = ROOT_DIR / "docs" / "evidence" / "route-ledger.json"
        if not path.exists():
            return {"ledger": None}
        return {"ledger": json.loads(path.read_text(encoding="utf-8"))["summary"]}

    @app.get("/api/receipts")
    async def receipts_list() -> dict[str, Any]:
        """The committed receipt bundles (recorded runs; no model call)."""
        from app.web.receiptsbundle import bundle_list

        return {"bundles": bundle_list()}

    @app.get("/api/receipts/{key}")
    async def receipts_bundle(key: str) -> dict[str, Any]:
        """One bundle's envelopes and the committed public key; the browser checks them."""
        from app.web.receiptsbundle import bundle

        found = bundle(key)
        if found is None:
            raise HTTPException(status_code=404, detail="no such bundle")
        return found

    @app.get("/receipts")
    async def receipts_page() -> FileResponse:
        return FileResponse(STATIC / "receipts.html")

    @app.get("/how")
    async def how_it_works() -> FileResponse:
        return FileResponse(STATIC / "how.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
