"""
Gruppenadressen tab: Projects, Floors, Rooms, Points, Special addresses,
the project tree, JSON backup/restore, and the GA preview/CSV export.
"""
import csv
import io
import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..ga_logic import build_ga_tree
from ..models import ProjectIn, FloorIn, RoomIn, RoomPointIn, RoomPointEditIn, SpecialItemIn, StructureMoveIn
from ..utils import AGED_KLAERUNG_DAYS, content_disposition

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

        klaerung_rows = db.execute(
            "SELECT project_id, COUNT(*) AS open_count, "
            "SUM(CASE WHEN julianday('now') - julianday(created_at) >= ? THEN 1 ELSE 0 END) AS aged_count "
            "FROM klaerungen WHERE status='offen' GROUP BY project_id",
            (AGED_KLAERUNG_DAYS,),
        ).fetchall()
        by_project = {r["project_id"]: r for r in klaerung_rows}

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
            "open_klaerungen_total": sum(r["open_count"] for r in klaerung_rows),
            "aged_klaerungen_total": sum(r["aged_count"] or 0 for r in klaerung_rows),
            "aged_threshold_days": AGED_KLAERUNG_DAYS,
            "projects_with_open_klaerungen": projects_with_open,
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
        "klaerungen": count("SELECT COUNT(*) FROM klaerungen WHERE room_id IN ({marks})", room_ids),
        "specials": count("SELECT COUNT(*) FROM special_items WHERE location IN ({marks})", [str(f) for f in floor_ids]),
        "actors_detached": count("SELECT COUNT(*) FROM actor_instances WHERE floor_id IN ({marks})", floor_ids),
        "verteiler_detached": count("SELECT COUNT(*) FROM verteiler WHERE floor_id IN ({marks})", floor_ids),
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
        for k in ("actors_detached", "verteiler_detached", "specials"):
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
    return {(r["address"], r["name"]) for r in _flatten_ga(build_ga_tree(project_id, db)) if _is_function(r)}


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
        # A Verteiler placed in this room moves along to the new Geschoss.
        db.execute("UPDATE verteiler SET floor_id=? WHERE room_id=?", (target_floor, room_id))
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


@router.post("/api/rooms/{room_id}/points")
def add_room_point(room_id: int, rp: RoomPointIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM room_points WHERE room_id=?", (room_id,)).fetchone()
        ids = []
        for i in range(max(1, rp.quantity)):
            label = rp.label
            if not label and rp.quantity > 1:
                label = str(i + 1)
            cur = db.execute(
                "INSERT INTO room_points (room_id, point_type_id, label, order_idx, has_bwm) VALUES (?, ?, ?, ?, ?)",
                (room_id, rp.point_type_id, label, count + i, int(rp.has_bwm)),
            )
            ids.append(cur.lastrowid)
        return {"ids": ids}


@router.put("/api/room-points/{rp_id}")
def update_room_point(rp_id: int, rp: RoomPointEditIn):
    with get_db() as db:
        db.execute(
            "UPDATE room_points SET point_type_id=?, label=?, has_bwm=? WHERE id=?",
            (rp.point_type_id, rp.label, int(rp.has_bwm), rp_id),
        )
    return {"ok": True}


@router.delete("/api/room-points/{rp_id}")
def delete_room_point(rp_id: int):
    with get_db() as db:
        db.execute("DELETE FROM room_points WHERE id=?", (rp_id,))
    return {"ok": True}


@router.get("/api/projects/{project_id}/tree")
def get_project_tree(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        floors = db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = {"id": project["id"], "name": project["name"], "floors": [], "unplaced_verteiler": []}
        verteiler = db.execute(
            "SELECT id, name, floor_id, room_id, row_count FROM verteiler WHERE project_id=? ORDER BY order_idx",
            (project_id,),
        ).fetchall()
        def verteiler_of(floor_id=None, room_id=None):
            return [
                {"id": v["id"], "name": v["name"], "row_count": v["row_count"]}
                for v in verteiler
                if (room_id is not None and v["room_id"] == room_id)
                or (room_id is None and v["floor_id"] == floor_id and v["room_id"] is None)
            ]
        result["unplaced_verteiler"] = verteiler_of(floor_id=None)
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
                        "verteiler": verteiler_of(room_id=r["id"]),
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
                 "verteiler": verteiler_of(floor_id=f["id"]), "rooms": room_list}
            )
        return result


@router.get("/api/projects/{project_id}/specials")
def list_specials(project_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM special_items WHERE project_id=? ORDER BY category_id, order_idx", (project_id,)
        ).fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "location": r["location"],
                "name": r["name"], "suffixes": json.loads(r["suffixes_json"]),
            }
            for r in rows
        ]


