"""
Pflichtenheft tab: documents, per room, the agreed functions (from GA points)
and devices (from Geräteplanung), plus a central-functions overview and the
device bill of materials - as a customer/electrician-facing PDF.
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_room_functions_by_category, get_central_functions_overview
from ..pdf_design import pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response
from ..utils import join_parts
from .geraeteplanung import device_summary

router = APIRouter(tags=["pflichtenheft"])


@router.get("/api/projects/{project_id}/export-pflichtenheft.pdf")
def export_pflichtenheft_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
        styles = pdf_styles()
        story = pdf_title_banner(
            f"Pflichtenheft — {project['name']}",
            "Dokumentation des vereinbarten Funktionsumfangs",
        )
        story.append(Paragraph(
            "Dieses Dokument beschreibt je Raum die geplanten Funktionen (Beleuchtung, Beschattung, "
            "Heizung, Steckdosen usw.) sowie die vorgesehenen Geräte (Sensoren, Bedienelemente usw.) "
            "und dient als Referenz für den vereinbarten Leistungsumfang.",
            styles["Body"],
        ))
        story.append(Spacer(1, 4 * mm))

        any_room = False
        for floor in floors:
            rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
            if not rooms:
                continue
            story.append(Paragraph(floor["name"], styles["SectionHeading"]))
            for room in rooms:
                any_room = True
                story.append(Paragraph(room["name"], styles["RoomHeading"]))
                functions = get_room_functions_by_category(db, room["id"])
                devices = db.execute(
                    "SELECT rd.*, at.manufacturer, at.model FROM room_devices rd "
                    "JOIN actor_types at ON rd.device_type_id = at.id "
                    "WHERE rd.room_id=? ORDER BY rd.order_idx",
                    (room["id"],),
                ).fetchall()
                if not functions and not devices:
                    story.append(Paragraph("Keine Funktionen oder Geräte geplant.", styles["BodyMuted"]))
                    continue
                for cat_name, items in functions.items():
                    story.append(Paragraph(f"<b>{cat_name}:</b> {', '.join(items)}", styles["Body"]))
                if devices:
                    device_list = ", ".join(
                        f"{d['quantity']}× {join_parts(d['manufacturer'], d['model'])}" + (f" ({d['note']})" if d["note"] else "")
                        for d in devices
                    )
                    story.append(Paragraph(f"<b>Geräte:</b> {device_list}", styles["Body"]))
                story.append(Spacer(1, 1.5 * mm))

        if not any_room:
            story.append(Paragraph("Noch keine Räume in diesem Projekt angelegt.", styles["BodyMuted"]))

        central_overview = get_central_functions_overview(db, project_id)
        if central_overview:
            story.append(PageBreak())
            story.append(Paragraph("Zentral- und Allgemeinfunktionen", styles["SectionHeading"]))
            story.append(Paragraph(
                "Automatisch generierte, projektweite bzw. je Geschoss verfügbare Funktionen "
                "(z.B. Sammelsteuerungen, Uhrzeit/Datum, Wetterdaten):",
                styles["Body"],
            ))
            story.append(Spacer(1, 2 * mm))
            for cat_name, items in central_overview:
                story.append(Paragraph(f"<b>{cat_name}:</b> {', '.join(items)}", styles["Body"]))
                story.append(Spacer(1, 1 * mm))

        summary = device_summary(project_id)
        if summary:
            story.append(PageBreak())
            story.append(Paragraph("Stückliste (Geräte gesamt)", styles["SectionHeading"]))
            table_data = [["Gruppe", "Gerät", "Anzahl"]]
            for s in summary:
                table_data.append([s["group_name"], s["device_name"], str(s["total"])])
            table = Table(table_data, colWidths=[35 * mm, 105 * mm, 25 * mm])
            table.setStyle(pdf_table_style())
            story.append(table)

        return build_pdf_response(
            story,
            footer_left_text=f"Pflichtenheft · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_pflichtenheft.pdf",
            doc_title=f"Pflichtenheft {project['name']}",
        )
