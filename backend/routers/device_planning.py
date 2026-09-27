"""
Device planning tab ("Geräteplanung"): which devices (any group - sensor,
touch panel, weather station, actuator...) are planned per room or floor, a
project-wide bill of materials ("Stückliste"), the device-list PDF export
(order list), and the devices-by-room PDF export (installation reference -
every device, grouped by Geschoss/Raum).

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the
/hx/... endpoints below return HTML fragments from
backend/templates/device_planning/, and the browser swaps them in - no
client-side cache. The JSON endpoints stay for the delete-impact counts,
the physical-address auto-assignment (pa_assign.py) and the tests.
"""
from xml.sax.saxutils import escape

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table
from reportlab.lib.units import mm

from ..db import get_db
from ..models import RoomDeviceIn, RoomDeviceEditIn, DeviceOrderFlagIn
from ..pdf_design import pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response, company_header_block, company_footer_line
from ..templating import templates
from ..utils import join_parts

router = APIRouter(tags=["device-planning"])


@router.get("/api/rooms/{room_id}/devices")
def list_room_devices(room_id: int):
    with get_db() as db:
        device_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
        rows = db.execute(
            "SELECT * FROM room_devices WHERE room_id=? ORDER BY order_idx", (room_id,)
        ).fetchall()
        result = []
        for r in rows:
            dt = device_types.get(r["device_type_id"], {})
            result.append(
                {
                    "id": r["id"], "device_type_id": r["device_type_id"],
                    "device_name": join_parts(dt.get("manufacturer", ""), dt.get("model", "")) or "?",
                    "group_name": dt.get("group_name", ""),
                    "quantity": r["quantity"], "note": r["note"],
                    "physical_address": r["physical_address"],
                }
            )
        return result


@router.post("/api/rooms/{room_id}/devices")
def add_room_device(room_id: int, rd: RoomDeviceIn):
    """Each call creates `quantity` independent quantity=1 rows (one per physical
    device, so each can get its own physical_address later) - `quantity` here just
    means "how many at once", it's never stored as an aggregate count. A given
    physical_address is only applied when quantity == 1 - can't sensibly hand the
    same address to several newly-created rows."""
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM room_devices WHERE room_id=?", (room_id,)).fetchone()
        quantity = max(1, rd.quantity)
        address = rd.physical_address if quantity == 1 else ""
        first_id = None
        for i in range(quantity):
            cur = db.execute(
                "INSERT INTO room_devices (room_id, device_type_id, quantity, note, physical_address, order_idx) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (room_id, rd.device_type_id, rd.note, address, count + i),
            )
            if first_id is None:
                first_id = cur.lastrowid
        return {"id": first_id}


@router.put("/api/room-devices/{rd_id}")
def update_room_device(rd_id: int, rd: RoomDeviceEditIn):
    with get_db() as db:
        db.execute(
            "UPDATE room_devices SET note=?, physical_address=? WHERE id=?",
            (rd.note, rd.physical_address, rd_id),
        )
    return {"ok": True}


@router.delete("/api/room-devices/{rd_id}")
def delete_room_device(rd_id: int):
    with get_db() as db:
        db.execute("DELETE FROM room_devices WHERE id=?", (rd_id,))
    return {"ok": True}


# --------------------------------------------------------------------------
# Floor-level devices: a device that isn't "in" any particular room - e.g. an
# outdoor temperature sensor or a Wetterstation on the facade, on an Aussen-
# marked floor with no natural room to attach it to. Same shape/semantics as
# room_devices above, just anchored to a floor instead of a room.
# --------------------------------------------------------------------------
@router.get("/api/floors/{floor_id}/devices")
def list_floor_devices(floor_id: int):
    with get_db() as db:
        device_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
        rows = db.execute(
            "SELECT * FROM floor_devices WHERE floor_id=? ORDER BY order_idx", (floor_id,)
        ).fetchall()
        result = []
        for r in rows:
            dt = device_types.get(r["device_type_id"], {})
            result.append(
                {
                    "id": r["id"], "device_type_id": r["device_type_id"],
                    "device_name": join_parts(dt.get("manufacturer", ""), dt.get("model", "")) or "?",
                    "group_name": dt.get("group_name", ""),
                    "quantity": r["quantity"], "note": r["note"],
                    "physical_address": r["physical_address"],
                }
            )
        return result


