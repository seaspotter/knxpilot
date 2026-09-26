// ---------- Time tracking ("Zeiterfassung": header timer + global tab) ----------
// Internal only - never part of any project export/documentation (its own
// timesheet PDF aside). The tab is rendered server-side with htmx
// (backend/templates/time_tracking/, /hx/time-tracking... endpoints); this
// file keeps what has to live in the browser: the header timer with its
// ticking clock, loading the tab, and the PDF download. The backend snaps
// every start/end to the grid set in Setup -> Zeiterfassung (1/15/30 min).
let RUNNING_TIMER = null;
let TIMER_TICK = null;
let TIME_TRACKING_ENABLED = false;
let TIME_TRACKING_ROUNDING = 15;

// Called by loadCompanyProfile() (setup.js) on page load and after saving.
function applyTimeTrackingSettings(c) {
  TIME_TRACKING_ENABLED = !!c.time_tracking_enabled;
  TIME_TRACKING_ROUNDING = c.time_tracking_rounding_minutes || 15;
  const navBtn = document.querySelector('nav button[data-tab="time-tracking"]');
  navBtn.style.display = TIME_TRACKING_ENABLED ? '' : 'none';
  if (!TIME_TRACKING_ENABLED && navBtn.classList.contains('active')) {
    document.querySelector('nav button[data-tab="projects"]').click();
  }
  renderTimerWidget();
}

function loadTimeTrackingTab() {
  return htmx.ajax('GET', '/hx/time-tracking', {target: '#time-tracking-root', swap: 'innerHTML'});
}

function timeTrackingTabOpen() {
  return document.getElementById('tab-time-tracking').classList.contains('active');
}

async function loadRunningTimer() {
  RUNNING_TIMER = await api('/time-entries/running');
  renderTimerWidget();
}

function formatElapsed(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = Math.floor(sec % 60);
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Header widget: shows Start while a project is open, the running clock +
// Stop while a timer runs (even with a different/no project open).
function renderTimerWidget() {
  const el = document.getElementById('tt-timer');
  if (!el) return;
  clearInterval(TIMER_TICK);
  if (RUNNING_TIMER) {
    const otherProject = RUNNING_TIMER.project_id !== CURRENT_PROJECT;
    // started_at is already snapped to the grid - may even lie a few
    // minutes in the future (12:08 -> 12:15), hence the clamp to 0 below.
    const since = new Date(RUNNING_TIMER.started_at).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
    el.innerHTML = `
      <span class="muted">seit ${since}</span>
      <span class="tt-clock" id="tt-clock" title="${TIME_TRACKING_ROUNDING === 1 ? 'Minutengenau' : `Start/Stopp werden auf ${TIME_TRACKING_ROUNDING} Min. gerundet`}">⏱ </span>
      ${otherProject ? `<span class="muted">${escapeHtml(RUNNING_TIMER.project_name)}</span>` : ''}
      <button class="btn danger small" onclick="stopTimer()">■ Stopp</button>`;
    const tick = () => {
      const sec = (Date.now() - new Date(RUNNING_TIMER.started_at).getTime()) / 1000;
      document.getElementById('tt-clock').textContent = '⏱ ' + formatElapsed(Math.max(0, sec));
    };
    tick();
    TIMER_TICK = setInterval(tick, 1000);
    el.style.display = '';
  } else if (CURRENT_PROJECT && TIME_TRACKING_ENABLED) {
    el.innerHTML = `<button class="btn secondary small" onclick="startTimer()" title="Zeiterfassung für dieses Projekt starten">▶ Start</button>`;
    el.style.display = '';
  } else {
    el.innerHTML = '';
    el.style.display = 'none';
  }
}

// The tab's list re-fetches itself on this event (see tab.html).
function refreshTimeEntryList() {
  if (timeTrackingTabOpen()) htmx.trigger(document.body, 'time-entries-changed');
}

async function startTimer() {
  if (!CURRENT_PROJECT) return;
  try {
    await api('/time-entries/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({project_id: CURRENT_PROJECT})});
  } catch (e) {
    showToast(e.message, 'warning');
  }
  await loadRunningTimer();
  refreshTimeEntryList();
}

async function stopTimer() {
  await api('/time-entries/stop', {method:'POST'});
  await loadRunningTimer();
  refreshTimeEntryList();
}

// Another browser tab may have started/stopped the timer meanwhile.
window.addEventListener('focus', () => { loadRunningTimer().catch(() => {}); });

// Timesheet PDF of the current filter. Passes the browser's time zone so
// the server (usually UTC in the container) renders local times.
function exportTimeEntriesPdf() {
  // Finished entries have an edit button - without any, the server would answer 404.
  if (!document.querySelector('#tt-list button[hx-get$="/edit"]')) return showToast('Keine abgeschlossenen Einträge zum Exportieren', 'warning');
  const filters = new FormData(document.getElementById('tt-filters'));
  const params = new URLSearchParams({
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    offset: new Date().getTimezoneOffset(),
  });
  if (filters.get('project_id')) params.set('project_id', filters.get('project_id'));
  if (filters.get('invoiced')) params.set('invoiced', filters.get('invoiced') === '1' ? 'true' : 'false');
  window.location.href = '/api/time-entries/export.pdf?' + params;
}
