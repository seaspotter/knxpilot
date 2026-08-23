"""
Project files: a handful of reference files attached to a project (building
drawings, manuals, an ETS export). Stored as a BLOB directly in the SQLite
DB (see db.py's project_files table) - deliberately not a general document
library, just enough for a few reference files alongside the rest of a
project's data.

Also home to the device-manual fetch action: Geräte Katalog -> Handbücher
lets the user curate a manufacturer PDF URL per device type
(actor_types.manual_url); here, "Herunterladen" fetches that URL and saves
the result as one of THIS project's files, for whichever devices are
actually used in the project (via geraeteplanung.device_summary()). This
is a plain http(s) GET of a URL the user themselves typed into their own
catalog - not a search/scrape - and only ever runs when the user clicks
the button, never automatically (matches the same "manual, confirm first"
choice made for routers/email.py's send action).
"""
import urllib.error
import urllib.request
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from ..db import get_db
from .geraeteplanung import device_summary

router = APIRouter(tags=["project_files"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB - generous for drawings/PDFs/an ETS export, not bulk storage


@router.get("/api/projects/{project_id}/files")
def list_project_files(project_id: int):
    """Metadata only (no `data`) - keeps the list cheap even if a file is large."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, project_id, filename, content_type, size_bytes, uploaded_at "
            "FROM project_files WHERE project_id=? ORDER BY uploaded_at, id",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/api/projects/{project_id}/files")
async def upload_project_file(project_id: int, file: UploadFile = File(...)):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, f"Datei zu gross (max. {MAX_FILE_SIZE // (1024 * 1024)} MB)")
        cur = db.execute(
            "INSERT INTO project_files (project_id, filename, content_type, size_bytes, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, file.filename or "Datei", file.content_type or "", len(data), data),
        )
        return {"id": cur.lastrowid}


@router.get("/api/project-files/{file_id}/download")
def download_project_file(file_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT filename, content_type, data FROM project_files WHERE id=?", (file_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        return Response(
            content=row["data"],
            media_type=row["content_type"] or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'},
        )


@router.delete("/api/project-files/{file_id}")
def delete_project_file(file_id: int):
    with get_db() as db:
        db.execute("DELETE FROM project_files WHERE id=?", (file_id,))
    return {"ok": True}


# ---------- Device manuals (Geräte Katalog -> Handbücher) ----------
def _manual_filename(manufacturer, model):
    name = " ".join(p for p in (manufacturer, model) if p) or "Geraet"
    return f"{name} Handbuch.pdf".replace("/", "-")


def _fetch_manual_bytes(url):
    """Downloads a manual from a manufacturer-provided URL, capped at
    MAX_FILE_SIZE - only http(s) schemes are allowed (the URL is admin-
    curated in the device catalog, not arbitrary end-user input, but
    rejecting other schemes is a cheap, free guard against e.g. a pasted
    local file:// path). Raises ValueError with a ready-to-show German
    message on any failure, so the caller doesn't need to translate
    exception types itself."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Nur http(s)-URLs werden unterstützt.")
    req = urllib.request.Request(url, headers={"User-Agent": "KNXpilot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = (resp.headers.get("Content-Type") or "application/pdf").split(";")[0].strip()
            chunks = []
            total = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise ValueError(f"Datei zu gross (max. {MAX_FILE_SIZE // (1024 * 1024)} MB).")
                chunks.append(chunk)
            return b"".join(chunks), content_type
    except urllib.error.HTTPError as e:
        raise ValueError(f"Server antwortete mit Fehler {e.code}.") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Nicht erreichbar: {e.reason}") from e


@router.get("/api/projects/{project_id}/manuals")
def list_project_manuals(project_id: int):
    """Every device used in the project that has a curated manual_url in
    the catalog, annotated with whether it's already been fetched into
    this project's Dateien - a plain filename-existence check (the same
    name fetch_project_manual() below would use), no separate tracking
    table needed."""
    with get_db() as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        existing_filenames = {
            r["filename"] for r in db.execute(
                "SELECT filename FROM project_files WHERE project_id=?", (project_id,)
            ).fetchall()
        }

    result = []
    for d in device_summary(project_id):
        if not d["manual_url"]:
            continue
        filename = _manual_filename(d["manufacturer"], d["model"])
        result.append({
            "device_type_id": d["device_type_id"],
            "device_name": d["device_name"],
            "manual_url": d["manual_url"],
            "already_downloaded": filename in existing_filenames,
        })
    return result


@router.post("/api/projects/{project_id}/fetch-manual/{device_type_id}")
def fetch_project_manual(project_id: int, device_type_id: int):
    """Fetches one device's curated manual URL and saves it as a project
    file - only ever runs on this explicit click, never automatically
    (same "manual, confirm first" choice as routers/email.py's send
    action). Re-clicking after it's already been fetched is a no-op
    (matched by filename) rather than a duplicate download."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        device_type = db.execute("SELECT * FROM actor_types WHERE id=?", (device_type_id,)).fetchone()
        if not device_type or not device_type["manual_url"]:
            raise HTTPException(404, "Kein Handbuch-Link für dieses Gerät hinterlegt.")

        filename = _manual_filename(device_type["manufacturer"], device_type["model"])
        existing = db.execute(
            "SELECT id FROM project_files WHERE project_id=? AND filename=?", (project_id, filename)
        ).fetchone()
        if existing:
            return {"ok": True, "already_downloaded": True, "file_id": existing["id"]}

        try:
            data, content_type = _fetch_manual_bytes(device_type["manual_url"])
        except ValueError as e:
            raise HTTPException(502, str(e))

        cur = db.execute(
            "INSERT INTO project_files (project_id, filename, content_type, size_bytes, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, filename, content_type, len(data), data),
        )
        return {"ok": True, "already_downloaded": False, "file_id": cur.lastrowid}


@router.post("/api/projects/{project_id}/fetch-manuals")
def fetch_all_project_manuals(project_id: int):
    """Bulk variant of fetch_project_manual() above - fetches every
    not-yet-downloaded manual for the project in one request, tolerating
    individual failures (a broken link for one device shouldn't block the
    rest)."""
    manuals = list_project_manuals(project_id)
    fetched, already, failed = [], [], []
    for m in manuals:
        if m["already_downloaded"]:
            already.append(m["device_name"])
            continue
        try:
            fetch_project_manual(project_id, m["device_type_id"])
            fetched.append(m["device_name"])
        except HTTPException as e:
            failed.append({"device_name": m["device_name"], "error": e.detail})
    return {"fetched": fetched, "already_downloaded": already, "failed": failed}
