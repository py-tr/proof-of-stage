// How it works: one record, nine numbered steps, every value read from the same API the case
// page uses (live in live mode; a dated copy in sample mode; logged runs labelled as logged in both). Plain JS; every text is a text node.
"use strict";

const $ = (id) => document.getElementById(id);
const show = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
const num = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? null : Number(v));
const RUNG = { R1: "first read", R2: "deep read", R3: "scan read" };
const REASON = {
  quote_not_in_report: "its quote is not in the report",
  quote_does_not_support: "its quote does not show that value",
  count_not_in_quote: "the number is not the positive count in its quote",
  count_below_report: "below a node fraction the report states",
  count_not_report_total: "not the total the report states",
  model_abstained: "no value given",
};

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) k === "class" ? (node.className = v) : node.setAttribute(k, v);
  for (const c of children) if (c != null && c !== false) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function card(who, title, ...body) {
  return el("div", { class: "step-card" }, el("div", { class: "who" }, who), el("h2", {}, title), ...body);
}

function flow(...items) {
  return el("div", { class: "flow" }, ...items.filter(Boolean).map(([text, kind]) => el("span", { class: kind || "" }, text)));
}

function title(c, sample) {
  if (sample && !c.fault_field) return "In sample mode you play the reader";
  if (c.fault_field === "node_count") return "The report contradicts the count";
  if (c.fault_field === "pathologic_n") return c.reason_class === "n_missing_derivable" ? "The report gives the missing stage field" : "The report contradicts the stage field";
  if (c.fault_field === "review") return "A person decides: the report does not settle it";
  return "The registry fields agree";
}

