"""Categories / Point types / Central templates / Company profile ("Setup" tab)."""
import io
import json
import sqlite3

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..models import PointTypeIn, CentralTemplateIn, CompanyProfileIn, CategoryRenameIn

router = APIRouter(tags=["setup"])


def _json_download(payload, filename):
    buf = io.StringIO()
    buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get("/api/categories/export-json")
def export_categories_json():
    """Names only, keyed by order_idx (= the fixed KNX main group number) -
    not a general backup/restore format like the other exports, since
    categories can't be added/removed/reordered. Re-importing this only ever
    renames the 6 existing categories back to whatever the file says."""
    with get_db() as db:
        rows = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        payload = {
            "format": "knx-categories-v1",
            "categories": [
                {"order_idx": r["order_idx"], "name": r["name"], "is_allgemein": bool(r["is_allgemein"])}
                for r in rows
            ],
        }
    return _json_download(payload, "kategorien.json")


@router.post("/api/categories/import-json")
def import_categories_json(payload: dict):
    """Renames categories by matching order_idx - never inserts, deletes, or
    reorders, since that mapping is fixed to the KNX main group numbers."""
    with get_db() as db:
        updated = 0
        skipped = 0
        for c in payload.get("categories", []):
            order_idx = c.get("order_idx")
            name = c.get("name", "")
            if order_idx is None or not name:
                skipped += 1
                continue
            try:
                cur = db.execute("UPDATE categories SET name=? WHERE order_idx=?", (name, order_idx))
            except sqlite3.IntegrityError:
                skipped += 1  # name collides with another category's current name
                continue
            if cur.rowcount:
                updated += 1
            else:
                skipped += 1
        return {"updated": updated, "skipped": skipped}


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


@router.get("/api/point-types/export-json")
def export_point_types_json():
    """References categories by order_idx (not the raw category_id, which
    could in principle differ between installs) so the file stays portable
    across any KNXpilot instance - it's a template of default/custom
    Funktionstypen, not a snapshot of one specific database's row ids."""
    with get_db() as db:
        categories = {r["id"]: r["order_idx"] for r in db.execute("SELECT * FROM categories").fetchall()}
        rows = db.execute("SELECT * FROM point_types ORDER BY category_id, id").fetchall()
        payload = {
            "format": "knx-point-types-v1",
            "point_types": [
                {
                    "category_order_idx": categories.get(r["category_id"]),
                    "name": r["name"], "suffixes": json.loads(r["suffixes_json"]),
                    "block_size": r["block_size"], "channel_type": r["channel_type"],
                    "channels_needed": r["channels_needed"],
                }
                for r in rows
            ],
        }
    return _json_download(payload, "funktionstypen.json")


@router.post("/api/point-types/import-json")
def import_point_types_json(payload: dict):
    """Upserts by (category, name) - re-importing the same file (e.g. after
    'Alle löschen') recreates everything; running it again afterwards
    updates in place instead of duplicating."""
    with get_db() as db:
        order_to_id = {r["order_idx"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
        imported = 0
        updated = 0
        skipped = 0
        for pt in payload.get("point_types", []):
            category_id = order_to_id.get(pt.get("category_order_idx"))
            name = pt.get("name", "")
            if category_id is None or not name:
                skipped += 1
                continue
            suffixes_json = json.dumps(pt.get("suffixes", []))
            existing = db.execute(
                "SELECT id FROM point_types WHERE category_id=? AND name=?", (category_id, name)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE point_types SET suffixes_json=?, block_size=?, channel_type=?, channels_needed=? "
                    "WHERE id=?",
                    (suffixes_json, pt.get("block_size", 5), pt.get("channel_type", ""),
                     pt.get("channels_needed", 1), existing["id"]),
                )
                updated += 1
            else:
                db.execute(
                    "INSERT INTO point_types (category_id, name, suffixes_json, block_size, channel_type, channels_needed) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (category_id, name, suffixes_json, pt.get("block_size", 5),
                     pt.get("channel_type", ""), pt.get("channels_needed", 1)),
                )
                imported += 1
        return {"imported": imported, "updated": updated, "skipped": skipped}


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


@router.get("/api/central-templates/export-json")
def export_central_templates_json():
    """References categories by order_idx, same portability reasoning as
    the Funktionstypen export."""
    with get_db() as db:
        categories = {r["id"]: r["order_idx"] for r in db.execute("SELECT * FROM categories").fetchall()}
        rows = db.execute("SELECT * FROM central_templates ORDER BY category_id, order_idx").fetchall()
        payload = {
            "format": "knx-central-templates-v1",
            "central_templates": [
                {
                    "category_order_idx": categories.get(r["category_id"]),
                    "name": r["name"], "scope": r["scope"], "suffixes": json.loads(r["suffixes_json"]),
                    "order_idx": r["order_idx"], "skip_outdoor_floors": bool(r["skip_outdoor_floors"]),
                    "block_size": r["block_size"], "trigger_count": r["trigger_count"],
                }
                for r in rows
            ],
        }
    return _json_download(payload, "zentral-vorlagen.json")


@router.post("/api/central-templates/import-json")
def import_central_templates_json(payload: dict):
    """Upserts by (category, name, scope) - re-importing the same file (e.g.
    after 'Alle löschen') recreates everything; running it again afterwards
    updates in place instead of duplicating."""
    with get_db() as db:
        order_to_id = {r["order_idx"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
        imported = 0
        updated = 0
        skipped = 0
        for ct in payload.get("central_templates", []):
            category_id = order_to_id.get(ct.get("category_order_idx"))
            name = ct.get("name", "")
            scope = ct.get("scope", "")
            if category_id is None or scope not in ("building", "floor", "room_multi"):
                skipped += 1
                continue
            suffixes_json = json.dumps(ct.get("suffixes", []))
            existing = db.execute(
                "SELECT id FROM central_templates WHERE category_id=? AND name=? AND scope=?",
                (category_id, name, scope),
            ).fetchone()
            values_tail = (
                suffixes_json, ct.get("order_idx", 0), int(ct.get("skip_outdoor_floors", False)),
                ct.get("block_size"), ct.get("trigger_count"),
            )
            if existing:
                db.execute(
                    "UPDATE central_templates SET suffixes_json=?, order_idx=?, skip_outdoor_floors=?, "
                    "block_size=?, trigger_count=? WHERE id=?",
                    values_tail + (existing["id"],),
                )
                updated += 1
            else:
                db.execute(
                    "INSERT INTO central_templates "
                    "(category_id, name, scope, suffixes_json, order_idx, skip_outdoor_floors, block_size, trigger_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (category_id, name, scope) + values_tail,
                )
                imported += 1
        return {"imported": imported, "updated": updated, "skipped": skipped}
