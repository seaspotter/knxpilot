// ---------- Pflichtenheft (project sub-tab) ----------
async function loadPflichtenheftForCurrentProject() {
  document.getElementById('pflichtenheft-detail').style.display = 'block';
  await renderPflichtenheftPreview();
}

async function renderPflichtenheftPreview() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const el = document.getElementById('pflichtenheft-preview');
  let lines = [];
  for (const floor of tree.floors) {
    lines.push(`<span class="main">${floor.name}</span>`);
    for (const room of floor.rooms) {
      lines.push(`  <span class="middle">${room.name}</span>`);
      const byCategory = {};
      room.points.forEach(p => {
        const pt = POINT_TYPES.find(x => x.id === p.point_type_id);
        if (!pt) return;
        const cat = CATEGORIES.find(c => c.id === pt.category_id);
        const catName = cat ? cat.name : '?';
        const desc = p.label ? `${p.label} (${pt.name})` : pt.name;
        byCategory[catName] = byCategory[catName] || [];
        byCategory[catName].push(desc + (p.has_bwm ? ' +BWM' : ''));
      });
      for (const [cat, items] of Object.entries(byCategory)) {
        lines.push(`    <span class="sub">${cat}: ${items.join(', ')}</span>`);
      }
      const devices = await api(`/rooms/${room.id}/devices`);
      if (devices.length) {
        const deviceList = devices.map(d => `${d.quantity}× ${d.device_name}${d.note ? ' — ' + d.note : ''}`).join(', ');
        lines.push(`    <span class="sub">Geräte: ${deviceList}</span>`);
      }
      if (Object.keys(byCategory).length === 0 && devices.length === 0) {
        lines.push(`    <span class="res">Keine Funktionen oder Geräte geplant</span>`);
      }
    }
  }
  el.innerHTML = lines.join('\n') || '<p class="muted">Noch keine Geschosse in diesem Projekt</p>';
}

function downloadPflichtenheft() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-pflichtenheft.pdf`;
}