@router.post("/api/projects/{project_id}/specials")
def add_special(project_id: int, s: SpecialItemIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM special_items WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO special_items (project_id, category_id, location, name, suffixes_json, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, s.category_id, s.location, s.name, json.dumps([x.dict() for x in s.suffixes]), count),
        )
        return {"id": cur.lastrowid}


@router.delete("/api/specials/{special_id}")
def delete_special(special_id: int):
    with get_db() as db:
        db.execute("DELETE FROM special_items WHERE id=?", (special_id,))
    return {"ok": True}


# --------------------------------------------------------------------------
# Project backup / duplicate / transfer (JSON) - separate from the ETS CSV export
# --------------------------------------------------------------------------
def _build_project_payload(db, project_id):
    """
    Full project definition as a dict: floors, rooms, points, and specials.
    References point types / categories by NAME (not internal id) so this
    payload can be re-imported on a different install even if ids don't line
    up, as long as the same Point Types / Categories exist there. Shared by
    the export-json endpoint and duplicate_project (which feeds it straight
    into _insert_project_from_payload without a round-trip through JSON).
    """
    project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(404, "Project not found")

    categories = {r["id"]: r["name"] for r in db.execute("SELECT * FROM categories").fetchall()}
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}
    # KNX lines are referenced by their "Bereich.Linie" address, not by id.
    line_rows = db.execute("SELECT * FROM knx_lines WHERE project_id=? ORDER BY area, line", (project_id,)).fetchall()
    line_addr = {r["id"]: f"{r['area']}.{r['line']}" for r in line_rows}

    floors_out = []
    for floor in db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall():
        rooms_out = []
        for room in db.execute(
            "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
        ).fetchall():
            points_out = []
            for point in db.execute(
                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
            ).fetchall():
                pt = point_types.get(point["point_type_id"])
                if not pt:
                    continue
                points_out.append(
                    {
                        "point_type_name": pt["name"],
                        "category_name": categories.get(pt["category_id"], ""),
                        "label": point["label"],
                        "has_bwm": bool(point["has_bwm"]),
                    }
                )
            rooms_out.append({"name": room["name"], "line": line_addr.get(room["line_id"]), "points": points_out})
        floors_out.append({"name": floor["name"], "is_outdoor": bool(floor["is_outdoor"]),
                           "line": line_addr.get(floor["line_id"]), "rooms": rooms_out})

    floor_order_by_id = {}
    for floor in db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall():
        floor_order_by_id[floor["id"]] = floor["order_idx"]

    specials_out = []
    for s in db.execute(
        "SELECT * FROM special_items WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall():
        location = s["location"]
        if location != "central" and location.isdigit() and int(location) in floor_order_by_id:
            location = f"floor:{floor_order_by_id[int(location)]}"
        specials_out.append(
            {
                "category_name": categories.get(s["category_id"], ""),
                "location": location,
                "name": s["name"],
                "suffixes": json.loads(s["suffixes_json"]),
            }
        )

    return {
        "format": "knx-ga-project-v1.1",
        "project_name": project["name"],
        "location": project["location"],
        "customer": project["customer"],
        "status": project["status"],
        "comment": project["comment"],
        "order_number": project["order_number"],
        "email": project["email"],
        "additional_recipients": project["additional_recipients"],
        "lines": [{"area": r["area"], "line": r["line"], "name": r["name"]} for r in line_rows],
        "floors": floors_out,
        "specials": specials_out,
    }


@router.get("/api/projects/{project_id}/export-json")
def export_project_json(project_id: int):
    with get_db() as db:
        payload = _build_project_payload(db, project_id)
    buf = io.StringIO()
    buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
    buf.seek(0)
    filename = f"{payload['project_name'].replace(' ', '_')}_backup.json"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(filename)},
    )


