// ---------- Übersicht (project sub-tab) ----------
function goToSubtab(name) {
  document.querySelector(`#workspace-subnav button[data-subtab="${name}"]`).click();
}

async function loadUebersichtForCurrentProject() {
  const [tree, preview, circuits, deviceSummary, klaerungen, verteiler, checklistStatus, uebergabeSections, central] = await Promise.all([
    api(`/projects/${CURRENT_PROJECT}/tree`),
    api(`/projects/${CURRENT_PROJECT}/preview`),
    api(`/projects/${CURRENT_PROJECT}/circuits`),
    api(`/projects/${CURRENT_PROJECT}/device-summary`),
    api(`/projects/${CURRENT_PROJECT}/klaerungen`),
    api(`/projects/${CURRENT_PROJECT}/verteiler`),
    api(`/projects/${CURRENT_PROJECT}/checklist-status`),
    api('/uebergabe-checklist-sections'),
    api(`/projects/${CURRENT_PROJECT}/central-functions-checklist`),
  ]);

  const floorCount = tree.floors.length;
  const roomCount = tree.floors.reduce((sum, f) => sum + f.rooms.length, 0);
  const pointCount = tree.floors.reduce((sum, f) => sum + f.rooms.reduce((s, r) => s + r.points.length, 0), 0);

  const gaCount = preview.main_groups.reduce((sum, m) => sum + m.middles.reduce((s, mid) => s + mid.subs.length, 0), 0);

  const assignedCount = circuits.filter(c => c.assignment).length;
  const totalCircuits = circuits.length;

  const totalDevices = deviceSummary.reduce((sum, d) => sum + d.total, 0);

  const openKlaerungen = klaerungen.filter(k => k.status === 'offen').length;

  // Funktionscheckliste totals - same per-room fetch pattern as
  // funktionscheckliste.js's own loader, just counting instead of rendering.
  let fcTotal = 0, fcChecked = 0;
  const roomChecklists = await Promise.all(
    tree.floors.flatMap(f => f.rooms).map(r => api(`/rooms/${r.id}/function-checklist`))
  );
  for (const byCategory of roomChecklists) {
    for (const items of Object.values(byCategory)) {
      for (const item of items) {
        fcTotal++;
        if (checklistStatus[item.key]?.status === 'ok') fcChecked++;
      }
    }
  }
  for (const [, items] of central) {
    for (const item of items) {
      fcTotal++;
      if (checklistStatus[item.key]?.status === 'ok') fcChecked++;
    }
  }

  const uebergabeTotal = uebergabeSections.reduce((sum, sec) => sum + sec.items.length, 0);
  const uebergabeAnswered = uebergabeSections.reduce(
    (sum, sec) => sum + sec.items.filter(it => checklistStatus[it.key]?.status).length, 0
  );

  const cards = [
    {
      subtab: 'struktur',
      title: 'Gebäudestruktur',
      body: `${floorCount} Geschosse · ${roomCount} Räume`,
    },
    {
      subtab: 'funktionen',
      title: 'Funktionen',
      body: pointCount ? `${pointCount} Punkte definiert` : 'Noch keine Punkte definiert',
    },
    {
      subtab: 'gruppenadressen',
      title: 'Gruppenadressen',
      body: gaCount ? `${gaCount} Gruppenadressen` : 'Noch keine Gruppenadressen',
    },
    {
      subtab: 'abgangsliste',
      title: 'Abgangsliste',
      body: totalCircuits ? `${assignedCount} / ${totalCircuits} Abgänge zugeordnet` : 'Noch keine Abgänge',
      warn: assignedCount < totalCircuits,
    },
    {
      subtab: 'geraeteplanung',
      title: 'Geräteplanung',
      body: totalDevices ? `${totalDevices} Geräte geplant` : 'Noch keine Geräte geplant',
    },
    {
      subtab: 'verteilerplanung',
      title: 'Verteilerplanung',
      body: verteiler.length ? `${verteiler.length} Verteiler angelegt` : 'Noch keine Verteiler angelegt',
    },
    {
      subtab: 'pflichtenheft',
      title: 'Pflichtenheft',
      body: 'Frühe Leistungsbeschreibung (PDF)',
    },
    {
      subtab: 'funktionscheckliste',
      title: 'Funktionscheckliste',
      body: fcTotal ? `${fcChecked} / ${fcTotal} Funktionen getestet` : 'Noch keine Funktionen geplant',
    },
    {
      subtab: 'uebergabe',
      title: 'Übergabe-Checkliste',
      body: `${uebergabeAnswered} / ${uebergabeTotal} Punkte beantwortet`,
    },
    {
      subtab: 'klaerungsliste',
      title: 'Klärungsliste',
      body: openKlaerungen ? `${openKlaerungen} offene Einträge` : 'Keine offenen Einträge',
      warn: openKlaerungen > 0,
    },
    {
      subtab: 'dokumentation',
      title: 'Dokumentation',
      body: 'Abschlussdokumentation (PDF)',
    },
  ];

  document.getElementById('uebersicht-cards').innerHTML = cards.map(c => `
    <div class="card stat-card" onclick="goToSubtab('${c.subtab}')">
      <h4>${c.title}</h4>
      <p class="${c.warn ? '' : 'muted'}" style="margin:0; ${c.warn ? 'color:var(--warn);' : ''}">${c.body}</p>
    </div>
  `).join('');

  await loadProjectFiles();
}

// ---------- Dateien (project files) ----------
async function loadProjectFiles() {
  const files = await api(`/projects/${CURRENT_PROJECT}/files`);
  const ul = document.getElementById('project-files-list');
  ul.innerHTML = files.map(f => `
    <li>
      <div><b>${f.filename}</b> <span class="pill">${humanFileSize(f.size_bytes)}</span> <span class="pill">${new Date(f.uploaded_at).toLocaleDateString('de-DE')}</span></div>
      <div>
        <button class="btn secondary small" onclick="downloadProjectFile(${f.id})">Herunterladen</button>
        <button class="btn danger small" onclick="deleteProjectFile(${f.id})">Löschen</button>
      </div>
    </li>
  `).join('') || '<li class="muted">Noch keine Dateien</li>';
}

function downloadProjectFile(id) {
  window.location.href = `/api/project-files/${id}/download`;
}

async function uploadProjectFile() {
  const input = document.getElementById('project-file-upload');
  const file = input.files[0];
  if (!file) return showToast('Zuerst eine Datei auswählen', 'warning');
  const formData = new FormData();
  formData.append('file', file);
  try {
    await api(`/projects/${CURRENT_PROJECT}/files`, {method: 'POST', body: formData});
  } catch (e) {
    return showToast(e.message, 'error');
  }
  input.value = '';
  await loadProjectFiles();
}

async function deleteProjectFile(id) {
  if (!(await showConfirm('Diese Datei löschen?', {danger: true}))) return;
  await api(`/project-files/${id}`, {method: 'DELETE'});
  await loadProjectFiles();
}
