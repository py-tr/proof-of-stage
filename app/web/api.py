"""FastAPI app for the one-case-at-a-time page."""

from __future__ import annotations

import asyncio
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
from app.web.evidence import challenge, count_rules, headline, recheck
from app.web.lineage import LiveLineage, MirrorLineage, lineage
from app.zetaris import ZetarisError

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
        warming = asyncio.get_running_loop().create_task(rule_source.warm())
        yield
        warming.cancel()

    app = FastAPI(title="Proof of Stage", docs_url=None, redoc_url=None, lifespan=lifespan)

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
                "R1 Nemotron Lightning, thinking off; R2 and R3 Nemotron Super, "
                f"thinking budget {THINKING_BUDGET}"
            ),
            "source_note": getattr(source, "source_note", None),
        }

    @app.get("/api/cohort")
    async def cohort() -> dict[str, Any]:
        return await _guarded(source.cohort())

    @app.get("/api/queue")
    async def queue() -> list[dict[str, Any]]:
        rows = await _guarded(source.queue())
        return [{**row, "headline": headline(row)} for row in rows]

    async def _case(case_id: str, fresh: bool = True) -> dict[str, Any]:
        found = await _guarded(source.case(case_id, fresh=fresh))
        if found is None:
            raise HTTPException(status_code=404, detail="case not found")
        return found

    @app.get("/api/case/{case_id}")
    async def case(case_id: str) -> dict[str, Any]:
        found = await _case(case_id)
        check = found["check"]
        edition, site = check.get("edition_code"), check.get("site_key")
        return {
            **found,
            "accepted": _rechecked(found),
            "headline": headline(check),
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

    @app.get("/api/redteam")
    async def redteam() -> dict[str, Any]:
        """The pre-registered v3 red-team chains, from the committed logs (no model call)."""
        from app.web.redteam import v3_chains

        return {"chains": v3_chains()}

    @app.get("/how")
    async def how_it_works() -> FileResponse:
        return FileResponse(STATIC / "how.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
