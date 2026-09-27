// ---------- Funktionscheckliste (project sub-tab "function-checklist") ----------
// Rendered server-side with htmx (backend/templates/function_checklist/,
// /hx/projects/{id}/function-checklist... endpoints in backend/routers/
// checkliste.py). Tapping a row is an htmx PUT on that row alone (see the
// template) - deliberately no full-list re-render, so scroll position isn't
// lost while walking through a building ticking boxes one at a time. Only
// the signature capture (canvas) stays client-side JS, shared with
// handover_checklist.js via ui.js's openSignatureCaptureModal().
function loadFunctionChecklist() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/function-checklist`, {target: '#subtab-function-checklist', swap: 'innerHTML'});
}

function reloadFunctionChecklistSignatures() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/function-checklist/signatures`, {target: '#fc-signatures', swap: 'outerHTML'});
}

function signFunctionChecklist(role, label) {
  openSignatureCaptureModal(label, async (dataUrl) => {
    await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({image: dataUrl}),
    });
    await reloadFunctionChecklistSignatures();
  });
}

async function deleteFunctionChecklistSignature(role, label) {
  const ok = await showConfirm(`Unterschrift von ${label} wirklich löschen?`, {danger: true});
  if (!ok) return;
  await api(`/projects/${CURRENT_PROJECT}/signatures/${role}`, {method: 'DELETE'});
  await reloadFunctionChecklistSignatures();
}

function downloadFunctionChecklist() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-funktionscheckliste.pdf`;
}
