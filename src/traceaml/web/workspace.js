"use strict";
let token = "", selected = null, role = "viewer";
const el = id => document.getElementById(id);
function message(text) { el("message").textContent = text; }
async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: {Authorization: `Bearer ${token}`, ...(body ? {"Content-Type": "application/json"} : {})}, ...(body ? {body: JSON.stringify(body)} : {})});
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if (response.status === 401) signout();
    throw new Error(typeof error.detail === "string" ? error.detail : `Request failed (${response.status}); check the input and reload the case.`);
  }
  return response;
}
function guarded(fn) { return async event => { event?.preventDefault(); try { await fn(); } catch (error) { message(error.message); } }; }
function signout() { token = ""; selected = null; el("token").value = ""; el("workspace").hidden = true; el("login").hidden = false; el("logout").hidden = true; el("cases").replaceChildren(); el("evidence").textContent = ""; el("notes").replaceChildren(); el("case-title").textContent = ""; el("note").value = ""; el("assignee").value = ""; el("disposition").value = ""; el("detail").hidden = true; }
async function refresh() {
  const result = await (await api("/v1/cases?limit=100")).json();
  el("cases").replaceChildren();
  for (const item of result.items) {
    const li = document.createElement("li"), button = document.createElement("button");
    button.textContent = `${item.title} · ${item.status}`;
    button.onclick = guarded(() => show(item.case_id)); li.append(button); el("cases").append(li);
  }
}
async function show(id) {
  selected = await (await api(`/v1/cases/${encodeURIComponent(id)}`)).json();
  const evidence = await (await api(`/v1/cases/${encodeURIComponent(id)}/evidence`)).json();
  el("detail").hidden = false;
  el("case-title").textContent = selected.title;
  el("summary").textContent = `Status: ${selected.status} · Revision ${selected.revision} · ${selected.updated_at}`;
  el("synthetic").textContent = selected.attributes.fixture === "synthetic" ? "SYNTHETIC DEMO DATA — no real customers or transactions" : "";
  el("status").value = selected.status; el("assignee").value = selected.assignee || "";
  el("disposition").value = selected.attributes.disposition || "";
  el("evidence").textContent = JSON.stringify(evidence, null, 2);
  el("notes").replaceChildren();
  for (const note of selected.attributes.notes || []) { const li = document.createElement("li"); li.textContent = `${note.author} (${note.created_at}): ${note.text}`; el("notes").append(li); }
  const readonly = role === "viewer" || selected.status === "closed";
  for (const id of ["save", "add-note", "status", "assignee", "disposition", "note", "investigate"]) el(id).disabled = readonly;
}
el("login-form").onsubmit = guarded(async () => { token = el("token").value.trim(); el("token").value = ""; const me = await (await api("/v1/me")).json(); role = me.role; el("identity").textContent = `${me.subject} · Tenant ${me.tenant_id} · ${me.role}`; el("login").hidden = true; el("workspace").hidden = false; el("logout").hidden = false; el("create").hidden = role === "viewer"; el("import-button").disabled = role === "viewer"; message("Signed in. Synthetic data is labelled in each demo case."); await refresh(); });
el("logout").onclick = signout;
el("refresh").onclick = guarded(refresh);
el("create-form").onsubmit = guarded(async () => { const item = await (await api("/v1/cases", "POST", {title: el("title").value, subject_account: el("subject-account").value || null})).json(); el("title").value = ""; await refresh(); await show(item.case_id); });
el("update-form").onsubmit = guarded(async () => { if (!selected) return; await api(`/v1/cases/${selected.case_id}`, "PATCH", {revision: selected.revision, status: el("status").value, assignee: el("assignee").value || null, disposition: el("disposition").value}); await show(selected.case_id); await refresh(); message("Case updated and audited."); });
el("note-form").onsubmit = guarded(async () => { if (!selected) return; await api(`/v1/cases/${selected.case_id}/notes`, "POST", {revision: selected.revision, text: el("note").value}); el("note").value = ""; await show(selected.case_id); message("Note saved and audited."); });
el("export").onclick = guarded(async () => { if (!selected) return; const response = await api(`/v1/cases/${selected.case_id}/export`, "POST"); const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = "case-export.taenc"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); message("Encrypted export downloaded. Use the offline decrypt-export command."); });
el("audit").onclick = guarded(async () => { const result = await (await api("/v1/audit/verify")).json(); message(result.valid ? "Audit chain verified." : "Audit integrity failure — stop processing and contact the administrator."); });
el("import-button").onclick = guarded(async () => { const file = el("import").files[0]; if (!file) throw new Error("Choose a JSON file."); if (file.size > 1048576) throw new Error("Maximum import size is 1 MiB."); const response = await api("/v1/imports", "POST", JSON.parse(await file.text())); const result = await response.json(); message(`${result.accepted} transactions imported and audited.`); });

el("investigate").onclick = guarded(async () => { if (!selected) return; await api(`/v1/cases/${selected.case_id}/investigate`, "POST", {revision: selected.revision, pack_id: selected.jurisdiction_packs[0] || "eu"}); await show(selected.case_id); message("Investigation recorded with source-linked evidence."); });
