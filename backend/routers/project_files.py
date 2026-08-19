"""
Project files: a handful of reference files attached to a project (building
drawings, manuals, an ETS export). Stored as a BLOB directly in the SQLite
DB (see db.py's project_files table) - deliberately not a general document
library, just enough for a few reference files alongside the rest of a
project's data.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from ..db import get_db

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