def _insert_project_from_payload(db, payload, forced_name=None):
    """
    Recreates a project from a payload produced by _build_project_payload.
    Matches Point Types and Categories by name against what already exists
    on this install - anything that doesn't match is skipped (not silently
    guessed at). If forced_name is given (duplicate_project), it's used
    as-is (caller already made sure it's unique) - otherwise, a project
    with the same name already existing gets "<name> (imported)" instead of
    overwriting it.
    """
    name = forced_name if forced_name is not None else payload.get("project_name", "Imported Project")
    if forced_name is None:
        existing = db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()
        if existing:
            name = f"{name} (imported)"

    categories_by_name = {r["name"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
    point_types_by_name = {
        (r["category_id"], r["name"]): r["id"] for r in db.execute("SELECT * FROM point_types").fetchall()
    }

    cur = db.execute(
        "INSERT INTO projects (name, location, customer, status, comment, order_number, "
        "email, additional_recipients) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            payload.get("location", ""),
            payload.get("customer", ""),
            payload.get("status", ""),
            payload.get("comment", ""),
            payload.get("order_number", ""),
            payload.get("email", ""),
            payload.get("additional_recipients", ""),
        ),
    )
    project_id = cur.lastrowid
    skipped = []

    line_ids = {}  # "Bereich.Linie" -> new knx_lines id
    for line in payload.get("lines", []):
        lcur = db.execute("INSERT INTO knx_lines (project_id, area, line, name) VALUES (?, ?, ?, ?)",
                          (project_id, int(line["area"]), int(line["line"]), line.get("name", "")))
        line_ids[f"{int(line['area'])}.{int(line['line'])}"] = lcur.lastrowid

    floor_id_map = {}  # index in payload -> new floor id, for resolving special locations
    for f_idx, floor in enumerate(payload.get("floors", [])):
        fcur = db.execute(
            "INSERT INTO floors (project_id, name, order_idx, is_outdoor, line_id) VALUES (?, ?, ?, ?, ?)",
            (project_id, floor["name"], f_idx, int(floor.get("is_outdoor", False)), line_ids.get(floor.get("line"))),
        )
        floor_id = fcur.lastrowid
        floor_id_map[f_idx] = floor_id
        for r_idx, room in enumerate(floor.get("rooms", [])):
            rcur = db.execute(
                "INSERT INTO rooms (floor_id, name, order_idx, line_id) VALUES (?, ?, ?, ?)",
                (floor_id, room["name"], r_idx, line_ids.get(room.get("line"))),
            )
            room_id = rcur.lastrowid
            for p_idx, point in enumerate(room.get("points", [])):
                cat_id = categories_by_name.get(point.get("category_name"))
                pt_id = point_types_by_name.get((cat_id, point.get("point_type_name")))
                if not pt_id:
                    skipped.append(f"{room['name']}: {point.get('point_type_name')}")
                    continue
                db.execute(
                    "INSERT INTO room_points (room_id, point_type_id, label, order_idx, has_bwm) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (room_id, pt_id, point.get("label", ""), p_idx, int(point.get("has_bwm", False))),
                )

    for s_idx, special in enumerate(payload.get("specials", [])):
        cat_id = categories_by_name.get(special.get("category_name"))
        if not cat_id:
            skipped.append(f"special: {special.get('name')}")
            continue
        location = special.get("location", "central")
        if isinstance(location, str) and location.startswith("floor:"):
            floor_pos = int(location.split(":", 1)[1])
            location = str(floor_id_map.get(floor_pos, "central"))
        db.execute(
            "INSERT INTO special_items (project_id, category_id, location, name, suffixes_json, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, cat_id, location, special.get("name", ""),
             json.dumps(special.get("suffixes", [])), s_idx),
        )

    return {"id": project_id, "name": name, "skipped": skipped}


@router.post("/api/projects/import-json")
def import_project_json(payload: dict):
    with get_db() as db:
        return _insert_project_from_payload(db, payload)


@router.post("/api/projects/{project_id}/duplicate")
def duplicate_project(project_id: int):
    """
    Same-install copy: builds the export payload and immediately re-inserts
    it under a new name, in one connection/transaction - no skipped items
    are possible here (Point Types/Categories always match themselves), the
    way they theoretically could on a cross-install import-json.
    """
    with get_db() as db:
        payload = _build_project_payload(db, project_id)
        base_name = payload["project_name"]
        name = f"{base_name} (Kopie)"
        n = 2
        while db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone():
            name = f"{base_name} (Kopie {n})"
            n += 1
        return _insert_project_from_payload(db, payload, forced_name=name)


# --------------------------------------------------------------------------
# GA preview / ETS CSV export
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/preview")
def preview_ga(project_id: int):
    return build_ga_tree(project_id)


def _flatten_ga(tree):
    """Every exported row as {address, name, dpt} - main and middle groups
    ("1/-/-", "1/2/-") included, since ETS needs those created too."""
    rows = []
    for main in tree["main_groups"]:
        rows.append({"address": f"{main['main']}/-/-", "name": main["name"], "dpt": ""})
        for middle in main["middles"]:
            rows.append({"address": f"{main['main']}/{middle['middle']}/-", "name": middle["name"], "dpt": ""})
            for sub in middle["subs"]:
                rows.append({"address": f"{main['main']}/{middle['middle']}/{sub['sub']}", "name": sub["name"], "dpt": sub["dpt"]})
    return rows


def _save_ga_snapshot(project_id, tree):
    with get_db() as db:
        db.execute(
            "INSERT INTO ga_export_snapshots (project_id, exported_at, data) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET exported_at=excluded.exported_at, data=excluded.data",
            (project_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             json.dumps(_flatten_ga(tree), ensure_ascii=False)),
        )


