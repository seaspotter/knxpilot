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

No automated tests exist yet. Verify changes manually by clicking through
the affected tab(s) in the browser — see the "Die vier Tabs" section in
[`README.md`](./README.md) for what each tab does.

## Project structure

```
backend/
  main.py           — creates the app, wires up routers, mounts frontend/ as static files
  db.py             — sqlite connection, schema, migrations, seed data
  models.py         — Pydantic request-body schemas
  ga_logic.py       — group-address tree generation, circuits, Pflichtenheft helpers
  pdf_design.py     — shared PDF look (banner, table style, page numbers, letterhead)
  utils.py          — small dependency-free helpers
  routers/
    setup.py          — company profile, categories, point types, central templates (Setup tab)
    geraete.py         — global device catalog (Geräte Katalog tab)
    projects.py        — projects, floors/rooms/points, backup/restore (Projekte tab: Gebäudestruktur sub-tab + project CRUD)
    abgangsliste.py    — actor instances, circuit assignment, CSV/PDF export (Abgangsliste sub-tab)
    geraeteplanung.py  — per-room device planning, bill of materials, PDF export (Geräteplanung sub-tab)
    pflichtenheft.py   — Pflichtenheft PDF export (Pflichtenheft sub-tab)
    klaerungsliste.py  — questions/tasks/notes per project (Klärungsliste sub-tab)
    project_files.py   — a handful of reference files per project, stored as a BLOB (Übersicht sub-tab)
    system.py          — self-update via git, changelog + manual + version endpoints (Update/Hilfe tabs)
frontend/
  index.html        — page shell: <head>, nav/tab markup, <script src> tags in load order
  css/style.css      — the entire stylesheet (single file, theming via CSS custom properties)
  js/
    api.js            — shared api() fetch wrapper, global state vars, theme toggle, tab-switch wiring
    ui.js              — toasts, modals, shared Markdown renderer (used by Update + Hilfe)
    setup.js           — company profile + categories + point types + central templates
    geraete.js         — actor types catalog
    projekte.js        — project CRUD/meta, floors/rooms (Gebäudestruktur sub-tab)
    funktionen.js      — assigning functions to rooms, Sonderadressen (Funktionen sub-tab)
    gruppenadressen.js — GA tree preview + CSV export (Gruppenadressen sub-tab)
    uebersicht.js      — project status dashboard + project files (Übersicht sub-tab)
    abgangsliste.js    — actor instances + circuit assignment
    geraeteplanung.js  — per-room device planning
    pflichtenheft.js   — Pflichtenheft preview
    klaerungsliste.js  — questions/tasks/notes
    update.js          — self-update tab + changelog viewer + version badge
    hilfe.js           — in-app manual (renders MANUAL.md)
    init.js            — page-load bootstrap, must load last (calls functions from the files above)
docs/
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
- **User-facing strings are German**; code identifiers, comments, and this
  documentation are English.
- **No automated tests** — when adding a feature, do a manual pass through
  the tab(s) it touches (create/edit/delete, and any PDF/CSV export) before
  considering it done.

## Adding a new feature

1. New endpoint → add it to the relevant `backend/routers/*.py` (or create
   a new router module + `app.include_router(...)` in `backend/main.py` if
   it doesn't fit an existing tab).
2. New request/response shape → add a Pydantic model to `backend/models.py`.
3. New UI → add markup to the relevant section of `frontend/index.html` and
   JS to the matching `frontend/js/*.js` file, following the `load*/render*`
   pattern above.
4. Manually verify by running the app locally and clicking through the
   affected tab.
