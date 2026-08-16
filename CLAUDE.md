# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What this is

KNXpilot — a KNX electrical-installation planning tool for electricians/
system integrators (group addresses, wiring lists, device planning,
customer documentation). German UI, single-tenant, no auth, meant to run on
a small internal server (see [`README.md`](./README.md) for the product
description and [`DEPLOYMENT.md`](./DEPLOYMENT.md) for how it's deployed).

## Architecture at a glance

- **Backend**: FastAPI under `backend/`, one router per UI tab/sub-tab
  (`backend/routers/*.py`), sqlite via a single connection helper in
  `backend/db.py`, Pydantic schemas in `backend/models.py`.
- **Frontend**: plain HTML/CSS/JS under `frontend/`, **no build step, no
  framework**. `backend/main.py` mounts `frontend/` directly as static
  files. One JS file per tab/sub-tab under `frontend/js/`, loaded via
  classic (non-module) `<script src>` tags in `frontend/index.html`.
- **No automated tests** exist. Changes are verified manually by running the
  app and clicking through the affected tab(s).

Full structure and conventions: [`DEVELOPMENT.md`](./DEVELOPMENT.md).

## A constraint you must respect: no frontend build step

`docker-compose.yml` bind-mounts the **entire repository** into the
container, and the in-app "Update" tab does a `git pull` inside the running
container followed by a process restart — **no image rebuild** for a normal
code update (see `backend/routers/system.py` and
[`DEPLOYMENT.md`](./DEPLOYMENT.md)).

This only works because the frontend is plain HTML/CSS/JS served as-is.
**Do not introduce a bundler/build step (Vite, Webpack, a JSX/TS
compile step, npm dependencies for the frontend, etc.) without first
raising it with the user** — it would break the self-update flow unless
built artifacts are committed to git or the deploy story is reworked. If a
task seems to call for a frontend framework, treat that as a decision for
the user to make explicitly, not something to introduce as a side effect of
"cleaning up" the frontend.

## Conventions

- Backend uses **relative imports** (`from .db import ...`, `from ..db
  import ...` in routers) — keep it that way.
- Frontend `<script>` tags must stay classic scripts, not `type="module"`:
  functions are invoked via inline `onclick="..."` in the HTML and are
  shared across files through the global scope. `frontend/js/api.js` loads
  first (defines the shared `api()` fetch wrapper and global state arrays
  like `PROJECTS_LIST`, `CURRENT_PROJECT`), `frontend/js/init.js` loads last
  (bootstraps the page by calling `load*()` in every other file).
- Frontend naming: `load*()` fetches + caches, `render*()` paints the cache
  into the DOM via template-literal `.innerHTML`, other verbs (`create*`,
  `save*`, `delete*`, `add*`) perform an action then re-load/re-render.
- All API calls go through the shared `api()` wrapper (prefixes `/api`,
  throws on non-2xx using the server's `detail` message). File
  downloads (CSV/PDF/JSON exports) use `window.location.href = '/api/...'`
  instead.
- User-facing strings are German; code, comments, and docs are English.
- One router file and one frontend JS file per UI tab/sub-tab — when adding
  a feature to an existing tab, that's almost always the only two files you
  need to touch (see the table in [`DEVELOPMENT.md`](./DEVELOPMENT.md)).

## Docs map

- [`README.md`](./README.md) — what the product does, how to use it, GA
  addressing model, the four tabs.
- [`DEVELOPMENT.md`](./DEVELOPMENT.md) — local dev setup, project structure,
  how to add a feature.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — persistence, the self-update
  mechanism, Proxmox/LXC deployment.
- [`CHANGELOG.md`](./CHANGELOG.md) — notable changes over time.
