// ---------- Distribution board planning (project sub-tab "Verteilerplanung") ----------
// Rendered server-side with htmx (backend/templates/distribution_boards/,
// /hx/... endpoints in backend/routers/distribution_boards.py) - creating,
// editing, deleting a board and placing/removing/moving items are all
// hx-* attributes there; this only loads the tab and the PDF download.
function loadDistributionBoardsForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/distribution-boards`, {target: '#subtab-distribution-boards', swap: 'innerHTML'});
}

function downloadDistributionBoardsPdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-distribution-boards.pdf`;
}
