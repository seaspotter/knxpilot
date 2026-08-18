// ---------- Klärungsliste (project sub-tab) ----------
let EDITING_KLAERUNG_ID = null;
let KLAERUNGEN = [];
let KL_ROOMS = [];
// Must match backend/utils.py's AGED_KLAERUNG_DAYS - only used here for
// the on-screen label text (the actual "aged" flag/age_days per entry
// always comes from the API, this doesn't re-derive it).
const KL_AGED_DAYS = 7;

async function loadKlaerungslisteForCurrentProject() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  renderKlRoomOptions(tree);
  KLAERUNGEN = await api(`/projects/${CURRENT_PROJECT}/klaerungen`);
  renderKlaerungsliste();
}

function renderKlRoomOptions(tree) {
  KL_ROOMS = [];
  tree.floors.forEach(floor => {
    floor.rooms.forEach(room => {
      KL_ROOMS.push({ id: room.id, label: `${floor.name} — ${room.name}`, points: room.points });
    });
  });
  const sel = document.getElementById('kl-room');
  sel.innerHTML = '<option value="">Allgemein (kein Raum)</option>' +
    KL_ROOMS.map(r => `<option value="${r.id}">${r.label}</option>`).join('');
  onKlRoomChange();
}

function onKlRoomChange() {
  const roomId = document.getElementById('kl-room').value;
  const pointSel = document.getElementById('kl-point');
  const room = KL_ROOMS.find(r => String(r.id) === roomId);
  if (!room || !room.points.length) {
    pointSel.style.display = 'none';
    pointSel.innerHTML = '<option value="">(kein bestimmter Punkt)</option>';
    return;
  }
  pointSel.style.display = '';
  pointSel.innerHTML = '<option value="">(kein bestimmter Punkt)</option>' +
    room.points.map(p => `<option value="${p.id}">${p.label || '(kein Label)'}</option>`).join('');
}

