// ---------- Circuit list (project sub-tab "Abgangsliste") ----------
// Rendered server-side with htmx (backend/templates/circuit_list/,
// /hx/... endpoints in backend/routers/circuit_list.py) - the channel
// summary, actor-instance list/form and the per-channel assignment selects
// are all hx-* attributes there; this only loads the tab, the line-select
// wiring (KNX lines stay classic JS, see lines.js), the PA/auto-assign
// preview dialogs (need the JSON preview before confirming) and the
// CSV/PDF downloads.
function loadCircuitListForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/circuit-list`, {target: '#subtab-circuit-list', swap: 'innerHTML'});
}

function setCircuitListBadge(openCount) {
  const btn = document.querySelector('#workspace-subnav button[data-subtab="circuit-list"]');
  if (btn) btn.textContent = openCount > 0 ? `Abgangsliste (${openCount})` : 'Abgangsliste';
}

// Kept current by the htmx channel-summary fragment (HX-Trigger:
// circuit-list-badge, see hx_channel_summary()) whenever it's re-rendered.
document.body.addEventListener('circuit-list-badge', ev => setCircuitListBadge(ev.detail.open || 0));

// Used once on opening a project (before the tab itself has ever been
// loaded, so there's no htmx fragment yet to have fired the event above).
async function refreshCircuitListBadge() {
  const summary = await api(`/projects/${CURRENT_PROJECT}/channel-summary`);
  setCircuitListBadge(summary.reduce((sum, s) => sum + (s.open || 0), 0));
}

async function setActorInstanceLine(id, value) {
  await api(`/actor-instances/${id}/line`, {method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({line_id: value ? parseInt(value, 10) : null})});
  await loadKnxLines();  // device counts per line changed
}

function reloadCircuitListSections() {
  htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/circuit-list/channel-summary`, {target: '#channel-summary-section', swap: 'innerHTML'});
  htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/circuit-list/actor-instances`, {target: '#actor-instances-section', swap: 'innerHTML'});
  htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/circuit-list/circuits`, {target: '#circuits-section', swap: 'innerHTML'});
}

// Shared by both the circuit list and device planning ("PA automatisch
// zuordnen" buttons in each) - the assignment itself is project-wide across
// both actor_instances and room_devices, so it always refreshes both tabs'
// device lists regardless of which one triggered it. Stays plain JS (not an
// hx-post form) because the confirmation dialog needs the computed preview
// text before the user commits.
async function assignPhysicalAddresses(prefixInputId) {
  const prefix = document.getElementById(prefixInputId).value.trim() || '1.1';
  const preview = await api(`/projects/${CURRENT_PROJECT}/assign-physical-addresses/preview`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prefix}),
  });
  if (!preview.assignments.length) {
    const why = preview.skipped.length ? ` (${preview.skipped.length} übersprungen: ${preview.skipped.join(', ')})` : '';
    return showToast(`Keine Adressen zu vergeben — alle Geräte haben bereits eine${why}.`, preview.skipped.length ? 'warning' : 'info');
  }
  let message = `${preview.assignments.length} physikalische Adresse(n) vergeben? Bereits gesetzte Adressen bleiben unverändert.\n\n`
    + previewList(preview.assignments.map(a => `${a.address}  ${a.device} — ${a.where}`));
  if (preview.skipped.length) message += `\n\nÜbersprungen:\n${previewList(preview.skipped)}`;
  if (!(await showConfirm(message, {confirmLabel: 'Adressen vergeben', wide: true}))) return;
  const result = await api(`/projects/${CURRENT_PROJECT}/assign-physical-addresses`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prefix}),
  });
  reloadCircuitListSections();
  await htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/device-planning`, {target: '#subtab-device-planning', swap: 'innerHTML'});
  const skippedText = result.skipped.length ? ` (${result.skipped.length} übersprungen: ${result.skipped.join(', ')})` : '';
  showToast(`${result.assigned} Adresse(n) vergeben${skippedText}.`, result.skipped.length ? 'warning' : 'success');
}

async function autoAssignCircuits() {
  const preview = await api(`/projects/${CURRENT_PROJECT}/circuits/auto-assign?dry_run=true`, {method: 'POST'});
  if (!preview.assigned && !preview.unassigned.length) {
    return showToast('Nichts zuzuordnen — bereits vollständig verdrahtet.', 'info');
  }
  if (preview.assigned) {
    let message = `${preview.assigned} Abgang/Abgänge automatisch zuordnen? Bestehende Zuordnungen bleiben unverändert.\n\n`
      + previewList(preview.details.map(d => `${d.circuit} → ${d.actor}, Kanal ${d.channel}`));
    if (preview.unassigned.length) message += `\n\nNicht zuordenbar (kein freier passender Kanal auf demselben Geschoss):\n${previewList(preview.unassigned)}`;
    if (!(await showConfirm(message, {confirmLabel: 'Zuordnen', wide: true}))) return;
  }
  const result = await api(`/projects/${CURRENT_PROJECT}/circuits/auto-assign`, {method: 'POST'});
  reloadCircuitListSections();
  if (result.unassigned.length) {
    showToast(`${result.assigned} Abgang/Abgänge zugeordnet.\n\nNicht zuordenbar (kein freier passender Aktorkanal auf demselben Geschoss):\n- ${result.unassigned.join('\n- ')}`, 'warning', {sticky: true});
  } else if (result.assigned) {
    showToast(`${result.assigned} Abgang/Abgänge zugeordnet.`, 'success');
  } else {
    showToast('Nichts zuzuordnen — bereits vollständig verdrahtet.', 'info');
  }
}

function downloadCircuitListCsv() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-circuit-list.csv`;
}

function downloadCircuitListPdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-circuit-list.pdf`;
}
