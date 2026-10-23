// Proof of Stage: one case at a time. Plain JS, no framework; every text is a text node.
"use strict";

const state = { mode: null, reader: "", queue: [], index: -1, current: null, saving: false, known: {} };
const $ = (id) => document.getElementById(id);
const FIELD_CLASS = { T: "t", N: "n", NPOS: "c" };
const FIELD_NAME = { T: "T", N: "N", NPOS: "Positive nodes" };
const GUARD_WHY = {
  quote_not_in_report: "its quote is not in the report word for word",
  count_not_in_quote: "the sentence is in the report, but it does not contain that number as the positive count",
  count_not_report_total: "the report states a different total positive-node count",
  count_below_report: "the report states more positive nodes elsewhere (a fraction), so this is one specimen, not the total",
  quote_too_short: "its quote is too short to prove anything",
  quote_does_not_support: "the quote is in the report, but it does not show that category (no matching stage, node count or size in it)",
  invalid_category: "not a valid category",
  invalid_count: "not a valid count",
  answer_not_json: "the answer was not readable",
  model_abstained: "Nemotron returned no value (it abstained)",
};
const why = (code) => (Object.hasOwn(GUARD_WHY, code) ? GUARD_WHY[code] : code);
const NAMED = (f) => f === "node_count" || f === "pathologic_n";

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function status(text) { $("status").textContent = text; }

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function num(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function show(value) { return value === null || value === undefined || value === "" ? "—" : String(value); }

// ---------- cohort ----------
async function loadCohort() {
  try {
    const c = await api("/api/cohort");
    const sum = (pred) => c.groups.filter(pred).reduce((a, g) => a + g.n, 0);
    const unread = state.queue.filter((q) => q.read === false).length;
    const total = sum(() => true);
    const contra = sum((g) => g.reason_class === "n_count_contradiction");
    const named = sum((g) => g.reason_class === "n_count_contradiction" && NAMED(g.fault_field));
    const missing = sum((g) => g.reason_class === "n_missing_derivable");
    const box = $("cohort");
    box.replaceChildren(
      c.sample ? el("b", {}, `Sample: ${total} bundled cases. `) : el("span", {}, el("b", {}, `${total}`), ` TCGA-BRCA cases, ${c.reports} reports · `),
      el("b", {}, `${contra}`), " where the recorded N and the node count cannot both be true",
      c.sample ? "" : el("span", {}, " · the report names the field in ", el("b", {}, `${named}`)),
      missing ? ` · ${missing} missing N the count could fill` : "",
      unread ? ` · ${unread} not read yet` : "",
      " · research data, not for clinical use");
  } catch (error) {
    $("cohort").textContent = `Cohort counts unavailable: ${error.message}`;
  }
}

// ---------- queue ----------
function rowLabel(item) {
  const vs = `${show(item.recorded_n)} vs ${show(num(item.lymph_nodes_positive))}`;
  if (item.fault_field === "node_count") return `Count field · ${vs}`;
  if (item.fault_field === "pathologic_n") return item.reason_class === "n_missing_derivable" ? `N missing · ${vs}` : `N field · ${vs}`;
  if (item.read === false) return `Not read yet · ${vs}`;
  if (item.fault_field === "review") return `Needs a person · ${vs}`;
  return `Contradiction · ${vs}`;
}

function renderQueue() {
  const lanes = { named: $("queue-named"), review: $("queue-review"), unread: $("queue-unread"), done: $("queue-done") };
  Object.values(lanes).forEach((lane) => lane.replaceChildren());
  state.queue.forEach((item, position) => {
    const lane = item.decided_at ? "done" : NAMED(item.fault_field) ? "named" : item.read === false ? "unread" : "review";
    const classes = ["row", lane === "review" || lane === "unread" ? "review" : "", lane === "done" ? "done" : "", position === state.index ? "active" : ""].join(" ");
    const row = el("div", { class: classes },
      el("div", { class: "id" }, item.case_id),
      el("div", { class: "what" }, rowLabel(item)),
      item.decided_at ? el("div", { class: "when" }, `decided ${item.decided_at} UTC`) : null);
    row.addEventListener("click", () => openCase(position));
    lanes[lane].append(row);
  });
  if (!lanes.named.children.length) lanes.named.append(el("p", { class: "small" }, state.mode === "sample" ? "Sample mode has no reader output: open a case and play the reader." : "No field named yet."));
  if (!lanes.done.children.length) lanes.done.append(el("p", { class: "small" }, "None yet."));
  if (!lanes.unread.children.length) lanes.unread.append(el("p", { class: "small" }, "None."));
}

// ---------- report with highlighted spans ----------
function emphasiseFractions(mark, text) {
  // In a long span, make the positive-count fraction stand out ("2/18", "1 of 16").
  const pattern = /(\d+\s*(?:\/|of|out of)\s*\d+)/gi;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    mark.append(text.slice(last, match.index), el("strong", {}, match[0]));
    last = match.index + match[0].length;
  }
  mark.append(text.slice(last));
}