@router.post("/api/floors/{floor_id}/devices")
def add_floor_device(floor_id: int, rd: RoomDeviceIn):
    """Same "quantity = how many blank rows at once" semantics as add_room_device."""
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM floor_devices WHERE floor_id=?", (floor_id,)).fetchone()
        quantity = max(1, rd.quantity)
        address = rd.physical_address if quantity == 1 else ""
        first_id = None
        for i in range(quantity):
            cur = db.execute(
                "INSERT INTO floor_devices (floor_id, device_type_id, quantity, note, physical_address, order_idx) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (floor_id, rd.device_type_id, rd.note, address, count + i),
            )
            if first_id is None:
                first_id = cur.lastrowid
        return {"id": first_id}


@router.put("/api/floor-devices/{fd_id}")
def update_floor_device(fd_id: int, rd: RoomDeviceEditIn):
    with get_db() as db:
        db.execute(
            "UPDATE floor_devices SET note=?, physical_address=? WHERE id=?",
            (rd.note, rd.physical_address, fd_id),
        )
    return {"ok": True}


@router.delete("/api/floor-devices/{fd_id}")
def delete_floor_device(fd_id: int):
    with get_db() as db:
        db.execute("DELETE FROM floor_devices WHERE id=?", (fd_id,))
    return {"ok": True}


@router.put("/api/projects/{project_id}/device-order-flags/{device_type_id}")
def set_device_order_flag(project_id: int, device_type_id: int, flag: DeviceOrderFlagIn):
    """Marks (or unmarks) a device type as "already have it, don't order" for this
    project only - e.g. a spare Wetterstation or Tor-Aktor left over from another
    job. Stays visible in the Stückliste, just excluded from the order table/count
    on the PDF export."""
    with get_db() as db:
        db.execute(
            "INSERT INTO device_order_flags (project_id, device_type_id, not_ordering) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id, device_type_id) DO UPDATE SET not_ordering=excluded.not_ordering",
            (project_id, device_type_id, int(flag.not_ordering)),
        )
    return {"ok": True}


@router.get("/api/projects/{project_id}/device-summary")
def device_summary(project_id: int):
    """Project-wide bill of materials: total quantity needed per device type,
    plus which rooms/floors use it - built from the room_devices planning
    list, floor_devices (room-less, e.g. outdoor devices), AND the actor
    instances already placed via the Abgangsliste tab (a device shouldn't
    need re-entering here just to show up in the overall total)."""
    with get_db() as db:
        device_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
        order_flags = {
            r["device_type_id"]: bool(r["not_ordering"])
            for r in db.execute(
                "SELECT * FROM device_order_flags WHERE project_id=?", (project_id,)
            ).fetchall()
        }
        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()

        totals = {}  # device_type_id -> {"total": int, "rooms": [...]}
        for floor in floors:
            rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
            for room in rooms:
                devices = db.execute(
                    "SELECT * FROM room_devices WHERE room_id=? ORDER BY order_idx", (room["id"],)
                ).fetchall()
                for rd in devices:
                    entry = totals.setdefault(rd["device_type_id"], {"total": 0, "rooms": []})
                    entry["total"] += rd["quantity"]
                    entry["rooms"].append(
                        {
                            "floor_name": floor["name"], "room_name": room["name"], "quantity": rd["quantity"],
                            "physical_address": rd["physical_address"],
                        }
                    )

            floor_devices = db.execute(
                "SELECT * FROM floor_devices WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
            ).fetchall()
            for fd in floor_devices:
                entry = totals.setdefault(fd["device_type_id"], {"total": 0, "rooms": []})
                entry["total"] += fd["quantity"]
                entry["rooms"].append(
                    {
                        "floor_name": floor["name"], "room_name": "(kein Raum)", "quantity": fd["quantity"],
                        "physical_address": fd["physical_address"],
                    }
                )

        actor_instances = db.execute(
            "SELECT ai.*, f.name as floor_name FROM actor_instances ai "
            "LEFT JOIN floors f ON ai.floor_id = f.id WHERE ai.project_id=?",
            (project_id,),
        ).fetchall()
        for ai in actor_instances:
            entry = totals.setdefault(ai["actor_type_id"], {"total": 0, "rooms": []})
            entry["total"] += 1
            entry["rooms"].append({
                "floor_name": ai["floor_name"] or "Ohne Geschoss",
                "room_name": ai["location_label"] or "(kein Standort)",
                "quantity": 1, "physical_address": ai["physical_address"],
            })

        result = []
        for device_type_id, entry in totals.items():
            dt = device_types.get(device_type_id, {})
            result.append(
                {
                    "device_type_id": device_type_id,
                    "manufacturer": dt.get("manufacturer", ""), "model": dt.get("model", ""),
                    "device_name": join_parts(dt.get("manufacturer", ""), dt.get("model", "")) or "?",
                    "group_name": dt.get("group_name", ""),
                    "description": dt.get("description", "") or "",
                    "total": entry["total"], "rooms": entry["rooms"],
                    "not_ordering": order_flags.get(device_type_id, False),
                    "manual_url": dt.get("manual_url", ""),
                }
            )
        # Alphabetical by device (manufacturer + model), case-insensitive -
        # "THeben" sorts with "Theben". Shared by the Stückliste, its PDF,
        # the Pflichtenheft and the Handbücher lists.
        result.sort(key=lambda r: (r["device_name"].casefold(), r["device_type_id"]))
        return result


