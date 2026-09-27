# Changelog

Notable changes to KNXpilot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this file starts from the
restructuring below — history before that is available via `git log`.
Written in English; the app's German on-screen labels appear only where
you need them to find something, always in quotes (e.g. the
"Nicht bestellen" checkbox). Tab and feature names use the English terms
from the glossary in `DEVELOPMENT.md` ("Naming").

## [Unreleased]

### Added

- **"Hilfe" tab: table of contents and search** — a sidebar lists every
  heading from the manual (click to jump), and a search box highlights
  matches in the rendered text, with Enter/Shift+Enter stepping to the
  next/previous match. Entirely client-side (renderMarkdown()/
  extractHeadings() in `ui.js`) - no server-side search index, the manual
  is small enough to filter/highlight in the browser.

### Changed

- **MANUAL.md rewritten much shorter** (~940 → ~330 lines) — cut internal
  code references (function/file names meaningless to the app's actual
  users, one of which pointed at `export_csv()`'s stale old location),
  removed explanations duplicated between the top-level "Die Tabs"
  summary and the detailed per-tab sections, and trimmed every section's
  prose down to what's needed to use the feature (dropped worked examples,
  restated edge cases, and "why it works this way" reasoning beyond the
  one sentence that answers an actual "why can't I..." question). No
  content describing an actual button/behavior was cut - same site
  visited, just fewer words getting there.
- **Last two German file names renamed to English** — `frontend/js/hilfe.js`
  → `help.js`, `frontend/js/projekte.js` → `projects.js` (identifier-only,
  no behavior change; neither is an htmx tab, so these were outside the
  migration list itself but still covered by the standing English-naming
  order).
- **"Gebäudestruktur" ("building structure") split out of the Projekte tab**,
  completing the agreed htmx migration list. `routers/projects.py` and
  `frontend/js/projekte.js` bundled two concerns (project CRUD/list/
  dashboard/backup vs. floors/rooms/the structure tree); the latter moved to
  a new `routers/building_structure.py` and `frontend/js/building_structure.js`.
  `routers/overview.py`'s stat card and the "struktur" subtab id were renamed
  to `building-structure` to match. The tree itself intentionally stays
  classic JS calling the same JSON APIs (not htmx fragments): drag & drop
  needs the whole tree as a client-side object to compute drop targets and
  populate the move dialogs, so there is no safely-separable read-only slice
  to render server-side without duplicating that fetch. No user-visible
  behavior changed.
- **"Abgangsliste" ("circuit list") is now server-rendered with htmx**,
  next in the agreed migration order — only "building structure" remains
  as classic JS now (drag & drop). `routers/abgangsliste.py` ->
  `routers/circuit_list.py` (router tag "circuit-list"); actor-instance
  add/edit/delete, the per-channel circuit-assignment selects and their
  live channel-demand summary are now `/hx/...` endpoints backed by new
  templates in `backend/templates/circuit_list/`. A single circuit
  assignment swaps only that row (its select's options depend on the
  actor-instance list, its channel-demand summary on the assignments, both
  refreshed via an `HX-Trigger` event rather than a full reload), while
  actor-instance add/edit/delete and the bulk "PA automatisch zuordnen" /
  "Alle automatisch zuordnen" actions re-render whole sections. The CSV/PDF
  exports moved from `/api/projects/{id}/export-abgangsliste.csv/.pdf` to
  `/export-circuit-list.csv/.pdf` (the downloaded file names and the CSV's
  columns/content are unchanged - the CSV is the ETS-import format other
  tools read). `build_abgangsliste_story()` -> `build_circuit_list_story()`,
  reused unchanged by `documentation.py`'s optional as-built section
  (chapter anchor `abgangsliste` -> `circuit-list`). `js/abgangsliste.js` ->
  `js/circuit_list.js`, now only loading the tab, the KNX line-select
  wiring, the PA/auto-assign preview dialogs (still plain JS - their
  confirmation dialogs need the computed preview before committing) and
  the CSV/PDF downloads. Renamed every cross-reference: `main.py`, the
  overview stat card, the documentation chapter table, `pa_assign.py`'s
  comment, `index.html`'s sub-tab id/script tag, `lines.js`'s pa-prefix
  field id. No database schema changes needed - `actor_instances`/
  `channel_assignments` were already English. Adds
  `tests/test_circuit_list_hx.py`. Full suite: 153 passed.

- **"Labels" now prints one label per device with a physical address,
  project-wide** — previously only actor instances from the Abgangsliste
  (with an optional, rarely-used per-channel mode); now also includes
  room/floor devices planned in Geräteplanung that have a physical
  address, sorted by address across the whole project. The unused
  per-channel option was removed. The label's second line is deliberately
  just where the device is (its room/floor, or an actor's location label)
  - no device type/manufacturer/model.
- **"Geräteplanung" and "Labels" sub-tabs: rendered server-side with htmx,
  German internal names renamed to English** — per-room/floor device
  add/edit/delete and the "Nicht bestellen" toggle are now server-rendered
  fragments (new templates in `backend/templates/device_planning/`), with
  the project-wide bill of materials ("Stückliste") refreshed as an
  out-of-band swap on every device change. `routers/geraeteplanung.py` →
  `routers/device_planning.py` (router tag `device-planning`); its two PDF
  exports moved from `/api/projects/{id}/export-geraeteliste.pdf` and
  `/export-geraete-je-raum.pdf` to `/export-device-list.pdf` and
  `/export-devices-by-room.pdf`, and the documentation chapter anchor
  `geraete-je-raum` → `devices-by-room`. `js/geraeteplanung.js` →
  `js/device_planning.js` (now only loads the tab and the PDF downloads).
  The Labels tab's export endpoint (`/api/projects/{id}/export-labels.pdf`)
  moved out of `routers/abgangsliste.py` into a new `routers/labels.py`,
  which also renders the tab (`backend/templates/labels/tab.html`);
  `backend/labels.py` (the label-sheet layout registry, `LABEL_FORMATS`)
  is unchanged. `js/labels.js` stays small vanilla JS (the label-position
  grid and the PDF download need no server round-trip), now reading each
  format's sheet size from the rendered `<option>`'s `data-size` instead
  of a duplicated client-side table. Sub-tab id `subtab-geraeteplanung` →
  `subtab-device-planning`; the overview stat-card id and the
  `pa-prefix-geraeteplanung` field renamed to match. JSON API paths
  (`/api/rooms/{id}/devices`, `/api/room-devices/{id}`,
  `/api/floors/{id}/devices`, `/api/floor-devices/{id}`,
  `/api/projects/{id}/device-order-flags/{id}`,
  `/api/projects/{id}/device-summary`) are unchanged.

### Fixed

- **"Klärungsliste" text/answer fields were narrower than intended** — the
  rename to "clarification list" updated the input classes in the template
  but left the matching CSS selectors on their old `kl-text-input`/
  `kl-answer-input` names, so the fields lost their `flex:1`/`min-width`
  sizing and fell back to the default narrow input width.
- **Unchecking a "Funktionscheckliste" item, or clearing a "Übergabe-
  Checkliste" answer, no longer leaves a stale "getestet am" timestamp
  next to it** — the htmx conversion of these two tabs always stamped
  `updated_at` on every write, checked or not, and the row template showed
  it unconditionally; it's now hidden when the item is unanswered again,
  matching the previous behavior.
- **Clearing the device catalog no longer fails when a device is used as
  a floor device** — "Katalog leeren" skipped devices used in rooms or as
  actuators, but not those planned as "devices without a room", so the
  database refused the delete and the whole action failed. Deleting a
  single device that's used in a project now explains why it can't be
  deleted instead of failing with a server error.

- **Update tab no longer half-installs updates with new Python packages** —
  it used to pull such an update and then only ask for `docker compose
  pull`, so until then the new frontend ran against the old backend (e.g.
  "Not Found" in the clarification list after the htmx change). Now it
  doesn't pull at all and shows, already when checking, the one command
  that does the whole update on the server (with a copy button).

### Changed

- **"Funktionen" and "Gruppenadressen" sub-tabs: rendered server-side with
  htmx, remaining German internal names renamed to English** — assigning a
  function to a room, editing/deleting a room point, adding/removing
  special addresses ("Sonderadressen"), the GA tree preview and the
  "Aktuellen Stand als in ETS übernommen markieren" action are now
  server-rendered fragments (new templates in `backend/templates/functions/`
  and `backend/templates/group_addresses/`, new `/hx/...` endpoints).
  Room-point/special-address/GA-preview/export logic moved out of
  `routers/projects.py` (which keeps the building-structure endpoints for
  its own, still-to-come htmx conversion) into two new router modules,
  `routers/functions.py` and `routers/group_addresses.py`; the shared
  `flatten_ga_tree()`/`is_function_row()` helpers moved to `ga_logic.py` so
  both the new group-addresses router and the building-structure drag & drop
  GA-impact dry run use the same logic. `js/funktionen.js` → `js/functions.js`,
  `js/gruppenadressen.js` → `js/group_addresses.js` (now only load their tab
  and hold the few things that stay client-side: the special-address suffix
  row helper, the GA tree expand/collapse, the CSV download). Sub-tab ids
  `subtab-funktionen`/`subtab-gruppenadressen` → `subtab-functions`/
  `subtab-group-addresses`; the overview stat-card ids and the documentation
  chapter anchor `gruppenadressen` → `functions`/`group-addresses`. The CSV
  export, JSON API paths (`/api/rooms/{id}/points`, `/api/room-points/{id}`,
  `/api/projects/{id}/specials`, `/api/projects/{id}/preview`,
  `/api/projects/{id}/ga-changes`, `/api/projects/{id}/ga-snapshot`,
  `/api/projects/{id}/export.csv`) are unchanged.
- **KNX lines: remaining German internal name renamed to English** —
  router `linien.py` → `lines.py`, JS `linien.js` → `lines.js`, router tag
  `linien` → `lines`; its routes, functions and DB schema (`knx_lines`)
  were already English. Identifier-only rename, no behavior change.
- **Function checklist and handover checklist: remaining German internal
  names renamed to English** — router `checkliste.py` → `checklists.py`;
  PDF builders `build_funktionscheckliste_pdf_bytes`/
  `build_uebergabe_checkliste_pdf_bytes` → `build_function_checklist_pdf_bytes`/
  `build_handover_checklist_pdf_bytes`; signature constants
  `UEBERGABE_SIGNATURES`/`FUNKTIONSCHECKLISTE_SIGNATURES` →
  `HANDOVER_SIGNATURES`/`FUNCTION_CHECKLIST_SIGNATURES`;
  `UEBERGABE_ITEMS_BY_KEY` → `HANDOVER_ITEMS_BY_KEY`; the PDF export paths
  `export-funktionscheckliste.pdf`/`export-uebergabe-checkliste.pdf` →
  `export-function-checklist.pdf`/`export-handover-checklist.pdf`; the
  `GET /api/uebergabe-checklist-sections` endpoint →
  `/api/handover-checklist-sections`; and the Dokumentation chapter anchors
  `funktionscheckliste`/`uebergabe` → `function-checklist`/`handover-checklist`.
  The `checklist_status.item_key` values stored for handover-checklist
  items (`uebergabe:<slug>`) are now `handover:<slug>`, migrated in place
  on existing installs. No UI-visible text changed.
- **Function checklist ("Funktionscheckliste") and handover checklist
  ("Übergabe-Checkliste") tabs rendered server-side with htmx** — looks
  and works the same, including the digital signature pad, but their HTML
  now comes from Jinja templates (`backend/templates/function_checklist/`,
  `backend/templates/handover_checklist/`) via `/hx/projects/{id}/
  function-checklist...`/`handover-checklist...` endpoints in
  `routers/checkliste.py`. Tapping a function-checklist row, or a
  handover-checklist Ja/Nein/Nicht-nötig switch or Bemerkungen field, is
  now its own htmx request that swaps back just that row - the
  function checklist still deliberately never re-renders the whole list,
  so scroll position survives while walking through a building. Renamed
  to English: `js/funktionscheckliste.js` → `js/function_checklist.js`,
  `js/uebergabe_checkliste.js` → `js/handover_checklist.js`, the sub-tab
  ids and the "Per E-Mail senden" document keys (`function_checklist`,
  `handover_checklist`). `routers/checkliste.py` and its existing JSON/PDF
  endpoint names/functions (`build_funktionscheckliste_pdf_bytes`,
  `build_uebergabe_checkliste_pdf_bytes`, `CHECKLIST_SECTIONS`) are
  unchanged, since `routers/documentation.py` and `routers/email.py`
  already depend on them.
- **Distribution board planning ("Verteilerplanung") tab rendered
  server-side with htmx** — creating/editing/deleting a board and
  placing/removing/moving RCD, LS and device items on it are now `/hx/
  projects/{id}/distribution-boards...`/`/hx/distribution-boards/{id}...`
  endpoints in the new `backend/routers/distribution_boards.py` (renamed
  from `verteiler.py`), rendering Jinja templates in
  `backend/templates/distribution_boards/`; `frontend/js/verteiler.js` is
  now `frontend/js/distribution_boards.js` and only loads the tab and the
  PDF download. Renamed to English throughout, including the database
  schema: the `verteiler`/`verteiler_items` tables are now
  `distribution_boards`/`distribution_board_items` (migrated in place on
  existing installs, keeping every row), and the JSON API/models moved
  from `/api/verteiler...` (`VerteilerIn` etc.) to
  `/api/distribution-boards...` (`DistributionBoardIn` etc.) - the
  Gebäudestruktur tree's JSON (`distribution_boards`/
  `unplaced_distribution_boards` instead of `verteiler`/
  `unplaced_verteiler`) and `frontend/js/projekte.js`'s drag & drop for it
  were updated to match.
