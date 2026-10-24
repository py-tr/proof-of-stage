"""Operator CLI for dependency checks and the stage_audit semantic layer."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

from app import config, zetaris
from app.providers import nightshift, nvidia
from app.providers.errors import EmptyAnswer
from app.providers.receipts import key_fingerprint
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
        pinned = config.getenv("NS_RECEIPT_PUBKEY")
        text, receipt = await nightshift.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            config.NS_SUPER_VL,
            item_id=f"doctor-chat-{uuid4().hex[:8]}",
            require_model=config.NS_SUPER_VL,
            retry_on_mismatch=True,
            require_signature=True,
            pinned_key=pinned,
            allow_cache=False,
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nightshift chat")
        reason = (
            f"model={receipt.winning_model!r} kind={receipt.winning_kind!r} "
            f"egress={receipt.egress_destination!r} sources={receipt.context_sources!r} "
            f"receipt_id={receipt.receipt_id!r} signature={receipt.signature} "
            f"signer={key_fingerprint(receipt.signer_key)} "
            f"key={'pinned (NS_RECEIPT_PUBKEY)' if pinned else 'NOT pinned: set NS_RECEIPT_PUBKEY'}"
        )
        lines.append(_line(True, "nightshift chat", reason))
    except Exception as exc:
        lines.append(_line(False, "nightshift chat", _exc_reason(exc)))
        failed += 1

    try:
        found = await nightshift.discover()
        text_class = found.get("text", {})
        ok = found.get("state") == "online" and config.NS_SUPER_VL in text_class.get("cloud", [])
        lines.append(
            _line(
                ok,
                "nightshift discovery",
                f"state={found.get('state')} models={len(found.get('models', []))} "
                f"modes={len(found.get('modes', []))} text={text_class.get('availability')!r} "
                f"ready={text_class.get('ready')!r} super_vl_cloud={ok}",
            )
        )
        if not ok:
            failed += 1
    except Exception as exc:
        lines.append(_line(False, "nightshift discovery", _exc_reason(exc)))
        failed += 1

    try:
        # contract v4's own done-test: a plain text request on a routing mode returns a string
        text, receipt = await nightshift.chat(
            [{"role": "user", "content": "Reply with one word: ready"}],
            "meterless/text",
            item_id=f"doctor-mode-{uuid4().hex[:8]}",
            require_signature=True,
            pinned_key=config.getenv("NS_RECEIPT_PUBKEY"),
            allow_cache=False,
            max_tokens=_PING_MAX_TOKENS,
        )
        _require_text(text, "nightshift meterless/text")
        lines.append(
            _line(
                True,
                "nightshift meterless/text",
                f"routed={receipt.winning_model!r} kind={receipt.winning_kind!r} "
                f"signature={receipt.signature}",
            )
        )
    except Exception as exc:
        reason = _exc_reason(exc)
        if "No provider is configured" in reason or "no_route" in reason:
            # 1.2.3: an opted-in Super VL is kept out of automatic routing, so a routing
            # mode needs another lane on Race; our product calls name Super VL explicitly
            reason += (
                " | no lane for automatic routing: an opted-in Super VL is excluded from"
                " races; put another Nemotron lane on Race, or rely on the explicit-id"
                " check above"
            )
        lines.append(_line(False, "nightshift meterless/text", reason))
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
    if args.usl_command == "demo":
        from app.usl.demo import run_demo, summary, write_doc, write_snapshot

        results, meta = await run_demo()
        sys.stdout.write(summary(results, meta))
        if args.write:
            sys.stdout.write(f"wrote {write_doc(results, meta).name}\n")
            snapshot = write_snapshot(results, meta)
            if snapshot:
                sys.stdout.write(f"wrote {snapshot.name}\n")
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


async def _reader_bench(step: str) -> int:
    from app.engine import baseline, reader_bench

    if step == "run":
        sys.stdout.write(json.dumps(await reader_bench.run_bench(), indent=2) + "\n")
        return 0
    reader_bench.frozen_case_ids()
    if not baseline.LABELS.exists():
        sys.stderr.write("no frozen labels yet\n")
        return 1
    text = baseline.LABELS.read_text(encoding="utf-8")
    if baseline.sha16(text) != baseline.LABELS.with_suffix(".sha16").read_text().strip():
        sys.stderr.write("the labels changed since they were frozen\n")
        return 1
    rows = [json.loads(line) for line in reader_bench.LOG.read_text(encoding="utf-8").splitlines()]
    result = reader_bench.score(rows, json.loads(text)["labels"])
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


async def _baseline(step: str) -> int:
    from app.engine import baseline

    if step == "run":
        sys.stdout.write(json.dumps(await baseline.run_baseline(), indent=2) + "\n")
        return 0
    record = baseline.frozen()
    if not baseline.LABELS.exists():
        sys.stderr.write(f"no frozen labels at {baseline.LABELS.relative_to(baseline.ROOT)}\n")
        return 1
    labels_text = baseline.LABELS.read_text(encoding="utf-8")
    want = (baseline.LABELS.with_suffix(".sha16")).read_text(encoding="utf-8").strip()
    if baseline.sha16(labels_text) != want:
        sys.stderr.write("the labels changed since they were frozen\n")
        return 1
    rows = await baseline.queue_rows(list(record["cases"]))
    a0 = {c: r.get("fault_field") for c, r in rows.items()}
    m0 = [json.loads(line) for line in baseline.LOG.read_text(encoding="utf-8").splitlines()]
    runs = {r["run"] for r in m0}
    if len(runs) != 1:
        sys.stderr.write(f"expected one M0 run in the log, found {sorted(runs)}\n")
        return 1
    result = baseline.score(m0, json.loads(labels_text)["labels"], a0)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


async def _adversary(version: str = "v2") -> int:
    from app.engine.adversary import frozen_cases, frozen_provider, prereg_path, run_chain
    from app.reports.ingest import read_reports_csv

    path = prereg_path(version)
    provider = frozen_provider(path)
    frozen = json.loads(path.read_text(encoding="utf-8"))
    known = frozenset(frozen.get("known_limits", ["fraction_under", "cued_over"]))
    stop = frozen.get("stop_after_consecutive_failures")
    reports = {cid: r.report_text for cid, r in read_reports_csv().items()}
    for case in frozen_cases(reports, path):
        record = await run_chain(
            case,
            reports[case.case_id],
            provider=provider,
            known_limits=known,
            stop_after_failures=stop,
        )
        sys.stdout.write(
            f"{case.case_id}: steps={record['steps']} engine={record['engine_status']} "
            f"wrong accepts={record['accepts_wrong']} bugs={len(record['bugs'])} "
            f"known-limit={len(record['known_limit_accepts'])} "
            f"carryover failures={record['carryover_failures']} "
            f"tokens saved (est)={record['tokens_saved_est']} "
            f"verdicts={record['verdicts']}" + "\n"
        )
        for row in record["bugs"] + record["known_limit_accepts"]:
            sys.stdout.write(
                f"  accept step {row['step']}: {row['value']} {row['kind']} {row['quote']!r}" + "\n"
            )
    return 0


async def _notes(case_ids: list[str], writer: str = "super") -> int:
    from app.notes.note import write_note
    from app.web.api import _rechecked
    from app.web.data import LiveData

    data, failed = LiveData(), 0
    for case_id in case_ids:
        found = await data.case(case_id)
        if found is None:
            sys.stdout.write(f"{case_id}: not found" + "\n")
            failed += 1
            continue
        try:
            note = await write_note({**found, "accepted": _rechecked(found)}, writer=writer)
        except Exception as exc:
            sys.stdout.write(f"{case_id}: ERROR {_exc_reason(exc)}" + "\n")
            failed += 1
            continue
        rc = note.get("receipt") or {
            "model": note.get("model"),
            "signature": "-",
            "receipt_id": "-",
        }
        sys.stdout.write(
            f"{case_id}: {note['status']} {note['reason']} {note['seconds']}s "
            f"model={rc['model']} signature={rc['signature']} receipt={rc['receipt_id']}" + "\n"
        )
        for sentence in note["sentences"]:
            cites = "".join(f"[{c}]" for c in sentence["cites"])
            sys.stdout.write(f"  {sentence['text']} {cites}" + "\n")
    return 1 if failed else 0


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
    demo_parser = usl_sub.add_parser("demo", help="Timed, reproducible USL query pack")
    demo_parser.add_argument("--write", action="store_true", help="Save docs/zetaris-demo.md")
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
        "--provider",
        choices=("nvidia", "nightshift"),
        default="nvidia",
        help="Model provider (legacy command; default NVIDIA direct; the ladder is `run`)",
    )
    read.add_argument("--store", action="store_true", help="Write results to Zetaris")
    scans = sub.add_parser("scans", help="Original report scans (GDC PDFs) read by Nemotron Parse")
    scans.add_argument("--case", action="append", required=True, help="Case id (repeatable)")
    run = sub.add_parser("run", help="One case through the Markovian evidence ladder (RUNGS)")
    run.add_argument("--case", required=True, help="Case id, e.g. TCGA-A2-A0CV")
    run.add_argument("--store", action="store_true", help="Append closed fields to Zetaris")
    run.add_argument(
        "--provider",
        choices=("nightshift", "nvidia"),
        default="nightshift",
        help="Nightshift (default: each rung's model pinned, Lightning at R1 and Super VL "
        "at R2/R3, signed receipts) or NVIDIA direct",
    )
    adversary = sub.add_parser(
        "adversary", help="The pre-registered red-team chain (3 cases x 20 steps)"
    )
    adversary.add_argument(
        "--version", default="v2", help="Which pre-registration to run (v2, v3); v2 is done"
    )
    sub.add_parser(
        "dial", help="Pre-registered dial test: the ladder vs always-4k, 30 consistent records"
    )
    bench = sub.add_parser(
        "reader-bench", help="Pre-registered: which Nemotron reads the queue best (run, then score)"
    )
    bench.add_argument("step", choices=("run", "score"))
    sub.add_parser(
        "r1-timing", help="Pre-registered: Lightning vs Super at R1, same hour, 3 trials"
    )
    sub.add_parser(
        "ultra-critic-v2",
        help="Pre-registered: the Ultra critic v2 (one Nightshift scope per call)",
    )
    sub.add_parser(
        "ultra-critic", help="Pre-registered: Ultra as a second reader that can only object"
    )
    sub.add_parser(
        "vision-scan", help="Pre-registered: Super VL reads the scan images vs Parse + Super"
    )
    sub.add_parser(
        "local-r1", help="Pre-registered: local Nemotron Lightning as the first read (on-device)"
    )
    sub.add_parser(
        "agent-probe-3", help="Pre-registered: does an agent use the verdict given the DQ rules"
    )
    sub.add_parser(
        "agent-probe-2", help="Pre-registered follow-up: does an agent use the checked column"
    )
    sub.add_parser(
        "agent-probe",
        help="Pre-registered: does an agent reading the USL descriptions use the verdict",
    )
    sub.add_parser(
        "hidden", help="Pre-registered: hidden errors in 60 consistent records (the ladder)"
    )
    sub.add_parser(
        "lightning", help="Pre-registered: Lightning in R1's place on the dial test's 28 records"
    )
    baseline = sub.add_parser(
        "baseline", help="Pre-registered M0: Super alone on the queue (run), then score vs labels"
    )
    baseline.add_argument("step", choices=("run", "score"))
    labels = sub.add_parser(
        "labels", help="Freeze the blind labels, then score every run that waits for them"
    )
    labels.add_argument("step", choices=("freeze", "score"))
    labels.add_argument("path", nargs="?", help="freeze: the labels.json the sheet downloaded")
    note = sub.add_parser("note", help="A cited case note by Super through Nightshift")
    note.add_argument("--case", action="append", required=True, help="Case id (repeatable)")
    note.add_argument(
        "--writer",
        choices=("super", "ultra"),
        default="super",
        help="super: through Nightshift (default); ultra: Nemotron Ultra on NVIDIA direct",
    )
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
        if args.command == "run":
            from app.engine.run_case import run_case, summary

            ladder, outcome = asyncio.run(
                run_case(args.case.strip().upper(), store=args.store, provider=args.provider)
            )
            sys.stdout.write(summary(ladder, outcome))
            return 0
        if args.command == "dial":
            from app.engine.dial import run_sample

            sys.stdout.write(json.dumps(asyncio.run(run_sample()), indent=2) + "\n")
            return 0
        if args.command == "reader-bench":
            return asyncio.run(_reader_bench(args.step))
        if args.command == "ultra-critic-v2":
            from app.engine.critic_v2 import run_critic_v2

            out = asyncio.run(run_critic_v2())
            sys.stdout.write(json.dumps(out, indent=2, default=str) + chr(10))
            return 0
        if args.command == "ultra-critic":
            from app.engine.critic import run_critic

            out = asyncio.run(run_critic())
            sys.stdout.write(json.dumps(out, indent=2, default=str) + chr(10))
            return 0
        if args.command == "vision-scan":
            from app.engine.vision import run_vision

            sys.stdout.write(json.dumps(asyncio.run(run_vision()), indent=2, default=str) + "\n")
            return 0
        if args.command == "r1-timing":
            from app.engine.timing import run_timing

            sys.stdout.write(json.dumps(asyncio.run(run_timing()), indent=2, default=str))
            return 0
        if args.command == "local-r1":
            from app.engine.local_r1 import run_local_r1

            sys.stdout.write(json.dumps(asyncio.run(run_local_r1()), indent=2, default=str))
            return 0
        if args.command == "agent-probe-3":
            from app.engine.agent_probe3 import run_probe3

            sys.stdout.write(json.dumps(asyncio.run(run_probe3()), indent=2, default=str))
            return 0
        if args.command == "agent-probe-2":
            from app.engine.agent_probe2 import run_probe2

            sys.stdout.write(json.dumps(asyncio.run(run_probe2()), indent=2, default=str))
            return 0
        if args.command == "agent-probe":
            from app.engine.agent_probe import run_probe

            sys.stdout.write(json.dumps(asyncio.run(run_probe()), indent=2, default=str))
            return 0
        if args.command == "hidden":
            from app.engine.hidden import run_hidden

            sys.stdout.write(json.dumps(asyncio.run(run_hidden()), indent=2) + "\n")
            return 0
        if args.command == "lightning":
            from app.engine.lightning import run_lightning

            sys.stdout.write(json.dumps(asyncio.run(run_lightning()), indent=2) + "\n")
            return 0
        if args.command == "labels":
            from app.engine import labels as labels_mod

            if args.step == "freeze":
                if not args.path:
                    sys.stderr.write("usage: labels freeze <labels.json>\n")
                    return 2
                out = labels_mod.freeze(Path(args.path))
            else:
                out = asyncio.run(labels_mod.score_all())
            sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")
            return 0
        if args.command == "baseline":
            return asyncio.run(_baseline(args.step))
        if args.command == "adversary":
            return asyncio.run(_adversary(args.version))
        if args.command == "note":
            return asyncio.run(_notes([c.strip().upper() for c in args.case], args.writer))
        if args.command == "scans":
            from app.scans.scans import parse_scan, write_parse_blocks_csv

            for case_id in args.case:
                found = asyncio.run(parse_scan(case_id.upper()))
                blocks = sum(len(page) for page in found["pages"])
                sys.stdout.write(
                    f"{case_id}: {len(found['pages'])} pages, {blocks} blocks, {found['model']}\n"
                )
            out, rows = write_parse_blocks_csv()
            sys.stdout.write(f"{out.name}: {rows} blocks (run `usl setup` to load them)\n")
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
