"""
Geräteplanung tab: which devices (any group - sensor, touch panel, weather
station, actuator...) are planned per room, a project-wide bill of
materials, and the Geräteliste PDF export (order list).
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
from reportlab.lib.units import mm

from ..db import get_db
from ..models import RoomDeviceIn
from ..pdf_design import pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response
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
                }
            )
        return result


@router.post("/api/rooms/{room_id}/devices")
def add_room_device(room_id: int, rd: RoomDeviceIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM room_devices WHERE room_id=?", (room_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO room_devices (room_id, device_type_id, quantity, note, order_idx) VALUES (?, ?, ?, ?, ?)",
            (room_id, rd.device_type_id, max(1, rd.quantity), rd.note, count),
        )
        return {"id": cur.lastrowid}


@router.delete("/api/room-devices/{rd_id}")
def delete_room_device(rd_id: int):
    with get_db() as db:
        db.execute("DELETE FROM room_devices WHERE id=?", (rd_id,))
    return {"ok": True}


@router.get("/api/projects/{project_id}/device-summary")
def device_summary(project_id: int):
    """Project-wide bill of materials: total quantity needed per device type,
    plus which rooms use it - built from the room_devices planning list."""
    with get_db() as db:
        device_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
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
                        {"floor_name": floor["name"], "room_name": room["name"], "quantity": rd["quantity"]}
                    )

        result = []
        for device_type_id, entry in totals.items():
            dt = device_types.get(device_type_id, {})
            result.append(
                {
                    "device_type_id": device_type_id,
                    "device_name": join_parts(dt.get("manufacturer", ""), dt.get("model", "")) or "?",
                    "group_name": dt.get("group_name", ""),
                    "total": entry["total"], "rooms": entry["rooms"],
                }
            )
        result.sort(key=lambda r: (r["group_name"], r["device_name"]))
        return result


@router.get("/api/projects/{project_id}/export-geraeteliste.pdf")
def export_geraeteliste_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        summary = device_summary(project_id)

        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
        room_rows = []
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
                    room_rows.append((floor["name"], room["name"], devices))

        styles = pdf_styles()
        story = pdf_title_banner(f"Geräteliste — {project['name']}", "Bestellübersicht")

        story.append(Paragraph("Stückliste (Bestellung)", styles["SectionHeading"]))
        table_data = [["Gruppe", "Gerät", "Anzahl"]]
        for s in summary:
            table_data.append([s["group_name"], s["device_name"], str(s["total"])])
        if len(table_data) == 1:
            story.append(Paragraph("Noch keine Geräte geplant.", styles["BodyMuted"]))
        else:
            table = Table(table_data, colWidths=[35 * mm, 105 * mm, 25 * mm])
            table.setStyle(pdf_table_style())
            story.append(table)

        if room_rows:
            story.append(PageBreak())
            story.append(Paragraph("Verteilung je Raum", styles["SectionHeading"]))
            current_floor = None
            for floor_name, room_name, devices in room_rows:
                if floor_name != current_floor:
                    story.append(Spacer(1, 2 * mm))
                    story.append(Paragraph(floor_name, styles["RoomHeading"]))
                    current_floor = floor_name
                device_list = ", ".join(
                    f"{d['quantity']}× {join_parts(d['manufacturer'], d['model'])}" + (f" ({d['note']})" if d["note"] else "")
                    for d in devices
                )
                story.append(Paragraph(f"<b>{room_name}:</b> {device_list}", styles["Body"]))
                story.append(Spacer(1, 1.5 * mm))

        return build_pdf_response(
            story,
            footer_left_text=f"Geräteliste · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_geraeteliste.pdf",
            doc_title=f"Geräteliste {project['name']}",
        )