function renderReport(text, spans) {
  const pre = $("report-text");
  pre.replaceChildren();
  if (!text) {
    pre.append("There is no public report for this case, so there is nothing to highlight and the contradiction stays unresolved.");
    return;
  }
  const cuts = new Set([0, text.length]);
  for (const s of spans) { cuts.add(s.start); cuts.add(s.end); }
  const points = [...cuts].filter((p) => p >= 0 && p <= text.length).sort((a, b) => a - b);
  let first = null;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const piece = text.slice(a, b);
    const covering = spans.filter((s) => s.start <= a && s.end >= b);
    if (!covering.length) { pre.append(piece); continue; }
    const mark = el("mark", { class: covering[covering.length - 1].cls, title: covering.map((s) => s.label).join(", ") });
    emphasiseFractions(mark, piece);
    pre.append(mark);
    if (!first || covering.some((s) => s.cls === "x")) first = mark;
  }
  if (first) first.scrollIntoView({ block: "center", behavior: "smooth" });
}

function acceptedSpans(accepted) {
  return accepted
    .filter((x) => FIELD_CLASS[x.field] && x.quote_start != null)
    .map((x) => ({ start: Number(x.quote_start), end: Number(x.quote_end), cls: FIELD_CLASS[x.field], label: `${x.field} quote` }));
}

// ---------- the USL strip ----------
function step(table, value, note, extra = "") {
  return el("div", { class: `step ${extra}` }, el("span", { class: "t" }, table), el("span", { class: "v" }, value), note ? el("div", {}, note) : null);
}

function renderStrip(data) {
  const c = data.check;
  const strip = $("strip");
  strip.replaceChildren();
  const rule = data.rules.registry_count[0];
  const reportBits = state.mode === "sample" ? "no reader output in sample mode"
    : [c.report_n ? `N ${c.report_n}` : null, num(c.report_nodes_positive) != null ? `count ${num(c.report_nodes_positive)}` : null].filter(Boolean).join(", ") || "no verified value";
  const verdict = c.fault_field || (state.mode === "sample" ? "(play the reader)" : "—");
  strip.append(
    step("recorded_stage", `${show(c.recorded_n)} · count ${show(num(c.lymph_nodes_positive))}`, `edition ${show(c.edition_code)}`),
    step("staging_rule", rule ? `${rule.rule_id} → ${rule.output}` : "no rule", rule && rule.min_value ? `${rule.min_value}${rule.max_value ? "–" + rule.max_value : "+"} positive` : (rule ? "nodes not examined" : "")),
    step("derived_stage", reportBits, state.mode === "sample" ? "" : "method nemotron_reader"),
    step("stage_check.fault_field", verdict, NAMED(c.fault_field) ? "named by the USL" : c.fault_field === "review" ? "a person decides" : "", NAMED(c.fault_field) ? "verdict" : "verdict review"));
  const failed = data.lineage.failed.map((f) => f.rule);
  const foot = el("div", { class: "strip-foot" }, "Data-quality rules failed: ",
    failed.length ? failed.map((r, i) => el("span", {}, i ? ", " : "", el("code", {}, r))) : "none",
    ` · evaluated by ${data.lineage.evaluated_by}`,
    data.lineage.mirror_disagrees ? " · note: the Python mirror disagrees with Zetaris on this case" : "");
  const details = el("details", {}, el("summary", {}, `rule text and where each USL table comes from (${data.lineage.sources_from})`));
  for (const f of data.lineage.failed) details.append(el("div", {}, el("code", {}, `${f.rule}: ${f.expression}`)));
  const list = el("ul");
  for (const s of data.lineage.sources) list.append(el("li", {}, el("code", {}, s.usl_table), ` ← ${s.source} (${s.kind})`));
  details.append(list);
  foot.append(details);
  strip.append(foot);
}

