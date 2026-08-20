// ---------- Funktionscheckliste (project sub-tab) ----------
// Digital, tap-to-check on-site testing record - per room and per central/
// Allgemein function. Deliberately does NOT re-render the whole list after
// each toggle (unlike most other toggles in this app, e.g. Klärungsliste's
// status buttons) - this list can be every room × every function, meant
// for walking through a building tapping boxes one at a time, and a full
// re-render after every single tap would reset scroll position each time.
let FUNKTIONSCHECKLISTE_STATUS = {};

async function loadFunktionschecklisteForCurrentProject() {
  const [tree, statusMap, central] = await Promise.all([
    api(`/projects/${CURRENT_PROJECT}/tree`),
    api(`/projects/${CURRENT_PROJECT}/checklist-status`),
    api(`/projects/${CURRENT_PROJECT}/central-functions-checklist`),
  ]);
  FUNKTIONSCHECKLISTE_STATUS = statusMap;
  const container = document.getElementById('funktionscheckliste-content');

  const floorBlocks = [];
  for (const floor of tree.floors) {
    const roomBlocks = [];
    for (const room of floor.rooms) {
      const byCategory = await api(`/rooms/${room.id}/function-checklist`);
      if (Object.keys(byCategory).length === 0) continue;
      roomBlocks.push(`<div class="room-card"><b>${room.name}</b>${renderChecklistCategories(byCategory)}</div>`);
    }
    if (roomBlocks.length) {
      floorBlocks.push(`<div class="floor-card"><b>${floor.name}</b>${roomBlocks.join('')}</div>`);
    }
  }

  let centralHtml = '';
  if (central.length) {
    const byCategory = {};
    central.forEach(([catName, items]) => { byCategory[catName] = items; });
    centralHtml = `<div class="floor-card"><b>Zentral- und Allgemeinfunktionen</b>${renderChecklistCategories(byCategory)}</div>`;
  }

  container.innerHTML = floorBlocks.join('') + centralHtml
    || '<p class="muted">Noch keine Funktionen geplant.</p>';
}

function renderChecklistCategories(byCategory) {
  return Object.entries(byCategory).map(([catName, items]) =>
    items.map(item => renderChecklistItem(catName, item)).join('')
  ).join('');
}

function renderChecklistItem(catName, item) {
  const checked = FUNKTIONSCHECKLISTE_STATUS[item.key]?.status === 'ok';
  return `
    <label id="${checklistDomId(item.key)}" style="display:flex; align-items:center; gap:8px; padding:5px 0; border-bottom:1px solid var(--border);">
      <input type="checkbox" ${checked ? 'checked' : ''} onchange="toggleFunctionChecklistItem('${item.key}', this.checked)">
      <span class="pill" style="flex-shrink:0;">${catName}</span>
      <span>${item.text}</span>
    </label>
  `;
}

function checklistDomId(key) {
  return 'fc-' + key.replace(/[^a-zA-Z0-9]/g, '-');
}

async function toggleFunctionChecklistItem(key, checked) {
  const status = checked ? 'ok' : '';
  await api(`/projects/${CURRENT_PROJECT}/checklist-status/${encodeURIComponent(key)}`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status, note: ''}),
  });
  FUNKTIONSCHECKLISTE_STATUS[key] = {status, note: ''};
  // Deliberately no re-render (see file header) - the checkbox already
  // shows its own new state natively, just keep the cache in sync so a
  // later re-render (e.g. after switching tabs and back) stays correct.
}

function downloadFunktionscheckliste() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-funktionscheckliste.pdf`;
}
