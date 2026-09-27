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

function showConfirm(message, { danger = false, confirmLabel = 'OK', wide = false } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(`
      <p></p>
      <div class="row modal-actions">
        <button class="btn secondary" data-action="cancel">Abbrechen</button>
        <button class="btn ${danger ? 'danger' : ''}" data-action="confirm">${escapeHtml(confirmLabel)}</button>
      </div>`, {
      wide,
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

// Bullet list for a showConfirm() preview ("what exactly will change") -
// long lists are cut off with a count so the dialog stays usable.
function previewList(lines, max = 40) {
  const shown = lines.slice(0, max).map(l => `• ${l}`);
  if (lines.length > max) shown.push(`… und ${lines.length - max} weitere`);
  return shown.join('\n');
}

// ---------- Small hand-written Markdown renderer (no library) ----------
// Used for both the Update tab's changelog and the Hilfe tab's manual.
// Supports: headings (any # depth, top-level # skipped since it's implied by
// the card heading), bullet lists with multi-line continuation, fenced code
// blocks, and inline `code`/**bold**.
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function inlineMarkdown(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function renderMarkdown(markdown) {
  const lines = markdown.split('\n');
  let html = '';
  let listOpen = false;
  const closeList = () => { if (listOpen) { html += '</ul>'; listOpen = false; } };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const heading = line.match(/^(#{1,6})\s+(.*)/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      if (level === 1) { i++; continue; } // top-level title, implied by the card heading
      const tag = 'h' + Math.min(level + 1, 6);
      html += `<${tag}>${inlineMarkdown(heading[2])}</${tag}>`;
      i++;
    } else if (/^```/.test(line)) {
      closeList();
      i++;
      const code = [];
      while (i < lines.length && !/^```/.test(lines[i])) { code.push(lines[i]); i++; }
      i++; // skip closing fence
      html += `<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`;
    } else if (/^-\s/.test(line)) {
      if (!listOpen) { html += '<ul>'; listOpen = true; }
      let text = line.replace(/^-\s*/, '');
      i++;
      while (i < lines.length && /^\s+\S/.test(lines[i])) { text += ' ' + lines[i].trim(); i++; }
      html += `<li>${inlineMarkdown(text)}</li>`;
    } else if (line.trim() === '') {
      closeList();
      i++;
    } else {
      closeList();
      let text = line.trim();
      i++;
      while (i < lines.length && lines[i].trim() !== '' && !/^[#-]/.test(lines[i]) && !/^```/.test(lines[i])) { text += ' ' + lines[i].trim(); i++; }
      html += `<p class="muted">${inlineMarkdown(text)}</p>`;
    }
  }
  closeList();
  return html;
}

// Single-field rename dialog -> Promise<string|null> (null if cancelled/closed without saving).
function openRenameModal(currentName, { title = 'Umbenennen' } = {}) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(`
      <h3>${title}</h3>
      <div class="row"><input type="text" id="rename-input" class="flex-input"></div>
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

// Single file-picker dialog -> Promise<File|null> (null if cancelled/closed
// without choosing a file). Callers still do their own read/parse/upload -
// this only replaces the "pick a file" step, so behavior stays identical to
// the previous always-visible <input type="file"> + separate button.
function openImportModal(title, hint) {
  return new Promise((resolve) => {
    let settled = false;
    const modal = openModal(`
      <h3>${title}</h3>
      ${hint ? `<p class="muted">${hint}</p>` : ''}
      <div class="row"><input type="file" id="import-modal-file" accept="application/json"></div>
      <div class="row modal-actions">
        <button class="btn secondary" data-action="cancel">Abbrechen</button>
        <button class="btn" data-action="import">Importieren</button>
      </div>`, {
      onClose: () => { if (!settled) { settled = true; resolve(null); } },
    });
    const doImport = () => {
      const file = modal.overlay.querySelector('#import-modal-file').files[0];
      if (!file) return showToast('Bitte zuerst eine Datei auswählen', 'warning');
      settled = true;
      resolve(file);
      modal.close();
    };
    modal.overlay.addEventListener('click', (ev) => {
      const action = ev.target.dataset && ev.target.dataset.action;
      if (action === 'import') doImport();
      if (action === 'cancel') modal.close();
    });
  });
}

function escapeAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

// ---------- htmx glue (tabs rendered server-side, e.g. klaerungsliste.js) ----------
// hx-confirm="..." uses the app's own confirm dialog instead of the browser's.
document.addEventListener('htmx:confirm', ev => {
  if (!ev.detail.question) return;
  ev.preventDefault();
  showConfirm(ev.detail.question, {danger: true, confirmLabel: 'Löschen'}).then(ok => { if (ok) ev.detail.issueRequest(true); });
});
// Errors show as a toast with the server's "detail" message, like api() does.
document.addEventListener('htmx:responseError', ev => {
  let message = `Fehler ${ev.detail.xhr.status}`;
  try { message = JSON.parse(ev.detail.xhr.responseText).detail || message; } catch (e) { /* not JSON */ }
  showToast(message, 'warning');
});
document.addEventListener('htmx:sendError', () => showToast('Server nicht erreichbar', 'warning'));
// Every htmx request tells the server the browser's time zone, so it can
// render local times (the container usually runs on UTC) - see
// client_zone() in backend/templating.py.
document.addEventListener('htmx:configRequest', ev => {
  ev.detail.headers['X-Timezone'] = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  ev.detail.headers['X-Timezone-Offset'] = String(new Date().getTimezoneOffset());
});
// Server-rendered dialogs: a fragment swapped into #hx-modal (end of
// index.html) whose root is a .modal-overlay. Closes on Escape, a click on
// the backdrop, or when the server sends HX-Trigger "hx-modal-close" (e.g.
// after a successful save).
function closeHxModal() {
  const el = document.getElementById('hx-modal');
  if (el) el.innerHTML = '';
}
document.addEventListener('hx-modal-close', closeHxModal);
document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape' && document.getElementById('hx-modal')?.innerHTML) closeHxModal();
});
// ---------- Shared digital-signature capture (canvas) ----------
// Used by both checklist tabs (function_checklist.js, handover_checklist.js)
// to capture a signature on-site instead of printing the PDF and signing on
// paper. This only draws the pad and hands the resulting PNG data URL to
// `onSave` - callers do their own api() PUT (role is project/tab-specific)
// and then reload their own htmx signature fragment.
function openSignatureCaptureModal(label, onSave) {
  const modal = openModal(`
    <h3>Unterschrift — ${label}</h3>
    <canvas id="sig-canvas" style="width:100%; height:200px; border:1px solid var(--border); border-radius:6px; touch-action:none; background:#fff; display:block;"></canvas>
    <div class="row modal-actions">
      <button class="btn secondary" data-action="clear">Löschen</button>
      <button class="btn secondary" data-action="cancel">Abbrechen</button>
      <button class="btn" data-action="save">Speichern</button>
    </div>
  `, { wide: true });

  const canvas = modal.overlay.querySelector('#sig-canvas');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let cssWidth = 0, cssHeight = 0;

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    cssWidth = rect.width;
    cssHeight = rect.height;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx.scale(dpr, dpr);
    ctx.lineWidth = 2.2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0f172a';
  }
  resizeCanvas();

  let drawing = false, lastX = 0, lastY = 0, hasDrawn = false;
  function pos(ev) {
    const rect = canvas.getBoundingClientRect();
    return [ev.clientX - rect.left, ev.clientY - rect.top];
  }
  canvas.addEventListener('pointerdown', (ev) => {
    drawing = true;
    hasDrawn = true;
    [lastX, lastY] = pos(ev);
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', (ev) => {
    if (!drawing) return;
    const [x, y] = pos(ev);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.stroke();
    [lastX, lastY] = [x, y];
  });
  const stopDrawing = () => { drawing = false; };
  canvas.addEventListener('pointerup', stopDrawing);
  canvas.addEventListener('pointerleave', stopDrawing);

  modal.overlay.addEventListener('click', async (ev) => {
    const action = ev.target.dataset && ev.target.dataset.action;
    if (action === 'clear') {
      ctx.clearRect(0, 0, cssWidth, cssHeight);
      hasDrawn = false;
    }
    if (action === 'cancel') modal.close();
    if (action === 'save') {
      if (!hasDrawn) { showToast('Bitte zuerst unterschreiben.', 'warning'); return; }
      const dataUrl = canvas.toDataURL('image/png');
      await onSave(dataUrl);
      modal.close();
    }
  });
}

// A server response can show a toast: HX-Trigger {"show-toast": {"message", "level"}}.
document.addEventListener('show-toast', ev => showToast(ev.detail.message, ev.detail.level || 'info', ev.detail.level === 'error' ? {sticky: true} : undefined));
