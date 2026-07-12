// reponses.js — Liste des réponses au questionnaire de badgeage

function getCurrentIsoWeek(){
  const now = new Date();
  const target = new Date(now.valueOf());
  const dayNr = (now.getDay() + 6) % 7;
  target.setDate(target.getDate() - dayNr + 3);
  const firstThursday = target.valueOf();
  target.setMonth(0, 1);
  if (target.getDay() !== 4) {
    target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
  }
  const week = 1 + Math.ceil((firstThursday - target) / (7 * 24 * 3600 * 1000));
  return `${now.getFullYear()}-W${String(week).padStart(2, "0")}`;
}

function isoWeekToDateRange(isoWeekStr){
  const [yearStr, weekStr] = isoWeekStr.split("-W");
  const year = parseInt(yearStr, 10);
  const week = parseInt(weekStr, 10);
  const simple = new Date(Date.UTC(year, 0, 1 + (week - 1) * 7));
  const dayOfWeek = simple.getUTCDay() || 7; // Lundi=1 ... Dimanche=7
  const lundi = new Date(simple);
  lundi.setUTCDate(simple.getUTCDate() - dayOfWeek + 1);
  const dimanche = new Date(lundi);
  dimanche.setUTCDate(lundi.getUTCDate() + 6);
  return {
    debut: lundi.toISOString().slice(0, 10),
    fin: dimanche.toISOString().slice(0, 10),
  };
}

function fmtFr(iso){
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function updateSemaineResume(){
  const val = document.getElementById("input-semaine").value;
  const resume = document.getElementById("semaine-resume");
  if (!val){ resume.textContent = ""; return; }
  const {debut, fin} = isoWeekToDateRange(val);
  resume.textContent = `Période sélectionnée : du ${fmtFr(debut)} au ${fmtFr(fin)}`;
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
  const semaineVal = document.getElementById("input-semaine").value;
  if (!semaineVal){
    resultatDiv.textContent = "Sélectionne d'abord une semaine.";
    return;
  }
  const {debut, fin} = isoWeekToDateRange(semaineVal);
  btn.disabled = true;
  resultatDiv.textContent = "Envoi en cours…";
  try {
    const data = await (await fetch("/api/send_reminders", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({date_debut: debut, date_fin: fin})
    })).json();
    if (!data.results.length){
      resultatDiv.textContent = `Aucune intervention manquée à relancer pour la semaine du ${fmtFr(debut)} au ${fmtFr(fin)}.`;
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

document.getElementById("input-semaine").value = getCurrentIsoWeek();
document.getElementById("input-semaine").addEventListener("change", updateSemaineResume);
updateSemaineResume();

load();
loadDernierEnvoi();