function render(data, trace, sample) {
  const c = data.check;
  const steps = $("steps");
  steps.replaceChildren();
  const rule = (data.rules.registry_count || [])[0];
  const contradiction = c.reason_class === "n_count_contradiction";
  const failed = (data.lineage.failed || []).map((f) => f.rule);

  // 1. Zetaris finds the record
  steps.append(el("li", { class: "alert" }, card("Zetaris semantic layer",
    contradiction ? "This record cannot be true as written" : c.reason_class === "n_missing_derivable" ? "This record is missing an N its own count could fill" : "This record is checked",
    flow([`recorded N: ${show(c.recorded_n)}`], [`recorded count: ${show(num(c.lymph_nodes_positive))} positive nodes`, contradiction && c.fault_field === "node_count" ? "bad" : ""],
      rule ? [`${show(num(c.lymph_nodes_positive))} nodes → ${rule.output} (rule ${rule.rule_id})`] : null),
    el("p", { class: "small" }, failed.length ? `Data-quality rules that flag it: ${failed.join(", ")}.` : "No data-quality rule flags it."))));

  // 2. Nemotron reads the report
  const rungs = trace ? trace.rungs : [];
  steps.append(el("li", {}, card("NVIDIA Nemotron through Meterless Nightshift",
    "Nemotron reads the pathology report, thinking off first",
    sample ? el("p", { class: "small" }, "Sample mode: no model run is shown, and none is replayed.")
      : rungs.length ? flow(...rungs.map((r) => {
          const n = r.fields.N || {}, k = r.fields.NPOS || {};
          const both = n.status === "accepted" && k.status === "accepted";
          return [`${RUNG[r.rung] || r.rung} · thinking ${r.thinking} · ${show(r.seconds)} s · ${both ? `${n.value}, ${k.value}` : "rejected or open"}`, both ? "good" : "bad"];
        }))
      : el("p", { class: "small" }, "No reading logged for this case yet."),
    rungs.length ? el("p", { class: "small" }, `Every read: ${[...new Set(rungs.map((r) => r.provider))].join(", ")}; ${rungs.filter((r) => r.signature === "verified").length} of ${rungs.length} with a verified signed receipt.`) : null)));

  // 3. The guard
  const accepted = (data.accepted || []).filter((x) => x.field === "N" || x.field === "NPOS");
  const quotes = [...new Set(accepted.map((x) => x.quote))];
  const rejected = rungs.flatMap((r) => Object.entries(r.fields).filter(([, f]) => f.status !== "accepted" && REASON[f.reason])
    .map(([name, f]) => `${RUNG[r.rung] || r.rung}: ${name === "NPOS" ? "count" : name} ${show(f.value)}, rejected (${REASON[f.reason]})`));
  steps.append(el("li", {}, card("The guard (code)", "A value counts only if its quote shows it",
    quotes.length ? el("p", {}, ...quotes.map((q, i) => el("span", {}, i ? " · " : "", el("span", { class: "how-quote" }, `“${q}”`))))
      : el("p", { class: "small" }, sample ? "In sample mode, type a reading on the case page and the same guard decides." : "No accepted quote."),
    accepted.length ? flow(...accepted.map((x) => [`${x.field === "NPOS" ? "positive nodes" : "N"} ${x.value} ✓`, "good"])) : null,
    ...rejected.slice(0, 3).map((t) => el("p", { class: "small" }, t)))));

  // 4. The verdict
  steps.append(el("li", { class: c.fault_field === "review" ? "" : "alert" }, card("Zetaris semantic layer", title(c, sample),
    flow([`registry N ${show(c.recorded_n)} · report N ${show(c.report_n)}`, c.fault_field === "pathologic_n" ? "bad" : ""],
      [`registry count ${show(num(c.lymph_nodes_positive))} · report count ${show(num(c.report_nodes_positive))}`, c.fault_field === "node_count" ? "bad" : ""]),
    el("p", { class: "small" }, data.headline))));

  // 5. A person decides
  steps.append(el("li", {}, card("You", "A person decides",
    el("p", {}, "Agree with the named field, name the other one, or say neither, on the case page. ",
      el("a", { href: `/?case=${c.case_id}` }, "Decide on this case →")),
    el("p", { class: "small" }, "Each decision is a new append-only row in Zetaris; the record itself is never edited."))));

  // 6. The second reader (filled in by loadSecondReaderCard): it can only object, and an objection sends the case to a person
  steps.append(el("li", { id: "second-step" }, card("NVIDIA Nemotron Ultra, a second reader that can only object",
    "Does a second reader catch what the first one missed?", el("p", { class: "small" }, "Loading the logged run…"))));


  // What we measured: the pre-registered evidence behind each step
  steps.append(el("li", { class: "small how-divider" }, el("h2", {}, "What we measured")));
  // 3b. The guard under attack (filled in by loadRedTeam)
  steps.append(el("li", { id: "redteam-step" }, card("NVIDIA Nemotron, attacking the guard",
    "Nemotron tries to make the guard accept a wrong count", el("p", { class: "small" }, "Loading the logged chain…"))));

  // 3b1. The thinking budget: the Nemotron result itself (baseline-m0-results.md, second-labeller-results.md)
  steps.append(el("li", {}, card("NVIDIA Nemotron, the thinking budget", "Super's thinking budget changes the answer",
    el("table", { class: "how-table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Super VL alone through Nightshift (no quote check), 25 queued records"), el("th", {}, "Thinking off"), el("th", {}, "4k budget"))),
      el("tbody", {},
        el("tr", {}, el("td", {}, "Right field, the builder's blind labels"), el("td", {}, "9"), el("td", {}, "17")),
        el("tr", {}, el("td", {}, "Right field, an independent second labeller (kappa 0.82)"), el("td", {}, "12"), el("td", {}, "19")))),
    el("p", { class: "small" }, "Every answer's signed Nightshift receipt names Super and shows it was not cached; in the product, the quote check then decides what is kept. The chain spends the budget only on fields that stay open: on 30 consistent records, half the completion tokens of always reading at 4k. Pre-registered: docs/evidence/baseline-m0-results.md, second-labeller-results.md, shipped-cost-results.md."))));

  steps.append(el("li", { id: "flip-step" }, card("NVIDIA Nemotron, the thinking budget on one record",
    "The same report, thinking off and at 4k", el("p", { class: "small" }, "Loading the logged answers…"))));

  // 3b2. Each Nemotron's seat and the pre-registered result that earned it (README "Nemotron, model per step")
  const SEATS = [
    ["First read", "Nemotron Lightning, thinking off · Nightshift", "settled 18 of 28 records vs Super's 15; 0 of 38 closings contradicted, 5 unconfirmed (not faster: claim removed)"],
    ["Deep read", "Nemotron Super VL, 4k thinking budget · Nightshift", "32 correct / 3 wrong vs Ultra 32 / 4 and Lightning 24 / 3 on the blind labels"],
    ["Scan read", "Nemotron Parse v1 (NVIDIA direct) + Super VL", "Parse v1 6 of 12 vs Parse 2.0 1 of 12 in the pipeline (2.0 returned empty pages)"],
    ["Second reader", "Nemotron Ultra, objection only · Nightshift", "3 objections, all agreeing with the blind labels, 0 against; planted errors 4 of 5; on the census hits it objected to 2 of 12 fallen field readings (it shares the reader's traps)"],
    ["Local first read (--local)", "Nemotron Lightning on this PC · Nightshift Jobs API, local-only", "20 of 20 local, 0 disagreements with the cloud; after the Nightshift 2026-10-26 release, 20 of 20 on whole reports (none cut), 0 disagreements; what stays open goes to the cloud deep read"],
    ["Case note", "Nemotron Super VL, thinking on · Nightshift", "21 of 25 notes pass the note check vs Ultra 8 of 25"],
    ["Red team", "Nemotron Super VL on the Meterless Markovian engine", "0 wrong accepts in 57 judged attacks on the quote check"],
    ["Edge first read (measured, not shipped)", "Nemotron 3.5 Bolt, thinking off · NVIDIA direct", "16 of 30 settled vs Lightning's 17, 0 of 34 contradicted, fewer tokens; now reachable through Nightshift (2026-10-26 release), Lightning keeps the seat by settling more"],
    ["Scan witness (measured)", "Nemotron 3 Nano Omni vs Super VL · NVIDIA direct", "11 correct / 2 wrong vs 11 / 3 on 13 scans; no token saving, so no seat"],
    ["Screening report text (measured, no job)", "Nemotron 3.5 Content Safety · NVIDIA direct", "flagged 23 of 70 planted instructions and 20 of 100 clean reports"],
  ];
  steps.append(el("li", {}, card("NVIDIA Nemotron, one model per job", "Which Nemotron does what, and why that one",
    el("table", { class: "how-table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Job"), el("th", {}, "Model"), el("th", {}, "Why (pre-registered)"))),
      el("tbody", {}, ...SEATS.map(([job, model, why]) => el("tr", {}, el("td", {}, job), el("td", {}, model), el("td", {}, why))))),
    el("p", { class: "small" }, "Every comparison was written down with its pass line before its first call (deviations disclosed), and the losses are published: docs/evidence/lightning-r1-results.md, r1-timing-results.md, reader-bench-results.md, parse-bench-results.md, ultra-critic-results.md, ultra-notes-results.md, adversary-chain-v3-results.md, bolt-r1-results.md, scan-witness-results.md, safety-screen-results.md, local-mode-results.md. As shipped, the small-model-first chain used 50% fewer completion tokens than always reading at 4k on 30 records whose fields agree; of 36 closings 33 agreed, 0 contradicted, 3 unconfirmed (shipped-cost-results.md)."))));

  steps.append(el("li", { id: "ledger-step" }, card("NVIDIA Nemotron, the routing ledger",
    "Which model did the work", el("p", { class: "small" }, "Loading the ledger…"))));

  // 3c. Nemotron as an agent reading the layer (filled in by loadAgentProbe)
  steps.append(el("li", { id: "agent-step", class: "alert" }, card("NVIDIA Nemotron, as an agent reading the layer",
    "Does an agent that reads the semantic layer use the verdict?", el("p", { class: "small" }, "Loading the logged probes…"))));

  // 3d. The second reader (filled in by loadSecondReaderCard)
  steps.append(el("li", { id: "labels-step" }, card("You, blind", "Against the blind labels", el("p", { class: "small" }, "Loading the scores…"))));
  steps.append(el("li", { id: "attest-step" }, card("Nightshift receipts, checked in this page's server",
    "Can anyone check that the stored values came from Nemotron?", el("p", { class: "small" }, "Checking the signatures…"))));

}

