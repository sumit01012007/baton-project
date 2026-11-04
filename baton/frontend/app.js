"use strict";
// Frontend only renders. Status, redaction and permissions are all decided by the backend.
const LV = ["Public", "Team", "Confidential"], ROLES = ["Intern", "Engineer", "Manager"];
const KEY = "demo-reviewer"; // demo only: a real deployment uses SSO/OAuth sessions
const $ = id => document.getElementById(id);
const esc = t => String(t).replace(/[&<>"]/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
const LAB = {verified:"Verified", uncertain:"Uncertain · single weak source", conflict:"Conflicting sources", blocked:"Blocked · quote not found in source", missing:"Missing evidence"};
let S = {tab:"review", role:"Engineer", d:null, h:null, open:null, edit:null, msg:""};

async function api(path, opt = {}) {
  const r = await fetch("/api" + path, {...opt, headers: {"X-Reviewer-Key": KEY, ...(opt.json ? {"Content-Type":"application/json"} : {}), ...(opt.headers||{})}, body: opt.json ? JSON.stringify(opt.json) : opt.body});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { S.msg = j.detail || r.statusText; throw new Error(S.msg); }
  S.msg = ""; return j;
}
async function load() {
  try { S.d = await api("/state"); S.h = S.tab === "handover" ? await api("/handover?role=" + S.role) : null; } catch (e) {}
  render();
}
const cites = (c, role) => (c.src || []).map(([s, q]) => `<button class="cite" data-a="src" data-s="${s}" data-q="${encodeURIComponent(q)}" data-r="${role}">${s} ${esc((S.d.sources.find(x => x.id === s) || {}).name || "")}</button>`).join(" ");
function card(c, rv) {
  const edit = S.edit === c.id;
  let h = `<div class="card"><div class="row"><span class="chip">${c.type}</span>${c.date ? `<span class="chip">${c.date}</span>` : ""}<span class="chip ${c.status}">${LAB[c.status]}</span>${c.h ? '<span class="chip">Human-authored</span>' : ""}<span class="chip">${LV[c.lvl]}</span>${!rv && c.r !== "pending" ? `<span class="chip ${c.r === "approved" ? "verified" : "blocked"}">${c.r}</span>` : ""}</div>`;
  h += edit ? `<textarea id="ed" rows="3">${esc(c.text)}</textarea><div class="row" style="margin-top:6px"><button class="on" data-a="save" data-i="${c.id}">Save correction</button><button data-a="cancel">Cancel</button></div>` : `<p style="margin:8px 0">${esc(c.text)}</p>`;
  h += `<div class="row">${c.src.length ? cites(c, rv ? S.role : "Reviewer") : '<span class="mut">No supporting source found.</span>'}</div>`;
  if (!rv && !edit) { const bad = ["blocked", "conflict", "missing"].includes(c.status);
    h += `<div class="row" style="margin-top:8px"><button class="ok" data-a="ap" data-i="${c.id}" ${bad ? "disabled" : ""}>Approve</button><button data-a="ed" data-i="${c.id}">Edit</button><button class="no" data-a="rj" data-i="${c.id}">Reject</button>${bad ? `<span class="mut">${c.status === "blocked" ? "Quote not found in source: reject or edit." : "Edit to resolve first."}</span>` : ""}</div>`; }
  return h + "</div>";
}
function review() {
  const d = S.d, n = d.claims.length, done = d.claims.filter(c => c.r !== "pending").length, attn = d.claims.filter(c => c.r === "pending" && ["conflict","missing","blocked"].includes(c.status)).length;
  return `<div class="card"><b>Handover readiness</b> <span class="mut">${done}/${n} reviewed · ${attn} need attention · AI: ${d.ai_mode} · storage: ${d.storage}</span><div class="bar" style="margin:8px 0"><i style="width:${Math.round(done/n*100)}%"></i></div>
  <div class="row"><button class="on" data-a="pub" ${done < n || d.published ? "disabled" : ""}>${d.published ? "Published ✓" : "Approve & publish handover"}</button><button data-a="ext">${d.ai_mode === "live" ? "Re-extract with Claude" : "Re-run extraction (offline demo)"}</button><button data-a="reset">Reset demo</button></div></div>
  <div class="wd">Reviewing as the departing member / approver. The backend re-checks every cited quote against its source; nothing is shared until each claim is approved, edited or rejected.</div>`
  + d.claims.map(c => card(c, false)).join("") + `<h2>Version history</h2><div class="card mut">${d.log.map(esc).join("<br>")}</div>`;
}
function handover() {
  let h = `<div class="roles">${ROLES.map(r => `<button class="${r === S.role ? "on" : ""}" data-a="role" data-r="${r}">${r}</button>`).join("")}</div>`;
  const o = S.h; if (!o || !o.published) return h + `<div class="card">No approved handover has been published yet.</div>`;
  h += `<div class="card"><b>Handover v${o.version}</b> <span class="mut">${o.visible.length} items visible to you</span></div>`;
  if (o.withheld) h += `<div class="wd">🔒 ${o.withheld} item${o.withheld > 1 ? "s were" : " was"} withheld above your clearance. The server removed ${o.withheld > 1 ? "them" : "it"} before sending, so ${o.withheld > 1 ? "they are" : "it is"} not hidden by the interface.</div>`;
  h += "<h2>5-day continuation plan</h2>" + o.plan.map(([t, l]) => `<div class="card"><b>${t}</b>${l.length ? l.map(c => `<div style="margin-top:6px">• ${esc(c.text)} ${cites(c, S.role)}</div>`).join("") : '<div class="mut">Nothing in your view.</div>'}</div>`).join("");
  h += "<h2>Timeline</h2>" + (o.timeline.map(c => `<div class="card"><span class="chip">${c.date}</span> ${esc(c.text)}</div>`).join("") || '<div class="mut">No dated items.</div>');
  h += "<h2>Decisions & context</h2>" + o.context.map(c => card(c, true)).join("");
  return h + `<div class="card"><button class="on" data-a="ack" ${o.acks[S.role] ? "disabled" : ""}>${o.acks[S.role] ? "Receipt acknowledged ✓" : "Acknowledge receipt"}</button> <span class="mut">${Object.keys(o.acks).length} of 3 roles acknowledged</span></div>`;
}
function sources() {
  return `<div class="wd">Import a text/Markdown/CSV file you are authorised to share and set its sensitivity. Then re-run extraction on the Review tab.</div>
  <div class="card row"><input type="file" id="f"><select id="lv"><option value="0">Public</option><option value="1" selected>Team</option><option value="2">Confidential</option></select><button class="on" data-a="up">Import</button></div>`
  + S.d.sources.map(s => `<div class="card"><div class="row"><b>${s.id}</b> ${esc(s.name)} <span class="chip">${s.kind}</span><span class="chip">${LV[s.lvl]}</span></div></div>`).join("");
}
function render() {
  $("tabs").innerHTML = [["review","Review (leaver)"],["handover","Handover (incoming)"],["src","Sources"]].map(([k, l]) => `<button class="${S.tab === k ? "on" : ""}" data-a="tab" data-t="${k}">${l}</button>`).join("");
  $("app").innerHTML = (S.msg ? `<div class="wd" style="border-color:var(--cf);color:var(--cf)">${esc(S.msg)}</div>` : "") + (!S.d ? "<p>Loading… is the backend running?</p>" : S.tab === "review" ? review() : S.tab === "handover" ? handover() : sources());
  const o = S.open;
  $("dr").innerHTML = o ? `<div class="drawer"><div class="row" style="justify-content:space-between"><b>${o.s} · ${esc(o.name)}</b><button data-a="x">Close</button></div><p class="mut">Highlighted text is the cited evidence.</p><pre>${hl(o.text, o.q)}</pre></div>` : "";
}
function hl(t, q) { const i = t.indexOf(q); return i < 0 ? esc(t) + "\n\n⚠ Quote not found in this source." : esc(t.slice(0, i)) + "<mark>" + esc(q) + "</mark>" + esc(t.slice(i + q.length)); }
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-a]"); if (!b) return; const a = b.dataset.a, i = b.dataset.i;
  try {
    if (a === "tab") { S.tab = b.dataset.t; S.open = null; await load(); return; }
    if (a === "role") { S.role = b.dataset.r; S.open = null; await load(); return; }
    if (a === "src") { const s = await api(`/source/${b.dataset.s}?role=${b.dataset.r}`); S.open = {s: s.id, name: s.name, text: s.text, q: decodeURIComponent(b.dataset.q)}; render(); return; }
    if (a === "x") S.open = null;
    else if (a === "ap") await api("/claims/" + i, {method:"PATCH", json:{action:"approve"}});
    else if (a === "rj") await api("/claims/" + i, {method:"PATCH", json:{action:"reject"}});
    else if (a === "ed") S.edit = +i; else if (a === "cancel") S.edit = null;
    else if (a === "save") { await api("/claims/" + i, {method:"PATCH", json:{action:"edit", text:$("ed").value}}); S.edit = null; }
    else if (a === "pub") await api("/publish", {method:"POST"});
    else if (a === "ext") { b.textContent = "Extracting…"; await api("/extract", {method:"POST"}); }
    else if (a === "reset") await api("/reset", {method:"POST"});
    else if (a === "ack") await api("/ack?role=" + S.role, {method:"POST"});
    else if (a === "up") { const f = $("f").files[0]; if (!f) return; const fd = new FormData(); fd.append("file", f); fd.append("lvl", $("lv").value); await api("/sources", {method:"POST", body:fd}); }
  } catch (err) {}
  await load();
});
load();
