"""
Gruppenadressen tab: Projects, Floors, Rooms, Points, Special addresses,
the project tree, JSON backup/restore, and the GA preview/CSV export.
"""
import csv
import io
import json
import sqlite3

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..ga_logic import build_ga_tree
from ..models import ProjectIn, FloorIn, RoomIn, RoomPointIn, SpecialItemIn

router = APIRouter(tags=["projects"])


# --------------------------------------------------------------------------
# Projects / Floors / Rooms / Points
# --------------------------------------------------------------------------
@router.get("/api/projects")
def list_projects():
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY id").fetchall()]


@router.post("/api/projects")
def create_project(p: ProjectIn):
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO projects (name) VALUES (?)", (p.name,))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "A project with that name already exists")
        return {"id": cur.lastrowid}


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


@router.delete("/api/floors/{floor_id}")
def delete_floor(floor_id: int):
    with get_db() as db:
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


@router.delete("/api/rooms/{room_id}")
def delete_room(room_id: int):
    with get_db() as db:
        db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
    return {"ok": True}


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
        result = {"id": project["id"], "name": project["name"], "floors": []}
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
                        "id": r["id"], "name": r["name"],
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
                {"id": f["id"], "name": f["name"], "is_outdoor": bool(f["is_outdoor"]), "rooms": room_list}
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
@router.get("/api/projects/{project_id}/export-json")
def export_project_json(project_id: int):
    """
    Full project definition as JSON: floors, rooms, points, and specials.
    References point types / categories by NAME (not internal id) so this file
    can be re-imported on a different install even if ids don't line up,
    as long as the same Point Types / Categories exist there.
    """
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        categories = {r["id"]: r["name"] for r in db.execute("SELECT * FROM categories").fetchall()}
        point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}

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
                rooms_out.append({"name": room["name"], "points": points_out})
            floors_out.append({"name": floor["name"], "is_outdoor": bool(floor["is_outdoor"]), "rooms": rooms_out})

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

        payload = {"format": "knx-ga-project-v1", "project_name": project["name"], "floors": floors_out, "specials": specials_out}
        buf = io.StringIO()
        buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
        buf.seek(0)
        filename = f"{project['name'].replace(' ', '_')}_backup.json"
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.post("/api/projects/import-json")
def import_project_json(payload: dict):
    """
    Recreates a project from a file produced by export-json. Matches Point Types
    and Categories by name against what already exists on this install - anything
    that doesn't match is skipped (not silently guessed at).
    If a project with the same name already exists, the import is saved under
    "<name> (imported)" instead of overwriting it.
    """
    with get_db() as db:
        name = payload.get("project_name", "Imported Project")
        existing = db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()
        if existing:
            name = f"{name} (imported)"

        categories_by_name = {r["name"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
        point_types_by_name = {
            (r["category_id"], r["name"]): r["id"] for r in db.execute("SELECT * FROM point_types").fetchall()
        }

        cur = db.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        project_id = cur.lastrowid
        skipped = []

        floor_id_map = {}  # index in payload -> new floor id, for resolving special locations
        for f_idx, floor in enumerate(payload.get("floors", [])):
            fcur = db.execute(
                "INSERT INTO floors (project_id, name, order_idx, is_outdoor) VALUES (?, ?, ?, ?)",
                (project_id, floor["name"], f_idx, int(floor.get("is_outdoor", False))),
            )
            floor_id = fcur.lastrowid
            floor_id_map[f_idx] = floor_id
            for r_idx, room in enumerate(floor.get("rooms", [])):
                rcur = db.execute(
                    "INSERT INTO rooms (floor_id, name, order_idx) VALUES (?, ?, ?)",
                    (floor_id, room["name"], r_idx),
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


# --------------------------------------------------------------------------
# GA preview / ETS CSV export
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/preview")
def preview_ga(project_id: int):
    return build_ga_tree(project_id)


@router.get("/api/projects/{project_id}/export.csv")
def export_csv(project_id: int):
    data = build_ga_tree(project_id)

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
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
