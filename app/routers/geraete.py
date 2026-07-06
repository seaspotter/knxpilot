"""
Device Types (global catalog shared across all projects: Aktoren, Sensoren,
Wetterstation, Bedienelemente, etc. Channel info only applies to "Aktor".)
"""
import io
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..models import ActorTypeIn

router = APIRouter(tags=["geraete"])


@router.get("/api/actor-types")
def list_actor_types():
    with get_db() as db:
        rows = db.execute("SELECT * FROM actor_types ORDER BY group_name, id").fetchall()
        return [
            {
                "id": r["id"], "manufacturer": r["manufacturer"], "model": r["model"],
                "group_name": r["group_name"], "description": r["description"],
                "channel_type": r["channel_type"], "channel_count": r["channel_count"],
            }
            for r in rows
        ]


@router.post("/api/actor-types")
def create_actor_type(at: ActorTypeIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO actor_types (manufacturer, model, group_name, description, channel_type, channel_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (at.manufacturer, at.model, at.group_name, at.description, at.channel_type, at.channel_count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/actor-types/{at_id}")
def update_actor_type(at_id: int, at: ActorTypeIn):
    with get_db() as db:
        db.execute(
            "UPDATE actor_types SET manufacturer=?, model=?, group_name=?, description=?, "
            "channel_type=?, channel_count=? WHERE id=?",
            (at.manufacturer, at.model, at.group_name, at.description, at.channel_type, at.channel_count, at_id),
        )
    return {"ok": True}


@router.delete("/api/actor-types/{at_id}")
def delete_actor_type(at_id: int):
    with get_db() as db:
        db.execute("DELETE FROM actor_types WHERE id=?", (at_id,))
    return {"ok": True}


@router.get("/api/actor-types/export-json")
def export_actor_types_json():
    with get_db() as db:
        rows = db.execute("SELECT * FROM actor_types ORDER BY id").fetchall()
        payload = {
            "format": "knx-actor-types-v2",
            "actor_types": [
                {
                    "manufacturer": r["manufacturer"], "model": r["model"],
                    "group_name": r["group_name"], "description": r["description"],
                    "channel_type": r["channel_type"], "channel_count": r["channel_count"],
                }
                for r in rows
            ],
        }
        buf = io.StringIO()
        buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="geraete_katalog.json"'},
        )


@router.post("/api/actor-types/import-json")
def import_actor_types_json(payload: dict):
    """Upserts by (manufacturer, model): updates group/description/channel info if that
    combination already exists, otherwise inserts a new device type."""
    with get_db() as db:
        imported = 0
        updated = 0
        for at in payload.get("actor_types", []):
            manufacturer = at.get("manufacturer", "")
            model = at.get("model", "")
            existing = db.execute(
                "SELECT id FROM actor_types WHERE manufacturer=? AND model=?", (manufacturer, model)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE actor_types SET group_name=?, description=?, channel_type=?, channel_count=? WHERE id=?",
                    (at.get("group_name", "Aktor"), at.get("description", ""),
                     at.get("channel_type", ""), at.get("channel_count"), existing["id"]),
                )
                updated += 1
            else:
                db.execute(
                    "INSERT INTO actor_types (manufacturer, model, group_name, description, channel_type, channel_count) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (manufacturer, model, at.get("group_name", "Aktor"), at.get("description", ""),
                     at.get("channel_type", ""), at.get("channel_count")),
                )
                imported += 1
        return {"imported": imported, "updated": updated}
