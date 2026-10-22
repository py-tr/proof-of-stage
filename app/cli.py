"""Operator CLI for dependency checks and the stage_audit semantic layer."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from uuid import uuid4

from app import config, zetaris
from app.providers import nightshift, nvidia
from app.providers.errors import EmptyAnswer
from app.reader.commands import fetch_reports, read_cases
from app.usl.setup import dq_report, setup, status_report, teardown

_PING_MAX_TOKENS = 800
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


def _line(ok: bool, name: str, reason: str) -> str:
    status = "PASS" if ok else "FAIL"
    return f"{status}  {name}: {reason}"


def _sanitize(text: str) -> str:
    cleaned = _URL_RE.sub("", text)
    cleaned = _BEARER_RE.sub("Bearer <redacted>", cleaned)
    for value in config.secret_values():
        cleaned = cleaned.replace(value, "<redacted>")
    return " ".join(cleaned.split())


def _exc_reason(exc: BaseException) -> str:
    return _sanitize(f"{type(exc).__name__}: {exc}")


def _require_text(text: str, label: str) -> str:
    if not text.strip():
        raise EmptyAnswer(f"{label} returned an empty answer")
    return text


async def _doctor() -> int:
    lines: list[str] = []
    failed = 0

    described = config.describe()
    unset = [name for name, state in described.items() if state == "unset"]
    config_ok = not unset
    if config_ok:
        reason = "all variables set"
    else:
        reason = "unset: " + ", ".join(unset)
    lines.append(_line(config_ok, "config", reason))
    if not config_ok:
        failed += 1

    try:
        health = await nightshift.health()
        ok = health == "online"
        lines.append(_line(ok, "nightshift health", health))
        if not ok:
            failed += 1
    except Exception as exc:
        lines.append(_line(False, "nightshift health", _exc_reason(exc)))
        failed += 1

    try:
        text, receipt = await nightshift.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            config.NS_LIGHTNING_CLOUD,
            item_id=f"doctor-chat-{uuid4().hex[:8]}",
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nightshift chat")
        reason = (
            f"model={receipt.winning_model!r} kind={receipt.winning_kind!r} "
            f"egress={receipt.egress_destination!r} sources={receipt.context_sources!r} "
            f"receipt_id={receipt.receipt_id!r}"
        )
        lines.append(_line(True, "nightshift chat", reason))
    except Exception as exc:
        lines.append(_line(False, "nightshift chat", _exc_reason(exc)))
        failed += 1

    try:
        text, _record = await nightshift.local_job(
            [{"role": "user", "content": "Reply with one word: ready"}],
            item_id=f"doctor-local-{uuid4().hex[:8]}",
        )
        _require_text(text, "nightshift local-job")
        lines.append(_line(True, "nightshift local-job", f"text={text!r}"))
    except Exception as exc:
        lines.append(_line(False, "nightshift local-job", _exc_reason(exc)))
        failed += 1

    try:
        text, served = await nvidia.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            config.NV_SUPER,
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nvidia chat")
        lines.append(_line(True, "nvidia chat", f"text={text!r} model={served!r}"))
    except Exception as exc:
        lines.append(_line(False, "nvidia chat", _exc_reason(exc)))
        failed += 1

    try:
        result = await zetaris.ping()
        lines.append(
            _line(True, "zetaris ping", f"rows={len(result.rows)} columns={result.columns!r}")
        )
    except Exception as exc:
        lines.append(_line(False, "zetaris ping", _exc_reason(exc)))
        failed += 1

    sys.stdout.write("\n".join(lines) + "\n")
    return 1 if failed else 0


async def _usl(args: argparse.Namespace) -> int:
    if args.usl_command == "setup":
        await setup()
        return 0
    if args.usl_command == "status":
        sys.stdout.write(await status_report())
        return 0
    if args.usl_command == "dq":
        sys.stdout.write(await dq_report(invalid_rule=args.invalid, limit=args.limit))
        return 0
    if args.usl_command == "teardown":
        if not args.yes:
            sys.stdout.write(
                "teardown refused: pass --yes to remove lightning.metastore.registry_audit, "
                "REG_FILES, GDC_REST, derived_extraction, and flag_log\n"
            )
            return 2
        await teardown()
        return 0
    return 2


def _utf8_stdout() -> None:
    # Model text holds characters like "≤"; a redirected Windows console is cp1252
    # and would raise mid-batch. Replace what cannot be encoded instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check config and each external dependency")
    usl = sub.add_parser("usl", help="Build and query the stage audit semantic layer")
    usl_sub = usl.add_subparsers(dest="usl_command", required=True)
    usl_sub.add_parser("setup", help="Idempotently create the semantic layer")
    usl_sub.add_parser("status", help="Show each object and whether it is activated")
    dq_parser = usl_sub.add_parser("dq", help="Run the stage_check data-quality rules")
    dq_parser.add_argument(
        "--invalid",
        metavar="RULE",
        default=None,
        help="Print invalid records for one rule instead of the count summary",
    )
    dq_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum invalid records to print with --invalid",
    )
    teardown_parser = usl_sub.add_parser(
        "teardown",
        help="Remove only registry_audit, REG_FILES, GDC_REST, and the two Postgres tables",
    )
    teardown_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm removal of those objects",
    )
    reports = sub.add_parser("reports", help="Pathology report text for the audited cases")
    reports_sub = reports.add_subparsers(dest="reports_command", required=True)
    reports_sub.add_parser("fetch", help="Download TCGA-Reports and keep the audited cases")
    read = sub.add_parser("read", help="Nemotron reads reports; verified answers go to Zetaris")
    read.add_argument("--case", action="append", default=None, help="Case id (repeatable)")
    read.add_argument("--rule", default=None, help="Read the cases a DQ rule marks invalid")
    read.add_argument("--limit", type=int, default=5, help="Maximum cases to read")
    read.add_argument(
        "--provider", choices=("nvidia", "nightshift"), default="nvidia", help="Model provider"
    )
    read.add_argument("--store", action="store_true", help="Write results to Zetaris")
    serve = sub.add_parser("serve", help="Run the case page (SAMPLE_MODE=true: offline sample)")
    serve.add_argument("--port", type=int, default=8000, help="Port on 127.0.0.1")
    sample = sub.add_parser("sample", help="Bundled sample cases for SAMPLE_MODE")
    sample_sub = sample.add_subparsers(dest="sample_command", required=True)
    sample_sub.add_parser("build", help="Rebuild app/web/sample/cases.json from the live USL")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return asyncio.run(_doctor())
        if args.command == "usl":
            return asyncio.run(_usl(args))
        if args.command == "reports":
            sys.stdout.write(asyncio.run(fetch_reports()))
            return 0
        if args.command == "serve":
            import uvicorn

            from app.web.api import create_app

            uvicorn.run(create_app(), host="127.0.0.1", port=args.port)
            return 0
        if args.command == "sample":
            from app.web.sample import build_sample

            sys.stdout.write(f"sample -> {asyncio.run(build_sample()).name}\n")
            return 0
        if args.command == "read":
            return asyncio.run(
                read_cases(
                    case_ids=args.case,
                    rule=args.rule,
                    limit=args.limit,
                    provider=args.provider,
                    store=args.store,
                )
            )
    except Exception as exc:
        sys.stderr.write(_sanitize(f"{type(exc).__name__}: {exc}") + "\n")
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