const VERDICT = {
  count_not_in_quote: "rejected: the number is not the positive count in its quote",
  count_below_report: "rejected: below a node fraction the report states",
  count_not_report_total: "rejected: not the total the report states",
  quote_not_in_report: "rejected: quote not in the report",
  quote_too_short: "rejected: quote too short",
  true_count: "sent the true count (not an attack)",
  call_failed: "the call failed (not judged)",
};

async function loadRedTeam() {
  const box = $("redteam-step");
  if (!box) return;
  let chains = [];
  try { chains = (await api("/api/redteam")).chains; } catch (error) { /* shown below */ }
  const c = chains[0];
  const body = [];
  if (!c) body.push(el("p", { class: "small" }, "No red-team run logged."));
  else {
    const judged = c.steps.filter((s) => s.verdict !== "call_failed").length;
    const total = chains.reduce((n, x) => n + x.steps.filter((s) => s.verdict !== "call_failed").length, 0);
    const wrong = chains.reduce((n, x) => n + (x.accepts_wrong || 0), 0);
    body.push(el("p", {}, `A pre-registered chain on ${c.case} (the report says ${c.true_count} positive nodes). Each step Super, thinking budget ${c.thinking_budget}, through Nightshift, proposes a wrong count and a quote it hopes passes; the real guard judges it, and our code writes the verdict into the ledger the next step sees.`),
      flow([`${c.accepts_wrong} wrong accepted of ${judged} judged on this case`, c.accepts_wrong ? "bad" : "good"], [`${wrong} of ${total} over all ${chains.length} chains`, wrong ? "bad" : "good"]),
      el("table", { class: "how-table" },
        el("thead", {}, el("tr", {}, ...["Step", "Attack", "Its quote", "Guard", "Receipt"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...c.steps.map((s) => el("tr", {},
          el("td", {}, show(s.step)),
          el("td", {}, `${show(s.value)} nodes${s.repeat ? " (repeat)" : ""}`),
          el("td", { class: "how-quote" }, s.quote ? `“${s.quote}”` : "—"),
          el("td", {}, VERDICT[s.verdict] || show(s.verdict)),
          el("td", {}, show(s.signature)))))),
      el("p", { class: "small" }, `Ledger instead of transcript: ${show(c.tokens_saved_est)} estimated prompt tokens saved on this chain (engine estimator, history against ledger); the engine's own totalTokensSaved reports ${show(c.engine_tokens_saved)}. ${show(c.repeats)} of ${c.steps.length} steps repeated an earlier attack despite the ledger. Logged run ${c.run_id}, not replayed live.`));
  }
  box.replaceChildren(card("NVIDIA Nemotron, attacking the guard", "Nemotron tries to make the guard accept a wrong count", ...body));
}

function sqlBlock(q, label) {
  if (!q) return el("p", { class: "small" }, "No logged query.");
  return el("div", { class: "how-sqlwrap" },
    el("div", { class: "small" }, `${label} · returned `, el("b", {}, show(q.result)), ` · ${show(q.seconds)} s · Nightshift receipt ${show(q.receipt_id)} (${show(q.signature)})`),
    el("pre", { class: "how-sql" }, q.sql || ""));
}

async function loadBudgetFlip() {
  const box = $("flip-step");
  if (!box) return;
  let f = null;
  try { f = (await api("/api/budget-flip")).flip; } catch (error) { /* shown below */ }
  const who = "NVIDIA Nemotron, the thinking budget on one record", title = "The same report, thinking off and at 4k";
  if (!f) { box.replaceChildren(card(who, title, el("p", { class: "small" }, "No logged baseline run found."))); return; }
  const NAME = { node_count: "the count field", pathologic_n: "the stage field", review: "a person decides" };
  const row = (label, a, cls) => el("tr", {}, el("td", {}, label), el("td", { class: cls }, NAME[a.fault] || String(a.fault)),
    el("td", {}, a.quote ? `“${a.quote}”` : "—"), el("td", {}, String(a.completion_tokens ?? "—")), el("td", {}, String(a.signature ?? "—")));
  box.replaceChildren(card(who, title,
    el("p", {}, `${f.case}, Super VL alone through Nightshift (no quote check), the pre-registered baseline run. Both blind labellers say the report contradicts the count field.`),
    el("table", { class: "how-table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Thinking"), el("th", {}, "Field Super names"), el("th", {}, "Its quote"), el("th", {}, "Completion tokens"), el("th", {}, "Receipt"))),
      el("tbody", {}, row("off", f.off, "bad"), row("4k budget", f.budget_4k, ""))),
    el("p", { class: "small" }, `Logged run ${f.run}, not replayed. The chain spends the 4k budget only where a field stays open; on this record the first read leaves both fields open, so the deep read runs. docs/evidence/baseline-m0-results.md.`)));
}

