// ---------- Init ----------
(async function init() {
  await loadAppVersion();
  await loadCompanyProfile();
  await loadCategories();
  await loadPointTypes();
  await loadCentralTemplates();
  await loadActorTypes();
  await loadProjects();
  await loadChangelog();
  await loadManual();
})();
