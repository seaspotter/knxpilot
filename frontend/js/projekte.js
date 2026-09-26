// ---------- Projects ----------
function openCreateProjectModal() {
  const modal = openModal(`
    <h3>Neues Projekt</h3>
    <div class="row">
      <input type="text" id="new-proj-name" class="flex-input-wide" placeholder="Projektname">
    </div>
    <div class="row mobile-fields">
      <input type="text" id="new-proj-customer" placeholder="Kunde">
      <input type="text" id="new-proj-location" placeholder="Standort">
    </div>
    <div class="row mobile-fields">
      <select id="new-proj-status">
        <option value="">— Status —</option>
        <option value="In Planung">In Planung</option>
        <option value="In Ausführung">In Ausführung</option>
        <option value="Abgeschlossen">Abgeschlossen</option>
        <option value="Pausiert">Pausiert</option>
      </select>
      <input type="text" id="new-proj-order-number" placeholder="Bestellnummer">
    </div>
    <div class="row">
      <input type="text" id="new-proj-comment" class="flex-input-wide" placeholder="Kommentar (optional)">
    </div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="create">Projekt erstellen</button>
    </div>`, { wide: true });

  document.getElementById('new-proj-name').focus();

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') return modal.close();
    if (action !== 'create') return;

    const name = document.getElementById('new-proj-name').value.trim();
    if (!name) return showToast('Projektname ist erforderlich', 'warning');
    const customer = document.getElementById('new-proj-customer').value.trim();
    const location = document.getElementById('new-proj-location').value.trim();
    const status = document.getElementById('new-proj-status').value;
    const order_number = document.getElementById('new-proj-order-number').value.trim();
    const comment = document.getElementById('new-proj-comment').value.trim();
    try {
      const created = await api('/projects', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, customer, location, status, order_number, comment})});
      modal.close();
      await loadProjects();
      document.querySelector('nav button[data-tab="projects"]').click();
      await openProject(created.id, name);
    } catch (e) {
      showToast(e.message, 'error');
    }
  });
}

// ---------- Project picker modal (used by the "Projekt öffnen" nav item) ----------
async function openProjectPickerModal() {
  await loadProjects();
  const modal = openModal(`
    <h3>Projekt öffnen</h3>
    <div class="row">
      <input type="text" id="picker-project-filter" class="flex-input-wide" placeholder="🔍 Suchen (Name, Kunde, Standort, Status, Bestellnummer)...">
    </div>
    <ul class="list" id="picker-projects-list" style="max-height:400px; overflow-y:auto;"></ul>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
    </div>`, { wide: true });

  const renderPicker = () => {
    const query = document.getElementById('picker-project-filter').value.trim().toLowerCase();
    const filtered = !query ? PROJECTS_LIST : PROJECTS_LIST.filter(p =>
      [p.name, p.customer, p.location, p.status, p.order_number]
        .some(field => (field || '').toLowerCase().includes(query))
    );
    document.getElementById('picker-projects-list').innerHTML = filtered.map(p => `
      <li>
        <div>
          <b>${p.name}</b>
          ${p.customer ? `<span class="pill">${p.customer}</span>` : ''}
          ${p.location ? `<span class="pill">${p.location}</span>` : ''}
          ${p.status ? `<span class="pill">${p.status}</span>` : ''}
        </div>
        <button class="btn secondary small" data-open-id="${p.id}">Öffnen</button>
      </li>`).join('') || `<li class="muted">${query ? 'Keine Projekte gefunden' : 'Noch keine Projekte'}</li>`;
  };
  renderPicker();
  document.getElementById('picker-project-filter').focus();
  document.getElementById('picker-project-filter').addEventListener('input', renderPicker);

  modal.overlay.addEventListener('click', async (ev) => {
    if (ev.target.dataset.action === 'cancel') return modal.close();
    const openId = ev.target.dataset.openId;
    if (!openId) return;
    const p = PROJECTS_LIST.find(p => p.id === parseInt(openId));
    if (!p) return;
    modal.close();
    document.querySelector('nav button[data-tab="projects"]').click();
    await openProject(p.id, p.name);
  });
}

function updateHeaderProjectChip() {
  const chip = document.getElementById('header-current-project');
  const p = PROJECTS_LIST.find(p => p.id === CURRENT_PROJECT);
  if (p) {
    document.getElementById('header-current-project-name').textContent = p.name;
    chip.style.display = '';
  } else {
    chip.style.display = 'none';
  }
  renderTimerWidget();
}