// ---------- the evidence panel ----------
// The band's title: which field the evidence names, in plain words.
function verdictTitle(c) {
  if (state.mode === "sample" && !c.fault_field) return ["Play the reader", "review"];
  if (c.fault_field === "node_count") return ["The node-count field is wrong", "named"];
  if (c.fault_field === "pathologic_n") {
    return [c.reason_class === "n_missing_derivable" ? "The N field should be filled in" : "The N field is wrong", "named"];
  }
  if (c.fault_field === "review" && c.read === false) return ["Not read yet", "review"];
  if (c.fault_field === "review") return ["A person decides: the evidence does not settle it", "review"];
  return ["The registry fields agree", "agree"];
}

function renderPanel(data) {
  const c = data.check;
  $("headline").textContent = data.headline;
  const [title, kind] = verdictTitle(c);
  $("verdict-title").textContent = title;
  $("verdict-band").className = `verdict-band ${kind === "named" ? "" : kind}`;
  $("report-title").textContent = `Pathology report · ${c.case_id} · edition ${show(c.edition_code)}`;
  renderStrip(data);
  const sample = state.mode === "sample";
  $("c-rec-n").textContent = show(c.recorded_n);
  $("c-der-n").textContent = show(c.derived_n);
  $("c-rep-n").textContent = sample ? "you play the reader ↓" : show(c.report_n);
  $("c-rec-c").textContent = show(num(c.lymph_nodes_positive));
  $("c-rep-c").textContent = sample ? "you play the reader ↓" : show(num(c.report_nodes_positive));
  for (const id of ["c-rec-n", "c-rec-c"]) $(id).classList.remove("bad");
  for (const id of ["c-rep-n", "c-rep-c"]) $(id).classList.remove("good");
  if (c.fault_field === "node_count") $("c-rec-c").classList.add("bad");
  if (c.fault_field === "pathologic_n") $("c-rec-n").classList.add("bad");
  if (!sample && c.report_n) $("c-rep-n").classList.add("good");
  if (!sample && num(c.report_nodes_positive) != null) $("c-rep-c").classList.add("good");

  const rules = $("rules");
  rules.replaceChildren();
  const ruleLine = (label, list) => {
    for (const r of list) rules.append(el("li", {}, `${label}: `, el("b", {}, r.output), ` — ${r.condition_text} (${r.rule_id}, ed. ${r.edition})`));
  };
  ruleLine(`Registry count ${show(num(c.lymph_nodes_positive))}`, data.rules.registry_count);
  if (num(c.report_nodes_positive) != null) ruleLine(`Report count ${num(c.report_nodes_positive)}`, data.rules.report_count);
  if (!rules.children.length) rules.append(el("li", {}, "No count rule applies."));

  renderNemotron(data);
  renderRejected(data);
  renderDecide(data);
  $("source-note").textContent = sample && state.sourceNote ? state.sourceNote : "";
}

