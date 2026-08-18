// ---------- Geräteplanung (project sub-tab) ----------
let EDITING_ROOM_DEVICE_ID = null;
let EDITING_ROOM_DEVICE_ROOM_ID = null;
let GERAETEPLANUNG_DEVICES_BY_ID = {};

async function loadGeraeteplanungForCurrentProject() {
  document.getElementById('geraeteplanung-detail').style.display = 'block';
  await renderDeviceSummary();
  await renderGeraeteplanungRooms();
}

async function renderDeviceSummary() {
  const summary = await api(`/projects/${CURRENT_PROJECT}/device-summary`);
  const ul = document.getElementById('device-summary-list');
  ul.innerHTML = summary.map(s => `
    <li>
      <div><b${s.not_ordering ? ' class="muted"' : ''}>${s.device_name}</b> <span class="pill">${s.group_name}</span>${s.not_ordering ? ' <span class="pill">Bereits vorhanden</span>' : ''}</div>
      <div class="row" style="margin:0; gap:10px;">
        <span class="pill">${s.total} Stück</span>
        <label style="display:flex; align-items:center; gap:4px; font-size:12px; white-space:nowrap;">
          <input type="checkbox" ${s.not_ordering ? 'checked' : ''} onchange="toggleDeviceOrderFlag(${s.device_type_id}, this.checked)">
          Nicht bestellen
        </label>
      </div>
    </li>`).join('') || '<li class="muted">Noch keine Geräte geplant</li>';
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
  const sections = [];
  for (const floor of tree.floors) {
    const roomBlocks = [];
    for (const room of floor.rooms) {
      const devices = await api(`/rooms/${room.id}/devices`);
      devices.forEach(d => { GERAETEPLANUNG_DEVICES_BY_ID[d.id] = d; });
      roomBlocks.push(renderRoomDevices(room, devices));
    }
    sections.push(`<div class="floor-card"><b>${floor.name}</b>${roomBlocks.join('') || '<p class="muted">Noch keine Räume</p>'}</div>`);
  }
  container.innerHTML = sections.join('') || '<p class="muted">Noch keine Geschosse in diesem Projekt</p>';
}

function renderRoomDevices(room, devices) {
  const devicesHtml = devices.map(d => `
    <span class="pill">${d.device_name}${d.physical_address ? ' · ' + d.physical_address : ''}${d.note ? ' — ' + d.note : ''} <a href="#" onclick="editRoomDevice(event, ${room.id}, ${d.id})" style="color:var(--accent); text-decoration:none;" title="Bearbeiten">✎</a> <a href="#" onclick="deleteRoomDevice(event, ${d.id})" style="color:var(--danger); text-decoration:none;">×</a></span>
  `).join('') || '<span class="muted">Keine Geräte</span>';
  return `
    <div class="room-card">
      <b>${room.name}</b>
      <div style="margin:6px 0;">${devicesHtml}</div>
      <div class="quick-add">
        <select id="rd-device-${room.id}" class="wide">
          ${ACTOR_TYPES.filter(at => at.group_name !== 'Aktor').map(at => `<option value="${at.id}">${at.group_name} — ${[at.manufacturer, at.model].filter(Boolean).join(' ')}</option>`).join('')}
        </select>
        <input type="number" id="rd-qty-${room.id}" value="1" min="1" title="Anzahl" oninput="updateRoomDeviceAddressState(${room.id})">
        <input type="text" id="rd-note-${room.id}" placeholder="Notiz (optional)" style="width:160px;">
        <input type="text" id="rd-address-${room.id}" placeholder="Physikalische Adresse" style="width:140px;">
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
