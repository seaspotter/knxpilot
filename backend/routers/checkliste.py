"""
Shared backend for the two digital on-site checklists (Funktionscheckliste,
Übergabe-Checkliste): a common checklist_status upsert mechanism (see
db.py), plus JSON endpoints that expose the already-keyed function/central-
function data (from ga_logic.py) and the static Übergabe-Checkliste catalog,
so neither frontend re-derives that filtering/grouping logic itself. Also
both tabs' PDF exports - kept in this one file rather than split across two
router files, since they need the exact same status-map-fetching logic
already written for the JSON endpoints, and the two tabs otherwise share no
router. See routers/pflichtenheft.py for the early-stage spec document
these checklists' results eventually feed into (via routers/
dokumentation.py) and its function_checklist_table(), reused here for the
Funktionscheckliste PDF export.
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_room_functions_by_category, get_central_functions_overview
from ..models import ChecklistStatusIn
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response,
    company_header_block, company_footer_line, checkbox_cell, signature_block,
)
from .pflichtenheft import function_checklist_table

router = APIRouter(tags=["checkliste"])


# ---------- Shared checklist-status store ----------
def get_status_map(db, project_id):
    rows = db.execute(
        "SELECT item_key, status, note FROM checklist_status WHERE project_id=?", (project_id,)
    ).fetchall()
    return {r["item_key"]: {"status": r["status"], "note": r["note"]} for r in rows}


@router.get("/api/projects/{project_id}/checklist-status")
def get_checklist_status(project_id: int):
    with get_db() as db:
        return get_status_map(db, project_id)


@router.put("/api/projects/{project_id}/checklist-status/{item_key}")
def set_checklist_status(project_id: int, item_key: str, body: ChecklistStatusIn):
    with get_db() as db:
        db.execute(
            "INSERT INTO checklist_status (project_id, item_key, status, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, item_key) DO UPDATE SET "
            "status=excluded.status, note=excluded.note, updated_at=CURRENT_TIMESTAMP",
            (project_id, item_key, body.status, body.note),
        )
    return {"ok": True}


# ---------- Funktionscheckliste ----------
@router.get("/api/rooms/{room_id}/function-checklist")
def room_function_checklist(room_id: int):
    """{category_name: [{key, text}, ...]} - same grouping the Pflichtenheft
    PDF uses, just exposed as JSON so the Funktionscheckliste tab doesn't
    have to re-derive it client-side."""
    with get_db() as db:
        return get_room_functions_by_category(db, room_id)


@router.get("/api/projects/{project_id}/central-functions-checklist")
def central_functions_checklist(project_id: int):
    """[[category_name, [{key, text}, ...]], ...] - see get_central_functions_overview()."""
    with get_db() as db:
        return get_central_functions_overview(db, project_id)


@router.get("/api/projects/{project_id}/export-funktionscheckliste.pdf")
def export_funktionscheckliste_pdf(project_id: int):
    """The on-site testing record: every planned function, grouped by
    Geschoss/Raum, with its real checked state - counterpart to
    Pflichtenheft's own "what's planned" listing, which deliberately has no
    checkbox column at all."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        status_map = get_status_map(db, project_id)

        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
            f"Funktionscheckliste — {project['name']}",
            "Digital erfasster Testfortschritt je Funktion",
        )

        any_room = False
        for floor in floors:
            rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
            if not rooms:
                continue
            floor_heading = Paragraph(floor["name"], styles["SectionHeading"])
            first_room_in_floor = True
            for room in rooms:
                functions = get_room_functions_by_category(db, room["id"])
                function_table = function_checklist_table(styles, functions, status_map=status_map)
                if not function_table:
                    continue
                any_room = True
                room_heading = Paragraph(room["name"], styles["RoomHeading"])
                group = [floor_heading, room_heading] if first_room_in_floor else [room_heading]
                first_room_in_floor = False
                group.append(function_table)
                story.append(KeepTogether(group))
                story.append(Spacer(1, 2.5 * mm))

        if not any_room:
            story.append(Paragraph("Noch keine Funktionen geplant.", styles["BodyMuted"]))

        central_overview = get_central_functions_overview(db, project_id)
        if central_overview:
            central_table = function_checklist_table(styles, dict(central_overview), status_map=status_map)
            if central_table:
                story.append(Paragraph("Zentral- und Allgemeinfunktionen", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story.append(central_table)

        return build_pdf_response(
            story,
            footer_left_text=f"Funktionscheckliste · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_funktionscheckliste.pdf",
            doc_title=f"Funktionscheckliste {project['name']}",
            footer_center_text=company_footer_line(company),
        )


# ---------- Übergabe-Checkliste ----------
# Generic, mostly project-independent handover checklist - its own sub-tab,
# checked digitally on-site (PDF is an export/snapshot only, not the
# primary interface). Modeled after common KNX-installation handover
# checklists, in KNXpilot's own wording rather than copied from any
# specific vendor's template. Each item has a hand-assigned stable slug
# (not derived from its text) so its checklist_status key survives a
# future wording tweak without silently resetting anyone's saved answer -
# only reordering/removing an item invalidates its key.
CHECKLIST_SECTIONS = [
    ("Sichtprüfung", [
        ("dosen_geschlossen", "Alle Abzweig- und Anschlussdosen geschlossen"),
        ("leuchten_isoliert", "Anschlüsse für bauseitige Leuchten isoliert bzw. mit provisorischer Fassung versehen"),
        ("taster_beschriftet", "Alle Taster nach Kundenwunsch beschriftet sowie sauber und fest montiert"),
        ("verteilungen_beschriftet", "Elektro-Verteilungen vollständig beschriftet und gereinigt"),
        ("verteilungsplaene", "Verteilungspläne in den Verteilungen hinterlegt"),
        ("bus_adressen_beschriftet", "Buskomponenten inkl. Taster mit physikalischer Adresse beschriftet"),
        ("netzwerkdosen_beschriftet", "Netzwerkdosen beschriftet"),
        ("beschreibungen_vorhanden", "Anlagen-/Gerätebeschreibungen sowie Bedienungsanleitungen in separatem Ordner vorhanden"),
        ("revisionsunterlagen_vorhanden", "Revisionsunterlagen, Pläne, Schema, Pflichtenheft in separatem Ordner vorhanden"),
        ("dokumentation_hinterlegt", "Dokumentation der Anlage hinterlegt"),
    ]),
    ("Funktionsprüfung", [
        ("messungen_durchgefuehrt", "Installation geprüft, alle Messungen durchgeführt (E-Check, Netzwerk usw.)"),
        ("funktionen_geprueft", "Licht, Dimmer, Jalousien, Zentral Aus, Szenen usw. auf korrekte Funktion geprüft"),
        ("fensterkontakte_geprueft", "Fensterkontakte geprüft"),
        ("gegensprechanlage_geprueft", "Gegensprechanlage geprüft"),
        ("schnittstellen_geprueft", "Schnittstellen zu Fremdsystemen geprüft (Musik, Alarm, Lüftung usw.)"),
        ("heizung_kalibriert", "Raumbezogene Kalibrierung der Raumtemperaturregler"),
    ]),
    ("Kundengespräch", [
        ("einfuehrung_installation", "Einführung des Kunden in die technische Installation"),
        ("einweisung_geraetestandort", "Einweisung über den Standort spezieller Geräte (z.B. Windfühler, Zentrale)"),
        ("einweisung_sicherheit", "Einweisung in Sicherheitsanwendungen und Alarmzentrale"),
        ("erlaeuterung_funktionen", "Erläuterung der Schalt-, Dimm- und Jalousiefunktionen"),
        ("erklaerung_visualisierung", "Erklärung von Inhalten und Navigation von Touchpanels/Visualisierungen"),
        ("einweisung_schaltuhren", "Einweisung in Schaltuhren und weitere kundenrelevante Funktionen (z.B. Szenen abrufen/speichern)"),
        ("einweisung_raumbediengeraete", "Einweisung in die Bedienung der Raumtemperaturregler und weiterer Raumbediengeräte"),
        ("verhalten_ausfall_besprochen", "Verhalten bei Bus-/Netzspannungsausfall und -wiederkehr besprochen"),
        ("offene_punkte_aufgenommen", "Offene Punkte der Installation aufgenommen"),
    ]),
    ("Anlagenübergabe", [
        ("uebergabe_software_doku", "Übergabe der Projekt-Software, Anlagendokumentation und aller Handbücher"),
        ("kundendienst_hinterlassen", "Kundendienst-Telefonnummer hinterlassen / Wartungsvertrag abgeschlossen"),
        ("abnahmeprotokoll_unterzeichnet", "Abnahme-Protokoll nach Pflichtenheft bzw. DIN 18015-4 unterzeichnet"),
    ]),
]


@router.get("/api/uebergabe-checklist-sections")
def uebergabe_checklist_sections():
    """Project-independent - the frontend always gets its item keys from
    here rather than inventing/hashing them itself."""
    return [
        {
            "section": section_title,
            "items": [{"key": f"uebergabe:{slug}", "text": text} for slug, text in items],
        }
        for section_title, items in CHECKLIST_SECTIONS
    ]


def checklist_section_table(styles, items, status_map):
    data = [["Aufgabe", "Ja", "Nein", "Nicht nötig", "Bemerkungen"]]
    for slug, text in items:
        entry = status_map.get(f"uebergabe:{slug}", {})
        status = entry.get("status", "")
        note = entry.get("note", "")
        data.append([
            Paragraph(text, styles["Body"]),
            checkbox_cell(checked=status == "ja"),
            checkbox_cell(checked=status == "nein"),
            checkbox_cell(checked=status == "nicht_noetig"),
            Paragraph(note, styles["Body"]) if note else "",
        ])
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
        status_map = get_status_map(db, project_id)

    styles = pdf_styles()
    story = company_header_block(company) + pdf_title_banner(
        f"Übergabe-Checkliste — {project['name']}",
        "Checkliste zur Übergabe einer Elektroinstallation mit KNX",
    )

    for i, (section_title, items) in enumerate(CHECKLIST_SECTIONS):
        if i > 0:
            story.append(Spacer(1, 4 * mm))
        story.append(KeepTogether([
            Paragraph(section_title, styles["SectionHeading"]),
            checklist_section_table(styles, items, status_map),
        ]))

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
