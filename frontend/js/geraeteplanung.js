// ---------- Geräteplanung (project sub-tab) ----------
let EDITING_ROOM_DEVICE_ID = null;
let EDITING_ROOM_DEVICE_ROOM_ID = null;
let GERAETEPLANUNG_DEVICES_BY_ID = {};
let EDITING_FLOOR_DEVICE_ID = null;
let EDITING_FLOOR_DEVICE_FLOOR_ID = null;
let GERAETEPLANUNG_FLOOR_DEVICES_BY_ID = {};

async function loadGeraeteplanungForCurrentProject() {
  document.getElementById('geraeteplanung-detail').style.display = 'block';
  await renderDeviceSummary();
  await renderGeraeteplanungRooms();
}

async function renderDeviceSummary() {
  const summary = await api(`/projects/${CURRENT_PROJECT}/device-summary`);
  const el = document.getElementById('device-summary-list');
  if (!summary.length) {
    el.innerHTML = '<p class="muted">Noch keine Geräte geplant</p>';
    return;
  }
  el.innerHTML = `<table class="data-table"><thead><tr>
      <th>Gerät</th><th>Beschreibung</th><th>Gruppe</th><th class="num">Anzahl</th><th class="actions">Nicht bestellen</th>
    </tr></thead><tbody>
    ${summary.map(s => `<tr${s.not_ordering ? ' class="muted-row"' : ''}>
      <td class="strong">${escapeHtml(s.device_name)}</td>
      <td>${escapeHtml(s.description || '')}${s.not_ordering ? ' <span class="pill">Bereits vorhanden</span>' : ''}</td>
      <td>${escapeHtml(s.group_name || '')}</td>
      <td class="num">${s.total}</td>
      <td class="actions"><input type="checkbox" ${s.not_ordering ? 'checked' : ''} onchange="toggleDeviceOrderFlag(${s.device_type_id}, this.checked)" title="Nicht bestellen (bereits vorhanden)"></td>
    </tr>`).join('')}
    </tbody></table>`;
}

async function toggleDeviceOrderFlag(deviceTypeId, notOrdering) {
  await api(`/projects/${CURRENT_PROJECT}/device-order-flags/${deviceTypeId}`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({not_ordering: notOrdering}),
  });
  await renderDeviceSummary();
}

async function renderGeraeteplanungRooms() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const container = document.getElementById('geraeteplanung-rooms');
  GERAETEPLANUNG_DEVICES_BY_ID = {};
  GERAETEPLANUNG_FLOOR_DEVICES_BY_ID = {};
  const sections = [];
  for (const floor of tree.floors) {
    const floorDevices = await api(`/floors/${floor.id}/devices`);
    floorDevices.forEach(d => { GERAETEPLANUNG_FLOOR_DEVICES_BY_ID[d.id] = d; });

    const roomBlocks = [];
    for (const room of floor.rooms) {
      const devices = await api(`/rooms/${room.id}/devices`);
      devices.forEach(d => { GERAETEPLANUNG_DEVICES_BY_ID[d.id] = d; });
      roomBlocks.push(renderRoomDevices(room, devices));
    }
    sections.push(`
      <div class="floor-card">
        <div class="rc-floor-title">${floor.name}</div>
        ${renderFloorDevices(floor, floorDevices)}
        ${roomBlocks.join('') || '<p class="muted">Noch keine Räume</p>'}
      </div>
    `);
  }
  container.innerHTML = sections.join('') || '<p class="muted">Noch keine Geschosse in diesem Projekt</p>';
}

