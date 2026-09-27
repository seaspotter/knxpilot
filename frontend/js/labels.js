// ---------- Labels (project sub-tab) ----------
// Rendered server-side with htmx (backend/templates/labels/tab.html,
// /hx/... endpoint in backend/routers/labels.py) - the tab itself has no
// persisted state, so this only loads it and handles the label-position
// grid + PDF download, both purely client-side. The sheet size per format
// comes from the #label-format option's data-size attribute (set from
// backend/labels.py's LABEL_FORMATS registry) rather than a duplicated
// client-side table.
let LABEL_START_POS = 1;

async function loadLabelsForCurrentProject() {
  await htmx.ajax('GET', `/hx/projects/${CURRENT_PROJECT}/labels`, {target: '#subtab-labels', swap: 'innerHTML'});
  renderLabelGrid();
}

function labelSheetSize() {
  const select = document.getElementById('label-format');
  const option = select && select.selectedOptions[0];
  return option ? parseInt(option.dataset.size, 10) || 189 : 189;
}

function renderLabelGrid() {
  const sheetSize = labelSheetSize();
  if (LABEL_START_POS > sheetSize) LABEL_START_POS = 1;
  const grid = document.getElementById('label-position-grid');
  if (!grid) return;
  const cells = [];
  for (let i = 1; i <= sheetSize; i++) {
    cells.push(`<div class="label-cell" data-pos="${i}" title="Etikett ${i}" onclick="setLabelStartPos(${i})"></div>`);
  }
  grid.innerHTML = cells.join('');
  updateLabelGridSelection();
}

function setLabelStartPos(pos) {
  LABEL_START_POS = pos;
  updateLabelGridSelection();
}

function updateLabelGridSelection() {
  const sheetSize = labelSheetSize();
  document.querySelectorAll('#label-position-grid .label-cell').forEach(el => {
    const pos = parseInt(el.dataset.pos);
    el.classList.toggle('used', pos < LABEL_START_POS);
    el.classList.toggle('start', pos === LABEL_START_POS);
  });
  document.getElementById('label-start-text').textContent =
    `Start bei Etikett Nr. ${LABEL_START_POS} von ${sheetSize} (auf ein freies Etikett klicken, um die Startposition zu ändern).`;
}

function downloadLabelsPdf() {
  const format = document.getElementById('label-format').value;
  const debug = document.getElementById('label-debug').checked ? 1 : 0;
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-labels.pdf?format=${format}&start=${LABEL_START_POS}&debug=${debug}`;
}
