"use strict";

const state = {
  pack: "eu",
  caseId: "case-northstar",
  provider: "local",
  classification: "restricted",
  snapshot: null,
  tourStep: 0,
};

const el = (id) => document.getElementById(id);
const text = (id, value) => { el(id).textContent = value; };
const create = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
};

function showToast(message) {
  const toast = el("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2600);
}

async function loadSnapshot() {
  document.body.setAttribute("aria-busy", "true");
  try {
    const params = new URLSearchParams({ pack: state.pack, case: state.caseId });
    const response = await fetch(`/api/demo?${params}`);
    if (!response.ok) throw new Error("The demonstration data could not be loaded.");
    state.snapshot = await response.json();
    render();
  } catch (error) {
    showToast(error.message);
  } finally {
    document.body.removeAttribute("aria-busy");
  }
}

function render() {
  const data = state.snapshot;
  text("metric-alerts", data.metrics.open_alerts);
  text("metric-evidence", `${data.metrics.evidence_coverage}%`);
  text("metric-audit", data.metrics.audit_integrity);
  text("metric-time", data.metrics.review_time);
  text("nav-count", data.metrics.open_alerts);
  text("case-alert", data.case.alert_id);
  text("case-customer", data.case.customer);
  text("case-account", data.case.subject_account);
  text("case-segment", data.case.segment);
  text("risk-score", data.case.risk_score);
  text("risk-label", `${data.case.risk_label} priority`);
  text("case-summary", data.case.summary);
  renderClaims(data.case.claims);
  renderAlerts(data.alerts);
  renderTransactions(data.transactions);
  renderRegulatory(data.regulatory);
  renderAudit(data.audit.events);
  drawGraph(data.graph);
  evaluatePolicy();
}

function renderClaims(claims) {
  const root = el("claims");
  root.replaceChildren();
  claims.forEach((claim, index) => {
    const row = create("article", "claim");
    row.append(create("span", "claim-number", String(index + 1)));
    const body = create("div");
    body.append(create("p", "", claim.text));
    body.append(create("small", "", "Deterministic rule result · Human review required"));
    row.append(body);
    row.append(create("span", "evidence-chip", claim.evidence_ids[0]));
    root.append(row);
  });
}

function renderAlerts(alerts) {
  text("queue-count", alerts.length);
  const root = el("alert-list");
  root.replaceChildren();
  alerts.forEach((alert) => {
    const button = create("button", `alert-item${alert.selected ? " selected" : ""}`);
    button.type = "button";
    button.setAttribute("aria-pressed", alert.selected ? "true" : "false");
    button.append(create("strong", "", alert.customer));
    const risk = create("span", "alert-risk", String(alert.risk_score));
    risk.append(create("small", "", alert.risk_label));
    button.append(risk);
    button.append(create("span", "", `${alert.alert_id} · ${alert.indicator_count} indicators`));
    button.addEventListener("click", () => {
      state.caseId = alert.case_id;
      loadSnapshot();
      document.getElementById("investigation").scrollIntoView({ behavior: "smooth" });
    });
    root.append(button);
  });
}

function renderTransactions(transactions) {
  const root = el("transaction-body");
  root.replaceChildren();
  transactions.forEach((transaction) => {
    const row = create("tr");
    row.append(create("td", "", transaction.transaction_id));
    row.append(create("td", "", new Date(transaction.occurred_at).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })));
    const route = create("td", "route");
    route.append(create("b", "", transaction.originator_country));
    route.append(document.createTextNode(" → "));
    route.append(create("b", "", transaction.beneficiary_country));
    row.append(route);
    row.append(create("td", "", transaction.channel));
    row.append(create("td", "", transaction.display_amount));
    root.append(row);
  });
}

function renderRegulatory(pack) {
  text("pack-name", pack.name);
  text("pack-details", `Pack ${pack.version} · Reviewed ${pack.reviewed_on} · ${pack.authorities.join(", ")}`);
  text("pack-disclaimer", pack.disclaimer);
  const root = el("pack-topics");
  root.replaceChildren(...pack.review_topics.map((topic) => create("span", "", topic)));
}

function renderAudit(events) {
  const root = el("audit-list");
  root.replaceChildren();
  events.slice(-5).reverse().forEach((event) => {
    const item = create("li");
    item.append(create("strong", "", event.event_type.replaceAll(".", " · ")));
    item.append(create("span", "", `${event.actor} · sequence ${event.sequence} · `));
    item.append(create("code", "", event.hash));
    root.append(item);
  });
}

