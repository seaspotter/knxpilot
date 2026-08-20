"""
Dokumentation tab: the end-of-project assembly - "everything, generated at
the end." Combines what Pflichtenheft covers (the agreed spec, reused
verbatim via build_pflichtenheft_spec_story()) with the two digital
checklists' actual recorded results (Funktionscheckliste, Übergabe-
Checkliste, both with real checked state) plus whichever optional as-built
sections (Abgangsliste, Verteilerplanung, Gruppenadressen, Klärungsliste,
Geräte je Raum) are toggled on in Setup -> Dokumentation. Reuses the
existing pflichtenheft_include_* company_profile columns as-is - moved
*usage* only, not renamed, since renaming would need a DB migration for a
purely internal wiring change.
"""
from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak, KeepTogether
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import build_ga_tree, get_room_functions_by_category, get_central_functions_overview
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response,
    company_header_block, company_footer_line,
)
from .abgangsliste import build_abgangsliste_story
from .verteiler import build_verteilerplanung_story
from .geraeteplanung import build_geraete_je_raum_story
from .pflichtenheft import build_pflichtenheft_spec_story, function_checklist_table
from .checkliste import get_status_map, CHECKLIST_SECTIONS, checklist_section_table, build_signature_row

router = APIRouter(tags=["dokumentation"])


