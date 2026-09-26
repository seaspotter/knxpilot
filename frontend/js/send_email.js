// ---------- Send by email (shared modal) ----------
// Used from the "Per E-Mail senden" button on Pflichtenheft,
// Funktionscheckliste, Übergabe-Checkliste, Dokumentation and the
// Klärungsliste's "Offene Punkte" - one shared implementation rather than
// duplicating the modal per document, since they just differ by which
// document type/label they pass in. Always a
// manual, one-click-per-send action (never triggered automatically, e.g.
// right after a signature is captured) - the dialog always shows exactly
// who's about to receive what before anything goes out.
async function openSendEmailModal(documentType, label) {
  let defaults;
  try {
    defaults = await api(`/projects/${CURRENT_PROJECT}/email-defaults`);
  } catch (e) {
    return showToast(e.message, 'error');
  }
  if (!defaults.smtp_enabled) {
    return showToast('E-Mail-Versand ist nicht eingerichtet (Setup → E-Mail).', 'warning');
  }

  const toValue = [defaults.to, defaults.additional_recipients].filter(Boolean).join(', ');
  const ccValue = defaults.cc_self_default ? defaults.company_email : '';

  const modal = openModal(`
    <h3>${label} per E-Mail senden</h3>
    <div class="row">
      <input type="text" id="send-email-to" class="flex-input-wide" placeholder="An (mehrere mit Komma getrennt)" value="${escapeAttr(toValue)}">
    </div>
    <div class="row">
      <input type="text" id="send-email-cc" class="flex-input-wide" placeholder="Kopie (CC, optional)" value="${escapeAttr(ccValue)}">
    </div>
    <div class="row">
      <input type="text" id="send-email-note" class="flex-input-wide" placeholder="Zusätzliche Nachricht (optional)">
    </div>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="send">Senden</button>
    </div>`, { wide: true });

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'cancel') return modal.close();
    if (action !== 'send') return;

    const to = document.getElementById('send-email-to').value.trim();
    const cc = document.getElementById('send-email-cc').value.trim();
    const note = document.getElementById('send-email-note').value.trim();
    if (!to && !cc) return showToast('Mindestens ein Empfänger ist erforderlich.', 'warning');

    const sendBtn = modal.overlay.querySelector('[data-action="send"]');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sende...';
    try {
      await api(`/projects/${CURRENT_PROJECT}/send-email`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ document: documentType, to, cc, note }),
      });
      modal.close();
      showToast(`${label} wurde versendet.`, 'success');
    } catch (e) {
      sendBtn.disabled = false;
      sendBtn.textContent = 'Senden';
      showToast(e.message, 'error');
    }
  });
}

async function sendTestEmail() {
  const to = document.getElementById('smtp-test-recipient').value.trim();
  if (!to) return showToast('Bitte eine Test-Empfängeradresse eingeben.', 'warning');
  try {
    await api('/send-test-email', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ to }),
    });
    showToast('Test-E-Mail wurde versendet.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}