@router.get("/api/projects/{project_id}/export-device-list.pdf")
def export_device_list_pdf(project_id: int):
    """Just the order-relevant Stückliste (Gruppe/Hersteller/Typ/Beschreibung/Anzahl) - no
    per-room breakdown, this is meant as a clean list to hand to a supplier.
    Devices marked "nicht bestellen" (see set_device_order_flag) are left out
    of the order table itself and listed separately underneath instead."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(f"Geräteliste — {project['name']}", "Bestellübersicht")
        story += build_stueckliste_story(device_summary(project_id), styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Geräteliste · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_geraeteliste.pdf",
            doc_title=f"Geräteliste {project['name']}",
            footer_center_text=company_footer_line(company),
        )


def build_stueckliste_story(summary, styles):
    """The Stückliste as it appears in every PDF - the Geräteliste (order)
    export here and the Pflichtenheft/Dokumentation (routers/specification.py)
    - so they're always identical: devices to order in a table (alphabetical,
    see device_summary), devices marked "Nicht bestellen" listed below as
    already present."""
    to_order = [s for s in summary if not s["not_ordering"]]
    already_have = [s for s in summary if s["not_ordering"]]
    heading = Paragraph("Stückliste", styles["SectionHeading"])
    table_data = [["Hersteller", "Typ", "Beschreibung", "Gruppe", "Anzahl"]]
    for s in to_order:
        table_data.append([
            _cell(v, styles) for v in
            (s["manufacturer"], s["model"], s["description"], s["group_name"], str(s["total"]))
        ])
    story = []
    if len(table_data) == 1:
        story.append(KeepTogether([heading, Paragraph("Noch keine Geräte geplant.", styles["BodyMuted"])]))
    else:
        table = Table(table_data, colWidths=[28 * mm, 38 * mm, 64 * mm, 34 * mm, 16 * mm], repeatRows=1)
        table.setStyle(pdf_table_style())
        story.append(KeepTogether([heading, table]))
    if already_have:
        story.append(Spacer(1, 4 * mm))
        text = ", ".join(f"{s['total']}× {s['device_name']}" for s in already_have)
        story.append(KeepTogether([
            Paragraph("Bereits vorhanden (nicht bestellt)", styles["SubHeading"]),
            Paragraph(escape(text), styles["BodyMuted"]),
        ]))
    return story


def _cell(text, styles):
    """Wrapping table cell - needed for the free-text Beschreibung column (a
    plain string cell would just overflow into the neighbouring column), and
    used for every body cell of the device tables so all cells of a row share
    the same vertical alignment."""
    return Paragraph(escape(text or ""), styles["TableCell"])


def _devices_by_room_rows(db, project_id):
    """Every device in the project - room_devices, floor_devices ("Ohne
    Raum"), and Abgangsliste's actor_instances (grouped by Standortbezeichnung,
    since they have no room_id) - as (floor_name, room_name, [devices]) tuples,
    device dicts shaped {manufacturer, model, group_name, description,
    physical_address}.
    Shared by the standalone Geräte-je-Raum PDF and its optional Pflichtenheft
    section, same pattern as build_distribution_boards_story/
    build_abgangsliste_story in the sibling routers."""
    rows = []
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    for floor in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        for room in rooms:
            devices = db.execute(
                "SELECT rd.*, at.manufacturer, at.model, at.group_name, at.description FROM room_devices rd "
                "JOIN actor_types at ON rd.device_type_id = at.id "
                "WHERE rd.room_id=? ORDER BY rd.order_idx",
                (room["id"],),
            ).fetchall()
            if devices:
                rows.append((floor["name"], room["name"], devices))

        floor_devices = db.execute(
            "SELECT fd.*, at.manufacturer, at.model, at.group_name, at.description FROM floor_devices fd "
            "JOIN actor_types at ON fd.device_type_id = at.id "
            "WHERE fd.floor_id=? ORDER BY fd.order_idx",
            (floor["id"],),
        ).fetchall()
        if floor_devices:
            rows.append((floor["name"], "Ohne Raum", floor_devices))

        actor_rows = db.execute(
            "SELECT ai.*, at.manufacturer, at.model, at.group_name, at.description FROM actor_instances ai "
            "JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? AND ai.floor_id=? ORDER BY ai.order_idx",
            (project_id, floor["id"]),
        ).fetchall()
        rows += _grouped_actor_rows(actor_rows, floor["name"])

    actor_no_floor = db.execute(
        "SELECT ai.*, at.manufacturer, at.model, at.group_name, at.description FROM actor_instances ai "
        "JOIN actor_types at ON ai.actor_type_id = at.id "
        "WHERE ai.project_id=? AND ai.floor_id IS NULL ORDER BY ai.order_idx",
        (project_id,),
    ).fetchall()
    rows += _grouped_actor_rows(actor_no_floor, "Ohne Geschoss")

    return rows


def _grouped_actor_rows(actor_rows, floor_name):
    """Abgangsliste actor instances grouped by Standortbezeichnung (they have
    no room_id, only a floor + free-text location) - room_devices-shaped."""
    by_label = {}
    for ai in actor_rows:
        by_label.setdefault(ai["location_label"] or "Sonstige Aktoren", []).append(ai)
    return [
        (floor_name, label, [
            {"manufacturer": ai["manufacturer"], "model": ai["model"], "group_name": ai["group_name"],
             "description": ai["description"], "physical_address": ai["physical_address"]}
            for ai in group
        ])
        for label, group in by_label.items()
    ]


def build_devices_by_room_story(db, project_id, styles):
    """One table per Raum/floor-location: Gruppe/Hersteller/Typ/Beschreibung/Adresse -
    factored out so both the standalone export and the Pflichtenheft's
    optional inclusion share one rendering."""
    rows = _devices_by_room_rows(db, project_id)
    story = []
    if not rows:
        story.append(Paragraph("Noch keine Geräte geplant.", styles["BodyMuted"]))
        return story

    current_floor = None
    for floor_name, room_name, devices in rows:
        group = []
        if floor_name != current_floor:
            if current_floor is not None:
                story.append(Spacer(1, 3 * mm))
            group.append(Paragraph(floor_name, styles["SectionHeading"]))
            current_floor = floor_name
        group.append(Paragraph(room_name, styles["RoomHeading"]))
        table_data = [["Gruppe", "Hersteller", "Typ", "Beschreibung", "Adresse"]]
        for d in devices:
            table_data.append([
                _cell(v, styles) for v in
                (d["group_name"], d["manufacturer"], d["model"], d["description"], d["physical_address"] or "—")
            ])
        table = Table(table_data, colWidths=[34 * mm, 26 * mm, 36 * mm, 60 * mm, 24 * mm], repeatRows=1)
        table.setStyle(pdf_table_style())
        group.append(table)
        # Keep the (optional floor +) room heading together with its table
        # so ReportLab never strands a heading alone at the bottom of a
        # page with the table starting on the next one - safe for a long
        # table too, KeepTogether only forces a fresh-page start for the
        # group, it doesn't stop the table itself from paginating normally
        # afterwards.
        story.append(KeepTogether(group))
        story.append(Spacer(1, 2 * mm))

    return story


@router.get("/api/projects/{project_id}/export-devices-by-room.pdf")
def export_devices_by_room_pdf(project_id: int):
    """Installation reference: every device in the project, grouped by
    Geschoss/Raum with Gruppe/Hersteller/Typ/Beschreibung/Adresse - the counterpart to
    the order-focused Geräteliste export above."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
            f"Geräte je Raum — {project['name']}", "Installationsübersicht"
        )
        story += build_devices_by_room_story(db, project_id, styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Geräte je Raum · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_geraete_je_raum.pdf",
            doc_title=f"Geräte je Raum {project['name']}",
            footer_center_text=company_footer_line(company),
        )


