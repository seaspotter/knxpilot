"""
Automatic/manual backups of the whole SQLite database - not just individual
projects (see routers/projects.py's export-json/duplicate for that, which
is a lossy per-project snapshot missing Abgangsliste/Geräteplanung/
Klärungsliste data, by design - it's meant for transferring/duplicating one
project, not disaster recovery). A full-database backup is a complete,
atomic snapshot: restoring is just replacing backend/data/knx_ga.db with a
downloaded copy and restarting.

Two destinations, both optional and independently toggleable in Setup ->
Backup:
  - "local": a filesystem path, meant to be a NAS/network share bind-mounted
    into the container (see DEPLOYMENT.md) - writing here is a plain file
    copy, no new dependency needed.
  - "nextcloud": a WebDAV folder, uploaded via plain HTTP (PUT to upload,
    PROPFIND to list existing backups for retention, DELETE to prune) using
    only the standard library (urllib) rather than adding a WebDAV client
    dependency for what's fundamentally three HTTP calls.

Scheduling lives in backend/main.py's background task; this module only
knows how to take one snapshot and ship it to whichever destinations are
enabled "right now" (run_backup_now reads the current company_profile row
itself, so it's always in sync with the latest saved settings).

Restoring (restore_database() below) is the reverse direction - always
validates the incoming file actually looks like a KNXpilot database first,
and always takes a fresh safety snapshot of the CURRENT database before
overwriting it, so an accidental/wrong restore is itself still
recoverable. The caller (backend/routers/system.py) is responsible for
restarting the process afterwards.
"""
import base64
import os
import re
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .db import DB_PATH

BACKUP_FILENAME_RE = re.compile(r"^knxpilot_backup_\d{8}_\d{6}\.db$")


def _snapshot_bytes():
    """A consistent point-in-time copy of the live database, taken via
    SQLite's own backup API - safe to run while the app is serving
    requests, unlike a plain file copy which could grab a half-written
    page mid-write."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "backup.db"
        source = sqlite3.connect(DB_PATH)
        try:
            dest = sqlite3.connect(tmp_path)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        return tmp_path.read_bytes()


def _backup_filename():
    return f"knxpilot_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"


# ---------- Listing / restoring ----------
# Tables that must be present for an uploaded/selected file to be treated
# as a genuine KNXpilot database before it's allowed to replace the live
# one - deliberately a subset of backend/db.py's schema (the ones least
# likely to ever be renamed), not an exhaustive/version-pinned check.
_EXPECTED_TABLES = {"projects", "company_profile", "categories", "floors", "room_points", "actor_types"}


def list_local_backups(path_str):
    """Newest-first metadata for every knxpilot_backup_<timestamp>.db file
    in the local/mounted backup folder - used by Setup -> Backup's
    "Vorhandene Sicherungen" list. Pre-restore safety snapshots (see
    restore_database()) use a different filename shape and deliberately
    don't show up here, or count against the regular retention pruning -
    they're a one-off just-in-case copy, not part of the rotation."""
    folder = Path(path_str) if path_str else None
    if not folder or not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.glob("knxpilot_backup_*.db"), reverse=True):
        if not BACKUP_FILENAME_RE.match(p.name):
            continue
        stat = p.stat()
        out.append({
            "filename": p.name,
            "size": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        })
    return out


def _looks_like_knxpilot_db(path):
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        return _EXPECTED_TABLES.issubset(tables)
    except sqlite3.Error:
        return False


