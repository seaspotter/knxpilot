// ---------- Gebäudestruktur: floor/room CRUD + tree with drag & drop ----------
// Geschoss -> Raum -> Verteiler, like the building view in ETS. Rooms can be
// dragged to another position/Geschoss, Geschosse reordered, Verteiler put on
// a Geschoss or into a room. Moves that shift group addresses (Mittelgruppe =
// Geschoss, address blocks follow the room order) are confirmed first, with
// the count from a server-side dry run. Touch devices without drag & drop use
// the ⇄ button instead.
//
// Kept as classic JS + JSON calls (not htmx) even though most other tabs have
// moved to server-rendered fragments: the drag & drop interaction needs the
// whole tree as a JS object client-side (computing drop targets, sibling
// order, and populating the move dialogs), so there is no read-only slice of
// this view that can be rendered server-side without either duplicating the
// tree fetch or re-deriving the same data twice. See DEVELOPMENT.md's htmx
// migration notes.
let STRUCT_TREE = null;
let STRUCT_DRAG = null;  // {kind: 'room'|'floor'|'distribution-board', id}

async function addFloor() {
  const name = document.getElementById('floor-name').value.trim();
  const is_outdoor = document.getElementById('floor-outdoor').checked;
  if (!name) return;
  await api(`/projects/${CURRENT_PROJECT}/floors`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, is_outdoor})});
  document.getElementById('floor-name').value = '';
  document.getElementById('floor-outdoor').checked = false;
  await renderFloors();
}

async function renameFloor(id, currentName, currentOutdoor) {
  const newName = await openRenameModal(currentName, {title: 'Geschoss umbenennen'});
  if (newName === null) return;
  await api('/floors/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: newName, is_outdoor: currentOutdoor})});
  await renderFloors();
}

async function deleteFloor(id) {
  const impact = await api(`/floors/${id}/delete-impact`);
  if (!(await showConfirm(`Geschoss "${impact.name}" löschen?${describeDeleteImpact(impact)}`, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api('/floors/' + id, {method:'DELETE'});
  await renderFloors();
}

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
  const unplaced = STRUCT_TREE.unplaced_distribution_boards.length
    ? `<div class="st-unplaced"><span class="muted">Verteiler ohne Geschoss — auf ein Geschoss oder einen Raum ziehen:</span>
        ${STRUCT_TREE.unplaced_distribution_boards.map(b => structDistributionBoardRow(b)).join('')}</div>` : '';
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
        ${floor.distribution_boards.map(b => structDistributionBoardRow(b)).join('')}
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
    ${room.distribution_boards.map(b => structDistributionBoardRow(b, true)).join('')}`;
}

function structDistributionBoardRow(board, inRoom = false) {
  return `
    <div class="st-row st-board-row${inRoom ? ' in-room' : ''}" draggable="true" data-kind="distribution-board" data-id="${board.id}">
      <span class="st-handle" title="Ziehen: auf ein Geschoss oder in einen Raum">⠿</span>
      <span class="st-icon" aria-hidden="true">▦</span>
      <a href="#" class="st-name" draggable="false" onclick="event.preventDefault(); openDistributionBoards()">${escapeHtml(board.name || 'Verteiler')}</a>
      <span class="st-meta">Verteiler · ${board.row_count} Reihen</span>
      <span class="st-spacer"></span>
      <button class="st-act" onclick="moveDistributionBoardDialog(${board.id})" title="Ort ändern">⇄</button>
      <span class="st-act-gap"></span><span class="st-act-gap"></span>
    </div>`;
}

function openDistributionBoards() {
  document.querySelector('#workspace-subnav button[data-subtab="distribution-boards"]').click();
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
  if (STRUCT_DRAG.kind === 'distribution-board' && (kind === 'room' || kind === 'floor')) return {mode: 'into', row};
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
  } else if (drag.kind === 'distribution-board') {
    await setDistributionBoardLocation(drag.id, kind === 'room' ? {room_id: id} : {floor_id: id});
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
}

async function setDistributionBoardLocation(id, body) {
  try {
    await api(`/distribution-boards/${id}/location`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
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

async function moveDistributionBoardDialog(boardId) {
  const options = STRUCT_TREE.floors.map(f => `
    <optgroup label="${escapeHtml(f.name)}">
      <option value="floor:${f.id}"${f.distribution_boards.some(b => b.id === boardId) ? ' selected' : ''}>${escapeHtml(f.name)} (ganzes Geschoss)</option>
      ${f.rooms.map(r => `<option value="room:${r.id}"${r.distribution_boards.some(b => b.id === boardId) ? ' selected' : ''}>${escapeHtml(r.name)}</option>`).join('')}
    </optgroup>`).join('');
  const value = await structSelectModal('Verteiler befindet sich in', options, 'Speichern');
  if (value === null) return;
  const [kind, id] = value.split(':');
  await setDistributionBoardLocation(boardId, kind === 'room' ? {room_id: parseInt(id, 10)} : {floor_id: parseInt(id, 10)});
}

async function addRoom(floorId) {
  const name = document.getElementById(`room-name-${floorId}`).value.trim();
  if (!name) return;
  await api(`/floors/${floorId}/rooms`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})});
  await renderFloors();
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
  showToast(`${names.length} Raum/Räume hinzugefügt.`, 'success');
}

async function renameRoom(id, currentName) {
  const newName = await openRenameModal(currentName, {title: 'Raum umbenennen'});
  if (newName === null) return;
  await api('/rooms/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: newName})});
  await renderFloors();
}

async function deleteRoom(id) {
  const impact = await api(`/rooms/${id}/delete-impact`);
  if (!(await showConfirm(`Raum "${impact.name}" löschen?${describeDeleteImpact(impact)}`, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api('/rooms/' + id, {method:'DELETE'});
  await renderFloors();
}
