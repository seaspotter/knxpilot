// ---------- Aktoren: Actor Types ----------
function onDeviceGroupChange() {
  const select = document.getElementById('actortype-group');
  const customInput = document.getElementById('actortype-group-custom');
  const isCustom = select.value === '__custom__';
  customInput.style.display = isCustom ? 'inline-block' : 'none';
  const effectiveGroup = isCustom ? customInput.value.trim() : select.value;
  const isAktor = effectiveGroup === 'Aktor';
  document.getElementById('actortype-channeltype-label').style.display = isAktor ? 'flex' : 'none';
  document.getElementById('actortype-count-label').style.display = isAktor ? 'flex' : 'none';
}

function getEffectiveDeviceGroup() {
  const select = document.getElementById('actortype-group');
  if (select.value === '__custom__') {
    return document.getElementById('actortype-group-custom').value.trim() || 'Sonstiges';
  }
  return select.value;
}

let EDITING_ACTOR_TYPE_ID = null;

async function saveActorType() {
  const manufacturer = document.getElementById('actortype-manufacturer').value.trim();
  const model = document.getElementById('actortype-model').value.trim();
  const group_name = getEffectiveDeviceGroup();
  const description = document.getElementById('actortype-description').value.trim();
  const isAktor = group_name === 'Aktor';
  const channel_type = isAktor ? document.getElementById('actortype-channeltype').value.trim() : '';
  const channel_count = isAktor ? (parseInt(document.getElementById('actortype-count').value) || 1) : null;
  if (!model) return alert('Modell ist erforderlich');
  if (isAktor && !channel_type) return alert('Type ist für die Gruppe "Aktor" erforderlich');
  const body = JSON.stringify({manufacturer, model, group_name, description, channel_type, channel_count});
  if (EDITING_ACTOR_TYPE_ID) {
    await api('/actor-types/' + EDITING_ACTOR_TYPE_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  } else {
    await api('/actor-types', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  }
  cancelEditActorType();
  await loadActorTypes();
}

function editActorType(id) {
  const at = ACTOR_TYPES.find(a => a.id === id);
  if (!at) return;
  EDITING_ACTOR_TYPE_ID = id;
  document.getElementById('actortype-manufacturer').value = at.manufacturer || '';
  document.getElementById('actortype-model').value = at.model || '';
  document.getElementById('actortype-description').value = at.description || '';
  const groupSelect = document.getElementById('actortype-group');
  const knownGroups = ['Aktor', 'Sensor', 'Wetterstation', 'Bedienelement', 'Sonstiges'];
  const groupCustom = document.getElementById('actortype-group-custom');
  if (knownGroups.includes(at.group_name)) {
    groupSelect.value = at.group_name;
    groupCustom.style.display = 'none';
    groupCustom.value = '';
  } else {
    groupSelect.value = '__custom__';
    groupCustom.style.display = 'inline-block';
    groupCustom.value = at.group_name || '';
  }
  document.getElementById('actortype-channeltype').value = at.channel_type || '';
  document.getElementById('actortype-count').value = at.channel_count || 8;
  onDeviceGroupChange();
  document.getElementById('actortype-save-btn').textContent = 'Änderungen speichern';
  document.getElementById('actortype-cancel-btn').style.display = '';
  document.getElementById('actortype-manufacturer').scrollIntoView({behavior: 'smooth', block: 'center'});
}

function cancelEditActorType() {
  EDITING_ACTOR_TYPE_ID = null;
  document.getElementById('actortype-manufacturer').value = '';
  document.getElementById('actortype-model').value = '';
  document.getElementById('actortype-channeltype').value = '';
  document.getElementById('actortype-description').value = '';
  document.getElementById('actortype-save-btn').textContent = 'Gerät speichern';
  document.getElementById('actortype-cancel-btn').style.display = 'none';
}

async function loadActorTypes() {
  ACTOR_TYPES = await api('/actor-types');
  renderActorTypesList();
}

function renderActorTypesList() {
  const container = document.getElementById('actor-types-groups');
  const countEl = document.getElementById('actortype-filter-count');
  const query = document.getElementById('actortype-filter').value.trim().toLowerCase();
  const filtered = !query ? ACTOR_TYPES : ACTOR_TYPES.filter(at =>
    [at.manufacturer, at.model, at.group_name, at.description, at.channel_type]
      .some(field => (field || '').toLowerCase().includes(query))
  );
  countEl.textContent = query ? `${filtered.length} von ${ACTOR_TYPES.length} Geräten` : '';

  const groups = {};
  filtered.forEach(at => {
    const g = at.group_name || 'Sonstiges';
    groups[g] = groups[g] || [];
    groups[g].push(at);
  });
  const groupNames = Object.keys(groups).sort();
  container.innerHTML = groupNames.map(g => `
    <h4 style="margin:14px 0 6px;">${g}</h4>
    <ul class="list">
      ${groups[g].map(at => `
        <li>
          <div>
            <b>${[at.manufacturer, at.model].filter(Boolean).join(' ')}</b>
            ${at.channel_type ? `<span class="pill">${at.channel_type}</span>` : ''}
            ${at.channel_count ? `<span class="pill">${at.channel_count} Kanäle</span>` : ''}
            ${at.description ? `<div class="muted" style="margin-top:2px;">${at.description}</div>` : ''}
          </div>
          <div class="row" style="gap:6px;">
            <button class="btn secondary small" onclick="editActorType(${at.id})">Bearbeiten</button>
            <button class="btn danger small" onclick="deleteActorType(${at.id})">Löschen</button>
          </div>
        </li>`).join('')}
    </ul>
  `).join('') || (query
    ? '<p class="muted">Keine Geräte gefunden</p>'
    : '<p class="muted">Noch keine Geräte</p>');
}

async function deleteActorType(id) {
  if (!confirm('Dieses Gerät löschen?')) return;
  if (EDITING_ACTOR_TYPE_ID === id) cancelEditActorType();
  await api('/actor-types/' + id, {method:'DELETE'});
  await loadActorTypes();
}

function exportActorTypesJson() {
  window.location.href = `/api/actor-types/export-json`;
}

async function importActorTypesJson() {
  const fileInput = document.getElementById('import-actortypes-file');
  const file = fileInput.files[0];
  if (!file) return alert('Bitte zuerst eine Katalog-.json-Datei auswählen');
  const text = await file.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    return alert('Diese Datei ist kein gültiges JSON');
  }
  const result = await api('/actor-types/import-json', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  fileInput.value = '';
  await loadActorTypes();
  alert(`Importiert: ${result.imported} neu, ${result.updated} aktualisiert.`);
}

