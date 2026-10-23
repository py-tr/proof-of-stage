// How it works: one record, five numbered steps, every value read live from the same API
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

async function load(caseId, sample) {
  const [data, found] = await Promise.all([api(`/api/case/${caseId}`), api(`/api/case/${caseId}/trace`)]);
  $("open-case").href = `/?case=${caseId}`;
  history.replaceState(null, "", `?case=${caseId}`);
  render(data, found.trace, sample);
}

async function start() {
  try {
    const mode = await api("/api/mode");
    const sample = mode.mode === "sample";
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
