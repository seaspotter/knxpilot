// ---------- Gruppenadressen (project sub-tab): GA tree preview / CSV export ----------
async function previewGA() {
  document.getElementById('gen-error').textContent = '';
  try {
    const data = await api(`/projects/${CURRENT_PROJECT}/preview`);
    const el = document.getElementById('ga-preview');
    el.innerHTML = data.main_groups.map(m => {
      const totalSubs = m.middles.reduce((sum, mid) => sum + mid.subs.length, 0);
      return `
      <details class="tree-main" open>
        <summary><span class="main">${m.main} ${m.name}</span> <span class="muted">(${totalSubs})</span></summary>
        ${m.middles.map(mid => `
          <details class="tree-middle">
            <summary><span class="middle">${m.main}/${mid.middle} ${mid.name}</span> <span class="muted">(${mid.subs.length})</span></summary>
            <div class="tree-subs">
              ${mid.subs.map(s => `
                <div class="tree-sub-row">
                  <span class="${s.name.endsWith('res') ? 'res' : 'sub'}">${m.main}/${mid.middle}/${s.sub} ${s.name}</span>${s.dpt ? ` <span class="addr">(${s.dpt})</span>` : ''}
                </div>`).join('')}
            </div>
          </details>`).join('')}
      </details>`;
    }).join('');
  } catch (e) {
    document.getElementById('gen-error').textContent = e.message;
  }
}

function expandAllGaTree(open) {
  document.querySelectorAll('#ga-preview details').forEach(d => { d.open = open; });
}

function downloadCSV() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export.csv`;
  // The download itself becomes the new baseline (server side) - refresh the
  // changes card once it has gone through.
  setTimeout(loadGaChanges, 1500);
}

// ---------- Änderungen seit dem letzten ETS-Export ----------
async function loadGaChanges() {
  const el = document.getElementById('ga-changes');
  let c;
  try {
    c = await api(`/projects/${CURRENT_PROJECT}/ga-changes`);
  } catch (e) {
    el.innerHTML = `<p class="error">${escapeHtml(e.message)}</p>`;
    return;
  }
  if (!c.exported_at) {
    el.innerHTML = `<p class="muted">Für dieses Projekt ist noch kein ETS-Export erfasst. Beim nächsten <b>CSV für ETS6 herunterladen</b> merkt sich KNXpilot den Stand und zeigt danach hier, was in ETS noch nachzutragen ist. Ist das ETS-Projekt bereits auf dem aktuellen Stand, den Stand einfach als übernommen markieren.</p>`;
    return;
  }
  const when = new Date(c.exported_at).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});
  const count = c.added.length + c.changed.length + c.moved.length + c.removed.length;
  if (!count) {
    el.innerHTML = `<p class="muted">✓ Keine Änderungen seit dem Export am ${when} — das ETS-Projekt ist auf dem aktuellen Stand.</p>`;
    return;
  }
  const dpt = d => d ? `<span class="muted">${escapeHtml(d)}</span>` : '';
  const section = (title, hint, head, rows) => rows.length ? `
    <h4 style="margin:12px 0 4px;">${title} <span class="pill">${rows.length}</span> <span class="muted" style="font-weight:normal;">${hint}</span></h4>
    <table class="data-table"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>` : '';
  // Order = the order to work through it in ETS: moves first (from the
  // highest target address down, so no address is taken yet), then the rest.
  el.innerHTML = `
    <p class="muted">Seit dem letzten Export am ${when} — das ist in ETS noch nachzutragen, am besten in dieser Reihenfolge:</p>
    ${section('1. Verschoben', 'in ETS die Adresse ändern (Verknüpfungen bleiben erhalten) — von oben nach unten abarbeiten', ['Name', 'Bisher', 'Neu'],
      c.moved.map(r => `<tr><td>${escapeHtml(r.name)}</td><td class="muted">${r.old_address}</td><td class="strong">${r.address}</td></tr>`))}
    ${section('2. Neu', 'in ETS anlegen', ['Adresse', 'Name', 'DPT'],
      c.added.map(r => `<tr><td class="strong">${r.address}</td><td>${escapeHtml(r.name)}</td><td>${dpt(r.dpt)}</td></tr>`))}
    ${section('3. Geändert', 'in ETS umbenennen / DPT anpassen', ['Adresse', 'Bisher', 'Neu'],
      c.changed.map(r => `<tr><td class="strong">${r.address}</td><td class="muted">${escapeHtml(r.old_name)} ${r.old_dpt !== r.dpt ? dpt(r.old_dpt) : ''}</td><td>${escapeHtml(r.name)} ${r.old_dpt !== r.dpt ? dpt(r.dpt) : ''}</td></tr>`))}
    ${section('4. Entfernt', 'in ETS löschen', ['Adresse', 'Name', 'DPT'],
      c.removed.map(r => `<tr class="muted-row"><td class="strong">${r.address}</td><td>${escapeHtml(r.name)}</td><td>${dpt(r.dpt)}</td></tr>`))}`;
}

async function markGaExported() {
  if (!(await showConfirm('Den aktuellen Stand der Gruppenadressen als in ETS übernommen markieren? Die Liste der Änderungen beginnt danach von vorn.'))) return;
  await api(`/projects/${CURRENT_PROJECT}/ga-snapshot`, {method: 'POST'});
  showToast('Als in ETS übernommen markiert', 'success');
  await loadGaChanges();
}