# --------------------------------------------------------------------------
# htmx fragments (backend/templates/device_planning/)
# --------------------------------------------------------------------------
def _actor_types_for_pickers(db):
    """Non-Aktor device types for the room/floor "add device" pickers -
    Aktoren (devices with physical channels) are placed in the Abgangsliste
    tab instead, with their own physical address there."""
    return [
        dict(r) for r in
        db.execute("SELECT * FROM actor_types WHERE group_name != 'Aktor' ORDER BY group_name, id").fetchall()
    ]


def _grouped_devices(devices):
    """devices (as returned by list_room_devices/list_floor_devices), grouped
    by catalog Gruppe into the shared rc-row layout - same look as the
    Funktionen sub-tab. Order of first appearance, not alphabetical."""
    groups = []
    by_group = {}
    for d in devices:
        key = d["group_name"] or "Sonstige"
        if key not in by_group:
            by_group[key] = {"group_name": key, "devices": []}
            groups.append(by_group[key])
        by_group[key]["devices"].append(d)
    return groups


def _floor_context(db, floor_id, editing_floor_device=None):
    floor = db.execute("SELECT * FROM floors WHERE id=?", (floor_id,)).fetchone()
    if not floor:
        raise HTTPException(404, "Floor not found")
    return {
        "floor": dict(floor), "devices": _grouped_devices(list_floor_devices(floor_id)),
        "actor_types": _actor_types_for_pickers(db), "editing_floor_device": editing_floor_device,
    }


