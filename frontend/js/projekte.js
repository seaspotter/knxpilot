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
  await renderSpecialLocationOptions();
  await renderActorInstanceForm();
  await renderCircuits();
  await renderChannelSummary();
}

async function deleteFloor(id) {
  await api('/floors/' + id, {method:'DELETE'});
  await renderFloors();
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
        <b>${floor.name}</b> ${floor.is_outdoor ? '<span class="pill">Aussen/unbeheizt</span>' : ''}
        <div>
          <input type="text" placeholder="Raumname" id="room-name-${floor.id}" style="width:140px;">
          <button class="btn secondary small" onclick="addRoom(${floor.id})">+ Raum hinzufügen</button>
          <button class="btn secondary small" onclick="toggleBulkRoomInput(${floor.id})">Mehrere...</button>
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
  const pointsByType = {};
  room.points.forEach(p => {
    pointsByType[p.point_type_id] = pointsByType[p.point_type_id] || [];
    pointsByType[p.point_type_id].push(p);
  });
  const pointsHtml = Object.entries(pointsByType).map(([ptId, pts]) => {
    const pt = POINT_TYPES.find(p => p.id === parseInt(ptId));
    const labels = pts.map(p => `<span class="pill">${p.label || '(kein Label)'}${p.has_bwm ? ' +BWM' : ''} <a href="#" onclick="deleteRoomPoint(event, ${p.id})" style="color:var(--danger); text-decoration:none;">×</a></span>`).join('');
    return `<div style="margin:4px 0;"><b>${pt?.name || '?'}</b>: ${labels}</div>`;
  }).join('') || '<p class="muted" style="margin:4px 0;">Noch keine Punkte</p>';

  return `
    <div class="room-card">
      <div class="row" style="justify-content:space-between;">
        <b>${room.name}</b>
        <button class="btn danger small" onclick="deleteRoom(${room.id})">Raum löschen</button>
      </div>
      ${pointsHtml}
      <div class="quick-add">
        <select id="ptype-${room.id}" class="wide">
          ${POINT_TYPES.map(pt => `<option value="${pt.id}">${CATEGORIES.find(c=>c.id===pt.category_id)?.name} — ${pt.name}</option>`).join('')}
        </select>
        <input type="text" id="label-${room.id}" placeholder="Label z.B. Decke, Spots, Nord (leer = keins)" style="width:210px;">
        <input type="number" id="qty-${room.id}" value="1" min="1" title="Anzahl">
        <label style="display:flex; align-items:center; gap:4px;"><input type="checkbox" id="bwm-${room.id}"> +BWM<span class="info-icon" tabindex="0" data-tip="BWM = Bewegungsmelder. Fügt diesem Punkt eine zusätzliche Bewegungsmelder-Adresse hinzu, zusätzlich zu den normalen Datenpunkten des Punkttyps.">i</span></label>
        <button class="btn secondary small" onclick="addPoint(${room.id})">+ Hinzufügen</button>
      </div>
    </div>
  `;
}

async function addRoom(floorId) {
  const name = document.getElementById(`room-name-${floorId}`).value.trim();
  if (!name) return;
  await api(`/floors/${floorId}/rooms`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  await renderFloors();
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
  await renderCircuits();
  await renderChannelSummary();
  showToast(`${names.length} Raum/Räume hinzugefügt.`, 'success');
}

async function deleteRoom(id) {
  await api('/rooms/' + id, {method:'DELETE'});
  await renderFloors();
  await renderCircuits();
  await renderChannelSummary();
}

async function addPoint(roomId) {
  const point_type_id = parseInt(document.getElementById(`ptype-${roomId}`).value);
  const label = document.getElementById(`label-${roomId}`).value.trim();
  const quantity = parseInt(document.getElementById(`qty-${roomId}`).value) || 1;
  const has_bwm = document.getElementById(`bwm-${roomId}`).checked;
  await api(`/rooms/${roomId}/points`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({point_type_id, label, quantity, has_bwm})});
  await renderFloors();
  await renderCircuits();
  await renderChannelSummary();
}

async function deleteRoomPoint(ev, id) {
  ev.preventDefault();
  await api('/room-points/' + id, {method:'DELETE'});
  await renderFloors();
  await renderCircuits();
  await renderChannelSummary();
}

// ---------- Specials ----------
function addSpecialSuffixRow(suffix='', dpt='') {
  const div = document.createElement('div');
  div.className = 'row';
  div.innerHTML = `
    <input type="text" placeholder="Suffix z.B. Auf/Ab" class="sp-suf-name" value="${suffix}">
    <input type="text" placeholder="DPT z.B. DPST-1-8" class="sp-suf-dpt" value="${dpt}">
    <button class="btn danger small" onclick="this.parentElement.remove()">x</button>`;
  document.getElementById('special-suffixes').appendChild(div);
}