async function loadProjects() {
  PROJECTS_LIST = await api('/projects');
  renderProjectsList();
  await loadProjectsDashboard();
}

// ---------- All-projects dashboard (above the Projekte list) ----------
async function loadProjectsDashboard() {
  const d = await api('/projects/dashboard');
  const el = document.getElementById('projects-dashboard-cards');
  if (!d.total) { el.innerHTML = ''; return; }

  const statusPills = Object.entries(d.by_status).map(([status, count]) => `
    <span class="pill" style="cursor:pointer;" onclick="filterProjectsByStatus('${status.replace(/'/g, "\\'")}')">${status}: ${count}</span>
  `).join('');

  const klaerungenWarn = d.aged_klaerungen_total > 0;
  const klaerungenBody = d.open_klaerungen_total
    ? `${d.open_klaerungen_total} offen${klaerungenWarn ? `, davon ${d.aged_klaerungen_total} seit ${d.aged_threshold_days}+ Tagen` : ''}`
    : 'Keine offenen Klärungen';
  const klaerungenList = d.projects_with_open_klaerungen.map(p => `
    <div class="row" style="margin:2px 0; cursor:pointer;" onclick="openProjectToSubtab(${p.id}, '${p.name.replace(/'/g, "\\'")}', 'klaerungsliste')">
      <span>${p.name}</span>
      <span class="pill" style="${p.aged_count > 0 ? 'border-color:var(--warn); color:var(--warn);' : ''}">${p.open_count}${p.aged_count > 0 ? ` (${p.aged_count} alt)` : ''}</span>
    </div>
  `).join('');

  const structureBody = d.projects_without_structure.length
    ? `${d.projects_without_structure.length} Projekt(e) ohne Geschosse`
    : 'Alle Projekte haben eine Struktur';
  const structureList = d.projects_without_structure.map(p => `
    <div class="row" style="margin:2px 0; cursor:pointer;" onclick="openProjectToSubtab(${p.id}, '${p.name.replace(/'/g, "\\'")}', 'struktur')">${p.name}</div>
  `).join('');

  el.innerHTML = `
    <div class="stat-card">
      <h4>Projekte gesamt</h4>
      <p style="margin:0 0 6px;">${d.total}</p>
      <div>${statusPills || '<span class="muted">Kein Status vergeben</span>'}</div>
    </div>
    <div class="stat-card">
      <h4>Offene Klärungen</h4>
      <p class="${klaerungenWarn ? '' : 'muted'}" style="margin:0 0 6px; ${klaerungenWarn ? 'color:var(--warn);' : ''}">${klaerungenBody}</p>
      ${klaerungenList}
    </div>
    <div class="stat-card">
      <h4>Ohne Struktur</h4>
      <p class="${d.projects_without_structure.length ? '' : 'muted'}" style="margin:0 0 6px;">${structureBody}</p>
      ${structureList}
    </div>
  `;
}

function filterProjectsByStatus(status) {
  document.getElementById('project-filter').value = status;
  renderProjectsList();
  document.getElementById('projects-list').scrollIntoView({behavior: 'smooth', block: 'start'});
}

async function openProjectToSubtab(id, name, subtab) {
  document.querySelector('nav button[data-tab="projects"]').click();
  await openProject(id, name);
  document.querySelector(`#workspace-subnav button[data-subtab="${subtab}"]`).click();
}

function renderProjectsList() {
  const ul = document.getElementById('projects-list');
  const countEl = document.getElementById('project-filter-count');
  const query = document.getElementById('project-filter').value.trim().toLowerCase();
  const filtered = !query ? PROJECTS_LIST : PROJECTS_LIST.filter(p =>
    [p.name, p.customer, p.location, p.status, p.order_number]
      .some(field => (field || '').toLowerCase().includes(query))
  );
  countEl.textContent = query ? `${filtered.length} von ${PROJECTS_LIST.length} Projekten` : '';

  ul.innerHTML = filtered.map(p => `
    <li>
      <div>
        <b>${p.name}</b>
        ${p.customer ? `<span class="pill">${p.customer}</span>` : ''}
        ${p.location ? `<span class="pill">${p.location}</span>` : ''}
        ${p.status ? `<span class="pill">${p.status}</span>` : ''}
        ${p.order_number ? `<span class="pill">${p.order_number}</span>` : ''}
      </div>
      <div>
        <button class="btn secondary small" onclick="openProject(${p.id}, '${p.name.replace(/'/g,"\\'")}')">Öffnen</button>
        <button class="btn secondary small" onclick="duplicateProject(${p.id})">Duplizieren</button>
        <button class="btn danger small" onclick="deleteProject(${p.id})">Löschen</button>
      </div>
    </li>`).join('') || (query
      ? '<li class="muted">Keine Projekte gefunden</li>'
      : '<li class="muted">Noch keine Projekte</li>');
}

