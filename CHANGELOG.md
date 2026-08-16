# Changelog

Notable changes to KNXpilot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this file starts from the
restructuring below — history before that is available via `git log`.

## [Unreleased]

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
