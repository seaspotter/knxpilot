// ---------- Hilfe (manual) ----------
// Renders MANUAL.md client-side (renderMarkdown() in ui.js), plus a table
// of contents built from its headings and a simple in-page search that
// highlights matches in the rendered content (Enter/Shift+Enter to step
// through them) - there's no server-side search index, the manual is small
// enough to filter/highlight entirely in the browser.
let MANUAL_MATCHES = [];
let MANUAL_MATCH_INDEX = -1;

async function loadManual() {
  const { markdown } = await api('/system/manual');
  const content = document.getElementById('manual-content');
  const toc = document.getElementById('manual-toc');
  if (!markdown) {
    content.innerHTML = '<p class="muted">Keine Anleitung gefunden.</p>';
    toc.innerHTML = '';
    return;
  }
  content.innerHTML = renderMarkdown(markdown);
  toc.innerHTML = extractHeadings(markdown).map(h =>
    `<a href="#${h.id}" class="manual-toc-l${h.level}" onclick="scrollToManualHeading(event, '${h.id}')">${escapeHtml(h.text)}</a>`
  ).join('');
}

function scrollToManualHeading(ev, id) {
  ev.preventDefault();
  document.getElementById(id)?.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function searchManual(query) {
  const content = document.getElementById('manual-content');
  const status = document.getElementById('manual-search-status');
  content.querySelectorAll('mark.manual-hl').forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
  content.normalize();
  MANUAL_MATCHES = [];
  MANUAL_MATCH_INDEX = -1;

  query = query.trim();
  if (!query) { status.textContent = ''; return; }

  const needle = query.toLowerCase();
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);

  for (const textNode of textNodes) {
    const text = textNode.textContent;
    const lower = text.toLowerCase();
    if (!lower.includes(needle)) continue;
    const frag = document.createDocumentFragment();
    let pos = 0, idx;
    while ((idx = lower.indexOf(needle, pos)) !== -1) {
      frag.appendChild(document.createTextNode(text.slice(pos, idx)));
      const mark = document.createElement('mark');
      mark.className = 'manual-hl';
      mark.textContent = text.slice(idx, idx + needle.length);
      frag.appendChild(mark);
      MANUAL_MATCHES.push(mark);
      pos = idx + needle.length;
    }
    frag.appendChild(document.createTextNode(text.slice(pos)));
    textNode.replaceWith(frag);
  }

  if (MANUAL_MATCHES.length) {
    MANUAL_MATCH_INDEX = 0;
    focusManualMatch();
  } else {
    status.textContent = 'Keine Treffer';
  }
}

function focusManualMatch() {
  document.querySelectorAll('mark.manual-hl.current').forEach(m => m.classList.remove('current'));
  const mark = MANUAL_MATCHES[MANUAL_MATCH_INDEX];
  if (!mark) return;
  mark.classList.add('current');
  mark.scrollIntoView({behavior: 'smooth', block: 'center'});
  document.getElementById('manual-search-status').textContent = `Treffer ${MANUAL_MATCH_INDEX + 1} von ${MANUAL_MATCHES.length}`;
}

function stepManualMatch(delta) {
  if (!MANUAL_MATCHES.length) return;
  MANUAL_MATCH_INDEX = (MANUAL_MATCH_INDEX + delta + MANUAL_MATCHES.length) % MANUAL_MATCHES.length;
  focusManualMatch();
}

// #manual-search is static markup (frontend/index.html), already present
// by the time this classic script runs at the end of <body> - no need to
// wait for DOMContentLoaded.
document.getElementById('manual-search').addEventListener('keydown', (ev) => {
  if (ev.key !== 'Enter') return;
  ev.preventDefault();
  stepManualMatch(ev.shiftKey ? -1 : 1);
});
