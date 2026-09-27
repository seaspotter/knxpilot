"""
Per-project JSON transfer: the "Sichern (JSON)" download, "Wiederherstellen
aus JSON-Sicherung" and "Duplizieren" (see routers/projects.py) - separate
from the whole-database backup in backup.py.

Everything is referenced by NAME or by POSITION, never by internal id, so a
payload can be restored on another install as long as the same catalog
entries exist there:
  - point types / categories / central templates by name,
  - devices (actor_types) by manufacturer + model,
  - KNX lines by their "Bereich.Linie" address,
  - floors, rooms and points by their position in the payload
    (floor index, [floor, room], [floor, room, point]),
  - actuators by their position in payload["actors"].
Anything that doesn't match on the target install is skipped and reported
(never silently guessed at).

Two modes:
  - "backup" (export-json / import-json): the complete project - planning
    data plus on-site results (checklist ticks, signatures), Klärungen, the
    last ETS export snapshot, project files and fetched manuals.
  - "duplicate": the planning data only (structure, functions, specials,
    lines, actuators + channel assignments, planned devices, "Nicht
    bestellen" flags, Verteiler) - a copy for a similar house starts
    untested, unsigned, never exported to ETS, without the original's
    Klärungen or files.
Zeiterfassung entries are never part of either (internal data, see
routers/time_tracking.py).
"""
import base64
import json

from fastapi import HTTPException

PAYLOAD_FORMAT = "knx-ga-project-v1.2"


def _b64(data):
    return base64.b64encode(data).decode("ascii") if data is not None else None


def _unb64(text):
    return base64.b64decode(text) if text else b""


