// ---------- Device planning (project sub-tab "Geräteplanung") ----------
// Rendered server-side with htmx (backend/templates/device_planning/,
// /hx/... endpoints in backend/routers/device_planning.py) - the bill of
// materials, per-room/floor device lists and their add/edit/delete forms
// are all hx-* attributes there; this only loads the tab and the PDF
// downloads.
function loadDevicePlanningForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/device-planning`, {target: '#subtab-device-planning', swap: 'innerHTML'});
}

function downloadDeviceListPdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-device-list.pdf`;
}

function downloadDevicesByRoomPdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-devices-by-room.pdf`;
}
