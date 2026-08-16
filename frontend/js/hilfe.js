// ---------- Hilfe (manual) ----------
async function loadManual() {
  const { markdown } = await api('/system/manual');
  document.getElementById('manual-content').innerHTML = markdown
    ? renderMarkdown(markdown)
    : '<p class="muted">Keine Anleitung gefunden.</p>';
}
