"""
Device catalog tab ("Geräte Katalog"): the global catalog of device types
shared across all projects (actuators, sensors, weather stations, operating
elements, ...; channel info only applies to the "Aktor" group), plus each
device's curated manual URL (sub-tab "Handbücher").

Both sub-tabs are rendered server-side with htmx (templates in
backend/templates/device_catalog/, /hx/device-catalog... endpoints at the
end of this file). The JSON endpoints stay for the pickers in other tabs
(ACTOR_TYPES cache in device_catalog.js), the JSON import/export with its
preview, and the tests.
"""
import io
import json

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from ..db import get_db, load_bundled_actor_type_defaults
from ..templating import templates
from ..models import ActorTypeIn, ManualUrlIn

router = APIRouter(tags=["device-catalog"])


def _upsert_actor_types(db, actor_types):
    """Upserts by (manufacturer, model): updates group/description/channel info if that
    combination already exists, otherwise inserts a new device type. Shared by the
    manual JSON import and the "import bundled defaults" action below.

    manual_url is deliberately handled differently from every other field:
    the bundled docs/templates/geraete-katalog_*.json files (and most
    hand-written supplier catalogs) simply don't have this KNXpilot-only,
    user-curated field, so it's only written on UPDATE when the incoming
    record actually includes a "manual_url" key - otherwise a re-import
    (e.g. "Standard-Katalog importieren" to pick up newly added models)
    would silently wipe every manual URL the user has already curated.
    A user's own catalog export *does* include the key (see
    export_actor_types_json below), so restoring/duplicating a full
    catalog backup still round-trips it correctly."""
    imported = 0
    updated = 0
    for at in actor_types:
        manufacturer = at.get("manufacturer", "")
        model = at.get("model", "")
        existing = db.execute(
            "SELECT id FROM actor_types WHERE manufacturer=? AND model=?", (manufacturer, model)
        ).fetchone()
        if existing:
            if "manual_url" in at:
                db.execute(
                    "UPDATE actor_types SET group_name=?, description=?, channel_type=?, "
                    "channel_count=?, width_te=?, manual_url=? WHERE id=?",
                    (at.get("group_name", "Aktor"), at.get("description", ""),
                     at.get("channel_type", ""), at.get("channel_count"), at.get("width_te"),
                     at.get("manual_url", ""), existing["id"]),
                )
            else:
                db.execute(
                    "UPDATE actor_types SET group_name=?, description=?, channel_type=?, channel_count=?, width_te=? WHERE id=?",
                    (at.get("group_name", "Aktor"), at.get("description", ""),
                     at.get("channel_type", ""), at.get("channel_count"), at.get("width_te"), existing["id"]),
                )
            updated += 1
        else:
            db.execute(
                "INSERT INTO actor_types (manufacturer, model, group_name, description, channel_type, channel_count, width_te, manual_url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (manufacturer, model, at.get("group_name", "Aktor"), at.get("description", ""),
                 at.get("channel_type", ""), at.get("channel_count"), at.get("width_te"), at.get("manual_url", "")),
            )
            imported += 1
    return imported, updated


@router.get("/api/actor-types")
def list_actor_types():
    with get_db() as db:
        rows = db.execute("SELECT * FROM actor_types ORDER BY group_name, id").fetchall()
        return [
            {
                "id": r["id"], "manufacturer": r["manufacturer"], "model": r["model"],
                "group_name": r["group_name"], "description": r["description"],
                "channel_type": r["channel_type"], "channel_count": r["channel_count"],
                "width_te": r["width_te"], "manual_url": r["manual_url"],
            }
            for r in rows
        ]


@router.post("/api/actor-types")
def create_actor_type(at: ActorTypeIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO actor_types (manufacturer, model, group_name, description, channel_type, channel_count, width_te, manual_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at.manufacturer, at.model, at.group_name, at.description, at.channel_type, at.channel_count,
             at.width_te, at.manual_url),
        )
        return {"id": cur.lastrowid}


@router.put("/api/actor-types/{at_id}")
def update_actor_type(at_id: int, at: ActorTypeIn):
    with get_db() as db:
        db.execute(
            "UPDATE actor_types SET manufacturer=?, model=?, group_name=?, description=?, "
            "channel_type=?, channel_count=?, width_te=?, manual_url=? WHERE id=?",
            (at.manufacturer, at.model, at.group_name, at.description, at.channel_type, at.channel_count,
             at.width_te, at.manual_url, at_id),
        )
    return {"ok": True}


@router.put("/api/actor-types/{at_id}/manual-url")
def update_actor_type_manual_url(at_id: int, body: ManualUrlIn):
    """A single-field update, used by the Handbücher sub-tab's compact
    inline-edit list - so saving one device's URL doesn't need to resend
    the rest of that device's (possibly not even loaded there) fields."""
    with get_db() as db:
        db.execute("UPDATE actor_types SET manual_url=? WHERE id=?", (body.manual_url, at_id))
    return {"ok": True}


