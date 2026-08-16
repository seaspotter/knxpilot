# Changelog

Notable changes to KNXpilot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this file starts from the
restructuring below — history before that is available via `git log`.

## [Unreleased]

### Added

- **Etiketten** export (Abgangsliste sub-tab): prints an Avery Zweckform
  L6037 label sheet (25.4 × 10 mm, 189 labels/sheet) — one label per
  actor instance (physical address + location) or per channel (physical
  address + channel letter, plus the assigned function/`RESERVE`), with a
  clickable position picker to resume a partially-used sheet instead of
  starting over, and a debug/test-print mode (border + position number)
  for checking alignment on plain paper before printing on real label
  stock. New `backend/labels.py` (the Avery L6037 layout math/canvas
  renderer, reusable by future label formats) and
  `GET /api/projects/{id}/export-labels.pdf`.

## [0.2.0] - 2026-08-16

### Added

- **Duplizieren** for projects: a one-click, same-install copy (floors,
  rooms, points, specials, and metadata), available both from a project's
  own header and as a button in each row of the project list. Auto-names
  the copy "<Name> (Kopie)" (numbered if that name is already taken) and,
  from the project header, switches straight into the new copy. New
  `POST /api/projects/{id}/duplicate` endpoint - builds on the existing
  export/import-json logic (now factored into shared
  `_build_project_payload()`/`_insert_project_from_payload()` helpers) but
  skips the JSON round-trip and can never skip an item, since Point Types/
  Categories always match themselves on the same install.

- Export/import (JSON) for Setup → Kategorien, Funktionstypen, and
  Zentral-/Allgemeinfunktions-Vorlagen — the same pattern the Geräte
  Katalog already had, so the new "Alle löschen" buttons (below) are
  always recoverable without a database reset. Kategorien's import only
  renames the 6 fixed categories (matched by main group number, never
  adds/removes); Funktionstypen and Zentral-Vorlagen upsert by
  category+name(+scope), so re-importing the same file twice updates in
  place instead of duplicating. New `GET/POST .../export-json` and
  `.../import-json` endpoints for all three. The current defaults for
  all four importable sections (including the existing Geräte Katalog)
  are now committed as reference/starter files under `docs/templates/`.
- "Alle löschen" bulk-clear buttons, each with a confirmation popup, for
  the Geräte Katalog, Setup → Funktionstypen, and Setup →
  Zentral-/Allgemeinfunktions-Vorlagen — for starting over with your own
  set instead of editing/deleting the seeded defaults one by one. Geräte
  Katalog and Funktionstypen only delete entries not already used by a
  project (in-use ones are skipped and reported, never force-deleted);
  Zentral-Vorlagen have no such restriction, since nothing else
  references them by id. New `DELETE /api/actor-types`,
  `DELETE /api/point-types`, `DELETE /api/central-templates` endpoints.
- More explanation in Setup (Funktionstypen, Zentral-/Allgemeinfunktions-
  Vorlagen, Kategorien) and MANUAL.md's addressing-model section on how
  these relate to the generated GA tree, and why the
  Hauptgruppe=Kategorie/Mittelgruppe=Geschoss/Untergruppe=Punkt scheme is
  built into the tool rather than a configurable setting (KNX's own
  0–31/0–7 main/middle group limits make an alternative ordering, e.g.
  floor-as-main-group, a different addressing engine, not a toggle).
- A new **Setup → Pflichtenheft** sub-tab controls what the Pflichtenheft
  PDF export includes: the Vorbemerkungen text, plus six checkboxes —
  whether to show Vorbemerkungen at all (new, lets you keep the text
  saved but hide the section), Stockwerk-/Raumverzeichnis and
  Geräteliste (on by default, matching prior behavior), and
  **Gruppenadressen**, **Abgangsliste**, and **Klärungsliste** sections
  (off by default, since they can make a larger project's Pflichtenheft
  very long) — `company_profile` gained six new columns for these
  toggles. The Abgangsliste export's per-floor/actuator/channel
  rendering was factored out into a shared `build_abgangsliste_story()`
  so both the standalone export and this optional section use the same
  code.
- The default Vorbemerkungen text (seeded on fresh installs) now covers
  more ground - Beleuchtung, Rollladen/Jalousie treated separately,
  Heizung, and Zentral-/Wetterfunktionen - condensed from common
  real-world Pflichtenheft templates without their page-length detail.
  Installs that already had a `company_profile` row before this default
  text existed (so the fresh-install seed never touched them) get it
  backfilled on next startup too, but only if the field is still empty -
  never overwrites text someone has actually written.
- Pflichtenheft PDF, made more professional: a **Vorbemerkungen** section
  (general operating-convention text, editable/clearable in the new Setup
  → Pflichtenheft tab, seeded with sensible default wording on fresh
  installs), a **Stockwerk- und Raumverzeichnis** table, and a
  **Getestet** checkbox next to every individual function (room-level and
  central/general) for hand-ticking during on-site commissioning —
  paper-style only, no tracked state, since KNXpilot doesn't know which
  physical button/Bedienelement drives which function (that's ETS
  programming).
