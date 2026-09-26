// ---------- Setup: all sub-tabs are rendered server-side with htmx ----------
// Rendered server-side with htmx (backend/templates/setup/, /hx/setup/...):
// each page is a form saving only its own fields. What stays here: loading a
// page when its sub-tab opens, the header branding/timer settings that
// depend on the company profile, the logo auto-crop (canvas, browser only)
// and restoring a backup (the app restarts, see update.js).
const SETUP_HX_SECTIONS = ['company', 'categories', 'function-types', 'central-templates', 'specification', 'documentation', 'email', 'time-tracking', 'backup'];

function loadSetupSection(name) {
  if (!SETUP_HX_SECTIONS.includes(name)) return;
  return htmx.ajax('GET', `/hx/setup/${name}`, {target: `#setup-subtab-${name}`, swap: 'innerHTML'});
}

function loadActiveSetupSection() {
  const active = document.querySelector('#setup-subnav button.active');
  return active ? loadSetupSection(active.dataset.subtab) : undefined;
}

// Header logo/name and the time tracking switch/grid - on page load and
// whenever a settings page was saved (HX-Trigger "company-profile-changed").
async function loadCompanyProfile() {
  const c = await api('/company-profile');
  applyTimeTrackingSettings(c);
  renderHeaderCompanyBranding(c);
}
document.addEventListener('company-profile-changed', () => { loadCompanyProfile().catch(() => {}); });

function renderHeaderCompanyBranding(c) {
  const el = document.getElementById('header-company-brand');
  if (!c || (!c.name && !c.logo_data_url)) { el.style.display = 'none'; el.innerHTML = ''; return; }
  el.innerHTML = `${c.logo_data_url ? `<img src="${escapeAttr(c.logo_data_url)}" alt="${escapeAttr(c.name || 'Firmenlogo')}">` : ''}${c.name ? `<span>${escapeHtml(c.name)}</span>` : ''}`;
  el.style.display = 'flex';
}

// ---------- Company logo (auto-cropped in the browser, stored as a data URL) ----------
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

function setCompanyLogo(dataUrl) {
  document.getElementById('company-logo-data').value = dataUrl;
  const img = document.getElementById('company-logo-preview');
  img.src = dataUrl;
  img.style.display = dataUrl ? '' : 'none';
}

function onCompanyLogoFileChange(event) {
  const file = event.target.files[0];
  if (!file) return;
  const MAX_BYTES = 2 * 1024 * 1024; // 2 MB - stored as base64 on the company profile
  if (file.size > MAX_BYTES) {
    showToast('Logo ist zu gross (max. 2 MB). Bitte ein kleineres Bild wählen.', 'warning');
    event.target.value = '';
    return;
  }
  const reader = new FileReader();
  reader.onload = async () => setCompanyLogo(await autocropLogoDataUrl(reader.result));
  reader.readAsDataURL(file);
}

function clearCompanyLogo() {
  document.getElementById('company-logo-file').value = '';
  setCompanyLogo('');
}

// ---------- Backup: restore (the app restarts afterwards) ----------
const RESTORE_CONFIRM_TEXT = (label) =>
  `Sicherung "${label}" wiederherstellen?\n\nDie komplette aktuelle Datenbank wird ersetzt (vorher wird automatisch eine Sicherung des aktuellen Stands angelegt) und die App startet danach neu. Nicht rückgängig zu machen, ausser über die eben angelegte Sicherung.`;

async function restoreFromExistingBackup(filename, source) {
  if (!(await showConfirm(RESTORE_CONFIRM_TEXT(filename), {danger: true}))) return;
  const path = source === 'nextcloud' ? `/system/restore-nextcloud/${encodeURIComponent(filename)}` : `/system/restore-local/${encodeURIComponent(filename)}`;
  await performRestore(() => api(path, {method: 'POST'}));
}

async function restoreFromUpload() {
  const fileInput = document.getElementById('restore-upload-file');
  const file = fileInput.files[0];
  if (!file) return showToast('Bitte zuerst eine Sicherungsdatei auswählen', 'warning');
  if (!(await showConfirm(RESTORE_CONFIRM_TEXT(file.name), {danger: true}))) return;
  const formData = new FormData();
  formData.append('file', file);
  await performRestore(() => api('/system/restore-upload', {method: 'POST', body: formData}));
}

async function performRestore(triggerFn) {
  try {
    const result = await triggerFn();
    if (result.restarting) {
      showToast('Wiederhergestellt. App startet neu...', 'info', {sticky: true});
      await waitForRestartThenReload();
    }
  } catch (e) {
    showToast('Wiederherstellen fehlgeschlagen: ' + e.message, 'error', {sticky: true});
  }
}

// ---------- Setup: list editors (categories, function types, central templates) ----------
// Rendered server-side with htmx too (backend/templates/setup/). The
// functions tab still reads categories/function types from these caches
// (funktionen.js), refreshed on load and after every change in Setup
// (HX-Trigger "setup-lists-changed").
async function loadSetupCaches() {
  [CATEGORIES, POINT_TYPES] = await Promise.all([api('/categories'), api('/point-types')]);
  const special = document.getElementById('special-category');
  if (special) special.innerHTML = CATEGORIES.map(c => `<option value="${c.id}">${c.order_idx}. ${escapeHtml(c.name)}</option>`).join('');
}
document.addEventListener('setup-lists-changed', () => { loadSetupCaches().catch(() => {}); });

// JSON import: pick a file (browser), post it to the import endpoint, then
// re-render the sub-tab.
async function importSetupJson(title, hint, endpoint, subtab, summary) {
  const file = await openImportModal(title, hint);
  if (!file) return;
  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch (e) {
    return showToast('Diese Datei ist kein gültiges JSON', 'error');
  }
  const result = await api(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
  await loadSetupSection(subtab);
  await loadSetupCaches();
  showToast(summary(result), 'success');
}

function importCategoriesJson() {
  return importSetupJson('Kategorien-Namen importieren',
    'Nur die Namen werden abgeglichen (nach Hauptgruppennummer) - fügt nie eine Kategorie hinzu oder entfernt eine, benennt nur die 6 bestehenden um.',
    '/categories/import-json', 'categories',
    r => `${r.updated} umbenannt${r.skipped ? `, ${r.skipped} übersprungen` : ''}.`);
}

function importPointTypesJson() {
  return importSetupJson('Funktionstypen importieren',
    'Der Import gleicht nach Kategorie+Name ab (bereits vorhandene werden aktualisiert, neue ergänzt).',
    '/point-types/import-json', 'function-types',
    r => `Importiert: ${r.imported} neu, ${r.updated} aktualisiert${r.skipped ? `, ${r.skipped} übersprungen` : ''}.`);
}

function importCentralTemplatesJson() {
  return importSetupJson('Zentral-/Allgemeinfunktions-Vorlagen importieren',
    'Der Import gleicht nach Kategorie+Name+Geltungsbereich ab (bereits vorhandene werden aktualisiert, neue ergänzt).',
    '/central-templates/import-json', 'central-templates',
    r => `Importiert: ${r.imported} neu, ${r.updated} aktualisiert${r.skipped ? `, ${r.skipped} übersprungen` : ''}.`);
}
