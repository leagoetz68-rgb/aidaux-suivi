let allData = [];
let moyenne = 0;
let chartInstance = null;

const COLORS = { manquees:"#C26259", partiels:"#FF4713", courtes:"#F39C12", longues:"#000F9F", ok:"#6FB89B", na:"#9AA3AF" };

function moisLabel(m){
  const noms=["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  const [y,mo]=m.split("-"); return `${noms[parseInt(mo,10)-1]} ${y}`;
}

async function init(){
  const mois = await (await fetch("/api/mois")).json();
  const selM = document.getElementById("f-mois");
  mois.forEach(m => selM.add(new Option(moisLabel(m), m)));

  document.getElementById("f-mois").addEventListener("change", load);
  document.getElementById("f-search").addEventListener("input", render);
  document.getElementById("m-close").addEventListener("click", closeModal);
  document.getElementById("modal").addEventListener("click", (e)=>{
    if (e.target.id === "modal") closeModal();
  });
  load();
}

let emails = {};

async function load(){
  showLoading(true);
  try {
    const mois = document.getElementById("f-mois").value;
    const q = mois ? `?mois=${mois}` : "";
    const d = await (await fetch(`/api/stats_intervenants${q}`)).json();
    allData = d.intervenants;
    moyenne = d.moyenne_taux;
    emails = await (await fetch("/api/intervenant_emails")).json();
    render();
  } finally { showLoading(false); }
}

async function saveEmail(nom, input){
  const email = input.value.trim();
  if (!email) return;
  await fetch("/api/intervenant_emails", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ intervenant: nom, email }),
  });
  emails[nom] = email;
}

function render(){
  const term = document.getElementById("f-search").value.toLowerCase();
  const data = allData.filter(d => d.intervenant.toLowerCase().includes(term));
  document.getElementById("count").textContent =
    `${data.length} intervenant${data.length>1?"s":""} · moyenne ${moyenne}%`;

  const tbody = document.getElementById("table-body");
  if (!data.length){ tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Aucun résultat.</td></tr>`; return; }

  tbody.innerHTML = data.map(d => {
    const cls = d.taux > moyenne ? "taux-high" : "taux-ok";
    const nomEch = d.intervenant.replace(/'/g,"\\'");
    return `<tr>
      <td><strong>${d.intervenant}</strong></td>
      <td>${d.total}</td>
      <td>${d.problemes}</td>
      <td><span class="taux-badge ${cls}">${d.taux}%</span></td>
      <td>${d.manquees}</td><td>${d.partiels}</td><td>${d.courtes}</td><td>${d.longues}</td>
      <td><input type="email" placeholder="email…" value="${emails[d.intervenant] || ""}"
            onblur="saveEmail('${nomEch}', this)" style="width:160px" /></td>
      <td><button class="btn-link" onclick="openDetail('${nomEch}')">Voir →</button></td>
    </tr>`;
  }).join("");
}

async function openDetail(nom){
  showLoading(true);
  try {
    const d = await (await fetch(`/api/detail_intervenant?intervenant=${encodeURIComponent(nom)}`)).json();
    const g = d.global;
    document.getElementById("m-nom").textContent = nom;
    document.getElementById("m-total").textContent = g.total;
    document.getElementById("m-probs").textContent = g.problemes;
    document.getElementById("m-taux").textContent = `${g.taux}%`;
    document.getElementById("m-manq").textContent = g.manquees;
    document.getElementById("m-clients").textContent = g.nb_clients;

    const diff = Math.round((g.taux - moyenne)*10)/10;
    const cmp = document.getElementById("m-compare");
    if (diff > 0){ cmp.textContent = `⚠ Taux supérieur de ${diff} pts à la moyenne (${moyenne}%)`; cmp.className = "compare-line high"; }
    else { cmp.textContent = `✓ Taux inférieur de ${Math.abs(diff)} pts à la moyenne (${moyenne}%)`; cmp.className = "compare-line ok"; }

    renderChart(d.evolution);
    document.getElementById("modal").style.display = "flex";
  } finally { showLoading(false); }
}

function renderChart(evo){
  if (chartInstance) chartInstance.destroy();
  const ctx = document.getElementById("m-chart");
  chartInstance = new Chart(ctx, {
    type:"bar",
    data:{
      labels: evo.map(e=>moisLabel(e.mois)),
      datasets:[
        {label:"Manquées",data:evo.map(e=>e.manquees),backgroundColor:COLORS.manquees},
        {label:"Partiels",data:evo.map(e=>e.partiels),backgroundColor:COLORS.partiels},
        {label:"Trop courtes",data:evo.map(e=>e.courtes),backgroundColor:COLORS.courtes},
        {label:"Trop longues",data:evo.map(e=>e.longues),backgroundColor:COLORS.longues},
        {label:"Non renseigné",data:evo.map(e=>e.na || 0),backgroundColor:COLORS.na},
        {label:"Sans problème",data:evo.map(e=>Math.max(0, e.total - e.manquees - e.partiels - e.courtes - e.longues - (e.na||0))),backgroundColor:COLORS.ok},
      ],
    },
    options:{ responsive:true, maintainAspectRatio:false,
      scales:{x:{stacked:true},y:{stacked:true,beginAtZero:true}},
      plugins:{legend:{position:"bottom",labels:{boxWidth:12,font:{size:11}}}} },
  });
}

function closeModal(){ document.getElementById("modal").style.display = "none"; }

init();
