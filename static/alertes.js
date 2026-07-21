async function init(){
  showLoading(true);
  try {
    const d = await (await fetch("/api/recidivistes")).json();
    render(d.recidivistes);
  } finally { showLoading(false); }
}

function render(data){
  document.getElementById("count").textContent =
    `${data.length} intervenant${data.length>1?"s":""} en alerte`;

  const tbody = document.getElementById("table-body");
  if (!data.length){
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Aucun intervenant en récidive actuellement.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(d => `<tr>
    <td><strong>🔴 ${d.intervenant}</strong></td>
    <td>${d.streak} mois</td>
    <td><span class="taux-badge taux-high">${d.taux_dernier_mois}%</span></td>
    <td>${d.taux_global}%</td>
    <td>${d.total_global}</td>
    <td>${d.email || "—"}</td>
  </tr>`).join("");
}

init();
