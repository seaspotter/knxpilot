// ---------- Pflichtenheft (project sub-tab) ----------
// The early-stage spec document: an "Inhalt" card listing the PDF's sections
// with what's in each, plus Vorschau (PDF in a browser tab) and download.
// See funktionscheckliste.js/uebergabe.js for the digital checklists, and
// dokumentation.js for the end-of-project assembly.
async function loadPflichtenheftForCurrentProject() {
  renderDocContents('pflichtenheft-contents', await api(`/projects/${CURRENT_PROJECT}/pflichtenheft-contents`));
}

function downloadPflichtenheft() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-pflichtenheft.pdf`;
}

function previewPflichtenheft() {
  window.open(`/api/projects/${CURRENT_PROJECT}/export-pflichtenheft.pdf?inline=1`, '_blank');
}