- **Klärungsliste renamed to English throughout** — router
  `klaerungsliste.py` → `clarification_list.py`, JS
  `klaerungsliste.js` → `clarification_list.js`, templates
  `backend/templates/klaerungsliste/` → `clarification_list/`, the sub-tab
  id/HX-Trigger event/JSON keys (`clarification-list`,
  `clarifications-changed`, `type`/`answer`), the API
  (`/api/klaerungen...` → `/api/clarifications...`,
  `KlaerungIn` → `ClarificationIn`) and the PDF export path
  (`export-klaerungsliste.pdf` → `export-clarification-list.pdf`). The
  database table `klaerungen` (with its `typ`/`antwort` columns) is now
  `clarifications` (`type`/`answer`), migrated in place on existing
  installs; a project backup/restore JSON still accepts the old
  `verteiler`/`klaerungen` payload keys from a backup taken before this
  change. No UI-visible text changed.
- **Overview, specification and documentation tabs rendered server-side
  with htmx** — the overview tab's stat cards (one per sub-tab, jumping
  there on click) and its project files ("Dateien") section, and the
  Pflichtenheft/Dokumentation tabs' "Inhalt" lists, now come from Jinja
  templates (`backend/templates/overview/`, `specification/`,
  `documentation/`, `project_files/`) instead of client-side JavaScript
  aggregating a dozen API calls; looks and works the same. Renamed to
  English along the way: `routers/pflichtenheft.py` →
  `routers/specification.py`, `routers/dokumentation.py` →
  `routers/documentation.py`, `js/uebersicht.js` → `js/overview.js`, the
  `Pflichtenheft`/`Dokumentation` sub-tab ids, the export endpoints
  (`export-specification.pdf`, `export-documentation.pdf`) and the
  `*-contents` endpoints.
- **Clarification list rendered server-side with htmx (trial)** — looks
  and works the same, but its HTML now comes from Jinja templates
  (`backend/templates/klaerungsliste/`) via `/hx/...` endpoints, with htmx
  (vendored in `frontend/vendor/`, no build step) doing the requests; the
  tab's JavaScript shrank from ~250 to ~60 lines, the rendering is now
  covered by pytest, and user text is escaped by default. The copy-as-text
  button now uses the same server-side grouping/numbering as the PDF.
  A trial for moving more of the frontend into Python - see DEVELOPMENT.md
  "htmx tabs". New dependency `jinja2` - after updating, run
  `docker compose pull && docker compose up -d` once. The entries now sit
  in a white card like the groups on every other tab.
- **Project manuals tab rendered server-side with htmx** — downloading,
  viewing and deleting a device manual now come from a Jinja template
  (`backend/templates/manuals/tab.html`); the download buttons are
  disabled while a download runs, and a failed download (e.g. a link that
  leads to a web page) is reported with its reason. The project sub-tab ID
  is now `manuals`.
- **Device catalog rendered server-side with htmx** — both sub-tabs
  (catalog and manual URLs) come from Jinja templates
  (`backend/templates/device_catalog/`) via `/hx/device-catalog...`
  endpoints: the search filters on the server, the form shows the
  actuator-only fields and the custom group field without custom
  JavaScript, and edits keep the current search. The JSON import/export
  with its change preview works as before. Renamed to English:
  `routers/device_catalog.py`, `js/device_catalog.js`, tab ID
  `device-catalog`.
- **Setup's settings pages rendered server-side with htmx** — company,
  specification, documentation, email, backup and time tracking now come
  from Jinja templates (`backend/templates/setup/`) via `/hx/setup/...`
  endpoints. Each page's "Speichern" now saves only that page's fields
  (before, every save button wrote all settings of all pages at once) and
  confirms with a toast; backup's "back up now" and the existing-backups
  list are server-rendered too (restoring, which restarts the app, and the
  logo auto-crop stay in the browser). The twelve German-named
  `company_profile` columns are renamed to English
  (`specification_preamble`, `specification_include_*`,
  `documentation_include_*` - renamed automatically on startup, values
  kept), and Setup's sub-tab IDs are English.
- **Setup's categories, function types and central templates editors
  rendered server-side with htmx** — completes the Setup tab. Categories
  are renamed inline instead of in a popup; the data point rows of the
  function type/template forms and the scope-dependent template fields
  work without custom JavaScript; deleting and clearing ask via the app's
  dialog and report back with a toast. JSON export/import work as before.
  The functions tab picks up changes made here immediately. Both lists
  now use aligned columns: name with category/block/channel (or scope) as
  a small line below on the left, the data points lined up next to it.
- **Setup → email as a tidy form** — labels (Versand, Server, Anmeldung,
  Absender, Kopie) in a fixed left column with the fields aligned next to
  them, and the test email in its own block below; a reusable
  `.form-grid` layout for settings forms.
- **Setup → time tracking: switch and rounding side by side** in one row.
- **Time tracking rendered server-side with htmx** — the second tab after
  the clarification list: list, filters, totals, the invoiced checkboxes
  and the add/edit dialog now come from Jinja templates
  (`backend/templates/time_tracking/`) via `/hx/time-tracking...`
  endpoints; the header timer keeps its live clock in the browser. Looks
  and works the same; times are rendered in the browser's time zone (every
  htmx request now sends it), and the tab's endpoints are covered by
  pytest. Renamed to English along the way: `routers/time_tracking.py`,
  `js/time_tracking.js`, and the `company_profile` columns
  `time_tracking_enabled`/`time_tracking_rounding_minutes` (renamed
  automatically on startup, values kept).
