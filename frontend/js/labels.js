// ---------- Labels (project sub-tab) ----------
// Per-format sheet size (labels per sheet) - keyed the same as
// backend/labels.py's LABEL_FORMATS, so adding a new format later means
// adding an entry here (and an <option> in index.html) alongside the
// backend registry entry.
const LABEL_FORMAT_SIZES = { l6037: 189 };

let LABEL_START_POS = 1;

function labelSheetSize() {
  const format = document.getElementById('label-format').value;
  return LABEL_FORMAT_SIZES[format] || 189;
}

function renderLabelGrid() {
  const sheetSize = labelSheetSize();
  if (LABEL_START_POS > sheetSize) LABEL_START_POS = 1;
  const grid = document.getElementById('label-position-grid');
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
  const source = document.getElementById('label-source').value;
  const debug = document.getElementById('label-debug').checked ? 1 : 0;
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export-labels.pdf?format=${format}&source=${source}&start=${LABEL_START_POS}&debug=${debug}`;
}
