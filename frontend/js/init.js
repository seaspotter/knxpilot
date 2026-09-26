// ---------- Init ----------
(async function init() {
  await loadAppVersion();
  await loadCompanyProfile();
  await loadSetupCaches();
  await loadActorTypes();
  await loadProjects();
  await loadRunningTimer();
  await loadChangelog();
  await loadManual();
})();