- **English names for everything but UI text** — standing convention:
  file names, identifiers, database tables, API paths, CSS classes and
  JSON keys are English, with a glossary for the domain terms in
  `DEVELOPMENT.md`; existing German names get renamed tab by tab. This
  changelog is now consistently English too.

## [0.8.0] - 2026-09-26

A big planning and handover release. The building structure is now an
ETS-like tree with drag & drop (floor → room → distribution board),
projects can be split into several KNX lines with physical addresses
assigned per line, and the function and handover checklists got a clearer
table layout with test dates and signatures. The specification and
documentation tabs show what their PDF contains - the documentation tab
doubles as a readiness check before handover - and the per-project JSON
backup now holds the complete project. Also: automated tests in CI, all
dependencies updated (fixes the open security alerts), and a `:dev`
Docker image. After updating, run `docker compose pull && docker compose
up -d` once - the Python packages changed.

### Added

- **Complete per-project JSON backup** — the JSON backup used to contain
  only the structure, functions, special addresses and lines; restoring it
  lost the circuit list, device planning, distribution boards and all
  on-site results. It now holds the whole project: actuators with channel
  assignments and physical addresses, planned devices, "Nicht bestellen"
  flags, distribution boards, clarifications, checklist ticks and notes,
  signatures, the last ETS export snapshot, project files and fetched
  manuals (never time tracking). Every reference is by name/position, so
  it restores on another install; unknown devices are reported, not
  guessed. **Duplicate** now copies the full planning (incl. actuators,
  assignments, devices, distribution boards) but starts untested, unsigned
  and never exported. Older backup files still import. The code moved to
  `backend/project_transfer.py`.