def build_project_payload(db, project_id, mode="backup"):
    project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(404, "Project not found")
    full = mode == "backup"

    categories = {r["id"]: r["name"] for r in db.execute("SELECT * FROM categories").fetchall()}
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}
    actor_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
    templates = {r["id"]: dict(r) for r in db.execute("SELECT * FROM central_templates").fetchall()}
    line_rows = db.execute("SELECT * FROM knx_lines WHERE project_id=? ORDER BY area, line", (project_id,)).fetchall()
    line_addr = {r["id"]: f"{r['area']}.{r['line']}" for r in line_rows}

    def device_ref(type_id):
        at = actor_types.get(type_id)
        return {"manufacturer": at["manufacturer"], "model": at["model"]} if at else None

    def devices_out(rows):
        out = []
        for d in rows:
            ref = device_ref(d["device_type_id"])
            if ref:
                out.append({**ref, "quantity": d["quantity"], "note": d["note"], "physical_address": d["physical_address"]})
        return out

    floor_ref, room_ref, point_ref = {}, {}, {}  # db id -> payload position
    floors_out = []
    for f_idx, floor in enumerate(db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()):
        floor_ref[floor["id"]] = f_idx
        rooms_out = []
        for r_idx, room in enumerate(db.execute(
            "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
        ).fetchall()):
            room_ref[room["id"]] = [f_idx, r_idx]
            points_out = []
            for point in db.execute(
                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
            ).fetchall():
                pt = point_types.get(point["point_type_id"])
                if not pt:
                    continue
                point_ref[point["id"]] = [f_idx, r_idx, len(points_out)]
                points_out.append({
                    "point_type_name": pt["name"],
                    "category_name": categories.get(pt["category_id"], ""),
                    "label": point["label"],
                    "has_bwm": bool(point["has_bwm"]),
                })
            rooms_out.append({
                "name": room["name"], "line": line_addr.get(room["line_id"]), "points": points_out,
                "devices": devices_out(db.execute(
                    "SELECT * FROM room_devices WHERE room_id=? ORDER BY order_idx", (room["id"],)).fetchall()),
            })
        floors_out.append({
            "name": floor["name"], "is_outdoor": bool(floor["is_outdoor"]),
            "line": line_addr.get(floor["line_id"]), "rooms": rooms_out,
            "devices": devices_out(db.execute(
                "SELECT * FROM floor_devices WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()),
        })

    specials_out = []
    for s in db.execute(
        "SELECT * FROM special_items WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall():
        location = s["location"]
        if location != "central" and location.isdigit() and int(location) in floor_ref:
            location = f"floor:{floor_ref[int(location)]}"
        specials_out.append({
            "category_name": categories.get(s["category_id"], ""),
            "location": location,
            "name": s["name"],
            "suffixes": json.loads(s["suffixes_json"]),
        })

    actor_ref, actors_out = {}, []
    for a in db.execute(
        "SELECT * FROM actor_instances WHERE project_id=? ORDER BY order_idx, id", (project_id,)
    ).fetchall():
        ref = device_ref(a["actor_type_id"])
        if not ref:
            continue
        actor_ref[a["id"]] = len(actors_out)
        actors_out.append({
            **ref, "floor": floor_ref.get(a["floor_id"]), "location_label": a["location_label"],
            "physical_address": a["physical_address"], "line": line_addr.get(a["line_id"]),
        })

    assignments_out = [
        {"point": point_ref[c["room_point_id"]], "channel_seq": c["channel_seq"],
         "actor": actor_ref[c["actor_instance_id"]], "channel_letter": c["channel_letter"]}
        for c in db.execute("SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)).fetchall()
        if c["room_point_id"] in point_ref and c["actor_instance_id"] in actor_ref
    ]

    order_flags_out = [
        {**device_ref(f["device_type_id"]), "not_ordering": bool(f["not_ordering"])}
        for f in db.execute("SELECT * FROM device_order_flags WHERE project_id=?", (project_id,)).fetchall()
        if device_ref(f["device_type_id"])
    ]

    distribution_boards_out = []
    for board in db.execute("SELECT * FROM distribution_boards WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall():
        items = []
        for it in db.execute(
            "SELECT * FROM distribution_board_items WHERE distribution_board_id=? ORDER BY row_idx, position_idx", (board["id"],)
        ).fetchall():
            if it["item_type"] == "device" and it["actor_instance_id"] not in actor_ref:
                continue
            items.append({
                "row_idx": it["row_idx"], "position_idx": it["position_idx"], "item_type": it["item_type"],
                "label": it["label"], "width_te": it["width_te"], "actor": actor_ref.get(it["actor_instance_id"]),
            })
        distribution_boards_out.append({
            "name": board["name"], "row_count": board["row_count"], "floor": floor_ref.get(board["floor_id"]),
            "room": room_ref.get(board["room_id"]), "items": items,
        })

    payload = {
        "format": PAYLOAD_FORMAT,
        "mode": mode,
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
        "actors": actors_out,
        "channel_assignments": assignments_out,
        "device_order_flags": order_flags_out,
        "distribution_boards": distribution_boards_out,
    }
    if not full:
        return payload

    payload["clarifications"] = [
        {"room": room_ref.get(c["room_id"]), "point": point_ref.get(c["room_point_id"]), "text": c["text"],
         "type": c["type"], "status": c["status"], "answer": c["answer"], "created_at": c["created_at"]}
        for c in db.execute("SELECT * FROM clarifications WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    ]

    checklist_out = []
    for c in db.execute("SELECT * FROM checklist_status WHERE project_id=?", (project_id,)).fetchall():
        entry = {"status": c["status"], "note": c["note"], "updated_at": c["updated_at"]}
        kind, _, ref = c["item_key"].partition(":")
        if kind == "room_point":
            if not ref.isdigit() or int(ref) not in point_ref:
                continue  # point deleted since - an orphaned row
            entry["point"] = point_ref[int(ref)]
        elif kind == "central":
            t = templates.get(int(ref)) if ref.isdigit() else None
            if not t:
                continue
            entry["central"] = {"category_name": categories.get(t["category_id"], ""), "name": t["name"], "scope": t["scope"]}
        else:
            entry["key"] = c["item_key"]  # e.g. "uebergabe:<slug>" - install-independent already
        checklist_out.append(entry)
    payload["checklist"] = checklist_out

    payload["signatures"] = [
        {"role": s["role"], "image": _b64(s["image"]), "signed_at": s["signed_at"]}
        for s in db.execute("SELECT * FROM project_signatures WHERE project_id=?", (project_id,)).fetchall()
    ]
    snap = db.execute("SELECT * FROM ga_export_snapshots WHERE project_id=?", (project_id,)).fetchone()
    payload["ga_export_snapshot"] = {"exported_at": snap["exported_at"], "data": snap["data"]} if snap else None
    payload["files"] = [
        {"filename": f["filename"], "content_type": f["content_type"], "size_bytes": f["size_bytes"],
         "data": _b64(f["data"]), "uploaded_at": f["uploaded_at"]}
        for f in db.execute("SELECT * FROM project_files WHERE project_id=? ORDER BY id", (project_id,)).fetchall()
    ]
    payload["manuals"] = [
        {**(device_ref(m["device_type_id"]) or {}), "device_name": m["device_name"], "content_type": m["content_type"],
         "size_bytes": m["size_bytes"], "data": _b64(m["data"]), "fetched_at": m["fetched_at"]}
        for m in db.execute("SELECT * FROM project_manuals WHERE project_id=? ORDER BY id", (project_id,)).fetchall()
        if device_ref(m["device_type_id"])
    ]
    return payload


def insert_project_from_payload(db, payload, forced_name=None):
    """Recreates a project from a build_project_payload() payload (any
    version - older backups simply lack the newer sections). If forced_name
    is given (duplicate), it's used as-is (caller already made sure it's
    unique); otherwise an existing project with the same name gets
    "<name> (imported)" instead of being overwritten."""
    name = forced_name if forced_name is not None else payload.get("project_name", "Imported Project")
    if forced_name is None:
        if db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone():
            name = f"{name} (imported)"

    categories_by_name = {r["name"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
    point_types_by_name = {
        (r["category_id"], r["name"]): r["id"] for r in db.execute("SELECT * FROM point_types").fetchall()
    }
    actor_types_by_name = {
        (r["manufacturer"], r["model"]): r["id"] for r in db.execute("SELECT * FROM actor_types").fetchall()
    }
    templates_by_name = {
        (r["category_id"], r["name"], r["scope"]): r["id"] for r in db.execute("SELECT * FROM central_templates").fetchall()
    }
    skipped = []

    def device_type(ref, context):
        type_id = actor_types_by_name.get((ref.get("manufacturer"), ref.get("model")))
        if not type_id:
            skipped.append(f"{context}: {ref.get('manufacturer', '')} {ref.get('model', '')} (nicht im Geräte Katalog)")
        return type_id

    cur = db.execute(
        "INSERT INTO projects (name, location, customer, status, comment, order_number, "
        "email, additional_recipients) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, payload.get("location", ""), payload.get("customer", ""), payload.get("status", ""),
         payload.get("comment", ""), payload.get("order_number", ""), payload.get("email", ""),
         payload.get("additional_recipients", "")),
    )
    project_id = cur.lastrowid

    line_ids = {}  # "Bereich.Linie" -> new knx_lines id
    for line in payload.get("lines", []):
        lcur = db.execute("INSERT INTO knx_lines (project_id, area, line, name) VALUES (?, ?, ?, ?)",
                          (project_id, int(line["area"]), int(line["line"]), line.get("name", "")))
        line_ids[f"{int(line['area'])}.{int(line['line'])}"] = lcur.lastrowid

    def insert_devices(table, owner_col, owner_id, devices, context):
        for d_idx, d in enumerate(devices):
            type_id = device_type(d, context)
            if type_id:
                db.execute(
                    f"INSERT INTO {table} ({owner_col}, device_type_id, quantity, note, physical_address, order_idx) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (owner_id, type_id, d.get("quantity", 1), d.get("note", ""), d.get("physical_address", ""), d_idx),
                )

    floor_map, room_map, point_map = {}, {}, {}  # payload position -> new id
    for f_idx, floor in enumerate(payload.get("floors", [])):
        fcur = db.execute(
            "INSERT INTO floors (project_id, name, order_idx, is_outdoor, line_id) VALUES (?, ?, ?, ?, ?)",
            (project_id, floor["name"], f_idx, int(floor.get("is_outdoor", False)), line_ids.get(floor.get("line"))),
        )
        floor_id = floor_map[f_idx] = fcur.lastrowid
        insert_devices("floor_devices", "floor_id", floor_id, floor.get("devices", []), floor["name"])
        for r_idx, room in enumerate(floor.get("rooms", [])):
            rcur = db.execute(
                "INSERT INTO rooms (floor_id, name, order_idx, line_id) VALUES (?, ?, ?, ?)",
                (floor_id, room["name"], r_idx, line_ids.get(room.get("line"))),
            )
            room_id = room_map[(f_idx, r_idx)] = rcur.lastrowid
            for p_idx, point in enumerate(room.get("points", [])):
                cat_id = categories_by_name.get(point.get("category_name"))
                pt_id = point_types_by_name.get((cat_id, point.get("point_type_name")))
                if not pt_id:
                    skipped.append(f"{room['name']}: {point.get('point_type_name')}")
                    continue
                pcur = db.execute(
                    "INSERT INTO room_points (room_id, point_type_id, label, order_idx, has_bwm) VALUES (?, ?, ?, ?, ?)",
                    (room_id, pt_id, point.get("label", ""), p_idx, int(point.get("has_bwm", False))),
                )
                point_map[(f_idx, r_idx, p_idx)] = pcur.lastrowid
            insert_devices("room_devices", "room_id", room_id, room.get("devices", []), room["name"])

    def room_of(ref):
        return room_map.get(tuple(ref)) if ref else None

    def point_of(ref):
        return point_map.get(tuple(ref)) if ref else None

    for s_idx, special in enumerate(payload.get("specials", [])):
        cat_id = categories_by_name.get(special.get("category_name"))
        if not cat_id:
            skipped.append(f"special: {special.get('name')}")
            continue
        location = special.get("location", "central")
        if isinstance(location, str) and location.startswith("floor:"):
            location = str(floor_map.get(int(location.split(":", 1)[1]), "central"))
        db.execute(
            "INSERT INTO special_items (project_id, category_id, location, name, suffixes_json, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, cat_id, location, special.get("name", ""), json.dumps(special.get("suffixes", [])), s_idx),
        )

    actor_map = {}  # payload position -> new actor_instances id
    for a_idx, a in enumerate(payload.get("actors", [])):
        type_id = device_type(a, "Aktor")
        if not type_id:
            continue
        acur = db.execute(
            "INSERT INTO actor_instances (project_id, actor_type_id, floor_id, location_label, physical_address, "
            "order_idx, line_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, type_id, floor_map.get(a.get("floor")), a.get("location_label", ""),
             a.get("physical_address", ""), a_idx, line_ids.get(a.get("line"))),
        )
        actor_map[a_idx] = acur.lastrowid

    for c in payload.get("channel_assignments", []):
        point_id, actor_id = point_of(c.get("point")), actor_map.get(c.get("actor"))
        if point_id and actor_id:
            db.execute(
                "INSERT INTO channel_assignments (project_id, room_point_id, channel_seq, actor_instance_id, channel_letter) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, point_id, c.get("channel_seq", 0), actor_id, c["channel_letter"]),
            )

    for f in payload.get("device_order_flags", []):
        type_id = actor_types_by_name.get((f.get("manufacturer"), f.get("model")))
        if type_id:
            db.execute("INSERT OR IGNORE INTO device_order_flags (project_id, device_type_id, not_ordering) VALUES (?, ?, ?)",
                       (project_id, type_id, int(f.get("not_ordering", False))))

    # "distribution_boards"/"clarifications" - accept the pre-rename payload
    # keys ("verteiler"/"klaerungen" with "typ"/"antwort" fields) too, so a
    # backup exported before this rename still restores.
    for b_idx, board in enumerate(payload.get("distribution_boards", payload.get("verteiler", []))):
        room_id = room_of(board.get("room"))
        floor_id = floor_map.get(board["room"][0]) if room_id else floor_map.get(board.get("floor"))
        bcur = db.execute(
            "INSERT INTO distribution_boards (project_id, floor_id, room_id, name, row_count, order_idx) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, floor_id, room_id, board.get("name", ""), board.get("row_count", 4), b_idx),
        )
        for it in board.get("items", []):
            actor_id = actor_map.get(it.get("actor"))
            if it.get("item_type") == "device" and not actor_id:
                continue
            db.execute(
                "INSERT INTO distribution_board_items (distribution_board_id, row_idx, position_idx, item_type, label, width_te, actor_instance_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bcur.lastrowid, it["row_idx"], it["position_idx"], it["item_type"], it.get("label", ""),
                 it.get("width_te"), actor_id),
            )

    for c_idx, c in enumerate(payload.get("clarifications", payload.get("klaerungen", []))):
        db.execute(
            "INSERT INTO clarifications (project_id, room_id, room_point_id, text, type, status, answer, order_idx, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
            (project_id, room_of(c.get("room")), point_of(c.get("point")), c.get("text", ""),
             c.get("type", c.get("typ", "Frage")), c.get("status", "offen"), c.get("answer", c.get("antwort", "")),
             c_idx, c.get("created_at")),
        )

    for c in payload.get("checklist", []):
        if "point" in c:
            point_id = point_of(c["point"])
            key = f"room_point:{point_id}" if point_id else None
        elif "central" in c:
            t = c["central"]
            template_id = templates_by_name.get((categories_by_name.get(t.get("category_name")), t.get("name"), t.get("scope")))
            key = f"central:{template_id}" if template_id else None
        else:
            key = c.get("key")
        if key:
            db.execute(
                "INSERT INTO checklist_status (project_id, item_key, status, note, updated_at) "
                "VALUES (?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP)) ON CONFLICT(project_id, item_key) DO NOTHING",
                (project_id, key, c.get("status", ""), c.get("note", ""), c.get("updated_at")),
            )

    for s in payload.get("signatures", []):
        db.execute("INSERT INTO project_signatures (project_id, role, image, signed_at) VALUES (?, ?, ?, ?) "
                   "ON CONFLICT(project_id, role) DO NOTHING",
                   (project_id, s["role"], _unb64(s.get("image")), s["signed_at"]))

    snap = payload.get("ga_export_snapshot")
    if snap:
        db.execute("INSERT INTO ga_export_snapshots (project_id, exported_at, data) VALUES (?, ?, ?)",
                   (project_id, snap["exported_at"], snap["data"]))

    for f in payload.get("files", []):
        data = _unb64(f.get("data"))
        db.execute(
            "INSERT INTO project_files (project_id, filename, content_type, size_bytes, data, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
            (project_id, f["filename"], f.get("content_type", "application/octet-stream"), len(data), data, f.get("uploaded_at")),
        )

    for m in payload.get("manuals", []):
        type_id = actor_types_by_name.get((m.get("manufacturer"), m.get("model")))
        if not type_id:
            skipped.append(f"Handbuch: {m.get('device_name', '')}")
            continue
        data = _unb64(m.get("data"))
        db.execute(
            "INSERT INTO project_manuals (project_id, device_type_id, device_name, content_type, size_bytes, data, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP)) ON CONFLICT(project_id, device_type_id) DO NOTHING",
            (project_id, type_id, m.get("device_name", ""), m.get("content_type", "application/pdf"), len(data), data,
             m.get("fetched_at")),
        )

    return {"id": project_id, "name": name, "skipped": skipped}