- A new **Übergabe-Checkliste** PDF export (Pflichtenheft sub-tab, next
  to the existing PDF button): a mostly generic KNX handover checklist
  (Sichtprüfung/Funktionsprüfung/Kundengespräch/Anlagenübergabe, tri-state
  Ja/Nein/Nicht-nötig checkboxes, Bemerkungen column, signature lines for
  Errichter and Kunde/Betreiber) - only the project name is filled in
  automatically.
- A "Projekt öffnen" picker modal (nav dropdown → **Projekt öffnen**):
  search across all projects and open one directly, from any tab,
  without needing to close whatever project is currently open first —
  picking a project always switches straight to it.
- A small 📁 project-name badge in the header, visible from every tab
  once a project is open, with its own **×** to close directly (no need
  to go back to the Projekte tab first). Updates live on open, rename,
  and delete.
- A new **Hilfe** tab renders the full usage manual (`MANUAL.md`) in-app,
  via a new `GET /api/system/manual` endpoint and `frontend/js/hilfe.js`.
  The Markdown-to-HTML renderer that used to be private to the Update
  tab's changelog view moved into `frontend/js/ui.js` as a shared,
  general-purpose `renderMarkdown()` (now also supports arbitrary
  heading depth and fenced code blocks, needed for the manual's KNX
  addressing table and CSV format block).
- README.md screenshots (`docs/screenshots/`): Übersicht, Funktionen,
  Gruppenadressen, and Abgangsliste.
- A GitHub Actions workflow (`.github/workflows/docker-publish.yml`)
  builds and publishes the Docker image to `ghcr.io/seaspotter/knxpilot`
  on every push to `main` (tag `latest`, plus a short-sha tag) and on
  version tags (e.g. `v0.1.0`), as a multi-arch manifest covering
  `linux/amd64` and `linux/arm64` (e.g. Raspberry Pi) — `docker compose
  pull` picks the right one for the host automatically.
- A small version badge in the header (e.g. `v0.1.0`, or
  `v0.1.0-3-gabc1234` for commits since the last release), from a new
  `GET /api/system/version` endpoint (`git describe`, local checkout
  only — no network fetch, unlike the existing update-check endpoint).

### Changed

- The Firma and Pflichtenheft tabs' save buttons now both read simply
  "Speichern" instead of "Firmenprofil speichern" — clearer given both
  tabs save fields on the same underlying profile record.
- The app's accent color (buttons, headings, active-tab underline,
  links) changed from blue to green, and the PDF exports' banner/table-
  header/section-heading color changed from dark navy to dark green —
  no more blue left anywhere in the design system.
- Export/Import/"Alle löschen" for the Geräte Katalog and Setup →
  Kategorien/Funktionstypen/Zentral-Vorlagen moved from a row of wide
  text buttons into a compact icon-button group in each card's top-right
  corner (hover for a tooltip). Import now opens a small popup to choose
  the file instead of an always-visible file picker next to the button —
  new shared `openImportModal()` helper in `frontend/js/ui.js`.
- The projects list's "Aus Sicherung wiederherstellen" and the opened
  project's "Sichern (JSON)" moved the same way, into icon buttons (⭱ in
  the list header, ⭳ next to the new ⧉ Duplizieren icon in the project
  header) instead of a wide text button/inline file input.
- README.md is now a short landing page (pitch, screenshots, key
  features, quickstart, links) instead of the full manual — all detailed
  per-tab usage instructions, the GA addressing model, and the CSV
  format moved to the new `MANUAL.md` (also viewable in-app via Hilfe).
- `docker-compose.yml` now pulls the published `ghcr.io/seaspotter/
  knxpilot:latest` image instead of building locally — a fresh deploy or
  a dependency update is now `docker compose pull && docker compose up
  -d`, no local build tools needed on the server. Building locally is
  still possible by swapping the `image:` line for `build: .`.
- The self-update mechanism's "requirements.txt/Dockerfile changed"
  message (`backend/routers/system.py`) now points at `docker compose
  pull && docker compose up -d` instead of `docker compose up -d
  --build`, matching the new image-based deploy flow.

## [0.1.0] - 2026-08-16

First release: the backend/frontend restructuring plus the full UI/UX
rework that followed it (toasts/modals, workflow dashboard, interactive
GA tree, mobile pass, bulk room add, focused views, nav dropdown,
in-app changelog, editable structure/functions/setup, and the
Gruppenadressen split) — see below for the full detail.

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
  convention. The tree now loads automatically when opening the tab
  (the "Vorschau" button still works, as a manual refresh), and
  Übersicht gained a matching "Gruppenadressen" stat card showing the
  total address count.
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
