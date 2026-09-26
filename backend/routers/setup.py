"""Categories / Point types / Central templates / Company profile ("Setup" tab).

The six settings pages that live on the company_profile row (company,
specification, documentation, email, time tracking, backup) are rendered
server-side with htmx: templates in backend/templates/setup/, /hx/setup/...
endpoints at the end of this file. Each page saves only its own fields
(SETTINGS_SECTIONS). The JSON company-profile endpoints stay for the header
branding/timer settings (setup.js) and the tests.
"""
import io
import json
import sqlite3
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..backup import list_local_backups, list_nextcloud_backups, run_backup_now
from ..db import get_db
from ..templating import client_zone, templates
from ..models import PointTypeIn, CentralTemplateIn, CompanyProfileIn, CategoryRenameIn
from ..utils import content_disposition

router = APIRouter(tags=["setup"])


def _json_download(payload, filename):
    buf = io.StringIO()
    buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.get("/api/company-profile")
def get_company_profile():
    with get_db() as db:
        r = db.execute("SELECT * FROM company_profile WHERE id=1").fetchone()
        return {
            "id": r["id"], "name": r["name"], "address": r["address"], "email": r["email"],
            "website": r["website"], "phone": r["phone"], "logo_data_url": r["logo_data_url"],
            "show_on_pdf": bool(r["show_on_pdf"]), "specification_preamble": r["specification_preamble"],
            "specification_include_preamble": bool(r["specification_include_preamble"]),
            "specification_include_structure": bool(r["specification_include_structure"]),
            "specification_include_device_list": bool(r["specification_include_device_list"]),
            "documentation_include_devices_per_room": bool(r["documentation_include_devices_per_room"]),
            "documentation_include_group_addresses": bool(r["documentation_include_group_addresses"]),
            "documentation_include_circuit_list": bool(r["documentation_include_circuit_list"]),
            "documentation_include_distribution_boards": bool(r["documentation_include_distribution_boards"]),
            "documentation_include_clarification_list": bool(r["documentation_include_clarification_list"]),
            "documentation_include_function_checklist": bool(r["documentation_include_function_checklist"]),
            "documentation_include_handover_checklist": bool(r["documentation_include_handover_checklist"]),
            "documentation_include_manuals": bool(r["documentation_include_manuals"]),
            "backup_enabled": bool(r["backup_enabled"]),
            "backup_interval_hours": r["backup_interval_hours"],
            "backup_retention_count": r["backup_retention_count"],
            "backup_local_enabled": bool(r["backup_local_enabled"]),
            "backup_local_path": r["backup_local_path"],
            "backup_nextcloud_enabled": bool(r["backup_nextcloud_enabled"]),
            "backup_nextcloud_url": r["backup_nextcloud_url"],
            "backup_nextcloud_username": r["backup_nextcloud_username"],
            "backup_nextcloud_password": r["backup_nextcloud_password"],
            "backup_last_run_at": r["backup_last_run_at"],
            "backup_last_run_status": r["backup_last_run_status"],
            "smtp_enabled": bool(r["smtp_enabled"]),
            "smtp_host": r["smtp_host"],
            "smtp_port": r["smtp_port"],
            "smtp_encryption": r["smtp_encryption"],
            "smtp_username": r["smtp_username"],
            "smtp_password": r["smtp_password"],
            "smtp_from_email": r["smtp_from_email"],
            "smtp_cc_self_default": bool(r["smtp_cc_self_default"]),
            "time_tracking_enabled": bool(r["time_tracking_enabled"]),
            "time_tracking_rounding_minutes": r["time_tracking_rounding_minutes"],
        }


