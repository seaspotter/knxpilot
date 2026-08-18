// ---------- Abgangsliste (project sub-tab) ----------
async function loadAbgangForCurrentProject() {
  document.getElementById('abgang-detail').style.display = 'block';
  await renderActorInstanceForm();
  await renderChannelSummary();
  await renderActorInstances();
  await renderCircuits();
}

async function renderChannelSummary() {
  const summary = await api(`/projects/${CURRENT_PROJECT}/channel-summary`);
  const ul = document.getElementById('channel-summary-list');
  ul.innerHTML = summary.map(s => `
    <li>
      <div><b>${s.floor_name}</b> <span class="pill">${s.channel_type}</span></div>
      <div>
        <span class="pill">${s.needed} benötigt</span>
        <span class="pill">${s.assigned} zugeordnet</span>
        <span class="pill" style="${s.open > 0 ? 'color:var(--warn);' : ''}">${s.open} offen</span>
      </div>
    </li>`).join('') || '<li class="muted">Noch keine Abgänge vorhanden</li>';
  updateAbgangslisteBadgeText(summary);
}

function updateAbgangslisteBadgeText(summary) {
  const openCount = summary.reduce((sum, s) => sum + (s.open || 0), 0);
  const btn = document.querySelector('#workspace-subnav button[data-subtab="abgangsliste"]');
  if (btn) btn.textContent = openCount > 0 ? `Abgangsliste (${openCount})` : 'Abgangsliste';
}

async function refreshAbgangslisteBadge() {
  const summary = await api(`/projects/${CURRENT_PROJECT}/channel-summary`);
  updateAbgangslisteBadgeText(summary);
}

// ---------- Abgangsliste: Actor Instances ----------
async function renderActorInstanceForm() {
  const tree = await api(`/projects/${CURRENT_PROJECT}/tree`);
  const actorsOnly = ACTOR_TYPES.filter(at => at.group_name === 'Aktor');
  document.getElementById('ai-actortype').innerHTML = actorsOnly.map(at =>
    `<option value="${at.id}">${[at.manufacturer, at.model].filter(Boolean).join(' ')} (${at.channel_type}, ${at.channel_count} Kanäle)</option>`).join('') ||
    '<option value="">Noch keine Aktoren definiert - im Geräte-Katalog-Tab anlegen (Gruppe: Aktor)</option>';
  document.getElementById('ai-floor').innerHTML = '<option value="">(kein Geschoss)</option>' +
    tree.floors.map(f => `<option value="${f.id}">${f.name}</option>`).join('');
}

let EDITING_ACTOR_INSTANCE_ID = null;