function renderNemotron(data) {
  const box = $("nemotron");
  box.replaceChildren();
  if (state.mode === "sample") {
    box.append(el("p", { class: "small" }, "Sample mode: model reads are off, and no saved model answer is replayed. The rules, the quote guard and the fault logic run live: use “Try to fool it” to play the reader."));
    return;
  }
  const accepted = Object.fromEntries(data.accepted.filter((x) => FIELD_CLASS[x.field]).map((x) => [x.field, x]));
  const reasons = Object.fromEntries(data.extractions.filter((x) => String(x.field).endsWith("_REASON")).map((x) => [x.field.replace("_REASON", ""), x]));
  const flags = data.flags.filter((f) => f.rule_id === "reader_review");
  for (const field of ["N", "NPOS", "T"]) {
    const x = accepted[field];
    if (x) {
      const said = reasons[field];
      box.append(el("div", { class: "line" },
        el("b", {}, `${FIELD_NAME[field]} = ${x.value}`), ` · quote at characters ${x.quote_start}–${x.quote_end}`,
        el("ul", { class: "checks" }, ...x.checks.map((k) => el("li", { class: k.ok ? "" : "no" }, k.check))),
        said ? el("div", { class: "said" }, `Nemotron's own sentence: “${said.value}”`) : null,
        el("div", { class: "small" }, "Model ", el("code", {}, show(x.model)), " · ",
          x.receipt_id ? el("span", {}, "Nightshift receipt ", el("code", {}, x.receipt_id)) : "NVIDIA direct; no Nightshift receipt",
          ` · read ${show(x.created_at)} UTC`)));
    } else {
      const f = flags.filter((g) => g.field === field).pop();
      box.append(el("div", { class: "line" }, el("b", {}, FIELD_NAME[field]), " · ",
        f ? el("span", { class: f.reason === "model_abstained" ? "small" : "fail" }, f.reason === "model_abstained" ? why(f.reason) : `not accepted: ${why(f.reason)}`) : el("span", { class: "small" }, "not read yet")));
    }
  }
  box.append(el("div", { class: "small" }, `Ticks are re-checked now by the same guard code. Reader: ${state.reader}.`));
}

function renderRejected(data) {
  const box = $("rejected");
  box.replaceChildren();
  const rejected = data.flags.filter((f) => f.rule_id === "reader_review" && f.reason !== "model_abstained" && f.quote);
  if (!rejected.length) return;
  box.append(el("h3", {}, "Answers the guard threw away"));
  for (const f of rejected) {
    const head = el("div", {}, el("b", {}, `${FIELD_NAME[f.field] || f.field} = `), f.reason === "count_not_in_quote" ? el("s", {}, show(f.derived_value)) : show(f.derived_value),
      ` · ${show(f.created_at)} UTC · rejected because ${why(f.reason)}`);
    const quote = f.reason === "count_not_in_quote" ? el("span", {}, `“${f.quote}”`) : el("s", {}, `“${f.quote}”`);
    box.append(el("div", { class: "rej" }, head, quote, el("div", { class: "small" }, `Model ${show(f.model)}`)));
  }
}

// ---------- decisions ----------
const CLAIM_TEXT = {
  node_count: "The count field is wrong",
  pathologic_n: "The N field is wrong",
  neither: "Neither: the flag is wrong",
  unsure: "Not sure",
};

function renderDecide(data) {
  const box = $("decide");
  box.replaceChildren();
  const fault = data.check.fault_field;
  const claims = fault === "node_count" ? ["node_count", "neither", "unsure"]
    : fault === "pathologic_n" ? ["pathologic_n", "neither", "unsure"]
    : ["node_count", "pathologic_n", "unsure"];
  claims.forEach((claim, i) => {
    const b = el("button", { class: i === 0 && NAMED(fault) ? "primary" : "", title: `key ${i + 1}` }, `${i + 1} ${CLAIM_TEXT[claim]}`);
    b.addEventListener("click", () => decide(claim));
    box.append(b);
  });
  state.claims = claims;
  const mine = data.flags.filter((f) => f.rule_id === "human_review");
  $("decided").replaceChildren(...mine.map((f) => el("div", {}, `Decision row ${f.flag_id}: ${f.reason}`)));
}