@router.put("/api/company-profile")
def update_company_profile(cp: CompanyProfileIn):
    if cp.time_tracking_rounding_minutes not in (1, 15, 30):
        raise HTTPException(400, "Rundung muss 1, 15 oder 30 Minuten sein")
    with get_db() as db:
        db.execute(
            "UPDATE company_profile SET name=?, address=?, email=?, website=?, phone=?, "
            "logo_data_url=?, show_on_pdf=?, specification_preamble=?, "
            "specification_include_preamble=?, "
            "specification_include_structure=?, specification_include_device_list=?, "
            "documentation_include_devices_per_room=?, "
            "documentation_include_group_addresses=?, documentation_include_circuit_list=?, "
            "documentation_include_distribution_boards=?, documentation_include_clarification_list=?, "
            "documentation_include_function_checklist=?, documentation_include_handover_checklist=?, "
            "documentation_include_manuals=?, "
            "backup_enabled=?, backup_interval_hours=?, backup_retention_count=?, "
            "backup_local_enabled=?, backup_local_path=?, "
            "backup_nextcloud_enabled=?, backup_nextcloud_url=?, "
            "backup_nextcloud_username=?, backup_nextcloud_password=?, "
            "smtp_enabled=?, smtp_host=?, smtp_port=?, smtp_encryption=?, "
            "smtp_username=?, smtp_password=?, smtp_from_email=?, smtp_cc_self_default=?, "
            "time_tracking_enabled=?, time_tracking_rounding_minutes=? WHERE id=1",
            (cp.name, cp.address, cp.email, cp.website, cp.phone, cp.logo_data_url,
             int(cp.show_on_pdf), cp.specification_preamble,
             int(cp.specification_include_preamble),
             int(cp.specification_include_structure), int(cp.specification_include_device_list),
             int(cp.documentation_include_devices_per_room),
             int(cp.documentation_include_group_addresses), int(cp.documentation_include_circuit_list),
             int(cp.documentation_include_distribution_boards), int(cp.documentation_include_clarification_list),
             int(cp.documentation_include_function_checklist), int(cp.documentation_include_handover_checklist),
             int(cp.documentation_include_manuals),
             int(cp.backup_enabled), cp.backup_interval_hours, cp.backup_retention_count,
             int(cp.backup_local_enabled), cp.backup_local_path,
             int(cp.backup_nextcloud_enabled), cp.backup_nextcloud_url,
             cp.backup_nextcloud_username, cp.backup_nextcloud_password,
             int(cp.smtp_enabled), cp.smtp_host, cp.smtp_port, cp.smtp_encryption,
             cp.smtp_username, cp.smtp_password, cp.smtp_from_email, int(cp.smtp_cc_self_default),
             int(cp.time_tracking_enabled), cp.time_tracking_rounding_minutes),
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


# ---------- htmx: settings pages on the company_profile row ----------
# Fields each settings page saves - (column, kind); a checkbox missing from
# the submitted form means "off". Every page only ever writes its own
# columns, so saving one page can't overwrite what's typed on another.
SETTINGS_SECTIONS = {
    "company": [("name", "text"), ("address", "text"), ("phone", "text"), ("email", "text"), ("website", "text"),
                ("logo_data_url", "text"), ("show_on_pdf", "bool")],
    "specification": [("specification_preamble", "text"), ("specification_include_preamble", "bool"),
                      ("specification_include_structure", "bool"), ("specification_include_device_list", "bool")],
    "documentation": [(c, "bool") for c in (
        "documentation_include_function_checklist", "documentation_include_handover_checklist",
        "documentation_include_manuals", "documentation_include_devices_per_room",
        "documentation_include_group_addresses", "documentation_include_circuit_list",
        "documentation_include_distribution_boards", "documentation_include_clarification_list")],
    "email": [("smtp_enabled", "bool"), ("smtp_host", "text"), ("smtp_port", "int"), ("smtp_encryption", "text"),
              ("smtp_username", "text"), ("smtp_password", "secret"), ("smtp_from_email", "text"),
              ("smtp_cc_self_default", "bool")],
    "time-tracking": [("time_tracking_enabled", "bool"), ("time_tracking_rounding_minutes", "int")],
    "backup": [("backup_enabled", "bool"), ("backup_interval_hours", "int"), ("backup_retention_count", "int"),
               ("backup_local_enabled", "bool"), ("backup_local_path", "text"), ("backup_nextcloud_enabled", "bool"),
               ("backup_nextcloud_url", "text"), ("backup_nextcloud_username", "text"),
               ("backup_nextcloud_password", "secret")],
}


def _company(db):
    return dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())


def _validate(values):
    if "time_tracking_rounding_minutes" in values and values["time_tracking_rounding_minutes"] not in (1, 15, 30):
        raise HTTPException(400, "Rundung muss 1, 15 oder 30 Minuten sein")
    for col in ("backup_interval_hours", "backup_retention_count"):
        if col in values and values[col] < 1:
            raise HTTPException(400, "Intervall und Aufbewahrung müssen mindestens 1 sein")
    if "smtp_port" in values and not 1 <= values["smtp_port"] <= 65535:
        raise HTTPException(400, "Ungültiger SMTP-Port")
    if values.get("smtp_encryption", "starttls") not in ("starttls", "ssl", "none"):
        raise HTTPException(400, "Unbekannte Verschlüsselung")


