// ---------- Klärungsliste (project sub-tab) ----------
// Rendered server-side with htmx: the tab's HTML (form, list, buttons) comes
// from backend/templates/klaerungsliste/ via the /hx/... endpoints in
// backend/routers/klaerungsliste.py, and the hx-* attributes in it do the
// requests - no client-side state here. What's left in this file: loading
// the tab, the subnav badge, and the copy/PDF buttons.
function loadKlaerungslisteForCurrentProject() {
  return htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/klaerungsliste`, {target: '#klaerungsliste-root', swap: 'innerHTML'});
}

function updateKlaerungsBadge(openCount, agedCount) {
  const btn = document.querySelector('#workspace-subnav button[data-subtab="klaerungsliste"]');
  if (!btn) return;
  btn.textContent = openCount > 0 ? `Klärungsliste (${openCount})` : 'Klärungsliste';
  btn.style.color = agedCount > 0 ? 'var(--warn)' : '';
}

// Every htmx response that changes the list sends the new counts
// (HX-Trigger: klaerungen-changed, see _render() in the router).
document.body.addEventListener('klaerungen-changed', ev => updateKlaerungsBadge(ev.detail.open, ev.detail.aged));

async function refreshKlaerungsBadge() {
  const entries = await api(`/projects/${CURRENT_PROJECT}/klaerungen`);
  updateKlaerungsBadge(entries.filter(k => k.status === 'offen').length, entries.filter(k => k.aged).length);
}

// ---------- Offene Punkte weitergeben ----------
function downloadKlaerungslistePdf() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-klaerungsliste.pdf`;
}

// The text (same grouping/numbers as the PDF) is rendered by the server into
// a hidden <textarea id="kl-open-text">, so copying needs no request - the
// clipboard only works directly inside the click.
async function copyOpenKlaerungenAsText() {
  const text = (document.getElementById('kl-open-text')?.value || '').trim();
  if (!text) return showToast('Keine offenen Punkte', 'warning');
  // navigator.clipboard only exists on HTTPS/localhost - KNXpilot usually
  // runs on a plain http:// LAN address, so fall back to execCommand.
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      if (!ok) throw new Error('copy failed');
    }
    showToast('Offene Punkte in die Zwischenablage kopiert', 'success');
  } catch (e) {
    showToast('Kopieren nicht möglich - bitte PDF verwenden', 'warning');
  }
}