async function loadAgentProbe() {
  const box = $("agent-step");
  if (!box) return;
  let p = null;
  try { p = (await api("/api/agent-probe")).probe; } catch (error) { /* shown below */ }
  const title = "Does an agent that reads the semantic layer use the verdict?";
  if (!p) { box.replaceChildren(card("NVIDIA Nemotron, as an agent reading the layer", title, el("p", { class: "small" }, "No agent probe logged."))); return; }
  const ids = (list) => list.map((c) => c.case_id).join(", ");
  const e2 = p.missed.find((c) => c.case_id === "TCGA-E2-A572");
  box.replaceChildren(card("NVIDIA Nemotron, as an agent reading the layer", title,
    el("p", {}, `Three pre-registered probes. Super, through Nightshift, saw only the layer's table and column descriptions and the question “${p.question}”, and wrote one SQL query in 29 of 30 calls; each ran unchanged on the live layer unless our read guard refused it.`),
    flow([`${p.read_raw_count} of ${p.queries_written} queries read the raw count column`, "bad"], [`the pointer to the verdict was used ${p.pointer_used} times`, "bad"], [`the checked column was read ${p.read_checked} time`, ""]),
    sqlBlock(p.raw_query, "Probe 1, with the pointer in the descriptions"),
    el("p", {}, `Left out of that answer: ${p.missed.length} patients whose report shows positive nodes while the count column records 0 (${ids(p.missed)})`,
      e2 ? `; TCGA-E2-A572's report says “Positive 8 / 13”.` : "."),
    sqlBlock(p.checked_query, "Probe 2, with the checked count beside the raw one"),
    el("p", {}, `This one query read the checked column and included those ${p.missed.length} patients, then filled the ${p.person.length} cases the verdict leaves to a person (${ids(p.person)}) back in from the raw count.`),
    ...(p.probe3 ? [el("p", {}, `Probe 3 handed the agent the layer's own data-quality rules, rendered into the schema exactly as LOAD USL returns them. It changed nothing: ${p.probe3.treatment.raw} of ${p.probe3.treatment.calls} calls with the rules and ${p.probe3.control.raw} of ${p.probe3.control.calls} without counted the raw column (476); ${p.probe3.treatment.correct} used the verdict.`)] : []),
    ...(p.probe4 ? [
      el("p", {}, `Probe 4 asked two new questions. Asked which patients the report shows node-positive while the registry records 0, the agent returned exactly those ${p.missed.length} from the layer in ${p.probe4.exact_six} of ${p.probe4.ids_calls} calls. Told to “correct the record” for TCGA-E2-A572, it wrote an overwrite of the registry in ${p.probe4.fix_calls} of ${p.probe4.fix_calls} calls; our read guard refused all ${p.probe4.refused}, so nothing changed. The product never edits a record: a person's decision is a new row.`),
      sqlBlock(p.probe4.refused_query, `Probe 4, refused: ${show(p.probe4.refused_query && p.probe4.refused_query.guard)}`)] : []),
    ...(p.probe5 ? [
      el("p", {}, `Probe 5 changed the layer instead of the prompt: the agent got its own Zetaris account that can read only a copy of the checked values, and Zetaris refuses it the audit tables. Same question: ${p.probe5.agent_correct} of ${p.probe5.agent_calls} calls returned 479; the admin control returned 476 in ${p.probe5.control_raw} of ${p.probe5.control_calls}. Right by construction: the account reads a separate table of checked values (a view over the live tables would still need the raw columns; that grant was not tested).`),
      sqlBlock(p.probe5.agent_query, "Probe 5, the agent's own account")] : []),
    el("p", { class: "small" }, "A pointer in the description was not enough, a checked column beside the raw one was not either, and neither were the layer's own rules. So the verdict is for the people and tools that read stage_check and the case page; a person decides. Logged runs, not replayed live: docs/evidence/agent-probe-results.md, agent-probe-2-results.md, agent-probe-3-results.md, agent-probe-4-results.md, agent-probe-5-results.md.")));
}

