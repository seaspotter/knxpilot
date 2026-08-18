// ---------- Verteilerplanung (project sub-tab) ----------
let VERTEILER_LIST = [];
let VERTEILER_ACTOR_INSTANCES = [];

async function loadVerteilerplanungForCurrentProject() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  document.getElementById('verteiler-floor').innerHTML =
    tree.floors.map(f => `<option value="${f.id}">${f.name}</option>`).join('') ||
    '<option value="">Noch keine Geschosse - zuerst in Gebäudestruktur anlegen</option>';
  VERTEILER_ACTOR_INSTANCES = await api(`/projects/${CURRENT_PROJECT}/actor-instances`);
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}

async function createVerteiler() {
  const floorVal = document.getElementById('verteiler-floor').value;
  if (!floorVal) return showToast('Zuerst ein Geschoss in Gebäudestruktur anlegen', 'warning');
  const floor_id = parseInt(floorVal);
  const name = document.getElementById('verteiler-name').value.trim();
  const row_count = parseInt(document.getElementById('verteiler-rows').value) || 4;
  await api(`/projects/${CURRENT_PROJECT}/verteiler`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({floor_id, name, row_count}),
  });
  document.getElementById('verteiler-name').value = '';
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}

function renderVerteilerList() {
  const container = document.getElementById('verteiler-list');
  container.innerHTML = VERTEILER_LIST.map(v => `
    <div class="card">
      <div class="row" style="justify-content:space-between;">
        <h4 style="margin:0;">${v.name || 'Verteiler'} ${v.floor_name ? `<span class="pill">${v.floor_name}</span>` : ''}</h4>
        <div class="row" style="margin:0; gap:6px;">
          <button class="btn secondary small" onclick="editVerteiler(${v.id})">Bearbeiten</button>
          <button class="btn danger small" onclick="deleteVerteiler(${v.id})">Löschen</button>
        </div>
      </div>
      ${v.rows.map((items, row_idx) => renderVerteilerRow(v, row_idx, items)).join('')}
    </div>
  `).join('') || '<p class="muted">Noch keine Verteiler angelegt</p>';
}

function renderVerteilerRow(v, row_idx, items) {
  const used = items.reduce((sum, it) => sum + (it.width_te || 0), 0);
  const free = v.row_width_te - used;
  const boxes = items.map((it, i) => `
    <div class="verteiler-item ${it.item_type}" style="flex:0 0 ${it.width_te / v.row_width_te * 100}%;" title="${it.width_te} TE">
      <div>${it.label}</div>
      ${it.sublabel ? `<div class="muted" style="font-size:10px;">${it.sublabel}</div>` : ''}
      <div class="verteiler-item-actions">
        ${i > 0 ? `<button onclick="moveVerteilerItem(${it.id}, 'left')" title="Nach links">‹</button>` : ''}
        <button onclick="deleteVerteilerItem(${it.id})" title="Entfernen">×</button>
        ${i < items.length - 1 ? `<button onclick="moveVerteilerItem(${it.id}, 'right')" title="Nach rechts">›</button>` : ''}
      </div>
    </div>`).join('');
  const emptyBox = free > 0
    ? `<div class="verteiler-item-empty" style="flex:0 0 ${free / v.row_width_te * 100}%;">${free} TE frei</div>`
    : '';
  return `
    <div class="verteiler-row">${boxes}${emptyBox}</div>
    <div class="row" style="margin:0 0 14px; gap:6px;">
      <button class="btn secondary small" onclick="addVerteilerItem(${v.id}, ${row_idx}, 'rcd')">+ RCD (4 TE)</button>
      <button class="btn secondary small" onclick="addVerteilerItem(${v.id}, ${row_idx}, 'ls')">+ LS (1 TE)</button>
      <button class="btn secondary small" onclick="openAddDeviceModal(${v.id}, ${row_idx})">+ Gerät...</button>
    </div>`;
}

async function addVerteilerItem(verteiler_id, row_idx, item_type) {
  try {
    await api(`/verteiler/${verteiler_id}/items`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({row_idx, item_type}),
    });
  } catch (e) {
    return showToast(e.message, 'error');
  }
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}

function openAddDeviceModal(verteiler_id, row_idx) {
  const v = VERTEILER_LIST.find(x => x.id === verteiler_id);
  const placed = new Set(
    VERTEILER_LIST.flatMap(x => x.rows.flat()).map(it => it.actor_instance_id).filter(Boolean)
  );
  const candidates = VERTEILER_ACTOR_INSTANCES.filter(ai => ai.floor_id === v.floor_id && !placed.has(ai.id));

  const options = candidates.map(ai =>
    `<option value="${ai.id}">${[ai.actor_type_name, ai.location_label, ai.physical_address].filter(Boolean).join(' · ')}</option>`
  ).join('') || '<option value="">Keine verfügbaren Geräte auf diesem Geschoss</option>';

  const modal = openModal(`
    <h3>Gerät hinzufügen</h3>
    <div class="row"><select id="verteiler-device-select" style="min-width:320px; flex:1;">${options}</select></div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="add">Hinzufügen</button>
    </div>`);

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') modal.close();
    if (action === 'add') {
      const val = document.getElementById('verteiler-device-select').value;
      if (!val) return showToast('Keine Geräte verfügbar', 'warning');
      modal.close();
      try {
        await api(`/verteiler/${verteiler_id}/items`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({row_idx, item_type: 'device', actor_instance_id: parseInt(val)}),
        });
      } catch (e) {
        return showToast(e.message, 'error');
      }
      VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
      renderVerteilerList();
    }
  });
}

async function deleteVerteilerItem(item_id) {
  await api(`/verteiler-items/${item_id}`, {method: 'DELETE'});
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}

async function moveVerteilerItem(item_id, direction) {
  await api(`/verteiler-items/${item_id}/move`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({direction}),
  });
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}

function editVerteiler(verteiler_id) {
  const v = VERTEILER_LIST.find(x => x.id === verteiler_id);
  const modal = openModal(`
    <h3>Verteiler bearbeiten</h3>
    <div class="row"><input type="text" id="verteiler-edit-name" style="min-width:220px; flex:1;"></div>
    <div class="row"><label style="display:flex; align-items:center; gap:4px;">Reihen <input type="number" id="verteiler-edit-rows" min="1" style="width:60px;"></label></div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>`);
  document.getElementById('verteiler-edit-name').value = v.name;
  document.getElementById('verteiler-edit-rows').value = v.row_count;

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') modal.close();
    if (action === 'save') {
      const name = document.getElementById('verteiler-edit-name').value.trim();
      const row_count = parseInt(document.getElementById('verteiler-edit-rows').value) || 1;
      try {
        await api(`/verteiler/${verteiler_id}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name, row_count}),
        });
      } catch (e) {
        return showToast(e.message, 'error');
      }
      modal.close();
      VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
      renderVerteilerList();
    }
  });
}

async function deleteVerteiler(verteiler_id) {
  if (!(await showConfirm('Diesen Verteiler löschen? Alle platzierten Elemente gehen verloren (die Geräte selbst bleiben in der Abgangsliste erhalten).', {danger: true}))) return;
  await api(`/verteiler/${verteiler_id}`, {method: 'DELETE'});
  VERTEILER_LIST = await api(`/projects/${CURRENT_PROJECT}/verteiler`);
  renderVerteilerList();
}
