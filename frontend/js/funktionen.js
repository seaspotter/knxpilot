// ---------- Funktionen (project sub-tab): room functions/points ----------
let EDITING_ROOM_POINT_ID = null;
let EDITING_ROOM_POINT_ROOM_ID = null;
let FUNKTIONEN_POINTS_BY_ID = {};

async function renderFunktionenRooms() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const container = document.getElementById('funktionen-rooms');
  FUNKTIONEN_POINTS_BY_ID = {};
  tree.floors.forEach(floor => floor.rooms.forEach(room => room.points.forEach(p => {
    FUNKTIONEN_POINTS_BY_ID[p.id] = p;
  })));
  if (!tree.floors.length) {
    container.innerHTML = '<p class="muted">Noch keine Geschosse — zuerst im Unterreiter Gebäudestruktur anlegen.</p>';
    return;
  }
  container.innerHTML = tree.floors.map(floor => `
    <div class="floor-card">
      <b>${floor.name}</b>
      ${floor.rooms.map(room => renderRoomFunctions(room)).join('') || '<p class="muted">Noch keine Räume — zuerst im Unterreiter Gebäudestruktur anlegen.</p>'}
    </div>
  `).join('');
}

function renderRoomFunctions(room) {
  const pointsByType = {};
  room.points.forEach(p => {
    pointsByType[p.point_type_id] = pointsByType[p.point_type_id] || [];
    pointsByType[p.point_type_id].push(p);
  });
  const pointsHtml = Object.entries(pointsByType).map(([ptId, pts]) => {
    const pt = POINT_TYPES.find(p => p.id === parseInt(ptId));
    const labels = pts.map(p => `<span class="pill">${p.label || '(kein Label)'}${p.has_bwm ? ' +BWM' : ''} <a href="#" onclick="editRoomPoint(event, ${room.id}, ${p.id})" style="color:var(--accent); text-decoration:none;" title="Bearbeiten">✎</a> <a href="#" onclick="deleteRoomPoint(event, ${p.id})" style="color:var(--danger); text-decoration:none;">×</a></span>`).join('');
    return `<div style="margin:4px 0;"><b>${pt?.name || '?'}</b>: ${labels}</div>`;
  }).join('') || '<p class="muted" style="margin:4px 0;">Noch keine Funktionen</p>';

  return `
    <div class="room-card">
      <b>${room.name}</b>
      ${pointsHtml}
      <div class="quick-add">
        <select id="ptype-${room.id}" class="wide">
          ${POINT_TYPES.map(pt => `<option value="${pt.id}">${CATEGORIES.find(c=>c.id===pt.category_id)?.name} — ${pt.name}</option>`).join('')}
        </select>
        <input type="text" id="label-${room.id}" placeholder="Label z.B. Decke, Spots, Nord (leer = keins)" style="width:210px;">
        <input type="number" id="qty-${room.id}" value="1" min="1" title="Anzahl">
        <label style="display:flex; align-items:center; gap:4px;"><input type="checkbox" id="bwm-${room.id}"> +BWM<span class="info-icon" tabindex="0" data-tip="BWM = Bewegungsmelder. Fügt diesem Punkt eine zusätzliche Bewegungsmelder-Adresse hinzu, zusätzlich zu den normalen Datenpunkten des Funktionstyps.">i</span></label>
        <button class="btn secondary small" id="save-btn-${room.id}" onclick="saveRoomPoint(${room.id})">+ Hinzufügen</button>
        <button class="btn secondary small" id="cancel-btn-${room.id}" onclick="cancelEditRoomPoint(${room.id})" style="display:none;">Abbrechen</button>
      </div>
    </div>
  `;
}

async function saveRoomPoint(roomId) {
  const point_type_id = parseInt(document.getElementById(`ptype-${roomId}`).value);
  const label = document.getElementById(`label-${roomId}`).value.trim();
  const has_bwm = document.getElementById(`bwm-${roomId}`).checked;
  if (EDITING_ROOM_POINT_ID && EDITING_ROOM_POINT_ROOM_ID === roomId) {
    await api('/room-points/' + EDITING_ROOM_POINT_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({point_type_id, label, has_bwm})});
  } else {
    const quantity = parseInt(document.getElementById(`qty-${roomId}`).value) || 1;
    await api(`/rooms/${roomId}/points`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({point_type_id, label, quantity, has_bwm})});
  }
  cancelEditRoomPoint(roomId);
  await renderFunktionenRooms();
  await renderFloors();
  await renderCircuits();
  await renderChannelSummary();
}

function editRoomPoint(ev, roomId, pointId) {
  ev.preventDefault();
  if (EDITING_ROOM_POINT_ROOM_ID !== null && EDITING_ROOM_POINT_ROOM_ID !== roomId) {
    cancelEditRoomPoint(EDITING_ROOM_POINT_ROOM_ID);
  }
  const point = FUNKTIONEN_POINTS_BY_ID[pointId];
  if (!point) return;
  EDITING_ROOM_POINT_ID = pointId;
  EDITING_ROOM_POINT_ROOM_ID = roomId;
  document.getElementById(`ptype-${roomId}`).value = point.point_type_id;
  document.getElementById(`label-${roomId}`).value = point.label || '';
  document.getElementById(`bwm-${roomId}`).checked = point.has_bwm;
  document.getElementById(`qty-${roomId}`).style.display = 'none';
  document.getElementById(`save-btn-${roomId}`).textContent = 'Änderungen speichern';
  document.getElementById(`cancel-btn-${roomId}`).style.display = '';
}

function cancelEditRoomPoint(roomId) {
  EDITING_ROOM_POINT_ID = null;
  EDITING_ROOM_POINT_ROOM_ID = null;
  const qtyField = document.getElementById(`qty-${roomId}`);
  const labelField = document.getElementById(`label-${roomId}`);
  const bwmField = document.getElementById(`bwm-${roomId}`);
  const saveBtn = document.getElementById(`save-btn-${roomId}`);
  const cancelBtn = document.getElementById(`cancel-btn-${roomId}`);
  if (!qtyField) return; // room no longer rendered (e.g. after a delete)
  qtyField.style.display = '';
  qtyField.value = '1';
  labelField.value = '';
  bwmField.checked = false;
  saveBtn.textContent = '+ Hinzufügen';
  cancelBtn.style.display = 'none';
}

async function deleteRoomPoint(ev, id) {
  ev.preventDefault();
  await api('/room-points/' + id, {method:'DELETE'});
  await renderFunktionenRooms();
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
