# Changelog

Notable changes to KNXpilot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this file starts from the
restructuring below — history before that is available via `git log`.

## [Unreleased]

### Added

- Toast notifications and a custom confirm modal (`frontend/js/ui.js`),
  replacing every native `alert()`/`confirm()` call across the frontend
  (24 + 7 call sites).
- An open-circuit-count badge on the Abgangsliste sub-tab button (e.g.
  "Abgangsliste (3)"), mirroring the existing Klärungsliste badge pattern.
- A new "Übersicht" sub-tab (`frontend/js/uebersicht.js`), now the default
  landing sub-tab when opening a project — 5 clickable status cards (one
  per other sub-tab) summarizing floors/rooms/points, circuit assignment
  progress, planned device count, and open Klärungen at a glance, each
  jumping straight to the relevant sub-tab on click.
- The Gruppenadressen preview is now a collapsible tree (native
  `<details>`/`<summary>`, `.ga-tree` in `frontend/css/style.css`) instead
  of one long block of monospace text — main groups open by default,
  middle groups (the actual source of clutter on larger projects) start
  collapsed, each showing an address count. "Alle aufklappen"/"Alle
  einklappen" buttons toggle everything at once.
- A responsive pass for phones/small tablets (`@media (max-width: 700px)`
  in `frontend/css/style.css`): the main nav and project sub-nav scroll
  horizontally instead of overflowing the page (the sub-nav has 6 buttons
  now after the Übersicht addition), list rows reflow instead of clipping,
  and touch targets are slightly larger. Purely additive — desktop layout
  is unaffected.
- Bulk room add: each floor's room quick-add now has a "Mehrere..."
  toggle revealing a textarea to paste multiple room names at once (one
  per line), instead of adding them one-by-one. Frontend-only, reuses the
  existing single-room endpoint in a loop; the original single-room input
  is unchanged.

### Changed

- Reworked the Projekte and Setup tabs from "everything stacked on one
  page" into focused views: the Setup tab now has a Firma/Kategorien/
  Punkttypen/Zentral-Vorlagen sub-nav (same pattern as the project
  workspace) instead of 4 always-visible cards; opening a project now
  hides the project list instead of leaving it visible above the
  workspace; and "create project" is now a modal (auto-focused, opens
  the new project directly on success) instead of an always-visible
  inline form. `frontend/js/ui.js`'s `showConfirm` now shares its
  overlay/Escape/backdrop-click plumbing with the new modal via a
  `openModal()` helper.

### Changed

- Restructured the project into separate `backend/` (FastAPI) and
  `frontend/` (plain HTML/CSS/JS, no build step) directories, replacing the
  previous single `app/` directory whose `static/index.html` held the
  entire frontend inline.
- Split the 1800-line monolithic `frontend/index.html` into a CSS file
  (`frontend/css/style.css`) and one JS file per UI tab/sub-tab under
  `frontend/js/`, mirroring the existing one-router-per-tab structure of
  the backend. No behavior changes.
- Added `CLAUDE.md`, `DEVELOPMENT.md`, and `DEPLOYMENT.md`; trimmed the
  corresponding "Persistenz & Deployment" and "Code-Struktur" sections out
  of `README.md` in favor of pointers to the new files.
- Updated `Dockerfile`, `.gitignore`, and `docker-compose.yml` comments for
  the new `backend/`/`frontend/` paths (the repo-wide bind mount itself is
  unaffected).
- Added a "Keep docs in sync with code changes" section to `CLAUDE.md`.

### Fixed

- `DEPLOYMENT.md`'s Proxmox instructions named `docker-compose-plugin`/
  `docker-ce` as an apt-installable fallback without noting that those are
  Docker's own package names, not Ubuntu's — `apt install` silently fails
  the whole transaction (including `docker.io`) when one package name
  doesn't resolve. Fixed to use Ubuntu's own `docker-compose-v2` package
  (no third-party repo needed), with Docker's official install script kept
  as a documented fallback for distros where that package isn't available.