async function decide(claim, reasonCode) {
  if (!state.current || state.saving) return;
  const caseId = state.current.check.case_id;
  if (claim === "neither" && !reasonCode) { $("reject-reasons").classList.remove("hidden"); state.pendingClaim = claim; return; }
  state.saving = true;
  document.querySelectorAll("#decide button, #reject-reasons button").forEach((b) => (b.disabled = true));
  status(`Saving the decision for ${caseId} to Zetaris…`);
  try {
    const saved = await api(`/api/case/${caseId}/decision`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim, reason_code: reasonCode || null }),
    });
    $("reject-reasons").classList.add("hidden");
    if (saved.saved) {
      status(`Appended to Zetaris oa_pg.flag_log: ${saved.flag_id} (${CLAIM_TEXT[claim]})`);
      const item = state.queue[state.index];
      item.decided_at = saved.created_at;
      await refreshQueueKeep(caseId);
    } else {
      status("Sample mode does not write to Zetaris: nothing was saved.");
    }
  } catch (error) {
    status(`NOT saved: ${error.message}. Nothing was written; the case stays open.`);
  } finally {
    state.saving = false;
    document.querySelectorAll("#decide button, #reject-reasons button").forEach((b) => (b.disabled = false));
  }
}

async function refreshQueueKeep(caseId) {
  try { state.queue = await api("/api/queue"); } catch (_error) { /* keep the old list */ }
  const position = state.queue.findIndex((q) => q.case_id === caseId);
  await openCase(position >= 0 ? position : 0, { keepStatus: true });
}

// ---------- try to fool it ----------
// ---------- how it was read (latest ladder run) ----------
const RUNG_NAME = { R1: "R1 fast read", R2: "R2 deep read", R3: "R3 the scan" };

function fieldVerdict(f) {
  if (!f) return "—";
  return f.status === "accepted" ? `${f.value} ✓` : `${f.value ?? "no value"} ✗ ${why(f.reason)}`;
}

function renderTrace(trace) {
  const box = $("trace");
  box.replaceChildren();
  if (!trace) {
    box.append(el("p", { class: "small" }, state.mode === "sample" ? "Sample mode: no model run is shown." : "No ladder run logged for this case yet."));
    return;
  }
  const head = el("tr", {}, ...["Rung", "Thinking", "Provider", "Tokens", "Seconds", "N", "Positive nodes"].map((h) => el("th", {}, h)));
  const rows = trace.rungs.map((r) => el("tr", {},
    el("td", {}, RUNG_NAME[r.rung] || r.rung),
    el("td", {}, r.thinking),
    el("td", {}, r.provider === "nightshift"
      ? el("span", {}, "Nightshift ", el("code", { title: `receipt ${show(r.receipt_id)} · signature ${show(r.signature)} · cached: ${r.from_cache ? "yes" : "no"}` }, `${show(r.signature)} receipt`))
      : "NVIDIA direct"),
    el("td", { class: r.budget.ok === false ? "over" : "", title: r.budget.how }, show(r.completion_tokens), r.budget.ok === false ? " (over budget)" : ""),
    el("td", {}, show(r.seconds)),
    el("td", {}, fieldVerdict(r.fields.N)),
    el("td", {}, fieldVerdict(r.fields.NPOS))));
  box.append(el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows)),
    el("p", { class: "small" }, `Run ${trace.run_id}. Stored values are the first ones written (append-only), so they can come from an earlier run. Hover a receipt for its id, a token count for the budget check.`));
}

async function loadTrace(caseId) {
  try {
    const found = await api(`/api/case/${caseId}/trace`);
    if (state.current && state.current.check.case_id === caseId) renderTrace(found.trace);
  } catch (error) {
    $("trace").textContent = `Could not load the ladder run: ${error.message}`;
  }
}

// ---------- case note (Nightshift) ----------
const NOTE_WHY = {
  answer_not_json: "the answer was not readable",
  sentence_count: "it did not have 1 to 4 sentences",
};
function noteWhy(code) {
  if (Object.hasOwn(NOTE_WHY, code)) return NOTE_WHY[code];
  const m = /^sentence_(\d+)_(.*)$/.exec(code || "");
  if (!m) return code;
  const rest = m[2]
    .replace(/^states_(.+)_not_in_cited_facts$/, "it states $1, which none of its cited facts says")
    .replace(/^cites_unknown_(.+)$/, "it cites $1, which is not a fact")
    .replace("no_citation", "it cites no fact").replace("too_long", "it is too long")
    .replace(/^word_(.+)_not_in_cited_facts$/, "it uses \u201c$1\u201d, a word none of its cited facts has")
    .replace(/^claims_(.+)_not_in_cited_facts$/, "it says “$1”, which none of its cited facts says")
    .replace("fact_id_in_text", "it writes a fact id into the text").replace("malformed", "it is malformed");
  return `sentence ${m[1]}: ${rest}`;
}

