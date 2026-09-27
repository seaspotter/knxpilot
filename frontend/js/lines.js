// ---------- KNX-Linien (Gebäudestruktur, optional) ----------
// Only for projects split into several TP lines (e.g. one per apartment plus
// an outdoor line). Without lines everything behaves as a single line with
// the PA prefix typed in next to "PA automatisch zuordnen" (default 1.1).
let KNX_LINES = [];

async function loadKnxLines() {
  KNX_LINES = await api(`/projects/${CURRENT_PROJECT}/lines`);
  renderKnxLines();
  updatePaPrefixFields();
}

function renderKnxLines() {
  const el = document.getElementById('knx-lines');
  if (!el) return;
  if (!KNX_LINES.length) {
    el.innerHTML = '<p class="muted" style="margin:0;">Keine eigenen Linien — das Projekt ist eine Linie (Standard 1.1). Nur nötig, wenn die Anlage über Linienkoppler in mehrere Linien geteilt wird, z.B. eine Linie je Wohnung.</p>';
    return;
  }
  el.innerHTML = `<table class="data-table"><thead><tr>
      <th>Linie</th><th>Name</th><th class="num">Geräte</th><th>Hinweise</th><th class="actions"></th>
    </tr></thead><tbody>
    ${KNX_LINES.map(l => `<tr>
      <td class="strong">${l.address}${l.is_default ? ' <span class="muted" style="font-weight:normal;">(Standard)</span>' : ''}</td>
      <td>${escapeHtml(l.name || '')}</td>
      <td class="num">${l.device_count}</td>
      <td>${l.warnings.length ? l.warnings.map(w => `<span class="pill" style="border-color:var(--warn); color:var(--warn);">${escapeHtml(w)}</span>`).join(' ') : '<span class="muted">✓</span>'}</td>
      <td class="actions">
        <button class="btn secondary small" onclick="editKnxLine(${l.id})">Bearbeiten</button>
        <button class="btn danger small" onclick="deleteKnxLine(${l.id})">Löschen</button>
      </td>
    </tr>`).join('')}
    </tbody></table>
    <p class="muted" style="margin:6px 0 0;">Geräte ohne eigene Zuordnung zählen zur Standardlinie (der ersten). Linienkoppler und Busspannungsversorgungen werden an ihrer Katalog-Beschreibung erkannt ("Koppler"/"Coupler", "Spannungsversorgung"/"PowerSupply"). Max. 64 Geräte pro Linie ohne Linienverstärker.</p>`;
}

function readLineForm(prefix) {
  const area = parseInt(document.getElementById(`${prefix}-area`).value, 10);
  const line = parseInt(document.getElementById(`${prefix}-line`).value, 10);
  const name = document.getElementById(`${prefix}-name`).value.trim();
  if (Number.isNaN(area) || Number.isNaN(line)) { showToast('Bereich und Linie sind erforderlich', 'warning'); return null; }
  return {area, line, name};
}

async function addKnxLine() {
  const body = readLineForm('kl-new');
  if (!body) return;
  try {
    await api(`/projects/${CURRENT_PROJECT}/lines`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  } catch (e) { return showToast(e.message, 'warning'); }
  ['kl-new-line', 'kl-new-name'].forEach(id => { document.getElementById(id).value = ''; });
  await renderFloors();
}

async function editKnxLine(id) {
  const l = KNX_LINES.find(l => l.id === id);
  const modal = openModal(`
    <h3>Linie bearbeiten</h3>
    <div class="row mobile-fields">
      <input type="number" id="kl-edit-area" min="0" max="15" title="Bereich" value="${l.area}">
      <input type="number" id="kl-edit-line" min="0" max="15" title="Linie" value="${l.line}">
      <input type="text" id="kl-edit-name" class="flex-input" placeholder="Name, z.B. Wohnung EG">
    </div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>`, { wide: true });
  document.getElementById('kl-edit-name').value = l.name || '';
  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') modal.close();
    if (action !== 'save') return;
    const body = readLineForm('kl-edit');
    if (!body) return;
    try {
      await api(`/lines/${id}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    } catch (e) { return showToast(e.message, 'warning'); }
    modal.close();
    await renderFloors();
  });
}

async function deleteKnxLine(id) {
  const l = KNX_LINES.find(l => l.id === id);
  if (!(await showConfirm(`Linie ${l.address}${l.name ? ` "${l.name}"` : ''} löschen?\n\nGeschosse, Räume und Aktoren auf dieser Linie fallen auf die Standardlinie zurück. Bereits vergebene physikalische Adressen bleiben unverändert.`, {danger: true, confirmLabel: 'Löschen'}))) return;
  await api(`/lines/${id}`, {method: 'DELETE'});
  await renderFloors();
}

// <select> for a floor/room/actuator - empty value = inherit.
function lineSelectHtml(currentId, inheritLabel, onchange) {
  if (!KNX_LINES.length) return '';
  return `<select class="line-select" onchange="${onchange}" title="KNX-Linie">
    <option value="">${inheritLabel}</option>
    ${KNX_LINES.map(l => `<option value="${l.id}"${l.id === currentId ? ' selected' : ''}>Linie ${l.address}${l.name ? ` ${escapeHtml(l.name)}` : ''}</option>`).join('')}
  </select>`;
}

async function setLine(kind, id, value) {
  await api(`/${kind}/${id}/line`, {method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({line_id: value ? parseInt(value, 10) : null})});
  await loadKnxLines();  // device counts per line changed
}

// With lines, "PA automatisch zuordnen" numbers each line on its own - the
// single prefix field would only confuse, so it's replaced by a hint.
function updatePaPrefixFields() {
  ['pa-prefix-circuit-list', 'pa-prefix-device-planning'].forEach(id => {
    const input = document.getElementById(id);
    if (!input) return;
    input.style.display = KNX_LINES.length ? 'none' : '';
    let hint = document.getElementById(id + '-hint');
    if (!hint) {
      hint = document.createElement('span');
      hint.id = id + '-hint';
      hint.className = 'muted';
      hint.textContent = 'je Linie';
      hint.title = 'Das Projekt hat mehrere KNX-Linien (Gebäudestruktur) - jede Linie wird mit ihrer eigenen Bereich.Linie-Adresse nummeriert.';
      input.after(hint);
    }
    hint.style.display = KNX_LINES.length ? '' : 'none';
  });
}
