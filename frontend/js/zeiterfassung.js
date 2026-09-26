// ---------- Zeiterfassung (header timer + global tab) ----------
// Internal only - never part of any project export/documentation (its own
// Stundennachweis PDF aside). The backend snaps every start/end to the
// nearest mark of the grid set in Setup -> Zeiterfassung (1/15/30 min; with
// 15: Start 12:04 -> 12:00, Stop 12:55 -> 13:00), so the manual-entry form
// only offers times on that grid too.
let RUNNING_TIMER = null;
let TIME_ENTRIES = [];
let TIMER_TICK = null;
let ZEIT_ENABLED = false;
let ZEIT_ROUNDING = 15;

// Called by loadCompanyProfile() (setup.js) on page load and after saving.
function applyZeiterfassungSettings(c) {
  ZEIT_ENABLED = !!c.zeiterfassung_enabled;
  ZEIT_ROUNDING = c.zeiterfassung_rounding_minutes || 15;
  const navBtn = document.querySelector('nav button[data-tab="zeiterfassung"]');
  navBtn.style.display = ZEIT_ENABLED ? '' : 'none';
  if (!ZEIT_ENABLED && navBtn.classList.contains('active')) {
    document.querySelector('nav button[data-tab="projects"]').click();
  }
  document.getElementById('zeit-rounding-hint').textContent = ZEIT_ROUNDING === 1
    ? 'Zeiten werden minutengenau erfasst.'
    : `Start und Stopp werden auf die nächsten ${ZEIT_ROUNDING} Minuten gerundet (z.B. 12:04 → 12:00, 12:55 → 13:00), mindestens ${ZEIT_ROUNDING} Minuten je Eintrag.`;
  renderTimerWidget();
}

async function loadRunningTimer() {
  RUNNING_TIMER = await api('/time-entries/running');
  renderTimerWidget();
}

function formatElapsed(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = Math.floor(sec % 60);
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatHours(minutes) {
  const h = Math.floor(minutes / 60), m = minutes % 60;
  return `${h}:${String(m).padStart(2, '0')} h`;
}

// Header widget: shows Start while a project is open, the running clock +
// Stop while a timer runs (even with a different/no project open).
function renderTimerWidget() {
  const el = document.getElementById('zeit-timer');
  if (!el) return;
  clearInterval(TIMER_TICK);
  if (RUNNING_TIMER) {
    const otherProject = RUNNING_TIMER.project_id !== CURRENT_PROJECT;
    // started_at is already snapped to the quarter hour - may even lie a few
    // minutes in the future (12:08 -> 12:15), hence the clamp to 0 below.
    const since = new Date(RUNNING_TIMER.started_at).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
    el.innerHTML = `
      <span class="muted">seit ${since}</span>
      <span class="zeit-clock" id="zeit-clock" title="${ZEIT_ROUNDING === 1 ? 'Minutengenau' : `Start/Stopp werden auf ${ZEIT_ROUNDING} Min. gerundet`}">⏱ </span>
      ${otherProject ? `<span class="muted">${escapeHtml(RUNNING_TIMER.project_name)}</span>` : ''}
      <button class="btn danger small" onclick="stopTimer()">■ Stopp</button>`;
    const tick = () => {
      const sec = (Date.now() - new Date(RUNNING_TIMER.started_at).getTime()) / 1000;
      document.getElementById('zeit-clock').textContent = '⏱ ' + formatElapsed(Math.max(0, sec));
    };
    tick();
    TIMER_TICK = setInterval(tick, 1000);
    el.style.display = '';
  } else if (CURRENT_PROJECT && ZEIT_ENABLED) {
    el.innerHTML = `<button class="btn secondary small" onclick="startTimer()" title="Zeiterfassung für dieses Projekt starten">▶ Start</button>`;
    el.style.display = '';
  } else {
    el.innerHTML = '';
    el.style.display = 'none';
  }
}

async function startTimer() {
  if (!CURRENT_PROJECT) return;
  try {
    await api('/time-entries/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({project_id: CURRENT_PROJECT})});
  } catch (e) {
    showToast(e.message, 'warning');
  }
  await loadRunningTimer();
}

async function stopTimer() {
  await api('/time-entries/stop', {method:'POST'});
  await loadRunningTimer();
  if (document.getElementById('tab-zeiterfassung').classList.contains('active')) await loadTimeEntries();
}

// Another browser tab may have started/stopped the timer meanwhile.
window.addEventListener('focus', () => { loadRunningTimer().catch(() => {}); });

// ---------- Tab: list, totals, edit ----------
async function loadTimeEntries() {
  const sel = document.getElementById('zeit-project-filter');
  const current = sel.value;
  // Every entry, unfiltered, so the per-project totals and the filter list
  // also cover entries of since-deleted projects.
  TIME_ENTRIES = await api('/time-entries');
  const projects = new Map();
  TIME_ENTRIES.forEach(e => projects.set(String(e.project_id), e.project_name));
  PROJECTS_LIST.forEach(p => { if (!projects.has(String(p.id))) projects.set(String(p.id), p.name); });
  sel.innerHTML = '<option value="">Alle Projekte</option>' +
    [...projects.entries()].sort((a, b) => a[1].localeCompare(b[1]))
      .map(([id, name]) => `<option value="${id}">${escapeHtml(name)}</option>`).join('');
  sel.value = projects.has(current) ? current : '';
  renderTimeEntries();
}

function filteredTimeEntries() {
  const pid = document.getElementById('zeit-project-filter').value;
  const inv = document.getElementById('zeit-invoiced-filter').value;
  return TIME_ENTRIES.filter(e =>
    (!pid || String(e.project_id) === pid) && (inv === '' || e.invoiced === (inv === '1')));
}

async function setTimeEntriesInvoiced(ids, invoiced) {
  await api('/time-entries/invoiced', {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ids, invoiced})});
  await loadTimeEntries();
}