- **Function checklist: test date and signatures** — every ticked row
  shows when it was ticked (the existing `updated_at`, now also printed
  under the checkbox in the PDF), and a new confirmation block
  ("Bestätigung: Funktionen getestet") takes on-screen signatures from the
  system integrator and, optionally, the customer (own `fc_*` roles,
  separate from the handover checklist's). They appear in the function
  checklist PDF and the documentation chapter; the documentation tab's
  contents card flags a missing system integrator signature.
- **README screenshots refreshed**, plus new ones of the building
  structure tree and the documentation tab.
- **Contents card and preview on the specification and documentation
  tabs** — both tabs used to show just two buttons. They now list the
  PDF's sections/chapters in order, each with whether it's included and
  what's in it; on the documentation tab this doubles as a readiness check
  (e.g. 9 of 36 functions tested, 0 of 2 signatures, open clarifications -
  shown in orange). The documentation's chapter list comes from the same
  spec the PDF's table of contents is built from. The **preview** button
  ("Vorschau") opens the PDF in a new browser tab instead of downloading
  it (`?inline=1` on both exports).
- **Building structure as a tree with drag & drop** — floor → room →
  distribution board as a compact collapsible tree (like the building view
  in ETS) instead of one card per room. Rooms can be dragged to another
  position or floor, floors reordered, and a distribution board dropped on
  a floor or into a room; a ⇄ button does the same without a mouse. Moves
  that change group addresses ask first and say how many (computed by a
  dry run on the server); after an ETS export the GA changes view lists
  what to update in ETS.
- **Distribution board in a room** — a distribution board can now
  optionally sit in a room (e.g. a technical room), chosen when creating
  it or by dragging it in the tree; shown on the distribution board card
  and in its PDF heading. When the room moves to another floor, the
  distribution board goes along.
- **Docker image for the dev branch** — every push to `dev` now also
  publishes `ghcr.io/seaspotter/knxpilot:dev`. A server tracking `dev`
  sets `KNXPILOT_IMAGE_TAG=dev` in a `.env` file next to
  `docker-compose.yml`, so `docker compose pull` after a dependency change
  gets matching packages instead of the `main` image. The Update tab's
  "new image needed" message says so when it runs on a non-main branch.
- **KNX lines (optional)** — projects split into several TP lines via
  line couplers (e.g. one line per apartment plus an outdoor line) can
  define their lines in the building structure and assign each floor, and
  optionally a single room or actuator, to a line. Automatic physical
  address assignment ("PA automatisch zuordnen") then numbers each line on
  its own (`1.1.10…`, `1.2.10…`), with the line coupler getting the line's
  `.0`. The lines table shows device counts per line and warns about more
  than 64 devices or a missing line coupler/bus power supply. Projects
  without lines behave exactly as before. Lines are included in JSON
  backups and when duplicating a project.
- **Automated tests** — a `pytest` suite (`tests/`, dev dependencies in
  `requirements-dev.txt`) covering schema migrations on fresh and old
  databases, the ETS group-address CSV against a golden file, every
  PDF/CSV/JSON export with special characters, time tracking rounding and
  editing, manual downloads and delete impact; runs in CI on every push
  (`.github/workflows/tests.yml`). The database location can now be
  overridden with `KNXPILOT_DB_PATH` (used by the tests). Writing it
  immediately found the download-filename bug below.
- **Group addresses: changes since the last ETS export** — every ETS CSV
  download now remembers the exported group addresses, and a new card at
  the top of the group addresses tab ("Änderungen seit dem letzten
  ETS-Export") shows what still has to be done in ETS, in working order:
  **moved** (a function now sits on a different address - typically
  because a new function shifted the rest of the floor's block; change the
  address in ETS to keep its links, listed highest-first so each target is
  already free), **new**, **changed** (same address, new name/DPT, e.g. a
  renamed room) and **removed**. A button ("Aktuellen Stand als in ETS
  übernommen markieren") sets the baseline without downloading - needed
  once for existing projects. New `ga_export_snapshots` table and
  `GET .../ga-changes` / `POST .../ga-snapshot` endpoints.
- **Groundwork for the ETS import** — `docs/FINDINGS-knxproj.md` lists the
  assumptions about the `.knxproj` format to verify against real exports
  before building the import, a proposed ETS → KNXpilot mapping and the
  open questions (password-protected projects, reusing an existing parser);
  `tools/knxproj_probe.py` is a read-only, standard-library-only inspector
  to run on a real export for that verification.
- **Dependabot** — `.github/dependabot.yml` opens weekly, grouped update
  PRs against `dev` for GitHub Actions, Python packages and the Docker base
  image. All workflows now use the latest (Node 24) majors of their actions
  (`actions/checkout@v7`, `actions/setup-python@v7`, docker/* latest),
  replacing the Node 20 versions GitHub deprecated.

### Changed

- **Handover checklist in the same table look** — each item has a
  yes / no / not needed switch on the right (the chosen answer coloured,
  tapping it again clears it), when it was answered, and a slimmer remarks
  line; README screenshot refreshed.
- **Function checklist as a table** — category pill in front, function in
  a slightly smaller font, and the "tested" checkbox on the right; the
  whole row is tappable and tested rows are greyed out.
- **Bill of materials sorted alphabetically by device** — manufacturer +
  model, case-insensitive, instead of by group; the same order in its PDF,
  the specification's device list and the manuals lists.
- **One bill of materials in every PDF** — the specification/documentation
  used a shorter group/device/quantity table than the device list (order)
  export. Both now render the same table (manufacturer, model,
  description, group, quantity - manufacturer first, matching the
  alphabetical order) with the devices marked "Nicht bestellen" listed
  underneath as already present.
- **Circuit list: actuators sorted by floor** — the project's actuator
  list (and every actuator picker built from it: circuits, labels,
  distribution board planning) now follows the building structure's floor
  order, like the circuits list already did; actuators without a floor
  come last.
- **Deleting a floor or room now asks first and says what goes with it** —
  previously deleting a floor or room happened immediately, without any
  confirmation, even though a floor takes all its rooms, functions,
  channel assignments, planned devices and clarifications with it. The
  confirmation now lists exactly what gets deleted and what only loses its
  floor (actuators, distribution boards); deleting a whole project shows
  the same breakdown and notes that logged time tracking entries are kept.
  New `GET .../delete-impact` endpoints for projects, floors and rooms.
- **Bulk actions show a preview before changing anything** — automatic
  circuit assignment ("Alle automatisch zuordnen") lists which circuit
  would go to which actuator channel and what can't be assigned; automatic
  physical address assignment ("PA automatisch zuordnen") lists which
  address goes to which device in which room; importing the standard
  catalog and a catalog JSON import list the new devices and, per changed
  device, each field's old and new value - so e.g. a description you
  edited yourself is never overwritten unseen, and an import with nothing
  to change doesn't run at all. The circuit preview runs the real
  assignment logic and rolls it back, so it can't differ from the actual
  result. New preview endpoints (`.../circuits/auto-assign?dry_run=true`,
  `.../assign-physical-addresses/preview`, `/api/actor-types/import-*/preview`).
- **Group addresses: removed the manual refresh button** — the GA tree
  (and now the ETS-changes card) is regenerated every time the tab is
  opened, so the refresh button was redundant (and was also the only
  oversized button in that row).

### Security

- **All dependencies updated to their latest releases** - fixes the 25
  known vulnerabilities Dependabot reported right after being enabled:
  Pillow 10.4.0 → 12.3.0 (17 advisories, incl. out-of-bounds writes and
  decompression bombs - relevant since logos/signatures are uploaded
  images) and python-multipart 0.0.12 → 0.0.32 (8 advisories, incl.
  denial of service via crafted uploads). Also FastAPI 0.115 → 0.141
  (Starlette 1.x), uvicorn 0.30 → 0.54, ReportLab 4.2 → 5.0; test tooling
  pytest 9 and httpx2 (Starlette's new test-client dependency). Dependabot
  security alerts and automatic security updates are now enabled for the
  repository. `main` is now a protected branch (no force pushes or
  deletion; a push must have passed the Tests workflow) - see the release
  routine in `DEVELOPMENT.md`.

### Fixed

- **Downloads no longer fail for names with special characters** — every
  export put the project name (or an uploaded file's name) into the
  download's filename header, which only allows Latin-1: a name containing
  e.g. an en dash "–" or "€" made every PDF/CSV/JSON export of that project
  fail with a server error, and a double quote broke the header. Filenames
  are now sent RFC 5987-encoded (exact UTF-8 name plus an ASCII fallback).
- **Special addresses of a deleted floor no longer linger** — deleting a
  floor now also removes the special addresses assigned to it; before,
  they stayed in the database invisibly, never showing up in the GA tree
  again.

## [0.7.1] - 2026-09-26

Open clarification list items can now be passed on to the customer or
electrician - as copyable text, a PDF with an answer column, or by email.
GitHub Releases are now created automatically from version tags, and a
special-character bug in the documentation PDF is fixed.

### Added

- **Clarification list: pass on the open items** — a new card in the
  clarification list tab ("Offene Punkte weitergeben") to clarify open
  questions with the customer or electrician: **copy as text** (numbered
  list grouped by room, for pasting into your own email - also works on a
  plain `http://` LAN address, where the browser's clipboard API isn't
  available), **PDF download** (an "open items" PDF with no./type/
  question/answer columns - answers already noted are filled in, otherwise
  left blank to fill in by hand) and **send by email** (same PDF via the
  existing email feature). Only entries with status *open*; text and PDF
  use the same numbering. New endpoint
  `GET /api/projects/{id}/export-klaerungsliste.pdf`.
- **GitHub Releases are created automatically** — new
  `.github/workflows/release.yml`: pushing a `vX.Y.Z` tag now also creates
  the GitHub Release, using that version's CHANGELOG section (including an
  optional summary paragraph right under the version heading) as the
  release text - no more creating releases by hand. Release routine
  documented in `DEVELOPMENT.md`.

### Fixed

- **Documentation PDF no longer breaks on special characters in the
  clarification list** — an entry containing `&` or `<` in its text or
  answer made the optional clarification list section (and with it the
  whole documentation PDF and its email sending) fail.

## [0.7.0] - 2026-09-26

Adds simple per-project time tracking, sending PDF exports by email, and
device manuals fetched on click into their own manuals tab. The project
tabs get a clearer, aligned room layout, the device lists and PDFs now
show each device's description, and a fresh-install bug in the device
catalog is fixed.

### Added

- **Time tracking: simple per-project time tracking** — while a project is
  open, the header shows a **▶ Start** button; a running timer shows its
  start time, a live clock and a stop button (survives closing the
  project, switching tabs or reloading; at most one timer at a time). New
  top-level **time tracking** tab: totals per project, all entries with
  edit/delete, a button to add forgotten times afterwards, an **invoiced**
  checkbox per entry plus "mark all shown as invoiced", filters by project
  and invoiced yes/no, and a **timesheet PDF** of the current selection.
  Start/stop snap to the nearest mark of a configurable grid (default
  15 min: 12:04 → 12:00, 12:55 → 13:00; minimum one grid step per entry);
  the manual-entry form only offers times on that grid. New Setup →
  **time tracking** sub-tab to switch the feature off (tab + header button
  hidden, data kept) or pick the grid: to the minute, 15 or 30 minutes - a
  changed grid only applies to new or re-saved entries, never
  recalculating already-invoiced ones. Strictly internal: stored in its
  own global `time_entries` table (kept when a project is deleted), never
  part of any project export (specification, documentation, checklists,
  JSON backup/duplicate, email). New `backend/routers/zeiterfassung.py`
  and `frontend/js/zeiterfassung.js`.
- **Device manuals: curate a URL, fetch into the project on click** — the
  device catalog gets a new **manuals** sub-tab (next to the existing
  catalog sub-tab) for storing a manufacturer PDF URL per device; leaving
  it blank simply means it's unused, no per-device tracking needed. Every
  project gets its own new **manuals** sub-tab, kept deliberately separate
  from the project files (files are what you upload yourself; manuals are
  what KNXpilot fetches on your behalf, stored in its own
  `project_manuals` table) - it lists every device actually used in the
  project that has a curated URL, with a download button per device
  (fetches the PDF server-side) plus a download-all button for the rest;
  already-fetched devices show view (opens the PDF in a new browser tab)
  and delete buttons instead, and re-fetching a still-saved one is a no-op
  rather than a duplicate download. Only ever runs on this explicit click,
  never automatically - same "manual, confirm first" principle as the
  email-sending feature. Plain stdlib `urllib` http(s) GET (no new
  dependency, no scraping/search), capped at 25 MB per file (same cap as
  project files). Only real PDFs are accepted - a link that lands on a web
  page instead, or a download that breaks off midway, is reported as a
  clear error (and skipped by download-all without stopping the rest)
  instead of being saved. Re-importing the device catalog (manual JSON
  import or importing the standard catalog) never overwrites a curated
  manual_url that isn't present in the imported data. The documentation
  export gets a matching optional **manuals** chapter (Setup →
  documentation, on by default) - a checklist-style list of which used
  devices have a manual on file and whether it's already been fetched;
  the PDFs themselves are deliberately not merged into the export, they
  stay in the project's own manuals tab.
- **Send PDF exports by email** — a send-by-email button ("Per E-Mail
  senden") next to the PDF download on the specification, function
  checklist, handover checklist and documentation tabs. Always
  manual/one-click - never triggered automatically (e.g. right after a
  signature is captured) - and always shows a confirmation dialog
  (pre-filled recipients, editable) before anything is sent. New
  per-project **email** (customer) and **further recipients** (free text,
  e.g. a general contractor) fields in the project edit form pre-fill the
  "to" field; a new Setup → **email** tab holds the SMTP credentials (same
  enable-flag/credentials shape as the existing Nextcloud backup fields)
  plus a "copy to me" default and a test-email button to verify the setup
  works before relying on it. New `backend/email_sender.py` (stdlib
  `smtplib`, no new dependency) and `backend/routers/email.py`
  (`GET /api/projects/{id}/email-defaults`,
  `POST /api/projects/{id}/send-email`, `POST /api/send-test-email`); each
  PDF export's story-building logic was factored out into a reusable
  `build_*_pdf_bytes()` function shared by the download endpoint and the
  new send-by-mail action, so the emailed PDF is always identical to the
  downloaded one.

### Changed

- **Device list and devices-per-room PDFs show the device description** —
  both exports (and the devices-per-room section of the documentation PDF)
  get a new **description** column filled from the device catalog's
  description field, so a bare model number like "BE-GT2TW.02" comes with
  a readable "Glastaster II Smart Weiß mit Temperatursensor". All cells in
  these tables now wrap instead of overflowing into the next column.
- **Device planning: the bill of materials is now a table** — columns
  device, description (from the device catalog), group, quantity and the
  "Nicht bestellen" checkbox, instead of a list of pills; devices marked
  as already available are greyed out with an "already present" tag.
- **Manuals sub-tab shows the device description** — each device line
  now shows its device catalog description next to the model number
  (e.g. "MDT BE-GT2TW.02 — Glastaster II Smart Weiß mit Temperatursensor").
- **Functions: the function dropdown remembers your last choice** — after
  adding a function, every room's dropdown now stays on the function type
  you last picked instead of jumping back to the first entry, so adding
  e.g. dimmed light to several rooms in a row needs no re-picking. Resets
  on page reload.
- **Clearer room layout across the project tabs** — in the functions tab,
  each room name is now a heading with an accent underline, function types
  sit in a fixed left column so every row's label pills start at the same
  position, the pills are larger, and the "add function" row is set apart
  by a divider. The same layout now applies to **device planning**
  (devices grouped by group, physical address and note shown inside the
  pill), the **circuit list** (circuits grouped by floor → room, with
  aligned function type / function / actuator channel columns instead of
  one flat list), and the floor/room headings of the **building
  structure**, **function checklist**, **clarification list** and
  **handover checklist**. On narrow screens the type label moves above
  its pills.

### Fixed

- **MDT AKD-0424R.02 / AKD-0424R2.02 are LED controllers, not dimmers** —
  the bundled starter catalog (`docs/templates/geraete-katalog_mdt.json`)
  had their type set to `Dimmen`; it's now `LED`. Only affects new
  installs automatically - an existing catalog picks it up by importing
  the standard catalog again in the device catalog (or by editing the two
  devices by hand).

## [0.6.0] - 2026-08-20

### Added

- Split the old specification tab (which conflated the pre-project spec, a
  never-persisted "tested" paper checkbox, and a grab-bag of optional
  as-built sections) into four focused sub-tabs:
  - **Specification** narrowed to just the early-stage spec (preamble,
    floor/room directory, planned functions/devices per room, device list)
    - no more checkbox column, nothing has been tested yet at this stage.
  - **Function checklist** (new): every planned function, tap-to-check
    digitally on-site (persisted, not printed/hand-ticked), plus a PDF
    export snapshot.
  - **Handover checklist** (new): the handover checklist, now filled in
    digitally on-site (yes/no/not needed + remarks per item, persisted)
    instead of only existing as a paper PDF; PDF export still available
    for signing. Scoped to the system integrator's own work
    (programming/commissioning, customer walkthrough, handover) - dropped
    the items about physical electrical installation (wiring, mounting,
    labeling, E-Check), which is the electrician's job, not this tool's
    user's; the PDF's signature line now reads "Systemintegrator" (system
    integrator) instead of "Errichter" (installer). Also supports
    capturing a real **digital signature** on-site (system integrator and
    customer/operator, drawn on an HTML canvas with a finger/mouse,
    editable/re-signable/deletable at any time) - embedded into the PDF
    export with a "signed at" timestamp instead of a blank line, no
    printing/scanning needed. New `project_signatures` table, new
    endpoints (`GET/PUT/DELETE /api/projects/{id}/signatures[/{role}]`,
    `GET /api/projects/{id}/signatures/{role}/image`). The system handover
    section was consolidated - four overlapping "is documentation/software
    handed over" items collapsed into one clear item each (operating
    instructions, system documentation, software/backups, passwords).
  - **Documentation** (new): the end-of-project assembly - the
    specification's content (now explicitly labeled as its own
    "Pflichtenheft" chapter, so it doesn't read as if written for this
    document) plus both checklists' actual recorded results, plus the
    optional as-built sections (circuit list, distribution board planning,
    group addresses, clarification list, devices per room) moved here from
    the specification's old Setup toggles (now under Setup →
    documentation, which also gained two new toggles - the function and
    handover checklists were previously always included, now optional like
    the rest, default on). The PDF opens with a short intro plus a
    clickable **table of contents** - real internal PDF links that jump
    straight to each included chapter.

  Fixed along the way: the standard "page X of Y" footer trick (deferring
  page-number drawing to the very end) silently broke ReportLab's
  internal-link anchors, since it postpones the API call that actually
  registers which page a bookmark is on - every table of contents entry
  was landing on page 1 regardless of its real target. The documentation
  PDF now does a genuine two-pass build (`build_pdf_response_two_pass()`)
  instead; every other export is unaffected.

  The overview sub-tab's summary cards now cover all three new tabs (the
  function and handover checklists show a checked/answered count, the
  documentation a static card) and no longer show the specification's old
  "view preview" text (stale since that tab's preview was removed).

  New `checklist_status` table (shared by both digital checklists), new
  `backend/routers/checkliste.py` (`GET/PUT
  /api/projects/{id}/checklist-status[/{item_key}]`,
  `GET /api/rooms/{id}/function-checklist`,
  `GET /api/projects/{id}/central-functions-checklist`,
  `GET /api/uebergabe-checklist-sections`, plus both PDF exports), new
  `backend/routers/dokumentation.py`
  (`GET /api/projects/{id}/export-dokumentation.pdf`).
- **Project files** section on the overview sub-tab: upload/download/delete
  a handful of reference files per project (building drawings, manuals, an
  ETS export), max. 25 MB each. Stored as a BLOB directly in the SQLite
  DB, so they're automatically covered by the existing whole-database
  backup feature with no separate file-storage/backup path needed -
  deliberately not included in a project's JSON export or duplication
  (backup/restore/duplicate), which stay a lightweight building structure/
  group addresses-only copy. New `project_files` table, new
  `backend/routers/project_files.py`
  (`GET/POST /api/projects/{id}/files`,
  `GET /api/project-files/{id}/download`, `DELETE /api/project-files/{id}`).

### Fixed

- The default device catalog was empty in a plain-image deployment
  (Portainer, bare `docker run`, no `docker-compose.yml` bind-mount), and
  **⟲ importing the standard catalog** silently imported 0 devices instead
  of fixing it - the `Dockerfile` never copied `docs/templates/`, where
  both the fresh-install seed and that button's re-import read the
  bundled `geraete-katalog_*.json` files from. Same root cause as the
  earlier help/changelog fix (v0.4.1) and the version-badge fix (also
  v0.4.1) - a data directory missing from the image, not a code bug -
  just not caught for this one at the time since `docs/templates/` is a
  third, separate directory from `CHANGELOG.md`/`MANUAL.md`. Verified by
  reproducing it: ran the app from a directory tree matching exactly what
  the Dockerfile now copies (no `docs/`), confirmed 0 devices seeded and
  0 imported by the button, added the `COPY`, reran, confirmed 91 devices
  seeded fresh and 91 re-imported after clearing the catalog.

## [0.5.0] - 2026-08-18

### Added

- Mobile/tablet-optimized data entry across the whole app, not just the
  on-site-usable tabs from the previous pass: every genuine multi-field
  form row now stacks each field onto its own full-width line below
  700px instead of wrapping several fixed-width fields into a cramped
  multi-column jumble - the functions tab's room-function quick-add, the
  device catalog's add-device form, the building structure, Setup
  (company, function types, central/general function templates, backup),
  project create/rename/meta-edit modals, the create form in distribution
  board planning, and more - via an opt-in `.mobile-fields` class, not
  applied to every `.row` (most are button toolbars that already wrap fine
  as-is). Several inline `style="width:…"`/`style="min-width:…; flex:1"`
  attributes were converted to shared width classes
  (`.w-60`/`.w-110`/.../`.w-220`, `.flex-input`, `.flex-input-wide`) along
  the way, since a mobile media query can't override an inline style
  without `!important`. Distribution board planning's DIN-rail row diagram
  (percentage-width boxes that became illegible, though not
  page-overflowing, once squeezed onto a narrow screen) gets a
  horizontal-scroll wrapper with a legible minimum width instead of being
  force-stacked like a form. Also: bigger touch targets app-wide below
  700px (buttons, inputs/selects incl. 16px font to avoid iOS Safari's
  auto-zoom-on-focus, icon buttons, inline pill edit/delete links),
  info-icon/icon-button tooltips capped to the viewport width, and a fix
  for the Update/help tabs' markdown-rendered `<pre><code>` blocks (e.g.
  the CSV column list in the manual) causing page-level horizontal
  overflow despite their own `overflow-x:auto`. Verified via CDP at a
  375px viewport across all 19 tabs/subtabs - zero horizontal overflow
  anywhere - and confirmed desktop (1400px) is visually unchanged.

