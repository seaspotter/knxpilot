// ---------- Übersicht (project sub-tab) ----------
function goToSubtab(name) {
  document.querySelector(`#workspace-subnav button[data-subtab="${name}"]`).click();
}

async function loadUebersichtForCurrentProject() {
  const [tree, circuits, deviceSummary, klaerungen] = await Promise.all([
    api(`/projects/${CURRENT_PROJECT}/tree`),
    api(`/projects/${CURRENT_PROJECT}/circuits`),
    api(`/projects/${CURRENT_PROJECT}/device-summary`),
    api(`/projects/${CURRENT_PROJECT}/klaerungen`),
  ]);

  const floorCount = tree.floors.length;
  const roomCount = tree.floors.reduce((sum, f) => sum + f.rooms.length, 0);
  const pointCount = tree.floors.reduce((sum, f) => sum + f.rooms.reduce((s, r) => s + r.points.length, 0), 0);

  const assignedCount = circuits.filter(c => c.assignment).length;
  const totalCircuits = circuits.length;

  const totalDevices = deviceSummary.reduce((sum, d) => sum + d.total, 0);

  const openKlaerungen = klaerungen.filter(k => k.status === 'offen').length;

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
      subtab: 'pflichtenheft',
      title: 'Pflichtenheft',
      body: '→ Vorschau ansehen',
    },
    {
      subtab: 'klaerungsliste',
      title: 'Klärungsliste',
      body: openKlaerungen ? `${openKlaerungen} offene Einträge` : 'Keine offenen Einträge',
      warn: openKlaerungen > 0,
    },
  ];

  document.getElementById('uebersicht-cards').innerHTML = cards.map(c => `
    <div class="card stat-card" onclick="goToSubtab('${c.subtab}')">
      <h4>${c.title}</h4>
      <p class="${c.warn ? '' : 'muted'}" style="margin:0; ${c.warn ? 'color:var(--warn);' : ''}">${c.body}</p>
    </div>
  `).join('');
}
