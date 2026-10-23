// How it works: one record, seven numbered steps, every value read live from the same API
// the case page uses. Plain JS; every text is a text node.
"use strict";

const $ = (id) => document.getElementById(id);
const show = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
const num = (v) => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? null : Number(v));
const RUNG = { R1: "fast read", R2: "deep read", R3: "the scan" };
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
  if (c.fault_field === "node_count") return "The node-count field is wrong";
  if (c.fault_field === "pathologic_n") return c.reason_class === "n_missing_derivable" ? "The N field should be filled in" : "The N field is wrong";
  if (c.fault_field === "review") return "A person decides: the evidence does not settle it";
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
    "Nemotron reads the pathology report, cheapest reasoning first",
    sample ? el("p", { class: "small" }, "Sample mode: no model run is shown, and none is replayed.")
      : rungs.length ? flow(...rungs.map((r) => {
          const n = r.fields.N || {}, k = r.fields.NPOS || {};
          const both = n.status === "accepted" && k.status === "accepted";
          return [`${RUNG[r.rung] || r.rung} · thinking ${r.thinking} · ${show(r.seconds)} s · ${both ? `${n.value}, ${k.value}` : "rejected or open"}`, both ? "good" : "bad"];
        }))
      : el("p", { class: "small" }, "No ladder run logged for this case yet."),
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

  // 3b. The guard under attack (filled in by loadRedTeam)
  steps.append(el("li", { id: "redteam-step" }, card("NVIDIA Nemotron, attacking the guard",
    "Nemotron tries to make the guard accept a wrong count", el("p", { class: "small" }, "Loading the logged chain…"))));

  // 3c. Nemotron as an agent reading the layer (filled in by loadAgentProbe)
  steps.append(el("li", { id: "agent-step", class: "alert" }, card("NVIDIA Nemotron, as an agent reading the layer",
    "Does an agent that reads the semantic layer use the verdict?", el("p", { class: "small" }, "Loading the logged probes…"))));

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
    el("p", {}, `Two pre-registered probes. Super, through Nightshift, saw only the layer's table and column descriptions and the question “${p.question}”, and wrote one SQL query each time; the query ran unchanged on the live layer.`),
    flow([`${p.read_raw_count} of ${p.queries_written} queries read the raw count column`, "bad"], [`the pointer to the verdict was used ${p.pointer_used} times`, "bad"], [`the checked column was read ${p.read_checked} time`, ""]),
    sqlBlock(p.raw_query, "Probe 1, with the pointer in the descriptions"),
    el("p", {}, `Left out of that answer: ${p.missed.length} patients whose report shows positive nodes while the count column records 0 (${ids(p.missed)})`,
      e2 ? `; TCGA-E2-A572's report says “Positive 8 / 13”.` : "."),
    sqlBlock(p.checked_query, "Probe 2, with the checked count beside the raw one"),
    el("p", {}, `This one query read the checked column and included those ${p.missed.length} patients, then filled the ${p.person.length} cases the verdict leaves to a person (${ids(p.person)}) back in from the raw count.`),
    el("p", { class: "small" }, "A pointer in the description was not enough, and a checked column beside the raw one was not either. So the verdict is for the people and tools that read stage_check and the case page; a person decides. Logged runs, not replayed live: docs/evidence/agent-probe-results.md, agent-probe-2-results.md.")));
}

async function load(caseId, sample) {
  const [data, found] = await Promise.all([api(`/api/case/${caseId}`), api(`/api/case/${caseId}/trace`)]);
  $("open-case").href = `/?case=${caseId}`;
  history.replaceState(null, "", `?case=${caseId}`);
  render(data, found.trace, sample);
  loadRedTeam();
  loadAgentProbe();
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
