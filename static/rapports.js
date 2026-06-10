// rapports.js — Génération et téléchargement du rapport PowerPoint

function moisLabel(m){
  const noms=["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  const [y,mo]=m.split("-"); return `${noms[parseInt(mo,10)-1]} ${y}`;
}

let allIntervenants = [];

async function init(){
  const [mois, intervenants] = await Promise.all([
    (await fetch("/api/mois")).json(),
    (await fetch("/api/intervenants")).json(),
  ]);
  const selM = document.getElementById("f-mois");
  mois.forEach(m => selM.add(new Option(moisLabel(m), m)));
  allIntervenants = intervenants;
  renderIntervChecks();

  document.getElementById("btn-generate").addEventListener("click", generate);

  // Afficher/masquer le bloc de sélection quand l'option est cochée
  document.getElementById("opt-intervenants").addEventListener("change", (e) => {
    document.getElementById("interv-select").style.display = e.target.checked ? "block" : "none";
  });
  // Mode "tous" vs "sélection"
  document.querySelectorAll('input[name="interv-mode"]').forEach(r =>
    r.addEventListener("change", () => {
      const sel = document.querySelector('input[name="interv-mode"]:checked').value === "select";
      document.getElementById("interv-list-wrap").style.display = sel ? "block" : "none";
    }));
  document.getElementById("interv-search").addEventListener("input", renderIntervChecks);
}

function renderIntervChecks(){
  const term = (document.getElementById("interv-search").value || "").toLowerCase();
  const wrap = document.getElementById("interv-checks");
  // Conserver les cochés actuels
  const checked = new Set([...wrap.querySelectorAll("input:checked")].map(c => c.value));
  const list = allIntervenants.filter(n => n.toLowerCase().includes(term));
  wrap.innerHTML = list.map(n => `
    <label class="interv-item">
      <input type="checkbox" value="${n.replace(/"/g,'&quot;')}" ${checked.has(n)?"checked":""} />
      ${n}
    </label>`).join("");
  wrap.querySelectorAll("input").forEach(c => c.addEventListener("change", updateCount));
  updateCount();
}

function updateCount(){
  const n = document.querySelectorAll("#interv-checks input:checked").length;
  document.getElementById("interv-count").textContent = n;
}

async function generate(){
  const checks = [...document.querySelectorAll(".report-options .report-opt input:checked")].map(c => c.value);
  if (!checks.length){ alert("Sélectionnez au moins une section."); return; }

  // Sélection précise d'intervenants ?
  let selectedInterv = [];
  const modeEl = document.querySelector('input[name="interv-mode"]:checked');
  if (checks.includes("intervenants") && modeEl && modeEl.value === "select") {
    selectedInterv = [...document.querySelectorAll("#interv-checks input:checked")].map(c => c.value);
    if (!selectedInterv.length){ alert("Sélectionnez au moins un intervenant, ou choisissez « Tous »."); return; }
  }

  const mois = document.getElementById("f-mois").value;
  const status = document.getElementById("gen-status");
  const btn = document.getElementById("btn-generate");

  btn.disabled = true;
  status.textContent = "⏳ Génération en cours…";
  showLoading(true);

  try {
    // Fenêtre native (pywebview) : on passe par un vrai dialogue "Enregistrer sous"
    if (window.pywebview && window.pywebview.api && window.pywebview.api.generer_rapport) {
      const r = await window.pywebview.api.generer_rapport(checks, mois || "", selectedInterv);
      if (r && r.ok) status.textContent = "✓ Rapport enregistré : " + r.path;
      else if (r && r.cancelled) status.textContent = "Enregistrement annulé.";
      else status.textContent = "❌ Erreur : " + ((r && r.error) || "inconnue");
      return;
    }

    // Navigateur classique (collègues) : téléchargement direct
    const params = new URLSearchParams({ sections: checks.join(",") });
    if (mois) params.set("mois", mois);
    selectedInterv.forEach(n => params.append("intervenant", n));

    const res = await fetch(`/api/rapport_pptx?${params}`);
    if (!res.ok){ throw new Error("Erreur serveur"); }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    let name = "rapport_aidaux";
    if (selectedInterv.length === 1) name = "rapport_" + selectedInterv[0].replace(/[^a-zA-Z0-9]+/g, "_");
    if (mois) name += "_" + mois;
    a.download = name + ".pptx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    status.textContent = "✓ Rapport téléchargé !";
  } catch (e) {
    status.textContent = "❌ Erreur lors de la génération.";
  } finally {
    btn.disabled = false;
    showLoading(false);
  }
}

init();
