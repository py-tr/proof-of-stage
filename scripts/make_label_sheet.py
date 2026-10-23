# ruff: noqa: E501  (the embedded HTML page has long lines)
"""Build the blind labelling sheet for the review queue (pre-registered ground truth).

The sheet shows only what a reviewer would have: the registry's recorded N category and
positive-node count (from the USL table stage_check), the paraphrased count rule, and the
full pathology report. It never shows the system's verdict, the model's readings or its
quotes. The reviewer names the field the report contradicts and copies the supporting line.

It embeds full report texts, so it is written OUTSIDE the repository (report texts are not
committed). Usage: python scripts/make_label_sheet.py <output.html>
"""

from __future__ import annotations

import asyncio
import html
import json
import random
import sys
from pathlib import Path

from app.engine.run_case import _rows
from app.reports.ingest import read_reports_csv
from app.usl.client import select
from app.usl.model import table_fqn
from app.web.evidence import n_range

SEED = 20261023


async def queue() -> list[dict]:
    rows = _rows(
        await select(
            "SELECT case_id, edition_code, site_key, recorded_n, lymph_nodes_positive, "
            f"lymph_nodes_tested, derived_n FROM {table_fqn('stage_check')} "
            "WHERE reason_class IN ('n_count_contradiction', 'n_missing_derivable')",
            limit=100,
        )
    )
    reports = read_reports_csv()
    cases = []
    for row in rows:
        report = reports.get(row["case_id"])
        if report is None:
            continue
        count = row.get("lymph_nodes_positive")
        cases.append(
            {
                "case_id": row["case_id"],
                "edition": row.get("edition_code"),
                "recorded_n": row.get("recorded_n") or "missing",
                "recorded_n_means": n_range(
                    row.get("recorded_n"), row.get("edition_code"), row.get("site_key")
                )
                if row.get("recorded_n")
                else None,
                "recorded_count": None if count in (None, "") else f"{float(count):g}",
                "tested": None
                if row.get("lymph_nodes_tested") in (None, "")
                else f"{float(row['lymph_nodes_tested']):g}",
                "count_rule_gives": row.get("derived_n"),
                "report": report.report_text,
            }
        )
    random.Random(SEED).shuffle(cases)  # a fixed order that is not the queue's
    return cases


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blind labels: review queue</title>
<style>
body { margin: 0; font: 14px/1.5 system-ui, "Segoe UI", sans-serif; color: #1d1d1b; background: #f6f6f3; }
header { position: sticky; top: 0; background: #1d1d1b; color: #fff; padding: 8px 14px; display: flex; gap: 12px; align-items: center; }
header button { font: inherit; padding: 4px 10px; border-radius: 6px; border: 0; cursor: pointer; }
main { display: grid; grid-template-columns: 380px minmax(0, 1fr); gap: 14px; padding: 14px; max-width: 1400px; margin: 0 auto; }
.card { background: #fff; border: 1px solid #e3e2dd; border-radius: 10px; padding: 12px 14px; }
.reg td, .reg th { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eee; }
.opt { display: block; margin: 6px 0; padding: 8px 10px; border: 1px solid #ddd; border-radius: 8px; cursor: pointer; }
.opt input { margin-right: 8px; }
textarea, input[type=text] { width: 100%; font: 13px ui-monospace, Consolas, monospace; box-sizing: border-box; }
pre { white-space: pre-wrap; font: 12.5px/1.6 ui-monospace, Consolas, monospace; margin: 0; max-height: 78vh; overflow: auto; }
.small { color: #6b6b66; font-size: 12px; }
.done { color: #2e7d32; }
mark { background: #fff3a0; border-radius: 2px; }
mark.cur { background: #ffb74d; outline: 2px solid #e65100; }
.sec { color: #1d4ed8; font-weight: 700; }
.sec.skip { color: #8a8a85; text-decoration: line-through; }
.sec.skip::after { content: " (not the result)"; font-weight: 400; text-decoration: none; }
.guide { background: #eef3fb; border: 1px solid #c9d7ee; border-radius: 8px; padding: 8px 10px; font-size: 13px; margin-bottom: 10px; }
</style></head><body>
<header><b>Blind labels</b><span id="pos"></span><span id="progress" class="small"></span>
<button id="prev">◀ prev</button><button id="next">next ▶</button><button id="dl">Download labels.json</button></header>
<main>
<div>
<div class="guide"><b>How to label (no medical knowledge needed)</b><br>
0. <span class="sec">Blue headings</span> = sections. The result is in FINAL DIAGNOSIS / SYNOPTIC / ADDENDUM; struck-through ones (pre-op, post-op, frozen section, gross) are not the result.<br>
1. Use the yellow highlights / "next node line" to find what the report says about lymph nodes.<br>
2. Write the <b>total</b> positive nodes (some reports list each specimen; the total is the summary line or the sum) and the pN category if printed (e.g. pT2N1aMX = N1a).<br>
3. Compare with the registry: report count fits the registry N but not its count = <b>count wrong</b>; fits the count but not the N = <b>N wrong</b>; unclear, micrometastases, isolated tumour cells, no count, or both off = <b>a person decides</b> (a valid answer).</div>
<div class="card">
<div class="small">Case <span id="cid"></span> · AJCC edition <span id="ed"></span></div>
<h3 style="margin:6px 0">What the registry says</h3>
<table class="reg">
<tr><th>Recorded N category</th><td id="rn"></td></tr>
<tr><th>Recorded positive nodes</th><td id="rc"></td></tr>
<tr><th>The count rule turns that count into</th><td id="rule"></td></tr>
</table>
<p class="small">Paraphrased rule: N0 = no positive nodes, N1 = 1–3, N2 = 4–9, N3 = 10 or more (micrometastases and isolated tumour cells are their own categories).</p>
</div>
<div class="card" style="margin-top:12px">
<h3 style="margin:0 0 6px">Your reading of the report</h3>
<label class="small">Positive lymph nodes the report states (total), or leave empty if it states none</label>
<input type="text" id="count">
<label class="small">N category the report states, if any (e.g. pN1a)</label>
<input type="text" id="n">
<p style="margin:10px 0 4px"><b>Which registry field does the report contradict?</b></p>
<label class="opt"><input type="radio" name="f" value="node_count">The node count is wrong (the report backs the N category)</label>
<label class="opt"><input type="radio" name="f" value="pathologic_n">The N category is wrong or missing (the report backs the count)</label>
<label class="opt"><input type="radio" name="f" value="review">A person must decide (the report settles neither, or contradicts both)</label>
<label class="small">The line(s) in the report that convinced you: each selection in the report is added on a new line (you can also edit the box) <button id="clearq" type="button" style="font-size:11px">clear</button></label>
<textarea id="quote" rows="4"></textarea>
<label class="small">Notes (optional)</label>
<input type="text" id="note">
</div>
<p class="small">Saved in this browser as you go. Download when done and send the file to Claude.</p>
</div>
<div class="card"><h3 style="margin:0 0 6px">Pathology report <button id="hit">next node line ▼</button> <span id="hits" class="small"></span></h3><pre id="report"></pre></div>
</main>
<script>
const CASES = __CASES__;
const KEY = "blind-labels-v1";
let labels = {}; try { labels = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let i = 0;
const $ = (id) => document.getElementById(id);
function save() { try { localStorage.setItem(KEY, JSON.stringify(labels)); } catch (e) {} progress(); }
function progress() { const n = CASES.filter((c) => labels[c.case_id] && labels[c.case_id].field).length; $("progress").textContent = `${n} of ${CASES.length} labelled`; }
function show() {
  const c = CASES[i], l = labels[c.case_id] || {};
  $("pos").textContent = `${i + 1} / ${CASES.length}`;
  $("cid").textContent = c.case_id; $("ed").textContent = c.edition || "—";
  $("rn").textContent = c.recorded_n + (c.recorded_n_means ? ` (${c.recorded_n_means})` : "");
  $("rc").textContent = c.recorded_count == null ? "missing" : c.recorded_count + (c.tested ? ` of ${c.tested} examined` : "");
  $("rule").textContent = c.count_rule_gives || "—";
  renderReport(c.report);
  $("count").value = l.count || ""; $("n").value = l.n || ""; $("quote").value = l.quote || ""; $("note").value = l.note || "";
  document.querySelectorAll("input[name=f]").forEach((r) => (r.checked = r.value === l.field));
}
// Keyword highlights only (no model output): lines about lymph nodes and the N category.
const KW = /(lymph\s*nodes?|nodes?|pN\s*\w*|N\s*stage|positive|metasta\w*|\d+\s*\/\s*\d+|\w+\s+of\s+\w+\s+(?:lymph\s+)?nodes?)/gi;
let hitIndex = -1;
// Section headings (blue): the result is in FINAL DIAGNOSIS / SYNOPTIC / ADDENDUM; the
// pre-op, post-op, frozen-section and gross parts are struck through (not the result).
const SEC = /(PRE-?\s?OPERATIVE DIAGNOSIS|POST-?\s?OPERATIVE DIAGNOSIS|FROZEN SECTION[A-Z ]*|INTRA-?\s?OPERATIVE[A-Z ]*|GROSS DESCRIPTION|MICROSCOPIC DESCRIPTION|FINAL (?:PATHOLOGIC )?DIAGNOSIS|DIAGNOSIS|SYNOPTIC[A-Z \-]*|CASE SYNOPSIS|COMMENTS?|ADDENDUM[A-Z ]*|CLINICAL HISTORY)/gi;
const SKIP = /PRE-?\s?OPERATIVE|POST-?\s?OPERATIVE|FROZEN|INTRA-?\s?OPERATIVE|GROSS|CLINICAL HISTORY/i;
function renderReport(text) {
  const pre = $("report"); pre.replaceChildren();
  const marks = [];
  let m; KW.lastIndex = 0; while ((m = KW.exec(text)) !== null) marks.push([m.index, m.index + m[0].length, "kw"]);
  SEC.lastIndex = 0; while ((m = SEC.exec(text)) !== null) marks.push([m.index, m.index + m[0].length, SKIP.test(m[0]) ? "skip" : "sec"]);
  marks.sort((a, b) => a[0] - b[0]);
  let last = 0;
  for (const [a, b, kind] of marks) {
    if (a < last) continue;
    if (a > last) pre.append(document.createTextNode(text.slice(last, a)));
    const node = document.createElement(kind === "kw" ? "mark" : "span");
    if (kind !== "kw") node.className = kind === "skip" ? "sec skip" : "sec";
    node.textContent = text.slice(a, b); pre.append(node); last = b;
  }
  pre.append(document.createTextNode(text.slice(last))); hitIndex = -1;
  $("hits").textContent = `${pre.querySelectorAll("mark").length} highlights`;
}
function nextHit() {
  const marks = $("report").querySelectorAll("mark"); if (!marks.length) return;
  marks.forEach((x) => x.classList.remove("cur")); hitIndex = (hitIndex + 1) % marks.length;
  marks[hitIndex].classList.add("cur"); marks[hitIndex].scrollIntoView({ block: "center", behavior: "smooth" });
}
function upd() {
  const c = CASES[i]; const f = document.querySelector("input[name=f]:checked");
  labels[c.case_id] = { field: f ? f.value : null, count: $("count").value.trim(), n: $("n").value.trim(), quote: $("quote").value, note: $("note").value, at: new Date().toISOString() };
  save();
}
["count", "n", "quote", "note"].forEach((id) => $(id).addEventListener("input", upd));
document.querySelectorAll("input[name=f]").forEach((r) => r.addEventListener("change", upd));
$("report").addEventListener("mouseup", () => {
  const s = String(window.getSelection() || "").trim();
  if (s.length <= 3) return;
  const lines = $("quote").value.split("\n").map((l) => l.trim()).filter(Boolean);
  if (!lines.includes(s)) lines.push(s);
  $("quote").value = lines.join("\n"); upd();
});
$("clearq").onclick = () => { $("quote").value = ""; upd(); };
$("hit").onclick = nextHit;
$("prev").onclick = () => { i = (i + CASES.length - 1) % CASES.length; show(); };
$("next").onclick = () => { i = (i + 1) % CASES.length; show(); };
$("dl").onclick = () => {
  const out = { labeller: "the builder (a lay reader, not a pathologist)", sheet_seed: __SEED__, labels };
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], { type: "application/json" }));
  a.download = "labels.json"; a.click();
};
show(); progress();
</script></body></html>
"""


def main(out: str) -> None:
    cases = asyncio.run(queue())
    page = PAGE.replace("__CASES__", json.dumps(cases, ensure_ascii=False)).replace(
        "__SEED__", str(SEED)
    )
    Path(out).write_text(page, encoding="utf-8")
    print(f"{len(cases)} cases -> {html.escape(out)}")


if __name__ == "__main__":
    main(sys.argv[1])
