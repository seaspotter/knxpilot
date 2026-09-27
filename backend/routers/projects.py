"""
Building structure ("Gebäudestruktur" sub-tab): Projects, Floors, Rooms, the
project tree (incl. drag & drop with GA-impact dry run), and JSON backup/
restore/duplicate. Room points/Sonderadressen live in routers/functions.py,
the GA preview/CSV export in routers/group_addresses.py - both still read
the same floors/rooms tables, but their own endpoints moved out when those
two sub-tabs were converted to htmx.
"""
import io
import json
import sqlite3

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..ga_logic import build_ga_tree, flatten_ga_tree, is_function_row
from ..project_transfer import build_project_payload, insert_project_from_payload
from ..models import ProjectIn, FloorIn, RoomIn, StructureMoveIn
from ..utils import AGED_CLARIFICATION_DAYS, content_disposition

router = APIRouter(tags=["projects"])


# --------------------------------------------------------------------------
# Projects / Floors / Rooms / Points
# --------------------------------------------------------------------------
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


def _impact(db, room_ids, floor_ids):
    """Counts of what deleting these rooms/floors takes with it (via ON DELETE
    CASCADE) or detaches (ON DELETE SET NULL) - shown in the delete
    confirmation so nothing disappears unannounced."""
    def count(sql, ids):
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        return db.execute(sql.format(marks=marks), ids).fetchone()[0]
    return {
        "rooms": len(room_ids),
        "points": count("SELECT COUNT(*) FROM room_points WHERE room_id IN ({marks})", room_ids),
        "assignments": count(
            "SELECT COUNT(*) FROM channel_assignments WHERE room_point_id IN "
            "(SELECT id FROM room_points WHERE room_id IN ({marks}))", room_ids),
        "devices": count("SELECT COUNT(*) FROM room_devices WHERE room_id IN ({marks})", room_ids)
                   + count("SELECT COUNT(*) FROM floor_devices WHERE floor_id IN ({marks})", floor_ids),
        "clarifications": count("SELECT COUNT(*) FROM clarifications WHERE room_id IN ({marks})", room_ids),
        "specials": count("SELECT COUNT(*) FROM special_items WHERE location IN ({marks})", [str(f) for f in floor_ids]),
        "actors_detached": count("SELECT COUNT(*) FROM actor_instances WHERE floor_id IN ({marks})", floor_ids),
        "distribution_boards_detached": count("SELECT COUNT(*) FROM distribution_boards WHERE floor_id IN ({marks})", floor_ids),
    }


@router.get("/api/floors/{floor_id}/delete-impact")
def floor_delete_impact(floor_id: int):
    with get_db() as db:
        floor = db.execute("SELECT name FROM floors WHERE id=?", (floor_id,)).fetchone()
        if not floor:
            raise HTTPException(404, "Floor not found")
        room_ids = [r["id"] for r in db.execute("SELECT id FROM rooms WHERE floor_id=?", (floor_id,))]
        return {"name": floor["name"], **_impact(db, room_ids, [floor_id])}


@router.get("/api/rooms/{room_id}/delete-impact")
def room_delete_impact(room_id: int):
    with get_db() as db:
        room = db.execute("SELECT name FROM rooms WHERE id=?", (room_id,)).fetchone()
        if not room:
            raise HTTPException(404, "Room not found")
        result = _impact(db, [room_id], [])
        result.pop("rooms")
        return {"name": room["name"], **result}


