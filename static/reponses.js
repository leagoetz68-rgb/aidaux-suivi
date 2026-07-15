// reponses.js — Liste des réponses au questionnaire de badgeage

function getToday(){
  const now = new Date();
  const tz = now.getTimezoneOffset() * 60000;
  return new Date(now - tz).toISOString().slice(0, 10);
}

function fmtFr(iso){
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function updateJourResume(){
  const val = document.getElementById("input-jour").value;
  const resume = document.getElementById("jour-resume");
  if (!val){ resume.textContent = ""; return; }
  resume.textContent = `Jour sélectionné : ${fmtFr(val)}`;
}

async function loadDernierEnvoi(){
  try {
    const data = await (await fetch("/api/dernier_envoi_hebdo")).json();
    const el = document.getElementById("dernier-envoi");
    el.textContent = data.dernier_envoi
      ? `Dernier envoi automatique : ${data.dernier_envoi}`
      : "Aucun envoi automatique effectué pour l'instant.";
  } catch (e) { /* silencieux */ }
}

async function load(){
  showLoading(true);
  try {
    const data = await (await fetch("/api/reponses")).json();
    document.getElementById("count").textContent =
      `${data.length} réponse${data.length>1?"s":""}`;

    const tbody = document.getElementById("table-body");
    if (!data.length){ tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Aucune réponse pour le moment.</td></tr>`; return; }

    tbody.innerHTML = data.map(r => `<tr>
      <td>${r.repondu_at}</td>
      <td><strong>${r.intervenant}</strong></td>
      <td>${r.client || ""}</td>
      <td>${r.date_prevue || ""}</td>
      <td>${r.raison}</td>
      <td>${r.commentaire || ""}</td>
    </tr>`).join("");
  } finally { showLoading(false); }
}

document.getElementById("btn-envoyer").addEventListener("click", async () => {
  const btn = document.getElementById("btn-envoyer");
  const resultatDiv = document.getElementById("envoi-resultat");
  const jourVal = document.getElementById("input-jour").value;
  if (!jourVal){
    resultatDiv.textContent = "Sélectionne d'abord un jour.";
    return;
  }
  btn.disabled = true;
  resultatDiv.textContent = "Envoi en cours…";
  try {
    const data = await (await fetch("/api/send_reminders", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({date_debut: jourVal, date_fin: jourVal})
    })).json();
    if (!data.results.length){
      resultatDiv.textContent = `Aucune intervention manquée à relancer pour le ${fmtFr(jourVal)}.`;
    } else {
      resultatDiv.innerHTML = data.results.map(r =>
        r.error ? `❌ ${r.intervenant} : ${r.error}` : `✅ ${r.intervenant} (${r.email}) : ${r.nb} intervention(s)`
      ).join("<br>");
    }
  } catch (e) {
    resultatDiv.textContent = "Erreur lors de l'envoi.";
  } finally {
    btn.disabled = false;
    loadDernierEnvoi();
  }
});

document.getElementById("input-jour").value = getToday();
document.getElementById("input-jour").addEventListener("change", updateJourResume);
updateJourResume();

load();
loadDernierEnvoi();
