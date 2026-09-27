// ---------- Manuals (project sub-tab "Handbücher") ----------
// Rendered server-side with htmx (backend/templates/manuals/tab.html,
// /hx/.../manuals endpoints in backend/routers/manuals.py) - downloading,
// viewing and deleting are hx-* attributes there; this only loads the tab.
function loadProjectManuals() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/manuals`, {target: '#subtab-manuals', swap: 'innerHTML'});
}