async function markShownTimeEntriesInvoiced() {
  const ids = filteredTimeEntries().filter(e => e.ended_at && !e.invoiced).map(e => e.id);
  if (!ids.length) return;
  if (!(await showConfirm(`${ids.length} Einträge als abgerechnet markieren?`))) return;
  await setTimeEntriesInvoiced(ids, true);
}

function renderTimeEntries() {
  const entries = filteredTimeEntries();
  const done = entries.filter(e => e.ended_at);
  const total = done.reduce((sum, e) => sum + e.billed_minutes, 0);
  document.getElementById('zeit-mark-invoiced-btn').style.display = done.some(e => !e.invoiced) ? '' : 'none';
  document.getElementById('zeit-filter-total').textContent = done.length ? `Summe: ${formatHours(total)}` : '';

  // Per-project totals (only when showing all projects).
  const totalsEl = document.getElementById('zeit-totals');
  if (!document.getElementById('zeit-project-filter').value && done.length) {
    const byProject = new Map();
    done.forEach(e => {
      const t = byProject.get(e.project_id) || {name: e.project_name, minutes: 0};
      t.minutes += e.billed_minutes;
      byProject.set(e.project_id, t);
    });
    totalsEl.innerHTML = `<h4>Summe je Projekt</h4>
      <table class="zeit-table"><thead><tr><th>Projekt</th><th class="num">Stunden</th></tr></thead><tbody>
      ${[...byProject.values()].sort((a, b) => a.name.localeCompare(b.name)).map(t =>
        `<tr><td>${escapeHtml(t.name)}</td><td class="num">${formatHours(t.minutes)}</td></tr>`).join('')}
      </tbody></table>`;
  } else {
    totalsEl.innerHTML = '';
  }

  const listEl = document.getElementById('zeit-entries');
  if (!entries.length) {
    listEl.innerHTML = `<p class="muted">${TIME_ENTRIES.length ? 'Keine Einträge für diese Auswahl.' : 'Noch keine Zeiten erfasst.'}</p>`;
    return;
  }
  const fmtDate = iso => new Date(iso).toLocaleDateString('de-DE', {weekday:'short', day:'2-digit', month:'2-digit', year:'numeric'});
  const fmtTime = iso => new Date(iso).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  listEl.innerHTML = `<h4>Einträge</h4>
    <table class="zeit-table"><thead><tr>
      <th>Datum</th><th>Projekt</th><th>Von</th><th>Bis</th><th class="num">Dauer</th><th>Notiz</th><th>Abgerechnet</th><th></th>
    </tr></thead><tbody>
    ${entries.map(e => `<tr>
      <td>${fmtDate(e.started_at)}</td>
      <td>${escapeHtml(e.project_name)}</td>
      <td>${fmtTime(e.started_at)}</td>
      <td>${e.ended_at ? fmtTime(e.ended_at) : '<span class="pill">läuft</span>'}</td>
      <td class="num" title="${e.ended_at ? `tatsächlich ${Math.round(e.raw_minutes)} Min.` : ''}">${e.ended_at ? formatHours(e.billed_minutes) : '—'}</td>
      <td>${escapeHtml(e.note || '')}</td>
      <td>${e.ended_at ? `<input type="checkbox" ${e.invoiced ? 'checked' : ''} onchange="setTimeEntriesInvoiced([${e.id}], this.checked)" title="Abgerechnet">` : ''}</td>
      <td class="zeit-actions">${e.ended_at ? `
        <button class="btn secondary small" onclick="openTimeEntryModal(${e.id})">Bearbeiten</button>
        <button class="btn danger small" onclick="deleteTimeEntry(${e.id})">Löschen</button>` : ''}</td>
    </tr>`).join('')}
    </tbody></table>`;
}

