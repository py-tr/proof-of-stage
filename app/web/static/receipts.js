// Receipt explorer: the committed Nightshift envelopes, each Ed25519 signature checked in this
// browser against the committed public key. The checks mirror app/verify.py. Recorded runs;
// nothing here calls a model. Plain JS; every text is a text node.
"use strict";

const $ = (id) => document.getElementById(id);
const show = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
const enc = new TextEncoder();

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

// The bytes Nightshift signs: the body as sorted, compact, UTF-8 JSON.
function canon(v) {
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  if (v && typeof v === "object") return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
  return JSON.stringify(v);
}

const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function fingerprint(keyB64) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(keyB64)));
  return Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

let engine = null; // "WebCrypto" or "tweetnacl"
async function makeVerifier() {
  try {
    await crypto.subtle.importKey("raw", new Uint8Array(32), { name: "Ed25519" }, false, ["verify"]);
    engine = "WebCrypto";
  } catch (error) {
    await new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/tweetnacl/1.0.3/nacl-fast.min.js";
      s.onload = ok;
      s.onerror = () => fail(new Error("This browser has no Ed25519 and the fallback library did not load."));
      document.head.append(s);
    });
    engine = "tweetnacl";
  }
}

const keys = new Map();
async function verifySig(keyB64, sigB64, bytes) {
  if (engine === "tweetnacl") return window.nacl.sign.detached.verify(bytes, b64(sigB64), b64(keyB64));
  if (!keys.has(keyB64)) keys.set(keyB64, await crypto.subtle.importKey("raw", b64(keyB64), { name: "Ed25519" }, false, ["verify"]));
  return crypto.subtle.verify({ name: "Ed25519" }, keys.get(keyB64), b64(sigB64), bytes);
}

// One row, the same checks as app/verify.py check_envelope.
async function check(row, pinnedFp) {
  const env = row.envelope || {};
  const ok = await verifySig(env.pubkey_b64, env.sig_b64, enc.encode(canon(env.body)));
  if (!ok) return { ok: false, problems: ["signature invalid"], signed: {} };
  const problems = [];
  const signed = (env.body && env.body.receipt) || {};
  if ((await fingerprint(env.pubkey_b64)) !== pinnedFp) problems.push("signed by a key other than the committed one");
  if (signed.receipt_id !== row.receipt_id) problems.push("receipt id differs from the signed body");
  const route = signed.winning_route || {};
  const model = String(route.model || "");
  if (!model.startsWith("nvidia/nemotron") && !model.startsWith("local-runtime/nemotron")) problems.push(`signed model is ${show(route.model)}`);
  if (route.model !== row.served_model) problems.push("served model differs from the signed body");
  const cache = (signed.cache || {}).status;
  if (![undefined, null, "miss", "bypass"].includes(cache)) problems.push(`cache ${cache}`);
  return { ok: problems.length === 0, problems, signed };
}

let current = null;

function oneByteTamper(row) {
  const body = JSON.parse(JSON.stringify(row.envelope.body));
  const id = String(body.receipt.receipt_id);
  body.receipt.receipt_id = id.slice(0, -1) + (id.slice(-1) === "a" ? "b" : "a");
  return { body, before: id, after: body.receipt.receipt_id };
}

async function renderTamper(row) {
  const box = $("tamper");
  const head = [el("div", { class: "who" }, "Tamper test"), el("h2", {}, "Change one byte, and the signature fails")];
  if (!row) { box.replaceChildren(...head, el("p", { class: "small" }, "No receipt in this bundle.")); return; }
  const t = oneByteTamper(row);
  const env = row.envelope;
  const original = await verifySig(env.pubkey_b64, env.sig_b64, enc.encode(canon(env.body)));
  const tampered = await verifySig(env.pubkey_b64, env.sig_b64, enc.encode(canon(t.body)));
  box.replaceChildren(...head,
    el("p", {}, `Receipt ${row.receipt_id} (${show(row.case)}), as Nightshift signed it: `, el("span", { class: original ? "rx-ok" : "rx-bad" }, original ? "valid" : "INVALID"), "."),
    el("div", { class: "rx-diff" }, "receipt_id: ", el("del", {}, t.before), " → ", el("ins", {}, t.after)),
    el("p", {}, "The same body with that one character changed, same signature: ", el("span", { class: tampered ? "rx-ok" : "rx-bad" }, tampered ? "valid (this should not happen)" : "INVALID"), "."),
    el("p", { class: "small" }, "Any change does the same: the model id, the cache status, the prompt size. python -m app.verify runs these checks offline, and a test changes one byte."));
}