// Devices grouped by catalog Gruppe (Sensor, Bedienelement, ...) into the
// shared rc-row layout - same look as the Funktionen sub-tab.
function renderDeviceRows(devices, editFn, deleteFn, ownerId) {
  const groups = new Map();
  devices.forEach(d => {
    const g = d.group_name || 'Sonstige';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(d);
  });
  if (!groups.size) return '<p class="muted" style="margin:4px 0;">Keine Geräte</p>';
  return `<div class="rc-rows">${[...groups.entries()].map(([group, items]) => `
    <div class="rc-row"><div class="rc-type">${group}</div><div class="rc-pills">${items.map(d => `
      <span class="rc-pill">${d.device_name}${d.physical_address ? ` <span class="rc-tag">${d.physical_address}</span>` : ''}${d.note ? ` <span class="rc-note">${d.note}</span>` : ''}
        <a href="#" onclick="${editFn}(event, ${ownerId}, ${d.id})" class="rc-pill-edit" title="Bearbeiten">✎</a>
        <a href="#" onclick="${deleteFn}(event, ${d.id})" class="rc-pill-del" title="Löschen">×</a></span>`).join('')}
    </div></div>`).join('')}</div>`;
}

function renderFloorDevices(floor, devices) {
  return `
    <div class="room-card rc-room">
      <div class="rc-room-title"><span>Geräte ohne Raum <span class="info-icon" tabindex="0" data-tip="Für Geräte, die keinem bestimmten Raum zuzuordnen sind - z.B. eine Wetterstation an der Fassade oder ein Aussen-Bewegungsmelder.">i</span></span></div>
      ${renderDeviceRows(devices, 'editFloorDevice', 'deleteFloorDevice', floor.id)}
      <div class="quick-add rc-add mobile-fields">
        <select id="fd-device-${floor.id}" class="wide">
          ${ACTOR_TYPES.filter(at => at.group_name !== 'Aktor').map(at => `<option value="${at.id}">${at.group_name} — ${[at.manufacturer, at.model].filter(Boolean).join(' ')}</option>`).join('')}
        </select>
        <input type="number" id="fd-qty-${floor.id}" value="1" min="1" title="Anzahl" oninput="updateFloorDeviceAddressState(${floor.id})">
        <input type="text" id="fd-note-${floor.id}" class="w-160" placeholder="Notiz (optional)">
        <input type="text" id="fd-address-${floor.id}" class="w-140" placeholder="Physikalische Adresse">
        <button class="btn secondary small" id="fd-save-btn-${floor.id}" onclick="saveFloorDevice(${floor.id})">+ Hinzufügen</button>
        <button class="btn secondary small" id="fd-cancel-btn-${floor.id}" onclick="cancelEditFloorDevice(${floor.id})" style="display:none;">Abbrechen</button>
      </div>
    </div>
  `;
}

async function saveFloorDevice(floorId) {
  if (EDITING_FLOOR_DEVICE_ID && EDITING_FLOOR_DEVICE_FLOOR_ID === floorId) {
    const note = document.getElementById(`fd-note-${floorId}`).value.trim();
    const physical_address = document.getElementById(`fd-address-${floorId}`).value.trim();
    await api('/floor-devices/' + EDITING_FLOOR_DEVICE_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({note, physical_address})});
  } else {
    const device_type_id = parseInt(document.getElementById(`fd-device-${floorId}`).value);
    const quantity = parseInt(document.getElementById(`fd-qty-${floorId}`).value) || 1;
    const note = document.getElementById(`fd-note-${floorId}`).value.trim();
    const physical_address = document.getElementById(`fd-address-${floorId}`).value.trim();
    if (!device_type_id) return showToast('Zuerst ein Gerät im Geräte-Katalog-Tab anlegen', 'warning');
    await api(`/floors/${floorId}/devices`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({device_type_id, quantity, note, physical_address})});
  }
  cancelEditFloorDevice(floorId);
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

function updateFloorDeviceAddressState(floorId) {
  if (EDITING_FLOOR_DEVICE_ID && EDITING_FLOOR_DEVICE_FLOOR_ID === floorId) return;
  const qty = parseInt(document.getElementById(`fd-qty-${floorId}`).value) || 1;
  const addressField = document.getElementById(`fd-address-${floorId}`);
  addressField.disabled = qty !== 1;
  if (qty !== 1) addressField.value = '';
}

