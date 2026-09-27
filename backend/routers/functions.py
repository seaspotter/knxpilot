"""
Functions tab ("Funktionen" sub-tab): assigning function types (room points)
to rooms, and special addresses ("Sonderadressen") that don't fit the
standard per-room/central schema.

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the
/hx/... endpoints below return HTML fragments from
backend/templates/functions/, and the browser swaps them in - no
client-side cache. The floors/rooms themselves belong to the building
structure tab (routers/projects.py, still classic JS) - this router only
reads them to render the rooms list.
"""
import json

from fastapi import APIRouter, Form, HTTPException, Request

from ..db import get_db
from ..models import RoomPointIn, RoomPointEditIn, SpecialItemIn
from ..templating import templates

router = APIRouter(tags=["functions"])


# --------------------------------------------------------------------------
# JSON API (kept for the building-structure tree/tests)
# --------------------------------------------------------------------------
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
# htmx fragments (backend/templates/functions/)
# --------------------------------------------------------------------------
def _point_types_by_category(db):
    categories = [dict(r) for r in db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()]
    point_types = [dict(r) for r in db.execute("SELECT * FROM point_types ORDER BY category_id, id").fetchall()]
    by_cat = {c["id"]: c["name"] for c in categories}
    return categories, [{**pt, "category_name": by_cat.get(pt["category_id"], "?")} for pt in point_types]


def _rooms_context(db, project_id):
    _, point_types = _point_types_by_category(db)
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    floor_list = []
    for f in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (f["id"],)).fetchall()
        room_list = []
        for r in rooms:
            room_list.append({**dict(r), "points": _room_points(db, r["id"], point_types)})
        floor_list.append({**dict(f), "rooms": room_list})
    return {"project_id": project_id, "floors": floor_list, "point_types": point_types}


