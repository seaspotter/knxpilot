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

function showConfirm(message, { danger = false } = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-card">
        <p></p>
        <div class="row">
          <button class="btn secondary" data-action="cancel">Abbrechen</button>
          <button class="btn ${danger ? 'danger' : ''}" data-action="confirm">OK</button>
        </div>
      </div>`;
    overlay.querySelector('p').textContent = message;
    document.body.appendChild(overlay);

    const finish = (result) => {
      document.removeEventListener('keydown', onKeydown);
      overlay.remove();
      resolve(result);
    };
    const onKeydown = (ev) => { if (ev.key === 'Escape') finish(false); };

    overlay.addEventListener('click', (ev) => {
      if (ev.target === overlay) finish(false);
      const action = ev.target.dataset && ev.target.dataset.action;
      if (action === 'confirm') finish(true);
      if (action === 'cancel') finish(false);
    });
    document.addEventListener('keydown', onKeydown);
  });
}
