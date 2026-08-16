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
- Floors, rooms, and room functions can now be renamed/edited after
  creation, not just deleted: floor and room names via a "Bearbeiten"
  button opening a rename dialog (`frontend/js/ui.js`'s
  `openRenameModal`), and a room's assigned functions (point type/label/
  BWM) via a ✎ edit link on each pill that repurposes the existing
  quick-add form into an edit form (same pattern already used for actor
  types). New backend endpoints: `PUT /api/floors/{id}`,
  `PUT /api/rooms/{id}`, `PUT /api/room-points/{id}`.
- Setup's Funktionstypen (formerly "Punkttypen") and Zentral-Vorlagen can
  now be edited in place (the backend already supported this; only the
  frontend UI was missing) — same "Bearbeiten" pattern as the Geräte
  Katalog's actor types.
- Categories can now be renamed via a new "Bearbeiten" button
  (`PUT /api/categories/{id}`) — reordering/adding/removing stays
  unsupported, since order directly maps to fixed KNX main group numbers.

### Changed

- Split the GA tree preview and CSV export out of the "Funktionen"
  sub-tab into its own new "Gruppenadressen" sub-tab, so that assigning
  functions to rooms and viewing/exporting the resulting group addresses
  are no longer stacked on the same page. Frontend-only — the moved code
  (`previewGA`, `expandAllGaTree`, `downloadCSV`) now lives in a new
  `frontend/js/gruppenadressen.js`, following the one-file-per-sub-tab
  convention.
- Renamed Setup's "Punkttypen" sub-tab and every user-facing label to
  "Funktionstypen", for terminology consistency with the "Funktionen"
  tab where those types get assigned to rooms (the underlying
  `point_types` table, `/api/point-types` endpoint, and JS variable
  names are unchanged — only displayed text moved).
- Floor and room rename now uses a "Bearbeiten" button in the same
  button row as "löschen", instead of the ✎ icon-link introduced in the
  previous change — matching the convention used everywhere else a name
  can be changed (actor types, Funktionstypen, Zentral-Vorlagen,
  Kategorien). Room-function pills keep their ✎/× icon-link pair, which
  predates this rework and fits a compact pill format better than a
  text button.
- Split the "Gruppenadressen" sub-tab into **Gebäudestruktur** (floors/
  rooms only) and **Funktionen** (assigning KNX functions to rooms,
  Sonderadressen, GA preview/export) — these were previously combined on
  one page. `frontend/js/funktionen.js` is a new file for the latter,
  following this project's one-file-per-sub-tab convention.
- Renamed the "Setup (Kategorien & Vorlagen)" tab to plain "Setup".
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
- The "Projekte" top-nav item is now a small dropdown (▾) with "Neues
  Projekt" and "Projekt öffnen", usable from any tab.
- Renamed the "Geräte" tab to "Geräte Katalog" for clarity (and the
  validation messages that reference it).
- The Update tab now shows this project's changelog
  (`GET /api/system/changelog`, new `.changelog` rendering in
  `frontend/js/update.js` — a small hand-written Markdown-to-HTML
  converter, no library added).
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

- The GA tree preview's expand/collapse triangles sat flush against the
  card's left edge instead of aligning with the rest of the card's
  content (`.ga-tree summary`'s `list-style-position: outside` pushed
  the native disclosure marker outside the content box). Changed to
  `inside`.
- List rows (`ul.list li`, used by Funktionstypen, Zentral-/
  Allgemeinfunktions-Vorlagen, Kategorien, actor types, etc.) let their
  "Bearbeiten"/"Löschen" buttons wrap onto a second line whenever the
  row's content wrapped to multiple lines (e.g. "LED (Tunable White)",
  "Klima"), since content and buttons shared equal flex-shrink. Fixed by
  giving the content column `min-width: 0` (free to shrink/wrap) and the
  button column `flex-shrink: 0` (stays put at its natural size).
- `DEPLOYMENT.md`'s Proxmox instructions named `docker-compose-plugin`/
  `docker-ce` as an apt-installable fallback without noting that those are
  Docker's own package names, not Ubuntu's — `apt install` silently fails
  the whole transaction (including `docker.io`) when one package name
  doesn't resolve. Fixed to use Ubuntu's own `docker-compose-v2` package
  (no third-party repo needed), with Docker's official install script kept
  as a documented fallback for distros where that package isn't available.