def _room_context(db, room_id, editing_room_device=None):
    room = db.execute(
        "SELECT r.*, f.project_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=?", (room_id,)
    ).fetchone()
    if not room:
        raise HTTPException(404, "Room not found")
    return {
        "room": dict(room), "devices": _grouped_devices(list_room_devices(room_id)),
        "actor_types": _actor_types_for_pickers(db), "editing_room_device": editing_room_device,
    }


def _floor_fragment(request, db, floor_id, editing_floor_device=None, with_summary=False):
    """Renders _floor.html, targeted at #floor-devices-{{ floor.id }}. Every
    mutation (add/edit/delete) also needs the project-wide Stückliste to
    stay in sync, so those calls pass with_summary=True to append it as an
    out-of-band swap (see backend/templates/device_planning/_summary.html) -
    a plain re-render/cancel-edit doesn't change any totals."""
    ctx = _floor_context(db, floor_id, editing_floor_device)
    html = templates.get_template("device_planning/_floor.html").render(**ctx)
    if not with_summary:
        return HTMLResponse(html)
    project_id = ctx["floor"]["project_id"]
    summary_html = templates.get_template("device_planning/_summary.html").render(
        summary=device_summary(project_id), project_id=project_id, oob=True,
    )
    return HTMLResponse(html + summary_html)


def _room_fragment(request, db, room_id, editing_room_device=None, with_summary=False):
    """Same as _floor_fragment above, for a room's device list
    (#room-devices-{{ room.id }})."""
    ctx = _room_context(db, room_id, editing_room_device)
    html = templates.get_template("device_planning/_room.html").render(**ctx)
    if not with_summary:
        return HTMLResponse(html)
    project_id = ctx["room"]["project_id"]
    summary_html = templates.get_template("device_planning/_summary.html").render(
        summary=device_summary(project_id), project_id=project_id, oob=True,
    )
    return HTMLResponse(html + summary_html)


def _tab_context(db, project_id):
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    floor_list = []
    for f in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (f["id"],)).fetchall()
        floor_list.append({
            "floor": dict(f),
            "devices": _grouped_devices(list_floor_devices(f["id"])),
            "rooms": [{"room": dict(r), "devices": _grouped_devices(list_room_devices(r["id"]))} for r in rooms],
        })
    return {
        "project_id": project_id, "floors": floor_list, "actor_types": _actor_types_for_pickers(db),
        "summary": device_summary(project_id),
    }


@router.get("/hx/projects/{project_id}/device-planning")
def hx_tab(request: Request, project_id: int):
    with get_db() as db:
        return templates.TemplateResponse(request, "device_planning/tab.html", _tab_context(db, project_id))


@router.put("/hx/projects/{project_id}/device-order-flags/{device_type_id}")
def hx_set_order_flag(request: Request, project_id: int, device_type_id: int, not_ordering: bool = Form(False)):
    with get_db() as db:
        set_device_order_flag(project_id, device_type_id, DeviceOrderFlagIn(not_ordering=not_ordering))
        return templates.TemplateResponse(request, "device_planning/_summary.html",
                                           {"summary": device_summary(project_id), "project_id": project_id})