def _room_points(db, room_id, point_types):
    by_id = {pt["id"]: pt for pt in point_types}
    points = db.execute("SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room_id,)).fetchall()
    grouped = []
    seen = {}
    for p in points:
        pt = by_id.get(p["point_type_id"])
        entry = {"id": p["id"], "label": p["label"], "has_bwm": bool(p["has_bwm"]), "point_type_id": p["point_type_id"]}
        key = p["point_type_id"]
        if key not in seen:
            seen[key] = {"point_type": pt, "points": []}
            grouped.append(seen[key])
        seen[key]["points"].append(entry)
    return grouped


def _room(request, db, room_id, project_id, editing_point=None):
    _, point_types = _point_types_by_category(db)
    room = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not room:
        raise HTTPException(404, "Room not found")
    return templates.TemplateResponse(request, "functions/_room.html", {
        "room": {**dict(room), "points": _room_points(db, room_id, point_types)},
        "point_types": point_types, "project_id": project_id, "editing_point": editing_point,
    })


@router.get("/hx/projects/{project_id}/functions")
def hx_tab(request: Request, project_id: int):
    with get_db() as db:
        return templates.TemplateResponse(request, "functions/tab.html", _rooms_context(db, project_id))


@router.post("/hx/rooms/{room_id}/points")
def hx_add_point(request: Request, room_id: int, point_type_id: int = Form(...),
                  label: str = Form(""), quantity: int = Form(1), has_bwm: bool = Form(False)):
    with get_db() as db:
        room = db.execute("SELECT r.*, f.project_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=?",
                           (room_id,)).fetchone()
        if not room:
            raise HTTPException(404, "Room not found")
        add_room_point(room_id, RoomPointIn(point_type_id=point_type_id, label=label.strip(),
                                             quantity=quantity, has_bwm=has_bwm))
        return _room(request, db, room_id, room["project_id"])


@router.get("/hx/room-points/{rp_id}/edit")
def hx_edit_point_form(request: Request, rp_id: int):
    with get_db() as db:
        point = db.execute(
            "SELECT rp.*, r.floor_id, f.project_id FROM room_points rp "
            "JOIN rooms r ON rp.room_id = r.id JOIN floors f ON r.floor_id = f.id WHERE rp.id=?", (rp_id,)
        ).fetchone()
        if not point:
            raise HTTPException(404, "Room point not found")
        return _room(request, db, point["room_id"], point["project_id"], editing_point=dict(point))


@router.get("/hx/rooms/{room_id}/cancel-edit")
def hx_cancel_edit(request: Request, room_id: int):
    with get_db() as db:
        room = db.execute("SELECT r.*, f.project_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=?",
                           (room_id,)).fetchone()
        if not room:
            raise HTTPException(404, "Room not found")
        return _room(request, db, room_id, room["project_id"])


@router.put("/hx/room-points/{rp_id}")
def hx_update_point(request: Request, rp_id: int, point_type_id: int = Form(...),
                     label: str = Form(""), has_bwm: bool = Form(False)):
    with get_db() as db:
        point = db.execute(
            "SELECT rp.*, r.floor_id, f.project_id FROM room_points rp "
            "JOIN rooms r ON rp.room_id = r.id JOIN floors f ON r.floor_id = f.id WHERE rp.id=?", (rp_id,)
        ).fetchone()
        if not point:
            raise HTTPException(404, "Room point not found")
        update_room_point(rp_id, RoomPointEditIn(point_type_id=point_type_id, label=label.strip(), has_bwm=has_bwm))
        return _room(request, db, point["room_id"], point["project_id"])


@router.delete("/hx/room-points/{rp_id}")
def hx_delete_point(request: Request, rp_id: int):
    with get_db() as db:
        point = db.execute(
            "SELECT rp.*, r.floor_id, f.project_id FROM room_points rp "
            "JOIN rooms r ON rp.room_id = r.id JOIN floors f ON r.floor_id = f.id WHERE rp.id=?", (rp_id,)
        ).fetchone()
        if not point:
            raise HTTPException(404, "Room point not found")
        db.execute("DELETE FROM room_points WHERE id=?", (rp_id,))
        return _room(request, db, point["room_id"], point["project_id"])


def _special_addresses_context(db, project_id):
    categories, _ = _point_types_by_category(db)
    floors = db.execute("SELECT id, name FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    rows = db.execute(
        "SELECT * FROM special_items WHERE project_id=? ORDER BY category_id, order_idx", (project_id,)
    ).fetchall()
    by_cat = {c["id"]: c["name"] for c in categories}
    specials = [
        {
            "id": r["id"], "name": r["name"], "location": r["location"],
            "category_name": by_cat.get(r["category_id"], "?"),
            "suffixes": json.loads(r["suffixes_json"]),
        }
        for r in rows
    ]
    return {"project_id": project_id, "categories": categories, "floors": [dict(f) for f in floors], "specials": specials}


@router.get("/hx/projects/{project_id}/special-addresses")
def hx_special_addresses(request: Request, project_id: int):
    with get_db() as db:
        return templates.TemplateResponse(request, "functions/_special_addresses.html", _special_addresses_context(db, project_id))


@router.post("/hx/projects/{project_id}/special-addresses")
def hx_create_special(request: Request, project_id: int, category_id: int = Form(...), location: str = Form(...),
                       name: str = Form(...), suffix: list[str] = Form([]), dpt: list[str] = Form([])):
    from ..models import Suffix
    suffixes = [Suffix(suffix=s.strip(), dpt=d.strip()) for s, d in zip(suffix, dpt) if s.strip()]
    with get_db() as db:
        if name.strip() and suffixes:
            add_special(project_id, SpecialItemIn(category_id=category_id, location=location,
                                                    name=name.strip(), suffixes=suffixes))
        return templates.TemplateResponse(request, "functions/_special_addresses.html", _special_addresses_context(db, project_id))


@router.delete("/hx/special-addresses/{special_id}")
def hx_delete_special(request: Request, special_id: int):
    with get_db() as db:
        row = db.execute("SELECT project_id FROM special_items WHERE id=?", (special_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Special address not found")
        db.execute("DELETE FROM special_items WHERE id=?", (special_id,))
        return templates.TemplateResponse(request, "functions/_special_addresses.html", _special_addresses_context(db, row["project_id"]))