def _section_context(request, db, section):
    c = _company(db)
    context = {"c": c, "section": section}
    if section == "backup" and c["backup_last_run_at"]:
        when = datetime.fromisoformat(c["backup_last_run_at"]).astimezone(client_zone(request))
        context["last_run"] = f"{when:%d.%m.%Y %H:%M}"
    return context


def _render_section(request, db, section, toast=None, level="success"):
    response = templates.TemplateResponse(request, f"setup/{section.replace('-', '_')}.html",
                                          _section_context(request, db, section))
    events = {"company-profile-changed": True}   # header logo/name, timer settings (setup.js)
    if toast:
        events["show-toast"] = {"message": toast, "level": level}
    response.headers["HX-Trigger"] = json.dumps(events)
    return response


@router.get("/hx/setup/{section}")
def hx_settings_page(request: Request, section: str):
    if section not in SETTINGS_SECTIONS:
        raise HTTPException(404, "Unbekannter Bereich")
    with get_db() as db:
        return templates.TemplateResponse(request, f"setup/{section.replace('-', '_')}.html",
                                          _section_context(request, db, section))


@router.post("/hx/setup/{section}")
async def hx_save_settings(request: Request, section: str):
    if section not in SETTINGS_SECTIONS:
        raise HTTPException(404, "Unbekannter Bereich")
    form = await request.form()
    values = {}
    for col, kind in SETTINGS_SECTIONS[section]:
        raw = form.get(col)
        if kind == "bool":
            values[col] = int(raw is not None)
        elif kind == "int":
            try:
                values[col] = int(raw)
            except (TypeError, ValueError):
                raise HTTPException(400, "Bitte eine ganze Zahl eingeben")
        else:
            values[col] = (raw or "").strip() if kind == "text" else (raw or "")
    _validate(values)
    with get_db() as db:
        db.execute(f"UPDATE company_profile SET {', '.join(f'{c}=?' for c in values)} WHERE id=1", list(values.values()))
        return _render_section(request, db, section, toast="Gespeichert.")


@router.post("/hx/setup/backup/run")
def hx_backup_now(request: Request):
    """"Jetzt sichern" - same as the scheduled backup, then the page with the
    new status line; the result also as a toast."""
    with get_db() as db:
        result = run_backup_now(db)
        detail = "; ".join(f"{k}: {v}" for k, v in result["results"].items())
        return _render_section(request, db, "backup",
                               toast="Sicherung erfolgreich." if result["ok"] else f"Sicherung fehlgeschlagen: {detail}",
                               level="success" if result["ok"] else "error")


@router.get("/hx/setup/backup/files")
def hx_backup_files(request: Request):
    """The existing backups (loaded separately - listing Nextcloud can take a moment)."""
    with get_db() as db:
        c = _company(db)
    files = [{**f, "source": "local"} for f in (list_local_backups(c["backup_local_path"]) if c["backup_local_enabled"] else [])]
    nextcloud_error = None
    if c["backup_nextcloud_enabled"]:
        try:
            files += [{**f, "source": "nextcloud"} for f in list_nextcloud_backups(
                c["backup_nextcloud_url"], c["backup_nextcloud_username"], c["backup_nextcloud_password"])]
        except Exception as e:
            nextcloud_error = str(e)
    zone = client_zone(request)
    for f in files:
        size = f.get("size") or 0
        f["size_text"] = next((f"{size / 1024 ** i:.1f} {u}" for i, u in ((3, "GB"), (2, "MB"), (1, "KB")) if size >= 1024 ** i),
                              f"{size} B") if size else ""
        f["modified_text"] = ""
        if f.get("modified_at"):
            try:
                f["modified_text"] = f"{datetime.fromisoformat(f['modified_at'].replace('Z', '+00:00')).astimezone(zone):%d.%m.%Y %H:%M}"
            except ValueError:
                f["modified_text"] = f["modified_at"]
    files.sort(key=lambda f: f["filename"], reverse=True)
    return templates.TemplateResponse(request, "setup/_backup_files.html",
                                      {"files": files, "nextcloud_error": nextcloud_error})
