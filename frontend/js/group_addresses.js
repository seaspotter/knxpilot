// ---------- Group addresses tab ("Gruppenadressen" sub-tab) ----------
// Rendered server-side with htmx (backend/templates/group_addresses/,
// /hx/... endpoints in backend/routers/group_addresses.py) - this only
// loads the tab, expands/collapses the (static) GA tree, and downloads the
// CSV (a plain link, per convention) then refreshes the changes card.
function loadGroupAddressesForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/group-addresses`, {target: '#subtab-group-addresses', swap: 'innerHTML'});
}

function expandAllGaTree(open) {
  document.querySelectorAll('#ga-preview details').forEach(d => { d.open = open; });
}

function downloadGroupAddressesCsv() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export.csv`;
  // The download itself becomes the new baseline (server side) - refresh the
  // changes card once it has gone through.
  setTimeout(() => htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/group-addresses/changes`, {target: '#ga-changes', swap: 'innerHTML'}), 1500);
}
