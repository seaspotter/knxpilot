"""
Klärungsliste sub-tab: per-project list of open questions/tasks/notes for
site visits, optionally tied to a room or a specific room point. Internal
only - does not appear in the Pflichtenheft export.
"""
from fastapi import APIRouter

from ..db import get_db
from ..models import KlaerungIn

router = APIRouter(tags=["klaerungsliste"])


@router.get("/api/projects/{project_id}/klaerungen")
def list_klaerungen(project_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT k.*, r.name AS room_name, rp.label AS point_label "
            "FROM klaerungen k "
            "LEFT JOIN rooms r ON k.room_id = r.id "
            "LEFT JOIN room_points rp ON k.room_point_id = rp.id "
            "WHERE k.project_id=? ORDER BY k.room_id IS NULL DESC, k.order_idx",
            (project_id,),
        ).fetchall()
        return [
            {
                "id": r["id"], "room_id": r["room_id"], "room_point_id": r["room_point_id"],
                "room_name": r["room_name"], "point_label": r["point_label"],
                "text": r["text"], "typ": r["typ"], "status": r["status"], "antwort": r["antwort"],
            }
            for r in rows
        ]


@router.post("/api/projects/{project_id}/klaerungen")
def add_klaerung(project_id: int, k: KlaerungIn):
    with get_db() as db:
        (count,) = db.execute(
            "SELECT COUNT(*) FROM klaerungen WHERE project_id=?", (project_id,)
        ).fetchone()
        cur = db.execute(
            "INSERT INTO klaerungen (project_id, room_id, room_point_id, text, typ, status, antwort, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, k.room_id, k.room_point_id, k.text, k.typ, k.status, k.antwort, count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/klaerungen/{k_id}")
def update_klaerung(k_id: int, k: KlaerungIn):
    with get_db() as db:
        db.execute(
            "UPDATE klaerungen SET room_id=?, room_point_id=?, text=?, typ=?, status=?, antwort=? WHERE id=?",
            (k.room_id, k.room_point_id, k.text, k.typ, k.status, k.antwort, k_id),
        )
    return {"ok": True}


@router.delete("/api/klaerungen/{k_id}")
def delete_klaerung(k_id: int):
    with get_db() as db:
        db.execute("DELETE FROM klaerungen WHERE id=?", (k_id,))
    return {"ok": True}
