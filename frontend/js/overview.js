// ---------- Übersicht (project sub-tab) ----------
// Rendered server-side with htmx (backend/templates/overview/tab.html,
// /hx/projects/{id}/overview): one stat card per other sub-tab plus the
// project files ("Dateien") section. This file only loads the tab and
// offers goToSubtab(), used by the cards' onclick to jump to another
// sub-tab (server-rendered markup can't call the subnav click handler
// directly, since that lives in api.js).
function goToSubtab(name) {
  document.querySelector(`#workspace-subnav button[data-subtab="${name}"]`).click();
}

function loadOverviewTab() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/overview`, {target: '#subtab-overview', swap: 'innerHTML'});
}
