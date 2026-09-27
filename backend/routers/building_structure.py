"""
Gebäudestruktur sub-tab: floors, rooms, the project structure tree (incl.
drag & drop with GA-impact dry run), and where a distribution board sits in
that tree. The Projekte-tab concerns (project CRUD/list/dashboard/backup/
duplicate) stay in routers/projects.py.

The tree UI itself stays classic JS with drag & drop wired to these JSON
endpoints (frontend/js/building_structure.js) - see DEVELOPMENT.md's htmx
migration notes for why this tab is the one exception left un-htmx'd.
Room points/Sonderadressen live in routers/functions.py, the GA preview/CSV
export in routers/group_addresses.py, and a distribution board's own
DIN-rail contents in routers/distribution_boards.py - all still read the
same floors/rooms tables, but their own endpoints moved out when those
sub-tabs were converted to htmx.
"""
from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..ga_logic import build_ga_tree, flatten_ga_tree, is_function_row
from ..models import FloorIn, RoomIn, StructureMoveIn

router = APIRouter(tags=["building-structure"])


def impact(db, room_ids, floor_ids):
    """Counts of what deleting these rooms/floors takes with it (via ON DELETE
    CASCADE) or detaches (ON DELETE SET NULL) - shown in the delete
    confirmation so nothing disappears unannounced. Shared with
    routers/projects.py's project-level delete-impact."""
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
        return {"name": floor["name"], **impact(db, room_ids, [floor_id])}


@router.get("/api/rooms/{room_id}/delete-impact")
def room_delete_impact(room_id: int):
    with get_db() as db:
        room = db.execute("SELECT name FROM rooms WHERE id=?", (room_id,)).fetchone()
        if not room:
            raise HTTPException(404, "Room not found")
        result = impact(db, [room_id], [])
        result.pop("rooms")
        return {"name": room["name"], **result}


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
