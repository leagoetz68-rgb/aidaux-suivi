// accueil.js — Tableau de bord (page d'accueil)

const COLORS = {
  manquees: "#C26259",
  partiels: "#FF4713",
  courtes:  "#F39C12",
  longues:  "#000F9F",
  ok:       "#6FB89B",
  na:       "#9AA3AF",
};
const okPart = e => Math.max(0, e.total - e.manquees - e.partiels - e.courtes - e.longues - (e.na || 0));

async function loadAccueil() {
  showLoading(true);
  try {
    const d = await (await fetch("/api/accueil")).json();

    if (!d.info || d.info.total === 0) {
      document.getElementById("empty-db").style.display = "block";
      document.getElementById("dashboard-content").style.display = "none";
      return;
    }

    document.getElementById("empty-db").style.display = "none";
    document.getElementById("dashboard-content").style.display = "block";

    // Infos générales
    document.getElementById("i-total").textContent  = d.info.total;
    document.getElementById("i-interv").textContent = d.info.nb_intervenants;
    document.getElementById("i-clients").textContent = d.info.nb_clients;
    document.getElementById("i-mois").textContent   = d.info.nb_mois;

    // KPIs problèmes
    const total = d.stats.total || 1;
    const pct = (n) => `${Math.round(n / total * 1000) / 10}% du total`;
    document.getElementById("k-manq").textContent = d.stats.manquees;
    document.getElementById("k-manq-pct").textContent = pct(d.stats.manquees);
    document.getElementById("k-part").textContent = d.stats.partiels;
    document.getElementById("k-part-pct").textContent = pct(d.stats.partiels);
    document.getElementById("k-court").textContent = d.stats.courtes;
    document.getElementById("k-long").textContent = d.stats.longues;

    renderEvolution(d.evolution);
    renderRepartition(d.stats);
    renderImports(d.imports);

  } finally {
    showLoading(false);
  }
}

function moisLabel(m) {
  // '2026-05' → 'mai 2026'
  const noms = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  if (!m) return m;
  const [y, mo] = m.split("-");
  return `${noms[parseInt(mo,10)-1]} ${y}`;
}

function renderEvolution(evo) {
  const ctx = document.getElementById("chart-evolution");
  const labels = evo.map(e => moisLabel(e.mois));
  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Manquées",  data: evo.map(e=>e.manquees), backgroundColor: COLORS.manquees },
        { label: "Badgeages partiels", data: evo.map(e=>e.partiels), backgroundColor: COLORS.partiels },
        { label: "Trop courtes", data: evo.map(e=>e.courtes), backgroundColor: COLORS.courtes },
        { label: "Trop longues", data: evo.map(e=>e.longues), backgroundColor: COLORS.longues },
        { label: "Non renseigné", data: evo.map(e=>e.na || 0), backgroundColor: COLORS.na },
        { label: "Sans problème", data: evo.map(okPart), backgroundColor: COLORS.ok },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

function renderRepartition(stats) {
  const ctx = document.getElementById("chart-repartition");
  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Manquées", "Badgeages partiels", "Trop courtes", "Trop longues", "Non renseigné", "Sans problème"],
      datasets: [{
        data: [stats.manquees, stats.partiels, stats.courtes, stats.longues, (stats.na || 0), okPart(stats)],
        backgroundColor: [COLORS.manquees, COLORS.partiels, COLORS.courtes, COLORS.longues, COLORS.na, COLORS.ok],
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
    },
  });
}

function renderImports(imports) {
  const tbody = document.getElementById("imports-body");
  if (!imports.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Aucun import.</td></tr>`;
    return;
  }
  tbody.innerHTML = imports.map(i => `
    <tr>
      <td>${i.filename}</td>
      <td>${i.imported_at}</td>
      <td>${i.rows_added}</td>
      <td>${i.rows_skipped}</td>
      <td>${i.period_min} → ${i.period_max}</td>
    </tr>`).join("");
}

loadAccueil();
