// interventions.js — Table filtrable des interventions à problèmes (base complète)

let currentPage = 1;
let activeController = null;

const BADGE_CLASS = {
  "Manquée": "badge-manquee",
  "Badgeage partiel": "badge-partiel",
  "Trop courte": "badge-courte",
  "Trop longue": "badge-longue",
};

function moisLabel(m) {
  const noms = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  const [y, mo] = m.split("-");
  return `${noms[parseInt(mo,10)-1]} ${y}`;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function getFilters() {
  return {
    intervenant: document.getElementById("f-intervenant").value,
    mois: document.getElementById("f-mois").value,
    type_probleme: document.getElementById("f-type").value,
    date_debut: document.getElementById("f-debut").value,
    date_fin: document.getElementById("f-fin").value,
  };
}

function buildQuery(filters, extra = {}) {
  const p = new URLSearchParams({ ...filters, ...extra });
  [...p.keys()].forEach(k => { if (!p.get(k)) p.delete(k); });
  return p.toString();
}

async function init() {
  // Remplir les dropdowns
  const [intervenants, mois] = await Promise.all([
    (await fetch("/api/intervenants")).json(),
    (await fetch("/api/mois")).json(),
  ]);
  const selI = document.getElementById("f-intervenant");
  intervenants.forEach(n => selI.add(new Option(n, n)));
  const selM = document.getElementById("f-mois");
  mois.forEach(m => selM.add(new Option(moisLabel(m), m)));

  ["f-intervenant","f-mois","f-type","f-debut","f-fin"].forEach(id =>
    document.getElementById(id).addEventListener("change", onFilterChange));
  document.getElementById("btn-reset").addEventListener("click", resetFilters);
  document.getElementById("btn-export").addEventListener("click", exportCSV);

  refreshAll();
}

function onFilterChange() { currentPage = 1; refreshAll(); }

function resetFilters() {
  ["f-intervenant","f-mois","f-type","f-debut","f-fin"].forEach(id =>
    document.getElementById(id).value = "");
  currentPage = 1;
  refreshAll();
}

async function refreshAll() {
  if (activeController) activeController.abort();
  activeController = new AbortController();
  const signal = activeController.signal;
  const filters = getFilters();
  const page = currentPage;

  showLoading(true);
  try {
    await Promise.all([refreshStats(filters, signal), refreshTable(filters, page, signal)]);
  } catch (e) {
    if (e.name !== "AbortError") console.error(e);
  } finally {
    showLoading(false);
  }
}

async function refreshStats(filters, signal) {
  const d = await (await fetch(`/api/stats?${buildQuery(filters)}`, { signal })).json();
  document.getElementById("kpi-total").textContent = d.total;
  document.getElementById("kpi-manq").textContent = d.manquees.count;
  document.getElementById("kpi-manq-pct").textContent = `${d.manquees.pct}%`;
  document.getElementById("kpi-part").textContent = d.partiels.count;
  document.getElementById("kpi-part-pct").textContent = `${d.partiels.pct}%`;
  document.getElementById("kpi-duree").textContent = d.courtes_longues.count;
  document.getElementById("kpi-duree-pct").textContent = `${d.courtes_longues.pct}%`;
}

async function refreshTable(filters, page, signal) {
  const d = await (await fetch(`/api/interventions?${buildQuery(filters, { page })}`, { signal })).json();
  document.getElementById("table-count").textContent =
    d.total === 0 ? "Aucune intervention" : `${d.total} intervention${d.total>1?"s":""}`;
  renderTable(d.rows);
  renderPagination(d.page, d.total_pages);
}

function renderTable(rows) {
  const tbody = document.getElementById("table-body");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Aucune intervention pour ces critères.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.date_prevue}</td><td>${r.intervenant}</td><td>${r.client}</td>
      <td><span class="badge ${BADGE_CLASS[r.type_probleme]||""}">${r.type_probleme}</span></td>
      <td>${r.timing}</td><td>${r.diff_minutes}</td>
      <td>${r.debut_reel}</td><td>${r.fin_reelle}</td>
      <td>
        <textarea class="commentaire-input" data-id="${r.id}" rows="1"
          style="width:160px;resize:vertical;font-size:12px;"
          placeholder="Note interne…">${escapeHtml(r.commentaire)}</textarea>
        <label style="display:flex;align-items:center;gap:4px;font-size:11px;margin-top:2px;white-space:nowrap;">
          <input type="checkbox" class="exclu-checkbox" data-id="${r.id}" ${r.exclu_relance ? "checked" : ""} />
          Exclure des relances
        </label>
      </td>
      <td><button class="btn-link danger" onclick="deleteInterv(${r.id})" title="Supprimer">✕</button></td>
    </tr>`).join("");

  tbody.querySelectorAll(".commentaire-input").forEach(el =>
    el.addEventListener("blur", () => saveCommentaire(el.dataset.id)));
  tbody.querySelectorAll(".exclu-checkbox").forEach(el =>
    el.addEventListener("change", () => saveCommentaire(el.dataset.id)));
}

async function saveCommentaire(id) {
  const commentaire = document.querySelector(`.commentaire-input[data-id="${id}"]`).value;
  const exclu_relance = document.querySelector(`.exclu-checkbox[data-id="${id}"]`).checked;
  await fetch("/api/commentaire_anomalie", {
    method: "POST", headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ id: parseInt(id, 10), commentaire, exclu_relance })
  });
}

async function deleteInterv(id) {
  if (!confirm("Supprimer cette intervention ?")) return;
  showLoading(true);
  try {
    await fetch("/api/delete_intervention", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ id })
    });
    refreshAll();
  } finally { showLoading(false); }
}

function renderPagination(page, total) {
  const el = document.getElementById("pagination");
  if (total <= 1) { el.innerHTML = ""; return; }
  const nums = buildPageNumbers(page, total);
  el.innerHTML = `
    <button class="page-btn" ${page<=1?"disabled":""} onclick="goPage(${page-1})">‹</button>
    ${nums.map(p => p==="…"
      ? `<span class="page-info">…</span>`
      : `<button class="page-btn ${p===page?"active":""}" onclick="goPage(${p})">${p}</button>`).join("")}
    <button class="page-btn" ${page>=total?"disabled":""} onclick="goPage(${page+1})">›</button>`;
}

function buildPageNumbers(cur, total) {
  if (total <= 7) return Array.from({length: total}, (_, i) => i+1);
  const s = new Set([1, total, cur, cur-1, cur+1].filter(p => p>=1 && p<=total));
  const sorted = [...s].sort((a,b)=>a-b);
  const out = [];
  sorted.forEach((p,i) => { if (i>0 && p-sorted[i-1]>1) out.push("…"); out.push(p); });
  return out;
}

function goPage(p) { currentPage = p; refreshAll(); }

function exportCSV() {
  window.location = `/api/export?${buildQuery(getFilters())}`;
}

init();
