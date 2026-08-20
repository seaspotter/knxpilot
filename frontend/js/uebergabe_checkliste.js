// ---------- Übergabe-Checkliste (project sub-tab) ----------
// Digital handover checklist - 3-way status (Ja/Nein/Nicht nötig) plus a
// Bemerkungen note per item, persisted via the same checklist_status
// endpoints as the Funktionscheckliste. Unlike that tab, status clicks DO
// trigger a full section re-render here (matching Klärungsliste's
// established pattern) since this list is short (~29 items total, not
// every room × every function) - no scroll-jump concern.
let UEBERGABE_SECTIONS = [];
let UEBERGABE_STATUS = {};
let UEBERGABE_SIGNATURES = {};

async function loadUebergabeForCurrentProject() {
  const [sections, statusMap, signatures] = await Promise.all([
    api('/uebergabe-checklist-sections'),
    api(`/projects/${CURRENT_PROJECT}/checklist-status`),
    api(`/projects/${CURRENT_PROJECT}/signatures`),
  ]);
  UEBERGABE_SECTIONS = sections;
  UEBERGABE_STATUS = statusMap;
  UEBERGABE_SIGNATURES = signatures;
  renderUebergabe();
}

function renderUebergabe() {
  const container = document.getElementById('uebergabe-content');
  container.innerHTML = UEBERGABE_SECTIONS.map(sec => `
    <div class="floor-card">
      <b>${sec.section}</b>
      ${sec.items.map(item => renderUebergabeItem(item)).join('')}
    </div>
  `).join('') + renderSignatures();
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

// ---------- Digital signatures ----------
// Captured via an HTML canvas signature pad instead of printing the PDF
// and signing on paper - editable/re-signable and deletable at any time.
// Embedded into both this PDF export and the Dokumentation export
// (backend/routers/checkliste.py's build_signature_row()).
const UEB_SIGNATURE_ROLES = [['systemintegrator', 'Systemintegrator'], ['kunde', 'Kunde/Betreiber']];

function renderSignatures() {
  return `
    <div class="floor-card">
      <b>Unterschriften</b>
      <div class="row" style="gap:20px; flex-wrap:wrap; margin-top:8px; align-items:flex-start;">
        ${UEB_SIGNATURE_ROLES.map(([role, label]) => renderSignatureBlock(role, label)).join('')}
      </div>
    </div>
  `;
}

function renderSignatureBlock(role, label) {
  const entry = UEBERGABE_SIGNATURES[role];
  if (!entry) {
    return `
      <div style="min-width:200px;">
        <div class="muted" style="margin-bottom:4px;">${label}</div>
        <button class="btn secondary small" onclick="openSignatureModal('${role}', '${label}')">Unterschreiben</button>
      </div>
    `;
  }
  const when = new Date(entry.signed_at).toLocaleString('de-DE');
  const imgUrl = `/api/projects/${CURRENT_PROJECT}/signatures/${role}/image?t=${encodeURIComponent(entry.signed_at)}`;
  return `
    <div style="min-width:200px;">
      <div class="muted" style="margin-bottom:4px;">${label}</div>
      <img src="${imgUrl}" alt="Unterschrift ${label}"
        style="max-width:220px; max-height:80px; background:#fff; border:1px solid var(--border); border-radius:6px; display:block;">
      <div class="muted" style="font-size:12px; margin-top:4px;">Unterschrieben am ${when}</div>
      <div class="row" style="gap:6px; margin-top:6px;">
        <button class="btn secondary small" onclick="openSignatureModal('${role}', '${label}')">Neu unterschreiben</button>
        <button class="btn danger small" onclick="deleteUebergabeSignature('${role}', '${label}')">Löschen</button>
      </div>
    </div>
  `;
}

function openSignatureModal(role, label) {
  const modal = openModal(`
    <h3>Unterschrift — ${label}</h3>
    <canvas id="sig-canvas" style="width:100%; height:200px; border:1px solid var(--border); border-radius:6px; touch-action:none; background:#fff; display:block;"></canvas>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="clear">Löschen</button>
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>
  `, { wide: true });

  const canvas = modal.overlay.querySelector('#sig-canvas');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let cssWidth = 0, cssHeight = 0;

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    cssWidth = rect.width;
    cssHeight = rect.height;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx.scale(dpr, dpr);
    ctx.lineWidth = 2.2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0f172a';
  }
  resizeCanvas();

  let drawing = false, lastX = 0, lastY = 0, hasDrawn = false;
  function pos(ev) {
    const rect = canvas.getBoundingClientRect();
    return [ev.clientX - rect.left, ev.clientY - rect.top];
  }
  canvas.addEventListener('pointerdown', (ev) => {
    drawing = true;
    hasDrawn = true;
    [lastX, lastY] = pos(ev);
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', (ev) => {
    if (!drawing) return;
    const [x, y] = pos(ev);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.stroke();
    [lastX, lastY] = [x, y];
  });
  const stopDrawing = () => { drawing = false; };
  canvas.addEventListener('pointerup', stopDrawing);
  canvas.addEventListener('pointerleave', stopDrawing);

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'clear') {
      ctx.clearRect(0, 0, cssWidth, cssHeight);
      hasDrawn = false;
    }
    if (action === 'cancel') modal.close();
    if (action === 'save') {
      if (!hasDrawn) { showToast('Bitte zuerst unterschreiben.', 'warning'); return; }
      const dataUrl = canvas.toDataURL('image/png');
      const r = await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {
        method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({image: dataUrl}),
      });
      UEBERGABE_SIGNATURES[role] = {signed_at: r.signed_at};
      modal.close();
      renderUebergabe();
    }
  });
}

async function deleteUebergabeSignature(role, label) {
  const ok = await showConfirm(`Unterschrift von ${label} wirklich löschen?`, {danger: true});
  if (!ok) return;
  await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {method: 'DELETE'});
  delete UEBERGABE_SIGNATURES[role];
  renderUebergabe();
}
