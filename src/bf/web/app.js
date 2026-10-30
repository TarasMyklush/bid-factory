// Bid Factory UI. Plain ES modules, no framework and no build step: the package ships these files as they are.
// Every dynamic value goes through html`` (escaped by default); raw() marks markup this file built itself.

/* ------------------------------------------------------------------ html and escaping */

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
const raw = (s) => new Raw(s);
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
function esc(v) {
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(esc).join("");
  if (v === null || v === undefined || v === false) return "";
  return String(v).replace(/[&<>"']/g, (c) => ESC[c]);
}
function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += esc(v) + strings[i + 1]; });
  return raw(out);
}
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ICONS = {
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5V21h16"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  check: '<path d="M5 12.5 10 17l9-10"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="m15 6-6 6 6 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  archive: '<path d="M3 4h18v4H3zM5 8v12h14V8M10 12h4"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9zM9 13l2 2 4-4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  package: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
};
const icon = (name, cls = "") => raw(`<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`);

/* ------------------------------------------------------------------ vocabulary */

const STATUS = {
  answered: { label: "Answered", cls: "ok" },
  partial: { label: "Partial", cls: "warn" },
  gap: { label: "Gap", cls: "bad" },
  client_decision: { label: "Client decision", cls: "violet" },
  not_applicable: { label: "Not applicable", cls: "" },
};
const STATUS_ORDER = ["gap", "client_decision", "partial", "answered", "not_applicable"];
const REC = {
  go: { label: "Go", cls: "go", pill: "ok", icon: "check", line: "The supplier meets every mandatory requirement on the evidence in its library." },
  no_go: { label: "No-go", cls: "no_go", pill: "bad", icon: "x", line: "Mandatory requirements are not met. Close the gaps below or decline the tender." },
  go_with_partner: { label: "Go with a partner", cls: "go_with_partner", pill: "warn", icon: "users", line: "Bid only with a partner that covers the gaps below." },
};
const PORTALS = {
  etimad: "Etimad (Saudi Arabia)", uae_federal_dpp: "UAE federal procurement", dubai_esupply: "Dubai eSupply",
  abu_dhabi: "Abu Dhabi procurement", semi_government: "Semi-government", private: "Private buyer", other: "Other",
};
const COUNTRIES = { SA: { label: "Saudi Arabia", offset: "+03:00", city: "Riyadh" }, AE: { label: "United Arab Emirates", offset: "+04:00", city: "Dubai" }, other: { label: "Other", offset: null } };
const STAGE_LABEL = {
  intake: "Read documents and classify data", extract: "Extract requirements", matrix: "Build compliance matrix",
  gaps: "Write gap report", draft: "Draft responses", pack: "Assemble pack", review: "Automated review", log: "Outcome logged",
};
const REVIEW_CODE = {
  A1: "Matrix incomplete", A2: "Mandatory gap", B1: "Citation to an unknown record", B2: "Claim without evidence",
  B3: "Evidence expires before the deadline", B4: "Citation permission", B5: "Personal contact details",
  C1: "Number not on the pricing sheet", D1: "Form incomplete", D2: "Open placeholder", F1: "Data tier breach",
  M0: "Model reviewer", M1: "Model reviewer note",
};
const OUTCOME_LABEL = {
  delivered: "Delivered to the client", submitted: "Submitted by the client", shortlisted: "Shortlisted", awarded: "Awarded",
  lost: "Lost", withdrawn: "Withdrawn", disqualified: "Disqualified", no_go: "No-go (not bid)",
};
const human = (s) => String(s || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;

function judgedBy(j) {
  if (!j) return "";
  if (j.startsWith("check:")) return `Deterministic check (${j.slice(6).replace(/_/g, " ")})`;
  if (j === "rules:coverage") return "Library match";
  if (j.startsWith("rules:")) return `Rule (${j.slice(6).replace(/_/g, " ")})`;
  if (j.startsWith("model")) return "Model judgement, validated against the library";
  return j;
}

/* ------------------------------------------------------------------ dates */

function parseIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::\d{2})?(Z|[+-]\d{2}:\d{2})?)?/.exec(iso || "");
  if (!m) return null;
  return { y: +m[1], mo: +m[2], d: +m[3], h: m[4], mi: m[5], off: m[6] === "Z" ? "+00:00" : m[6] };
}
function fmtDate(iso) {
  const p = parseIso(iso);
  if (!p) return iso || "";
  return new Date(Date.UTC(p.y, p.mo - 1, p.d)).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
function fmtDeadline(iso) {
  const p = parseIso(iso);
  if (!p) return iso || "";
  const off = p.off ? ` (UTC${p.off.replace(":00", "")})` : "";
  return `${fmtDate(iso)}, ${p.h}:${p.mi}${off}`;
}
function fmtWhen(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso || "";
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function daysLeftLabel(n) {
  if (n === null || n === undefined) return { text: "", cls: "" };
  if (n < 0) return { text: "closed", cls: "past" };
  if (n === 0) return { text: "due today", cls: "urgent" };
  return { text: `${plural(n, "day")} left`, cls: n <= 3 ? "urgent" : n <= 7 ? "soon" : "" };
}
function expiry(validUntil, ref) {
  if (!validUntil) return null;
  const until = new Date(validUntil + "T00:00:00Z");
  const base = ref ? new Date(ref) : new Date();
  const days = Math.floor((until - base) / 86400000);
  if (days < 0) return { cls: "bad", text: ref ? `expires before the deadline (${fmtDate(validUntil)})` : `expired ${fmtDate(validUntil)}` };
  if (days <= 90) return { cls: "warn", text: `valid until ${fmtDate(validUntil)}` };
  return { cls: "", text: `valid until ${fmtDate(validUntil)}` };
}
const fmtBytes = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`);

/* ------------------------------------------------------------------ markdown (the toolkit's own output only) */

function inline(s) {
  let t = esc(s);
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s).,;:]|$)/g, "$1<em>$2</em>");
  t = t.replace(/\[LIB:([A-Za-z0-9_.\-]+)\]/g, (m, id) => `<button type="button" class="cite" data-action="cite" data-id="${id}" aria-label="Library record ${id}">${id}</button>`);
  t = t.replace(/\[PRICING\]/g, '<span class="cite pricing" title="From the client pricing sheet">PRICING</span>');
  t = t.replace(/\[(CLIENT INPUT NEEDED|CLIENT DECISION NEEDED|INVALID CITATION)([^\]]*)\]/g, (m, k, rest) => {
    const cls = k === "CLIENT DECISION NEEDED" ? "decision" : k === "INVALID CITATION" ? "invalid" : "";
    return `<mark class="ph ${cls}">${k}${rest}</mark>`;
  });
  t = t.replace(/\[ \]/g, "☐").replace(/\[x\]/gi, "☑");
  t = t.replace(/NOT FOR SUBMISSION/g, '<span class="not-for-submission">NOT FOR SUBMISSION</span>');
  return t;
}
function md(src) {
  const lines = String(src || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let i = 0;
  const isBlockStart = (l) => /^(#{1,6}\s|>|\||```|\s*([-*]|\d+\.)\s+|(-{3,}|\*{3,})\s*$)/.test(l);
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    let m;
    if (l.startsWith("```")) {
      const buf = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++; out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`); continue;
    }
    if ((m = /^(#{1,6})\s+(.*)$/.exec(l))) {
      const n = Math.min(m[1].length + 1, 5);
      out.push(`<h${n} dir="auto">${inline(m[2])}</h${n}>`); i++; continue;
    }
    if (/^(-{3,}|\*{3,})\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (l.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
      const isSep = (r) => r.includes("-") && /^[\s|:-]+$/.test(r);
      const body = rows.filter((r) => !isSep(r));
      const head = body.shift();
      out.push("<div class=\"table-wrap\"><table><thead><tr>" + cells(head).map((c) => `<th dir="auto">${inline(c)}</th>`).join("") +
        "</tr></thead><tbody>" + body.map((r) => "<tr>" + cells(r).map((c) => `<td dir="auto">${inline(c)}</td>`).join("") + "</tr>").join("") +
        "</tbody></table></div>");
      continue;
    }
    if (l.startsWith(">")) {
      const buf = [];
      while (i < lines.length && lines[i].startsWith(">")) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote dir="auto">${inline(buf.join(" "))}</blockquote>`); continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      const ordered = /^\s*\d+\./.test(l);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(`<li dir="auto">${inline(item)}</li>`);
      }
      out.push(`<${ordered ? "ol" : "ul"}>${items.join("")}</${ordered ? "ol" : "ul"}>`); continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) buf.push(lines[i++]);
    if (!buf.length) buf.push(lines[i++]);
    out.push(`<p dir="auto">${inline(buf.join(" "))}</p>`);
  }
  return raw(out.join("\n"));
}

/* ------------------------------------------------------------------ api */

class ApiError extends Error { constructor(status, message) { super(message); this.status = status; } }

async function api(method, path, body, { text = false, rawBody = null } = {}) {
  const headers = { "X-BF-Request": "1" };
  let payload;
  if (rawBody) { payload = rawBody; headers["Content-Type"] = "application/octet-stream"; }
  else if (body !== undefined) { payload = JSON.stringify(body); headers["Content-Type"] = "application/json"; }
  const res = await fetch(path, { method, headers, body: payload, credentials: "same-origin", cache: "no-store" });
  if (res.status === 401) { showLocked(); throw new ApiError(401, "session locked"); }
  if (text) {
    if (!res.ok) throw new ApiError(res.status, `could not load ${path}`);
    return res.text();
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error || res.statusText);
  return data;
}
const runUrl = (id, rest = "") => `/api/runs/${encodeURIComponent(id)}${rest}`;
const downloadUrl = (id, path, inlineView = false) => `${runUrl(id, "/download")}?path=${encodeURIComponent(path)}${inlineView ? "&inline=1" : ""}`;

/* ------------------------------------------------------------------ app shell */

const app = {
  status: null, handlers: {}, timers: [], dirty: false, lastHash: location.hash, ignoreHash: false,
  newBid: null, reqFilter: { q: "", status: "all", mandatory: false, scored: false, owner: "all" },
  draftMode: "preview", signoff: {}, libFilter: { q: "", type: "all" }, matrixCache: {},
};
const main = () => $("#main");

function on(action, fn) { app.handlers[action] = fn; }
function every(ms, fn) { const t = setInterval(fn, ms); app.timers.push(t); }

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (!el) {
    if (!e.target.closest(".popover")) closePopover();
    return;
  }
  const fn = app.handlers[el.dataset.action];
  if (fn) { e.preventDefault(); fn(el, e); }
});
document.addEventListener("input", (e) => {
  const el = e.target.closest("[data-input]");
  if (el && app.handlers[el.dataset.input]) app.handlers[el.dataset.input](el, e);
});
document.addEventListener("change", (e) => {
  const el = e.target.closest("[data-change]");
  if (el && app.handlers[el.dataset.change]) app.handlers[el.dataset.change](el, e);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { if (closePopover()) return; if (app.handlers.escape) app.handlers.escape(e); }
  if (app.handlers.keydown) app.handlers.keydown(e);
});
window.addEventListener("beforeunload", (e) => { if (app.dirty) { e.preventDefault(); e.returnValue = ""; } });

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = html`${icon(kind === "bad" ? "alert" : "check")}<span>${message}</span>`.s;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "bad" ? 7000 : 3500);
}

