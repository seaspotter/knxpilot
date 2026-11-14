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

// Wires one row of nav/subnav buttons: clicking a button deactivates its
// siblings and panels, activates its own, and runs that tab's loader (if
// any) - shared by the top-level nav and every subnav (workspace, setup,
// device catalog), which all follow this same pattern.
function wireSubnav(navSelector, dataKey, panelsSelector, panelIdPrefix, loaders) {
  document.querySelectorAll(`${navSelector} button[data-${dataKey}]`).forEach(btn => {
    btn.onclick = async () => {
      document.querySelectorAll(`${navSelector} button[data-${dataKey}]`).forEach(b => b.classList.remove('active'));
      document.querySelectorAll(panelsSelector).forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      const key = btn.dataset[dataKey];
      document.getElementById(panelIdPrefix + key).classList.add('active');
      const loader = loaders[key] || loaders.default;
      if (loader) await loader(key);
    };
  });
}

wireSubnav('nav', 'tab', '.tab', 'tab-', {
  'time-tracking': loadTimeTrackingTab,
  setup: loadActiveSetupSection,
  'device-catalog': loadActiveDeviceCatalogSection,
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

wireSubnav('#workspace-subnav', 'subtab', '#project-detail .subtab', 'subtab-', {
  overview: loadOverviewTab,
  functions: loadFunctionsForCurrentProject,
  'group-addresses': loadGroupAddressesForCurrentProject,
  'circuit-list': loadCircuitListForCurrentProject,
  labels: loadLabelsForCurrentProject,
  'device-planning': loadDevicePlanningForCurrentProject,
  'distribution-boards': loadDistributionBoardsForCurrentProject,
  specification: loadSpecificationTab,
  documentation: loadDocumentationTab,
  'function-checklist': loadFunctionChecklist,
  'handover-checklist': loadHandoverChecklist,
  'clarification-list': loadClarificationListForCurrentProject,
  manuals: loadProjectManuals,
});

wireSubnav('#setup-subnav', 'subtab', '#tab-setup .subtab', 'setup-subtab-', { default: loadSetupSection });
wireSubnav('#device-catalog-subnav', 'subtab', '#tab-device-catalog .subtab', 'device-catalog-subtab-', { default: loadDeviceCatalogSection });