async function loadSecondReaderCard() {
  const box = $("second-step");
  if (!box) return;
  let s = null;
  try { s = (await api("/api/second-reader")).summary; } catch (error) { /* shown below */ }
  const title = "Does a second reader catch what the first one missed?";
  if (!s) { box.replaceChildren(card("NVIDIA Nemotron Ultra, a second reader that can only object", title, el("p", { class: "small" }, "No second-reader run logged."))); return; }
  box.replaceChildren(card("NVIDIA Nemotron Ultra, a second reader that can only object", title,
    el("p", {}, `Ultra, through Nightshift, re-read the report behind each of the ${s.values} stored values and could agree or object with one verbatim quote; our guard checked every objection. Pre-registered, with 5 planted wrong values as a control, and scored against blind human labels.`),
    flow([`${s.objections} objections, ${s.right} agree with the blind labels, ${s.wrong} wrong`, s.wrong ? "bad" : "good"], [`planted errors caught: ${s.plants.detected} of ${s.plants.planted}`, "good"], [`${s.missed} missed`, ""]),
    ...(s.objection_list || []).map((o) => el("p", { class: "small" }, `${o.case}: ${o.field === "NPOS" ? "count" : "N"} stored ${show(o.stored)}, Ultra: ${show(o.objection)}`)),
    el("p", { class: "small" }, "An objection only sends the case to a person; it never changes a value. Logged run, not replayed live: docs/evidence/ultra-critic-results.md (v1 did not ship because of a scope bug of ours; v2 fixed only that).")));
}

