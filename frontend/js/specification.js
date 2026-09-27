// ---------- Pflichtenheft (project sub-tab) ----------
// Rendered server-side with htmx (backend/templates/specification/tab.html,
// /hx/projects/{id}/specification): intro + Vorschau/PDF/email buttons plus
// an "Inhalt" list of what the PDF's sections contain. This file only loads
// the tab and offers the download/preview URLs.
function loadSpecificationTab() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/specification`, {target: '#subtab-specification', swap: 'innerHTML'});
}

function downloadSpecification() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-specification.pdf`;
}

function previewSpecification() {
  window.open(`/api/projects/${CURRENT_PROJECT}/export-specification.pdf?inline=1`, '_blank');
}
