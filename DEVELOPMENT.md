# Development

## Branches

- **`dev`** — active work happens here. Commit and push freely.
- **`main`** — what deployments actually run: the Docker image
  ([`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml))
  and every server's self-update (`git pull` on `main`, see
  [`DEPLOYMENT.md`](./DEPLOYMENT.md)) both track it. `main` only moves
  forward at a release, via a fast-forward merge from `dev`
  (`git checkout main && git merge --ff-only dev`) plus a `vX.Y.Z` tag —
  see `CHANGELOG.md` for the version history.
- **Release routine:** on `dev`, rename `## [Unreleased]` in `CHANGELOG.md`
  to `## [X.Y.Z] - YYYY-MM-DD` (optionally with a short summary paragraph
  directly under that heading), commit and push `dev`, and **wait until the
  Tests workflow has passed for that commit** (`gh run watch`, or the
  Actions tab); then
  `git checkout main && git merge --ff-only dev && git tag -a vX.Y.Z -m vX.Y.Z`
  and `git push origin main vX.Y.Z`. `main` is protected: no force pushes,
  no deletion, and a push is only accepted if its commit passed the
  `pytest` check - since `main` is fast-forwarded to the already-tested
  `dev` commit, that just means "don't release before the tests are
  green". No pull request is required. Pushing the tag does the rest
  automatically: [`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml)
  builds and publishes the Docker image, and
  [`.github/workflows/release.yml`](./.github/workflows/release.yml)
  creates the GitHub Release with that version's CHANGELOG section as its
  text (it fails loudly if the section is missing, and skips if a release
  already exists).
- **Dependency updates:** Dependabot ([`.github/dependabot.yml`](./.github/dependabot.yml))
  checks weekly for newer GitHub Actions, Python packages
  (`requirements*.txt`) and the Docker base image, and opens grouped pull
  requests against `dev`; the Tests workflow runs on each. A new Python
  minor version in the base image also needs the pinned packages to support
  it — build the image locally before merging that one.
- To switch your local checkout between them: `git checkout dev` /
  `git checkout main` (or `git switch dev` / `git switch main`). `main`
  only has what's actually been released, so it'll usually look "behind"
  `dev` day-to-day — that's expected, not a problem to fix.
- The running app shows which version it's on in the header (via
  `git describe`, e.g. `v0.1.0` on a release commit, `v0.1.0-3-gabc1234`
  for commits since the last release) — see `/api/system/version` in
  `backend/routers/system.py`. Only populated inside a real git checkout
  (i.e. the deployed container), not local dev.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. No separate frontend server, no build step —
`backend/main.py` mounts `frontend/` directly as static files, and
`--reload` picks up backend changes; for frontend changes, just reload the
browser tab.

There's no local `.db` file checked into the repo — `backend/db.py` creates
`backend/data/knx_ga.db` on first run and seeds it with default categories,
point types, central-function templates, and an actor-type catalog (see
`seed_defaults()` / `seed_default_actor_types()` in `backend/db.py`).

## Tests

```bash
pip install -r requirements-dev.txt   # pytest + httpx2, on top of requirements.txt
pytest
```

The suite under `tests/` covers the backend: schema setup on a fresh and
on an old database, the ETS group-address CSV (format rules plus a golden
file, `tests/fixtures/musterhaus_ga.csv`), every PDF/CSV/JSON export built
from a demo project whose names contain `&`, `<`, quotes, an en dash and
`€`, Zeiterfassung rounding/editing, manual downloads against a local HTTP
server, and the delete-impact counts. Each test runs against its own
throwaway database (`tests/conftest.py` points `KNXPILOT_DB_PATH` /
`backend.db.DB_PATH` at a temp file), so the real `backend/data/knx_ga.db`
is never touched. CI runs it on every push to `dev`/`main`
([`.github/workflows/tests.yml`](./.github/workflows/tests.yml)).

If a change to the addressing logic changes the GA export *on purpose*,
regenerate the golden file with `KNXPILOT_UPDATE_GOLDEN=1 pytest
tests/test_ga_export.py` and review the diff before committing it.

The frontend has no automated tests — verify UI changes by clicking
through the affected tab(s) in the browser (see [`MANUAL.md`](./MANUAL.md)
for what each tab does).

## Project structure

```
backend/
  main.py           — creates the app, wires up routers, mounts frontend/ as static files
  db.py             — sqlite connection, schema, migrations, seed data
  models.py         — Pydantic request-body schemas
  ga_logic.py       — group-address tree generation, circuits, per-room/central function listings (used by Pflichtenheft and the checklists)
  pdf_design.py     — shared PDF look (banner, table style, page numbers, letterhead); build_pdf_bytes()/build_pdf_bytes_two_pass() are the raw-bytes builders every export (and email.py's send action) go through
  templating.py     — Jinja2 setup for the htmx tabs (templates/, autoescaped)
  templates/<tab>/  — server-rendered HTML fragments of the htmx tabs (so far: klaerungsliste/, time_tracking/, setup/, device_catalog/, manuals/, overview/, specification/, documentation/, project_files/)
  project_transfer.py — per-project JSON backup/restore + duplicate (what's included, name/position-based references)
  pa_assign.py      — physical-address auto-assign (bucket convention, per KNX line) + line coupler/power supply detection
  email_sender.py   — SMTP mechanics (stdlib smtplib) behind routers/email.py's send-by-mail action
  utils.py          — small dependency-free helpers
  routers/
    setup.py          — Setup tab (htmx, /hx/setup/...): settings pages on the company profile (SETTINGS_SECTIONS) and the categories/function types/central templates editors, plus their JSON APIs
    device_catalog.py  — device catalog tab (htmx: /hx/device-catalog...): catalog + per-device manual URL, JSON import/export with preview, ACTOR_TYPES API
    projects.py        — projects, floors/rooms/points (incl. tree moves with GA-impact dry run), backup/restore (Projekte tab: Gebäudestruktur sub-tab + project CRUD)
    linien.py          — optional KNX lines (Bereich.Linie) + floor/room/actuator line assignment, per-line device counts/warnings (Gebäudestruktur sub-tab)
    abgangsliste.py    — actor instances, circuit assignment, CSV/PDF export (Abgangsliste sub-tab)
    geraeteplanung.py  — per-room device planning, bill of materials, PDF export (Geräteplanung sub-tab)
    specification.py   — early-stage spec PDF export, htmx "Inhalt" tab (Pflichtenheft sub-tab); also home to function_checklist_table(), shared with checkliste.py
    checkliste.py      — digital on-site checklists: checklist_status upsert, Funktionscheckliste + Übergabe-Checkliste JSON/PDF (their sub-tabs)
    documentation.py   — end-of-project assembly PDF, combining Pflichtenheft content + both checklists' results + a Handbücher checklist + optional as-built sections, htmx "Inhalt" tab; the chapter list (DOCUMENTATION_CHAPTERS) also drives it (Dokumentation sub-tab)
    email.py           — "Per E-Mail senden" endpoints, reusing each export's build_*_pdf_bytes() function (Setup → E-Mail + every export tab)
    klaerungsliste.py  — questions/tasks/notes per project + "Offene Punkte" PDF export (Klärungsliste sub-tab)
    overview.py        — overview tab (htmx, "Übersicht"): one stat card per sub-tab, aggregated from each sub-tab's own data
    project_files.py   — a handful of reference files per project, stored as a BLOB, htmx list fragment nested into the overview tab (Übersicht sub-tab)
    manuals.py         — project manuals tab ("Handbücher", htmx): fetches a device's catalog-curated manual_url into the project's own store
    time_tracking.py   — internal per-project time tracking ("Zeiterfassung" tab, htmx): header timer JSON API + /hx/ tab fragments + its own timesheet PDF; never part of any project export
    system.py          — self-update via git, changelog + manual + version endpoints (Update/Hilfe tabs)
frontend/
  index.html        — page shell: <head>, nav/tab markup, <script src> tags in load order
  vendor/           — vendored third-party files, committed as-is (no npm): htmx-<version>.min.js + its license
  css/style.css      — the entire stylesheet (single file, theming via CSS custom properties)
  js/
    api.js            — shared api() fetch wrapper, global state vars, theme toggle, tab-switch wiring
    ui.js              — toasts, modals, shared Markdown renderer (used by Update + Hilfe)
    send_email.js      — shared "Per E-Mail senden" modal, called from Pflichtenheft/Funktionscheckliste/Übergabe-Checkliste/Dokumentation
    setup.js           — loads the htmx Setup sub-tabs, header branding, logo auto-crop, backup restore, JSON import (file picker), categories/function types cache for the functions tab
    device_catalog.js  — loads the htmx device catalog sub-tabs, ACTOR_TYPES cache for other tabs' pickers, JSON import dialogs
    projekte.js        — project CRUD/meta, Geschoss/Raum/Verteiler tree with drag & drop (Gebäudestruktur sub-tab)
    linien.js          — optional KNX lines card + the line <select>s used by projekte.js/abgangsliste.js (Gebäudestruktur sub-tab)
    funktionen.js      — assigning functions to rooms, Sonderadressen (Funktionen sub-tab)
    gruppenadressen.js — GA tree preview + CSV export (Gruppenadressen sub-tab)
    overview.js        — loads the htmx overview tab, goToSubtab() for the stat cards' onclick (Übersicht sub-tab)
    manuals.js         — loads the htmx project manuals tab
    time_tracking.js   — header start/stop timer (live clock), loads the htmx time tracking tab, timesheet PDF download
    abgangsliste.js    — actor instances + circuit assignment
    geraeteplanung.js  — per-room device planning
    specification.js   — loads the htmx Pflichtenheft tab, Vorschau and PDF download
    funktionscheckliste.js — digital on-site function testing checklist
    uebergabe_checkliste.js — digital handover checklist
    klaerungsliste.js  — questions/tasks/notes, copy/PDF/email of the open points
    documentation.js   — loads the htmx Dokumentation tab, Vorschau and PDF download
    update.js          — self-update tab + changelog viewer + version badge
    hilfe.js           — in-app manual (renders MANUAL.md)
    init.js            — page-load bootstrap, must load last (calls functions from the files above)
tests/
  conftest.py       — throwaway database per test, demo-project seed helper
  test_*.py         — backend tests (see "Tests" above)
  fixtures/         — golden files, e.g. musterhaus_ga.csv (the demo project's ETS export)
tools/
  knxproj_probe.py  — read-only inspector for real ETS .knxproj exports (groundwork for the ETS import, see docs/FINDINGS-knxproj.md)
docs/
  FINDINGS-knxproj.md — ETS project-file format: hypotheses to verify against real exports, proposed mapping, open questions
  screenshots/      — README.md's screenshots
  templates/        — default-data JSON exports (Kategorien, Funktionstypen,
                      Zentral-/Allgemeinfunktions-Vorlagen, Geräte Katalog),
                      importable via each Setup tab's "Importieren (JSON)"
                      button - re-download the current defaults here after
                      changing them, so an "Alle löschen" is always
                      recoverable without a database reset
```

The backend router split and the frontend JS-file split both follow the
same principle: **one file per UI tab/sub-tab**. If you're adding a feature
to, say, the Abgangsliste sub-tab, the code almost always belongs in
`backend/routers/abgangsliste.py` and `frontend/js/abgangsliste.js` — you
rarely need to touch anything else.

## Conventions to follow

- **Backend imports are relative** (`from .db import get_db`, `from ..db
  import get_db` in routers). Keep it that way — no absolute `backend.db`
  imports.
- **No frontend build step, on purpose** — see [`CLAUDE.md`](./CLAUDE.md)
  and [`DEPLOYMENT.md`](./DEPLOYMENT.md) for why. Frontend `<script>` tags
  in `frontend/index.html` must stay classic scripts (no `type="module"`):
  functions are called from inline `onclick="..."` attributes in the HTML
  and from other JS files, which only works if every script shares one
  global scope. `frontend/js/api.js` must load first (it defines the shared
  `api()` wrapper and global state), `frontend/js/init.js` must load last
  (it calls the `load*()` functions defined in every other file).
- **Naming pattern in the frontend JS**: `load*()` fetches from the API and
  populates a global cache array/object; `render*()` paints that cache into
  the DOM; other verbs (`create*`, `save*`, `delete*`, `add*`) perform an
  action and then usually call the relevant `load*`/`render*` again.
  Rendering is template-literal strings assigned to `.innerHTML`, not
  `document.createElement` — stay consistent with that pattern for list/
  table/tree rendering.
- **All API calls go through the shared `api()` wrapper** in `api.js`
  (`api('/projects')`, etc. — it prefixes `/api`, throws on non-2xx with the
  server's `detail` message, and auto-parses JSON). File downloads
  (CSV/PDF/JSON exports) bypass it and just set
  `window.location.href = '/api/...'`.
- **htmx tabs** (so far the clarification list and time tracking; the
  other tabs are classic JS and get converted one at a time, in the order
  under "htmx migration" below): the tab's HTML is rendered by the server from Jinja
  templates in `backend/templates/<tab>/`, returned by `/hx/...` endpoints
  in the tab's router, and `hx-*` attributes in that HTML do the requests
  and swap the answer in - no client-side cache, no `render*()`. The tab's
  JS file only loads the tab (`htmx.ajax(...)` into a root `<div>`) and
  holds the few things that must stay in the browser (clipboard, downloads,
  badge). Conventions: actions that change the list re-render only the part
  that changed (so a half-typed form survives); `hx-confirm` shows the
  app's own dialog and failed requests show a toast with the server's
  `detail` (both wired up once in `ui.js`); the server tells the page about
  side effects via an `HX-Trigger` response header (e.g. new badge
  counts). Jinja autoescapes all user text. htmx is vendored in
  `frontend/vendor/` (no CDN, works offline on a LAN, and the git-pull
  update keeps working); to update it, replace the file with the new
  release's `dist/htmx.min.js` from npm and change the version in its
  name and the `<script>` tag. JSON endpoints stay where other code needs
  them (exports, badge, tests). Shared helpers for all htmx tabs: every
  htmx request sends the browser's time zone (`X-Timezone`, read with
  `templating.client_zone(request)` - render times in the user's zone,
  the container runs on UTC); dialogs are fragments swapped into
  `#hx-modal` (root element `.modal-overlay`, closed by Escape, a
  backdrop click, `closeHxModal()` or the server's `HX-Trigger:
  hx-modal-close`); a list can refresh itself after any mutation via
  `hx-trigger="<event> from:body"` plus an `HX-Trigger: <event>` header,
  so mutation endpoints don't need to know the current filters; a response
  can show a toast via `HX-Trigger: {"show-toast": {"message", "level"}}`.
- **htmx migration** (agreed with the user 2026-09-26): one tab per change,
  each renamed to English in the same change, with pytest coverage for its
  `/hx/` endpoints and a browser pass; confirm each next tab with the
  user. Order: ~~clarification list~~, ~~time tracking~~, ~~Setup~~,
  ~~device catalog~~, ~~project manuals~~, ~~overview~~, ~~specification~~,
  ~~documentation~~, function + handover checklists, functions + group
  addresses, device planning + distribution board planning + labels,
  circuit list, building structure (drag & drop stays JS).
- **User-facing strings are German**; everything else is English: code
  identifiers, comments, file/directory names, database tables/columns,
  API paths, CSS classes, template names, JSON keys, this documentation
  (standing order since 2026-09-26). Use the glossary below for the
  domain terms. Existing German names are renamed tab by tab (together
  with each tab's move to htmx); don't add new ones.

  | UI (German) | English name in code |
  |---|---|
  | Projekt, Übersicht | project, overview |
  | Gebäudestruktur, Geschoss, Raum | building structure, floor, room |
  | Funktionen (Punkte je Raum) | functions / room points |
  | Sonder-/Zusatzadressen | special addresses |
  | Gruppenadressen | group addresses |
  | KNX-Linien, Linienkoppler | KNX lines, line coupler |
  | Abgangsliste, Abgang, Aktor, Kanal | circuit list, circuit, actuator, channel |
  | Labels (Etiketten) | labels |
  | Geräteplanung, Stückliste | device planning, bill of materials |
  | Verteilerplanung, Verteiler | distribution board planning, distribution board |
  | Pflichtenheft | specification |
  | Funktionscheckliste | function checklist |
  | Übergabe-Checkliste | handover checklist |
  | Klärungsliste, Klärung | clarification list, clarification |
  | Handbücher | manuals |
  | Dokumentation | documentation |
  | Geräte Katalog | device catalog |
  | Zeiterfassung | time tracking |
  | Setup, Hilfe, Update | setup, help, update |
- **Tests** — run `pytest` before committing; add a test for new backend
  logic (especially anything that writes data, migrates the schema or
  builds an export). UI changes still need a manual pass through the
  tab(s) they touch (create/edit/delete, and any PDF/CSV export).

## Adding a new feature

1. New endpoint → add it to the relevant `backend/routers/*.py` (or create
   a new router module + `app.include_router(...)` in `backend/main.py` if
   it doesn't fit an existing tab).
2. New request/response shape → add a Pydantic model to `backend/models.py`.
3. New UI → add markup to the relevant section of `frontend/index.html` and
   JS to the matching `frontend/js/*.js` file, following the `load*/render*`
   pattern above - or, in an htmx tab, edit its template in
   `backend/templates/<tab>/` and add an `/hx/...` endpoint (see "htmx
   tabs" above; test it with pytest like any other endpoint).
4. Manually verify by running the app locally and clicking through the
   affected tab.
