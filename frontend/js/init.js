// ---------- Init ----------
(async function init() {
  await loadCompanyProfile();
  await loadCategories();
  await loadPointTypes();
  await loadCentralTemplates();
  await loadActorTypes();
  await loadProjects();
})();
