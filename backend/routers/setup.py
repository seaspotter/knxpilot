"""Categories / Point types / Central templates / Company profile ("Setup" tab)."""
import json
import sqlite3

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import PointTypeIn, CentralTemplateIn, CompanyProfileIn, CategoryRenameIn

router = APIRouter(tags=["setup"])


@router.get("/api/company-profile")
def get_company_profile():
    with get_db() as db:
        r = db.execute("SELECT * FROM company_profile WHERE id=1").fetchone()
        return {
            "id": r["id"], "name": r["name"], "address": r["address"], "email": r["email"],
            "website": r["website"], "phone": r["phone"], "logo_data_url": r["logo_data_url"],
            "show_on_pdf": bool(r["show_on_pdf"]), "pflichtenheft_preamble": r["pflichtenheft_preamble"],
            "pflichtenheft_include_vorbemerkungen": bool(r["pflichtenheft_include_vorbemerkungen"]),
            "pflichtenheft_include_struktur": bool(r["pflichtenheft_include_struktur"]),
            "pflichtenheft_include_geraeteliste": bool(r["pflichtenheft_include_geraeteliste"]),
            "pflichtenheft_include_gruppenadressen": bool(r["pflichtenheft_include_gruppenadressen"]),
            "pflichtenheft_include_abgangsliste": bool(r["pflichtenheft_include_abgangsliste"]),
            "pflichtenheft_include_klaerungsliste": bool(r["pflichtenheft_include_klaerungsliste"]),
        }


@router.put("/api/company-profile")
def update_company_profile(cp: CompanyProfileIn):
    with get_db() as db:
        db.execute(
            "UPDATE company_profile SET name=?, address=?, email=?, website=?, phone=?, "
            "logo_data_url=?, show_on_pdf=?, pflichtenheft_preamble=?, "
            "pflichtenheft_include_vorbemerkungen=?, "
            "pflichtenheft_include_struktur=?, pflichtenheft_include_geraeteliste=?, "
            "pflichtenheft_include_gruppenadressen=?, pflichtenheft_include_abgangsliste=?, "
            "pflichtenheft_include_klaerungsliste=? WHERE id=1",
            (cp.name, cp.address, cp.email, cp.website, cp.phone, cp.logo_data_url,
             int(cp.show_on_pdf), cp.pflichtenheft_preamble,
             int(cp.pflichtenheft_include_vorbemerkungen),
             int(cp.pflichtenheft_include_struktur), int(cp.pflichtenheft_include_geraeteliste),
             int(cp.pflichtenheft_include_gruppenadressen), int(cp.pflichtenheft_include_abgangsliste),
             int(cp.pflichtenheft_include_klaerungsliste)),
        )
    return {"ok": True}


@router.get("/api/categories")
def list_categories():
    with get_db() as db:
        rows = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        return [dict(r) for r in rows]


@router.put("/api/categories/{category_id}")
def rename_category(category_id: int, c: CategoryRenameIn):
    with get_db() as db:
        try:
            db.execute("UPDATE categories SET name=? WHERE id=?", (c.name, category_id))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "A category with that name already exists")
    return {"ok": True}


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


@router.delete("/api/point-types")
def clear_point_types():
    """Bulk-clears Funktionstypen for building your own set from scratch.
    Only deletes types not already assigned to a room point in some project
    - those are skipped, not force-deleted, to avoid orphaning real project
    data. Categories themselves are untouched (they stay fixed to the KNX
    main group numbers regardless)."""
    with get_db() as db:
        (total,) = db.execute("SELECT COUNT(*) FROM point_types").fetchone()
        db.execute(
            "DELETE FROM point_types WHERE id NOT IN (SELECT point_type_id FROM room_points)"
        )
        (remaining,) = db.execute("SELECT COUNT(*) FROM point_types").fetchone()
    return {"deleted": total - remaining, "skipped_in_use": remaining}


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


@router.delete("/api/central-templates")
def clear_central_templates():
    """Bulk-clears every Zentral-/Allgemeinfunktions-Vorlage across all
    categories, for building your own from scratch. Unlike Funktionstypen,
    nothing else references these by id (they're regenerated fresh into the
    GA tree at preview/export time, never stored per-project), so this is
    a plain, unconditional delete - no "in use" cases to skip."""
    with get_db() as db:
        (total,) = db.execute("SELECT COUNT(*) FROM central_templates").fetchone()
        db.execute("DELETE FROM central_templates")
    return {"deleted": total}