function dialog({ title, body, confirm = "Confirm", danger = false, cancel = "Cancel" }) {
  const d = $("#dialog");
  d.innerHTML = html`<form method="dialog">
    <div class="d-body"><h2>${title}</h2><div class="muted">${body}</div></div>
    <div class="d-foot"><button class="btn" value="cancel">${cancel}</button>
    <button class="btn ${danger ? "danger" : "primary"}" value="ok">${confirm}</button></div></form>`.s;
  d.showModal();
  return new Promise((resolve) => d.addEventListener("close", () => resolve(d.returnValue === "ok"), { once: true }));
}

let popoverEl = null;
function closePopover() { if (popoverEl) { popoverEl.remove(); popoverEl = null; return true; } return false; }
function openPopover(anchor, content) {
  closePopover();
  popoverEl = document.createElement("div");
  popoverEl.className = "popover";
  popoverEl.setAttribute("role", "dialog");
  popoverEl.innerHTML = content.s;
  document.body.append(popoverEl);
  const r = anchor.getBoundingClientRect();
  const w = popoverEl.offsetWidth, h = popoverEl.offsetHeight;
  let left = Math.min(Math.max(12, r.left), window.innerWidth - w - 12);
  let top = r.bottom + 8;
  if (top + h > window.innerHeight - 12) top = Math.max(12, r.top - h - 8);
  popoverEl.style.left = `${left}px`;
  popoverEl.style.top = `${top}px`;
}

function renderNav(active, runs) {
  const items = [
    ["bids", "#/", "list", "Bids", runs !== undefined ? runs : ""],
    ["new", "#/new", "plus", "New bid", ""],
    ["libraries", "#/libraries", "book", "Libraries", ""],
    ["settings", "#/settings", "sliders", "Settings", ""],
  ];
  $("#nav").innerHTML = items.map(([key, href, ic, label, count]) => html`<a class="nav-item" href="${href}" ${raw(active === key ? 'aria-current="page"' : "")}>${icon(ic)}<span>${label}</span>${count !== "" ? html`<span class="count">${count}</span>` : ""}</a>`.s).join("");
  const st = app.status;
  if (st) {
    $("#sidebar-foot").innerHTML = html`
      <div class="row">${icon("lock")}<span>Local session, this computer only</span></div>
      <div class="row" title="${st.workspace}">${icon("folder")}<span class="mono" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${st.workspace.replace(/^\/(Users|home)\/[^/]+/, "~")}</span></div>
      <div>bf ${st.version}</div>`.s;
  }
}

function showLocked() {
  app.timers.forEach(clearInterval);
  app.timers = [];
  main().innerHTML = html`<div class="locked"><div class="card">${icon("lock", "xl")}<h1>Session locked</h1>
    <p class="muted">Open the link printed in the terminal where <code>bf ui</code> is running. It signs this browser in for this session only.</p></div></div>`.s;
}

function errorCard(err, retry = true) {
  return html`<div class="card card-pad stack"><div class="row">${icon("alert", "lg")}<h2>Something went wrong</h2></div>
    <p class="muted">${err.message || String(err)}</p>${retry ? html`<div><button class="btn" data-action="reload">${icon("refresh")} Try again</button></div>` : ""}</div>`;
}

