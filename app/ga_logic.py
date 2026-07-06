"""
Core generation logic, shared across multiple routers:
- build_ga_tree(): the Group Address tree (used by preview, CSV/ETS export)
- get_circuits(): every physical output a project needs (used by Abgangsliste)
- get_room_functions_by_category() / get_central_functions_overview(): human-readable
  summaries used by the Pflichtenheft
"""
import json

from fastapi import HTTPException

from .db import get_db
from .utils import join_parts


def get_room_functions_by_category(db, room_id):
    """Human-readable GA functions in a room, grouped by category name - for the Pflichtenheft."""
    categories = {r["id"]: r["name"] for r in db.execute("SELECT * FROM categories").fetchall()}
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}
    points = db.execute("SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room_id,)).fetchall()
    by_category = {}
    for p in points:
        pt = point_types.get(p["point_type_id"])
        if not pt:
            continue
        cat_name = categories.get(pt["category_id"], "?")
        label = p["label"]
        desc = f"{label} ({pt['name']})" if label else pt["name"]
        if p["has_bwm"]:
            desc += " +BWM"
        by_category.setdefault(cat_name, []).append(desc)
    return by_category


CENTRAL_SCOPE_LABELS = {
    "building": "projektweit",
    "floor": "je Geschoss",
    "room_multi": "bei mehreren Punkten im Raum",
}


def get_central_functions_overview(db, project_id):
    """Human-readable summary of which central/general function templates apply,
    for categories actually used in this project - for the Pflichtenheft."""
    categories = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}

    used_category_ids = set()
    for floor in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall():
        for room in db.execute("SELECT * FROM rooms WHERE floor_id=?", (floor["id"],)).fetchall():
            for point in db.execute("SELECT * FROM room_points WHERE room_id=?", (room["id"],)).fetchall():
                pt = point_types.get(point["point_type_id"])
                if pt:
                    used_category_ids.add(pt["category_id"])
    for r in db.execute("SELECT DISTINCT category_id FROM special_items WHERE project_id=?", (project_id,)).fetchall():
        used_category_ids.add(r["category_id"])

    overview = []
    for cat in categories:
        if not cat["is_allgemein"] and cat["id"] not in used_category_ids:
            continue
        templates = db.execute(
            "SELECT * FROM central_templates WHERE category_id=? ORDER BY order_idx", (cat["id"],)
        ).fetchall()
        if not templates:
            continue
        items = []
        for t in templates:
            suffixes = json.loads(t["suffixes_json"])
            fallback = suffixes[0]["suffix"] if suffixes and suffixes[0]["suffix"] else "Funktion"
            label = t["name"] or fallback
            scope_label = CENTRAL_SCOPE_LABELS.get(t["scope"], t["scope"])
            items.append(f"{label} ({scope_label})")
        overview.append((cat["name"], items))
    return overview