### Fixed

- PDF exports no longer strand a section heading alone at the bottom of a
  page with its table/content starting on the next one - every
  `SectionHeading`/`RoomHeading` across the shared PDF story-builders
  (device list, devices per room, distribution board planning, circuit
  list, specification incl. group addresses, handover checklist) is now
  wrapped with at least its first following flowable in a ReportLab
  `KeepTogether` group. Safe for long tables too - `KeepTogether` only
  forces a fresh-page start for the group, it doesn't stop a long table
  from paginating normally afterwards (verified against a 200-row table).
- The header version badge now shows something meaningful in a plain-image
  deployment too (Portainer, bare `docker run`, no `docker-compose.yml`
  bind-mount) instead of going blank - `GET /api/system/version` fell back
  to `None` whenever there was no live `.git` checkout to `git describe`.
  The version is now baked into the image at build time (`KNXPILOT_IMAGE_VERSION`,
  set via `--build-arg` in `.github/workflows/docker-publish.yml`, which
  now also fetches full tag history to compute it) and used as a fallback
  only when the live git describe isn't available.

### Added

- New [`DEPLOYMENT-authelia-synology-portainer.md`](./DEPLOYMENT-authelia-synology-portainer.md) -
  a tested, standalone walkthrough for running KNXpilot behind Authelia
  on a Synology NAS via Portainer (image-only, no git checkout on the
  server), including the Synology reverse-proxy configuration and a
  troubleshooting table for the real issues hit along the way.

### Fixed

