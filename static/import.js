// import.js — Page d'import multi-CSV

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFiles(fileInput.files);
});

async function uploadFiles(files) {
  const form = new FormData();
  for (const f of files) form.append("file", f);

  showLoading(true);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const d = await res.json();
    renderResults(d.results || []);
    loadFiles();
  } catch (e) {
    alert("Erreur lors de l'import.");
  } finally {
    showLoading(false);
  }
}

async function loadFiles() {
  const imports = await (await fetch("/api/imports")).json();
  const tbody = document.getElementById("files-body");
  if (!imports.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Aucun fichier importé.</td></tr>`;
    return;
  }
  tbody.innerHTML = imports.map(i => `
    <tr>
      <td>${i.filename}</td>
      <td>${i.imported_at}</td>
      <td>${i.nb_actuel}</td>
      <td>${i.period_min || "—"} → ${i.period_max || "—"}</td>
      <td><button class="btn-link danger" onclick="deleteImport(${i.id}, '${i.filename.replace(/'/g,"\\'")}')">Supprimer</button></td>
    </tr>`).join("");
}

async function deleteImport(id, filename) {
  if (!confirm(`Supprimer le fichier « ${filename} » et toutes ses interventions ?`)) return;
  showLoading(true);
  try {
    const r = await (await fetch("/api/delete_import", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ id })
    })).json();
    loadFiles();
  } finally { showLoading(false); }
}

function renderResults(results) {
  const card = document.getElementById("import-results");
  const tbody = document.getElementById("results-body");
  card.style.display = "block";
  tbody.innerHTML = results.map(r => {
    if (r.error) {
      return `<tr><td>${r.filename}</td><td colspan="4" style="color:#C0392B">❌ ${r.error}</td></tr>`;
    }
    return `<tr>
      <td>${r.filename}</td>
      <td style="color:#1E8449">✓ Importé</td>
      <td>${r.added}</td>
      <td>${r.skipped}</td>
      <td>${r.period_min || "—"} → ${r.period_max || "—"}</td>
    </tr>`;
  }).join("");
}

// Réinitialisation
document.getElementById("btn-reset-db").addEventListener("click", async () => {
  if (!confirm("Supprimer TOUTES les données enregistrées ? Cette action est irréversible.")) return;
  showLoading(true);
  try {
    await fetch("/api/reset", { method: "POST" });
    alert("Base réinitialisée.");
    document.getElementById("import-results").style.display = "none";
    loadFiles();
  } finally {
    showLoading(false);
  }
});

loadFiles();