function renderNote(note) {
  const box = $("note");
  box.replaceChildren();
  if (!note) {
    box.append(el("p", { class: "small" }, "No note yet for this case."));
    return;
  }
  if (note.status !== "accepted") {
    box.append(el("p", {}, el("span", { class: "fail" }, "Not shown"), `: ${noteWhy(note.reason)}. The guard checks every sentence against the facts it cites.`));
  }
  for (const s of note.sentences) {
    box.append(el("p", {}, s.text, ...s.cites.map((c) => el("span", { class: "cite", title: note.facts[c] || "" }, c))));
  }
  const rc = note.receipt || {};
  box.append(el("div", { class: "receipt" },
    "Model ", el("code", {}, show(rc.model)), " · Nightshift receipt ", el("code", {}, show(rc.receipt_id)),
    ` · Ed25519 signature ${show(rc.signature)} · cached: ${rc.from_cache ? "yes" : "no"} · egress ${show(rc.egress)} · ${show(note.seconds)} s · ${show(note.created_at)}`));
}

async function loadNote(caseId) {
  const live = state.mode === "live";
  $("note-run").classList.toggle("hidden", !live);
  if (!live) {
    $("note").replaceChildren(el("p", { class: "small" }, "Sample mode: the case note needs Nightshift (live mode); no saved note is replayed."));
    return;
  }
  try {
    const found = await api(`/api/case/${caseId}/note`);
    if (state.current && state.current.check.case_id === caseId) renderNote(found.note);
  } catch (error) {
    $("note").textContent = `Could not load the note: ${error.message}`;
  }
}

