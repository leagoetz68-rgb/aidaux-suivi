// mensuel.js — Suivi mois par mois

function moisLabel(m){
  const noms=["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  const [y,mo]=m.split("-"); return `${noms[parseInt(mo,10)-1]} ${y}`;
}

async function init(){
  showLoading(true);
  try {
    const d = await (await fetch("/api/mensuel")).json();
    renderChart(d.mois);
    renderTable(d.mois);
    renderClients(d.top_clients);
  } finally { showLoading(false); }
}

const SEUIL_NON_BADGEAGE = 4; // % objectif fixé par le département

function tauxNonBadgeage(m){
  return m.total ? Math.round((m.manquees + m.partiels) / m.total * 1000) / 10 : 0;
}

function renderChart(mois){
  const ctx = document.getElementById("chart-taux");
  const nonBadge = mois.map(tauxNonBadgeage);
  // Échelle Y : laisser de la marge au-dessus du max et du seuil
  const ymax = Math.max(SEUIL_NON_BADGEAGE, ...nonBadge, ...mois.map(m=>m.taux)) * 1.2;

  new Chart(ctx, {
    type:"line",
    data:{
      labels: mois.map(m=>moisLabel(m.mois)),
      datasets:[
        {
          label:"Taux de non-badgeage (%)",
          data: nonBadge,
          borderColor:"#C26259", backgroundColor:"rgba(194,98,89,.12)",
          fill:true, tension:.3, pointRadius:4, order:2,
        },
        {
          label:"Taux de problèmes global (%)",
          data: mois.map(m=>m.taux),
          borderColor:"#9AA3AF", backgroundColor:"transparent",
          borderWidth:1.5, borderDash:[3,3], fill:false, tension:.3, pointRadius:0, order:3,
        },
        {
          label:`Objectif département ≤ ${SEUIL_NON_BADGEAGE}%`,
          data: mois.map(()=>SEUIL_NON_BADGEAGE),
          borderColor:"#1E8849", borderWidth:2, borderDash:[7,4],
          fill:false, pointRadius:0, order:1,
        },
      ],
    },
    options:{ responsive:true, maintainAspectRatio:false,
      scales:{y:{beginAtZero:true, suggestedMax:ymax, ticks:{callback:v=>v+"%"}}},
      plugins:{legend:{position:"bottom", labels:{boxWidth:14, font:{size:11}}}} },
  });
}

function renderTable(mois){
  const tbody = document.getElementById("table-body");
  if (!mois.length){ tbody.innerHTML=`<tr><td colspan="9" class="empty-state">Aucune donnée.</td></tr>`; return; }
  tbody.innerHTML = mois.map(m => {
    let varCell = "—";
    if (m.variation !== null){
      if (m.variation > 0) varCell = `<span style="color:#C0392B">▲ +${m.variation} pts</span>`;
      else if (m.variation < 0) varCell = `<span style="color:#1E8849">▼ ${m.variation} pts</span>`;
      else varCell = `<span style="color:#6B7280">= stable</span>`;
    }
    return `<tr>
      <td><strong>${moisLabel(m.mois)}</strong></td>
      <td>${m.total}</td><td>${m.problemes}</td>
      <td><span class="taux-badge ${m.taux>15?'taux-high':'taux-ok'}">${m.taux}%</span></td>
      <td>${varCell}</td>
      <td>${m.manquees}</td><td>${m.partiels}</td><td>${m.courtes}</td><td>${m.longues}</td>
    </tr>`;
  }).join("");
}

function renderClients(clients){
  const tbody = document.getElementById("clients-body");
  if (!clients.length){ tbody.innerHTML=`<tr><td colspan="2" class="empty-state">Aucune donnée.</td></tr>`; return; }
  tbody.innerHTML = clients.map(c =>
    `<tr><td>${c.client}</td><td>${c.problemes}</td></tr>`).join("");
}

init();