// Turns a */delete-impact response into the "what else goes with it" lines
// of a delete confirmation - only non-zero counts are listed.
const DELETE_IMPACT_LABELS = [
  ['floors', 'Geschoss(e)'], ['rooms', 'Raum/Räume'], ['points', 'Funktion(en)'],
  ['assignments', 'Kanalzuordnung(en) in der Abgangsliste'], ['devices', 'geplante(s) Gerät(e)'],
  ['actors', 'Aktor(en)'], ['specials', 'Sonderadresse(n)'], ['klaerungen', 'Klärungslisten-Eintrag/Einträge'],
  ['files', 'Datei(en)'], ['manuals', 'heruntergeladene(s) Handbuch/Handbücher'],
];
function describeDeleteImpact(impact) {
  const deleted = DELETE_IMPACT_LABELS.filter(([k]) => impact[k]).map(([k, label]) => `• ${impact[k]} ${label}`);
  const detached = [];
  if (impact.actors_detached) detached.push(`• ${impact.actors_detached} Aktor(en) verlieren ihre Geschoss-Zuordnung (bleiben erhalten)`);
  if (impact.verteiler_detached) detached.push(`• ${impact.verteiler_detached} Verteiler verlieren ihre Geschoss-Zuordnung (bleiben erhalten)`);
  let text = deleted.length ? `\n\nDabei wird mitgelöscht:\n${deleted.join('\n')}` : '\n\nEs hängt nichts weiter daran.';
  if (detached.length) text += `\n\nAusserdem:\n${detached.join('\n')}`;
  return text;
}