@router.get("/api/projects/{project_id}/delete-impact")
def project_delete_impact(project_id: int):
    with get_db() as db:
        floor_ids = [r["id"] for r in db.execute("SELECT id FROM floors WHERE project_id=?", (project_id,))]
        room_ids = [r["id"] for r in db.execute(
            "SELECT r.id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,))]
        result = _impact(db, room_ids, floor_ids)
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


@router.post("/api/projects/{project_id}/floors")
def add_floor(project_id: int, f: FloorIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM floors WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO floors (project_id, name, order_idx, is_outdoor) VALUES (?, ?, ?, ?)",
            (project_id, f.name, count, int(f.is_outdoor)),
        )
        return {"id": cur.lastrowid}


@router.put("/api/floors/{floor_id}")
def update_floor(floor_id: int, f: FloorIn):
    with get_db() as db:
        db.execute(
            "UPDATE floors SET name=?, is_outdoor=? WHERE id=?",
            (f.name, int(f.is_outdoor), floor_id),
        )
    return {"ok": True}


@router.delete("/api/floors/{floor_id}")
def delete_floor(floor_id: int):
    with get_db() as db:
        # special_items.location is a polymorphic string ('central' or a floor
        # id), so there's no FK to cascade - without this they'd linger as
        # invisible leftovers that never show up in the GA tree again.
        db.execute("DELETE FROM special_items WHERE location=?", (str(floor_id),))
        db.execute("DELETE FROM floors WHERE id=?", (floor_id,))
    return {"ok": True}


@router.post("/api/floors/{floor_id}/rooms")
def add_room(floor_id: int, r: RoomIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM rooms WHERE floor_id=?", (floor_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO rooms (floor_id, name, order_idx) VALUES (?, ?, ?)",
            (floor_id, r.name, count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/rooms/{room_id}")
def update_room(room_id: int, r: RoomIn):
    with get_db() as db:
        db.execute("UPDATE rooms SET name=? WHERE id=?", (r.name, room_id))
    return {"ok": True}


@router.delete("/api/rooms/{room_id}")
def delete_room(room_id: int):
    with get_db() as db:
        db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
    return {"ok": True}


# Drag & drop in the Gebäudestruktur tree. Moving a room (or reordering
# floors/rooms) shifts group addresses: the Mittelgruppe is the Geschoss and
# the rooms' address blocks follow their order. So the frontend first calls
# with dry_run=true, which applies the move inside the transaction, compares
# the GA tree before/after and rolls back - the count goes into the confirm.
def _function_gas(db, project_id):
    return {(r["address"], r["name"]) for r in flatten_ga_tree(build_ga_tree(project_id, db)) if is_function_row(r)}


def _reorder(db, table, ids):
    for idx, row_id in enumerate(ids):
        db.execute(f"UPDATE {table} SET order_idx=? WHERE id=?", (idx, row_id))


def _finish_move(db, project_id, before, dry_run):
    after = _function_gas(db, project_id)
    changed = len(before - after)
    if dry_run:
        db.rollback()
    has_snapshot = db.execute(
        "SELECT 1 FROM ga_export_snapshots WHERE project_id=?", (project_id,)
    ).fetchone() is not None
    return {"ga_changed": changed, "exported": has_snapshot}


@router.post("/api/rooms/{room_id}/move")
def move_room(room_id: int, m: StructureMoveIn):
    with get_db() as db:
        room = db.execute(
            "SELECT r.*, f.project_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=?", (room_id,)
        ).fetchone()
        if not room:
            raise HTTPException(404, "Room not found")
        target_floor = m.floor_id if m.floor_id is not None else room["floor_id"]
        if not db.execute("SELECT 1 FROM floors WHERE id=? AND project_id=?", (target_floor, room["project_id"])).fetchone():
            raise HTTPException(400, "Geschoss gehört nicht zu diesem Projekt")
        before = _function_gas(db, room["project_id"])

        old_siblings = [r["id"] for r in db.execute(
            "SELECT id FROM rooms WHERE floor_id=? AND id<>? ORDER BY order_idx", (room["floor_id"], room_id))]
        target_siblings = old_siblings if target_floor == room["floor_id"] else [r["id"] for r in db.execute(
            "SELECT id FROM rooms WHERE floor_id=? ORDER BY order_idx", (target_floor,))]
        target_siblings.insert(max(0, min(m.index, len(target_siblings))), room_id)
        db.execute("UPDATE rooms SET floor_id=? WHERE id=?", (target_floor, room_id))
        # A distribution board placed in this room moves along to the new Geschoss.
        db.execute("UPDATE distribution_boards SET floor_id=? WHERE room_id=?", (target_floor, room_id))
        if target_floor != room["floor_id"]:
            _reorder(db, "rooms", old_siblings)
        _reorder(db, "rooms", target_siblings)
        return _finish_move(db, room["project_id"], before, m.dry_run)


@router.post("/api/floors/{floor_id}/move")
def move_floor(floor_id: int, m: StructureMoveIn):
    with get_db() as db:
        floor = db.execute("SELECT * FROM floors WHERE id=?", (floor_id,)).fetchone()
        if not floor:
            raise HTTPException(404, "Floor not found")
        before = _function_gas(db, floor["project_id"])
        siblings = [r["id"] for r in db.execute(
            "SELECT id FROM floors WHERE project_id=? AND id<>? ORDER BY order_idx", (floor["project_id"], floor_id))]
        siblings.insert(max(0, min(m.index, len(siblings))), floor_id)
        _reorder(db, "floors", siblings)
        return _finish_move(db, floor["project_id"], before, m.dry_run)


@router.get("/api/projects/{project_id}/tree")
def get_project_tree(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        floors = db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = {"id": project["id"], "name": project["name"], "floors": [], "unplaced_distribution_boards": []}
        boards = db.execute(
            "SELECT id, name, floor_id, room_id, row_count FROM distribution_boards WHERE project_id=? ORDER BY order_idx",
            (project_id,),
        ).fetchall()
        def distribution_boards_of(floor_id=None, room_id=None):
            return [
                {"id": b["id"], "name": b["name"], "row_count": b["row_count"]}
                for b in boards
                if (room_id is not None and b["room_id"] == room_id)
                or (room_id is None and b["floor_id"] == floor_id and b["room_id"] is None)
            ]
        result["unplaced_distribution_boards"] = distribution_boards_of(floor_id=None)
        for f in floors:
            rooms = db.execute(
                "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (f["id"],)
            ).fetchall()
            room_list = []
            for r in rooms:
                points = db.execute(
                    "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (r["id"],)
                ).fetchall()
                room_list.append(
                    {
                        "id": r["id"], "name": r["name"], "line_id": r["line_id"],
                        "distribution_boards": distribution_boards_of(room_id=r["id"]),
                        "points": [
                            {
                                "id": p["id"], "point_type_id": p["point_type_id"], "label": p["label"],
                                "has_bwm": bool(p["has_bwm"]),
                            }
                            for p in points
                        ],
                    }
                )
            result["floors"].append(
                {"id": f["id"], "name": f["name"], "is_outdoor": bool(f["is_outdoor"]), "line_id": f["line_id"],
                 "distribution_boards": distribution_boards_of(floor_id=f["id"]), "rooms": room_list}
            )
        return result


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