def get_circuits(db, project_id):
    """
    Every physical output ("circuit") the project needs: one entry per channel a
    room_point requires (usually 1, but channels_needed can be >1 for e.g. a
    tunable-white driver needing 2 physical dimming channels).
    """
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}
    actor_instances = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_instances WHERE project_id=?", (project_id,)).fetchall()}
    actor_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
    assignments = {
        (a["room_point_id"], a["channel_seq"]): dict(a)
        for a in db.execute("SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)).fetchall()
    }

    circuits = []
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    for floor in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        for room in rooms:
            points = db.execute(
                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
            ).fetchall()
            for point in points:
                pt = point_types.get(point["point_type_id"])
                if not pt or not pt["channel_type"]:
                    continue  # this point type has no physical channel configured
                base_name = join_parts(room["name"], point["label"])
                for seq in range(pt["channels_needed"]):
                    fn_name = base_name if pt["channels_needed"] == 1 else f"{base_name} ({seq + 1})"
                    key = (point["id"], seq)
                    assignment = assignments.get(key)
                    assignment_info = None
                    if assignment:
                        ai = actor_instances.get(assignment["actor_instance_id"])
                        at = actor_types.get(ai["actor_type_id"]) if ai else None
                        assignment_info = {
                            "actor_instance_id": assignment["actor_instance_id"],
                            "channel_letter": assignment["channel_letter"],
                            "actor_name": join_parts(at.get("manufacturer", ""), at.get("model", "")) if at else "?",
                            "location_label": ai["location_label"] if ai else "",
                            "physical_address": ai["physical_address"] if ai else "",
                        }
                    circuits.append(
                        {
                            "room_point_id": point["id"], "channel_seq": seq,
                            "floor_id": floor["id"], "floor_name": floor["name"], "room_name": room["name"],
                            "function_name": fn_name, "point_type_name": pt["name"],
                            "channel_type": pt["channel_type"], "assignment": assignment_info,
                        }
                    )
    return circuits


def build_ga_tree(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        categories = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        point_types = {
            r["id"]: {
                "category_id": r["category_id"], "name": r["name"],
                "suffixes": json.loads(r["suffixes_json"]), "block_size": r["block_size"],
            }
            for r in db.execute("SELECT * FROM point_types").fetchall()
        }
        floors = db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        specials_by_cat = {}
        for r in db.execute("SELECT * FROM special_items WHERE project_id=? ORDER BY order_idx", (project_id,)):
            specials_by_cat.setdefault(r["category_id"], []).append(
                {"location": r["location"], "name": r["name"], "suffixes": json.loads(r["suffixes_json"])}
            )

        # Which categories actually have at least one point anywhere in this project?
        # Categories with no usage and no specials are skipped entirely (e.g. no Steckdosen
        # in the project -> no Steckdosen Main Group / central function generated).
        used_category_ids = set(specials_by_cat.keys())
        for floor in floors:
            for room in db.execute("SELECT * FROM rooms WHERE floor_id=?", (floor["id"],)).fetchall():
                for point in db.execute("SELECT * FROM room_points WHERE room_id=?", (room["id"],)).fetchall():
                    pt = point_types.get(point["point_type_id"])
                    if pt:
                        used_category_ids.add(pt["category_id"])

        main_groups = []
        for main_idx, cat in enumerate(categories):
            cat_id = cat["id"]

            if not cat["is_allgemein"] and cat_id not in used_category_ids:
                continue  # category unused in this project - skip its Main Group entirely

            central_templates = [
                dict(t) for t in db.execute(
                    "SELECT * FROM central_templates WHERE category_id=? ORDER BY order_idx", (cat_id,)
                ).fetchall()
            ]
            middles = []

            if cat["is_allgemein"]:
                # Each 'building' scope central template becomes its own Middle Group.
                for middle_idx, tmpl in enumerate(central_templates):
                    suffixes = json.loads(tmpl["suffixes_json"])
                    subs = [
                        {"sub": i, "name": f"{s['suffix']}", "dpt": s["dpt"]}
                        for i, s in enumerate(suffixes)
                    ]
                    middles.append({"middle": middle_idx, "name": tmpl["name"], "subs": subs})

            else:
                # Middle 0: Zentralfunktionen (building-scope + one block per floor + special 'central' items)
                central_subs = []
                sub_idx = 0
                for tmpl in central_templates:
                    suffixes = json.loads(tmpl["suffixes_json"])
                    if tmpl["scope"] == "building":
                        for s in suffixes:
                            central_subs.append({"sub": sub_idx, "name": f"{tmpl['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                            sub_idx += 1
                    elif tmpl["scope"] == "floor":
                        for floor in floors:
                            if tmpl["skip_outdoor_floors"] and floor["is_outdoor"]:
                                continue
                            for s in suffixes:
                                central_subs.append(
                                    {"sub": sub_idx, "name": f"{tmpl['name']} {floor['name']} {s['suffix']}".strip(), "dpt": s["dpt"]}
                                )
                                sub_idx += 1

                # room_multi scope: one block per room that has >= trigger_count points in this category
                room_multi_templates = [t for t in central_templates if t["scope"] == "room_multi"]
                if room_multi_templates:
                    for floor in floors:
                        rooms_here = db.execute(
                            "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
                        ).fetchall()
                        for room in rooms_here:
                            room_points_here = db.execute(
                                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
                            ).fetchall()
                            count_in_cat = sum(
                                1 for p in room_points_here
                                if point_types.get(p["point_type_id"], {}).get("category_id") == cat_id
                            )
                            for tmpl in room_multi_templates:
                                if tmpl["skip_outdoor_floors"] and floor["is_outdoor"]:
                                    continue
                                trigger = tmpl["trigger_count"] or 2
                                if count_in_cat < trigger:
                                    continue
                                suffixes = json.loads(tmpl["suffixes_json"])
                                prefix = join_parts(room["name"], tmpl["name"])
                                used = 0
                                for s in suffixes:
                                    central_subs.append(
                                        {"sub": sub_idx, "name": join_parts(prefix, s["suffix"]), "dpt": s["dpt"]}
                                    )
                                    sub_idx += 1
                                    used += 1
                                if tmpl["block_size"]:
                                    for _ in range(max(0, tmpl["block_size"] - used)):
                                        central_subs.append(
                                            {"sub": sub_idx, "name": join_parts(prefix, "res"), "dpt": ""}
                                        )
                                        sub_idx += 1

                for special in specials_by_cat.get(cat_id, []):
                    if special["location"] == "central":
                        for s in special["suffixes"]:
                            central_subs.append({"sub": sub_idx, "name": f"{special['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                            sub_idx += 1

                if central_subs:
                    middles.append({"middle": 0, "name": "Zentralfunktionen", "subs": central_subs})

                # Middle 1..n: one per floor
                for floor_pos, floor in enumerate(floors):
                    middle_idx = floor_pos + (1 if central_subs else 0)
                    rooms = db.execute(
                        "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
                    ).fetchall()
                    subs = []
                    sub_idx = 0
                    for room in rooms:
                        points = db.execute(
                            "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
                        ).fetchall()
                        for point in points:
                            pt = point_types.get(point["point_type_id"])
                            if not pt or pt["category_id"] != cat_id:
                                continue
                            label = point["label"]
                            prefix = f"{room['name']} {label}".strip() if label else room["name"]
                            point_suffixes = list(pt["suffixes"])
                            if point["has_bwm"]:
                                point_suffixes = point_suffixes + [{"suffix": "BWM", "dpt": "DPST-1-1"}]
                            used = 0
                            for s in point_suffixes:
                                if sub_idx > 255:
                                    raise HTTPException(400, f"Floor '{floor['name']}' / '{cat['name']}' exceeds 256 Sub Groups.")
                                subs.append({"sub": sub_idx, "name": f"{prefix} {s['suffix']}", "dpt": s["dpt"]})
                                sub_idx += 1
                                used += 1
                            for _ in range(max(0, pt["block_size"] - used)):
                                if sub_idx > 255:
                                    raise HTTPException(400, f"Floor '{floor['name']}' / '{cat['name']}' exceeds 256 Sub Groups.")
                                subs.append({"sub": sub_idx, "name": f"{prefix} res", "dpt": ""})
                                sub_idx += 1
                    for special in specials_by_cat.get(cat_id, []):
                        if special["location"] == str(floor["id"]):
                            for s in special["suffixes"]:
                                subs.append({"sub": sub_idx, "name": f"{special['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                                sub_idx += 1
                    if subs:
                        middles.append({"middle": middle_idx, "name": floor["name"], "subs": subs})

            if middles:
                main_groups.append({"main": main_idx, "name": cat["name"], "middles": middles})

        return {"project_name": project["name"], "main_groups": main_groups}