@router.delete("/api/actor-types/{at_id}")
def delete_actor_type(at_id: int):
    with get_db() as db:
        db.execute("DELETE FROM actor_types WHERE id=?", (at_id,))
    return {"ok": True}


@router.delete("/api/actor-types")
def clear_actor_types():
    """Bulk-clears the catalog for starting over with your own (e.g. after
    importing several supplier JSON files and wanting to drop the seeded
    starter catalog). Only deletes types not referenced by any project's
    Geräteplanung/Abgangsliste - those are skipped, not force-deleted, since
    that would silently orphan real project data."""
    with get_db() as db:
        (total,) = db.execute("SELECT COUNT(*) FROM actor_types").fetchone()
        db.execute(
            "DELETE FROM actor_types WHERE id NOT IN ("
            "SELECT device_type_id FROM room_devices "
            "UNION SELECT device_type_id FROM floor_devices "
            "UNION SELECT actor_type_id FROM actor_instances)"
        )
        (remaining,) = db.execute("SELECT COUNT(*) FROM actor_types").fetchone()
    return {"deleted": total - remaining, "skipped_in_use": remaining}


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
                    "width_te": r["width_te"], "manual_url": r["manual_url"],
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


_CATALOG_FIELDS = [("group_name", "Gruppe"), ("description", "Beschreibung"), ("channel_type", "Type"),
                   ("channel_count", "Kanäle"), ("width_te", "TE"), ("manual_url", "Handbuch-Link")]


def _catalog_import_diff(db, actor_types):
    """What an import would change, field by field, before anything is
    written - mirrors _upsert_actor_types() exactly (incl. manual_url only
    counting when the incoming record has that key)."""
    new, changed, unchanged = [], [], 0
    for at in actor_types:
        name = " ".join(p for p in (at.get("manufacturer", ""), at.get("model", "")) if p) or "?"
        existing = db.execute(
            "SELECT * FROM actor_types WHERE manufacturer=? AND model=?", (at.get("manufacturer", ""), at.get("model", ""))
        ).fetchone()
        if not existing:
            new.append(name)
            continue
        diffs = []
        for field, label in _CATALOG_FIELDS:
            if field == "manual_url" and field not in at:
                continue
            default = "Aktor" if field == "group_name" else ("" if field not in ("channel_count", "width_te") else None)
            old, incoming = existing[field], at.get(field, default)
            if (old or None) != (incoming or None):
                diffs.append({"field": label, "old": old, "new": incoming})
        if diffs:
            changed.append({"device": name, "changes": diffs})
        else:
            unchanged += 1
    return {"new": new, "changed": changed, "unchanged": unchanged}


@router.post("/api/actor-types/import-json/preview")
def preview_import_actor_types_json(payload: dict):
    with get_db() as db:
        return _catalog_import_diff(db, payload.get("actor_types", []))


@router.post("/api/actor-types/import-defaults/preview")
def preview_import_default_actor_types():
    with get_db() as db:
        return _catalog_import_diff(db, load_bundled_actor_type_defaults())


@router.post("/api/actor-types/import-json")
def import_actor_types_json(payload: dict):
    with get_db() as db:
        imported, updated = _upsert_actor_types(db, payload.get("actor_types", []))
        return {"imported": imported, "updated": updated}


@router.post("/api/actor-types/import-defaults")
def import_default_actor_types():
    """Re-imports every bundled docs/templates/geraete-katalog_*.json file (the same
    ones a fresh install seeds from), using the same upsert-by-(manufacturer, model)
    merge as a manual JSON import. Opt-in only, unlike the old startup-backfill
    behaviour this replaces - a device you've deliberately deleted stays deleted
    unless you click this yourself."""
    with get_db() as db:
        imported, updated = _upsert_actor_types(db, load_bundled_actor_type_defaults())
        return {"imported": imported, "updated": updated}


# ---------- htmx fragments (backend/templates/device_catalog/) ----------
KNOWN_GROUPS = ["Aktor", "Sensor", "Wetterstation", "Bedienelement", "Sonstiges"]


def _grouped(q, fields):
    """Devices matching the search `q` (in the given fields), grouped by
    group name, groups sorted - as [(group, [device, ...]), ...]."""
    q = (q or "").strip().lower()
    devices = [d for d in list_actor_types()
               if not q or any(q in (d.get(f) or "").lower() for f in fields)]
    groups = {}
    for d in devices:
        groups.setdefault(d["group_name"] or "Sonstiges", []).append(d)
    return sorted(groups.items()), len(devices)


def _catalog(request, q="", editing=None, toast=None):
    groups, shown = _grouped(q, ("manufacturer", "model", "group_name", "description", "channel_type"))
    response = templates.TemplateResponse(request, "device_catalog/catalog.html", {
        "groups": groups, "shown": shown, "total": len(list_actor_types()), "q": q,
        "editing": editing, "known_groups": KNOWN_GROUPS})
    events = {"catalog-changed": True}   # refreshes the ACTOR_TYPES cache (device_catalog.js)
    if toast:
        events["show-toast"] = {"message": toast, "level": "success"}
    response.headers["HX-Trigger"] = json.dumps(events)
    return response


