"""
Verteilerplanung tab: a simple visual DIN-rail cabinet layout per Geschoss.
Fixed 12-TE-wide rows; each row holds RCD/LS-Schalter blocks (simple labeled/
sized placeholders, no link to specific circuits) and/or actor instances
already placed via the Abgangsliste tab (their width comes live from
actor_types.width_te).
"""
from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import VerteilerIn, VerteilerUpdateIn, VerteilerItemIn, VerteilerItemMoveIn
from ..utils import join_parts

router = APIRouter(tags=["verteiler"])

ROW_WIDTH_TE = 12
DEFAULT_WIDTH_TE = {"rcd": 4, "ls": 1}


def _serialize_verteiler(db, row):
    items = db.execute(
        "SELECT vi.*, "
        "ai.location_label as ai_location_label, ai.physical_address as ai_physical_address, "
        "at.manufacturer as at_manufacturer, at.model as at_model, at.width_te as at_width_te "
        "FROM verteiler_items vi "
        "LEFT JOIN actor_instances ai ON vi.actor_instance_id = ai.id "
        "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
        "WHERE vi.verteiler_id=? ORDER BY vi.row_idx, vi.position_idx",
        (row["id"],),
    ).fetchall()

    rows = [[] for _ in range(row["row_count"])]
    for it in items:
        if it["item_type"] == "device":
            width_te = it["at_width_te"]
            label = it["ai_location_label"] or join_parts(it["at_manufacturer"], it["at_model"]) or "?"
            sublabel = it["ai_physical_address"]
        else:
            width_te = it["width_te"]
            label = it["label"] or ("RCD" if it["item_type"] == "rcd" else "LS")
            sublabel = ""
        entry = {
            "id": it["id"], "item_type": it["item_type"], "width_te": width_te,
            "label": label, "sublabel": sublabel, "actor_instance_id": it["actor_instance_id"],
        }
        if 0 <= it["row_idx"] < len(rows):
            rows[it["row_idx"]].append(entry)

    return {
        "id": row["id"], "floor_id": row["floor_id"], "name": row["name"],
        "row_count": row["row_count"], "row_width_te": ROW_WIDTH_TE, "rows": rows,
    }


