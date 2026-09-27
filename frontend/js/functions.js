// ---------- Functions tab ("Funktionen" sub-tab) ----------
// Rendered server-side with htmx (backend/templates/functions/, /hx/...
// endpoints in backend/routers/functions.py) - assigning a function to a
// room, editing/deleting a room point and adding/removing Sonderadressen
// are all hx-* attributes there; this only loads the tab and holds the
// "add suffix row" helper, which has to stay client-side (it edits an
// as-yet-unsubmitted form before any request is made).
function loadFunctionsForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/functions`, {target: '#subtab-functions', swap: 'innerHTML'});
}

function addSpecialAddressSuffixRow(suffix = '', dpt = '') {
  const div = document.createElement('div');
  div.className = 'row mobile-fields';
  div.innerHTML = `
    <input type="text" name="suffix" placeholder="Suffix z.B. Auf/Ab" value="${suffix}">
    <input type="text" name="dpt" placeholder="DPT z.B. DPST-1-8" value="${dpt}">
    <button class="btn danger small" type="button" onclick="this.parentElement.remove()">x</button>`;
  document.getElementById('sa-suffixes').appendChild(div);
}
