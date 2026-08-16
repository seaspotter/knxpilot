// ---------- Setup: Company profile ----------
let COMPANY_LOGO_DATA_URL = '';

async function loadCompanyProfile() {
  const c = await api('/company-profile');
  document.getElementById('company-name').value = c.name || '';
  document.getElementById('company-address').value = c.address || '';
  document.getElementById('company-phone').value = c.phone || '';
  document.getElementById('company-email').value = c.email || '';
  document.getElementById('company-website').value = c.website || '';
  document.getElementById('company-show-on-pdf').checked = !!c.show_on_pdf;
  COMPANY_LOGO_DATA_URL = c.logo_data_url || '';
  updateCompanyLogoPreview();
  renderHeaderCompanyBranding(c);
}

function autocropLogoDataUrl(dataUrl) {
  // Many logo files ship with transparent or white padding baked around the
  // actual mark, which makes them look tiny once fit into a small header/PDF
  // box - the box renders at the intended size, but most of it is blank. This
  // crops to the actual visible content so the full box is used.
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      let imgData;
      try {
        imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      } catch (e) {
        resolve(dataUrl);
        return;
      }
      const { data, width, height } = imgData;
      let hasAlpha = false;
      for (let i = 3; i < data.length; i += 4 * 37) {
        if (data[i] < 255) { hasAlpha = true; break; }
      }
      const bgR = data[0], bgG = data[1], bgB = data[2];
      const isBackground = (i) => {
        if (hasAlpha) return data[i + 3] < 12;
        return Math.abs(data[i] - bgR) + Math.abs(data[i + 1] - bgG) + Math.abs(data[i + 2] - bgB) < 18;
      };

      let minX = width, minY = height, maxX = -1, maxY = -1;
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          const i = (y * width + x) * 4;
          if (!isBackground(i)) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
      if (maxX < minX || maxY < minY) { resolve(dataUrl); return; }

      const pad = 4;
      minX = Math.max(0, minX - pad);
      minY = Math.max(0, minY - pad);
      maxX = Math.min(width - 1, maxX + pad);
      maxY = Math.min(height - 1, maxY + pad);
      const cropW = maxX - minX + 1, cropH = maxY - minY + 1;

      const cropCanvas = document.createElement('canvas');
      cropCanvas.width = cropW;
      cropCanvas.height = cropH;
      cropCanvas.getContext('2d').drawImage(canvas, minX, minY, cropW, cropH, 0, 0, cropW, cropH);
      resolve(cropCanvas.toDataURL('image/png'));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}

