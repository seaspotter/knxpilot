// ---------- Dokumentation (project sub-tab) ----------
// The end-of-project assembly PDF: an "Inhalt" card with every chapter in
// PDF order and its status (e.g. "42 / 75 getestet") as a readiness check
// before handing it over, plus Vorschau and download. Which optional
// chapters it includes is controlled in Setup -> Dokumentation.
async function loadDokumentationForCurrentProject() {
  renderDocContents('dokumentation-contents', await api(`/projects/${CURRENT_PROJECT}/dokumentation-contents`));
}

function downloadDokumentation() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-dokumentation.pdf`;
}

function previewDokumentation() {
  window.open(`/api/projects/${CURRENT_PROJECT}/export-dokumentation.pdf?inline=1`, '_blank');
}
