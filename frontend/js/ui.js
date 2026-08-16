// ---------- Toasts & confirm modal (replaces native alert()/confirm()) ----------
function getToastContainer() {
  let el = document.querySelector('.toast-container');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast-container';
    document.body.appendChild(el);
  }
  return el;
}

function showToast(message, type = 'info', { sticky = false } = {}) {
  const container = getToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  const remove = () => toast.remove();
  toast.addEventListener('click', remove);
  container.appendChild(toast);
  if (!sticky) setTimeout(remove, 4000);
  return toast;
}

// Shared modal shell: creates the overlay/card, wires Escape + backdrop-click
// to close(). onClose fires whenever the modal closes for ANY reason
// (Escape, backdrop click, or the caller's own close()) - callers that need
// to settle a promise on every close path (not just their own buttons)
// should use it, guarding against double-settling since it also fires after
// an explicit close() call. Returns {overlay, close}.
function openModal(bodyHtml, { wide = false, onClose } = {}) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `<div class="modal-card${wide ? ' wide' : ''}">${bodyHtml}</div>`;
  document.body.appendChild(overlay);

  const close = () => {
    document.removeEventListener('keydown', onKeydown);
    overlay.remove();
    if (onClose) onClose();
  };
  const onKeydown = (ev) => { if (ev.key === 'Escape') close(); };
  overlay.addEventListener('click', (ev) => { if (ev.target === overlay) close(); });
  document.addEventListener('keydown', onKeydown);

  return { overlay, close };
}

function showConfirm(message, { danger = false } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(`
      <p></p>
      <div class="row modal-actions">
        <button class="btn secondary" data-action="cancel">Abbrechen</button>
        <button class="btn ${danger ? 'danger' : ''}" data-action="confirm">OK</button>
      </div>`, {
      onClose: () => { if (!settled) { settled = true; resolve(false); } },
    });
    modal.overlay.querySelector('p').textContent = message;

    modal.overlay.addEventListener('click', (ev) => {
      const action = ev.target.dataset && ev.target.dataset.action;
      if (action === 'confirm') { settled = true; resolve(true); modal.close(); }
      if (action === 'cancel') modal.close();
    });
  });
}

// Single-field rename dialog -> Promise<string|null> (null if cancelled/closed without saving).
function openRenameModal(currentName, { title = 'Umbenennen' } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(`
      <h3>${title}</h3>
      <div class="row"><input type="text" id="rename-input" style="min-width:260px; flex:1;"></div>
      <div class="row modal-actions">
        <button class="btn secondary" data-action="cancel">Abbrechen</button>
        <button class="btn" data-action="save">Speichern</button>
      </div>`, {
      onClose: () => { if (!settled) { settled = true; resolve(null); } },
    });
    const input = modal.overlay.querySelector('#rename-input');
    input.value = currentName;
    input.focus();
    input.select();

    const save = () => {
      const val = input.value.trim();
      if (!val) return showToast('Name darf nicht leer sein', 'warning');
      settled = true;
      resolve(val);
      modal.close();
    };
    input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') save(); });
    modal.overlay.addEventListener('click', (ev) => {
      const action = ev.target.dataset && ev.target.dataset.action;
      if (action === 'save') save();
      if (action === 'cancel') modal.close();
    });
  });
}
