"""Categories / Point types / Central templates ("Setup" tab - rarely touched)."""
import json

from fastapi import APIRouter

from ..db import get_db
from ..models import PointTypeIn, CentralTemplateIn

router = APIRouter(tags=["setup"])


@router.get("/api/categories")
def list_categories():
    with get_db() as db:
        rows = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        return [dict(r) for r in rows]


@router.get("/api/point-types")
def list_point_types():
    with get_db() as db:
        rows = db.execute("SELECT * FROM point_types ORDER BY category_id, id").fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "name": r["name"],
                "suffixes": json.loads(r["suffixes_json"]), "block_size": r["block_size"],
                "channel_type": r["channel_type"], "channels_needed": r["channels_needed"],
            }
            for r in rows
        ]


@router.post("/api/point-types")
def create_point_type(pt: PointTypeIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO point_types (category_id, name, suffixes_json, block_size, channel_type, channels_needed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pt.category_id, pt.name, json.dumps([s.dict() for s in pt.suffixes]), pt.block_size,
             pt.channel_type, pt.channels_needed),
        )
        return {"id": cur.lastrowid}


@router.put("/api/point-types/{pt_id}")
def update_point_type(pt_id: int, pt: PointTypeIn):
    with get_db() as db:
        db.execute(
            "UPDATE point_types SET category_id=?, name=?, suffixes_json=?, block_size=?, "
            "channel_type=?, channels_needed=? WHERE id=?",
            (pt.category_id, pt.name, json.dumps([s.dict() for s in pt.suffixes]), pt.block_size,
             pt.channel_type, pt.channels_needed, pt_id),
        )
    return {"ok": True}


@router.delete("/api/point-types/{pt_id}")
def delete_point_type(pt_id: int):
    with get_db() as db:
        db.execute("DELETE FROM point_types WHERE id=?", (pt_id,))
    return {"ok": True}


@router.get("/api/central-templates")
def list_central_templates():
    with get_db() as db:
        rows = db.execute("SELECT * FROM central_templates ORDER BY category_id, order_idx").fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "name": r["name"],
                "scope": r["scope"], "suffixes": json.loads(r["suffixes_json"]),
                "order_idx": r["order_idx"], "skip_outdoor_floors": bool(r["skip_outdoor_floors"]),
                "block_size": r["block_size"], "trigger_count": r["trigger_count"],
            }
            for r in rows
        ]


@router.post("/api/central-templates")
def create_central_template(ct: CentralTemplateIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO central_templates "
            "(category_id, name, scope, suffixes_json, order_idx, skip_outdoor_floors, block_size, trigger_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ct.category_id, ct.name, ct.scope, json.dumps([s.dict() for s in ct.suffixes]), ct.order_idx,
             int(ct.skip_outdoor_floors), ct.block_size, ct.trigger_count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/central-templates/{ct_id}")
def update_central_template(ct_id: int, ct: CentralTemplateIn):
    with get_db() as db:
        db.execute(
            "UPDATE central_templates SET category_id=?, name=?, scope=?, suffixes_json=?, order_idx=?, "
            "skip_outdoor_floors=?, block_size=?, trigger_count=? WHERE id=?",
            (ct.category_id, ct.name, ct.scope, json.dumps([s.dict() for s in ct.suffixes]), ct.order_idx,
             int(ct.skip_outdoor_floors), ct.block_size, ct.trigger_count, ct_id),
        )
    return {"ok": True}


@router.delete("/api/central-templates/{ct_id}")
def delete_central_template(ct_id: int):
    with get_db() as db:
        db.execute("DELETE FROM central_templates WHERE id=?", (ct_id,))
    return {"ok": True}