async function router() {
  if (app.ignoreHash) { app.ignoreHash = false; return; }
  if (app.dirty && location.hash !== app.lastHash) {
    const leave = await dialog({ title: "Discard unsaved changes?", body: "You have edits to this section that are not saved.", confirm: "Discard changes", danger: true, cancel: "Keep editing" });
    if (!leave) { app.ignoreHash = true; location.hash = app.lastHash; return; }
    app.dirty = false;
  }
  const samePage = app.lastHash.split("/").slice(0, 3).join("/") === location.hash.split("/").slice(0, 3).join("/");
  app.lastHash = location.hash;
  if (!samePage) window.scrollTo(0, 0);
  app.timers.forEach(clearInterval);
  app.timers = [];
  app.handlers = { reload: () => router() };
  closePopover();
  const [path] = (location.hash.replace(/^#/, "") || "/").split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (!app.status) app.status = await api("GET", "/api/status");
    if (parts.length === 0) return await bidsView();
    if (parts[0] === "new") return await newBidView();
    if (parts[0] === "job" && parts[1]) return await jobView(parts[1]);
    if (parts[0] === "bid" && parts[1]) return await bidView(parts[1], parts[2] || "overview", parts[3]);
    if (parts[0] === "libraries") return parts[1] ? await libraryView(parts[1]) : await librariesView();
    if (parts[0] === "settings") return await settingsView();
    renderNav("");
    main().innerHTML = html`<div class="page"><div class="card empty">${icon("info")}<h2>Page not found</h2><a class="btn" href="#/">Back to bids</a></div></div>`.s;
  } catch (err) {
    if (err.status === 401) return;
    main().innerHTML = html`<div class="page">${errorCard(err)}</div>`.s;
  }
}
window.addEventListener("hashchange", router);

/* ------------------------------------------------------------------ bids */

function deadlineCell(r) {
  const dl = daysLeftLabel(r.days_left);
  return html`<div class="nowrap">${fmtDeadline(r.tender.deadline)}</div><div class="small deadline ${dl.cls}">${dl.text}</div>`;
}
function recPill(rec) {
  if (!rec) return html`<span class="faint">–</span>`;
  const r = REC[rec];
  return html`<span class="pill ${r.pill}"><span class="dot"></span>${r.label}</span>`;
}
function reviewPill(s) {
  if (s.status) return html`<span class="pill bad">${icon("shield")} Refused</span>`;
  if (s.busy) return html`<span class="pill accent">Processing</span>`;
  if (s.logged) return html`<span class="pill outline">${OUTCOME_LABEL[s.logged] || human(s.logged)}</span>`;
  if (s.signed_off) return html`<span class="pill ok">${icon("check")} Signed off</span>`;
  if (s.stale) return html`<span class="pill warn">Draft edited</span>`;
  if (s.review === "blocked") return html`<span class="pill bad">${plural(s.blocking || 0, "blocker")}</span>`;
  if (s.review === "ready_for_human_review") return html`<span class="pill accent">Ready for review</span>`;
  return html`<span class="pill">In progress</span>`;
}
function stageBar(s) {
  const all = ["intake", "extract", "matrix", "gaps", "draft", "pack", "review", "log"];
  return html`<div class="stages" aria-label="${s.stages.length} of ${all.length} stages done">${all.map((st) => html`<i class="${s.stages.includes(st) ? "on" : ""}" title="${STAGE_LABEL[st]}"></i>`)}</div>`;
}
const tierBadge = (t, title = "") => t ? html`<span class="tier ${t}" title="${title}">${icon("shield")}Tier ${t}</span>` : "";

async function bidsView() {
  const [runs, tenders] = await Promise.all([api("GET", "/api/runs"), api("GET", "/api/tenders")]);
  renderNav("bids", runs.length);
  const open = runs.filter((r) => !r.status && !r.logged);
  const due = open.filter((r) => r.days_left !== null && r.days_left >= 0 && r.days_left <= 7).length;
  const blocked = open.filter((r) => r.review === "blocked").length;
  const ready = open.filter((r) => r.review === "ready_for_human_review" && !r.signed_off).length;
  const unused = tenders.filter((t) => !t.used_by.length && t.files.length);
  on("open", (el) => { location.hash = `#/bid/${encodeURIComponent(el.dataset.id)}`; });
  main().innerHTML = html`<div class="page">
    <div class="page-head"><div><h1>Bids</h1><p class="sub">Every tender in this workspace, nearest deadline first.</p></div>
      <a class="btn primary" href="#/new">${icon("plus")} New bid</a></div>
    <div class="grid-4">
      ${statCard("Open bids", open.length, "")}
      ${statCard("Due within 7 days", due, due ? "Check the submission checklist" : "")}
      ${statCard("Blocked by review", blocked, blocked ? "Fix before delivery" : "")}
      ${statCard("Awaiting sign-off", ready, ready ? "Human review gate" : "")}
    </div>
    ${runs.length ? html`<div class="card"><div class="table-wrap"><table class="table">
      <thead><tr><th>Deadline</th><th>Tender</th><th>Client</th><th>Data</th><th>Recommendation</th><th>Status</th><th>Progress</th><th class="sr-only">Open</th></tr></thead>
      <tbody>${runs.map((r) => html`<tr class="clickable" data-action="open" data-id="${r.run_id}">
        <td>${deadlineCell(r)}</td>
        <td class="req"><a href="#/bid/${encodeURIComponent(r.run_id)}"><strong dir="auto">${r.tender.title || r.tender.reference}</strong></a>
          <div class="small muted" dir="auto">${r.tender.reference} · ${r.tender.buyer}</div></td>
        <td>${r.client_id}</td><td>${tierBadge(r.tier)}</td><td>${recPill(r.recommendation)}</td>
        <td>${reviewPill(r)}</td><td>${stageBar(r)}</td><td class="faint">${icon("chevron")}</td></tr>`)}</tbody></table></div></div>`
      : html`<div class="card empty">${icon("file")}<h2>No bids yet</h2>
        <p>Start with a tender's documents and the client's bid library. The toolkit extracts every requirement,
        checks it against the library and drafts a cited response.</p>
        ${unused.length ? html`<p class="small">There ${unused.length === 1 ? "is a tender" : `are ${unused.length} tenders`} in the workspace ready to use, for example <strong>${unused[0].meta?.title || unused[0].id}</strong>.</p>` : ""}
        <a class="btn primary" href="#/new">${icon("plus")} Start a bid</a></div>`}
  </div>`.s;
}
function statCard(label, value, foot) {
  return html`<div class="card stat"><div class="label">${label}</div><div class="value">${value}</div>${foot ? html`<div class="foot">${foot}</div>` : ""}</div>`;
}

/* ------------------------------------------------------------------ new bid */

function freshNewBid() {
  return { step: 1, mode: "upload", tender: null, meta: { buyer: "", reference: "", title: "", portal: "etimad", country: "SA", deadline: "", offset: "+03:00", category: "it_software" },
    client: "", library: "", handling: "restricted", model: "auto", uploading: 0, prefilled: false };
}
function prefill(nb) {
  const m = nb.tender?.meta;
  if (!m || nb.prefilled) return;
  for (const k of ["buyer", "reference", "title", "portal", "country", "category"]) if (m[k] && !nb.meta[k]?.length) nb.meta[k] = m[k];
  for (const k of ["portal", "country", "category"]) if (m[k]) nb.meta[k] = m[k];
  const p = parseIso(m.deadline);
  if (p && p.h) { nb.meta.deadline = `${p.y}-${String(p.mo).padStart(2, "0")}-${String(p.d).padStart(2, "0")}T${p.h}:${p.mi}`; nb.meta.offset = p.off || nb.meta.offset; }
  if (m.public === true) nb.handling = "public";
  nb.prefilled = true;
}
const documentsIn = (t) => (t?.files || []).filter((f) => !f.name.endsWith(".json"));

function expectedModel(nb) {
  const m = app.status.models;
  const tier = nb.handling === "public" ? "A" : nb.handling === "classified" ? "C" : "B";
  if (tier === "C") return { ok: false, text: "The toolkit refuses classified material. Handle this tender by hand." };
  if (nb.model === "rules") return { ok: true, text: "Deterministic rules only. Nothing leaves this computer." };
  if (nb.model === "anthropic") {
    if (tier !== "A") return { ok: false, text: "Refused: restricted material may not be sent to Claude, which is not hosted in the region." };
    return m.anthropic_key ? { ok: true, text: `Claude (${m.anthropic_model}) for matrix judgement and drafting.` } : { ok: false, text: "Claude is selected but ANTHROPIC_API_KEY is not set where bf ui was started." };
  }
  if (nb.model === "tier-b") return m.tier_b_endpoint ? { ok: true, text: `In-country model at ${m.tier_b_endpoint}.` } : { ok: false, text: "No in-country endpoint is configured (BF_TIER_B_URL)." };
  if (tier === "A" && m.anthropic_key) return { ok: true, text: `Claude (${m.anthropic_model}), because the tender is public and a key is set.` };
  if (m.tier_b_endpoint) return { ok: true, text: `In-country model at ${m.tier_b_endpoint}.` };
  return { ok: true, text: "Deterministic rules, because no model is configured for this data tier. Nothing leaves this computer." };
}

async function newBidView() {
  renderNav("new");
  if (!app.newBid) app.newBid = freshNewBid();
  const nb = app.newBid;
  const [tenders, libraries] = await Promise.all([api("GET", "/api/tenders"), api("GET", "/api/libraries")]);
  if (!nb.library && libraries.length === 1 && !libraries[0].error) nb.library = libraries[0].name;
  const draw = () => { main().innerHTML = newBidHtml(nb, tenders, libraries).s; bindDropzone(nb); };

  const upload = async (files) => {
    if (!files.length) return;
    try {
      if (!nb.tender) nb.tender = await api("POST", "/api/tenders", { label: files[0].name.replace(/\.[^.]+$/, "") });
      nb.uploading = files.length; draw();
      for (const f of files) {
        let name = f.name.replace(/[^A-Za-z0-9 ._()-]/g, "_");
        if (!/^[A-Za-z0-9]/.test(name)) name = "file-" + name;
        try { nb.tender = await api("PUT", `/api/tenders/${encodeURIComponent(nb.tender.id)}/files/${encodeURIComponent(name)}`, undefined, { rawBody: f }); }
        catch (err) { toast(err.message, "bad"); }
        nb.uploading--;
      }
      prefill(nb); draw();
    } catch (err) { nb.uploading = 0; toast(err.message, "bad"); draw(); }
  };
  app.handlers.uploadFiles = upload;
  on("pick-files", () => $("#file-input").click());
  app.handlers["files-chosen"] = (el) => { upload([...el.files]); el.value = ""; };
  on("mode", (el) => { nb.mode = el.dataset.mode; draw(); });
  on("remove-file", async (el) => {
    try { nb.tender = await api("DELETE", `/api/tenders/${encodeURIComponent(nb.tender.id)}/files/${encodeURIComponent(el.dataset.name)}`); draw(); }
    catch (err) { toast(err.message, "bad"); }
  });
  app.handlers["pick-tender"] = (el) => { nb.tender = tenders.find((t) => t.id === el.value); nb.prefilled = false; prefill(nb); draw(); };
  app.handlers["field"] = (el) => {
    const k = el.name;
    if (k in nb.meta) nb.meta[k] = el.value; else nb[k] = el.value;
    if (k === "country" && COUNTRIES[el.value].offset) nb.meta.offset = COUNTRIES[el.value].offset;
    if (["country", "handling", "model", "library"].includes(k) || el.type === "radio") draw();
  };
  on("step", (el) => {
    const to = +el.dataset.to;
    if (to > nb.step && !validStep(nb)) return;
    nb.step = to; draw(); window.scrollTo(0, 0); main().focus({ preventScroll: true });
  });
  on("reset", () => { app.newBid = freshNewBid(); router(); });
  on("start", async (el) => {
    el.setAttribute("aria-disabled", "true");
    const m = nb.meta;
    try {
      const job = await api("POST", "/api/jobs", {
        tender_id: nb.tender.id, library: nb.library, client: nb.client.trim(), model: nb.model,
        public: nb.handling === "public", buyer: m.buyer, reference: m.reference, title: m.title, portal: m.portal,
        country: m.country, deadline: `${m.deadline}:00${m.offset}`, category: m.category,
      });
      app.newBid = null;
      location.hash = `#/job/${job.id}`;
    } catch (err) { el.removeAttribute("aria-disabled"); toast(err.message, "bad"); }
  });
  draw();
}

function validStep(nb) {
  if (nb.step === 1) {
    if (!documentsIn(nb.tender).length) { toast("Add at least one tender document (PDF, Word, Markdown or text).", "bad"); return false; }
    prefill(nb);
  }
  if (nb.step === 2) {
    const m = nb.meta;
    const missing = [["buyer", m.buyer], ["reference", m.reference], ["title", m.title], ["deadline", m.deadline], ["client id", nb.client.trim()], ["library", nb.library]].filter(([, v]) => !v).map(([k]) => k);
    if (!/^[+-]\d{2}:\d{2}$/.test(m.offset)) missing.push("UTC offset (for example +03:00)");
    if (missing.length) { toast(`Fill in: ${missing.join(", ")}`, "bad"); return false; }
  }
  return true;
}

function newBidHtml(nb, tenders, libraries) {
  const steps = ["Tender documents", "Tender details", "Data handling"];
  const head = html`<div class="page-head"><div><h1>New bid</h1><p class="sub">Three steps. Nothing is processed until you start the bid.</p></div>
    ${nb.tender || nb.client ? html`<button class="btn ghost" data-action="reset">Start over</button>` : ""}</div>
    <ol class="stepper" aria-label="Progress">${steps.map((s, i) => html`<li class="${i + 1 < nb.step ? "done" : ""}" ${raw(i + 1 === nb.step ? 'aria-current="step"' : "")}><span class="num">${i + 1 < nb.step ? icon("check") : i + 1}</span>${s}</li>`)}</ol>`;
  let body;
  if (nb.step === 1) body = stepDocuments(nb, tenders);
  else if (nb.step === 2) body = stepDetails(nb, libraries);
  else body = stepHandling(nb, libraries);
  return html`<div class="page narrow">${head}${body}</div>`;
}

function stepDocuments(nb, tenders) {
  const docs = nb.tender?.files || [];
  const existing = tenders.filter((t) => t.files.length);
  return html`<div class="card"><div class="card-head"><h2>Tender documents</h2>
      <div class="segmented" role="group" aria-label="Source">
        <button type="button" data-action="mode" data-mode="upload" aria-pressed="${String(nb.mode === "upload")}">Upload</button>
        <button type="button" data-action="mode" data-mode="existing" aria-pressed="${String(nb.mode === "existing")}">In workspace${existing.length ? ` (${existing.length})` : ""}</button>
      </div></div>
    <div class="card-body stack">
    ${nb.mode === "upload" ? html`
      <div class="dropzone" id="dropzone" data-action="pick-files" role="button" tabindex="0" aria-label="Add tender documents">
        ${icon("upload", "xl")}<div><strong>Drop the tender documents here</strong> or click to choose files</div>
        <div class="small">PDF, Word (.docx), Markdown or text. Add <code>tender.json</code> to fill in the details automatically, and <code>pricing.json</code> for a bid-specific price sheet.</div>
      </div>
      <input type="file" id="file-input" class="sr-only" multiple accept=".pdf,.docx,.md,.txt,.json" data-change="files-chosen" tabindex="-1">
      ${nb.uploading ? html`<p class="muted small" role="status">Uploading ${plural(nb.uploading, "file")}…</p>` : ""}
      ${docs.length ? html`<div class="filelist">${docs.map((f) => html`<div class="file">${icon("file")}<span class="name grow">${f.name}</span><span class="small faint">${fmtBytes(f.bytes)}</span>
        <button class="btn ghost sm" data-action="remove-file" data-name="${f.name}" aria-label="Remove ${f.name}">${icon("x")}</button></div>`)}</div>` : ""}
      <p class="small muted">${icon("lock")} Files are stored only in this workspace on this computer and are deleted when the bid is closed.</p>`
    : existing.length ? html`<div class="choice" role="radiogroup" aria-label="Tenders in the workspace">${existing.map((t) => html`
        <label class="choice-card"><input type="radio" name="tender" value="${t.id}" data-change="pick-tender" ${raw(nb.tender?.id === t.id ? "checked" : "")}>
          <div class="grow"><div class="title" dir="auto">${t.meta?.title || t.id}</div>
          <div class="small muted">${t.meta?.reference ? `${t.meta.reference} · ` : ""}${plural(documentsIn(t).length, "document")}${t.meta ? " · details included" : ""}${t.used_by.length ? ` · used by ${plural(t.used_by.length, "bid")}` : ""}</div></div></label>`)}</div>`
      : html`<div class="empty">${icon("folder")}<p>No tenders in the workspace yet. Upload the documents instead.</p></div>`}
    </div></div>
    <div class="btn-row" style="justify-content:flex-end"><button class="btn primary" data-action="step" data-to="2" ${raw(documentsIn(nb.tender).length ? "" : 'aria-disabled="true"')}>Continue ${icon("chevron")}</button></div>`;
}

function stepDetails(nb, libraries) {
  const m = nb.meta;
  const country = COUNTRIES[m.country] || COUNTRIES.other;
  const field = (name, label, value, hint = "", attrs = "", cls = "") => html`<label class="field ${cls}">${label}${hint ? html`<span class="hint">${hint}</span>` : ""}
    <input type="text" name="${name}" value="${value}" data-input="field" ${raw(attrs)}></label>`;
  return html`<div class="card"><div class="card-head"><h2>Tender details</h2>${nb.tender?.meta ? html`<span class="pill accent">${icon("check")} Filled from tender.json</span>` : ""}</div>
    <div class="card-body form-grid">
      ${field("title", "Tender title", m.title, "", 'dir="auto"', "span-2")}
      ${field("buyer", "Buyer", m.buyer, "", 'dir="auto"')}
      ${field("reference", "Tender reference", m.reference)}
      <label class="field">Portal<select name="portal" data-change="field">${Object.entries(PORTALS).map(([k, v]) => html`<option value="${k}" ${raw(m.portal === k ? "selected" : "")}>${v}</option>`)}</select></label>
      <label class="field">Country<select name="country" data-change="field">${Object.entries(COUNTRIES).map(([k, v]) => html`<option value="${k}" ${raw(m.country === k ? "selected" : "")}>${v.label}</option>`)}</select></label>
      <label class="field">Submission deadline<span class="hint">${country.offset ? `${country.city} time, UTC${country.offset.replace(":00", "")}` : "Local time at the buyer"}</span>
        <input type="datetime-local" name="deadline" value="${m.deadline}" data-input="field"></label>
      ${country.offset ? html`<div></div>` : field("offset", "UTC offset at the buyer", m.offset, "For example +03:00")}
      ${field("client", "Client id", nb.client, "Short supplier name for logs", 'autocomplete="off"')}
      ${field("category", "Category", m.category, "it_software for the first ten bids")}
    </div></div>
    <div class="card"><div class="card-head"><h2>Client bid library</h2><a class="small" href="#/libraries">Browse libraries</a></div>
      <div class="card-body">${libraries.length ? html`<div class="choice" role="radiogroup" aria-label="Library">${libraries.map((l) => html`
        <label class="choice-card"><input type="radio" name="library" value="${l.name}" data-change="field" ${raw(nb.library === l.name ? "checked" : "")} ${raw(l.error ? "disabled" : "")}>
          <div class="grow"><div class="title">${l.company || l.name}</div>
          <div class="small muted">${l.error ? html`<span class="pill bad">Invalid</span> ${l.error}` : html`${l.name} · ${plural(l.records, "record")}${l.has_pricing ? " · pricing sheet" : ""}`}</div>
          ${l.expired || l.expiring ? html`<div class="small" style="margin-top:4px">${l.expired ? html`<span class="pill bad">${l.expired} expired</span> ` : ""}${l.expiring ? html`<span class="pill warn">${l.expiring} expiring within 90 days</span>` : ""}</div>` : ""}</div></label>`)}</div>`
      : html`<div class="empty">${icon("book")}<p>No libraries found in <code>${app.status.libraries}</code>. Add a client library folder there, or start <code>bf ui --libraries DIR</code>.</p></div>`}</div></div>
    <div class="btn-row between"><button class="btn" data-action="step" data-to="1">${icon("back")} Back</button><button class="btn primary" data-action="step" data-to="3">Continue ${icon("chevron")}</button></div>`;
}

function stepHandling(nb, libraries) {
  const exp = expectedModel(nb);
  const m = nb.meta;
  const lib = libraries.find((l) => l.name === nb.library);
  const opt = (value, title, body, tier) => html`<label class="choice-card"><input type="radio" name="handling" value="${value}" data-change="field" ${raw(nb.handling === value ? "checked" : "")}>
    <div class="grow"><div class="row"><span class="title">${title}</span>${tierBadge(tier)}</div><div class="small muted">${body}</div></div></label>`;
  const blocked = !exp.ok || nb.handling === "classified";
  return html`<div class="card"><div class="card-head"><h2>How sensitive are these documents?</h2></div>
    <div class="card-body stack"><div class="choice" role="radiogroup" aria-label="Data handling">
      ${opt("public", "Public tender", "Published openly, for example on Etimad or a government portal, with no personal data in it. Claude may be used if it is configured.", "A")}
      ${opt("restricted", "Restricted (the default)", "Shared under NDA or a supplier login, or containing personal data. Only the in-country model or deterministic rules are used.", "B")}
      ${opt("classified", "Classified", "Marked secret or confidential by the buyer, or security related. The toolkit refuses it; the team handles it by hand.", "C")}
    </div>
    <p class="small muted">${icon("info")} The toolkit also scans the documents. If it finds restricted or classified markers it raises the tier. It never lowers it.</p></div></div>
    <div class="card"><div class="card-head"><h2>Model</h2></div><div class="card-body stack">
      <label class="field">Routing<select name="model" data-change="field">
        ${[["auto", "Automatic (recommended)"], ["rules", "Deterministic rules only"], ["tier-b", "In-country model"], ["anthropic", "Claude (public tenders only)"]].map(([v, l]) => html`<option value="${v}" ${raw(nb.model === v ? "selected" : "")}>${l}</option>`)}
      </select></label>
      <div class="banner ${exp.ok ? "info" : "bad"}">${icon(exp.ok ? "cpu" : "alert")}<div class="grow">${exp.text}</div></div>
    </div></div>
    <div class="card"><div class="card-head"><h2>Summary</h2></div><div class="card-body"><dl class="facts">
      <dt>Tender</dt><dd dir="auto">${m.title} <span class="muted">(${m.reference})</span></dd>
      <dt>Buyer</dt><dd dir="auto">${m.buyer}</dd>
      <dt>Portal</dt><dd>${PORTALS[m.portal]}</dd>
      <dt>Deadline</dt><dd>${fmtDeadline(`${m.deadline}:00${m.offset}`)}</dd>
      <dt>Documents</dt><dd>${documentsIn(nb.tender).map((f) => f.name).join(", ")}</dd>
      <dt>Client</dt><dd>${nb.client} · ${lib ? `${lib.company || lib.name}, ${plural(lib.records, "record")}` : nb.library}</dd>
    </dl></div></div>
    <div class="btn-row between"><button class="btn" data-action="step" data-to="2">${icon("back")} Back</button>
      <button class="btn primary" data-action="start" ${raw(blocked ? 'aria-disabled="true"' : "")}>${icon("check")} Start bid</button></div>`;
}

function bindDropzone(nb) {
  const dz = $("#dropzone");
  if (!dz) return;
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#file-input").click(); } });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
  dz.addEventListener("drop", (e) => app.handlers.uploadFiles([...e.dataTransfer.files]));
}

/* ------------------------------------------------------------------ job progress */

async function jobView(id) {
  renderNav("new");
  const draw = (job) => {
    const done = job.state === "done";
    const title = { running: "Preparing the bid", done: "Bid ready", failed: "The run stopped", refused: "Refused" }[job.state];
    main().innerHTML = html`<div class="page narrow">
      <div class="page-head"><div><h1>${title}</h1><p class="sub">${job.kind === "rerun" ? "Re-running from the current library." : "Every step runs on this computer."}</p></div></div>
      ${job.state === "refused" ? html`<div class="banner bad">${icon("shield")}<div class="grow"><strong>Refused by the data tier rules</strong>${job.error}</div></div>` : ""}
      ${job.state === "failed" ? html`<div class="banner bad">${icon("alert")}<div class="grow"><strong>A step failed</strong><span class="mono">${job.error}</span></div></div>` : ""}
      <div class="card card-pad"><ol class="progress" aria-live="polite">${job.stages.map((s) => html`<li class="${s.state}">
        <span class="state">${s.state === "done" ? icon("check") : s.state === "blocked" ? icon("alert") : ["failed", "refused"].includes(s.state) ? icon("x") : ""}</span>
        <div><div class="label">${STAGE_LABEL[s.name] || s.name}${s.state === "blocked" ? " — blocking findings" : ""}</div>${s.message ? html`<div class="msg">${s.message}</div>` : ""}</div></li>`)}</ol></div>
      <div class="btn-row">${job.run_id ? html`<a class="btn ${done ? "primary" : ""}" href="#/bid/${encodeURIComponent(job.run_id)}">Open bid ${icon("chevron")}</a>` : ""}
        ${job.state !== "running" && !job.run_id ? html`<a class="btn" href="#/new">Back to the new bid</a>` : ""}</div></div>`.s;
    return job;
  };
  let job = draw(await api("GET", `/api/jobs/${encodeURIComponent(id)}`));
  if (job.state !== "running") return;
  every(700, async () => {
    try {
      job = draw(await api("GET", `/api/jobs/${encodeURIComponent(id)}`));
      if (job.state !== "running") {
        app.timers.forEach(clearInterval); app.timers = [];
        delete app.matrixCache[job.run_id];
        if (job.state === "done" && job.run_id) setTimeout(() => { if (location.hash === `#/job/${id}`) location.hash = `#/bid/${encodeURIComponent(job.run_id)}`; }, 900);
      }
    } catch { /* keep polling */ }
  });
}

/* ------------------------------------------------------------------ bid */

const TABS = [
  ["overview", "Overview", "grid"], ["requirements", "Requirements", "list"], ["gaps", "Gaps", "target"],
  ["draft", "Draft", "edit"], ["review", "Review", "clipboard"], ["pack", "Pack", "package"], ["close", "Close out", "flag"],
];

async function loadMatrix(id, force = false) {
  if (force || !app.matrixCache[id]) app.matrixCache[id] = await api("GET", runUrl(id, "/matrix"));
  return app.matrixCache[id];
}

async function bidView(id, tab, sub) {
  renderNav("bids");
  const d = await api("GET", runUrl(id));
  const s = d.summary;
  const refused = Boolean(s.status);
  if (refused) tab = "overview";
  const matrixTab = ["requirements", "gaps", "draft"].includes(tab);
  const mx = matrixTab && d.matrix_summary ? await loadMatrix(id, s.busy) : null;

  on("rerun", async (el) => {
    const from = el.dataset.from;
    const edits = Object.keys(d.run.ui?.edits || {}).length;
    const ok = from === "pack" ? true : await dialog({
      title: "Re-check against the library?",
      body: html`This rebuilds the matrix, gap report, draft, pack and review from the library as it is now. Reviewer notes are kept.${edits ? html` <strong>Your edits to ${plural(edits, "section")} will be replaced by a fresh draft.</strong>` : ""} Sign-off is cleared.`,
      confirm: "Re-check",
    });
    if (!ok) return;
    try {
      const job = await api("POST", runUrl(id, "/rerun"), { from, model: "auto" });
      delete app.matrixCache[id];
      location.hash = `#/job/${job.id}`;
    } catch (err) { toast(err.message, "bad"); }
  });

  const counts = d.matrix_summary?.by_status || {};
  const gapCount = (counts.gap || 0) + (counts.partial || 0) + (counts.client_decision || 0);
  const placeholders = (d.sections?.sections || []).reduce((a, x) => a + (x.placeholders || 0), 0);
  const tabCount = {
    requirements: d.matrix_summary ? html`<span class="n">${d.matrix_summary.total}</span>` : "",
    gaps: gapCount ? html`<span class="n ${d.matrix_summary.mandatory_gaps ? "bad" : "warn"}">${gapCount}</span>` : "",
    draft: placeholders ? html`<span class="n warn">${placeholders}</span>` : "",
    review: d.review?.counts?.blocking ? html`<span class="n bad">${d.review.counts.blocking}</span>` : "",
  };
  const dl = daysLeftLabel(s.days_left);
  const t = d.run.tender;
  const header = html`<div class="bid-head">
    <div class="crumbs"><a href="#/">Bids</a>${icon("chevron")}<span>${t.reference}</span></div>
    <div class="page-head"><div class="grow"><h1 dir="auto">${t.title}</h1>
      <div class="bid-meta" style="margin-top:8px">
        <span dir="auto">${t.buyer}</span><span>${PORTALS[t.portal] || t.portal}</span>
        <span class="row">${icon("clock")}<span>${fmtDeadline(t.deadline)}</span>${dl.text ? html`<span class="deadline ${dl.cls}">· ${dl.text}</span>` : ""}</span>
        ${tierBadge(s.tier, (d.run.tier?.reasons || []).join("; "))}<span>Client <strong>${d.run.client_id}</strong></span>
      </div></div>
      ${refused ? "" : html`<div class="btn-row">
        ${s.stale ? html`<button class="btn primary" data-action="rerun" data-from="pack" ${raw(s.busy ? 'aria-disabled="true"' : "")}>${icon("refresh")} Rebuild pack and review</button>` : ""}
        <button class="btn" data-action="rerun" data-from="matrix" ${raw(s.busy || !d.matrix_summary ? 'aria-disabled="true"' : "")}>${icon("refresh")} Re-check against library</button></div>`}
    </div>
    ${s.busy ? html`<div class="banner info">${icon("refresh")}<div class="grow"><strong>Processing</strong>This bid is being rebuilt. ${d.job ? html`<a href="#/job/${d.job}">Watch progress</a>` : ""}</div></div>` : ""}
    ${refused ? "" : html`<nav class="tabs" aria-label="Bid sections">${TABS.map(([k, label, ic]) => html`<a href="#/bid/${encodeURIComponent(id)}/${k}" ${raw(tab === k ? 'aria-current="page"' : "")}>${icon(ic)}${label}${tabCount[k] || ""}</a>`)}</nav>`}
  </div>`;

  let body;
  const view = { overview: overviewTab, requirements: requirementsTab, gaps: gapsTab, draft: draftTab, review: reviewTab, pack: packTab, close: closeTab }[tab];
  if (!view) body = html`<div class="card empty"><h2>Unknown section</h2></div>`;
  else if (matrixTab && !mx) body = notYet("The compliance matrix has not been built yet.");
  else body = await view(id, d, mx, sub);
  main().innerHTML = html`<div class="page">${header}${body}</div>`.s;
  if (app.afterRender) { const f = app.afterRender; app.afterRender = null; f(); }
  if (s.busy) every(1500, async () => {
    try { const next = await api("GET", runUrl(id)); if (!next.summary.busy) { delete app.matrixCache[id]; router(); } } catch { /* ignore */ }
  });
}
const notYet = (msg) => html`<div class="card empty">${icon("clock")}<h2>Not ready yet</h2><p>${msg}</p></div>`;

/* ---------- overview */

function overviewTab(id, d) {
  const s = d.summary, ms = d.matrix_summary, run = d.run;
  if (s.status) {
    return html`<div class="banner bad">${icon("shield", "lg")}<div class="grow"><strong>This tender is classified (Tier C). Nothing was processed.</strong>
      ${(run.tier?.reasons || []).join("; ")}. Handle it by hand, outside the toolkit.</div></div>`;
  }
  if (!ms) return notYet("The pipeline has not reached the compliance matrix.");
  const rec = REC[ms.go_no_go.recommendation];
  const total = ms.total || 1;
  const bars = STATUS_ORDER.filter((k) => ms.by_status[k]).map((k) => html`<span class="c-${k}" style="width:${(ms.by_status[k] / total) * 100}%" title="${STATUS[k].label}: ${ms.by_status[k]}"></span>`);
  const pts = ms.scored_points_available ? Math.round((ms.scored_points_evidenced / ms.scored_points_available) * 100) : null;
  const rv = d.review;
  const next = [];
  if (ms.mandatory_gaps) next.push(html`<li class="row"><span class="pill bad">${ms.mandatory_gaps}</span><span class="grow">Close the mandatory gaps with the client. Each one has an action and a date.</span>
    <a class="btn sm" href="${downloadUrl(id, "gap-report.md")}">${icon("download")} Gap report</a><a class="btn sm" href="#/bid/${encodeURIComponent(id)}/gaps">Open gaps</a></li>`);
  if (s.stale) next.push(html`<li class="row"><span class="pill warn">${icon("edit")}</span><span class="grow">The draft was edited after the last review. Rebuild the pack and review.</span><button class="btn sm" data-action="rerun" data-from="pack">Rebuild</button></li>`);
  if (rv?.result === "blocked") next.push(html`<li class="row"><span class="pill bad">${rv.counts.blocking}</span><span class="grow">Resolve the blocking review findings before anything goes to the client.</span><a class="btn sm" href="#/bid/${encodeURIComponent(id)}/review">Review</a></li>`);
  if (rv?.result === "ready_for_human_review" && !s.signed_off && !s.stale) next.push(html`<li class="row"><span class="pill accent">${icon("clipboard")}</span><span class="grow">Read the pack and sign off the human review checklist.</span><a class="btn sm primary" href="#/bid/${encodeURIComponent(id)}/review">Sign off</a></li>`);
  if (placeholdersOf(d)) next.push(html`<li class="row"><span class="pill warn">${placeholdersOf(d)}</span><span class="grow">Placeholders in the draft need the client's input or decision.</span><a class="btn sm" href="#/bid/${encodeURIComponent(id)}/draft">Draft</a></li>`);
  if (s.signed_off && !s.logged) next.push(html`<li class="row"><span class="pill ok">${icon("check")}</span><span class="grow">Signed off. Send the pack to the client, then log the outcome and close.</span><a class="btn sm primary" href="#/bid/${encodeURIComponent(id)}/close">Close out</a></li>`);
  return html`
    <div class="card verdict ${rec.cls}"><div class="badge">${icon(rec.icon, "xl")}</div><div class="grow">
      <div class="small muted">Recommendation</div><h2>${rec.label}</h2><p class="muted" style="margin-top:4px">${rec.line}</p>
      ${ms.go_no_go.reasons?.length ? html`<ul>${ms.go_no_go.reasons.map((r) => html`<li dir="auto">${r}</li>`)}</ul>` : ""}</div></div>
    <div class="grid-4">
      ${statCard("Requirements", ms.total, `${ms.mandatory_total} mandatory`)}
      <div class="card stat"><div class="label">Mandatory gaps</div><div class="value" style="color:${ms.mandatory_gaps ? "var(--bad)" : "var(--ok)"}">${ms.mandatory_gaps}</div><div class="foot">${ms.mandatory_gaps ? "Pack is marked NOT FOR SUBMISSION" : "None open"}</div></div>
      <div class="card stat"><div class="label">Scored points evidenced</div><div class="value">${pts !== null ? html`${pts}<small>%</small>` : "–"}</div>
        ${pts !== null ? html`<div class="meter"><span style="width:${pts}%"></span></div><div class="foot">${ms.scored_points_evidenced} of ${ms.scored_points_available} points</div>` : html`<div class="foot">No published weights</div>`}</div>
      <div class="card stat"><div class="label">Automated review</div><div class="value" style="font-size:18px;margin-top:8px">${rv ? (rv.result === "blocked" ? html`<span class="pill bad">Blocked</span>` : html`<span class="pill ok">Passed</span>`) : "–"}</div>
        ${rv ? html`<div class="foot">${plural(rv.counts.blocking, "blocker")}, ${rv.counts.advisory} advisory, ${plural(rv.counts.client_action, "client action")}</div>` : ""}</div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-head"><h2>Next steps</h2></div><div class="card-body">
        ${next.length ? html`<ul class="stack" style="list-style:none;margin:0;padding:0">${next}</ul>` : html`<p class="muted">Nothing outstanding.</p>`}</div></div>
      <div class="card"><div class="card-head"><h2>Requirements by status</h2><a class="small" href="#/bid/${encodeURIComponent(id)}/requirements">View all</a></div>
        <div class="card-body stack"><div class="dist">${bars}</div>
        <div class="legend">${STATUS_ORDER.filter((k) => ms.by_status[k]).map((k) => html`<span><i class="c-${k}"></i>${STATUS[k].label} ${ms.by_status[k]}</span>`)}</div></div></div>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-head"><h2>Data handling</h2>${tierBadge(s.tier)}</div><div class="card-body"><dl class="facts">
        <dt>Detected</dt><dd>Tier ${run.tier.detected}${run.tier.detected !== run.tier.tier ? `, raised to ${run.tier.tier}` : ""}</dd>
        <dt>Why</dt><dd>${(run.tier.reasons || []).join("; ")}</dd>
        ${run.tier.residency_mentions?.length ? html`<dt>Residency clauses</dt><dd>${run.tier.residency_mentions.join("; ")}</dd>` : ""}
        <dt>Matrix judged by</dt><dd>${run.stages.matrix?.model === "rules" ? "Deterministic rules" : run.stages.matrix?.model || "–"}</dd>
        <dt>Draft written by</dt><dd>${run.stages.draft?.model === "rules" ? "Deterministic rules" : run.stages.draft?.model || "–"}</dd>
      </dl></div></div>
      <div class="card"><div class="card-head"><h2>Activity</h2></div><div class="card-body"><dl class="facts">
        ${Object.entries(run.stages).map(([k, v]) => html`<dt>${STAGE_LABEL[k] || k}</dt><dd>${fmtWhen(v.at)}</dd>`)}
        ${run.ui?.signoff ? html`<dt>Signed off</dt><dd>${run.ui.signoff.reviewer}, ${fmtWhen(run.ui.signoff.at)}</dd>` : ""}
      </dl></div></div>
    </div>`;
}
const placeholdersOf = (d) => (d.sections?.sections || []).reduce((a, x) => a + (x.placeholders || 0), 0);

/* ---------- requirements */

function filteredRows(rows) {
  const f = app.reqFilter, q = f.q.trim().toLowerCase();
  return rows.filter((r) => (f.status === "all" || r.status === f.status) && (!f.mandatory || r.mandatory) && (!f.scored || r.scored) &&
    (f.owner === "all" || r.owner === f.owner) &&
    (!q || [r.id, r.text, r.category, r.risk_note, r.gap_action, ...(r.evidence || []).map((e) => e.library_id)].join(" ").toLowerCase().includes(q)));
}

function requirementsTab(id, d, mx, sub) {
  const rows = mx.matrix.rows;
  const f = app.reqFilter;
  const counts = Object.fromEntries(Object.keys(STATUS).map((k) => [k, rows.filter((r) => r.status === k).length]));
  const tableBody = () => {
    const list = filteredRows(rows);
    return list.length ? list.map((r) => html`<tr class="clickable" data-action="row" data-id="${r.id}" aria-selected="${String(r.id === sub)}">
      <td class="id">${r.id}</td>
      <td class="req"><div class="text" dir="auto">${r.text}</div><div class="small faint">${r.source.location}</div></td>
      <td class="small">${human(r.category)}</td>
      <td class="nowrap">${r.mandatory ? html`<span class="tag" title="Mandatory">M</span> ` : ""}${r.scored ? html`<span class="tag" title="Scored">S${r.weight ? ` ${r.weight}` : ""}</span>` : ""}</td>
      <td><span class="pill ${STATUS[r.status].cls}"><span class="dot"></span>${STATUS[r.status].label}</span></td>
      <td class="small mono">${(r.evidence || []).map((e) => e.library_id).join(", ") || html`<span class="faint">–</span>`}</td></tr>`).map(esc).join("")
      : `<tr><td colspan="6"><div class="empty"><p>No requirements match these filters.</p></div></td></tr>`;
  };
  const refresh = () => {
    $("#req-body").innerHTML = tableBody();
    $$("[data-action='status-filter']").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.status === f.status)));
    $("#req-count").textContent = `${filteredRows(rows).length} of ${rows.length}`;
  };
  on("row", (el) => { location.hash = `#/bid/${encodeURIComponent(id)}/requirements/${encodeURIComponent(el.dataset.id)}`; });
  on("status-filter", (el) => { f.status = el.dataset.status; refresh(); });
  app.handlers["req-search"] = (el) => { f.q = el.value; refresh(); };
  app.handlers["req-toggle"] = (el) => { f[el.name] = el.type === "checkbox" ? el.checked : el.value; refresh(); };

  const selected = sub ? rows.find((r) => r.id === sub) : null;
  const closeDrawer = () => { location.hash = `#/bid/${encodeURIComponent(id)}/requirements`; };
  if (selected) {
    on("close-drawer", closeDrawer);
    app.handlers.escape = closeDrawer;
    app.handlers.keydown = (e) => {
      if (["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement?.tagName)) return;
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "j" && e.key !== "k") return;
      const list = filteredRows(rows), i = list.findIndex((r) => r.id === selected.id);
      const nxt = list[i + (e.key === "ArrowDown" || e.key === "j" ? 1 : -1)];
      if (nxt) { e.preventDefault(); location.hash = `#/bid/${encodeURIComponent(id)}/requirements/${encodeURIComponent(nxt.id)}`; }
    };
    on("save-note", async () => {
      try {
        const row = await api("PATCH", runUrl(id, `/rows/${encodeURIComponent(selected.id)}`), { reviewer_notes: $("#note").value });
        Object.assign(selected, row); toast("Reviewer note saved");
      } catch (err) { toast(err.message, "bad"); }
    });
    app.afterRender = () => { $(".drawer .close")?.focus(); };
  }
  return html`<div class="card">
    <div class="toolbar">
      <input type="search" placeholder="Search requirements, ids, records" value="${f.q}" data-input="req-search" aria-label="Search requirements">
      <div class="chips" role="group" aria-label="Status">
        <button class="chip" data-action="status-filter" data-status="all" aria-pressed="${String(f.status === "all")}">All <span class="n">${rows.length}</span></button>
        ${STATUS_ORDER.filter((k) => counts[k]).map((k) => html`<button class="chip" data-action="status-filter" data-status="${k}" aria-pressed="${String(f.status === k)}">${STATUS[k].label} <span class="n">${counts[k]}</span></button>`)}
      </div>
      <label class="check small"><input type="checkbox" name="mandatory" data-change="req-toggle" ${raw(f.mandatory ? "checked" : "")}> Mandatory</label>
      <label class="check small"><input type="checkbox" name="scored" data-change="req-toggle" ${raw(f.scored ? "checked" : "")}> Scored</label>
      <select name="owner" data-change="req-toggle" aria-label="Owner" style="width:auto">
        ${[["all", "Any owner"], ["client", "Client"], ["bid_factory", "Bid Factory"], ["partner", "Partner"]].map(([v, l]) => html`<option value="${v}" ${raw(f.owner === v ? "selected" : "")}>${l}</option>`)}
      </select>
      <span class="small faint" id="req-count" style="margin-left:auto">${filteredRows(rows).length} of ${rows.length}</span>
    </div>
    <div class="table-wrap"><table class="table"><thead><tr><th>ID</th><th>Requirement</th><th>Category</th><th>Type</th><th>Status</th><th>Evidence</th></tr></thead>
    <tbody id="req-body">${raw(tableBody())}</tbody></table></div></div>
    ${selected ? drawer(selected, mx.records, d) : ""}`;
}

