"""
Geräteplanung tab: which devices (any group - sensor, touch panel, weather
station, actuator...) are planned per room or floor, a project-wide bill of
materials, the Geräteliste PDF export (order list), and the Geräte je Raum
PDF export (installation reference - every device, grouped by Geschoss/Raum).
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table
from reportlab.lib.units import mm

from ..db import get_db
from ..models import RoomDeviceIn, RoomDeviceEditIn, DeviceOrderFlagIn
from ..pdf_design import pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response, company_header_block, company_footer_line
from ..utils import join_parts

router = APIRouter(tags=["geraeteplanung"])


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
                    "total": entry["total"], "rooms": entry["rooms"],
                    "not_ordering": order_flags.get(device_type_id, False),
                }
            )
        result.sort(key=lambda r: (r["group_name"], r["device_name"]))
        return result


@router.get("/api/projects/{project_id}/export-geraeteliste.pdf")
def export_geraeteliste_pdf(project_id: int):
    """Just the order-relevant Stückliste (Gruppe/Hersteller/Typ/Anzahl) - no
    per-room breakdown, this is meant as a clean list to hand to a supplier.
    Devices marked "nicht bestellen" (see set_device_order_flag) are left out
    of the order table itself and listed separately underneath instead."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        summary = device_summary(project_id)
        to_order = [s for s in summary if not s["not_ordering"]]
        already_have = [s for s in summary if s["not_ordering"]]

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(f"Geräteliste — {project['name']}", "Bestellübersicht")

        heading = Paragraph("Stückliste (Bestellung)", styles["SectionHeading"])
        table_data = [["Gruppe", "Hersteller", "Typ", "Anzahl"]]
        for s in to_order:
            table_data.append([s["group_name"], s["manufacturer"], s["model"], str(s["total"])])
        if len(table_data) == 1:
            story.append(KeepTogether([heading, Paragraph("Noch keine Geräte geplant.", styles["BodyMuted"])]))
        else:
            table = Table(table_data, colWidths=[30 * mm, 55 * mm, 65 * mm, 15 * mm])
            table.setStyle(pdf_table_style())
            story.append(KeepTogether([heading, table]))

        if already_have:
            story.append(Spacer(1, 4 * mm))
            text = ", ".join(f"{s['total']}× {s['device_name']}" for s in already_have)
            story.append(KeepTogether([
                Paragraph("Bereits vorhanden (nicht bestellt)", styles["SubHeading"]),
                Paragraph(text, styles["BodyMuted"]),
            ]))

        return build_pdf_response(
            story,
            footer_left_text=f"Geräteliste · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_geraeteliste.pdf",
            doc_title=f"Geräteliste {project['name']}",
            footer_center_text=company_footer_line(company),
        )


def _geraete_je_raum_rows(db, project_id):
    """Every device in the project - room_devices, floor_devices ("Ohne
    Raum"), and Abgangsliste's actor_instances (grouped by Standortbezeichnung,
    since they have no room_id) - as (floor_name, room_name, [devices]) tuples,
    device dicts shaped {manufacturer, model, group_name, physical_address}.
    Shared by the standalone Geräte-je-Raum PDF and its optional Pflichtenheft
    section, same pattern as build_verteilerplanung_story/
    build_abgangsliste_story in the sibling routers."""
    rows = []
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    for floor in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        for room in rooms:
            devices = db.execute(
                "SELECT rd.*, at.manufacturer, at.model, at.group_name FROM room_devices rd "
                "JOIN actor_types at ON rd.device_type_id = at.id "
                "WHERE rd.room_id=? ORDER BY rd.order_idx",
                (room["id"],),
            ).fetchall()
            if devices:
                rows.append((floor["name"], room["name"], devices))

        floor_devices = db.execute(
            "SELECT fd.*, at.manufacturer, at.model, at.group_name FROM floor_devices fd "
            "JOIN actor_types at ON fd.device_type_id = at.id "
            "WHERE fd.floor_id=? ORDER BY fd.order_idx",
            (floor["id"],),
        ).fetchall()
        if floor_devices:
            rows.append((floor["name"], "Ohne Raum", floor_devices))

        actor_rows = db.execute(
            "SELECT ai.*, at.manufacturer, at.model, at.group_name FROM actor_instances ai "
            "JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? AND ai.floor_id=? ORDER BY ai.order_idx",
            (project_id, floor["id"]),
        ).fetchall()
        rows += _grouped_actor_rows(actor_rows, floor["name"])

    actor_no_floor = db.execute(
        "SELECT ai.*, at.manufacturer, at.model, at.group_name FROM actor_instances ai "
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
             "physical_address": ai["physical_address"]}
            for ai in group
        ])
        for label, group in by_label.items()
    ]


def build_geraete_je_raum_story(db, project_id, styles):
    """One table per Raum/floor-location: Gruppe/Hersteller/Typ/Adresse -
    factored out so both the standalone export and the Pflichtenheft's
    optional inclusion share one rendering."""
    rows = _geraete_je_raum_rows(db, project_id)
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
        table_data = [["Gruppe", "Hersteller", "Typ", "Adresse"]]
        for d in devices:
            table_data.append([d["group_name"], d["manufacturer"], d["model"], d["physical_address"] or "—"])
        table = Table(table_data, colWidths=[25 * mm, 45 * mm, 65 * mm, 35 * mm], repeatRows=1)
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


@router.get("/api/projects/{project_id}/export-geraete-je-raum.pdf")
def export_geraete_je_raum_pdf(project_id: int):
    """Installation reference: every device in the project, grouped by
    Geschoss/Raum with Gruppe/Hersteller/Typ/Adresse - the counterpart to
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
        story += build_geraete_je_raum_story(db, project_id, styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Geräte je Raum · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_geraete_je_raum.pdf",
            doc_title=f"Geräte je Raum {project['name']}",
            footer_center_text=company_footer_line(company),
        )
