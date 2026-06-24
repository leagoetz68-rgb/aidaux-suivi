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

document.getElementById("btn-envoyer").addEventListener("click", async () => {
  const btn = document.getElementById("btn-envoyer");
  const resultatDiv = document.getElementById("envoi-resultat");
  btn.disabled = true;
  resultatDiv.textContent = "Envoi en cours…";
  try {
    const data = await (await fetch("/api/send_reminders", {method:"POST"})).json();
    if (!data.results.length){
      resultatDiv.textContent = "Aucun rappel à envoyer pour le moment.";
    } else {
      resultatDiv.innerHTML = data.results.map(r =>
        r.error ? `❌ ${r.intervenant} : ${r.error}` : `✅ ${r.intervenant} (${r.email}) : ${r.nb} intervention(s)`
      ).join("<br>");
    }
  } catch (e) {
    resultatDiv.textContent = "Erreur lors de l'envoi.";
  } finally {
    btn.disabled = false;
  }
});

load();
