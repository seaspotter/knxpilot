// ---------- Pflichtenheft (project sub-tab) ----------
// Purely static content (intro text + download button, see index.html) -
// the early-stage spec document, nothing dynamic to load here. See
// funktionscheckliste.js/uebergabe.js for the digital checklists, and
// dokumentation.js for the end-of-project assembly.
function downloadPflichtenheft() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-pflichtenheft.pdf`;
}
