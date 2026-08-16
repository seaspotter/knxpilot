// ---------- Projects ----------
function openCreateProjectModal() {
  const modal = openModal(`
    <h3>Neues Projekt</h3>
    <div class="row">
      <input type="text" id="new-proj-name" placeholder="Projektname" style="min-width:300px; flex:1;">
    </div>
    <div class="row">
      <input type="text" id="new-proj-customer" placeholder="Kunde">
      <input type="text" id="new-proj-location" placeholder="Standort">
    </div>
    <div class="row">
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
      <input type="text" id="new-proj-comment" placeholder="Kommentar (optional)" style="min-width:300px; flex:1;">
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
      <input type="text" id="picker-project-filter" placeholder="🔍 Suchen (Name, Kunde, Standort, Status, Bestellnummer)..." style="min-width:300px; flex:1;">
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
}

async function loadProjects() {
  PROJECTS_LIST = await api('/projects');
  renderProjectsList();
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

async function deleteProject(id) {
  if (!(await showConfirm('Dieses Projekt und alles darin löschen?', {danger: true}))) return;
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
  await api('/floors/' + id, {method:'DELETE'});
  await renderFloors();
  await renderFunktionenRooms();
  await renderSpecialLocationOptions();
  await renderActorInstanceForm();
  await renderCircuits();
  await renderChannelSummary();
}

async function renderFloors() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const container = document.getElementById('floors-container');
  container.innerHTML = tree.floors.map(floor => `
    <div class="floor-card">
      <div class="row" style="justify-content:space-between;">
        <div>
          <b>${floor.name}</b>
          ${floor.is_outdoor ? '<span class="pill">Aussen/unbeheizt</span>' : ''}
        </div>
        <div>
          <input type="text" placeholder="Raumname" id="room-name-${floor.id}" style="width:140px;">
          <button class="btn secondary small" onclick="addRoom(${floor.id})">+ Raum hinzufügen</button>
          <button class="btn secondary small" onclick="toggleBulkRoomInput(${floor.id})">Mehrere...</button>
          <button class="btn secondary small" onclick="renameFloor(${floor.id}, '${floor.name.replace(/'/g,"\\'")}', ${floor.is_outdoor})">Bearbeiten</button>
          <button class="btn danger small" onclick="deleteFloor(${floor.id})">Geschoss löschen</button>
        </div>
      </div>
      <div class="row" id="bulk-room-row-${floor.id}" style="display:none;">
        <textarea id="bulk-room-names-${floor.id}" placeholder="Ein Raumname pro Zeile, z.B.:&#10;Wohnzimmer&#10;Küche&#10;Bad" rows="4" style="flex:1; min-width:220px;"></textarea>
        <button class="btn secondary small" onclick="addRoomsBulk(${floor.id})">Alle hinzufügen</button>
      </div>
      ${floor.rooms.map(room => renderRoom(room)).join('') || '<p class="muted">Noch keine Räume</p>'}
    </div>
  `).join('') || '<p class="muted">Noch keine Geschosse — oben eines hinzufügen.</p>';
}

function renderRoom(room) {
  return `
    <div class="room-card">
      <div class="row" style="justify-content:space-between;">
        <b>${room.name}</b>
        <div>
          <button class="btn secondary small" onclick="renameRoom(${room.id}, '${room.name.replace(/'/g,"\\'")}')">Bearbeiten</button>
          <button class="btn danger small" onclick="deleteRoom(${room.id})">Raum löschen</button>
        </div>
      </div>
      <p class="muted" style="margin:4px 0;">${room.points.length} Funktion(en) — im Unterreiter Funktionen zuweisen</p>
    </div>
  `;
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