function onCompanyLogoFileChange(event) {
  const file = event.target.files[0];
  if (!file) return;
  const MAX_BYTES = 2 * 1024 * 1024; // 2 MB - round-trips as base64 on every Setup load
  if (file.size > MAX_BYTES) {
    showToast('Logo ist zu gross (max. 2 MB). Bitte ein kleineres Bild wählen.', 'warning');
    event.target.value = '';
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => {
    COMPANY_LOGO_DATA_URL = await autocropLogoDataUrl(reader.result);
    updateCompanyLogoPreview();
  };
  reader.readAsDataURL(file);
}

function clearCompanyLogo() {
  COMPANY_LOGO_DATA_URL = '';
  document.getElementById('company-logo-file').value = '';
  updateCompanyLogoPreview();
}

function updateCompanyLogoPreview() {
  const img = document.getElementById('company-logo-preview');
  if (COMPANY_LOGO_DATA_URL) { img.src = COMPANY_LOGO_DATA_URL; img.style.display = ''; }
  else { img.src = ''; img.style.display = 'none'; }
}

async function saveCompanyProfile() {
  const body = JSON.stringify({
    name: document.getElementById('company-name').value.trim(),
    address: document.getElementById('company-address').value.trim(),
    phone: document.getElementById('company-phone').value.trim(),
    email: document.getElementById('company-email').value.trim(),
    website: document.getElementById('company-website').value.trim(),
    logo_data_url: COMPANY_LOGO_DATA_URL,
    show_on_pdf: document.getElementById('company-show-on-pdf').checked,
  });
  await api('/company-profile', {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  await loadCompanyProfile();
}

function renderHeaderCompanyBranding(c) {
  const el = document.getElementById('header-company-brand');
  if (!c || (!c.name && !c.logo_data_url)) { el.style.display = 'none'; el.innerHTML = ''; return; }
  el.innerHTML = `${c.logo_data_url ? `<img src="${c.logo_data_url}" alt="${c.name || 'Firmenlogo'}">` : ''}${c.name ? `<span>${c.name}</span>` : ''}`;
  el.style.display = 'flex';
}

// ---------- Setup: Categories ----------
async function loadCategories() {
  CATEGORIES = await api('/categories');
  const ul = document.getElementById('categories-list');
  ul.innerHTML = CATEGORIES.map(c => `
    <li>
      <span><b>${c.main_label ?? ''}</b> ${c.order_idx}. ${c.name} ${c.is_allgemein ? '<span class="pill">Allgemein-Vorlage</span>' : ''}</span>
      <button class="btn secondary small" onclick="renameCategory(${c.id}, '${c.name.replace(/'/g,"\\'")}')">Bearbeiten</button>
    </li>
  `).join('');
  const catSelects = ['pt-category', 'ct-category', 'special-category'];
  catSelects.forEach(id => {
    document.getElementById(id).innerHTML = CATEGORIES.map(c => `<option value="${c.id}">${c.order_idx}. ${c.name}</option>`).join('');
  });
}

async function renameCategory(id, currentName) {
  const newName = await openRenameModal(currentName, {title: 'Kategorie umbenennen'});
  if (newName === null) return;
  try {
    await api('/categories/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name: newName})});
    await loadCategories();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ---------- Setup: Point Types ----------
function addPtSuffixRow(suffix='', dpt='') {
  const div = document.createElement('div');
  div.className = 'row';
  div.innerHTML = `
    <input type="text" placeholder="Suffix z.B. Schalten" class="pt-suf-name" value="${suffix}">
    <input type="text" placeholder="DPT z.B. DPST-1-1" class="pt-suf-dpt" value="${dpt}">
    <button class="btn danger small" onclick="this.parentElement.remove()">x</button>`;
  document.getElementById('pt-suffixes').appendChild(div);
}

let EDITING_POINT_TYPE_ID = null;

async function savePointType() {
  const category_id = parseInt(document.getElementById('pt-category').value);
  const name = document.getElementById('pt-name').value.trim();
  const block_size = parseInt(document.getElementById('pt-blocksize').value) || 5;
  const channel_type = document.getElementById('pt-channeltype').value.trim();
  const channels_needed = parseInt(document.getElementById('pt-channelsneeded').value) || 1;
  const suffixes = [...document.querySelectorAll('#pt-suffixes .row')].map(r => ({
    suffix: r.querySelector('.pt-suf-name').value.trim(),
    dpt: r.querySelector('.pt-suf-dpt').value.trim()
  })).filter(s => s.suffix);
  if (!name || suffixes.length === 0) return showToast('Name und mindestens ein Datenpunkt erforderlich', 'warning');
  const body = JSON.stringify({category_id, name, suffixes, block_size, channel_type, channels_needed});
  if (EDITING_POINT_TYPE_ID) {
    await api('/point-types/' + EDITING_POINT_TYPE_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  } else {
    await api('/point-types', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  }
  cancelEditPointType();
  await loadPointTypes();
}

function editPointType(id) {
  const pt = POINT_TYPES.find(p => p.id === id);
  if (!pt) return;
  EDITING_POINT_TYPE_ID = id;
  document.getElementById('pt-category').value = pt.category_id;
  document.getElementById('pt-name').value = pt.name;
  document.getElementById('pt-blocksize').value = pt.block_size;
  document.getElementById('pt-channeltype').value = pt.channel_type || '';
  document.getElementById('pt-channelsneeded').value = pt.channels_needed || 1;
  document.getElementById('pt-suffixes').innerHTML = '';
  pt.suffixes.forEach(s => addPtSuffixRow(s.suffix, s.dpt));
  document.getElementById('pt-save-btn').textContent = 'Änderungen speichern';
  document.getElementById('pt-cancel-btn').style.display = '';
  document.getElementById('pt-name').scrollIntoView({behavior: 'smooth', block: 'center'});
}

function cancelEditPointType() {
  EDITING_POINT_TYPE_ID = null;
  document.getElementById('pt-name').value = '';
  document.getElementById('pt-channeltype').value = '';
  document.getElementById('pt-channelsneeded').value = '1';
  document.getElementById('pt-suffixes').innerHTML = '';
  document.getElementById('pt-save-btn').textContent = 'Funktionstyp speichern';
  document.getElementById('pt-cancel-btn').style.display = 'none';
}

async function loadPointTypes() {
  POINT_TYPES = await api('/point-types');
  const ul = document.getElementById('point-types-list');
  ul.innerHTML = POINT_TYPES.map(pt => {
    const cat = CATEGORIES.find(c => c.id === pt.category_id);
    return `<li>
      <div><b>${pt.name}</b> <span class="pill">${cat?.name||'?'}</span> <span class="pill">Block ${pt.block_size}</span>
        ${pt.channel_type ? `<span class="pill">Kanal: ${pt.channel_type} ×${pt.channels_needed}</span>` : ''}
        ${pt.suffixes.map(s=>`<span class="pill">${s.suffix} · ${s.dpt}</span>`).join('')}
      </div>
      <div class="row" style="gap:6px;">
        <button class="btn secondary small" onclick="editPointType(${pt.id})">Bearbeiten</button>
        <button class="btn danger small" onclick="deletePointType(${pt.id})">Löschen</button>
      </div>
    </li>`;
  }).join('') || '<li class="muted">Noch keine Funktionstypen</li>';
}

async function deletePointType(id) {
  if (!(await showConfirm('Diesen Funktionstyp löschen?', {danger: true}))) return;
  if (EDITING_POINT_TYPE_ID === id) cancelEditPointType();
  await api('/point-types/' + id, {method:'DELETE'});
  await loadPointTypes();
}


// ---------- Setup: Central Templates ----------
function addCtSuffixRow(suffix='', dpt='') {
  const div = document.createElement('div');
  div.className = 'row';
  div.innerHTML = `
    <input type="text" placeholder="Suffix z.B. Ein/Aus" class="ct-suf-name" value="${suffix}">
    <input type="text" placeholder="DPT z.B. DPST-1-1" class="ct-suf-dpt" value="${dpt}">
    <button class="btn danger small" onclick="this.parentElement.remove()">x</button>`;
  document.getElementById('ct-suffixes').appendChild(div);
}

function onCtScopeChange() {
  const scope = document.getElementById('ct-scope').value;
  document.getElementById('ct-skip-outdoor-label').style.display = scope === 'floor' ? 'flex' : 'none';
  document.getElementById('ct-blocksize-label').style.display = scope === 'room_multi' ? 'flex' : 'none';
  document.getElementById('ct-trigger-label').style.display = scope === 'room_multi' ? 'flex' : 'none';
}

let EDITING_CENTRAL_TEMPLATE_ID = null;

async function saveCentralTemplate() {
  const category_id = parseInt(document.getElementById('ct-category').value);
  const scope = document.getElementById('ct-scope').value;
  const name = document.getElementById('ct-name').value.trim();
  const skip_outdoor_floors = document.getElementById('ct-skip-outdoor').checked;
  const blockSizeVal = document.getElementById('ct-blocksize').value.trim();
  const triggerVal = document.getElementById('ct-trigger').value.trim();
  const block_size = scope === 'room_multi' && blockSizeVal ? parseInt(blockSizeVal) : null;
  const trigger_count = scope === 'room_multi' && triggerVal ? parseInt(triggerVal) : null;
  const suffixes = [...document.querySelectorAll('#ct-suffixes .row')].map(r => ({
    suffix: r.querySelector('.ct-suf-name').value.trim(),
    dpt: r.querySelector('.ct-suf-dpt').value.trim()
  })).filter(s => s.suffix);
  if (suffixes.length === 0) return showToast('Mindestens ein Datenpunkt erforderlich', 'warning');
  if (EDITING_CENTRAL_TEMPLATE_ID) {
    const existing = CENTRAL_TEMPLATES.find(c => c.id === EDITING_CENTRAL_TEMPLATE_ID);
    const body = JSON.stringify({category_id, name, scope, suffixes, skip_outdoor_floors, block_size, trigger_count, order_idx: existing ? existing.order_idx : 0});
    await api('/central-templates/' + EDITING_CENTRAL_TEMPLATE_ID, {method:'PUT', headers:{'Content-Type':'application/json'}, body});
  } else {
    const body = JSON.stringify({category_id, name, scope, suffixes, skip_outdoor_floors, block_size, trigger_count});
    await api('/central-templates', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  }
  cancelEditCentralTemplate();
  await loadCentralTemplates();
}

function editCentralTemplate(id) {
  const ct = CENTRAL_TEMPLATES.find(c => c.id === id);
  if (!ct) return;
  EDITING_CENTRAL_TEMPLATE_ID = id;
  document.getElementById('ct-category').value = ct.category_id;
  document.getElementById('ct-scope').value = ct.scope;
  onCtScopeChange();
  document.getElementById('ct-name').value = ct.name || '';
  document.getElementById('ct-skip-outdoor').checked = ct.skip_outdoor_floors;
  document.getElementById('ct-blocksize').value = ct.block_size || '';
  document.getElementById('ct-trigger').value = ct.trigger_count || 2;
  document.getElementById('ct-suffixes').innerHTML = '';
  ct.suffixes.forEach(s => addCtSuffixRow(s.suffix, s.dpt));
  document.getElementById('ct-save-btn').textContent = 'Änderungen speichern';
  document.getElementById('ct-cancel-btn').style.display = '';
  document.getElementById('ct-category').scrollIntoView({behavior: 'smooth', block: 'center'});
}

function cancelEditCentralTemplate() {
  EDITING_CENTRAL_TEMPLATE_ID = null;
  document.getElementById('ct-name').value = '';
  document.getElementById('ct-skip-outdoor').checked = false;
  document.getElementById('ct-blocksize').value = '';
  document.getElementById('ct-trigger').value = '2';
  document.getElementById('ct-suffixes').innerHTML = '';
  document.getElementById('ct-save-btn').textContent = 'Vorlage speichern';
  document.getElementById('ct-cancel-btn').style.display = 'none';
}

async function loadCentralTemplates() {
  CENTRAL_TEMPLATES = await api('/central-templates');
  const ul = document.getElementById('central-templates-list');
  ul.innerHTML = CENTRAL_TEMPLATES.map(ct => {
    const cat = CATEGORIES.find(c => c.id === ct.category_id);
    const extra = [];
    if (ct.skip_outdoor_floors) extra.push('<span class="pill">ohne Aussen</span>');
    if (ct.scope === 'room_multi') {
      extra.push(`<span class="pill">ab ${ct.trigger_count || 2} Punkten</span>`);
      if (ct.block_size) extra.push(`<span class="pill">Block ${ct.block_size}</span>`);
    }
    return `<li>
      <div><b>${ct.name || '(kein Präfix)'}</b> <span class="pill">${cat?.name||'?'}</span> <span class="pill">${ct.scope}</span> ${extra.join(' ')}
        ${ct.suffixes.map(s=>`<span class="pill">${s.suffix || '(keiner)'} · ${s.dpt}</span>`).join('')}
      </div>
      <div class="row" style="gap:6px;">
        <button class="btn secondary small" onclick="editCentralTemplate(${ct.id})">Bearbeiten</button>
        <button class="btn danger small" onclick="deleteCentralTemplate(${ct.id})">Löschen</button>
      </div>
    </li>`;
  }).join('') || '<li class="muted">Noch keine Vorlagen</li>';
}

async function deleteCentralTemplate(id) {
  if (!(await showConfirm('Diese Vorlage löschen?', {danger: true}))) return;
  if (EDITING_CENTRAL_TEMPLATE_ID === id) cancelEditCentralTemplate();
  await api('/central-templates/' + id, {method:'DELETE'});
  await loadCentralTemplates();
}