function editFloorDevice(ev, floorId, deviceId) {
  ev.preventDefault();
  if (EDITING_FLOOR_DEVICE_FLOOR_ID !== null && EDITING_FLOOR_DEVICE_FLOOR_ID !== floorId) {
    cancelEditFloorDevice(EDITING_FLOOR_DEVICE_FLOOR_ID);
  }
  const device = GERAETEPLANUNG_FLOOR_DEVICES_BY_ID[deviceId];
  if (!device) return;
  EDITING_FLOOR_DEVICE_ID = deviceId;
  EDITING_FLOOR_DEVICE_FLOOR_ID = floorId;
  document.getElementById(`fd-device-${floorId}`).style.display = 'none';
  document.getElementById(`fd-qty-${floorId}`).style.display = 'none';
  document.getElementById(`fd-note-${floorId}`).value = device.note || '';
  const addressField = document.getElementById(`fd-address-${floorId}`);
  addressField.disabled = false;
  addressField.value = device.physical_address || '';
  document.getElementById(`fd-save-btn-${floorId}`).textContent = 'Änderungen speichern';
  document.getElementById(`fd-cancel-btn-${floorId}`).style.display = '';
}

function cancelEditFloorDevice(floorId) {
  EDITING_FLOOR_DEVICE_ID = null;
  EDITING_FLOOR_DEVICE_FLOOR_ID = null;
  const deviceField = document.getElementById(`fd-device-${floorId}`);
  const qtyField = document.getElementById(`fd-qty-${floorId}`);
  const noteField = document.getElementById(`fd-note-${floorId}`);
  const addressField = document.getElementById(`fd-address-${floorId}`);
  const saveBtn = document.getElementById(`fd-save-btn-${floorId}`);
  const cancelBtn = document.getElementById(`fd-cancel-btn-${floorId}`);
  if (!deviceField) return; // floor no longer rendered (e.g. after a delete)
  deviceField.style.display = '';
  qtyField.style.display = '';
  qtyField.value = '1';
  noteField.value = '';
  addressField.disabled = false;
  addressField.value = '';
  saveBtn.textContent = '+ Hinzufügen';
  cancelBtn.style.display = 'none';
}

async function deleteFloorDevice(ev, id) {
  ev.preventDefault();
  if (EDITING_FLOOR_DEVICE_ID === id) cancelEditFloorDevice(EDITING_FLOOR_DEVICE_FLOOR_ID);
  await api('/floor-devices/' + id, {method:'DELETE'});
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

function renderRoomDevices(room, devices) {
  return `
    <div class="room-card rc-room">
      <div class="rc-room-title">${room.name}</div>
      ${renderDeviceRows(devices, 'editRoomDevice', 'deleteRoomDevice', room.id)}
      <div class="quick-add rc-add mobile-fields">
        <select id="rd-device-${room.id}" class="wide">
          ${ACTOR_TYPES.filter(at => at.group_name !== 'Aktor').map(at => `<option value="${at.id}">${at.group_name} — ${[at.manufacturer, at.model].filter(Boolean).join(' ')}</option>`).join('')}
        </select>
        <input type="number" id="rd-qty-${room.id}" value="1" min="1" title="Anzahl" oninput="updateRoomDeviceAddressState(${room.id})">
        <input type="text" id="rd-note-${room.id}" class="w-160" placeholder="Notiz (optional)">
        <input type="text" id="rd-address-${room.id}" class="w-140" placeholder="Physikalische Adresse">
        <button class="btn secondary small" id="rd-save-btn-${room.id}" onclick="saveRoomDevice(${room.id})">+ Hinzufügen</button>
        <button class="btn secondary small" id="rd-cancel-btn-${room.id}" onclick="cancelEditRoomDevice(${room.id})" style="display:none;">Abbrechen</button>
      </div>
    </div>
  `;
}

async function saveRoomDevice(roomId) {
  if (EDITING_ROOM_DEVICE_ID && EDITING_ROOM_DEVICE_ROOM_ID === roomId) {
    const note = document.getElementById(`rd-note-${roomId}`).value.trim();
    const physical_address = document.getElementById(`rd-address-${roomId}`).value.trim();
    await api('/room-devices/' + EDITING_ROOM_DEVICE_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({note, physical_address})});
  } else {
    const device_type_id = parseInt(document.getElementById(`rd-device-${roomId}`).value);
    const quantity = parseInt(document.getElementById(`rd-qty-${roomId}`).value) || 1;
    const note = document.getElementById(`rd-note-${roomId}`).value.trim();
    const physical_address = document.getElementById(`rd-address-${roomId}`).value.trim();
    if (!device_type_id) return showToast('Zuerst ein Gerät im Geräte-Katalog-Tab anlegen', 'warning');
    await api(`/rooms/${roomId}/devices`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({device_type_id, quantity, note, physical_address})});
  }
  cancelEditRoomDevice(roomId);
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

