// ---------- Geräteplanung (project sub-tab) ----------
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
      <div><b>${s.device_name}</b> <span class="pill">${s.group_name}</span></div>
      <div><span class="pill">${s.total} Stück</span></div>
    </li>`).join('') || '<li class="muted">Noch keine Geräte geplant</li>';
}

async function renderGeraeteplanungRooms() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const container = document.getElementById('geraeteplanung-rooms');
  const sections = [];
  for (const floor of tree.floors) {
    const roomBlocks = [];
    for (const room of floor.rooms) {
      const devices = await api(`/rooms/${room.id}/devices`);
      const devicesHtml = devices.map(d => `
        <span class="pill">${d.quantity}× ${d.device_name}${d.note ? ' — ' + d.note : ''} <a href="#" onclick="deleteRoomDevice(event, ${d.id})" style="color:var(--danger); text-decoration:none;">×</a></span>
      `).join('') || '<span class="muted">Keine Geräte</span>';
      roomBlocks.push(`
        <div class="room-card">
          <b>${room.name}</b>
          <div style="margin:6px 0;">${devicesHtml}</div>
          <div class="quick-add">
            <select id="rd-device-${room.id}" class="wide">
              ${ACTOR_TYPES.filter(at => at.group_name !== 'Aktor').map(at => `<option value="${at.id}">${at.group_name} — ${[at.manufacturer, at.model].filter(Boolean).join(' ')}</option>`).join('')}
            </select>
            <input type="number" id="rd-qty-${room.id}" value="1" min="1" title="Anzahl">
            <input type="text" id="rd-note-${room.id}" placeholder="Notiz (optional)" style="width:160px;">
            <button class="btn secondary small" onclick="addRoomDevice(${room.id})">+ Hinzufügen</button>
          </div>
        </div>
      `);
    }
    sections.push(`<div class="floor-card"><b>${floor.name}</b>${roomBlocks.join('') || '<p class="muted">Noch keine Räume</p>'}</div>`);
  }
  container.innerHTML = sections.join('') || '<p class="muted">Noch keine Geschosse in diesem Projekt</p>';
}

async function addRoomDevice(roomId) {
  const device_type_id = parseInt(document.getElementById(`rd-device-${roomId}`).value);
  const quantity = parseInt(document.getElementById(`rd-qty-${roomId}`).value) || 1;
  const note = document.getElementById(`rd-note-${roomId}`).value.trim();
  if (!device_type_id) return showToast('Zuerst ein Gerät im Geräte-Katalog-Tab anlegen', 'warning');
  await api(`/rooms/${roomId}/devices`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({device_type_id, quantity, note})});
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

async function deleteRoomDevice(ev, id) {
  ev.preventDefault();
  await api('/room-devices/' + id, {method:'DELETE'});
  await renderGeraeteplanungRooms();
  await renderDeviceSummary();
}

function downloadGeraeteliste() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-geraeteliste.pdf`;
}