- `authelia/nginx.conf` hardcodes the forwarded scheme to `https` instead
  of reflecting the incoming connection's own scheme (`$scheme`) - this
  front proxy only makes sense behind a TLS-terminating edge reverse
  proxy, and most of those (Synology's DSM reverse proxy included)
  forward internally over plain HTTP after terminating TLS themselves, so
  `$scheme` evaluated to `http` and Authelia rejected the session cookie
  as an "insecure scheme". Found via real-world testing behind a Synology
  reverse proxy.
- `docker-compose.authelia.yml`'s `authelia` service now publishes port
  9091 (`ports`) instead of only `expose`-ing it - an edge reverse proxy
  (Synology's included) runs on the host, not inside the compose network,
  so it could never actually reach the login portal with `expose` alone;
  the `auth.*` subdomain would 404 instead of showing the Authelia login.
- `Dockerfile` now also copies `CHANGELOG.md`/`MANUAL.md` into the image -
  previously only `backend/`/`frontend/` were included, so the **help**
  tab and the Update tab's changelog viewer came up empty when running
  the plain image directly (e.g. Portainer) instead of the documented
  `docker-compose.yml` bind-mount deployment. Unlike self-update (which
  genuinely needs a real git checkout), these are just static files, so
  this fixes it properly rather than hiding the tab.

## [0.4.1] - 2026-08-18

### Added

- The **Update** tab now auto-hides when `/app` isn't a real git checkout
  (e.g. running the plain `ghcr.io/seaspotter/knxpilot` image directly -
  in Portainer or a bare `docker run` - instead of the documented
  `docker-compose.yml` bind-mount deployment) - previously it showed a
  confusing raw git error, since self-update can never work without the
  repo mounted in. No configuration needed, detected automatically. New
  `self_update_available` field on `GET /api/system/version`. See
  `DEPLOYMENT.md`, section "Betrieb ohne Bind-Mount" (running without the
  bind mount) for the same deployment mode's related help/changelog
  limitation.

## [0.4.0] - 2026-08-18

### Added

- New `docker-compose.authelia.yml` - an alternative deployment stack
  fronting KNXpilot with [Authelia](https://www.authelia.com/) (password +
  TOTP login) behind an nginx forward-auth proxy, for setups that expose
  KNXpilot via a domain/reverse proxy (e.g. a Synology DSM reverse proxy)
  instead of only within the LAN. See `DEPLOYMENT.md`, section "KNXpilot
  hinter Authelia" (KNXpilot behind Authelia).
- New **devices per room** PDF export (the PDF download in that section
  of device planning) - every device in the project (room devices, floor
  devices, and the circuit list's actuator instances) grouped by
  floor/room with group, manufacturer, model and physical address, as an
  installation reference distinct from the order-focused device list
  export. Also available as an optional specification section (a new
  devices-per-room checkbox in Setup → specification, same pattern as the
  existing circuit list/distribution board planning sections there). New
  `GET /api/projects/{id}/export-geraete-je-raum.pdf`, new
  `pflichtenheft_include_geraete_je_raum` company-profile column.
- Device planning devices can now attach directly to a **floor** instead
  of always requiring a room - for devices that don't belong to any
  particular room, e.g. a weather station on the facade or an outdoor
  motion detector. New "devices without a room" section per floor, same
  add/edit/quantity/address behavior as room devices (including working
  with automatic physical address assignment and "Nicht bestellen"). New
  `floor_devices` table (sibling to `room_devices` rather than an in-place
  migration), new `GET/POST /api/floors/{id}/devices`,
  `PUT/DELETE /api/floor-devices/{id}`.
- Device planning's bill of materials entries can be marked **"Nicht
  bestellen"** (don't order; per project, per device type) for devices
  already on hand - e.g. a spare weather station or gate actuator left
  over from another job. Stays visible in the bill of materials (with an
  "already present" note) but drops out of the device list PDF's order
  table, listed separately underneath instead. New `device_order_flags`
  table, new `PUT /api/projects/{id}/device-order-flags/{device_type_id}`.
- Device list PDF (device planning → PDF download) reworked: manufacturer
  and model are now separate table columns (previously combined into one
  "device" column), and the per-room distribution section is gone - this
  export is meant as a clean order list for a supplier, not a room-by-room
  breakdown (that's what the specification's own device listing is for).
- Device planning entries are now **per-instance** instead of quantity-
  aggregated (one row was "N× DeviceType"; now each physical device is its
  own row) so each can carry its own **physical address**, the way the
  circuit list's actuator instances already could - non-actuator bus
  devices (sensors, operating elements, weather stations) need an
  individual KNX address too, not just actuators. "Quantity" in the
  quick-add form now means "how many independent rows to create at once";
  each is editable (note + address) via a new edit link. One-time,
  idempotent migration splits any pre-existing aggregated row into that
  many quantity=1 rows - no data lost. New `PUT /api/room-devices/{id}`.
  The quick-add form itself now also takes a physical address directly
  when adding exactly one device at once (disabled for bulk-adds of more
  than one, since a single typed-in address can't be distributed across
  several new rows).
- **Automatic physical address assignment** ("PA automatisch zuordnen";
  circuit list and device planning, both act project-wide across both
  tabs) fills in physical KNX addresses for every device without one,
  following a fixed convention: a system devices block (0-5), then one
  actuators block per floor, then one sensors/operating elements block per
  floor, then an outdoor block (any floor marked outdoor/unheated, weather
  station devices first) - each block starts at the next multiple of 10
  and reserves as many full decades as its actual device count needs, so
  later additions don't collide with the next block. Never overwrites an
  address already set; devices with no floor are skipped and reported.
  Area.line prefix (default `1.1`) is editable per run. New
  `backend/pa_assign.py`, new
  `POST /api/projects/{id}/assign-physical-addresses`.
- Device planning's **bill of materials** (project-wide, both the in-app
  total and the device list PDF's per-room breakdown) now also counts
  actuator instances placed via the circuit list tab - previously those
  only counted if separately re-entered as a `room_devices` planning entry
  too, so the "total" undercounted anything only wired via the circuit
  list. The overview dashboard's device planning card total updates
  accordingly, since it already reads from the same endpoint. New
  `_actor_instance_room_rows()` helper factors the merge for the PDF's
  per-room section, grouped by location label (circuit list actuator
  instances don't have a `room_id`, only a floor + free-text location).
  The **actuator** group is no longer offered in device planning's device
  picker either - now that circuit list actuators already count toward the
  same bill of materials, entering an actuator here too would just be a
  second, redundant (and easy to lose track of) way to log the same kind
  of device, with none of the circuit list's floor/address/channel
  tracking.
- The **overview** gets a distribution board planning card ("N
  distribution boards created"), matching the one-card-per-sub-tab pattern
  already used for the others (labels still excluded - no natural short
  summary for it).
- Circuit list: actuator instances can now be **edited** (floor, location
  label, physical address) after being created — e.g. add actuators first
  and fill in the physical address later, once known. The actuator type
  itself isn't editable this way (delete and re-add instead), since a
  different channel type/count could orphan already-assigned circuits. New
  `PUT /api/actor-instances/{id}`.
- **Distribution board planning** — new project sub-tab: a simple visual
  DIN-rail cabinet layout per floor. A distribution board has a fixed
  number of 12-TE rows; each row holds RCD/circuit breaker blocks (simple
  labeled/sized placeholders, default 4TE/1TE, no link to specific
  circuits yet - see `ROADMAP.md`) and/or actuator instances already
  placed via the circuit list tab, sized from their device catalog TE
  width (a device without a TE width set can't be placed, and the device
  picker shows each candidate's TE alongside its address). Rows enforce
  the 12 TE capacity and a device can only be placed once across all
  distribution boards in a project. New `verteiler`/`verteiler_items`
  tables, new `backend/routers/verteiler.py`.
- Distribution board planning: the **PDF download** exports every
  distribution board in the project as one document - one
  proportionally-sized row table per DIN-rail row, matching the on-screen
  layout. Can also be optionally included in the specification PDF (new
  checkbox in Setup → specification, same on/off pattern as the circuit
  list/group addresses/clarification list). New
  `GET /api/projects/{id}/export-verteilerplanung.pdf`, new
  `company_profile.pflichtenheft_include_verteilerplanung` column.
- Device catalog entries can now record a **TE** ("Teilungseinheiten",
  DIN-rail width units - 1 TE = 18mm) alongside type/channels. Optional,
  blank unless known - only meaningful for rail-mounted devices. First
  piece of the still-unbuilt DIN-rail/distribution board layout roadmap
  item (`ROADMAP.md`): capturing device widths now, independent of the
  bigger allocation/layout work that builds on it later. New
  `actor_types.width_te` column, included in export/import JSON.
- The seeded starter catalog now includes real datasheet TE widths for
  most rail-mounted devices (MDT, Phoenix Contact, Gira, Enertex - fed
  in by the user), plus 14 previously-uncatalogued devices found along
  the way (two more MDT shutter actuators with travel time measurement,
  nine Enertex system/power-supply/dimmer devices, three Theben
  presence/motion sensors).
- The starter catalog is no longer a hardcoded Python list - a fresh
  install now seeds directly from the bundled `docs/templates/
  geraete-katalog_<manufacturer>.json` files (one per manufacturer:
  `_mdt`, `_bj`, `_phoenix`, `_elsner`, `_theben`, `_gira`, `_enertex`,
  `_hoermann`), the same files also offered as downloadable templates -
  a new manufacturer file just needs to follow the naming pattern to be
  picked up, no code change. A new **⟲ import standard catalog** button
  ("Standard-Katalog importieren", device catalog tab) re-runs that same
  import on demand later (e.g. to pick up newly-added default devices) -
  deliberately **not** automatic on every restart like an earlier version
  of this change did, since a device someone intentionally deleted
  shouldn't silently reappear. New `POST /api/actor-types/import-defaults`.
- **Project overview** — a status dashboard above the projects list,
  summarizing every project at once: total count with clickable
  per-status badges (click sets the search field to that status), open
  clarifications total (with an "aged" sub-count — see below — and each
  affected project listed, clicking jumps straight into its clarification
  list), and projects with no floors defined yet (each clicking straight
  into the building structure). New `GET /api/projects/dashboard`,
  computed with a handful of aggregate SQL queries rather than one call
  per project.
- **Aging in the clarification list**: an open entry unanswered for more
  than 7 days is now flagged - an "N days open" badge on the entry
  itself, the sub-tab button turns warn-colored, and a summary line
  appears above the list. The same 7-day threshold and aged count feed
  the new project overview above. `GET /projects/{id}/klaerungen` now
  includes `age_days`/`aged` per entry (computed in SQL via `julianday()`,
  not client-side, to avoid timezone-parsing ambiguity). New shared
  `AGED_KLAERUNG_DAYS` constant in `backend/utils.py`.

### Changed

- **Automatic circuit assignment** ("Alle automatisch zuordnen", circuit
  list) now prefers aligned channel pairs (A+B, C+D, E+F, G+H) for
  shutter/blind circuits: when 2+ unassigned circuits from the same room
  land on the same actuator, they get placed on a shared pair instead of
  whatever two channels happen to be next free — many shading actuators
  share a common input/reference per channel pair (e.g. for travel time
  measurement), so this now matches real wiring instead of just filling
  channels in document order. Every other channel type keeps its previous
  first-free-channel behavior unchanged. `get_circuits()`
  (`backend/ga_logic.py`) now also returns `room_id` per circuit
  (additive, used for the grouping).

### Fixed

- `GET /api/projects/{id}/actor-instances` crashed with a 500 if any
  actor instance's device type had no `channel_count` (i.e. any group
  other than actuator) - `dict.get(key, default)` only falls back when the
  key is *missing*, not when its value is `None`, and `actor_types`
  always has the column, just `NULL` for non-actuator groups. Only
  surfaced once non-actuator devices could plausibly end up referenced
  from this table (surfaced while testing automatic physical address
  assignment's system devices bucket).
- The project workspace's sub-tab row (now 10 tabs after this session's
  additions) could run out of room and misalign the active-tab underline
  against the row's bottom border. `.subnav` now wraps onto a second row
  on narrow-ish desktop widths instead of cramming everything onto one
  line - mobile keeps its existing horizontal-scroll behavior unchanged
  (that media query already overrides wrapping back off).

## [0.3.1] - 2026-08-16

### Fixed

- Listing/pruning existing Nextcloud backups (used by Setup → backup's
  list of existing backups and by retention pruning after each upload)
  sent a body-less `PROPFIND` request, which several real WebDAV servers -
  Nextcloud's SabreDAV included - reject or mishandle even though the
  WebDAV RFC technically allows omitting the body. This made a perfectly
  successful backup **upload** get reported as a failure, because the
  retention step run right after it would throw. Now sends a proper
  request body/`Content-Type`, and a listing/pruning failure is logged
  but no longer turns an already-successful upload into a reported
  failure.

### Added

- **Setup → backup**'s list of existing backups now includes Nextcloud
  backups too (previously local-only), each with its own download/restore
  buttons, and a Nextcloud listing error (e.g. wrong URL/credentials) is
  shown without hiding an otherwise-working local list. New
  `GET /api/system/backups/nextcloud/{filename}/download` and
  `POST /api/system/restore-nextcloud/{filename}`.

## [0.3.0] - 2026-08-16

### Added

- A new **Setup → backup** sub-tab: automatic and/or manual (a back-up-now
  button) backups of the whole database (not just one project - a
  complete, atomic snapshot via SQLite's own `.backup()` API) to a NAS/
  mounted folder and/or Nextcloud (WebDAV), independently toggleable,
  each with its own retention count (oldest backups beyond it are pruned
  automatically). Automatic backups run from a lightweight in-process
  background task (checks every 15 min whether the configured interval
  has elapsed) - no external scheduler/cron needed, though the manual
  button plus `POST /api/system/backup` work fine for a host-cron setup
  too, if preferred. Nextcloud upload uses plain WebDAV over the standard
  library (`urllib`) - no new dependency for that part. New
  `backend/backup.py`, 11 new `company_profile` columns, see
  `DEPLOYMENT.md` for the NAS bind-mount and Nextcloud app-password
  setup.
- **Restoring now happens in the app itself**, not just by hand: **Setup
  → backup** lists every backup in the NAS/mounted destination (with
  per-file download/restore), and a restore-from-upload option restores
  from any uploaded `.db` file (e.g. downloaded from Nextcloud). Either
  path validates the file actually looks like a KNXpilot database first
  (rejects anything else with a clear error, nothing touched), always
  takes a `knxpilot_backup_prerestore_<timestamp>.db` safety snapshot of
  the *current* database before overwriting it (so a wrong/accidental
  restore is itself still recoverable), then restarts the app the same
  way the self-update flow does. New `GET /api/system/backups`,
  `GET /api/system/backups/{filename}/download`,
  `POST /api/system/restore-local/{filename}`,
  `POST /api/system/restore-upload`. **New dependency:
  `python-multipart`** (required by FastAPI for file-upload form
  parsing) - this release needs `docker compose pull && docker compose
  up -d` (not just a self-update restart) to pick it up.
- A new **labels** project sub-tab (next to the circuit list, whose
  actuator/channel data it reuses): prints a label sheet for the
  distribution cabinet — one label per actuator instance (physical address
  + location) or per channel (physical address + channel letter, plus the
  assigned function/`RESERVE`), with a clickable position picker to resume
  a partially-used sheet instead of starting over, and a debug/test-print
  mode (border + position number) for checking alignment on plain paper
  before printing on real label stock. A **format** dropdown selects the
  label sheet — currently only Avery Zweckform L6037 (25.4 × 10 mm, 189
  labels/sheet), but the backend (`backend/labels.py`'s `LABEL_FORMATS`
  registry) and frontend (`frontend/js/labels.js`) are both structured so
  a second format is just a new registry entry + `<option>`, not a
  rewrite. New `GET /api/projects/{id}/export-labels.pdf`.

### Changed

- The default specification **preamble** text is now a much fuller
  writeup (contributed by the user): glossary (sensor, actuator, scene,
  ETS), basic operating philosophy, a per-trade function overview
  (lighting, shading, heating), priorities/protection/central functions,
  and a closing note footnote — replacing the previous shorter text
  (which itself replaced an even earlier one; both old versions are
  recognized and upgraded, see below). Installs whose preamble still
  exactly matches a previous default (i.e. never customized) get upgraded
  to the current one on next startup, same "never touch text someone
  actually wrote" backfill pattern used when this field was first
  introduced.
- The preamble field now supports light formatting - blank lines between
  paragraphs, `##`/`###` for a heading, a line that's only `**text**` for
  a smaller subheading, a line that's only `*text*` for an italic
  aside/footnote, `---` for a horizontal rule, `- ` for bullet points, and
  `**text**` inline for bold - rendered accordingly in the PDF (new
  `SubHeading`/`BodyBullet` paragraph styles in `backend/pdf_design.py`,
  plus `HRFlowable` for the rule). Previously it was rendered as flat
  paragraphs only.
- The specification PDF's optional **group addresses** section moved to
  always be the last section (after the clarification list), regardless
  of which other optional sections are also selected - it's usually the
  longest (every group address as its own table row), so it now sits
  after the more narrative sections instead of between the central/general
  functions and the circuit list.

### Fixed

- Frontend files (`frontend/`, served as static files by
  `backend/main.py`) were browser-cacheable with no revalidation hint, so
  after the self-update flow's `git pull` + restart, a browser could keep
  serving pre-update HTML/CSS/JS until the user happened to hard-refresh
  — several reported "the update isn't showing up" cases this session
  turned out to be exactly this. Now served with `Cache-Control:
  no-cache`: the browser still keeps a local copy, but must revalidate
  it (a cheap conditional GET via the ETag Starlette's `StaticFiles`
  already sends) before using it, so a normal reload always picks up
  changed files while unchanged ones still avoid a full re-download.

## [0.2.0] - 2026-08-16

### Added

- **Duplicate** for projects: a one-click, same-install copy (floors,
  rooms, points, specials, and metadata), available both from a project's
  own header and as a button in each row of the project list. Auto-names
  the copy "<Name> (Kopie)" (numbered if that name is already taken) and,
  from the project header, switches straight into the new copy. New
  `POST /api/projects/{id}/duplicate` endpoint - builds on the existing
  export/import-json logic (now factored into shared
  `_build_project_payload()`/`_insert_project_from_payload()` helpers) but
  skips the JSON round-trip and can never skip an item, since point types/
  categories always match themselves on the same install.
- Export/import (JSON) for Setup → categories, function types, and
  central/general function templates — the same pattern the device
  catalog already had, so the new delete-all buttons (below) are always
  recoverable without a database reset. The categories import only
  renames the 6 fixed categories (matched by main group number, never
  adds/removes); function types and central templates upsert by
  category+name(+scope), so re-importing the same file twice updates in
  place instead of duplicating. New `GET/POST .../export-json` and
  `.../import-json` endpoints for all three. The current defaults for all
  four importable sections (including the existing device catalog) are
  now committed as reference/starter files under `docs/templates/`.
- Delete-all bulk-clear buttons, each with a confirmation popup, for the
  device catalog, Setup → function types, and Setup → central/general
  function templates — for starting over with your own set instead of
  editing/deleting the seeded defaults one by one. The device catalog and
  function types only delete entries not already used by a project
  (in-use ones are skipped and reported, never force-deleted); central
  templates have no such restriction, since nothing else references them
  by id. New `DELETE /api/actor-types`, `DELETE /api/point-types`,
  `DELETE /api/central-templates` endpoints.
- More explanation in Setup (function types, central/general function
  templates, categories) and MANUAL.md's addressing-model section on how
  these relate to the generated GA tree, and why the main group =
  category / middle group = floor / sub group = point scheme is built into
  the tool rather than a configurable setting (KNX's own 0–31/0–7
  main/middle group limits make an alternative ordering, e.g.
  floor-as-main-group, a different addressing engine, not a toggle).
- A new **Setup → specification** sub-tab controls what the specification
  PDF export includes: the preamble text, plus six checkboxes — whether to
  show the preamble at all (new, lets you keep the text saved but hide the
  section), the floor/room directory and device list (on by default,
  matching prior behavior), and **group addresses**, **circuit list**, and
  **clarification list** sections (off by default, since they can make a
  larger project's specification very long) — `company_profile` gained
  six new columns for these toggles. The circuit list export's
  per-floor/actuator/channel rendering was factored out into a shared
  `build_abgangsliste_story()` so both the standalone export and this
  optional section use the same code.
- The default preamble text (seeded on fresh installs) now covers more
  ground - lighting, roller shutters/blinds treated separately, heating,
  and central/weather functions - condensed from common real-world
  specification templates without their page-length detail. Installs
  that already had a `company_profile` row before this default text
  existed (so the fresh-install seed never touched them) get it
  backfilled on next startup too, but only if the field is still empty -
  never overwrites text someone has actually written.
- Specification PDF, made more professional: a **preamble** section
  (general operating-convention text, editable/clearable in the new Setup
  → specification tab, seeded with sensible default wording on fresh
  installs), a **floor and room directory** table, and a **tested**
  checkbox next to every individual function (room-level and
  central/general) for hand-ticking during on-site commissioning —
  paper-style only, no tracked state, since KNXpilot doesn't know which
  physical button/operating element drives which function (that's ETS
  programming).
- A new **handover checklist** PDF export (specification sub-tab, next to
  the existing PDF button): a mostly generic KNX handover checklist
  (visual inspection/function test/customer briefing/system handover,
  tri-state yes/no/not needed checkboxes, remarks column, signature lines
  for installer and customer/operator) - only the project name is filled
  in automatically.
- An open-project picker modal (nav dropdown → **open project**): search
  across all projects and open one directly, from any tab, without needing
  to close whatever project is currently open first — picking a project
  always switches straight to it.
- A small 📁 project-name badge in the header, visible from every tab
  once a project is open, with its own **×** to close directly (no need
  to go back to the projects tab first). Updates live on open, rename,
  and delete.
- A new **help** tab renders the full usage manual (`MANUAL.md`) in-app,
  via a new `GET /api/system/manual` endpoint and `frontend/js/hilfe.js`.
  The Markdown-to-HTML renderer that used to be private to the Update
  tab's changelog view moved into `frontend/js/ui.js` as a shared,
  general-purpose `renderMarkdown()` (now also supports arbitrary
  heading depth and fenced code blocks, needed for the manual's KNX
  addressing table and CSV format block).
- README.md screenshots (`docs/screenshots/`): overview, functions, group
  addresses, and circuit list.
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

- The company and specification tabs' save buttons now both simply read
  "Speichern" (save) instead of "Firmenprofil speichern" (save company
  profile) — clearer given both tabs save fields on the same underlying
  profile record.
- The app's accent color (buttons, headings, active-tab underline,
  links) changed from blue to green, and the PDF exports' banner/table-
  header/section-heading color changed from dark navy to dark green —
  no more blue left anywhere in the design system.
- Export/import/delete-all for the device catalog and Setup →
  categories/function types/central templates moved from a row of wide
  text buttons into a compact icon-button group in each card's top-right
  corner (hover for a tooltip). Import now opens a small popup to choose
  the file instead of an always-visible file picker next to the button —
  new shared `openImportModal()` helper in `frontend/js/ui.js`.
- The projects list's restore-from-backup button and the opened project's
  JSON backup button moved the same way, into icon buttons (⭱ in the list
  header, ⭳ next to the new ⧉ duplicate icon in the project header)
  instead of a wide text button/inline file input.
- README.md is now a short landing page (pitch, screenshots, key
  features, quickstart, links) instead of the full manual — all detailed
  per-tab usage instructions, the GA addressing model, and the CSV
  format moved to the new `MANUAL.md` (also viewable in-app via the help
  tab).
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
in-app changelog, editable structure/functions/setup, and the group
addresses split) — see below for the full detail.

### Added

- Toast notifications and a custom confirm modal (`frontend/js/ui.js`),
  replacing every native `alert()`/`confirm()` call across the frontend
  (24 + 7 call sites).
- An open-circuit-count badge on the circuit list sub-tab button (e.g.
  "Abgangsliste (3)"), mirroring the existing clarification list badge
  pattern.
- A new **overview** sub-tab (`frontend/js/uebersicht.js`), now the
  default landing sub-tab when opening a project — 5 clickable status
  cards (one per other sub-tab) summarizing floors/rooms/points, circuit
  assignment progress, planned device count, and open clarifications at a
  glance, each jumping straight to the relevant sub-tab on click.
- The group addresses preview is now a collapsible tree (native
  `<details>`/`<summary>`, `.ga-tree` in `frontend/css/style.css`) instead
  of one long block of monospace text — main groups open by default,
  middle groups (the actual source of clutter on larger projects) start
  collapsed, each showing an address count. Expand-all/collapse-all
  buttons toggle everything at once.
- A responsive pass for phones/small tablets (`@media (max-width: 700px)`
  in `frontend/css/style.css`): the main nav and project sub-nav scroll
  horizontally instead of overflowing the page (the sub-nav has 6 buttons
  now after the overview addition), list rows reflow instead of clipping,
  and touch targets are slightly larger. Purely additive — desktop layout
  is unaffected.
- Bulk room add: each floor's room quick-add now has a "Mehrere..."
  (several) toggle revealing a textarea to paste multiple room names at
  once (one per line), instead of adding them one-by-one. Frontend-only,
  reuses the existing single-room endpoint in a loop; the original
  single-room input is unchanged.
- Floors, rooms, and room functions can now be renamed/edited after
  creation, not just deleted: floor and room names via an edit button
  opening a rename dialog (`frontend/js/ui.js`'s `openRenameModal`), and a
  room's assigned functions (point type/label/motion detector flag) via a
  ✎ edit link on each pill that repurposes the existing quick-add form
  into an edit form (same pattern already used for actuator types). New
  backend endpoints: `PUT /api/floors/{id}`, `PUT /api/rooms/{id}`,
  `PUT /api/room-points/{id}`.
- Setup's function types (formerly "point types") and central templates
  can now be edited in place (the backend already supported this; only
  the frontend UI was missing) — same edit-button pattern as the device
  catalog's actuator types.
- Categories can now be renamed via a new edit button
  (`PUT /api/categories/{id}`) — reordering/adding/removing stays
  unsupported, since order directly maps to fixed KNX main group numbers.

### Changed

- Split the GA tree preview and CSV export out of the functions sub-tab
  into its own new group addresses sub-tab, so that assigning functions to
  rooms and viewing/exporting the resulting group addresses are no longer
  stacked on the same page. Frontend-only — the moved code (`previewGA`,
  `expandAllGaTree`, `downloadCSV`) now lives in a new
  `frontend/js/gruppenadressen.js`, following the one-file-per-sub-tab
  convention. The tree now loads automatically when opening the tab (the
  preview button still works, as a manual refresh), and the overview
  gained a matching group addresses stat card showing the total address
  count.
- Renamed Setup's "Punkttypen" (point types) sub-tab and every
  user-facing label to "Funktionstypen" (function types), for terminology
  consistency with the functions tab where those types get assigned to
  rooms (the underlying `point_types` table, `/api/point-types` endpoint,
  and JS variable names are unchanged — only displayed text moved).
- Floor and room rename now uses an edit button in the same button row as
  delete, instead of the ✎ icon-link introduced in the previous change —
  matching the convention used everywhere else a name can be changed
  (actuator types, function types, central templates, categories).
  Room-function pills keep their ✎/× icon-link pair, which predates this
  rework and fits a compact pill format better than a text button.
- Split the group addresses sub-tab into the **building structure**
  (floors/rooms only) and **functions** (assigning KNX functions to rooms,
  special addresses, GA preview/export) — these were previously combined
  on one page. `frontend/js/funktionen.js` is a new file for the latter,
  following this project's one-file-per-sub-tab convention.
- Renamed the "Setup (Kategorien & Vorlagen)" tab to plain "Setup".
- Reworked the projects and Setup tabs from "everything stacked on one
  page" into focused views: the Setup tab now has a
  company/categories/point types/central templates sub-nav (same pattern
  as the project workspace) instead of 4 always-visible cards; opening a
  project now hides the project list instead of leaving it visible above
  the workspace; and "create project" is now a modal (auto-focused, opens
  the new project directly on success) instead of an always-visible
  inline form. `frontend/js/ui.js`'s `showConfirm` now shares its
  overlay/Escape/backdrop-click plumbing with the new modal via an
  `openModal()` helper.
- The projects top-nav item is now a small dropdown (▾) with "new
  project" and "open project", usable from any tab.
- Renamed the "Geräte" (devices) tab to "Geräte Katalog" (device catalog)
  for clarity (and the validation messages that reference it).
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
  corresponding persistence/deployment and code structure sections out of
  `README.md` in favor of pointers to the new files.
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
- List rows (`ul.list li`, used by function types, central/general
  function templates, categories, actuator types, etc.) let their
  edit/delete buttons wrap onto a second line whenever the row's content
  wrapped to multiple lines (e.g. "LED (Tunable White)", "Klima"), since
  content and buttons shared equal flex-shrink. Fixed by giving the
  content column `min-width: 0` (free to shrink/wrap) and the button
  column `flex-shrink: 0` (stays put at its natural size).
- `DEPLOYMENT.md`'s Proxmox instructions named `docker-compose-plugin`/
  `docker-ce` as an apt-installable fallback without noting that those are
  Docker's own package names, not Ubuntu's — `apt install` silently fails
  the whole transaction (including `docker.io`) when one package name
  doesn't resolve. Fixed to use Ubuntu's own `docker-compose-v2` package
  (no third-party repo needed), with Docker's official install script kept
  as a documented fallback for distros where that package isn't available.