function drawGraph(graph) {
  const canvas = el("graph-canvas");
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(box.width * ratio));
  canvas.height = Math.max(1, Math.round(box.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const width = box.width;
  const height = box.height;
  ctx.clearRect(0, 0, width, height);
  const subject = graph.nodes.find((node) => node.kind === "subject");
  const related = graph.nodes.filter((node) => node.kind !== "subject");
  const points = new Map([[subject.id, { x: width * .5, y: height * .5, node: subject }]]);
  related.forEach((node, index) => {
    const angle = (-Math.PI / 2) + (Math.PI * 2 * index / Math.max(related.length, 1));
    points.set(node.id, {
      x: width * .5 + Math.cos(angle) * Math.min(width * .34, 180),
      y: height * .5 + Math.sin(angle) * Math.min(height * .34, 78),
      node,
    });
  });
  ctx.lineWidth = 1.3;
  ctx.font = "9px ui-sans-serif, sans-serif";
  graph.edges.forEach((edge) => {
    const from = points.get(edge.source);
    const to = points.get(edge.target);
    if (!from || !to) return;
    ctx.strokeStyle = "#b7c9c7";
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    const labelWidth = ctx.measureText(edge.label).width + 10;
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.fillRect(midX - labelWidth / 2, midY - 8, labelWidth, 15);
    ctx.fillStyle = "#667785";
    ctx.textAlign = "center";
    ctx.fillText(edge.label, midX, midY + 3);
  });
  points.forEach((point) => {
    const isSubject = point.node.kind === "subject";
    ctx.beginPath();
    ctx.arc(point.x, point.y, isSubject ? 24 : 18, 0, Math.PI * 2);
    ctx.fillStyle = isSubject ? "#167b75" : "#ffffff";
    ctx.fill();
    ctx.lineWidth = isSubject ? 0 : 2;
    ctx.strokeStyle = "#90aaa9";
    if (!isSubject) ctx.stroke();
    ctx.fillStyle = isSubject ? "#ffffff" : "#294651";
    ctx.font = `${isSubject ? "700" : "650"} ${isSubject ? 10 : 9}px ui-sans-serif, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(point.node.label, point.x, point.y + 3);
  });
  el("graph-fallback").textContent = graph.edges.map((edge) => `${edge.source} sent ${edge.label} to ${edge.target}`).join(". ");
}

async function evaluatePolicy() {
  const result = el("policy-result");
  result.className = "policy-result checking";
  result.textContent = "Checking policy…";
  try {
    const params = new URLSearchParams({ provider: state.provider, classification: state.classification });
    const response = await fetch(`/api/policy?${params}`);
    const decision = await response.json();
    result.className = `policy-result ${decision.allowed ? "allowed" : "blocked"}`;
    result.textContent = `${decision.allowed ? "Allowed" : "Blocked"} · ${decision.reason}`;
  } catch {
    result.className = "policy-result blocked";
    result.textContent = "Policy check unavailable. No provider was contacted.";
  }
}

const tour = [
  { target: "alert-queue", title: "Alert triage", copy: "Choose a synthetic alert to rebuild the investigation with traceable source activity." },
  { target: "investigation", title: "Evidence-first explanation", copy: "Every claim is generated from deterministic findings and linked to a stable evidence identifier." },
  { target: "relationships", title: "Network context", copy: "The relationship view maps the subject, counterparties and transaction paths in scope." },
  { target: "controls", title: "Governed AI routing", copy: "Try Online API with Restricted data to see TraceAML block the route before any provider is contacted." },
];

function showTourStep() {
  const step = tour[state.tourStep];
  text("tour-step", `${state.tourStep + 1} of ${tour.length}`);
  text("tour-title", step.title);
  text("tour-copy", step.copy);
  text("tour-next", state.tourStep === tour.length - 1 ? "Finish" : "Next");
  document.getElementById(step.target).scrollIntoView({ behavior: "smooth", block: "center" });
}

el("pack-select").addEventListener("change", (event) => { state.pack = event.target.value; loadSnapshot(); });
document.querySelectorAll("[data-provider]").forEach((button) => button.addEventListener("click", () => {
  state.provider = button.dataset.provider;
  document.querySelectorAll("[data-provider]").forEach((item) => item.classList.toggle("selected", item === button));
  evaluatePolicy();
}));
el("classification-select").addEventListener("change", (event) => { state.classification = event.target.value; evaluatePolicy(); });
el("copy-report").addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.snapshot.case.report_id);
  showToast("Report ID copied to clipboard.");
});
el("export-button").addEventListener("click", () => showToast("Evidence manifest prepared in memory. No customer data leaves this device."));
el("mobile-menu").addEventListener("click", () => document.querySelector(".sidebar").classList.toggle("open"));
document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => document.querySelector(".sidebar").classList.remove("open")));
el("tour-button").addEventListener("click", () => { state.tourStep = 0; el("tour-coach").hidden = false; showTourStep(); });
el("tour-exit").addEventListener("click", () => { el("tour-coach").hidden = true; });
el("tour-next").addEventListener("click", () => {
  if (state.tourStep === tour.length - 1) { el("tour-coach").hidden = true; showToast("Tour complete. You can now explore each alert."); return; }
  state.tourStep += 1;
  showTourStep();
});
window.addEventListener("resize", () => { if (state.snapshot) drawGraph(state.snapshot.graph); });

loadSnapshot();
