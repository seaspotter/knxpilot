// ---------- Dokumentation (project sub-tab) ----------
// Rendered server-side with htmx (backend/templates/documentation/tab.html,
// /hx/projects/{id}/documentation): intro + Vorschau/PDF/email buttons plus
// the chapter-by-chapter "Inhalt" list (a readiness check before handing the
// PDF over). This file only loads the tab and offers the download/preview
// URLs. Which optional chapters are included is controlled in
// Setup -> Dokumentation.
function loadDocumentationTab() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/documentation`, {target: '#subtab-documentation', swap: 'innerHTML'});
}

function downloadDocumentation() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-documentation.pdf`;
}

function previewDocumentation() {
  window.open(`/api/projects/${CURRENT_PROJECT}/export-documentation.pdf?inline=1`, '_blank');
}