function drawer(r, records, d) {
  const deadline = d.run.tender.deadline;
  return html`<div class="drawer-scrim" data-action="close-drawer"></div>
  <aside class="drawer" role="dialog" aria-modal="true" aria-label="Requirement ${r.id}">
    <header><span class="mono muted">${r.id}</span><span class="pill ${STATUS[r.status].cls}"><span class="dot"></span>${STATUS[r.status].label}</span>
      ${r.mandatory ? html`<span class="tag">Mandatory</span>` : ""}${r.scored ? html`<span class="tag">Scored${r.weight ? ` · ${r.weight}` : ""}</span>` : ""}
      <button class="btn ghost sm close" style="margin-left:auto" data-action="close-drawer" aria-label="Close">${icon("x")}</button></header>
    <div class="body">
      <div class="quote" dir="auto">${r.text}</div>
      <dl class="facts">
        <dt>Source</dt><dd>${r.source.document}, ${r.source.location}</dd>
        <dt>Category</dt><dd>${human(r.category)}</dd>
        <dt>Owner</dt><dd>${r.owner === "bid_factory" ? "Bid Factory" : human(r.owner)}</dd>
        <dt>Answered in</dt><dd>${r.response_section || "–"}</dd>
        <dt>Judged by</dt><dd>${judgedBy(r.judged_by)}</dd>
      </dl>
      ${r.risk_note || r.gap_action ? html`<div class="banner ${r.status === "gap" ? "bad" : "warn"}">${icon("alert")}<div class="grow">
        ${r.risk_note ? html`<strong dir="auto">${r.risk_note}</strong>` : ""}${r.gap_action ? html`<div dir="auto">${r.gap_action}${r.gap_deadline ? html` <span class="muted">· by ${fmtDate(r.gap_deadline)}</span>` : ""}</div>` : ""}</div></div>` : ""}
      <div class="stack-sm"><div class="section-title">Evidence</div>
        ${(r.evidence || []).length ? r.evidence.map((e) => evidenceCard(e, records[e.library_id], deadline)) : html`<p class="muted small">No library record supports this requirement.</p>`}</div>
      <div class="stack-sm"><label class="section-title" for="note">Reviewer notes</label>
        <textarea id="note" rows="4" placeholder="Visible to the team in the matrix. Kept when the bid is re-checked." ${raw(d.summary.busy ? "disabled" : "")}>${r.reviewer_notes || ""}</textarea></div>
    </div>
    <footer><span class="small faint">↑ ↓ to move between requirements · Esc to close</span><button class="btn primary sm" data-action="save-note" ${raw(d.summary.busy ? 'aria-disabled="true"' : "")}>Save note</button></footer>
  </aside>`;
}

