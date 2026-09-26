// ---------- Handbücher (device manuals: fetch-on-click into their own project store) ----------
async function loadProjectManuals() {
  const manuals = await api(`/projects/${CURRENT_PROJECT}/manuals`);
  const ul = document.getElementById('project-manuals-list');
  ul.innerHTML = manuals.map(m => `
    <li>
      <div><b>${escapeHtml(m.device_name)}</b>${m.description ? ` <span class="muted">— ${escapeHtml(m.description)}</span>` : ''}</div>
      <div class="row" style="margin:0; gap:6px;">
        ${m.file_id
          ? `<button class="btn secondary small" onclick="viewProjectManual(${m.file_id})">Ansehen</button>
             <button class="btn danger small" onclick="deleteProjectManual(${m.file_id})">Löschen</button>`
          : `<button class="btn secondary small" onclick="fetchProjectManual(${m.device_type_id})">Herunterladen</button>`}
      </div>
    </li>
  `).join('') || '<li class="muted">Keine Handbuch-Links für verwendete Geräte hinterlegt</li>';
}

function viewProjectManual(fileId) {
  window.open(`/api/project-manuals/${fileId}/view`, '_blank');
}

async function fetchProjectManual(deviceTypeId) {
  try {
    await api(`/projects/${CURRENT_PROJECT}/fetch-manual/${deviceTypeId}`, {method: 'POST'});
  } catch (e) {
    return showToast(e.message, 'error');
  }
  await loadProjectManuals();
}

async function fetchAllProjectManuals() {
  const result = await api(`/projects/${CURRENT_PROJECT}/fetch-manuals`, {method: 'POST'});
  await loadProjectManuals();
  if (result.failed.length) {
    showToast(`${result.fetched.length} heruntergeladen, ${result.failed.length} fehlgeschlagen: ${result.failed.map(f => f.device_name).join(', ')}`, 'warning');
  } else if (result.fetched.length) {
    showToast(`${result.fetched.length} Handbücher heruntergeladen.`, 'success');
  } else {
    showToast('Alle Handbücher bereits gespeichert.', 'success');
  }
}

async function deleteProjectManual(fileId) {
  if (!(await showConfirm('Dieses Handbuch aus dem Projekt löschen?', {danger: true}))) return;
  await api(`/project-manuals/${fileId}`, {method: 'DELETE'});
  await loadProjectManuals();
}