async function saveActorInstance() {
  const floorVal = document.getElementById('ai-floor').value;
  const floor_id = floorVal ? parseInt(floorVal) : null;
  const location_label = document.getElementById('ai-location').value.trim();
  const physical_address = document.getElementById('ai-address').value.trim();

  if (EDITING_ACTOR_INSTANCE_ID) {
    await api(`/actor-instances/${EDITING_ACTOR_INSTANCE_ID}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({floor_id, location_label, physical_address})});
    cancelEditActorInstance();
  } else {
    const actor_type_id = parseInt(document.getElementById('ai-actortype').value);
    if (!actor_type_id) return showToast('Zuerst einen Aktortyp im Aktoren-Tab anlegen', 'warning');
    await api(`/projects/${CURRENT_PROJECT}/actor-instances`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({actor_type_id, floor_id, location_label, physical_address})});
    document.getElementById('ai-location').value = '';
    document.getElementById('ai-address').value = '';
  }
  await renderActorInstances();
  await renderCircuits();
  await renderChannelSummary();
}

function editActorInstance(id) {
  const ai = ACTOR_INSTANCES.find(a => a.id === id);
  if (!ai) return;
  EDITING_ACTOR_INSTANCE_ID = id;
  const actortype = document.getElementById('ai-actortype');
  actortype.value = ''; // this device's type isn't changeable here - see ActorInstanceEditIn
  actortype.disabled = true;
  document.getElementById('ai-floor').value = ai.floor_id || '';
  document.getElementById('ai-location').value = ai.location_label || '';
  document.getElementById('ai-address').value = ai.physical_address || '';
  document.getElementById('ai-save-btn').textContent = 'Änderungen speichern';
  document.getElementById('ai-cancel-btn').style.display = '';
  actortype.scrollIntoView({behavior: 'smooth', block: 'center'});
}

function cancelEditActorInstance() {
  EDITING_ACTOR_INSTANCE_ID = null;
  document.getElementById('ai-actortype').disabled = false;
  document.getElementById('ai-floor').value = '';
  document.getElementById('ai-location').value = '';
  document.getElementById('ai-address').value = '';
  document.getElementById('ai-save-btn').textContent = '+ Aktor hinzufügen';
  document.getElementById('ai-cancel-btn').style.display = 'none';
}

let ACTOR_INSTANCES = [];

async function renderActorInstances() {
  ACTOR_INSTANCES = await api(`/projects/${CURRENT_PROJECT}/actor-instances`);
  const ul = document.getElementById('actor-instances-list');
  ul.innerHTML = ACTOR_INSTANCES.map(ai => {
    const grid = ai.channel_map.map(ch => {
      const isUsed = !!ch.function;
      const title = isUsed ? ch.function : 'Frei';
      return `<div class="channel-box ${isUsed ? 'used' : 'free'}" title="${ch.letter}: ${title}">${ch.letter}</div>`;
    }).join('');
    return `<li style="flex-direction:column; align-items:stretch;">
      <div class="row" style="justify-content:space-between; margin-bottom:0;">
        <div><b>${ai.actor_type_name}</b> <span class="pill">${ai.channel_type}</span>
          ${ai.floor_name ? `<span class="pill">${ai.floor_name}</span>` : ''}
          ${ai.location_label ? `<span class="pill">${ai.location_label}</span>` : ''}
          ${ai.physical_address ? `<span class="pill">${ai.physical_address}</span>` : ''}
          <span class="pill">${ai.channels_used}/${ai.channel_count} belegt</span>
        </div>
        <div class="row" style="margin:0; gap:6px;">
          <button class="btn secondary small" onclick="editActorInstance(${ai.id})">Bearbeiten</button>
          <button class="btn danger small" onclick="deleteActorInstance(${ai.id})">Löschen</button>
        </div>
      </div>
      <div class="channel-map">${grid}</div>
    </li>`;
  }).join('') || '<li class="muted">Noch keine Aktoren hinzugefügt</li>';
}

async function deleteActorInstance(id) {
  if (!(await showConfirm('Diesen Aktor löschen? Zugeordnete Abgänge werden dadurch nicht mehr zugeordnet.', {danger: true}))) return;
  if (EDITING_ACTOR_INSTANCE_ID === id) cancelEditActorInstance();
  await api('/actor-instances/' + id, {method:'DELETE'});
  await renderActorInstances();
  await renderCircuits();
  await renderChannelSummary();
}

// ---------- Abgangsliste: Circuits ----------
async function renderCircuits() {
  const [circuits, instances] = await Promise.all([
    api(`/projects/${CURRENT_PROJECT}/circuits`),
    api(`/projects/${CURRENT_PROJECT}/actor-instances`),
  ]);
  const assignedCount = circuits.filter(c => c.assignment).length;
  document.getElementById('circuits-summary').textContent =
    `${assignedCount} / ${circuits.length} Abgänge zugeordnet`;

  const ul = document.getElementById('circuits-list');
  ul.innerHTML = circuits.map(c => {
    const matching = instances.filter(ai => ai.channel_type === c.channel_type);
    const options = ['<option value="">— nicht zugeordnet —</option>'];
    matching.forEach(ai => {
      const usedLetters = new Set(); // filled below via data attr trick isn't needed; server rejects duplicates anyway
      for (let i = 1; i <= ai.channel_count; i++) {
        const letter = toChannelLetter(i);
        const isCurrent = c.assignment && c.assignment.actor_instance_id === ai.id && c.assignment.channel_letter === letter;
        options.push(`<option value="${ai.id}|${letter}" ${isCurrent ? 'selected' : ''}>${ai.actor_type_name} (${ai.physical_address || ai.location_label || ai.id}) — ${letter}</option>`);
      }
    });
    const selectedValue = c.assignment ? `${c.assignment.actor_instance_id}|${c.assignment.channel_letter}` : '';
    return `<li>
      <div>${c.floor_name} / <b>${c.function_name}</b> <span class="pill">${c.channel_type}</span> <span class="pill">${c.point_type_name}</span></div>
      <select onchange="onCircuitAssignChange(${c.room_point_id}, ${c.channel_seq}, this.value)" ${matching.length === 0 ? 'disabled title="Noch kein passender Aktor hinzugefügt"' : ''}>
        ${options.join('')}
      </select>
    </li>`;
  }).join('') || '<li class="muted">Noch keine Abgänge — oben Räume und Punkte hinzufügen</li>';

  // Ensure each select reflects current assignment (re-set value since duplicate option values across selects is fine per-select)
  [...ul.querySelectorAll('select')].forEach((sel, i) => {
    const c = circuits[i];
    if (c && c.assignment) sel.value = `${c.assignment.actor_instance_id}|${c.assignment.channel_letter}`;
    else sel.value = '';
  });
}

function toChannelLetter(i) {
  let label = '';
  let x = i;
  while (x > 0) {
    const rem = (x - 1) % 26;
    label = String.fromCharCode(65 + rem) + label;
    x = Math.floor((x - 1) / 26);
  }
  return label;
}

async function onCircuitAssignChange(room_point_id, channel_seq, value) {
  if (!value) {
    await api(`/projects/${CURRENT_PROJECT}/circuits/${room_point_id}/${channel_seq}`, {method:'DELETE'});
  } else {
    const [actor_instance_id, channel_letter] = value.split('|');
    try {
      await api(`/projects/${CURRENT_PROJECT}/circuits/assign`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({room_point_id, channel_seq, actor_instance_id: parseInt(actor_instance_id), channel_letter})});
    } catch (e) {
      showToast(e.message, 'error');
    }
  }
  await renderCircuits();
  await renderActorInstances();
  await renderChannelSummary();
}

async function autoAssignCircuits() {
  const result = await api(`/projects/${CURRENT_PROJECT}/circuits/auto-assign`, {method:'POST'});
  await renderCircuits();
  await renderActorInstances();
  await renderChannelSummary();
  if (result.unassigned.length) {
    showToast(`${result.assigned} Abgang/Abgänge zugeordnet.\n\nNicht zuordenbar (kein freier passender Aktorkanal auf demselben Geschoss):\n- ${result.unassigned.join('\n- ')}`, 'warning', {sticky: true});
  } else if (result.assigned) {
    showToast(`${result.assigned} Abgang/Abgänge zugeordnet.`, 'success');
  } else {
    showToast('Nichts zuzuordnen — bereits vollständig verdrahtet.', 'info');
  }
}

function downloadAbgangsliste() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-abgangsliste.csv`;
}

function downloadAbgangslistePdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-abgangsliste.pdf`;
}