// The address field only makes sense when adding exactly one device at once -
// several newly-created rows can't share a single typed-in address. Disabled
// (not hidden) when quantity != 1, so it stays visible/discoverable either way.
function updateRoomDeviceAddressState(roomId) {
  if (EDITING_ROOM_DEVICE_ID && EDITING_ROOM_DEVICE_ROOM_ID === roomId) return; // edit mode always allows it
  const qty = parseInt(document.getElementById(`rd-qty-${roomId}`).value) || 1;
  const addressField = document.getElementById(`rd-address-${roomId}`);
  addressField.disabled = qty !== 1;
  if (qty !== 1) addressField.value = '';
}

function editRoomDevice(ev, roomId, deviceId) {
  ev.preventDefault();
  if (EDITING_ROOM_DEVICE_ROOM_ID !== null && EDITING_ROOM_DEVICE_ROOM_ID !== roomId) {
    cancelEditRoomDevice(EDITING_ROOM_DEVICE_ROOM_ID);
  }
  const device = GERAETEPLANUNG_DEVICES_BY_ID[deviceId];
  if (!device) return;
  EDITING_ROOM_DEVICE_ID = deviceId;
  EDITING_ROOM_DEVICE_ROOM_ID = roomId;
  document.getElementById(`rd-device-${roomId}`).style.display = 'none';
  document.getElementById(`rd-qty-${roomId}`).style.display = 'none';
  document.getElementById(`rd-note-${roomId}`).value = device.note || '';
  const addressField = document.getElementById(`rd-address-${roomId}`);
  addressField.disabled = false;
  addressField.value = device.physical_address || '';
  document.getElementById(`rd-save-btn-${roomId}`).textContent = 'Änderungen speichern';
  document.getElementById(`rd-cancel-btn-${roomId}`).style.display = '';
}

function cancelEditRoomDevice(roomId) {
  EDITING_ROOM_DEVICE_ID = null;
  EDITING_ROOM_DEVICE_ROOM_ID = null;
  const deviceField = document.getElementById(`rd-device-${roomId}`);
  const qtyField = document.getElementById(`rd-qty-${roomId}`);
  const noteField = document.getElementById(`rd-note-${roomId}`);
  const addressField = document.getElementById(`rd-address-${roomId}`);
  const saveBtn = document.getElementById(`rd-save-btn-${roomId}`);
  const cancelBtn = document.getElementById(`rd-cancel-btn-${roomId}`);
  if (!deviceField) return; // room no longer rendered (e.g. after a delete)
  deviceField.style.display = '';
  qtyField.style.display = '';
  qtyField.value = '1';
  noteField.value = '';
  addressField.disabled = false;
  addressField.value = '';
  saveBtn.textContent = '+ Hinzufügen';
  cancelBtn.style.display = 'none';
}

async function deleteRoomDevice(ev, id) {
  ev.preventDefault();
  if (EDITING_ROOM_DEVICE_ID === id) cancelEditRoomDevice(EDITING_ROOM_DEVICE_ROOM_ID);
  await api('/room-devices/' + id, {method:'DELETE'});
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

function downloadGeraeteliste() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-geraeteliste.pdf`;
}

function downloadGeraeteJeRaumPdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-geraete-je-raum.pdf`;
}