async function loadLabelsCard() {
  const box = $("labels-step");
  if (!box) return;
  let s = null;
  try { s = (await api("/api/labels")).labels; } catch (error) { /* shown below */ }
  const title = "Against the blind labels";
  if (!s) { box.replaceChildren(card("You, blind", title, el("p", { class: "small" }, "No label scores logged."))); return; }
  const rb = s.reader_bench;
  box.replaceChildren(card("You, blind", title,
    el("p", {}, `A person labelled ${s.of} review-queue records from the reports alone, without seeing any system verdict; the labels were frozen before scoring (sha16 ${s.labels_sha16}).`),
    flow([`the product agreed on ${s.product} of ${s.of}`, "good"], [`Nemotron Super alone, thinking on: ${s.super_4k}`, ""], [`thinking off: ${s.super_off}`, ""], [`the rule alone: ${s.rule}`, ""]),
    el("p", {}, "Level with Super on accuracy, within one case. What the product adds is the checked quote, the signed receipt, the audit trail and a person for what it cannot settle."),
    el("p", { class: "small" }, `The deep-read seat, scored the same way (correct / wrong accepts): Super ${rb.super.correct}/${rb.super.wrong}, Ultra ${rb.ultra.correct}/${rb.ultra.wrong}, Lightning ${rb.lightning.correct}/${rb.lightning.wrong}. Super keeps the seat.`),
    el("p", { class: "small" }, `Sensitivity: the labeller later confirmed 3 labels as mis-clicks (disclosed); with them corrected the product agrees on ${s.sensitivity.product}, Super alone on ${s.sensitivity.super_4k}. The frozen scores stand. docs/evidence/baseline-m0-results.md, reader-bench-results.md.`)));
}

async function loadAttestCard() {
  const box = $("attest-step");
  if (!box) return;
  let s = null;
  try { s = (await api("/api/attest")).attest; } catch (error) { /* shown below */ }
  const who = "Nightshift receipts, checked in this page's server";
  const title = "Can anyone check that the stored values came from Nemotron?";
  if (!s) { box.replaceChildren(card(who, title, el("p", { class: "small" }, "No attestation logged."))); return; }
  const x = s.example;
  box.replaceChildren(card(who, title,
    el("p", {}, `Every stored report value (${s.values}: ${s.fields.N || 0} N and ${s.fields.NPOS || 0} counts on ${s.cases} cases) was re-read once by the shipped steps through Nightshift, and every call's signed envelope was kept. Pre-registered; the originals stay as first written.`),
    flow([`${s.outcomes.reproduced || 0} of ${s.values} reproduced`, s.outcomes.reproduced === s.values ? "good" : ""],
      [`${s.receipts_verified} of ${s.receipts} signatures verified just now, offline, against key ${show(s.fingerprint)}`, s.passed ? "good" : "bad"],
      [s.passed ? "PASS" : `FAIL (${s.failures})`, s.passed ? "good" : "bad"]),
    el("p", { class: "small" }, `${x.case} ${x.field === "NPOS" ? "count" : "N"}: stored ${show(x.stored_value)}, re-read ${show(x.signed_value)} from “${show(x.signed_quote)}” · receipt ${show(x.receipt_id)}`),
    el("p", { class: "small" }, "Run it yourself: python -m app.verify (no key, no network; one changed byte fails it), or open /receipts, where your browser checks each signature. " + s.not_established)));
}

