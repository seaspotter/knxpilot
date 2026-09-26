// ---------- Zeiterfassung (header timer + global tab) ----------
// Internal only - never part of any export/documentation. Durations are
// rounded up to 15 min by the backend (billed_minutes); raw times stay editable.
let RUNNING_TIMER = null;
let TIME_ENTRIES = [];
let TIMER_TICK = null;

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
    el.innerHTML = `
      <span class="zeit-clock" id="zeit-clock" title="Läuft seit ${new Date(RUNNING_TIMER.started_at).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})} - wird auf volle 15 Min. aufgerundet">⏱ </span>
      ${otherProject ? `<span class="muted">${escapeHtml(RUNNING_TIMER.project_name)}</span>` : ''}
      <button class="btn danger small" onclick="stopTimer()">■ Stopp</button>`;
    const tick = () => {
      const sec = (Date.now() - new Date(RUNNING_TIMER.started_at).getTime()) / 1000;
      document.getElementById('zeit-clock').textContent = '⏱ ' + formatElapsed(Math.max(0, sec));
    };
    tick();
    TIMER_TICK = setInterval(tick, 1000);
    el.style.display = '';
  } else if (CURRENT_PROJECT) {
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
  return pid ? TIME_ENTRIES.filter(e => String(e.project_id) === pid) : TIME_ENTRIES;
}

function renderTimeEntries() {
  const entries = filteredTimeEntries();
  const done = entries.filter(e => e.ended_at);
  const total = done.reduce((sum, e) => sum + e.billed_minutes, 0);
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
    listEl.innerHTML = '<p class="muted">Noch keine Zeiten erfasst.</p>';
    return;
  }
  const fmtDate = iso => new Date(iso).toLocaleDateString('de-DE', {weekday:'short', day:'2-digit', month:'2-digit', year:'numeric'});
  const fmtTime = iso => new Date(iso).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  listEl.innerHTML = `<h4>Einträge</h4>
    <table class="zeit-table"><thead><tr>
      <th>Datum</th><th>Projekt</th><th>Von</th><th>Bis</th><th class="num">Dauer</th><th>Notiz</th><th></th>
    </tr></thead><tbody>
    ${entries.map(e => `<tr>
      <td>${fmtDate(e.started_at)}</td>
      <td>${escapeHtml(e.project_name)}</td>
      <td>${fmtTime(e.started_at)}</td>
      <td>${e.ended_at ? fmtTime(e.ended_at) : '<span class="pill">läuft</span>'}</td>
      <td class="num" title="${e.ended_at ? `tatsächlich ${Math.round(e.raw_minutes)} Min.` : ''}">${e.ended_at ? formatHours(e.billed_minutes) : '—'}</td>
      <td>${escapeHtml(e.note || '')}</td>
      <td class="zeit-actions">${e.ended_at ? `
        <button class="btn secondary small" onclick="openTimeEntryModal(${e.id})">Bearbeiten</button>
        <button class="btn danger small" onclick="deleteTimeEntry(${e.id})">Löschen</button>` : ''}</td>
    </tr>`).join('')}
    </tbody></table>`;
}

// ISO (UTC) <-> <input type="datetime-local"> value (browser local time).
function isoToLocalInput(iso) {
  const d = new Date(iso);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
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
      <label class="muted">Von <input type="datetime-local" id="te-start"></label>
      <label class="muted">Bis <input type="datetime-local" id="te-end"></label>
    </div>
    <div class="row"><input type="text" id="te-note" class="flex-input-wide" placeholder="Notiz (optional)"></div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>`, { wide: true });

  document.getElementById('te-project').value = String(defaultProject || (PROJECTS_LIST[0] && PROJECTS_LIST[0].id) || '');
  document.getElementById('te-start').value = isoToLocalInput(e ? e.started_at : new Date(now.getTime() - 3600000).toISOString());
  document.getElementById('te-end').value = isoToLocalInput(e ? e.ended_at : now.toISOString());
  document.getElementById('te-note').value = e ? e.note : '';

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') modal.close();
    if (action !== 'save') return;
    const project_id = parseInt(document.getElementById('te-project').value);
    const start = document.getElementById('te-start').value;
    const end = document.getElementById('te-end').value;
    if (!project_id || !start || !end) return showToast('Projekt, Von und Bis sind erforderlich', 'warning');
    const body = JSON.stringify({
      project_id,
      started_at: new Date(start).toISOString(),
      ended_at: new Date(end).toISOString(),
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

// Built client-side (not via window.location.href like the other exports)
// so dates/times come out in the browser's own time zone - the server
// container usually runs in UTC. Semicolon + decimal comma + BOM so it
// opens cleanly in a German Excel.
function exportTimeEntriesCsv() {
  const entries = filteredTimeEntries().filter(e => e.ended_at).slice().reverse();
  if (!entries.length) return showToast('Keine abgeschlossenen Einträge zum Exportieren', 'warning');
  const q = v => `"${String(v).replace(/"/g, '""')}"`;
  const hours = min => (min / 60).toFixed(2).replace('.', ',');
  const date = iso => new Date(iso).toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit', year:'numeric'});
  const time = iso => new Date(iso).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  const lines = [['Projekt', 'Datum', 'Von', 'Bis', 'Stunden (15-Min.-Takt)', 'Notiz'].map(q).join(';')];
  entries.forEach(e => lines.push(
    [e.project_name, date(e.started_at), time(e.started_at), time(e.ended_at), hours(e.billed_minutes), e.note || ''].map(q).join(';')
  ));
  lines.push('');
  const byProject = new Map();
  entries.forEach(e => byProject.set(e.project_name, (byProject.get(e.project_name) || 0) + e.billed_minutes));
  byProject.forEach((min, name) => lines.push([`Summe ${name}`, '', '', '', hours(min), ''].map(q).join(';')));
  if (byProject.size > 1) {
    lines.push([q('Summe gesamt'), '', '', '', q(hours(entries.reduce((s, e) => s + e.billed_minutes, 0))), ''].join(';'));
  }

  const pid = document.getElementById('zeit-project-filter').value;
  const label = pid ? entries[0].project_name.replace(/[^\wäöüÄÖÜß-]+/g, '_') : 'alle_projekte';
  const blob = new Blob(['﻿' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `zeiterfassung_${label}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