def _gruppenadressen_story(project_id, styles):
    """Compact table rendering of the GA tree (see build_ga_tree()) for the
    optional Dokumentation "Gruppenadressen" section - Adresse/Name/DPT per
    Middle Group, since a full project can have hundreds of addresses and the
    interactive tree view's collapsibility doesn't translate to a static PDF."""
    tree = build_ga_tree(project_id)
    story = []
    for m_idx, main in enumerate(tree["main_groups"]):
        if m_idx > 0:
            story.append(PageBreak())
        total_subs = sum(len(mid["subs"]) for mid in main["middles"])
        main_heading = Paragraph(f"{main['main']} {main['name']} ({total_subs})", styles["SectionHeading"])
        for mid_idx, mid in enumerate(main["middles"]):
            mid_heading = Paragraph(
                f"{main['main']}/{mid['middle']} {mid['name']} ({len(mid['subs'])})", styles["RoomHeading"]
            )
            table_data = [["Adresse", "Name", "DPT"]]
            for s in mid["subs"]:
                table_data.append([
                    f"{main['main']}/{mid['middle']}/{s['sub']}",
                    Paragraph(s["name"], styles["Body"]),
                    s["dpt"] or "",
                ])
            table = Table(table_data, colWidths=[25 * mm, 115 * mm, 40 * mm], repeatRows=1)
            table.setStyle(pdf_table_style([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            # Keep each (middle-group) heading with its own table so it's
            # never stranded alone at the bottom of a page - the first
            # middle group in a main group also carries the main-group
            # heading along, since that one has no PageBreak of its own
            # (m_idx == 0, see above).
            group = [main_heading, mid_heading, table] if mid_idx == 0 else [mid_heading, table]
            story.append(KeepTogether(group))
            story.append(Spacer(1, 3 * mm))
        if not main["middles"]:
            story.append(main_heading)
    return story


def _klaerungsliste_story(db, project_id, styles):
    """Table rendering of the Klärungsliste for the optional Dokumentation
    section - all entries regardless of status (offen/geklärt/abgelehnt),
    each clearly labeled, so nothing is silently omitted from the record."""
    rows = db.execute(
        "SELECT k.*, r.name AS room_name FROM klaerungen k "
        "LEFT JOIN rooms r ON k.room_id = r.id "
        "WHERE k.project_id=? ORDER BY k.room_id IS NULL DESC, k.order_idx",
        (project_id,),
    ).fetchall()
    if not rows:
        return [Paragraph("Keine Einträge vorhanden.", styles["BodyMuted"])]
    table_data = [["Raum", "Typ", "Text", "Status", "Antwort"]]
    for r in rows:
        table_data.append([
            Paragraph(r["room_name"] or "Allgemein", styles["Body"]),
            Paragraph(r["typ"], styles["Body"]),
            Paragraph(r["text"], styles["Body"]),
            Paragraph(r["status"], styles["Body"]),
            Paragraph(r["antwort"] or "", styles["Body"]),
        ])
    table = Table(table_data, colWidths=[28 * mm, 20 * mm, 55 * mm, 20 * mm, 57 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return [table]


def _funktionscheckliste_story(db, project_id, styles, status_map):
    """Same per-floor/per-room grouping as the standalone Funktionscheckliste
    export (routers/checkliste.py), with real checked state, reused here as
    a section within the full Dokumentation."""
    story = []
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
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
    return story


def _uebergabe_story(db, project_id, styles, status_map):
    """Same section grouping as the standalone Übergabe-Checkliste export
    (routers/checkliste.py), with the real Ja/Nein/Nicht-nötig answers and
    Bemerkungen text, plus the real captured signatures (if any)."""
    story = []
    for i, (section_title, items) in enumerate(CHECKLIST_SECTIONS):
        if i > 0:
            story.append(Spacer(1, 4 * mm))
        story.append(KeepTogether([
            Paragraph(section_title, styles["SectionHeading"]),
            checklist_section_table(styles, items, status_map),
        ]))
    story.append(Spacer(1, 8 * mm))
    story.append(build_signature_row(db, project_id, styles))
    return story


@router.get("/api/projects/{project_id}/export-dokumentation.pdf")
def export_dokumentation_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        status_map = get_status_map(db, project_id)
        styles = pdf_styles()

        story = company_header_block(company) + pdf_title_banner(
            f"Dokumentation — {project['name']}",
            "Vollständige Abschlussdokumentation",
        )
        story.append(Paragraph(
            "Dieses Dokument fasst die gesamte Projektdokumentation zusammen: den vereinbarten "
            "Funktionsumfang, die tatsächlichen Testergebnisse der Funktions- und Übergabe-Checkliste "
            "sowie die ausgewählten Zusatzabschnitte.",
            styles["Body"],
        ))
        story.append(Spacer(1, 4 * mm))

        story += build_pflichtenheft_spec_story(db, project_id, company, styles)

        story.append(PageBreak())
        story.append(Paragraph("Funktionscheckliste — Testergebnisse", styles["SectionHeading"]))
        story.append(Spacer(1, 2 * mm))
        story += _funktionscheckliste_story(db, project_id, styles, status_map)

        story.append(PageBreak())
        story.append(Paragraph("Übergabe-Checkliste — Ergebnisse", styles["SectionHeading"]))
        story.append(Spacer(1, 2 * mm))
        story += _uebergabe_story(db, project_id, styles, status_map)

        if company.get("pflichtenheft_include_abgangsliste", False):
            abgangsliste_story = build_abgangsliste_story(db, project_id, styles, page_break_between_floors=False)
            if abgangsliste_story:
                story.append(PageBreak())
                story.append(Paragraph("Abgangsliste", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story += abgangsliste_story

        if company.get("pflichtenheft_include_verteilerplanung", False):
            verteilerplanung_story = build_verteilerplanung_story(db, project_id, styles)
            if verteilerplanung_story:
                story.append(PageBreak())
                story.append(Paragraph("Verteilerplanung", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story += verteilerplanung_story

        if company.get("pflichtenheft_include_geraete_je_raum", False):
            geraete_je_raum_story = build_geraete_je_raum_story(db, project_id, styles)
            if geraete_je_raum_story:
                story.append(PageBreak())
                story.append(Paragraph("Geräte je Raum", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story += geraete_je_raum_story

        if company.get("pflichtenheft_include_klaerungsliste", False):
            story.append(PageBreak())
            story.append(Paragraph("Klärungsliste", styles["SectionHeading"]))
            story.append(Spacer(1, 2 * mm))
            story += _klaerungsliste_story(db, project_id, styles)

        # Gruppenadressen last, deliberately - it's the longest/most
        # reference-table-like section on a larger project (every GA in a
        # dense table), so it goes at the very back rather than breaking up
        # the more narrative sections above it.
        if company.get("pflichtenheft_include_gruppenadressen", False):
            ga_story = _gruppenadressen_story(project_id, styles)
            if ga_story:
                story.append(PageBreak())
                story.append(Paragraph("Gruppenadressen", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story += ga_story

        return build_pdf_response(
            story,
            footer_left_text=f"Dokumentation · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_dokumentation.pdf",
            doc_title=f"Dokumentation {project['name']}",
            footer_center_text=company_footer_line(company),
        )