def restore_database(data):
    """
    Validates `data` (raw bytes of a .db file) looks like a real KNXpilot
    database, takes a pre-restore safety snapshot of the CURRENT live
    database, then atomically replaces backend/data/knx_ga.db with it.
    Raises ValueError (caller turns this into a 400) if the file doesn't
    pass validation - nothing is touched in that case. The caller must
    restart the process afterwards; this function doesn't, since it has
    no opinion on how (BackgroundTasks vs. otherwise).
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(data)
        tmp_path = Path(f.name)
    try:
        if not _looks_like_knxpilot_db(tmp_path):
            raise ValueError("Diese Datei sieht nicht wie eine KNXpilot-Datenbank aus.")

        safety_name = f"knxpilot_backup_prerestore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
        (DB_PATH.parent / safety_name).write_bytes(_snapshot_bytes())

        # NamedTemporaryFile defaults to 0600 - match the original DB
        # file's mode so a replace never quietly tightens permissions on
        # a bind-mounted volume other tooling on the host might expect to
        # read.
        try:
            os.chmod(tmp_path, DB_PATH.stat().st_mode)
        except OSError:
            pass
        os.replace(tmp_path, DB_PATH)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------- Local / mounted-folder destination ----------
def _write_local(path_str, filename, data, retention):
    folder = Path(path_str)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(data)
    existing = sorted(p.name for p in folder.glob("knxpilot_backup_*.db") if BACKUP_FILENAME_RE.match(p.name))
    if retention > 0:
        for old_name in existing[:-retention]:
            (folder / old_name).unlink(missing_ok=True)


# ---------- Nextcloud (WebDAV) destination ----------
def _webdav_request(url, method, username, password, data=None, extra_headers=None):
    req = urllib.request.Request(url, data=data, method=method)
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    return urllib.request.urlopen(req, timeout=30)


def _webdav_list(base_url, username, password):
    """PROPFIND (Depth: 1) the backup folder, return the filenames of any
    existing knxpilot_backup_*.db entries - namespace-agnostic XML parse,
    since WebDAV servers may prefix the DAV: namespace differently."""
    with _webdav_request(base_url, "PROPFIND", username, password, extra_headers={"Depth": "1"}) as resp:
        root = ET.fromstring(resp.read())
    names = []
    for el in root.iter():
        if el.tag.endswith("href") and el.text:
            name = urllib.parse.unquote(el.text.rstrip("/").rsplit("/", 1)[-1])
            if BACKUP_FILENAME_RE.match(name):
                names.append(name)
    return sorted(names)


def _upload_nextcloud(url, username, password, filename, data, retention):
    base = url if url.endswith("/") else url + "/"
    # Ensure the target folder exists - MKCOL on an already-existing
    # collection returns 405, which is the expected/harmless case here.
    try:
        _webdav_request(base, "MKCOL", username, password)
    except urllib.error.HTTPError as e:
        if e.code != 405:
            raise
    _webdav_request(base + filename, "PUT", username, password, data=data)
    if retention > 0:
        existing = _webdav_list(base, username, password)
        for old_name in existing[:-retention]:
            try:
                _webdav_request(base + old_name, "DELETE", username, password)
            except urllib.error.HTTPError:
                pass  # best-effort prune - a failed cleanup shouldn't fail the whole backup


# ---------- Orchestration ----------
def run_backup_now(db):
    """Runs whichever destinations are enabled on the company_profile row
    as of right now, returns {"ok": bool, "results": {dest: "ok"|error}}.
    Also updates backup_last_run_at/backup_last_run_status on that same
    row - callers own the get_db()/commit, this only issues db.execute()
    against the connection it's given."""
    cp = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
    results = {}

    if not cp["backup_local_enabled"] and not cp["backup_nextcloud_enabled"]:
        results["error"] = "Kein Ziel aktiviert"
    else:
        filename = _backup_filename()
        data = _snapshot_bytes()

        if cp["backup_local_enabled"]:
            try:
                _write_local(cp["backup_local_path"], filename, data, cp["backup_retention_count"])
                results["local"] = "ok"
            except Exception as e:
                results["local"] = f"Fehler: {e}"

        if cp["backup_nextcloud_enabled"]:
            try:
                _upload_nextcloud(
                    cp["backup_nextcloud_url"], cp["backup_nextcloud_username"], cp["backup_nextcloud_password"],
                    filename, data, cp["backup_retention_count"],
                )
                results["nextcloud"] = "ok"
            except Exception as e:
                results["nextcloud"] = f"Fehler: {e}"

    ok = bool(results) and "error" not in results and all(v == "ok" for v in results.values())
    status_text = "OK" if ok else "; ".join(f"{k}: {v}" for k, v in results.items())
    db.execute(
        "UPDATE company_profile SET backup_last_run_at=?, backup_last_run_status=? WHERE id=1",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), status_text),
    )
    return {"ok": ok, "results": results}