function evidenceCard(e, rec, deadline) {
  const ex = expiry(e.valid_until || rec?.valid_until, null);
  const atDeadline = (e.valid_until || rec?.valid_until) ? expiry(e.valid_until || rec.valid_until, deadline) : null;
  return html`<div class="evidence"><div class="head"><span class="mono small">${e.library_id}</span>${rec ? html`<span class="tag">${rec.type}</span><strong dir="auto">${rec.title}</strong>` : html`<span class="pill bad">Not in library</span>`}</div>
    ${rec ? html`<div class="small" dir="auto">${rec.summary}</div>` : ""}
    <div class="small muted" dir="auto">${e.relevance}</div>
    ${ex ? html`<div class="small"><span class="pill ${atDeadline && atDeadline.cls === "bad" ? "bad" : ex.cls}">${atDeadline && atDeadline.cls === "bad" ? atDeadline.text : ex.text}</span></div>` : ""}
    ${rec?.permission && rec.permission !== "public" ? html`<div class="small"><span class="pill warn">Citation: ${rec.permission === "on_request" ? "client approval needed" : "not permitted"}</span></div>` : ""}</div>`;
}

/* ---------- gaps */

function gapsTab(id, d, mx) {
  const sev = { gap: 0, client_decision: 1, partial: 2 };
  const rows = mx.matrix.rows.filter((r) => r.status in sev)
    .sort((a, b) => (b.mandatory - a.mandatory) || (sev[a.status] - sev[b.status]) || String(a.gap_deadline || "9").localeCompare(String(b.gap_deadline || "9")));
  const client = rows.filter((r) => r.owner === "client"), ours = rows.filter((r) => r.owner !== "client");
  const card = (r) => html`<div class="card card-pad stack-sm">
    <div class="row wrap"><a class="mono small" href="#/bid/${encodeURIComponent(id)}/requirements/${encodeURIComponent(r.id)}">${r.id}</a>
      <span class="pill ${STATUS[r.status].cls}"><span class="dot"></span>${STATUS[r.status].label}</span>${r.mandatory ? html`<span class="tag">Mandatory</span>` : ""}
      ${r.gap_deadline ? html`<span class="small muted" style="margin-left:auto">${icon("clock")} by ${fmtDate(r.gap_deadline)}</span>` : ""}</div>
    <strong dir="auto">${r.risk_note || r.text}</strong>
    ${r.gap_action ? html`<div dir="auto"><span class="muted">Action:</span> ${r.gap_action}</div>` : ""}
    ${r.risk_note ? html`<div class="small faint" dir="auto">${r.text}</div>` : ""}</div>`;
  const ms = d.matrix_summary, rec = REC[ms.go_no_go.recommendation];
  return html`<div class="banner ${ms.mandatory_gaps ? "bad" : "ok"}">${icon(ms.mandatory_gaps ? "alert" : "check")}<div class="grow">
      <strong>${ms.mandatory_gaps ? `${plural(ms.mandatory_gaps, "mandatory gap")} · recommendation: ${rec.label}` : "No mandatory gaps"}</strong>
      ${ms.mandatory_gaps ? "Send the gap report to the client. Each gap has an owner, an action and the date it must close by to leave time for review." : "Remaining items are partial answers or decisions that improve the score."}</div>
      <a class="btn" href="${downloadUrl(id, "gap-report.md")}">${icon("download")} Gap report</a></div>
    <div class="grid-2" style="align-items:start">
      <div class="stack"><div class="row"><h2>Client actions</h2><span class="pill">${client.length}</span></div>${client.length ? client.map(card) : html`<p class="muted">None.</p>`}</div>
      <div class="stack"><div class="row"><h2>Our actions</h2><span class="pill">${ours.length}</span></div>${ours.length ? ours.map(card) : html`<p class="muted">None.</p>`}</div>
    </div>`;
}

