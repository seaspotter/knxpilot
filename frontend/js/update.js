// ---------- Self-update ----------
async function checkForUpdate() {
  const statusEl = document.getElementById('update-status');
  const errorEl = document.getElementById('update-error');
  const btn = document.getElementById('update-btn');
  statusEl.textContent = 'Suche nach Updates...';
  errorEl.style.display = 'none';
  errorEl.textContent = '';
  btn.style.display = 'none';
  try {
    const status = await api('/system/status');
    if (status.error) {
      statusEl.textContent = status.current ? `Aktuelle Version: ${status.current}` : '';
      errorEl.textContent = 'Prüfung fehlgeschlagen: ' + status.error;
      errorEl.style.display = 'block';
      return;
    }
    if (status.update_available) {
      statusEl.textContent = `Update verfügbar (${status.current} → ${status.latest})`;
      btn.style.display = 'inline-block';
    } else {
      statusEl.textContent = `Aktuell (${status.current})`;
    }
  } catch (e) {
    statusEl.textContent = '';
    errorEl.textContent = 'Prüfung fehlgeschlagen: ' + e.message;
    errorEl.style.display = 'block';
  }
}

async function performUpdate() {
  if (!(await showConfirm('Neueste Version laden und die App jetzt neu starten?'))) return;
  const statusEl = document.getElementById('update-status');
  const btn = document.getElementById('update-btn');
  btn.disabled = true;
  statusEl.textContent = 'Aktualisiere...';
  try {
    const result = await api('/system/update', {method: 'POST'});
    if (!result.ok) {
      showToast('Update fehlgeschlagen:\n\n' + result.message, 'error', {sticky: true});
      statusEl.textContent = '';
      btn.disabled = false;
      return;
    }
    if (result.restarting) {
      statusEl.textContent = 'Startet neu...';
      await waitForRestartThenReload();
    } else {
      showToast(result.message, 'info', {sticky: true});
      statusEl.textContent = '';
      btn.disabled = false;
      await checkForUpdate();
    }
  } catch (e) {
    showToast('Update fehlgeschlagen: ' + e.message, 'error', {sticky: true});
    statusEl.textContent = '';
    btn.disabled = false;
  }
}

async function waitForRestartThenReload() {
  // Poll until the server comes back up (docker's restart policy brings it back
  // within a second or two), then reload the page to get the fresh frontend too.
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const r = await fetch('/api/categories');
      if (r.ok) {
        window.location.reload();
        return;
      }
    } catch (e) { /* server still restarting - keep polling */ }
  }
  document.getElementById('update-status').textContent = 'Startet noch... bitte in Kürze manuell neu laden.';
}

