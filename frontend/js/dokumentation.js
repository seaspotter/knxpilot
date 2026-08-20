// ---------- Dokumentation (project sub-tab) ----------
// Purely static content (intro text + download button, see index.html) -
// the end-of-project assembly PDF, nothing dynamic to load here. Which
// optional sections it includes is controlled in Setup -> Dokumentation.
function downloadDokumentation() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-dokumentation.pdf`;
}