@router.post("/hx/rooms/{room_id}/devices")
def hx_add_room_device(request: Request, room_id: int, device_type_id: int = Form(...), quantity: int = Form(1),
                        note: str = Form(""), physical_address: str = Form("")):
    with get_db() as db:
        add_room_device(room_id, RoomDeviceIn(device_type_id=device_type_id, quantity=quantity,
                                               note=note.strip(), physical_address=physical_address.strip()))
        return _room_fragment(request, db, room_id, with_summary=True)


@router.get("/hx/room-devices/{rd_id}/edit")
def hx_edit_room_device_form(request: Request, rd_id: int):
    with get_db() as db:
        rd = db.execute("SELECT * FROM room_devices WHERE id=?", (rd_id,)).fetchone()
        if not rd:
            raise HTTPException(404, "Room device not found")
        return _room_fragment(request, db, rd["room_id"], editing_room_device=dict(rd))


@router.get("/hx/rooms/{room_id}/devices/cancel-edit")
def hx_cancel_edit_room_device(request: Request, room_id: int):
    with get_db() as db:
        return _room_fragment(request, db, room_id)


@router.put("/hx/room-devices/{rd_id}")
def hx_update_room_device(request: Request, rd_id: int, note: str = Form(""), physical_address: str = Form("")):
    with get_db() as db:
        rd = db.execute("SELECT * FROM room_devices WHERE id=?", (rd_id,)).fetchone()
        if not rd:
            raise HTTPException(404, "Room device not found")
        update_room_device(rd_id, RoomDeviceEditIn(note=note.strip(), physical_address=physical_address.strip()))
        return _room_fragment(request, db, rd["room_id"], with_summary=True)


@router.delete("/hx/room-devices/{rd_id}")
def hx_delete_room_device(request: Request, rd_id: int):
    with get_db() as db:
        rd = db.execute("SELECT * FROM room_devices WHERE id=?", (rd_id,)).fetchone()
        if not rd:
            raise HTTPException(404, "Room device not found")
    delete_room_device(rd_id)  # own commit-on-exit connection, must run (and commit) before the re-render below
    with get_db() as db:
        return _room_fragment(request, db, rd["room_id"], with_summary=True)


# Floor-level devices mirror the room-level ones above (same shape/semantics,
# see list_floor_devices/add_floor_device).
@router.post("/hx/floors/{floor_id}/devices")
def hx_add_floor_device(request: Request, floor_id: int, device_type_id: int = Form(...), quantity: int = Form(1),
                         note: str = Form(""), physical_address: str = Form("")):
    with get_db() as db:
        add_floor_device(floor_id, RoomDeviceIn(device_type_id=device_type_id, quantity=quantity,
                                                 note=note.strip(), physical_address=physical_address.strip()))
        return _floor_fragment(request, db, floor_id, with_summary=True)


@router.get("/hx/floor-devices/{fd_id}/edit")
def hx_edit_floor_device_form(request: Request, fd_id: int):
    with get_db() as db:
        fd = db.execute("SELECT * FROM floor_devices WHERE id=?", (fd_id,)).fetchone()
        if not fd:
            raise HTTPException(404, "Floor device not found")
        return _floor_fragment(request, db, fd["floor_id"], editing_floor_device=dict(fd))


@router.get("/hx/floors/{floor_id}/devices/cancel-edit")
def hx_cancel_edit_floor_device(request: Request, floor_id: int):
    with get_db() as db:
        return _floor_fragment(request, db, floor_id)


@router.put("/hx/floor-devices/{fd_id}")
def hx_update_floor_device(request: Request, fd_id: int, note: str = Form(""), physical_address: str = Form("")):
    with get_db() as db:
        fd = db.execute("SELECT * FROM floor_devices WHERE id=?", (fd_id,)).fetchone()
        if not fd:
            raise HTTPException(404, "Floor device not found")
        update_floor_device(fd_id, RoomDeviceEditIn(note=note.strip(), physical_address=physical_address.strip()))
        return _floor_fragment(request, db, fd["floor_id"], with_summary=True)


@router.delete("/hx/floor-devices/{fd_id}")
def hx_delete_floor_device(request: Request, fd_id: int):
    with get_db() as db:
        fd = db.execute("SELECT * FROM floor_devices WHERE id=?", (fd_id,)).fetchone()
        if not fd:
            raise HTTPException(404, "Floor device not found")
    delete_floor_device(fd_id)  # own commit-on-exit connection, must run (and commit) before the re-render below
    with get_db() as db:
        return _floor_fragment(request, db, fd["floor_id"], with_summary=True)
