"""
Projekte tab: project list, dashboard, CRUD, delete-impact, and JSON backup/
restore/duplicate. The Gebäudestruktur sub-tab (floors, rooms, the structure
tree, drag & drop, move endpoints) lives in routers/building_structure.py.
"""
import io
import json
import sqlite3

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from .building_structure import impact
from ..project_transfer import build_project_payload, insert_project_from_payload
from ..models import ProjectIn
from ..utils import AGED_CLARIFICATION_DAYS, content_disposition

router = APIRouter(tags=["projects"])


@router.get("/api/projects")
def list_projects():
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY id").fetchall()]


@router.get("/api/projects/dashboard")
def projects_dashboard():
    """Aggregated status across every project, for the all-projects
    dashboard shown above the Projekte list (frontend/js/projekte.js's
    loadProjectsDashboard(), called every time loadProjects() is - so it
    stays in sync with every create/delete/duplicate automatically). Kept
    as one query pass per concern rather than N+1 per-project calls,
    since it needs to cover every project on every project-list load."""
    with get_db() as db:
        projects = db.execute("SELECT id, name, status FROM projects ORDER BY name").fetchall()

        by_status = {}
        for p in projects:
            status = p["status"] or "(ohne Status)"
            by_status[status] = by_status.get(status, 0) + 1

        floor_counts = {
            r["project_id"] for r in db.execute("SELECT DISTINCT project_id FROM floors").fetchall()
        }
        without_structure = [{"id": p["id"], "name": p["name"]} for p in projects if p["id"] not in floor_counts]

        clarification_rows = db.execute(
            "SELECT project_id, COUNT(*) AS open_count, "
            "SUM(CASE WHEN julianday('now') - julianday(created_at) >= ? THEN 1 ELSE 0 END) AS aged_count "
            "FROM clarifications WHERE status='offen' GROUP BY project_id",
            (AGED_CLARIFICATION_DAYS,),
        ).fetchall()
        by_project = {r["project_id"]: r for r in clarification_rows}

        projects_with_open = [
            {
                "id": p["id"], "name": p["name"],
                "open_count": by_project[p["id"]]["open_count"],
                "aged_count": by_project[p["id"]]["aged_count"] or 0,
            }
            for p in projects if p["id"] in by_project
        ]
        projects_with_open.sort(key=lambda x: (-x["aged_count"], -x["open_count"]))

        return {
            "total": len(projects),
            "by_status": by_status,
            "open_clarifications_total": sum(r["open_count"] for r in clarification_rows),
            "aged_clarifications_total": sum(r["aged_count"] or 0 for r in clarification_rows),
            "aged_threshold_days": AGED_CLARIFICATION_DAYS,
            "projects_with_open_clarifications": projects_with_open,
            "projects_without_structure": without_structure,
        }


@router.post("/api/projects")
def create_project(p: ProjectIn):
    with get_db() as db:
        try:
            cur = db.execute(
                "INSERT INTO projects (name, location, customer, status, comment, order_number, "
                "email, additional_recipients) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p.name, p.location, p.customer, p.status, p.comment, p.order_number,
                 p.email, p.additional_recipients),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(400, "A project with that name already exists")
        return {"id": cur.lastrowid}


@router.put("/api/projects/{project_id}")
def update_project(project_id: int, p: ProjectIn):
    with get_db() as db:
        try:
            db.execute(
                "UPDATE projects SET name=?, location=?, customer=?, status=?, comment=?, order_number=?, "
                "email=?, additional_recipients=? WHERE id=?",
                (p.name, p.location, p.customer, p.status, p.comment, p.order_number,
                 p.email, p.additional_recipients, project_id),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(400, "A project with that name already exists")
    return {"ok": True}


@router.get("/api/projects/{project_id}/delete-impact")
def project_delete_impact(project_id: int):
    with get_db() as db:
        floor_ids = [r["id"] for r in db.execute("SELECT id FROM floors WHERE project_id=?", (project_id,))]
        room_ids = [r["id"] for r in db.execute(
            "SELECT r.id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,))]
        result = impact(db, room_ids, floor_ids)
        result["floors"] = len(floor_ids)
        result["actors"] = db.execute("SELECT COUNT(*) FROM actor_instances WHERE project_id=?", (project_id,)).fetchone()[0]
        result["files"] = db.execute("SELECT COUNT(*) FROM project_files WHERE project_id=?", (project_id,)).fetchone()[0]
        result["manuals"] = db.execute("SELECT COUNT(*) FROM project_manuals WHERE project_id=?", (project_id,)).fetchone()[0]
        for k in ("actors_detached", "distribution_boards_detached", "specials"):
            result.pop(k)  # the whole project goes, nothing is merely detached
        return result


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    with get_db() as db:
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"ok": True}


# --------------------------------------------------------------------------
# Project backup / duplicate / transfer (JSON) - separate from the ETS CSV export.
# The payload itself (what's in it, how references survive another install,
# "backup" vs "duplicate" mode) lives in backend/project_transfer.py.
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/export-json")
def export_project_json(project_id: int):
    with get_db() as db:
        payload = build_project_payload(db, project_id, mode="backup")
    buf = io.StringIO()
    buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
    buf.seek(0)
    filename = f"{payload['project_name'].replace(' ', '_')}_backup.json"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.post("/api/projects/import-json")
def import_project_json(payload: dict):
    with get_db() as db:
        return insert_project_from_payload(db, payload)


@router.post("/api/projects/{project_id}/duplicate")
def duplicate_project(project_id: int):
    """
    Same-install copy of the planning data ("duplicate" mode - no checklist
    results, signatures, ETS export state, Klärungen or files): builds the
    payload and immediately re-inserts it under a new name, in one
    connection/transaction - nothing can be skipped here, since every
    catalog reference matches itself on the same install.
    """
    with get_db() as db:
        payload = build_project_payload(db, project_id, mode="duplicate")
        base_name = payload["project_name"]
        name = f"{base_name} (Kopie)"
        n = 2
        while db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone():
            name = f"{base_name} (Kopie {n})"
            n += 1
        return insert_project_from_payload(db, payload, forced_name=name)
