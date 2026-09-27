// ---------- Übergabe-Checkliste (project sub-tab "handover-checklist") ----------
// Rendered server-side with htmx (backend/templates/handover_checklist/,
// /hx/projects/{id}/handover-checklist... endpoints in backend/routers/
// checkliste.py). Each row's Ja/Nein/Nicht-nötig switch and Bemerkungen
// field are independent htmx PUTs, swapped back into just that row. Only
// the signature capture (canvas) stays client-side JS, shared with
// function_checklist.js via ui.js's openSignatureCaptureModal().
function loadHandoverChecklist() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/handover-checklist`, {target: '#subtab-handover-checklist', swap: 'innerHTML'});
}

function reloadHandoverChecklistSignatures() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/handover-checklist/signatures`, {target: '#handover-signatures', swap: 'outerHTML'});
}

function signHandoverChecklist(role, label) {
  openSignatureCaptureModal(label, async (dataUrl) => {
    await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({image: dataUrl}),
    });
    await reloadHandoverChecklistSignatures();
  });
}

async function deleteHandoverChecklistSignature(role, label) {
  const ok = await showConfirm(`Unterschrift von ${label} wirklich löschen?`, {danger: true});
  if (!ok) return;
  await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {method: 'DELETE'});
  await reloadHandoverChecklistSignatures();
}

function downloadHandoverChecklist() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-uebergabe-checkliste.pdf`;
}