/* ---------- draft */

async function draftTab(id, d, mx, sub) {
  const sections = d.sections?.sections || [];
  if (!sections.length) return notYet("The draft has not been written yet.");
  const file = sections.some((x) => x.file === sub) ? sub : sections[0].file;
  const sec = sections.find((x) => x.file === file);
  const doc = await api("GET", runUrl(id, `/sections/${encodeURIComponent(file)}`));
  const edits = d.run.ui?.edits || {};
  const busy = d.summary.busy;
  const records = mx.records;

  on("draft-mode", (el) => {
    if (el.dataset.mode === "preview" && app.dirty) { doc.text = $("#editor").value; }
    app.draftMode = el.dataset.mode;
    $("#draft-pane").innerHTML = pane().s;
    $$("[data-action='draft-mode']").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === app.draftMode)));
    if (app.draftMode === "edit") $("#editor")?.focus();
  });
  app.handlers["editor-input"] = () => { app.dirty = true; $("#dirty").hidden = false; };
  on("save-section", async () => {
    const text = $("#editor") ? $("#editor").value : doc.text;
    try {
      await api("PUT", runUrl(id, `/sections/${encodeURIComponent(file)}`), { text });
      app.dirty = false; app.draftMode = "preview"; toast("Section saved. Rebuild the pack and review before sign-off."); router();
    } catch (err) { toast(err.message, "bad"); }
  });
  on("cite", (el) => {
    const rec = records[el.dataset.id];
    const ex = rec ? expiry(rec.valid_until, d.run.tender.deadline) : null;
    openPopover(el, rec ? html`<div class="row"><span class="mono small">${rec.id}</span><span class="tag">${rec.type}</span></div><strong dir="auto">${rec.title}</strong>
      <div class="muted" dir="auto">${rec.summary}</div>${ex ? html`<div><span class="pill ${ex.cls}">${ex.text}</span></div>` : ""}
      ${rec.permission && rec.permission !== "public" ? html`<div><span class="pill warn">Citation: ${rec.permission === "on_request" ? "client approval needed" : "not permitted"}</span></div>` : ""}`
      : html`<strong>${el.dataset.id}</strong><span class="pill bad">Not in the library</span>`);
  });

  const pane = () => app.draftMode === "edit"
    ? html`<div class="card-body stack"><textarea id="editor" class="editor" data-input="editor-input" spellcheck="true" aria-label="Section text (Markdown)" ${raw(busy ? "disabled" : "")}>${doc.text}</textarea>
      <p class="small muted">Markdown. Keep every factual sentence cited as <code>[LIB:ID]</code> or <code>[PRICING]</code>, or mark it <code>[CLIENT INPUT NEEDED: ...]</code>. The automated review checks it again.</p></div>`
    : html`<div class="doc">${md(doc.text)}</div>`;

  return html`
    ${d.summary.stale ? html`<div class="banner warn">${icon("edit")}<div class="grow"><strong>The draft changed after the last review</strong>Rebuild the pack and review so the Word files and checks include your edits.</div>
      <button class="btn primary" data-action="rerun" data-from="pack" ${raw(busy ? 'aria-disabled="true"' : "")}>Rebuild pack and review</button></div>` : ""}
    <div class="split">
      <nav class="card section-list" aria-label="Sections">${sections.map((x) => html`<a href="#/bid/${encodeURIComponent(id)}/draft/${encodeURIComponent(x.file)}" ${raw(x.file === file ? 'aria-current="page"' : "")}>
        <span class="row"><strong class="grow">${x.title}</strong>${edits[x.file] ? html`<span class="edited-dot" title="Edited"></span>` : ""}</span>
        <span class="meta"><span>${plural(x.rows.length, "requirement")}</span><span>${plural(x.citations.length, "record")}</span>${x.placeholders ? html`<span class="pill warn">${x.placeholders} to fill</span>` : ""}</span></a>`)}</nav>
      <div class="card">
        <div class="card-head"><div class="row"><h2>${sec.title}</h2>${edits[file] ? html`<span class="pill warn">Edited ${fmtWhen(edits[file])}</span>` : ""}<span class="pill warn" id="dirty" hidden>Unsaved</span></div>
          <div class="btn-row"><div class="segmented" role="group" aria-label="Mode">
            <button type="button" data-action="draft-mode" data-mode="preview" aria-pressed="${String(app.draftMode === "preview")}">${icon("eye")} Preview</button>
            <button type="button" data-action="draft-mode" data-mode="edit" aria-pressed="${String(app.draftMode === "edit")}" ${raw(busy ? "disabled" : "")}>${icon("edit")} Edit</button></div>
            <button class="btn primary sm" data-action="save-section" ${raw(busy ? 'aria-disabled="true"' : "")}>Save</button></div></div>
        <div class="card-body small muted row wrap" style="border-bottom:1px solid var(--border);padding-top:10px;padding-bottom:10px">
          <span class="row"><span class="cite">ID</span> cited library record</span><span class="row"><span class="cite pricing">PRICING</span> pricing sheet</span>
          <span class="row"><mark class="ph">CLIENT INPUT NEEDED</mark></span><span class="row"><mark class="ph decision">CLIENT DECISION NEEDED</mark></span></div>
        <div id="draft-pane">${pane()}</div>
      </div></div>`;
}

