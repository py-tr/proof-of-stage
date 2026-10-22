from __future__ import annotations

from app.usl.client import guard_select
from app.usl.demo import StepResult, render, steps


def test_every_demo_query_passes_the_read_guard() -> None:
    for step in steps():
        guard_select(step.sql)  # the pack only reads, through the same guard as the app


def test_render_follows_the_demo_template_and_shows_failures() -> None:
    pack = steps()
    results = [StepResult(pack[0], 1.2, ["usl_table", "rows"], [["flag", 6]], 8)]
    results.append(StepResult(pack[1], 0.5, [], [], 0, error="boom"))
    text = render(
        results,
        {
            "run_at": "2026-10-23 04:00 UTC",
            "contract_tables": 8,
            "contract_seconds": 1.0,
            "total_seconds": 3.0,
        },
    )
    for heading in ("## What we built", "## What data", "## How to run it", "## Cleanup"):
        assert heading in text
    assert "(first 1 of 8)" in text and "**Failed:** boom" in text
