"""
Project files: a handful of reference files attached to a project (building
drawings, an ETS export, etc.). Stored as a BLOB directly in the SQLite
DB (see db.py's project_files table) - deliberately not a general document
library, just enough for a few reference files alongside the rest of a
project's data.

Device manuals are handled separately, in routers/manuals.py - fetched
from a catalog-curated URL rather than uploaded, and kept in their own
project_manuals table so this list only ever shows what the user
themselves uploaded.

The "Dateien" section of the overview tab (routers/overview.py) is
rendered server-side with htmx: the /hx/... endpoints below render just the
`<ul>` list fragment (backend/templates/project_files/_list.html), fetched
on load and re-fetched after upload/delete - the same nested-fragment
pattern Setup -> Backup's file list uses.
"""
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from ..db import get_db
from ..templating import client_zone, templates
from ..utils import content_disposition, human_file_size

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
            headers={"Content-Disposition": content_disposition(row["filename"])},
        )


@router.delete("/api/project-files/{file_id}")
def delete_project_file(file_id: int):
    with get_db() as db:
        db.execute("DELETE FROM project_files WHERE id=?", (file_id,))
    return {"ok": True}


# ---------- htmx fragment (backend/templates/project_files/_list.html) ----------
def _files_list(request, project_id):
    zone = client_zone(request)
    files = list_project_files(project_id)
    for f in files:
        f["size_text"] = human_file_size(f["size_bytes"])
        f["date_text"] = datetime.fromisoformat(f["uploaded_at"]).astimezone(zone).strftime("%d.%m.%Y") if f["uploaded_at"] else ""
    return templates.TemplateResponse(request, "project_files/_list.html", {"files": files})


@router.get("/hx/projects/{project_id}/files")
def hx_list(request: Request, project_id: int):
    return _files_list(request, project_id)


@router.post("/hx/projects/{project_id}/files")
async def hx_upload(request: Request, project_id: int, file: UploadFile = File(...)):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        data = await file.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, f"Datei zu gross (max. {MAX_FILE_SIZE // (1024 * 1024)} MB)")
        db.execute(
            "INSERT INTO project_files (project_id, filename, content_type, size_bytes, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, file.filename or "Datei", file.content_type or "", len(data), data),
        )
    return _files_list(request, project_id)


@router.delete("/hx/project-files/{file_id}")
def hx_delete(request: Request, file_id: int):
    with get_db() as db:
        row = db.execute("SELECT project_id FROM project_files WHERE id=?", (file_id,)).fetchone()
        if not row:
            raise HTTPException(404, "File not found")
        db.execute("DELETE FROM project_files WHERE id=?", (file_id,))
    return _files_list(request, row["project_id"])