/* ---------- review */

function whereLink(id, d, where) {
  if (!where) return "";
  if (/^C-\d+/.test(where)) return html`<a class="where" href="#/bid/${encodeURIComponent(id)}/requirements/${encodeURIComponent(where)}">${where}</a>`;
  const file = where.split(":")[0];
  if ((d.sections?.sections || []).some((x) => x.file === file)) return html`<a class="where" href="#/bid/${encodeURIComponent(id)}/draft/${encodeURIComponent(file)}">${where}</a>`;
  return html`<span class="where">${where}</span>`;
}

function reviewTab(id, d) {
  const rv = d.review, s = d.summary;
  if (!rv) return notYet("The automated review has not run yet.");
  const groups = [["blocking", "Blocking", "bad"], ["advisory", "Advisory", "warn"], ["client_action", "Client actions", "violet"]];
  const so = app.signoff[id] || (app.signoff[id] = { checked: new Set(), reviewer: "", hours: "" });
  const checklist = app.status.checklist;
  const total = checklist.reduce((a, c) => a + c.items.length, 0);
  const signed = d.run.ui?.signoff;
  const reason = rv.result === "blocked" ? "Resolve the blocking findings first." : s.stale ? "Rebuild the pack and review to include your draft edits." : s.busy ? "The bid is being processed." : "";
  const updateBtn = () => {
    const btn = $("#signoff-btn"); if (!btn) return;
    const ready = !reason && so.checked.size === total && so.reviewer.trim();
    if (ready) btn.removeAttribute("aria-disabled"); else btn.setAttribute("aria-disabled", "true");
    $("#signoff-count").textContent = `${so.checked.size} of ${total} confirmed`;
  };
  app.handlers["check-item"] = (el) => { el.checked ? so.checked.add(el.value) : so.checked.delete(el.value); updateBtn(); };
  app.handlers["signoff-field"] = (el) => { so[el.name] = el.value; updateBtn(); };
  on("signoff", async () => {
    try {
      await api("POST", runUrl(id, "/signoff"), { reviewer: so.reviewer, hours: so.hours ? Number(so.hours) : null, checked: [...so.checked] });
      delete app.signoff[id]; toast("Signed off"); router();
    } catch (err) { toast(err.message, "bad"); }
  });
  app.afterRender = updateBtn;
  return html`
    <div class="banner ${rv.result === "blocked" ? "bad" : "ok"}">${icon(rv.result === "blocked" ? "alert" : "check", "lg")}<div class="grow">
      <strong>${rv.result === "blocked" ? `Blocked: ${plural(rv.counts.blocking, "blocking finding")}` : "Automated review passed"}</strong>
      ${rv.result === "blocked" ? "Nothing goes to the client until these are resolved, in the library or in the draft, and the bid is re-checked." : "A person still reads the pack and signs the checklist below."}</div>
      <a class="btn" href="${downloadUrl(id, "review-findings.md")}">${icon("download")} Findings</a></div>
    ${s.stale ? html`<div class="banner warn">${icon("edit")}<div class="grow"><strong>These findings are from before your draft edits</strong>Rebuild the pack and review to check the edited text.</div><button class="btn primary" data-action="rerun" data-from="pack">Rebuild</button></div>` : ""}
    <div class="grid-3">${groups.map(([k, label, cls]) => html`<div class="card stat"><div class="label">${label}</div><div class="value" style="color:var(--${cls === "violet" ? "violet" : cls})">${rv.counts[k] || 0}</div></div>`)}</div>
    ${groups.map(([k, label, cls]) => {
      const list = rv.findings.filter((f) => f.severity === k);
      if (!list.length) return "";
      return html`<div class="card"><div class="card-head"><h2>${label}</h2><span class="pill ${cls}">${list.length}</span></div>
        ${list.map((f) => html`<div class="finding"><span class="tag" title="${REVIEW_CODE[f.code] || ""}">${f.code}</span>
          <div><div class="row wrap"><strong>${REVIEW_CODE[f.code] || f.code}</strong>${whereLink(id, d, f.where)}</div><div class="muted small" dir="auto">${f.message}</div></div></div>`)}</div>`;
    })}
    <div class="card" id="signoff"><div class="card-head"><h2>Human review sign-off</h2>${signed ? html`<span class="pill ok">${icon("check")} Signed</span>` : html`<span class="small muted" id="signoff-count"></span>`}</div>
      <div class="card-body stack">
      ${signed ? html`<div class="banner ok">${icon("check")}<div class="grow"><strong>Signed off by ${signed.reviewer}</strong>${fmtWhen(signed.at)}${signed.hours ? ` · ${signed.hours} hours` : ""}. Editing the draft or re-checking clears the sign-off.</div></div>`
      : html`${reason ? html`<div class="banner warn">${icon("lock")}<div class="grow">${reason}</div></div>` : ""}
        <p class="muted">Read the pack in full, then confirm each item. During the first ten bids every section is read.</p>
        <div class="checklist">${checklist.map((sec, i) => html`<fieldset><legend>${sec.section}</legend>${sec.items.map((item, j) => html`
          <label class="check"><input type="checkbox" value="${i}-${j}" data-change="check-item" ${raw(so.checked.has(`${i}-${j}`) ? "checked" : "")} ${raw(reason ? "disabled" : "")}><span>${raw(inline(item))}</span></label>`)}</fieldset>`)}</div>
        <div class="form-grid"><label class="field">Reviewer<input type="text" name="reviewer" value="${so.reviewer}" data-input="signoff-field" autocomplete="name" ${raw(reason ? "disabled" : "")}></label>
          <label class="field">Hours spent<span class="hint">Recorded in the outcome log</span><input type="number" name="hours" min="0" step="0.5" value="${so.hours}" data-input="signoff-field" ${raw(reason ? "disabled" : "")}></label></div>
        <div><button class="btn primary" id="signoff-btn" data-action="signoff" aria-disabled="true">${icon("check")} Sign off</button></div>`}
      </div></div>`;
}

/* ---------- pack */

async function packTab(id, d) {
  if (!d.pack) return notYet("The pack has not been assembled yet.");
  const ref = d.run.tender.reference.replace(/[^A-Za-z0-9-]/g, "_");
  const nice = (name) => {
    const base = name.replace(new RegExp(`^${ref}_`), "").replace(/\.[^.]+$/, "").replace(/^\d+_/, "");
    return human(base.replace(/-/g, " "));
  };
  const checklistFile = d.pack_files.find((f) => /_00_submission-checklist\.md$/.test(f.name));
  let checklist = "";
  if (checklistFile) {
    try { checklist = await api("GET", downloadUrl(id, checklistFile.path, true), undefined, { text: true }); } catch { /* optional */ }
  }
  return html`
    <div class="banner ${d.pack.deliverable ? "ok" : "bad"}">${icon(d.pack.deliverable ? "check" : "alert", "lg")}<div class="grow">
      <strong>${d.pack.deliverable ? "Deliverable pack" : `NOT FOR SUBMISSION: ${plural(d.pack.mandatory_gaps, "mandatory gap")} open`}</strong>
      ${d.pack.deliverable ? "Send it to the client for signature after sign-off. The client submits it on the portal under its own registration." : "Every file is stamped NOT FOR SUBMISSION until the gaps close and the bid is re-checked."}</div>
      <a class="btn primary" href="${downloadUrl(id, "pack.zip")}">${icon("download")} Download all (.zip)</a></div>
    <div class="grid-2" style="align-items:start">
      <div class="card"><div class="card-head"><h2>Files</h2><span class="small muted">Built ${fmtWhen(d.pack.generated_at)}</span></div>
        <div class="card-body filelist">${d.pack_files.map((f) => html`<div class="file">${icon("file")}<span class="grow"><span class="name">${nice(f.name)}</span><span class="small faint mono fname" title="${f.name}">${f.name}</span></span>
          <span class="tag">${f.name.split(".").pop().toUpperCase()}</span><span class="small faint">${fmtBytes(f.bytes)}</span>
          <a class="btn ghost sm" href="${downloadUrl(id, f.path)}" aria-label="Download ${f.name}">${icon("download")}</a></div>`)}</div></div>
      <div class="stack">
        <div class="card"><div class="card-head"><h2>Attach at submission</h2></div><div class="card-body stack-sm">
          ${d.attach_at_submission.length ? d.attach_at_submission.map((a) => html`<div class="row">${icon("lock")}<span class="grow">${a.title}</span><span class="mono small faint">${a.id}</span></div>`)
          : html`<p class="muted small">Nothing extra. Identity documents never pass through the toolkit; the client attaches them from its own systems.</p>`}</div></div>
        <div class="banner info">${icon("shield")}<div class="grow"><strong>The client submits</strong>Bid Factory never holds portal credentials. The client signs and uploads on ${PORTALS[d.run.tender.portal] || d.run.tender.portal}.</div></div>
      </div></div>
    ${checklist ? html`<div class="card"><div class="card-head"><h2>Submission checklist</h2></div><div class="doc">${md(checklist)}</div></div>` : ""}`;
}

/* ---------- close out */

