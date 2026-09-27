"""
Pflichtenheft tab: the early-stage, pre-project spec document - what the
customer agreed to. Documents, per room, the agreed functions (from GA
points) and devices (from Geräteplanung), plus a central-functions overview
and the device bill of materials, as a customer/electrician-facing PDF.
Deliberately narrow: no "Getestet" checkboxes (nothing's been tested yet at
this stage - see routers/checklists.py's Funktionscheckliste for that) and
no as-built sections like Abgangsliste/Verteilerplanung/Gruppenadressen/
Klärungsliste (those live in routers/documentation.py's end-of-project
Dokumentation export instead, alongside both checklists' recorded results).
`function_checklist_table()` below is shared with checklists.py's
Funktionscheckliste PDF export - same rendering, with or without a real
checked-state column.
"""
import re

from fastapi import APIRouter, HTTPException, Request
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak, HRFlowable, KeepTogether
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_room_functions_by_category, get_central_functions_overview
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_bytes, pdf_response,
    company_header_block, company_footer_line, checkbox_cell,
)
from ..templating import templates
from ..utils import join_parts, local_time_text
from .device_planning import build_stueckliste_story, device_summary


router = APIRouter(tags=["specification"])


def _inline_bold(text):
    """**bold** -> ReportLab's mini-XML <b>bold</b> (Paragraph renders a
    small HTML-like subset natively - no separate markdown-to-PDF library
    needed for just this)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


_FULLY_BOLD_RE = re.compile(r"^\*\*(.+)\*\*$")
_FULLY_ITALIC_RE = re.compile(r"^\*([^*].*[^*]|[^*])\*$")
_HR_RE = re.compile(r"^-{3,}$")


def _preamble_story(text, styles):
    """
    Turns the free-text Vorbemerkungen field into formatted flowables using
    a small, deliberately-limited markdown-like syntax (mirrors the
    frontend's own lightweight renderMarkdown() in spirit, not
    implementation - this one targets ReportLab Paragraphs, not HTML):
      ## Heading / ### Heading  -> subsection heading (RoomHeading style;
                                    either depth, no separate tier - see below)
      **Whole line bold**       -> smaller sub-subheading (SubHeading style)
      *Whole line italic*       -> muted aside/footnote (BodyMuted style)
      ---                       -> a thin horizontal rule
      - item text               -> bulleted paragraph (BodyBullet style)
      blank line                -> paragraph break
      **bold**/*italic* inline  -> bold/italic run anywhere else
    Anything else is a plain Body paragraph. Blocks are separated by blank
    lines; single newlines within a block are folded into the same
    paragraph (so the textarea's own line-wrapping doesn't force breaks).
    """
    story = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        joined = " ".join(line.strip() for line in block.split("\n"))
        bold_match = _FULLY_BOLD_RE.match(joined)
        italic_match = _FULLY_ITALIC_RE.match(joined)
        if _HR_RE.match(joined):
            story.append(HRFlowable(width="100%", thickness=0.5, spaceBefore=2, spaceAfter=2))
            continue
        elif joined.startswith("### ") or joined.startswith("## "):
            heading_text = joined.split(" ", 1)[1]
            story.append(Paragraph(_inline_bold(heading_text), styles["RoomHeading"]))
        elif bold_match:
            story.append(Paragraph(_inline_bold(bold_match.group(0)), styles["SubHeading"]))
        elif italic_match:
            story.append(Paragraph(_inline_bold(italic_match.group(1)), styles["BodyMuted"]))
        elif joined.startswith("- "):
            # A blank-line-separated block can itself contain several "- "
            # bullet lines (one per line, no further blank lines between
            # them) - split back out so each becomes its own bullet.
            for line in block.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    story.append(Paragraph(_inline_bold(line[2:]), styles["BodyBullet"]))
        else:
            story.append(Paragraph(_inline_bold(joined), styles["Body"]))
        story.append(Spacer(1, 1.5 * mm))
    return story


def function_checklist_table(styles, rows_by_category, status_map=None):
    """Kategorie | Funktion (| Getestet, only when status_map is given) - one
    row per individual function, category name shown only on its first row
    for readability. Shared between Pflichtenheft's own "what's planned"
    listing (status_map=None - nothing has been tested yet at the spec
    stage, so no checkbox column at all) and the Funktionscheckliste PDF
    export (routers/checklists.py), which passes the real
    {item_key: {status, note}} map from checklist_status so the checkbox
    reflects what's actually been checked on-site. Returns None if there's
    nothing to list."""
    show_checkbox = status_map is not None
    header = ["Kategorie", "Funktion", "Getestet"] if show_checkbox else ["Kategorie", "Funktion"]
    data = [header]
    for cat_name, items in rows_by_category.items():
        for i, item in enumerate(items):
            row = [
                Paragraph(cat_name, styles["Body"]) if i == 0 else "",
                Paragraph(item["text"], styles["Body"]),
            ]
            if show_checkbox:
                entry = status_map.get(item["key"], {})
                checked = entry.get("status") == "ok"
                when = local_time_text(entry.get("updated_at")) if checked else ""
                row.append([checkbox_cell(checked=checked), Paragraph(when, styles["TinyMuted"])] if when
                           else checkbox_cell(checked=checked))
            data.append(row)
    if len(data) == 1:
        return None
    col_widths = [40 * mm, 114 * mm, 26 * mm] if show_checkbox else [45 * mm, 135 * mm]
    extra_style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if show_checkbox:
        extra_style.append(("ALIGN", (2, 0), (2, -1), "CENTER"))
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(pdf_table_style(extra_style))
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


def build_specification_story(db, project_id, company, styles):
    """Vorbemerkungen, Stockwerk-/Raumverzeichnis, per-room functions/
    devices, Zentralfunktionen and Stückliste - factored out of
    export_specification_pdf() so routers/documentation.py's end-of-project
    export can include the exact same "what was planned" content verbatim,
    alongside the checklists' actual on-site results."""
    story = []
    preamble = (company.get("specification_preamble") or "").strip()
    if preamble and company.get("specification_include_preamble", True):
        preamble_flowables = _preamble_story(preamble, styles)
        heading = Paragraph("Vorbemerkungen", styles["SectionHeading"])
        if preamble_flowables:
            story.append(KeepTogether([heading, preamble_flowables[0]]))
            story += preamble_flowables[1:]
        else:
            story.append(heading)
        story.append(Spacer(1, 2 * mm))

    # Collect floor/room data once, used for both the directory table and
    # the per-room detail section below.
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    floor_rooms = []
    for floor in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        floor_rooms.append((floor, rooms))

    if company.get("specification_include_structure", True):
        directory_table = _floor_room_table(styles, [(f["name"], [r["name"] for r in rooms]) for f, rooms in floor_rooms if rooms])
        if directory_table:
            story.append(KeepTogether([
                Paragraph("Stockwerk- und Raumverzeichnis", styles["SectionHeading"]), directory_table,
            ]))
            story.append(PageBreak())

    any_room = False
    for floor, rooms in floor_rooms:
        if not rooms:
            continue
        floor_heading = Paragraph(floor["name"], styles["SectionHeading"])
        first_room_in_floor = True
        for room in rooms:
            any_room = True
            room_heading = Paragraph(room["name"], styles["RoomHeading"])
            # Only the first room of a floor needs to carry the floor
            # heading along - it has no PageBreak/Spacer of its own
            # before it, so it's the one at risk of being stranded
            # alone; later rooms in the same floor already start their
            # own KeepTogether group with a room heading.
            heading_group = [floor_heading, room_heading] if first_room_in_floor else [room_heading]
            first_room_in_floor = False

            functions = get_room_functions_by_category(db, room["id"])
            devices = db.execute(
                "SELECT rd.*, at.manufacturer, at.model FROM room_devices rd "
                "JOIN actor_types at ON rd.device_type_id = at.id "
                "WHERE rd.room_id=? ORDER BY rd.order_idx",
                (room["id"],),
            ).fetchall()
            if not functions and not devices:
                heading_group.append(Paragraph("Keine Funktionen oder Geräte geplant.", styles["BodyMuted"]))
                story.append(KeepTogether(heading_group))
                continue

            device_list_para = None
            if devices:
                device_list = ", ".join(
                    (f"{d['quantity']}× " if d["quantity"] != 1 else "") + join_parts(d['manufacturer'], d['model'])
                    + (f" [{d['physical_address']}]" if d["physical_address"] else "")
                    + (f" ({d['note']})" if d["note"] else "")
                    for d in devices
                )
                device_list_para = Paragraph(f"<b>Geräte:</b> {device_list}", styles["Body"])

            function_table = function_checklist_table(styles, functions)
            if function_table:
                heading_group.append(function_table)
                story.append(KeepTogether(heading_group))
                story.append(Spacer(1, 2 * mm))
                if device_list_para:
                    story.append(device_list_para)
            elif device_list_para:
                heading_group.append(device_list_para)
                story.append(KeepTogether(heading_group))
            else:
                story.append(KeepTogether(heading_group))
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
        central_table = function_checklist_table(styles, dict(central_overview))
        if central_table:
            story.append(central_table)

    if company.get("specification_include_device_list", True):
        summary = device_summary(project_id)
        if summary:
            story.append(PageBreak())
            story += build_stueckliste_story(summary, styles)  # same as the Geräteliste export

    return story


def build_specification_pdf_bytes(project_id: int):
    """The raw PDF bytes + suggested filename - shared by the HTTP download
    endpoint below and routers/email.py's send-by-mail action, so both
    always produce the exact same document."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

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
        story += build_specification_story(db, project_id, company, styles)

        data = build_pdf_bytes(
            story,
            footer_left_text=f"Pflichtenheft · {project['name']}",
            doc_title=f"Pflichtenheft {project['name']}",
            footer_center_text=company_footer_line(company),
        )
        return data, f"{project['name'].replace(' ', '_')}_pflichtenheft.pdf"


@router.get("/api/projects/{project_id}/export-specification.pdf")
def export_specification_pdf(project_id: int, inline: bool = False):
    data, filename = build_specification_pdf_bytes(project_id)
    return pdf_response(data, filename, inline=inline)


# ---------- "Inhalt" card on the Pflichtenheft tab ----------
def specification_stats(db, project_id):
    """Counts behind the contents card - shared with routers/documentation.py,
    whose first chapter is this same Pflichtenheft content."""
    floors = db.execute("SELECT id FROM floors WHERE project_id=?", (project_id,)).fetchall()
    rooms = db.execute(
        "SELECT r.id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,)
    ).fetchall()
    functions = empty_rooms = devices = 0
    for room in rooms:
        n_functions = sum(len(items) for items in get_room_functions_by_category(db, room["id"]).values())
        (n_devices,) = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM room_devices WHERE room_id=?", (room["id"],)
        ).fetchone()
        functions += n_functions
        devices += n_devices
        empty_rooms += not n_functions and not n_devices
    central = sum(len(items) for _, items in get_central_functions_overview(db, project_id))
    summary = device_summary(project_id)
    return {
        "floors": len(floors), "rooms": len(rooms), "functions": functions, "devices": devices,
        "empty_rooms": empty_rooms, "central": central,
        "device_types": len(summary), "device_total": sum(s["total"] for s in summary),
    }


def _section(title, included, detail, warn=False):
    return {"title": title, "included": included, "detail": detail, "warn": warn}


@router.get("/api/projects/{project_id}/specification-contents")
def specification_contents(project_id: int):
    """The PDF's sections in PDF order, with what each one contains - same
    conditions as build_specification_story()."""
    with get_db() as db:
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        s = specification_stats(db, project_id)
    off = "aus (Setup → Pflichtenheft)"
    has_preamble = bool((company.get("specification_preamble") or "").strip())
    sections = []
    if not company.get("specification_include_preamble", True):
        sections.append(_section("Vorbemerkungen", False, off))
    else:
        sections.append(_section("Vorbemerkungen", has_preamble,
                                 "Text aus Setup → Pflichtenheft" if has_preamble else "kein Text hinterlegt (Setup → Pflichtenheft)"))
    if not company.get("specification_include_structure", True):
        sections.append(_section("Stockwerk- und Raumverzeichnis", False, off))
    else:
        sections.append(_section("Stockwerk- und Raumverzeichnis", s["rooms"] > 0, f"{s['floors']} Geschosse · {s['rooms']} Räume"))
    detail = f"{s['functions']} Funktionen · {s['devices']} Geräte"
    if s["empty_rooms"]:
        detail += f" · {s['empty_rooms']} Raum/Räume noch ohne Funktionen oder Geräte"
    sections.append(_section("Funktionen und Geräte je Raum", s["rooms"] > 0,
                             detail if s["rooms"] else "noch keine Räume angelegt", warn=bool(s["empty_rooms"]) or not s["rooms"]))
    sections.append(_section("Zentral- und Allgemeinfunktionen", s["central"] > 0,
                             f"{s['central']} Funktionen" if s["central"] else "keine"))
    if not company.get("specification_include_device_list", True):
        sections.append(_section("Stückliste", False, off))
    else:
        sections.append(_section("Stückliste", s["device_types"] > 0,
                                 f"{s['device_types']} Gerätetypen · {s['device_total']} Stück" if s["device_types"] else "noch keine Geräte geplant"))
    return sections


# ---------- htmx fragment (backend/templates/specification/tab.html) ----------
@router.get("/hx/projects/{project_id}/specification")
def hx_tab(request: Request, project_id: int):
    return templates.TemplateResponse(request, "specification/tab.html",
                                      {"sections": specification_contents(project_id)})