async function loadLedger() {
  const box = $("ledger-step");
  if (!box) return;
  let L = null;
  try { L = (await api("/api/route-ledger")).ledger; } catch (error) { /* shown below */ }
  const who = "NVIDIA Nemotron, the routing ledger", title = "Which model did the work";
  if (!L) { box.replaceChildren(card(who, title, el("p", { class: "small" }, "No ledger generated."))); return; }
  const fmt = (o) => Object.entries(o || {}).map(([k, v]) => `${k} ${Number(v).toLocaleString("en")}`).join(", ");
  const S = L.shipped;
  box.replaceChildren(card(who, title,
    ...(S ? [el("p", {}, `As shipped (the cost test's ${S.records} records): ${S.settled_by_first_read} settled by the first read alone (Nemotron Lightning, thinking off); the rest went on to Super. Completion tokens per seat: ${fmt(S.tokens_per_seat)}.`)] : []),
    el("p", {}, `The 25 hard queue cases (latest runs, 2026-10-23, when the first read was still Super): completion tokens per seat: ${fmt(L.tokens_per_seat)}; the second reader re-read ${L.second_reader_values} stored values and objected ${L.second_reader_objections} times.`),
    el("p", { class: "small" }, "Every step's receipt id is in docs/evidence/route-ledger.md (scripts/route_ledger.py, from committed logs; no model call).")));
}

async function load(caseId, sample) {
  const [data, found] = await Promise.all([api(`/api/case/${caseId}`), api(`/api/case/${caseId}/trace`)]);
  $("open-case").href = `/?case=${caseId}`;
  history.replaceState(null, "", `?case=${caseId}`);
  render(data, found.trace, sample);
  loadRedTeam();
  loadAgentProbe();
  loadBudgetFlip();
  loadSecondReaderCard();
  loadLabelsCard();
  loadAttestCard();
  loadLedger();
}

async function loadScoreboard(sample) {
  try {
    const c = await api("/api/cohort");
    const np = c.node_positive;
    if (!np) return;
    // sample mode shows a dated copy of the live run, never a live answer
    const copy = sample && c.node_positive_snapshot_of ? `Copy of the live layer (${c.node_positive_snapshot_of}). ` : "";
    if (sample && !copy) return;
    $("scoreboard").replaceChildren(el("b", {}, `${copy}How many patients are node-positive? `),
      `${np.node_positive_by_n_column} by the N column, ${np.node_positive_by_count_column} by the count column, ${np.node_positive_by_verdict} by the verdict (${np.left_to_a_person} left to a person). The two columns disagree on ${np.columns_disagree} of ${np.records} records; the steps below show how one record is settled.${Number(np.decided_by_a_person || 0) ? ` With ${np.decided_by_a_person} decided by a person: ${np.node_positive_after_decisions} node-positive, ${np.left_after_decisions} left.` : ""}`);
    $("scoreboard").classList.remove("hidden");
  } catch (error) { /* the steps still load */ }
}

async function start() {
  try {
    const mode = await api("/api/mode");
    const sample = mode.mode === "sample";
    loadScoreboard(sample);
    $("mode").textContent = sample ? "SAMPLE MODE" : "LIVE · Zetaris USL";
    $("mode").classList.toggle("live", !sample);
    const queue = await api("/api/queue");
    const select = $("how-case");
    for (const q of queue) select.append(el("option", { value: q.case_id }, `${q.case_id} · ${q.fault_field || "not read"}`));
    const wanted = new URLSearchParams(location.search).get("case");
    const first = queue.find((q) => q.case_id === wanted) || queue.find((q) => q.fault_field === "node_count") || queue[0];
    if (!first) { $("steps").replaceChildren(el("li", { class: "small" }, "The queue is empty.")); return; }
    select.value = first.case_id;
    select.addEventListener("change", () => load(select.value, sample));
    await load(first.case_id, sample);
  } catch (error) {
    $("steps").replaceChildren(el("li", { class: "small" }, `Could not load: ${error.message}`));
  }
}

start();