function closeTab(id, d) {
  const s = d.summary, logged = d.run.stages.log;
  const signed = d.run.ui?.signoff;
  const sel = (name, label, opts) => html`<label class="field">${label}<select name="${name}">${opts.map(([v, l]) => html`<option value="${v}">${l}</option>`)}</select></label>`;
  const num = (name, label, hint = "", value = "") => html`<label class="field">${label}${hint ? html`<span class="hint">${hint}</span>` : ""}<input type="number" name="${name}" min="0" step="any" value="${value}"></label>`;
  const yn = [["", "–"], ["yes", "Yes"], ["no", "No"]];
  on("log-outcome", async () => {
    const form = $("#outcome-form");
    const data = Object.fromEntries([...new FormData(form).entries()].filter(([, v]) => v !== ""));
    try { await api("POST", runUrl(id, "/outcome"), data); toast("Outcome logged"); router(); } catch (err) { toast(err.message, "bad"); }
  });
  on("close-bid", async () => {
    const force = $("#force")?.checked || false;
    if (!logged && !force) { toast("Log the outcome first, or confirm closing without it.", "bad"); return; }
    if (!signed && !$("#unsigned")?.checked) { toast("Confirm that this pack was not signed off.", "bad"); return; }
    const ok = await dialog({ title: "Deliver and close this bid?", body: html`The pack, draft, matrix, gap report and review are copied to <code>${app.status.delivered}/${id}</code>. The run workspace and the uploaded tender documents are then <strong>deleted from this computer</strong>. This cannot be undone.`, confirm: "Deliver and close", danger: true });
    if (!ok) return;
    try {
      const res = await api("POST", runUrl(id, "/close"), { force });
      delete app.matrixCache[id];
      toast(`Delivered to ${res.delivered_to}`); location.hash = "#/";
    } catch (err) { toast(err.message, "bad"); }
  });
  return html`<div class="grid-2" style="align-items:start">
    <div class="card"><div class="card-head"><h2>1. Log the outcome</h2>${logged ? html`<span class="pill ok">${icon("check")} ${OUTCOME_LABEL[logged.outcome] || logged.outcome}</span>` : ""}</div>
      <form class="card-body stack" id="outcome-form">
        <p class="muted small">One row per bid in <code>${app.status.outcome_log}</code>. Log again later to record the result; the row is updated, not duplicated.</p>
        <div class="form-grid">
          <label class="field span-2">Outcome<select name="outcome">${app.status.outcomes.map((o) => html`<option value="${o}" ${raw(o === (logged?.outcome || (s.recommendation === "no_go" && !s.deliverable ? "no_go" : "delivered")) ? "selected" : "")}>${OUTCOME_LABEL[o] || o}</option>`)}</select></label>
          ${num("fee_aed", "Fee (AED)")}${num("success_fee_pct", "Success fee (%)")}
          ${num("human_review_hours", "Human review hours", signed?.hours ? "From the sign-off" : "", signed?.hours ?? "")}${num("clarification_rounds", "Clarification rounds")}
          ${sel("submitted_on_time", "Submitted on time", yn)}<div></div>
          <label class="field span-2">Notes<textarea name="notes" rows="2"></textarea></label>
        </div>
        <details><summary class="small" style="cursor:pointer;font-weight:600">After the result (optional)</summary>
          <div class="form-grid" style="margin-top:12px">${sel("shortlisted", "Shortlisted", yn)}${sel("awarded", "Awarded", yn)}
            ${num("contract_value_aed", "Contract value (AED)")}${num("buyer_score_pct", "Buyer score (%)")}
            ${sel("debrief_received", "Debrief received", yn)}<label class="field">Loss reason<input type="text" name="loss_reason"></label></div></details>
        <div><button class="btn primary" data-action="log-outcome" ${raw(s.busy ? 'aria-disabled="true"' : "")}>${logged ? "Update the log" : "Save to the outcome log"}</button></div>
      </form></div>
    <div class="card"><div class="card-head"><h2>2. Deliver and close</h2></div><div class="card-body stack">
      <p>Copies the deliverables to <code>${app.status.delivered}/${id}</code>, the folder synced to the client's tenant, then deletes this bid's workspace and uploaded documents.</p>
      ${!signed ? html`<div class="banner warn">${icon("alert")}<div class="grow"><strong>Not signed off</strong>The human review gate was not completed for this pack.</div></div>
        <label class="check"><input type="checkbox" id="unsigned"><span>I understand this pack was not signed off (for example a no-go or a withdrawn bid).</span></label>` : ""}
      ${!logged ? html`<label class="check"><input type="checkbox" id="force"><span>Close without an outcome log entry.</span></label>` : ""}
      <div><button class="btn danger" data-action="close-bid" ${raw(s.busy ? 'aria-disabled="true"' : "")}>${icon("archive")} Deliver and close</button></div>
    </div></div></div>`;
}

/* ------------------------------------------------------------------ libraries */

async function librariesView() {
  renderNav("libraries");
  const libs = await api("GET", "/api/libraries");
  main().innerHTML = html`<div class="page">
    <div class="page-head"><div><h1>Libraries</h1><p class="sub">Each client's evidence: registrations, certificates, projects, people and pricing. Read from <code>${app.status.libraries}</code>.</p></div></div>
    ${libs.length ? html`<div class="grid-3">${libs.map((l) => html`<a class="card card-pad stack-sm" href="#/libraries/${encodeURIComponent(l.name)}" style="color:inherit;text-decoration:none">
      <div class="row">${icon("book", "lg")}<strong class="grow">${l.company || l.name}</strong>${icon("chevron")}</div>
      ${l.error ? html`<span class="pill bad">Invalid</span><p class="small muted">${l.error}</p>`
      : html`<p class="small muted">${l.name} · ${plural(l.records, "record")}${l.has_pricing ? " · pricing sheet" : ""}</p>
        <div class="row wrap">${Object.entries(l.types).map(([k, v]) => html`<span class="tag">${k} ${v}</span>`)}</div>
        ${l.expired || l.expiring ? html`<div class="row wrap">${l.expired ? html`<span class="pill bad">${l.expired} expired</span>` : ""}${l.expiring ? html`<span class="pill warn">${l.expiring} expiring soon</span>` : ""}</div>` : ""}`}</a>`)}</div>`
    : html`<div class="card empty">${icon("book")}<h2>No libraries yet</h2><p>A library is a folder with <code>records/*.json</code> and an optional <code>pricing.json</code>, built in the client's first week.
      Put it in <code>${app.status.libraries}</code>. The format is in <code>templates/bid-library.md</code>.</p></div>`}</div>`.s;
}

async function libraryView(name) {
  renderNav("libraries");
  const lib = await api("GET", `/api/libraries/${encodeURIComponent(name)}`);
  const f = app.libFilter;
  const types = [...new Set(lib.records.map((r) => r.type))].sort();
  const rowsHtml = () => {
    const q = f.q.toLowerCase();
    const list = lib.records.filter((r) => (f.type === "all" || r.type === f.type) && (!q || [r.id, r.title, r.summary, (r.tags || []).join(" ")].join(" ").toLowerCase().includes(q)));
    return list.map((r) => {
      const ex = expiry(r.valid_until, null);
      return html`<tr class="clickable" data-action="toggle-rec" data-id="${r.id}"><td class="id">${r.id}</td><td><span class="tag">${r.type}</span></td>
        <td><strong dir="auto">${r.title}</strong><div class="small muted rec-detail" data-for="${r.id}" hidden dir="auto">${r.summary}${r.text ? html`<br><br>${r.text}` : ""}${r.figures ? html`<br><br><span class="mono">${JSON.stringify(r.figures)}</span>` : ""}</div></td>
        <td>${ex ? html`<span class="pill ${ex.cls}">${ex.text}</span>` : html`<span class="faint">–</span>`}</td>
        <td>${r.permission && r.permission !== "public" ? html`<span class="pill warn">${r.permission === "on_request" ? "Approval needed" : "Do not cite"}</span>` : html`<span class="faint">–</span>`}</td></tr>`.s;
    }).join("") || `<tr><td colspan="5"><div class="empty"><p>No records match.</p></div></td></tr>`;
  };
  on("toggle-rec", (el) => { const det = $(`.rec-detail[data-for="${CSS.escape(el.dataset.id)}"]`); if (det) det.hidden = !det.hidden; });
  on("lib-type", (el) => { f.type = el.dataset.type; $("#lib-body").innerHTML = rowsHtml(); $$("[data-action='lib-type']").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.type === f.type))); });
  app.handlers["lib-search"] = (el) => { f.q = el.value; $("#lib-body").innerHTML = rowsHtml(); };
  const s = lib.summary;
  main().innerHTML = html`<div class="page">
    <div><div class="crumbs"><a href="#/libraries">Libraries</a>${icon("chevron")}<span>${name}</span></div>
      <div class="page-head"><div><h1>${s.company || name}</h1><p class="sub mono small">${s.path}</p></div></div></div>
    ${s.error ? html`<div class="banner bad">${icon("alert")}<div class="grow"><strong>This library cannot be loaded</strong>${s.error}</div></div>` : html`
    <div class="grid-4">${statCard("Records", s.records, "")}${statCard("Expired", s.expired, s.expired ? "Renew before citing" : "")}${statCard("Expiring within 90 days", s.expiring, "")}${statCard("Pricing sheet", s.has_pricing ? "Yes" : "No", "")}</div>
    <div class="banner info">${icon("shield")}<div class="grow">Shown as the toolkit sees it: person records are pseudonymised and contact details removed. Identity documents are never loaded${lib.attach_at_submission.length ? ` (${lib.attach_at_submission.length} listed for the client to attach at submission)` : ""}.</div></div>
    <div class="card"><div class="toolbar"><input type="search" placeholder="Search records" value="${f.q}" data-input="lib-search" aria-label="Search records">
      <div class="chips"><button class="chip" data-action="lib-type" data-type="all" aria-pressed="${String(f.type === "all")}">All</button>${types.map((t) => html`<button class="chip" data-action="lib-type" data-type="${t}" aria-pressed="${String(f.type === t)}">${t}</button>`)}</div></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>ID</th><th>Type</th><th>Record</th><th>Validity</th><th>Citation</th></tr></thead><tbody id="lib-body">${raw(rowsHtml())}</tbody></table></div></div>`}
  </div>`.s;
}

/* ------------------------------------------------------------------ settings */

async function settingsView() {
  renderNav("settings");
  app.status = await api("GET", "/api/status");
  const st = app.status, m = st.models;
  const yes = (b, t, f) => b ? html`<span class="pill ok">${icon("check")} ${t}</span>` : html`<span class="pill">${f}</span>`;
  main().innerHTML = html`<div class="page narrow">
    <div class="page-head"><div><h1>Settings</h1><p class="sub">Read-only. Change these where <code>bf ui</code> is started, then restart it.</p></div></div>
    <div class="card"><div class="card-head"><h2>Models</h2></div><div class="card-body stack">
      <dl class="facts">
        <dt>Claude (Tier A only)</dt><dd>${yes(m.anthropic_key, "API key set", "No API key")} ${m.anthropic_sdk ? "" : html`<span class="pill warn">SDK not installed</span>`} <span class="mono small">${m.anthropic_model}</span></dd>
        <dt>In-country model</dt><dd>${m.tier_b_endpoint ? html`<span class="pill ok">${icon("check")} ${m.tier_b_endpoint}</span> <span class="mono small">${m.tier_b_model}</span>` : html`<span class="pill">Not configured</span>`}</dd>
      </dl>
      <p class="small muted">Claude: set <code>ANTHROPIC_API_KEY</code> (and optionally <code>BF_MODEL</code>). In-country model: set <code>BF_TIER_B_URL</code>, <code>BF_TIER_B_MODEL</code> and <code>BF_TIER_B_KEY</code> for any OpenAI-compatible server on in-country infrastructure, such as vLLM inside the company network.
      With neither, every stage runs on deterministic rules and nothing leaves this computer.</p></div></div>
    <div class="card"><div class="card-head"><h2>Data tiers</h2></div><div class="table-wrap"><table class="table"><thead><tr><th>Tier</th><th>Material</th><th>Processed by</th></tr></thead><tbody>
      <tr><td>${tierBadge("A")}</td><td>Declared public, no personal data</td><td>Claude if configured, else the in-country model, else rules</td></tr>
      <tr><td>${tierBadge("B")}</td><td>The default: NDA, supplier login, personal data</td><td>In-country model if configured, else rules. Never Claude.</td></tr>
      <tr><td>${tierBadge("C")}</td><td>Classified</td><td>Nobody. The toolkit refuses it.</td></tr></tbody></table></div></div>
    <div class="card"><div class="card-head"><h2>Workspace</h2></div><div class="card-body"><dl class="facts">
      <dt>Workspace</dt><dd class="mono small">${st.workspace}</dd><dt>Libraries</dt><dd class="mono small">${st.libraries}</dd>
      <dt>Deliveries</dt><dd class="mono small">${st.delivered}</dd><dt>Outcome log</dt><dd class="mono small">${st.outcome_log}</dd><dt>Version</dt><dd>bf ${st.version}</dd></dl></div></div>
    <div class="card"><div class="card-head"><h2>Security</h2></div><div class="card-body stack-sm small">
      <p>${icon("lock")} The interface listens on this computer only unless it was started with <code>--host</code>. Access needs the one-time link printed at start-up; it sets a session cookie for this browser.</p>
      <p>${icon("shield")} No fonts, scripts or images load from the internet. Requests from other websites are refused.</p></div></div>
  </div>`.s;
}

router();