function loadEdit(row, scroll) {
  current = row;
  $("edit").value = JSON.stringify(row.envelope.body, null, 1);
  $("edit-result").textContent = `Loaded ${row.receipt_id}. Change something, then check.`;
  if (scroll) $("edit-card").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function checkEdit() {
  const out = $("edit-result");
  if (!current) { out.textContent = "Pick a receipt in the table first."; return; }
  let body;
  try { body = JSON.parse($("edit").value); } catch (error) { out.replaceChildren(el("span", { class: "rx-bad" }, "Not valid JSON"), ` (${error.message}).`); return; }
  const env = current.envelope;
  const ok = await verifySig(env.pubkey_b64, env.sig_b64, enc.encode(canon(body)));
  const same = canon(body) === canon(env.body);
  out.replaceChildren(el("span", { class: ok ? "rx-ok" : "rx-bad" }, ok ? "Signature valid" : "Signature INVALID"),
    same ? " (the body is byte for byte the one Nightshift signed)." : ok ? "." : " (the body differs from the one Nightshift signed).");
}

async function loadBundle(key) {
  $("rows").textContent = "Checking…";
  const data = await api(`/api/receipts/${encodeURIComponent(key)}`);
  const pinnedFp = data.fingerprint;
  const computedFp = await fingerprint(data.pubkey_b64);
  const results = [];
  for (const row of data.rows) results.push({ row, ...(await check(row, pinnedFp)) });
  const good = results.filter((r) => r.ok).length;
  const models = {};
  for (const r of results) if (r.ok) { const m = (r.signed.winning_route || {}).model; models[m] = (models[m] || 0) + 1; }
  $("summary").replaceChildren(
    el("div", { class: "who" }, `Checked in this browser (${engine})`),
    el("h2", {}, data.label),
    el("div", { class: "flow" },
      el("span", { class: good === results.length && results.length ? "good" : "bad" }, `${good} of ${results.length} receipts pass every check`),
      el("span", { class: computedFp === pinnedFp ? "good" : "bad" }, `committed key ${pinnedFp}${computedFp === pinnedFp ? "" : " (fingerprint mismatch)"}`)),
    el("p", { class: "small" }, "Signed models: " + (Object.entries(models).map(([m, n]) => `${m} × ${n}`).join(", ") || "—")),
    el("p", { class: "small" }, "Per receipt: the Ed25519 signature over the body; the signer is the committed key; the signed receipt id is this row's; the signed model is a Nemotron and the one the run logged; the cache was not used."));
  await renderTamper(data.rows[0]);
  const table = el("table", { class: "how-table" },
    el("thead", {}, el("tr", {}, ...["", "case", "receipt", "signed model", "cache", "prompt tokens", ""].map((h) => el("th", {}, h)))));
  const tbody = el("tbody");
  for (const r of results) {
    const s = r.signed;
    const btn = el("button", { class: "rx-link", type: "button" }, "edit");
    btn.addEventListener("click", () => loadEdit(r.row, true));
    tbody.append(el("tr", {},
      el("td", {}, el("span", { class: r.ok ? "rx-ok" : "rx-bad" }, r.ok ? "✓" : "✗")),
      el("td", {}, show(r.row.case)),
      el("td", {}, show(r.row.receipt_id), r.ok ? "" : el("div", { class: "rx-bad" }, r.problems.join("; "))),
      el("td", {}, show((s.winning_route || {}).model)),
      el("td", {}, show((s.cache || {}).status)),
      el("td", {}, show((s.autopilot || {}).prompt_tokens)),
      el("td", {}, btn)));
  }
  table.append(tbody);
  $("rows").replaceChildren(table);
  $("not-established").textContent = data.not_established;
  if (data.rows[0]) loadEdit(data.rows[0], false);
}

async function start() {
  $("check-edit").addEventListener("click", checkEdit);
  try { await makeVerifier(); } catch (error) { $("summary").replaceChildren(el("p", { class: "rx-bad" }, error.message)); return; }
  const { bundles } = await api("/api/receipts");
  const select = $("bundle");
  for (const b of bundles.filter((x) => x.present)) select.append(el("option", { value: b.id }, b.label));
  const wanted = new URLSearchParams(location.search).get("bundle");
  if (wanted && bundles.some((b) => b.id === wanted && b.present)) select.value = wanted;
  select.addEventListener("change", () => { history.replaceState(null, "", `?bundle=${select.value}`); loadBundle(select.value); });
  await loadBundle(select.value);
}

start();
