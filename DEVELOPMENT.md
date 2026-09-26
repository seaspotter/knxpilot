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
  directly under that heading) and commit; then
  `git checkout main && git merge --ff-only dev && git tag -a vX.Y.Z -m vX.Y.Z`
  and `git push origin main vX.Y.Z`. Pushing the tag does the rest
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
  email_sender.py   — SMTP mechanics (stdlib smtplib) behind routers/email.py's send-by-mail action
  utils.py          — small dependency-free helpers
  routers/
    setup.py          — company profile (incl. SMTP credentials), categories, point types, central templates (Setup tab)
    geraete.py         — global device catalog + curated manual_url per device (Geräte Katalog tab: Katalog + Handbücher sub-tabs)
    projects.py        — projects, floors/rooms/points, backup/restore (Projekte tab: Gebäudestruktur sub-tab + project CRUD)
    abgangsliste.py    — actor instances, circuit assignment, CSV/PDF export (Abgangsliste sub-tab)
    geraeteplanung.py  — per-room device planning, bill of materials, PDF export (Geräteplanung sub-tab)
    pflichtenheft.py   — early-stage spec PDF export (Pflichtenheft sub-tab); also home to function_checklist_table(), shared with checkliste.py
    checkliste.py      — digital on-site checklists: checklist_status upsert, Funktionscheckliste + Übergabe-Checkliste JSON/PDF (their sub-tabs)
    dokumentation.py   — end-of-project assembly PDF, combining Pflichtenheft content + both checklists' results + a Handbücher checklist + optional as-built sections (Dokumentation sub-tab)
    email.py           — "Per E-Mail senden" endpoints, reusing each export's build_*_pdf_bytes() function (Setup → E-Mail + every export tab)
    klaerungsliste.py  — questions/tasks/notes per project + "Offene Punkte" PDF export (Klärungsliste sub-tab)
    project_files.py   — a handful of reference files per project, stored as a BLOB (Übersicht sub-tab)
    manuals.py         — fetches a device's catalog-curated manual_url into the project's own Handbücher store (Handbücher sub-tab)
    zeiterfassung.py   — internal per-project time tracking: header start/stop timer + global time_entries list (Zeiterfassung tab) + its own Stundennachweis PDF; never part of any project export
    system.py          — self-update via git, changelog + manual + version endpoints (Update/Hilfe tabs)
frontend/
  index.html        — page shell: <head>, nav/tab markup, <script src> tags in load order
  css/style.css      — the entire stylesheet (single file, theming via CSS custom properties)
  js/
    api.js            — shared api() fetch wrapper, global state vars, theme toggle, tab-switch wiring
    ui.js              — toasts, modals, shared Markdown renderer (used by Update + Hilfe)
    send_email.js      — shared "Per E-Mail senden" modal, called from Pflichtenheft/Funktionscheckliste/Übergabe-Checkliste/Dokumentation
    setup.js           — company profile (incl. SMTP settings) + categories + point types + central templates
    geraete.js         — actor types catalog + Handbücher sub-tab (per-device manual URL)
    projekte.js        — project CRUD/meta, floors/rooms (Gebäudestruktur sub-tab)
    funktionen.js      — assigning functions to rooms, Sonderadressen (Funktionen sub-tab)
    gruppenadressen.js — GA tree preview + CSV export (Gruppenadressen sub-tab)
    uebersicht.js      — project status dashboard + project files (Übersicht sub-tab)
    manuals.js         — device manuals: view/fetch/delete (Handbücher sub-tab)
    zeiterfassung.js   — header start/stop timer, Zeiterfassung tab (edit entries, totals, Stundennachweis PDF download)
    abgangsliste.js    — actor instances + circuit assignment
    geraeteplanung.js  — per-room device planning
    pflichtenheft.js   — Pflichtenheft PDF download button (static content)
    funktionscheckliste.js — digital on-site function testing checklist
    uebergabe_checkliste.js — digital handover checklist
    klaerungsliste.js  — questions/tasks/notes, copy/PDF/email of the open points
    dokumentation.js   — Dokumentation PDF download button (static content)
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
- **User-facing strings are German**; code identifiers, comments, and this
  documentation are English.
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
   pattern above.
4. Manually verify by running the app locally and clicking through the
   affected tab.
