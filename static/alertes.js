async function init(){
  showLoading(true);
  try {
    const d = await (await fetch("/api/recidivistes")).json();
    render(d.recidivistes);
  } finally { showLoading(false); }
}

function escapeHtml(s){
  return (s||"").toString()
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

function render(data){
  document.getElementById("count").textContent =
    `${data.length} intervenant${data.length>1?"s":""} en alerte`;

  const tbody = document.getElementById("table-body");
  if (!data.length){
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Aucun intervenant en récidive actuellement.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map((d, i) => `<tr>
    <td><strong>🔴 ${d.intervenant}</strong></td>
    <td>${d.streak} mois</td>
    <td><span class="taux-badge taux-high">${d.taux_dernier_mois}%</span></td>
    <td>${d.taux_global}%</td>
    <td>${d.total_global}</td>
    <td>${d.email || "—"}</td>
    <td><button class="btn-link" data-idx="${i}" data-nom="${escapeHtml(d.intervenant)}">Voir l'historique</button></td>
  </tr>
  <tr class="relances-row" id="relances-${i}" style="display:none;">
    <td colspan="7"><div class="relances-panel" id="relances-panel-${i}">Chargement…</div></td>
  </tr>`).join("");

  tbody.querySelectorAll(".btn-link").forEach(btn => {
    btn.onclick = () => toggleHistorique(btn.dataset.idx, btn.dataset.nom, btn);
  });
}

async function toggleHistorique(idx, nom, btn){
  const row = document.getElementById(`relances-${idx}`);
  const panel = document.getElementById(`relances-panel-${idx}`);
  const visible = row.style.display !== "none";
  if (visible){
    row.style.display = "none";
    btn.textContent = "Voir l'historique";
    return;
  }
  row.style.display = "";
  btn.textContent = "Masquer l'historique";
  if (panel.dataset.loaded) return;
  const d = await (await fetch(`/api/historique_relances?intervenant=${encodeURIComponent(nom)}`)).json();
  renderHistorique(panel, nom, d.historique);
  panel.dataset.loaded = "1";
}

function renderHistorique(panel, nom, historique){
  if (!historique.length){
    panel.innerHTML = `<p class="empty-state">Aucune relance envoyée pour le moment.</p>`;
    return;
  }
  panel.innerHTML = `
    <table class="mini-table">
      <thead><tr>
        <th>Mois</th><th>Relances envoyées</th><th>Dernière relance</th>
        <th>Réponse reçue</th><th>Commentaire</th>
      </tr></thead>
      <tbody>
        ${historique.map(h => `<tr>
          <td>${h.mois}</td>
          <td>${h.nb_relances}</td>
          <td>${h.derniere_relance || "—"}</td>
          <td><input type="checkbox" class="chk-reponse" data-mois="${h.mois}" ${h.reponse_recue ? "checked" : ""}></td>
          <td><input type="text" class="txt-commentaire" data-mois="${h.mois}" value="${escapeHtml(h.commentaire)}" placeholder="Ex. a justifié par SMS le..."></td>
        </tr>`).join("")}
      </tbody>
    </table>`;

  panel.querySelectorAll(".chk-reponse").forEach(chk => {
    chk.onchange = () => saveRelanceReponse(nom, panel, chk.dataset.mois);
  });
  panel.querySelectorAll(".txt-commentaire").forEach(txt => {
    txt.onblur = () => saveRelanceReponse(nom, panel, txt.dataset.mois);
  });
}

function saveRelanceReponse(nom, panel, mois){
  const chk = panel.querySelector(`.chk-reponse[data-mois="${mois}"]`);
  const txt = panel.querySelector(`.txt-commentaire[data-mois="${mois}"]`);
  fetch("/api/relance_reponse", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      intervenant: nom,
      mois: mois,
      reponse_recue: chk.checked,
      commentaire: txt.value,
    }),
  });
}

init();
