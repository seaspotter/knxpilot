"""
Pflichtenheft tab: documents, per room, the agreed functions (from GA points)
and devices (from Geräteplanung), plus a central-functions overview and the
device bill of materials - as a customer/electrician-facing PDF. Also exports
a generic, mostly project-independent handover checklist (Übergabe-Checkliste)
alongside it.
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_room_functions_by_category, get_central_functions_overview
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response,
    company_header_block, company_footer_line, checkbox_cell, signature_block,
)
from ..utils import join_parts
from .geraeteplanung import device_summary

router = APIRouter(tags=["pflichtenheft"])


def _function_checklist_table(styles, rows_by_category):
    """Kategorie | Funktion | Getestet (checkbox) - one row per individual
    function, category name shown only on its first row for readability.
    Returns None if there's nothing to list."""
    data = [["Kategorie", "Funktion", "Getestet"]]
    for cat_name, items in rows_by_category.items():
        for i, item in enumerate(items):
            data.append([
                Paragraph(cat_name, styles["Body"]) if i == 0 else "",
                Paragraph(item, styles["Body"]),
                checkbox_cell(),
            ])
    if len(data) == 1:
        return None
    table = Table(data, colWidths=[45 * mm, 118 * mm, 17 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _floor_room_table(styles, floor_rooms):
    """Geschoss | Raum directory table, floor name shown only on its first row."""
    data = [["Geschoss", "Raum"]]
    for floor_name, room_names in floor_rooms:
        for i, room_name in enumerate(room_names):
            data.append([
                Paragraph(floor_name, styles["Body"]) if i == 0 else "",
                Paragraph(room_name, styles["Body"]),
            ])
    if len(data) == 1:
        return None
    table = Table(data, colWidths=[70 * mm, 110 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return table


@router.get("/api/projects/{project_id}/export-pflichtenheft.pdf")
def export_pflichtenheft_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
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

        preamble = (company.get("pflichtenheft_preamble") or "").strip()
        if preamble:
            story.append(Paragraph("Vorbemerkungen", styles["SectionHeading"]))
            for para in preamble.split("\n\n"):
                story.append(Paragraph(para.replace("\n", "<br/>"), styles["Body"]))
                story.append(Spacer(1, 1.5 * mm))
            story.append(Spacer(1, 2 * mm))

        # Collect floor/room data once, used for both the directory table and
        # the per-room detail section below.
        floor_rooms = []
        for floor in floors:
            rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
            floor_rooms.append((floor, rooms))

        directory_table = _floor_room_table(styles, [(f["name"], [r["name"] for r in rooms]) for f, rooms in floor_rooms if rooms])
        if directory_table:
            story.append(Paragraph("Stockwerk- und Raumverzeichnis", styles["SectionHeading"]))
            story.append(directory_table)
            story.append(PageBreak())

        any_room = False
        for floor, rooms in floor_rooms:
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
                function_table = _function_checklist_table(styles, functions)
                if function_table:
                    story.append(function_table)
                    story.append(Spacer(1, 2 * mm))
                if devices:
                    device_list = ", ".join(
                        f"{d['quantity']}× {join_parts(d['manufacturer'], d['model'])}" + (f" ({d['note']})" if d["note"] else "")
                        for d in devices
                    )
                    story.append(Paragraph(f"<b>Geräte:</b> {device_list}", styles["Body"]))
                story.append(Spacer(1, 2.5 * mm))

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
            central_table = _function_checklist_table(styles, dict(central_overview))
            if central_table:
                story.append(central_table)

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
            footer_center_text=company_footer_line(company),
        )


# ---------- Übergabe-Checkliste ----------
# Generic, mostly project-independent handover checklist (only the project
# name/date are filled in) - a companion document to the Pflichtenheft above,
# meant to be printed and hand-ticked during the on-site handover meeting.
# Modeled after common KNX-installation handover checklists, in KNXpilot's
# own wording rather than copied from any specific vendor's template.
CHECKLIST_SECTIONS = [
    ("Sichtprüfung", [
        "Alle Abzweig- und Anschlussdosen geschlossen",
        "Anschlüsse für bauseitige Leuchten isoliert bzw. mit provisorischer Fassung versehen",
        "Alle Taster nach Kundenwunsch beschriftet sowie sauber und fest montiert",
        "Elektro-Verteilungen vollständig beschriftet und gereinigt",
        "Verteilungspläne in den Verteilungen hinterlegt",
        "Buskomponenten inkl. Taster mit physikalischer Adresse beschriftet",
        "Netzwerkdosen beschriftet",
        "Anlagen-/Gerätebeschreibungen sowie Bedienungsanleitungen in separatem Ordner vorhanden",
        "Revisionsunterlagen, Pläne, Schema, Pflichtenheft in separatem Ordner vorhanden",
        "Dokumentation der Anlage hinterlegt",
    ]),
    ("Funktionsprüfung", [
        "Installation geprüft, alle Messungen durchgeführt (E-Check, Netzwerk usw.)",
        "Licht, Dimmer, Jalousien, Zentral Aus, Szenen usw. auf korrekte Funktion geprüft",
        "Fensterkontakte geprüft",
        "Gegensprechanlage geprüft",
        "Schnittstellen zu Fremdsystemen geprüft (Musik, Alarm, Lüftung usw.)",
        "Raumbezogene Kalibrierung der Raumtemperaturregler",
    ]),
    ("Kundengespräch", [
        "Einführung des Kunden in die technische Installation",
        "Einweisung über den Standort spezieller Geräte (z.B. Windfühler, Zentrale)",
        "Einweisung in Sicherheitsanwendungen und Alarmzentrale",
        "Erläuterung der Schalt-, Dimm- und Jalousiefunktionen",
        "Erklärung von Inhalten und Navigation von Touchpanels/Visualisierungen",
        "Einweisung in Schaltuhren und weitere kundenrelevante Funktionen (z.B. Szenen abrufen/speichern)",
        "Einweisung in die Bedienung der Raumtemperaturregler und weiterer Raumbediengeräte",
        "Verhalten bei Bus-/Netzspannungsausfall und -wiederkehr besprochen",
        "Offene Punkte der Installation aufgenommen",
    ]),
    ("Anlagenübergabe", [
        "Übergabe der Projekt-Software, Anlagendokumentation und aller Handbücher",
        "Kundendienst-Telefonnummer hinterlassen / Wartungsvertrag abgeschlossen",
        "Abnahme-Protokoll nach Pflichtenheft bzw. DIN 18015-4 unterzeichnet",
    ]),
]


def _checklist_section_table(styles, items):
    data = [["Aufgabe", "Ja", "Nein", "Nicht nötig", "Bemerkungen"]]
    for item in items:
        data.append([Paragraph(item, styles["Body"]), checkbox_cell(), checkbox_cell(), checkbox_cell(), ""])
    table = Table(data, colWidths=[85 * mm, 12 * mm, 12 * mm, 20 * mm, 51 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


@router.get("/api/projects/{project_id}/export-uebergabe-checkliste.pdf")
def export_uebergabe_checkliste_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())

    styles = pdf_styles()
    story = company_header_block(company) + pdf_title_banner(
        f"Übergabe-Checkliste — {project['name']}",
        "Checkliste zur Übergabe einer Elektroinstallation mit KNX",
    )

    for i, (section_title, items) in enumerate(CHECKLIST_SECTIONS):
        if i > 0:
            story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(section_title, styles["SectionHeading"]))
        story.append(_checklist_section_table(styles, items))

    story.append(Spacer(1, 8 * mm))
    sig_row = Table([[
        signature_block("Datum, Unterschrift Errichter", styles),
        signature_block("Datum, Unterschrift Kunde/Betreiber", styles),
    ]], colWidths=[90 * mm, 90 * mm])
    sig_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_row)

    return build_pdf_response(
        story,
        footer_left_text=f"Übergabe-Checkliste · {project['name']}",
        filename=f"{project['name'].replace(' ', '_')}_uebergabe_checkliste.pdf",
        doc_title=f"Übergabe-Checkliste {project['name']}",
        footer_center_text=company_footer_line(company),
    )
