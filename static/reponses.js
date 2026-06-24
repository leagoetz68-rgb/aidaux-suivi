// reponses.js — Liste des réponses au questionnaire de badgeage

async function load(){
  showLoading(true);
  try {
    const data = await (await fetch("/api/reponses")).json();
    document.getElementById("count").textContent =
      `${data.length} réponse${data.length>1?"s":""}`;

    const tbody = document.getElementById("table-body");
    if (!data.length){ tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Aucune réponse pour le moment.</td></tr>`; return; }

    tbody.innerHTML = data.map(r => `<tr>
      <td>${r.repondu_at}</td>
      <td><strong>${r.intervenant}</strong></td>
      <td>${r.raison}</td>
      <td>${r.commentaire || ""}</td>
    </tr>`).join("");
  } finally { showLoading(false); }
}

load();