// ISO (UTC) -> {date: 'YYYY-MM-DD', time: 'HH:MM'} in browser local time,
// time rounded to the nearest grid mark (same rule as the backend).
function isoToGridParts(iso) {
  const step = ZEIT_ROUNDING * 60000;
  const d = new Date(Math.round(new Date(iso).getTime() / step) * step);
  const pad = n => String(n).padStart(2, '0');
  return {date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}`};
}

// Minutengenau: a plain time input; otherwise a dropdown of the grid's times.
function timeFieldHtml(id) {
  if (ZEIT_ROUNDING === 1) return `<input type="time" id="${id}">`;
  const times = Array.from({length: 1440 / ZEIT_ROUNDING}, (_, i) => {
    const m = i * ZEIT_ROUNDING;
    return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  });
  return `<select id="${id}">${times.map(t => `<option>${t}</option>`).join('')}</select>`;
}

function openTimeEntryModal(id = null) {
  const e = id ? TIME_ENTRIES.find(e => e.id === id) : null;
  const defaultProject = e ? e.project_id : (CURRENT_PROJECT || document.getElementById('zeit-project-filter').value);
  const now = new Date();
  const modal = openModal(`
    <h3>${e ? 'Eintrag bearbeiten' : 'Eintrag nachtragen'}</h3>
    <div class="row"><select id="te-project" class="flex-input-wide">
      ${PROJECTS_LIST.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('')}
    </select></div>
    <div class="row mobile-fields">
      <input type="date" id="te-date">
      <label class="muted">Von ${timeFieldHtml('te-start')}</label>
      <label class="muted">Bis ${timeFieldHtml('te-end')}</label>
    </div>
    <div class="row"><input type="text" id="te-note" class="flex-input-wide" placeholder="Notiz (optional)"></div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>`, { wide: true });

  document.getElementById('te-project').value = String(defaultProject || (PROJECTS_LIST[0] && PROJECTS_LIST[0].id) || '');
  const start = isoToGridParts(e ? e.started_at : new Date(now.getTime() - 3600000).toISOString());
  const end = isoToGridParts(e ? e.ended_at : now.toISOString());
  document.getElementById('te-date').value = start.date;
  document.getElementById('te-start').value = start.time;
  document.getElementById('te-end').value = end.time;
  document.getElementById('te-note').value = e ? e.note : '';

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') modal.close();
    if (action !== 'save') return;
    const project_id = parseInt(document.getElementById('te-project').value);
    const date = document.getElementById('te-date').value;
    const from = document.getElementById('te-start').value;
    const to = document.getElementById('te-end').value;
    if (!project_id || !date || !from || !to) return showToast('Projekt, Datum, Von und Bis sind erforderlich', 'warning');
    if (to === from) return showToast('Bis muss nach Von liegen', 'warning');
    const startDate = new Date(`${date}T${from}`);
    const endDate = new Date(`${date}T${to}`);
    if (to < from) endDate.setDate(endDate.getDate() + 1); // past midnight
    const body = JSON.stringify({
      project_id,
      started_at: startDate.toISOString(),
      ended_at: endDate.toISOString(),
      note: document.getElementById('te-note').value.trim(),
    });
    try {
      if (e) await api('/time-entries/' + e.id, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
      else await api('/time-entries', {method:'POST', headers:{'Content-Type':'application/json'}, body});
    } catch (err) {
      return showToast(err.message, 'warning');
    }
    modal.close();
    await loadTimeEntries();
  });
}

async function deleteTimeEntry(id) {
  if (!(await showConfirm('Diesen Zeiteintrag löschen?', {danger: true}))) return;
  await api('/time-entries/' + id, {method:'DELETE'});
  await loadTimeEntries();
}

// Stundennachweis PDF of the current filter. Passes the browser's time zone
// so the server (usually UTC in the container) renders local times.
function exportTimeEntriesPdf() {
  const entries = filteredTimeEntries().filter(e => e.ended_at);
  if (!entries.length) return showToast('Keine abgeschlossenen Einträge zum Exportieren', 'warning');
  const params = new URLSearchParams({
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    offset: new Date().getTimezoneOffset(),
  });
  const pid = document.getElementById('zeit-project-filter').value;
  if (pid) params.set('project_id', pid);
  const inv = document.getElementById('zeit-invoiced-filter').value;
  if (inv !== '') params.set('invoiced', inv === '1' ? 'true' : 'false');
  window.location.href = '/api/time-entries/export.pdf?' + params;
}
