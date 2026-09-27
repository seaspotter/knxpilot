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

let CATEGORIES = [], POINT_TYPES = [], ACTOR_TYPES = [], PROJECTS_LIST = [];
let CURRENT_PROJECT = null;

document.querySelectorAll('nav button[data-tab]').forEach(btn => {
  btn.onclick = async () => {
    document.querySelectorAll('nav button[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'time-tracking') await loadTimeTrackingTab();
    if (btn.dataset.tab === 'setup') await loadActiveSetupSection();
    if (btn.dataset.tab === 'device-catalog') await loadActiveDeviceCatalogSection();
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
    if (btn.dataset.subtab === 'overview') await loadOverviewTab();
    if (btn.dataset.subtab === 'functions') await loadFunctionsForCurrentProject();
    if (btn.dataset.subtab === 'group-addresses') await loadGroupAddressesForCurrentProject();
    if (btn.dataset.subtab === 'abgangsliste') await loadAbgangForCurrentProject();
    if (btn.dataset.subtab === 'labels') await loadLabelsForCurrentProject();
    if (btn.dataset.subtab === 'device-planning') await loadDevicePlanningForCurrentProject();
    if (btn.dataset.subtab === 'distribution-boards') await loadDistributionBoardsForCurrentProject();
    if (btn.dataset.subtab === 'specification') await loadSpecificationTab();
    if (btn.dataset.subtab === 'documentation') await loadDocumentationTab();
    if (btn.dataset.subtab === 'function-checklist') await loadFunctionChecklist();
    if (btn.dataset.subtab === 'handover-checklist') await loadHandoverChecklist();
    if (btn.dataset.subtab === 'clarification-list') await loadClarificationListForCurrentProject();
    if (btn.dataset.subtab === 'manuals') await loadProjectManuals();
  };
});

document.querySelectorAll('#setup-subnav button').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#setup-subnav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#tab-setup .subtab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('setup-subtab-' + btn.dataset.subtab).classList.add('active');
    loadSetupSection(btn.dataset.subtab);
  };
});

document.querySelectorAll('#device-catalog-subnav button').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('#device-catalog-subnav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#tab-device-catalog .subtab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('device-catalog-subtab-' + btn.dataset.subtab).classList.add('active');
    loadDeviceCatalogSection(btn.dataset.subtab);
  };
});

