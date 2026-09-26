// ---------- Funktionscheckliste (project sub-tab) ----------
// Digital, tap-to-check on-site testing record - per room and per central/
// Allgemein function. Deliberately does NOT re-render the whole list after
// each toggle (unlike most other toggles in this app, e.g. Klärungsliste's
// status buttons) - this list can be every room × every function, meant
// for walking through a building tapping boxes one at a time, and a full
// re-render after every single tap would reset scroll position each time.
let FUNKTIONSCHECKLISTE_STATUS = {};

async function loadFunktionschecklisteForCurrentProject() {
  const [tree, statusMap, central, signatures] = await Promise.all([
    api(`/projects/${CURRENT_PROJECT}/tree`),
    api(`/projects/${CURRENT_PROJECT}/checklist-status`),
    api(`/projects/${CURRENT_PROJECT}/central-functions-checklist`),
    api(`/projects/${CURRENT_PROJECT}/signatures`),
  ]);
  FUNKTIONSCHECKLISTE_STATUS = statusMap;
  PROJECT_SIGNATURES = signatures;
  const container = document.getElementById('funktionscheckliste-content');

  const floorBlocks = [];
  for (const floor of tree.floors) {
    const roomBlocks = [];
    for (const room of floor.rooms) {
      const byCategory = await api(`/rooms/${room.id}/function-checklist`);
      if (Object.keys(byCategory).length === 0) continue;
      roomBlocks.push(`<div class="room-card rc-room"><div class="rc-room-title">${room.name}</div>${renderChecklistCategories(byCategory)}</div>`);
    }
    if (roomBlocks.length) {
      floorBlocks.push(`<div class="floor-card"><div class="rc-floor-title">${floor.name}</div>${roomBlocks.join('')}</div>`);
    }
  }

  let centralHtml = '';
  if (central.length) {
    const byCategory = {};
    central.forEach(([catName, items]) => { byCategory[catName] = items; });
    centralHtml = `<div class="floor-card"><div class="rc-floor-title">Zentral- und Allgemeinfunktionen</div>${renderChecklistCategories(byCategory)}</div>`;
  }

  container.innerHTML = (floorBlocks.join('') + centralHtml
    || '<p class="muted">Noch keine Funktionen geplant.</p>') + '<div id="fc-signatures"></div>';
  renderFunktionsSignatures();
}

// Own signature pair (fc_* roles, separate from the Übergabe-Checkliste's);
// the customer's is optional. Only this block re-renders after signing, not
// the whole list (see file header).
function renderFunktionsSignatures() {
  document.getElementById('fc-signatures').innerHTML = `
    <div class="floor-card">
      <div class="rc-floor-title">Bestätigung: Funktionen getestet</div>
      <div class="row" style="gap:20px; flex-wrap:wrap; margin-top:8px; align-items:flex-start;">
        ${renderSignatureBlock('fc_systemintegrator', 'Systemintegrator', 'renderFunktionsSignatures')}
        ${renderSignatureBlock('fc_kunde', 'Kunde/Betreiber', 'renderFunktionsSignatures', 'optional')}
      </div>
    </div>`;
}

// "26.09.26, 14:32" - updated_at is sqlite CURRENT_TIMESTAMP (UTC, no zone).
function checklistWhen(entry) {
  if (!entry || entry.status !== 'ok' || !entry.updated_at) return '';
  const iso = entry.updated_at.includes('T') ? entry.updated_at : entry.updated_at.replace(' ', 'T') + 'Z';
  return new Date(iso).toLocaleString('de-DE', {day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit'});
}

function renderChecklistCategories(byCategory) {
  return Object.entries(byCategory).map(([catName, items]) =>
    items.map(item => renderChecklistItem(catName, item)).join('')
  ).join('');
}

function renderChecklistItem(catName, item) {
  const entry = FUNKTIONSCHECKLISTE_STATUS[item.key];
  const checked = entry?.status === 'ok';
  // Table-like row: category pill | function | "getestet" + checkbox on the
  // right. The whole row is the <label>, so tapping anywhere toggles it.
  return `
    <label id="${checklistDomId(item.key)}" class="fc-row${checked ? ' done' : ''}">
      <span class="pill">${catName}</span>
      <span class="fc-text">${item.text}</span>
      <span class="fc-check"><span class="fc-when">${checklistWhen(entry)}</span>getestet
        <input type="checkbox" ${checked ? 'checked' : ''} onchange="toggleFunctionChecklistItem('${item.key}', this.checked)">
      </span>
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
  FUNKTIONSCHECKLISTE_STATUS[key] = {status, note: '', updated_at: new Date().toISOString()};
  const row = document.getElementById(checklistDomId(key));
  if (row) {
    row.classList.toggle('done', checked);
    row.querySelector('.fc-when').textContent = checklistWhen(FUNKTIONSCHECKLISTE_STATUS[key]);
  }
  // Deliberately no re-render (see file header) - the checkbox already
  // shows its own new state natively, just keep the cache in sync so a
  // later re-render (e.g. after switching tabs and back) stays correct.
}

function downloadFunktionscheckliste() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-funktionscheckliste.pdf`;
}
