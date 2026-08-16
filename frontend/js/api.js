// ---------- Theme ----------
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme-toggle').textContent = theme === 'light' ? '🌙 Dunkel' : '☀️ Hell';
  localStorage.setItem('knx-ga-theme', theme);
}
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'light' ? 'dark' : 'light');
}
applyTheme(localStorage.getItem('knx-ga-theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'));

const api = (path, opts) => fetch('/api' + path, opts).then(async r => {
  if (!r.ok) { const t = await r.json().catch(()=>({detail:r.statusText})); throw new Error(t.detail || 'Error'); }
  return r.headers.get('content-type')?.includes('json') ? r.json() : r;
});

let CATEGORIES = [], POINT_TYPES = [], CENTRAL_TEMPLATES = [], ACTOR_TYPES = [], PROJECTS_LIST = [];
let CURRENT_PROJECT = null;

document.querySelectorAll('nav button[data-tab]').forEach(btn => {
  btn.onclick = async () => {
    document.querySelectorAll('nav button[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  };
});

// ---------- Nav dropdown (Projekte menu) ----------
function toggleProjekteMenu(ev) {
  ev.stopPropagation();
  const menu = document.getElementById('projekte-dropdown-menu');
  menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}
function closeNavDropdowns() {
  const menu = document.getElementById('projekte-dropdown-menu');
  if (menu) menu.style.display = 'none';
}
document.addEventListener('click', closeNavDropdowns);

document.querySelectorAll('#workspace-subnav button').forEach(btn => {
  btn.onclick = async () => {
    document.querySelectorAll('#workspace-subnav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#project-detail .subtab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('subtab-' + btn.dataset.subtab).classList.add('active');
    if (btn.dataset.subtab === 'uebersicht') await loadUebersichtForCurrentProject();
    if (btn.dataset.subtab === 'gruppenadressen') await previewGA();
    if (btn.dataset.subtab === 'abgangsliste') await loadAbgangForCurrentProject();
    if (btn.dataset.subtab === 'labels') renderLabelGrid();
    if (btn.dataset.subtab === 'geraeteplanung') await loadGeraeteplanungForCurrentProject();
    if (btn.dataset.subtab === 'pflichtenheft') await loadPflichtenheftForCurrentProject();
    if (btn.dataset.subtab === 'klaerungsliste') await loadKlaerungslisteForCurrentProject();
  };
});

document.querySelectorAll('#setup-subnav button').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#setup-subnav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#tab-setup .subtab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('setup-subtab-' + btn.dataset.subtab).classList.add('active');
  };
});