@router.get("/api/projects/{project_id}/verteiler")
def list_verteiler(project_id: int):
    with get_db() as db:
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        rows = db.execute(
            "SELECT * FROM verteiler WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = []
        for row in rows:
            v = _serialize_verteiler(db, row)
            v["floor_name"] = floors.get(row["floor_id"], "")
            result.append(v)
        return result


@router.post("/api/projects/{project_id}/verteiler")
def create_verteiler(project_id: int, v: VerteilerIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM verteiler WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO verteiler (project_id, floor_id, name, row_count, order_idx) VALUES (?, ?, ?, ?, ?)",
            (project_id, v.floor_id, v.name, max(1, v.row_count), count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/verteiler/{verteiler_id}")
def update_verteiler(verteiler_id: int, v: VerteilerUpdateIn):
    with get_db() as db:
        (max_row,) = db.execute(
            "SELECT COALESCE(MAX(row_idx), -1) FROM verteiler_items WHERE verteiler_id=?", (verteiler_id,)
        ).fetchone()
        if v.row_count < max_row + 1:
            raise HTTPException(400, f"Reihe {max_row + 1} enthält noch Elemente - erst leeren oder umziehen")
        db.execute(
            "UPDATE verteiler SET name=?, row_count=? WHERE id=?",
            (v.name, max(1, v.row_count), verteiler_id),
        )
    return {"ok": True}


@router.delete("/api/verteiler/{verteiler_id}")
def delete_verteiler(verteiler_id: int):
    with get_db() as db:
        db.execute("DELETE FROM verteiler WHERE id=?", (verteiler_id,))
    return {"ok": True}


@router.post("/api/verteiler/{verteiler_id}/items")
def add_verteiler_item(verteiler_id: int, item: VerteilerItemIn):
    with get_db() as db:
        v = db.execute("SELECT * FROM verteiler WHERE id=?", (verteiler_id,)).fetchone()
        if not v:
            raise HTTPException(404, "Verteiler not found")
        if item.row_idx < 0 or item.row_idx >= v["row_count"]:
            raise HTTPException(400, "Ungültige Reihe")

        if item.item_type == "device":
            if not item.actor_instance_id:
                raise HTTPException(400, "Gerät fehlt")
            ai = db.execute(
                "SELECT ai.*, at.width_te as at_width_te FROM actor_instances ai "
                "JOIN actor_types at ON ai.actor_type_id = at.id WHERE ai.id=?",
                (item.actor_instance_id,),
            ).fetchone()
            if not ai:
                raise HTTPException(404, "Gerät nicht gefunden")
            if ai["at_width_te"] is None:
                raise HTTPException(400, "Diesem Gerät fehlt eine TE-Breite im Geräte-Katalog")
            already = db.execute(
                "SELECT 1 FROM verteiler_items WHERE actor_instance_id=?", (item.actor_instance_id,)
            ).fetchone()
            if already:
                raise HTTPException(400, "Dieses Gerät ist bereits in einem Verteiler platziert")
            width_te = ai["at_width_te"]
            label = ""
        elif item.item_type in ("rcd", "ls"):
            width_te = item.width_te or DEFAULT_WIDTH_TE[item.item_type]
            label = item.label
        else:
            raise HTTPException(400, "Unbekannter item_type")

        (used,) = db.execute(
            "SELECT COALESCE(SUM(CASE WHEN vi.item_type='device' THEN at.width_te ELSE vi.width_te END), 0) "
            "FROM verteiler_items vi "
            "LEFT JOIN actor_instances ai ON vi.actor_instance_id = ai.id "
            "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE vi.verteiler_id=? AND vi.row_idx=?",
            (verteiler_id, item.row_idx),
        ).fetchone()
        free = ROW_WIDTH_TE - used
        if width_te > free:
            raise HTTPException(400, f"Reihe ist voll (nur noch {free} TE frei)")

        (next_pos,) = db.execute(
            "SELECT COALESCE(MAX(position_idx) + 1, 0) FROM verteiler_items WHERE verteiler_id=? AND row_idx=?",
            (verteiler_id, item.row_idx),
        ).fetchone()
        cur = db.execute(
            "INSERT INTO verteiler_items (verteiler_id, row_idx, position_idx, item_type, label, width_te, actor_instance_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (verteiler_id, item.row_idx, next_pos, item.item_type, label,
             width_te if item.item_type in ("rcd", "ls") else None, item.actor_instance_id),
        )
        return {"id": cur.lastrowid}


@router.delete("/api/verteiler-items/{item_id}")
def delete_verteiler_item(item_id: int):
    with get_db() as db:
        db.execute("DELETE FROM verteiler_items WHERE id=?", (item_id,))
    return {"ok": True}


@router.post("/api/verteiler-items/{item_id}/move")
def move_verteiler_item(item_id: int, m: VerteilerItemMoveIn):
    with get_db() as db:
        it = db.execute("SELECT * FROM verteiler_items WHERE id=?", (item_id,)).fetchone()
        if not it:
            raise HTTPException(404, "Item not found")
        op = "<" if m.direction == "left" else ">"
        order = "DESC" if m.direction == "left" else "ASC"
        neighbor = db.execute(
            f"SELECT * FROM verteiler_items WHERE verteiler_id=? AND row_idx=? AND position_idx {op} ? "
            f"ORDER BY position_idx {order} LIMIT 1",
            (it["verteiler_id"], it["row_idx"], it["position_idx"]),
        ).fetchone()
        if not neighbor:
            return {"ok": True}
        db.execute("UPDATE verteiler_items SET position_idx=? WHERE id=?", (neighbor["position_idx"], it["id"]))
        db.execute("UPDATE verteiler_items SET position_idx=? WHERE id=?", (it["position_idx"], neighbor["id"]))
    return {"ok": True}
