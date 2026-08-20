// ---------- Übergabe-Checkliste (project sub-tab) ----------
// Digital handover checklist - 3-way status (Ja/Nein/Nicht nötig) plus a
// Bemerkungen note per item, persisted via the same checklist_status
// endpoints as the Funktionscheckliste. Unlike that tab, status clicks DO
// trigger a full section re-render here (matching Klärungsliste's
// established pattern) since this list is short (~29 items total, not
// every room × every function) - no scroll-jump concern.
let UEBERGABE_SECTIONS = [];
let UEBERGABE_STATUS = {};

async function loadUebergabeForCurrentProject() {
  const [sections, statusMap] = await Promise.all([
    api('/uebergabe-checklist-sections'),
    api(`/projects/${CURRENT_PROJECT}/checklist-status`),
  ]);
  UEBERGABE_SECTIONS = sections;
  UEBERGABE_STATUS = statusMap;
  renderUebergabe();
}

function renderUebergabe() {
  const container = document.getElementById('uebergabe-content');
  container.innerHTML = UEBERGABE_SECTIONS.map(sec => `
    <div class="floor-card">
      <b>${sec.section}</b>
      ${sec.items.map(item => renderUebergabeItem(item)).join('')}
    </div>
  `).join('');
}

const UEB_STATUS_LABEL = {ja: 'Ja', nein: 'Nein', nicht_noetig: 'Nicht nötig'};
const UEB_STATUS_CLASS = {ja: 'status-geklaert', nein: 'status-abgelehnt', nicht_noetig: 'status-offen'};
const UEB_STATUS_OPTIONS = ['ja', 'nein', 'nicht_noetig'];

function renderUebergabeItem(item) {
  const entry = UEBERGABE_STATUS[item.key] || {status: '', note: ''};
  const buttons = UEB_STATUS_OPTIONS.filter(v => v !== entry.status)
    .map(v => `<button class="btn secondary small" onclick="setUebergabeStatus('${item.key}', '${v}')">${UEB_STATUS_LABEL[v]}</button>`)
    .join('');
  return `
    <div style="padding:8px 0; border-bottom:1px solid var(--border);">
      <div class="row" style="justify-content:space-between;">
        <div>
          <span>${item.text}</span>
          ${entry.status ? `<span class="pill ${UEB_STATUS_CLASS[entry.status]}">${UEB_STATUS_LABEL[entry.status]}</span>` : ''}
        </div>
        <div class="row" style="gap:6px; margin:0;">${buttons}</div>
      </div>
      <input type="text" class="flex-input" placeholder="Bemerkungen"
        value="${escapeAttr(entry.note)}"
        onblur="saveUebergabeNote('${item.key}', this.value)"
        style="margin-top:6px; width:100%;">
    </div>
  `;
}

async function setUebergabeStatus(key, status) {
  const currentNote = UEBERGABE_STATUS[key]?.note || '';
  await api(`/projects/${CURRENT_PROJECT}/checklist-status/${encodeURIComponent(key)}`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status, note: currentNote}),
  });
  UEBERGABE_STATUS[key] = {status, note: currentNote};
  renderUebergabe();
}

async function saveUebergabeNote(key, note) {
  const currentStatus = UEBERGABE_STATUS[key]?.status || '';
  await api(`/projects/${CURRENT_PROJECT}/checklist-status/${encodeURIComponent(key)}`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status: currentStatus, note}),
  });
  UEBERGABE_STATUS[key] = {status: currentStatus, note};
  // Local-cache-only, no re-render (matches saveKlAntwortInline's pattern
  // in klaerungsliste.js) - avoids losing focus/cursor on blur-triggered save.
}

function downloadUebergabeChecklist() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-uebergabe-checkliste.pdf`;
}