def _address_key(address):
    return tuple(-1 if part == "-" else int(part) for part in address.split("/"))


def _is_function(row):
    """A real function's group address - not a main/middle group row and not
    a reserved "res" placeholder."""
    return not row["address"].endswith("-") and not row["name"].endswith("res")


@router.get("/api/projects/{project_id}/ga-changes")
def ga_changes(project_id: int):
    """What changed in the group addresses since the last ETS export - i.e.
    what still has to be done in ETS.

    Adding or removing a function shifts every later address in its block,
    so real functions are matched by name first: one that now sits on a
    different address is "moved" (in ETS: change that group address's
    address, which keeps its links to devices - not delete + re-create).
    Moves are listed from the highest target address down, the order that
    avoids address collisions in ETS. With the moves applied, the rest is
    compared by address: "added" (create), "changed" (same address, new name
    or DPT - e.g. a renamed room, or a "res" slot now used by a function)
    and "removed" (delete)."""
    current = _flatten_ga(build_ga_tree(project_id))
    with get_db() as db:
        snap = db.execute("SELECT * FROM ga_export_snapshots WHERE project_id=?", (project_id,)).fetchone()
    if not snap:
        return {"exported_at": None, "total": len(current)}
    before = json.loads(snap["data"])

    def unique_functions(rows):
        names = [r["name"] for r in rows if _is_function(r)]
        return {r["name"]: r for r in rows if _is_function(r) and names.count(r["name"]) == 1}
    before_fn, now_fn = unique_functions(before), unique_functions(current)
    moved = [
        {"name": n, "old_address": before_fn[n]["address"], "address": now_fn[n]["address"],
         "old_dpt": before_fn[n]["dpt"], "dpt": now_fn[n]["dpt"]}
        for n in now_fn if n in before_fn and before_fn[n]["address"] != now_fn[n]["address"]
    ]

    # ETS state once the moves are done: moved functions leave their old
    # address and take their new one (anything that sat there has to go).
    state = {r["address"]: r for r in before}
    displaced = []
    for m in moved:
        state.pop(m["old_address"], None)
    for m in moved:
        if m["address"] in state:
            displaced.append(state[m["address"]])
        state[m["address"]] = {"address": m["address"], "name": m["name"], "dpt": m["old_dpt"]}

    now = {r["address"]: r for r in current}
    added = [now[a] for a in now if a not in state]
    removed = [state[a] for a in state if a not in now] + displaced
    changed = [
        {"address": a, "old_name": state[a]["name"], "name": now[a]["name"], "old_dpt": state[a]["dpt"], "dpt": now[a]["dpt"]}
        for a in now if a in state and (state[a]["name"], state[a]["dpt"]) != (now[a]["name"], now[a]["dpt"])
    ]
    by_addr = lambda rows: sorted(rows, key=lambda r: _address_key(r["address"]))
    return {
        "exported_at": snap["exported_at"], "total": len(current),
        "moved": sorted(moved, key=lambda r: _address_key(r["address"]), reverse=True),
        "added": by_addr(added), "changed": by_addr(changed), "removed": by_addr(removed),
    }


@router.post("/api/projects/{project_id}/ga-snapshot")
def mark_ga_exported(project_id: int):
    """"Aktuellen Stand als in ETS übernommen markieren" - sets the baseline
    without downloading (e.g. the ETS project was already brought up to date
    by hand, or for projects exported before snapshots existed)."""
    _save_ga_snapshot(project_id, build_ga_tree(project_id))
    return {"ok": True}


@router.get("/api/projects/{project_id}/export.csv")
def export_csv(project_id: int):
    data = build_ga_tree(project_id)
    # This download is "the ETS export" - remember it as the baseline for
    # the changes view above.
    _save_ga_snapshot(project_id, data)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL)

    writer.writerow(
        ["Main", "Middle", "Sub", "Address", "Central", "Unfiltered", "Description", "DatapointType", "Security"]
    )

    for main in data["main_groups"]:
        writer.writerow([main["name"], "", "", f"{main['main']}/-/-", "", "", "", "", "Auto"])
        for middle in main["middles"]:
            writer.writerow(["", middle["name"], "", f"{main['main']}/{middle['middle']}/-", "", "", "", "", "Auto"])
            for sub in middle["subs"]:
                writer.writerow(
                    [
                        "", "", sub["name"],
                        f"{main['main']}/{middle['middle']}/{sub['sub']}",
                        "", "", "", sub["dpt"], "Auto",
                    ]
                )

    buf.seek(0)
    filename = f"{data['project_name'].replace(' ', '_')}_group_addresses.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("iso-8859-1", errors="replace")]),
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition(filename)},
    )