async function deleteProject(id) {
  const p = PROJECTS_LIST.find(p => p.id === id);
  const impact = await api(`/projects/${id}/delete-impact`);
  const message = `Projekt "${p ? p.name : ''}" endgültig löschen?${describeDeleteImpact(impact)}\n\nErfasste Zeiten (Zeiterfassung) bleiben erhalten.`;
  if (!(await showConfirm(message, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api('/projects/' + id, {method:'DELETE'});
  if (CURRENT_PROJECT === id) {
    document.getElementById('project-detail').style.display = 'none';
    document.getElementById('projects-list-card').style.display = '';
    CURRENT_PROJECT = null;
    updateHeaderProjectChip();
  }
  await loadProjects();
}

async function openProject(id, name) {
  CURRENT_PROJECT = id;
  document.getElementById('projects-list-card').style.display = 'none';
  document.getElementById('project-detail').style.display = 'block';
  document.getElementById('project-detail-title').textContent = name;
  document.getElementById('ga-preview').innerHTML = '';
  document.getElementById('gen-error').textContent = '';
  cancelEditProjectMeta();
  renderProjectMeta();

  document.querySelectorAll('#workspace-subnav button').forEach(b => b.classList.remove('active'));
  document.querySelector('#workspace-subnav button[data-subtab="uebersicht"]').classList.add('active');
  document.querySelectorAll('#project-detail .subtab').forEach(t => t.classList.remove('active'));
  document.getElementById('subtab-uebersicht').classList.add('active');

  await renderFloors();
  await renderFunktionenRooms();
  await renderSpecialLocationOptions();
  await renderSpecials();
  await refreshKlaerungsBadge();
  await refreshAbgangslisteBadge();
  await loadUebersichtForCurrentProject();
}

function closeProject() {
  document.getElementById('project-detail').style.display = 'none';
  document.getElementById('projects-list-card').style.display = '';
  CURRENT_PROJECT = null;
  updateHeaderProjectChip();
}

// ---------- Project metadata (edit-in-place) ----------
function renderProjectMeta() {
  const p = PROJECTS_LIST.find(p => p.id === CURRENT_PROJECT);
  if (!p) return;
  document.getElementById('project-detail-title').textContent = p.name;
  const pills = [p.customer, p.location, p.status, p.order_number]
    .filter(Boolean).map(v => `<span class="pill">${v}</span>`).join('');
  document.getElementById('project-meta-pills').innerHTML = pills;
  document.getElementById('project-meta-comment').textContent = p.comment || '';
  updateHeaderProjectChip();
}

function editProjectMeta() {
  const p = PROJECTS_LIST.find(p => p.id === CURRENT_PROJECT);
  if (!p) return;
  document.getElementById('pm-name').value = p.name || '';
  document.getElementById('pm-customer').value = p.customer || '';
  document.getElementById('pm-location').value = p.location || '';
  document.getElementById('pm-status').value = p.status || '';
  document.getElementById('pm-order-number').value = p.order_number || '';
  document.getElementById('pm-email').value = p.email || '';
  document.getElementById('pm-additional-recipients').value = p.additional_recipients || '';
  document.getElementById('pm-comment').value = p.comment || '';
  document.getElementById('project-meta-view').style.display = 'none';
  document.getElementById('project-meta-edit').style.display = '';
}

function cancelEditProjectMeta() {
  document.getElementById('project-meta-view').style.display = '';
  document.getElementById('project-meta-edit').style.display = 'none';
}

async function saveProjectMeta() {
  const name = document.getElementById('pm-name').value.trim();
  if (!name) return showToast('Projektname ist erforderlich', 'warning');
  const body = JSON.stringify({
    name,
    customer: document.getElementById('pm-customer').value.trim(),
    location: document.getElementById('pm-location').value.trim(),
    status: document.getElementById('pm-status').value,
    order_number: document.getElementById('pm-order-number').value.trim(),
    email: document.getElementById('pm-email').value.trim(),
    additional_recipients: document.getElementById('pm-additional-recipients').value.trim(),
    comment: document.getElementById('pm-comment').value.trim(),
  });
  await api('/projects/' + CURRENT_PROJECT, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  await loadProjects();
  cancelEditProjectMeta();
  renderProjectMeta();
}

async function addFloor() {
  const name = document.getElementById('floor-name').value.trim();
  const is_outdoor = document.getElementById('floor-outdoor').checked;
  if (!name) return;
  await api(`/projects/${CURRENT_PROJECT}/floors`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, is_outdoor})});
  document.getElementById('floor-name').value = '';
  document.getElementById('floor-outdoor').checked = false;
  await renderFloors();
  await renderFunktionenRooms();
  await renderSpecialLocationOptions();
  await renderActorInstanceForm();
  await renderCircuits();
  await renderChannelSummary();
}

async function renameFloor(id, currentName, currentOutdoor) {
  const newName = await openRenameModal(currentName, {title: 'Geschoss umbenennen'});
  if (newName === null) return;
  await api('/floors/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: newName, is_outdoor: currentOutdoor})});
  await renderFloors();
  await renderFunktionenRooms();
}

async function deleteFloor(id) {
  const impact = await api(`/floors/${id}/delete-impact`);
  if (!(await showConfirm(`Geschoss "${impact.name}" löschen?${describeDeleteImpact(impact)}`, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api('/floors/' + id, {method:'DELETE'});
  await renderFloors();
  await renderFunktionenRooms();
  await renderSpecialLocationOptions();
  await renderActorInstanceForm();
  await renderCircuits();
  await renderChannelSummary();
}

// ---------- Gebäudestruktur: tree with drag & drop ----------
// Geschoss -> Raum -> Verteiler, like the building view in ETS. Rooms can be
// dragged to another position/Geschoss, Geschosse reordered, Verteiler put on
// a Geschoss or into a room. Moves that shift group addresses (Mittelgruppe =
// Geschoss, address blocks follow the room order) are confirmed first, with
// the count from a server-side dry run. Touch devices without drag & drop use
// the ⇄ button instead.
let STRUCT_TREE = null;
let STRUCT_DRAG = null;  // {kind: 'room'|'floor'|'verteiler', id}

function structCollapsed() {
  try { return JSON.parse(localStorage.getItem('knxpilot-struct-collapsed') || '[]'); } catch (e) { return []; }
}

function toggleStructFloor(floorId) {
  const collapsed = new Set(structCollapsed());
  collapsed.has(floorId) ? collapsed.delete(floorId) : collapsed.add(floorId);
  try { localStorage.setItem('knxpilot-struct-collapsed', JSON.stringify([...collapsed])); } catch (e) { /* ignore */ }
  document.querySelector(`.st-floor[data-floor-id="${floorId}"]`).classList.toggle('collapsed');
}

async function renderFloors() {
  await loadKnxLines();
  STRUCT_TREE = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const collapsed = new Set(structCollapsed());
  const container = document.getElementById('floors-container');
  const unplaced = STRUCT_TREE.unplaced_verteiler.length
    ? `<div class="st-unplaced"><span class="muted">Verteiler ohne Geschoss — auf ein Geschoss oder einen Raum ziehen:</span>
        ${STRUCT_TREE.unplaced_verteiler.map(v => structVerteilerRow(v)).join('')}</div>` : '';
  container.innerHTML = STRUCT_TREE.floors.length ? `<div class="struct-tree">${STRUCT_TREE.floors.map(floor => {
    const points = floor.rooms.reduce((n, r) => n + r.points.length, 0);
    return `
    <div class="st-floor${collapsed.has(floor.id) ? ' collapsed' : ''}" data-floor-id="${floor.id}">
      <div class="st-row st-floor-row" draggable="true" data-kind="floor" data-id="${floor.id}">
        <button class="st-toggle" onclick="toggleStructFloor(${floor.id})" title="Auf-/Zuklappen">›</button>
        <span class="st-handle" title="Ziehen zum Verschieben">⠿</span>
        <span class="st-name st-floor-name">${escapeHtml(floor.name)}</span>
        ${floor.is_outdoor ? '<span class="pill">Aussen/unbeheizt</span>' : ''}
        <span class="st-meta">${floor.rooms.length} Räume · ${points} Funktionen</span>
        <span class="st-spacer"></span>
        ${lineSelectHtml(floor.line_id, 'Standardlinie', `setLine('floors', ${floor.id}, this.value)`)}
        <button class="st-act" onclick="moveFloorDialog(${floor.id})" title="Verschieben">⇄</button>
        <button class="st-act" onclick="renameFloorById(${floor.id})" title="Umbenennen">✎</button>
        <button class="st-act danger" onclick="deleteFloor(${floor.id})" title="Geschoss löschen">×</button>
      </div>
      <div class="st-children">
        ${floor.verteiler.map(v => structVerteilerRow(v)).join('')}
        ${floor.rooms.map(room => structRoomRow(room)).join('') || '<div class="st-empty muted">Noch keine Räume — hier einen Raum hineinziehen oder unten anlegen</div>'}
        <div class="st-add row">
          <input type="text" placeholder="Raumname" id="room-name-${floor.id}" onkeydown="if(event.key==='Enter') addRoom(${floor.id})">
          <button class="btn secondary small" onclick="addRoom(${floor.id})">+ Raum</button>
          <button class="btn secondary small" onclick="toggleBulkRoomInput(${floor.id})">Mehrere...</button>
        </div>
        <div class="row mobile-fields st-add" id="bulk-room-row-${floor.id}" style="display:none;">
          <textarea id="bulk-room-names-${floor.id}" class="flex-input" placeholder="Ein Raumname pro Zeile, z.B.:&#10;Wohnzimmer&#10;Küche&#10;Bad" rows="4"></textarea>
          <button class="btn secondary small" onclick="addRoomsBulk(${floor.id})">Alle hinzufügen</button>
        </div>
      </div>
    </div>`;
  }).join('')}</div>` + unplaced : '<p class="muted">Noch keine Geschosse — oben eines hinzufügen.</p>' + unplaced;
  wireStructDragDrop(container);
}

function structRoomRow(room) {
  return `
    <div class="st-row st-room-row" draggable="true" data-kind="room" data-id="${room.id}">
      <span class="st-handle" title="Ziehen zum Verschieben">⠿</span>
      <span class="st-name">${escapeHtml(room.name)}</span>
      <span class="st-meta">${room.points.length} Funktion(en)</span>
      <span class="st-spacer"></span>
      ${lineSelectHtml(room.line_id, 'Linie wie Geschoss', `setLine('rooms', ${room.id}, this.value)`)}
      <button class="st-act" onclick="moveRoomDialog(${room.id})" title="In anderes Geschoss verschieben">⇄</button>
      <button class="st-act" onclick="renameRoomById(${room.id})" title="Umbenennen">✎</button>
      <button class="st-act danger" onclick="deleteRoom(${room.id})" title="Raum löschen">×</button>
    </div>
    ${room.verteiler.map(v => structVerteilerRow(v, true)).join('')}`;
}

function structVerteilerRow(v, inRoom = false) {
  return `
    <div class="st-row st-verteiler-row${inRoom ? ' in-room' : ''}" draggable="true" data-kind="verteiler" data-id="${v.id}">
      <span class="st-handle" title="Ziehen: auf ein Geschoss oder in einen Raum">⠿</span>
      <span class="st-icon" aria-hidden="true">▦</span>
      <a href="#" class="st-name" draggable="false" onclick="event.preventDefault(); openVerteilerplanung()">${escapeHtml(v.name || 'Verteiler')}</a>
      <span class="st-meta">Verteiler · ${v.row_count} Reihen</span>
      <span class="st-spacer"></span>
      <button class="st-act" onclick="moveVerteilerDialog(${v.id})" title="Ort ändern">⇄</button>
      <span class="st-act-gap"></span><span class="st-act-gap"></span>
    </div>`;
}

function openVerteilerplanung() {
  document.querySelector('#workspace-subnav button[data-subtab="verteilerplanung"]').click();
}

function structFloorOf(roomId) {
  return STRUCT_TREE.floors.find(f => f.rooms.some(r => r.id === roomId));
}

function renameFloorById(id) {
  const f = STRUCT_TREE.floors.find(f => f.id === id);
  renameFloor(id, f.name, f.is_outdoor);
}

function renameRoomById(id) {
  renameRoom(id, structFloorOf(id).rooms.find(r => r.id === id).name);
}

function clearStructDropMarks() {
  document.querySelectorAll('.st-drop-before, .st-drop-after, .st-drop-into')
    .forEach(el => el.classList.remove('st-drop-before', 'st-drop-after', 'st-drop-into'));
}

// Where a drop on `row` would go, or null if not allowed:
// {mode: 'before'|'after'|'into', row}
function structDropTarget(row, ev) {
  if (!STRUCT_DRAG || !row) return null;
  const kind = row.dataset.kind, id = parseInt(row.dataset.id, 10);
  if (kind === STRUCT_DRAG.kind && id === STRUCT_DRAG.id) return null;
  const rect = row.getBoundingClientRect();
  const upper = ev.clientY < rect.top + rect.height / 2;
  if (STRUCT_DRAG.kind === 'room') {
    if (kind === 'room') return {mode: upper ? 'before' : 'after', row};
    if (kind === 'floor') return {mode: 'into', row};
  }
  if (STRUCT_DRAG.kind === 'floor' && kind === 'floor') return {mode: upper ? 'before' : 'after', row};
  if (STRUCT_DRAG.kind === 'verteiler' && (kind === 'room' || kind === 'floor')) return {mode: 'into', row};
  return null;
}

function wireStructDragDrop(container) {
  container.querySelectorAll('.st-row[draggable]').forEach(row => {
    row.addEventListener('dragstart', ev => {
      // Don't start a drag from the line <select>/buttons inside the row.
      if (ev.target.closest && ev.target !== row) { ev.preventDefault(); return; }
      STRUCT_DRAG = {kind: row.dataset.kind, id: parseInt(row.dataset.id, 10)};
      ev.dataTransfer.effectAllowed = 'move';
      ev.dataTransfer.setData('text/plain', `${STRUCT_DRAG.kind}:${STRUCT_DRAG.id}`);
      row.classList.add('st-dragging');
    });
    row.addEventListener('dragend', () => {
      row.classList.remove('st-dragging');
      clearStructDropMarks();
      STRUCT_DRAG = null;
    });
    row.addEventListener('dragover', ev => {
      const target = structDropTarget(row, ev);
      clearStructDropMarks();
      if (!target) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = 'move';
      row.classList.add(`st-drop-${target.mode}`);
    });
    row.addEventListener('dragleave', () => row.classList.remove('st-drop-before', 'st-drop-after', 'st-drop-into'));
    row.addEventListener('drop', async ev => {
      const target = structDropTarget(row, ev);
      const drag = STRUCT_DRAG;
      clearStructDropMarks();
      if (!target || !drag) return;
      ev.preventDefault();
      await applyStructDrop(drag, target);
    });
  });
}

async function applyStructDrop(drag, target) {
  const kind = target.row.dataset.kind, id = parseInt(target.row.dataset.id, 10);
  if (drag.kind === 'room') {
    let floor, index;
    if (kind === 'floor') {
      floor = STRUCT_TREE.floors.find(f => f.id === id);
      index = floor.rooms.filter(r => r.id !== drag.id).length;  // append
    } else {
      floor = structFloorOf(id);
      const siblings = floor.rooms.map(r => r.id).filter(rid => rid !== drag.id);
      index = siblings.indexOf(id) + (target.mode === 'after' ? 1 : 0);
    }
    const current = structFloorOf(drag.id);
    const room = current.rooms.find(r => r.id === drag.id);
    if (floor.id === current.id) {
      if (current.rooms.findIndex(r => r.id === drag.id) === index) return;  // dropped where it already is
      await moveStructure(`/rooms/${drag.id}/move`, {floor_id: floor.id, index}, `Reihenfolge ändern: "${room.name}" in "${floor.name}" verschieben?`,
        'Die Adressblöcke der Räume folgen ihrer Reihenfolge im Geschoss — die Räume zwischen alter und neuer Position rutschen auf andere Untergruppen.');
    } else {
      await moveStructure(`/rooms/${drag.id}/move`, {floor_id: floor.id, index}, `Raum "${room.name}" nach "${floor.name}" verschieben?`);
    }
  } else if (drag.kind === 'floor') {
    const siblings = STRUCT_TREE.floors.map(f => f.id).filter(fid => fid !== drag.id);
    const index = siblings.indexOf(id) + (target.mode === 'after' ? 1 : 0);
    const floor = STRUCT_TREE.floors.find(f => f.id === drag.id);
    await moveStructure(`/floors/${drag.id}/move`, {index}, `Geschoss "${floor.name}" verschieben?`,
      'Die Mittelgruppen sind nach Geschossen durchnummeriert — die Geschosse zwischen alter und neuer Position bekommen eine andere Mittelgruppe.');
  } else if (drag.kind === 'verteiler') {
    await setVerteilerLocation(drag.id, kind === 'room' ? {room_id: id} : {floor_id: id});
  }
}

// Dry run first: only moves that actually shift group addresses ask.
async function moveStructure(url, body, question,
    why = 'Die Mittelgruppe ist das Geschoss, und die Adressblöcke folgen der Reihenfolge der Räume.') {
  let dry;
  try {
    dry = await api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...body, dry_run: true})});
  } catch (e) { return showToast(e.message, 'warning'); }
  if (dry.ga_changed) {
    let message = `${question}\n\nDadurch ändern sich ${dry.ga_changed} Gruppenadresse(n). ${why}`;
    if (dry.exported) message += '\n\nDas Projekt wurde bereits nach ETS exportiert: was danach in ETS nachzuziehen ist, zeigt Gruppenadressen → "Änderungen seit dem letzten ETS-Export".';
    if (!(await showConfirm(message, {confirmLabel: 'Verschieben'}))) return;
  }
  await api(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  await refreshAfterStructureMove();
}

async function refreshAfterStructureMove() {
  await renderFloors();
  await renderFunktionenRooms();
  await renderSpecialLocationOptions();
  await renderActorInstanceForm();
  await renderCircuits();
  await renderChannelSummary();
}

async function setVerteilerLocation(id, body) {
  try {
    await api(`/verteiler/${id}/location`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  } catch (e) { return showToast(e.message, 'warning'); }
  await renderFloors();
}

// ⇄ buttons: the same moves without drag & drop (touch, keyboard).
function structSelectModal(title, optionsHtml, confirmLabel = 'Verschieben') {
  return new Promise(resolve => {
    const modal = openModal(`
      <h3>${title}</h3>
      <select id="st-move-target" style="width:100%;">${optionsHtml}</select>
      <div class="row modal-actions">
        <button class="btn secondary" data-action="cancel">Abbrechen</button>
        <button class="btn" data-action="ok">${confirmLabel}</button>
      </div>`, {onClose: () => resolve(null)});
    modal.overlay.addEventListener('click', ev => {
      const action = ev.target.dataset && ev.target.dataset.action;
      if (action === 'cancel') { modal.close(); }
      if (action === 'ok') { const v = document.getElementById('st-move-target').value; resolve(v); modal.close(); }
    });
  });
}

async function moveRoomDialog(roomId) {
  const current = structFloorOf(roomId);
  const room = current.rooms.find(r => r.id === roomId);
  const value = await structSelectModal(`Raum "${escapeHtml(room.name)}" verschieben nach`,
    STRUCT_TREE.floors.map(f => `<option value="${f.id}"${f.id === current.id ? ' selected' : ''}>${escapeHtml(f.name)}${f.id === current.id ? ' (aktuell)' : ''}</option>`).join(''));
  if (value === null) return;
  const floor = STRUCT_TREE.floors.find(f => f.id === parseInt(value, 10));
  if (floor.id === current.id) return;
  await moveStructure(`/rooms/${roomId}/move`, {floor_id: floor.id, index: floor.rooms.length}, `Raum "${room.name}" nach "${floor.name}" verschieben?`);
}

async function moveFloorDialog(floorId) {
  const floors = STRUCT_TREE.floors;
  const pos = floors.findIndex(f => f.id === floorId);
  const value = await structSelectModal(`Geschoss "${escapeHtml(floors[pos].name)}" verschieben an Position`,
    floors.map((f, i) => `<option value="${i}"${i === pos ? ' selected' : ''}>${i + 1}.${i === pos ? ' (aktuell)' : ` — ${i < pos ? 'vor' : 'nach'} ${escapeHtml(f.name)}`}</option>`).join(''));
  if (value === null || parseInt(value, 10) === pos) return;
  await moveStructure(`/floors/${floorId}/move`, {index: parseInt(value, 10)}, `Geschoss "${floors[pos].name}" verschieben?`,
    'Die Mittelgruppen sind nach Geschossen durchnummeriert — die Geschosse zwischen alter und neuer Position bekommen eine andere Mittelgruppe.');
}

async function moveVerteilerDialog(verteilerId) {
  const options = STRUCT_TREE.floors.map(f => `
    <optgroup label="${escapeHtml(f.name)}">
      <option value="floor:${f.id}"${f.verteiler.some(v => v.id === verteilerId) ? ' selected' : ''}>${escapeHtml(f.name)} (ganzes Geschoss)</option>
      ${f.rooms.map(r => `<option value="room:${r.id}"${r.verteiler.some(v => v.id === verteilerId) ? ' selected' : ''}>${escapeHtml(r.name)}</option>`).join('')}
    </optgroup>`).join('');
  const value = await structSelectModal('Verteiler befindet sich in', options, 'Speichern');
  if (value === null) return;
  const [kind, id] = value.split(':');
  await setVerteilerLocation(verteilerId, kind === 'room' ? {room_id: parseInt(id, 10)} : {floor_id: parseInt(id, 10)});
}

async function addRoom(floorId) {
  const name = document.getElementById(`room-name-${floorId}`).value.trim();
  if (!name) return;
  await api(`/floors/${floorId}/rooms`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  await renderFloors();
  await renderFunktionenRooms();
  await renderCircuits();
  await renderChannelSummary();
}

function toggleBulkRoomInput(floorId) {
  const row = document.getElementById(`bulk-room-row-${floorId}`);
  row.style.display = row.style.display === 'none' ? 'flex' : 'none';
}

async function addRoomsBulk(floorId) {
  const textarea = document.getElementById(`bulk-room-names-${floorId}`);
  const names = textarea.value.split('\n').map(n => n.trim()).filter(Boolean);
  if (!names.length) return showToast('Mindestens ein Raumname erforderlich', 'warning');
  for (const name of names) {
    await api(`/floors/${floorId}/rooms`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  }
  await renderFloors();
  await renderFunktionenRooms();
  await renderCircuits();
  await renderChannelSummary();
  showToast(`${names.length} Raum/Räume hinzugefügt.`, 'success');
}

async function renameRoom(id, currentName) {
  const newName = await openRenameModal(currentName, {title: 'Raum umbenennen'});
  if (newName === null) return;
  await api('/rooms/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: newName})});
  await renderFloors();
  await renderFunktionenRooms();
}

async function deleteRoom(id) {
  const impact = await api(`/rooms/${id}/delete-impact`);
  if (!(await showConfirm(`Raum "${impact.name}" löschen?${describeDeleteImpact(impact)}`, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api('/rooms/' + id, {method:'DELETE'});
  await renderFloors();
  await renderFunktionenRooms();
  await renderCircuits();
  await renderChannelSummary();
}

function exportProjectJson() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-json`;
}

async function importProjectJson() {
  const file = await openImportModal('Projekt aus Sicherung wiederherstellen', 'Erstellt ein neues Projekt aus einer zuvor per "Sichern (JSON)" heruntergeladenen Datei. Existiert bereits ein Projekt mit demselben Namen, wird die Wiederherstellung als "<Name> (imported)" angelegt.');
  if (!file) return;
  const text = await file.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    return showToast('Diese Datei ist kein gültiges JSON', 'error');
  }
  const result = await api('/projects/import-json', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  await loadProjects();
  if (result.skipped && result.skipped.length) {
    showToast(`Importiert als "${result.name}".\n\nEinige Elemente wurden übersprungen, da ihr Funktionstyp/ihre Kategorie auf dieser Installation nicht existiert:\n- ${result.skipped.join('\n- ')}`, 'warning', {sticky: true});
  } else {
    showToast(`Importiert als "${result.name}".`, 'success');
  }
}

async function duplicateProject(id, { open = false } = {}) {
  const result = await api(`/projects/${id}/duplicate`, {method:'POST'});
  await loadProjects();
  showToast(`Dupliziert als "${result.name}".`, 'success');
  if (open) {
    document.querySelector('nav button[data-tab="projects"]').click();
    await openProject(result.id, result.name);
  }
}