async function saveKlaerung() {
  const text = document.getElementById('kl-text').value.trim();
  if (!text) return showToast('Text ist erforderlich', 'warning');
  const typ = document.getElementById('kl-typ').value;
  const roomVal = document.getElementById('kl-room').value;
  const pointVal = document.getElementById('kl-point').value;
  const room_id = roomVal ? parseInt(roomVal) : null;
  const room_point_id = pointVal ? parseInt(pointVal) : null;

  if (EDITING_KLAERUNG_ID) {
    const existing = KLAERUNGEN.find(k => k.id === EDITING_KLAERUNG_ID);
    const body = JSON.stringify({
      room_id, room_point_id, text, typ,
      status: existing ? existing.status : 'offen',
      antwort: existing ? existing.antwort : '',
    });
    await api('/klaerungen/' + EDITING_KLAERUNG_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  } else {
    const body = JSON.stringify({room_id, room_point_id, text, typ});
    await api(`/projects/${CURRENT_PROJECT}/klaerungen`, {method:'POST', headers:{'Content-Type':'application/json'}, body});
  }
  cancelEditKlaerung();
  await loadKlaerungslisteForCurrentProject();
}

function editKlaerung(id) {
  const k = KLAERUNGEN.find(k => k.id === id);
  if (!k) return;
  EDITING_KLAERUNG_ID = id;
  document.getElementById('kl-typ').value = k.typ;
  document.getElementById('kl-room').value = k.room_id || '';
  onKlRoomChange();
  document.getElementById('kl-point').value = k.room_point_id || '';
  document.getElementById('kl-text').value = k.text;
  document.getElementById('kl-form-title').textContent = 'Eintrag bearbeiten';
  document.getElementById('kl-save-btn').textContent = 'Änderungen speichern';
  document.getElementById('kl-cancel-btn').style.display = '';
}

function cancelEditKlaerung() {
  EDITING_KLAERUNG_ID = null;
  document.getElementById('kl-typ').value = 'Frage';
  document.getElementById('kl-room').value = '';
  onKlRoomChange();
  document.getElementById('kl-text').value = '';
  document.getElementById('kl-form-title').textContent = 'Neuer Eintrag';
  document.getElementById('kl-save-btn').textContent = '+ Hinzufügen';
  document.getElementById('kl-cancel-btn').style.display = 'none';
}

async function setKlaerungStatus(id, status) {
  const k = KLAERUNGEN.find(k => k.id === id);
  if (!k) return;
  const body = JSON.stringify({room_id: k.room_id, room_point_id: k.room_point_id, text: k.text, typ: k.typ, antwort: k.antwort, status});
  await api('/klaerungen/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  await loadKlaerungslisteForCurrentProject();
}

async function deleteKlaerung(id) {
  if (!(await showConfirm('Diesen Eintrag löschen?', {danger: true}))) return;
  if (EDITING_KLAERUNG_ID === id) cancelEditKlaerung();
  await api('/klaerungen/' + id, {method:'DELETE'});
  await loadKlaerungslisteForCurrentProject();
}

function escapeAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

async function saveKlAntwortInline(input) {
  const id = parseInt(input.dataset.id);
  const k = KLAERUNGEN.find(k => k.id === id);
  if (!k) return;
  const antwort = input.value.trim();
  if (antwort === (k.antwort || '')) return;
  const body = JSON.stringify({room_id: k.room_id, room_point_id: k.room_point_id, text: k.text, typ: k.typ, status: k.status, antwort});
  await api('/klaerungen/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  k.antwort = antwort;
}

const KL_STATUS_CLASS = {offen: 'status-offen', 'geklärt': 'status-geklaert', abgelehnt: 'status-abgelehnt'};

function renderKlaerungsliste() {
  const container = document.getElementById('klaerungsliste-groups');
  const digestEl = document.getElementById('klaerungsliste-digest');
  const groups = new Map();
  const order = [];
  KLAERUNGEN.forEach(k => {
    const key = k.room_id || 'allgemein';
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key).push(k);
  });

  if (digestEl) {
    const agedCount = KLAERUNGEN.filter(k => k.aged).length;
    digestEl.innerHTML = agedCount
      ? `<p style="color:var(--warn); margin:0 0 10px;">⚠ ${agedCount} offene${agedCount === 1 ? 'r Eintrag ist' : ' Einträge sind'} seit mehr als ${KL_AGED_DAYS} Tagen unbeantwortet.</p>`
      : '';
  }

  container.innerHTML = order.map(key => {
    const entries = groups.get(key);
    const roomInfo = key === 'allgemein' ? null : KL_ROOMS.find(r => r.id === key);
    const heading = roomInfo ? roomInfo.label : 'Allgemein';
    return `
      <div class="floor-card">
        <b>${heading}</b>
        ${entries.map(k => `
          <div class="room-card">
            <div class="row" style="justify-content:space-between;">
              <div>
                <span class="pill">${k.typ}</span>
                <span class="pill ${KL_STATUS_CLASS[k.status] || ''}">${k.status}</span>
                ${k.point_label ? `<span class="pill">${k.point_label}</span>` : ''}
                ${k.aged ? `<span class="pill" style="border-color:var(--warn); color:var(--warn);">${k.age_days} Tage offen</span>` : ''}
              </div>
              <div class="row" style="gap:6px; margin:0;">
                ${k.status !== 'offen' ? `<button class="btn secondary small" onclick="setKlaerungStatus(${k.id}, 'offen')">Offen</button>` : ''}
                ${k.status !== 'geklärt' ? `<button class="btn secondary small" onclick="setKlaerungStatus(${k.id}, 'geklärt')">✓ Geklärt</button>` : ''}
                ${k.status !== 'abgelehnt' ? `<button class="btn secondary small" onclick="setKlaerungStatus(${k.id}, 'abgelehnt')">✗ Abgelehnt</button>` : ''}
                <button class="btn secondary small" onclick="editKlaerung(${k.id})">Bearbeiten</button>
                <button class="btn danger small" onclick="deleteKlaerung(${k.id})">Löschen</button>
              </div>
            </div>
            <div style="margin-top:4px;">${k.text}</div>
            <div class="row" style="margin-top:6px;">
              <input type="text" class="kl-answer-input" data-id="${k.id}" value="${escapeAttr(k.antwort || '')}" placeholder="Antwort/Ergebnis..." onblur="saveKlAntwortInline(this)" onkeydown="if(event.key==='Enter'){this.blur();}">
            </div>
          </div>`).join('')}
      </div>`;
  }).join('') || '<p class="muted">Noch keine Einträge</p>';

  updateKlaerungsBadgeText(KLAERUNGEN);
}

function updateKlaerungsBadgeText(entries) {
  const openCount = entries.filter(k => k.status === 'offen').length;
  const agedCount = entries.filter(k => k.aged).length;
  const btn = document.querySelector('#workspace-subnav button[data-subtab="klaerungsliste"]');
  if (!btn) return;
  btn.textContent = openCount > 0 ? `Klärungsliste (${openCount})` : 'Klärungsliste';
  btn.style.color = agedCount > 0 ? 'var(--warn)' : '';
}

async function refreshKlaerungsBadge() {
  const entries = await api(`/projects/${CURRENT_PROJECT}/klaerungen`);
  updateKlaerungsBadgeText(entries);
}