async function writeNote() {
  if (!state.current) return;
  const caseId = state.current.check.case_id;
  const button = $("note-run");
  button.disabled = true;
  $("note").replaceChildren(el("p", { class: "small" }, "Asking Nemotron Super through Nightshift (thinking off; usually a few seconds)…"));
  try {
    const note = await api(`/api/case/${caseId}/note`, { method: "POST" });
    if (state.current.check.case_id === caseId) renderNote(note);
  } catch (error) {
    $("note").textContent = `No note: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

async function challenge() {
  if (!state.current) return;
  const caseId = state.current.check.case_id;
  const body = { field: $("f-field").value, value: $("f-value").value.trim(), quote: $("f-quote").value, known: state.known };
  const out = $("f-out");
  out.textContent = "Checking…";
  try {
    const verdict = await api(`/api/case/${caseId}/challenge`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    out.replaceChildren();
    if (verdict.status === "accepted") {
      out.append(el("span", { class: "pass" }, `Accepted ${FIELD_NAME[verdict.field]} = ${verdict.value}`),
        verdict.field === "NPOS" ? ": the quote is in the report and its positive count is that number." : ": the quote is in the report word for word and shows that category (a matching stage, a node count that implies it, or a tumour size in its range).");
      if (verdict.used) {
        if (verdict.used.report_n_main) state.known.report_n_main = verdict.used.report_n_main;
        if (verdict.used.report_nodes_positive) state.known.report_nodes_positive = verdict.used.report_nodes_positive;
        const f = verdict.fault_field_if_accepted;
        const text = f === "node_count" ? "the count field" : f === "pathologic_n" ? "the N field" : f === "review" ? "no field yet: a person decides (add the other answer to settle it)" : "nothing (no contradiction here)";
        out.append(el("div", {}, `With your readings so far (N ${show(verdict.used.report_n_main)}, count ${show(verdict.used.report_nodes_positive)}) the USL rule would name: `, el("b", {}, text)));
      }
      const spans = acceptedSpans(state.current.accepted || []);
      spans.push({ start: verdict.span[0], end: verdict.span[1], cls: "x", label: "your quote" });
      renderReport(state.current.report_text, spans);
    } else {
      out.append(el("span", { class: "fail" }, verdict.status === "abstained" ? "No value" : "Rejected"), `: ${why(verdict.reason)}. Nothing is written.`);
    }
  } catch (error) {
    out.textContent = `Error: ${error.message}`;
  }
}

// ---------- open a case ----------
async function openCase(position, options = {}) {
  if (position < 0 || position >= state.queue.length) return;
  state.index = position;
  state.known = {};
  renderQueue();
  const caseId = state.queue[position].case_id;
  if (!options.keepStatus) status(`Waiting for ${state.mode === "sample" ? "the bundled sample" : "Zetaris (stage_check, path_report, derived_stage, flag_log)"} for ${caseId}…`);
  try {
    const data = await api(`/api/case/${caseId}`);
    state.current = data;
    renderPanel(data);
    renderReport(data.report_text, acceptedSpans(data.accepted));
    loadNote(caseId);
    loadTrace(caseId);
    $("f-out").replaceChildren();
    $("reject-reasons").classList.add("hidden");
    history.replaceState(null, "", `?case=${caseId}`);
    if (!options.keepStatus) status(`${caseId} · ${state.mode === "sample" ? "sample data, no network" : "read live from the Zetaris USL"}`);
  } catch (error) {
    status(`Could not load ${caseId}: ${error.message}. The queue still works.`);
  }
}

// ---------- wiring ----------
function wire() {
  document.querySelectorAll(".reasons button").forEach((b) => b.addEventListener("click", () => decide("neither", b.dataset.r)));
  $("f-run").addEventListener("click", challenge);
  $("note-run").addEventListener("click", writeNote);
  $("report-text").addEventListener("mouseup", () => {
    const picked = String(window.getSelection() || "").trim();
    if (picked.length > 3) $("f-quote").value = picked;
  });
  document.querySelectorAll("[data-mark]").forEach((cell) => {
    const marks = () => document.querySelectorAll(`#report-text mark.${cell.dataset.mark}`);
    cell.addEventListener("mouseenter", () => {
      const found = marks();
      found.forEach((m) => m.classList.add("glow"));
      if (found.length) found[0].scrollIntoView({ block: "center", behavior: "smooth" });
    });
    cell.addEventListener("mouseleave", () => marks().forEach((m) => m.classList.remove("glow")));
  });
  document.addEventListener("keydown", (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    const key = event.key.toLowerCase();
    const reasonsOpen = !$("reject-reasons").classList.contains("hidden");
    if (key === "j") openCase(state.index + 1);
    else if (key === "k") openCase(state.index - 1);
    else if (["1", "2", "3", "4"].includes(key) && reasonsOpen) decide("neither", ["addendum", "misread", "rule", "other"][Number(key) - 1]);
    else if (["1", "2", "3"].includes(key) && state.claims) decide(state.claims[Number(key) - 1]);
  });
}

async function start() {
  wire();
  try {
    const mode = await api("/api/mode");
    state.mode = mode.mode;
    state.reader = mode.reader;
    state.sourceNote = mode.source_note;
    const badge = $("mode");
    badge.textContent = state.mode === "sample" ? "SAMPLE MODE · rules live · model reads off" : "LIVE · Zetaris USL stage_audit";
    badge.classList.toggle("live", state.mode === "live");
    status(state.mode === "sample" ? "Loading the bundled sample…" : "Waiting for Zetaris stage_check…");
    state.queue = await api("/api/queue");
    renderQueue();
    loadCohort();
    if (!state.queue.length) { status("The queue is empty: no case has a node-count contradiction or a missing N."); return; }
    const wanted = new URLSearchParams(location.search).get("case");
    let position = state.queue.findIndex((q) => q.case_id === wanted);
    if (position < 0) position = state.queue.findIndex((q) => q.fault_field === "node_count" && !q.decided_at);
    openCase(position < 0 ? 0 : position);
  } catch (error) {
    status(`Could not load the queue: ${error.message}`);
  }
}

start();
