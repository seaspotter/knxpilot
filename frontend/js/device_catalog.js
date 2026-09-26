// ---------- Device catalog tab ("Geräte Katalog": catalog + manual URLs) ----------
// Both sub-tabs are rendered server-side with htmx (backend/templates/
// device_catalog/, /hx/device-catalog...). What stays here: loading a
// sub-tab, the ACTOR_TYPES cache the pickers in other tabs use (circuit
// list, device planning, distribution board planning) - refreshed after
// every catalog change (HX-Trigger "catalog-changed") - and the JSON
// imports, which need the file picker plus a preview confirmation.
function loadDeviceCatalogSection(name) {
  const url = name === 'manuals' ? '/hx/device-catalog/manuals' : '/hx/device-catalog';
  return htmx.ajax('GET', url, {target: `#device-catalog-subtab-${name}`, swap: 'innerHTML'});
}

function loadActiveDeviceCatalogSection() {
  const active = document.querySelector('#device-catalog-subnav button.active');
  return loadDeviceCatalogSection(active ? active.dataset.subtab : 'catalog');
}

async function loadActorTypes() {
  ACTOR_TYPES = await api('/actor-types');
}
document.addEventListener('catalog-changed', () => { loadActorTypes().catch(() => {}); });

async function importActorTypesJson() {
  const file = await openImportModal('Geräte-Katalog importieren', 'Der Import gleicht nach Hersteller+Modell ab (bereits vorhandene werden aktualisiert, neue ergänzt) - mehrere Kataloge unterschiedlicher Hersteller lassen sich also nacheinander importieren, sie werden zusammengeführt statt ersetzt.');
  if (!file) return;
  const text = await file.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (e) {
    return showToast('Diese Datei ist kein gültiges JSON', 'error');
  }
  const body = JSON.stringify(payload);
  const preview = await api('/actor-types/import-json/preview', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  if (!(await confirmCatalogImport(preview, 'Geräte-Katalog importieren'))) return;
  const result = await api('/actor-types/import-json', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  await loadActorTypes();
  await loadActiveDeviceCatalogSection();
  showToast(`Importiert: ${result.imported} neu, ${result.updated} aktualisiert.`, 'success');
}

// Confirmation listing exactly what a catalog import changes (per device and
// field) - so e.g. a description you edited yourself isn't overwritten unseen.
async function confirmCatalogImport(preview, title) {
  if (!preview.new.length && !preview.changed.length) {
    showToast(`Nichts zu tun — alle ${preview.unchanged} Geräte sind bereits auf diesem Stand.`, 'info');
    return false;
  }
  const fmt = v => (v === null || v === undefined || v === '') ? '(leer)' : String(v);
  let message = `${title}?`;
  if (preview.changed.length) {
    message += `\n\n${preview.changed.length} Gerät(e) werden geändert:\n` + previewList(preview.changed.map(c =>
      `${c.device}: ${c.changes.map(d => `${d.field} „${fmt(d.old)}“ → „${fmt(d.new)}“`).join('; ')}`), 30);
  }
  if (preview.new.length) message += `\n\n${preview.new.length} Gerät(e) kommen neu dazu:\n${previewList(preview.new, 20)}`;
  if (preview.unchanged) message += `\n\n${preview.unchanged} Gerät(e) bleiben unverändert.`;
  return showConfirm(message, {confirmLabel: 'Importieren', wide: true});
}

async function importDefaultActorTypes() {
  const preview = await api('/actor-types/import-defaults/preview', {method:'POST'});
  if (!(await confirmCatalogImport(preview, 'Mitgelieferten Standard-Katalog importieren'))) return;
  const result = await api('/actor-types/import-defaults', {method:'POST'});
  await loadActorTypes();
  await loadActiveDeviceCatalogSection();
  showToast(`Importiert: ${result.imported} neu, ${result.updated} aktualisiert.`, 'success');
}