@router.get("/hx/device-catalog")
def hx_catalog(request: Request, q: str = ""):
    return _catalog(request, q)


@router.get("/hx/device-catalog/list")
def hx_catalog_list(request: Request, q: str = ""):
    groups, shown = _grouped(q, ("manufacturer", "model", "group_name", "description", "channel_type"))
    return templates.TemplateResponse(request, "device_catalog/_list.html", {
        "groups": groups, "shown": shown, "total": len(list_actor_types()), "q": q})


@router.get("/hx/device-catalog/{at_id}/edit")
def hx_edit(request: Request, at_id: int, q: str = ""):
    editing = next((d for d in list_actor_types() if d["id"] == at_id), None)
    if not editing:
        raise HTTPException(404, "Gerät nicht gefunden")
    return _catalog(request, q, editing=editing)


async def _device_from_form(request, existing=None):
    """Form -> ActorTypeIn. The group comes from the select, or the custom
    text field for "Andere"; type/channels only count for "Aktor". The
    manual URL is curated on the other sub-tab, so an edit keeps it."""
    form = await request.form()
    group = form.get("group_name") or "Aktor"
    if group == "__custom__":
        group = (form.get("group_custom") or "").strip() or "Sonstiges"
    is_actuator = group == "Aktor"
    model = (form.get("model") or "").strip()
    channel_type = (form.get("channel_type") or "").strip() if is_actuator else ""
    if not model:
        raise HTTPException(400, "Modell ist erforderlich")
    if is_actuator and not channel_type:
        raise HTTPException(400, 'Type ist für die Gruppe "Aktor" erforderlich')

    def number(name, default=None):
        value = (form.get(name) or "").strip()
        try:
            return int(value) if value else default
        except ValueError:
            raise HTTPException(400, "Bitte eine ganze Zahl eingeben")
    return ActorTypeIn(
        manufacturer=(form.get("manufacturer") or "").strip(), model=model, group_name=group,
        description=(form.get("description") or "").strip(), channel_type=channel_type,
        channel_count=number("channel_count", 1) if is_actuator else None, width_te=number("width_te"),
        manual_url=existing["manual_url"] if existing else ""), form.get("q") or ""


@router.post("/hx/device-catalog")
async def hx_create(request: Request):
    device, q = await _device_from_form(request)
    create_actor_type(device)
    return _catalog(request, q, toast="Gerät gespeichert.")


@router.put("/hx/device-catalog/{at_id}")
async def hx_update(request: Request, at_id: int):
    existing = next((d for d in list_actor_types() if d["id"] == at_id), None)
    if not existing:
        raise HTTPException(404, "Gerät nicht gefunden")
    device, q = await _device_from_form(request, existing)
    update_actor_type(at_id, device)
    return _catalog(request, q, toast="Gerät gespeichert.")


@router.delete("/hx/device-catalog/{at_id}")
def hx_delete(request: Request, at_id: int, q: str = ""):
    with get_db() as db:
        in_use = db.execute(
            "SELECT 1 FROM room_devices WHERE device_type_id=? UNION SELECT 1 FROM floor_devices WHERE device_type_id=? "
            "UNION SELECT 1 FROM actor_instances WHERE actor_type_id=?", (at_id, at_id, at_id)).fetchone()
    if in_use:
        raise HTTPException(400, "Dieses Gerät wird in einem Projekt verwendet (Geräteplanung oder Abgangsliste) und kann nicht gelöscht werden")
    delete_actor_type(at_id)
    return _catalog(request, q)


@router.delete("/hx/device-catalog")
def hx_clear(request: Request):
    result = clear_actor_types()
    skipped = f", {result['skipped_in_use']} in Verwendung übersprungen" if result["skipped_in_use"] else ""
    return _catalog(request, toast=f"{result['deleted']} gelöscht{skipped}.")


@router.get("/hx/device-catalog/manuals")
def hx_manuals(request: Request, q: str = ""):
    groups, shown = _grouped(q, ("manufacturer", "model", "group_name"))
    return templates.TemplateResponse(request, "device_catalog/manuals.html", {"groups": groups, "q": q})


@router.get("/hx/device-catalog/manuals/list")
def hx_manuals_list(request: Request, q: str = ""):
    groups, shown = _grouped(q, ("manufacturer", "model", "group_name"))
    return templates.TemplateResponse(request, "device_catalog/_manuals_list.html", {"groups": groups, "q": q})


@router.put("/hx/device-catalog/{at_id}/manual-url")
async def hx_manual_url(request: Request, at_id: int):
    """Saved on change, no re-render (keeps focus while tabbing through the list)."""
    update_actor_type_manual_url(at_id, ManualUrlIn(manual_url=((await request.form()).get("manual_url") or "").strip()))
    response = Response(status_code=200)
    response.headers["HX-Trigger"] = json.dumps({"catalog-changed": True})
    return response