async function renderSpecialLocationOptions() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const sel = document.getElementById('special-location');
  sel.innerHTML = `<option value="central">Zentralfunktionen (ganze Kategorie)</option>` +
    tree.floors.map(f => `<option value="${f.id}">Geschoss: ${f.name}</option>`).join('');
}

async function createSpecial() {
  const category_id = parseInt(document.getElementById('special-category').value);
  const location = document.getElementById('special-location').value;
  const name = document.getElementById('special-name').value.trim();
  const suffixes = [...document.querySelectorAll('#special-suffixes .row')].map(r => ({
    suffix: r.querySelector('.sp-suf-name').value.trim(),
    dpt: r.querySelector('.sp-suf-dpt').value.trim()
  })).filter(s => s.suffix);
  if (!name || suffixes.length === 0) return showToast('Name und mindestens ein Datenpunkt erforderlich', 'warning');
  await api(`/projects/${CURRENT_PROJECT}/specials`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({category_id, location, name, suffixes})});
  document.getElementById('special-name').value = '';
  document.getElementById('special-suffixes').innerHTML = '';
  await renderSpecials();
}

async function renderSpecials() {
  const specials = await api(`/projects/${CURRENT_PROJECT}/specials`);
  const ul = document.getElementById('specials-list');
  ul.innerHTML = specials.map(s => {
    const cat = CATEGORIES.find(c => c.id === s.category_id);
    return `<li>
      <div><b>${s.name}</b> <span class="pill">${cat?.name||'?'}</span> <span class="pill">${s.location === 'central' ? 'Zentral' : 'Geschoss'}</span>
        ${s.suffixes.map(x=>`<span class="pill">${x.suffix} · ${x.dpt}</span>`).join('')}
      </div>
      <button class="btn danger small" onclick="deleteSpecial(${s.id})">Löschen</button>
    </li>`;
  }).join('') || '<li class="muted">Noch keine</li>';
}

async function deleteSpecial(id) {
  await api('/specials/' + id, {method:'DELETE'});
  await renderSpecials();
}


// ---------- Preview / Export ----------
async function previewGA() {
  document.getElementById('gen-error').textContent = '';
  try {
    const data = await api(`/projects/${CURRENT_PROJECT}/preview`);
    const el = document.getElementById('ga-preview');
    el.innerHTML = data.main_groups.map(m => {
      const totalSubs = m.middles.reduce((sum, mid) => sum + mid.subs.length, 0);
      return `
      <details class="tree-main" open>
        <summary><span class="main">${m.main} ${m.name}</span> <span class="muted">(${totalSubs})</span></summary>
        ${m.middles.map(mid => `
          <details class="tree-middle">
            <summary><span class="middle">${m.main}/${mid.middle} ${mid.name}</span> <span class="muted">(${mid.subs.length})</span></summary>
            <div class="tree-subs">
              ${mid.subs.map(s => `
                <div class="tree-sub-row">
                  <span class="${s.name.endsWith('res') ? 'res' : 'sub'}">${m.main}/${mid.middle}/${s.sub} ${s.name}</span>${s.dpt ? ` <span class="addr">(${s.dpt})</span>` : ''}
                </div>`).join('')}
            </div>
          </details>`).join('')}
      </details>`;
    }).join('');
  } catch (e) {
    document.getElementById('gen-error').textContent = e.message;
  }
}

function expandAllGaTree(open) {
  document.querySelectorAll('#ga-preview details').forEach(d => { d.open = open; });
}

function downloadCSV() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export.csv`;
}

function exportProjectJson() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-json`;
}

async function importProjectJson() {
  const fileInput = document.getElementById('import-json-file');
  const file = fileInput.files[0];
  if (!file) return showToast('Bitte zuerst eine Sicherungs-.json-Datei auswählen', 'warning');
  const text = await file.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    return showToast('Diese Datei ist kein gültiges JSON', 'error');
  }
  const result = await api('/projects/import-json', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  fileInput.value = '';
  await loadProjects();
  if (result.skipped && result.skipped.length) {
    showToast(`Importiert als "${result.name}".\n\nEinige Elemente wurden übersprungen, da ihr Punkttyp/ihre Kategorie auf dieser Installation nicht existiert:\n- ${result.skipped.join('\n- ')}`, 'warning', {sticky: true});
  } else {
    showToast(`Importiert als "${result.name}".`, 'success');
  }
}

