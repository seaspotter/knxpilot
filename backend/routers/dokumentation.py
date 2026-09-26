"""
Dokumentation tab: the end-of-project assembly - "everything, generated at
the end." Combines what Pflichtenheft covers (the agreed spec, reused
verbatim via build_pflichtenheft_spec_story(), explicitly labeled as its
own "Pflichtenheft" chapter so it doesn't read as if it were written for
this document) with the two digital checklists' actual recorded results
(Funktionscheckliste, Übergabe-Checkliste, both with real checked state),
a "Handbücher" chapter listing which used devices have a manual on file
(a checklist-style record only - the manual PDFs themselves stay in the
project's own Handbücher tab/project_manuals store, never merged into
this document), plus whichever optional as-built sections (Abgangsliste,
Verteilerplanung, Gruppenadressen, Klärungsliste, Geräte je Raum) are
toggled on in Setup -> Dokumentation. The three checklist-style chapters
are themselves toggleable via
dokumentation_include_funktionscheckliste/_uebergabe/_handbuecher
(default on); the five as-built sections reuse the existing
pflichtenheft_include_* company_profile columns as-is - moved *usage*
only, not renamed, since renaming would need a DB migration for a purely
internal wiring change.

The export opens with an Inhaltsverzeichnis whose entries are real
clickable internal PDF links (ReportLab's `<a href="#anchor">`/
`<a name="anchor"/>` mini-XML tags inside Paragraph text) built from the
same `chapters` list that drives the body, so the two can never drift out
of sync. Uses build_pdf_bytes_two_pass() rather than the usual
build_pdf_bytes() - see pdf_design.py's make_numbered_canvas() for why
plain single-pass "Seite X von Y" numbering silently breaks those internal
links.
"""
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException
from reportlab.platypus import Paragraph, Spacer, Table, PageBreak, KeepTogether
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import build_ga_tree, get_circuits, get_room_functions_by_category, get_central_functions_overview
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, checkbox_cell, build_pdf_bytes_two_pass, pdf_response,
    company_header_block, company_footer_line,
)
from .abgangsliste import build_abgangsliste_story
from .verteiler import build_verteilerplanung_story
from .geraeteplanung import build_geraete_je_raum_story, device_summary
from .pflichtenheft import build_pflichtenheft_spec_story, function_checklist_table, pflichtenheft_stats
from .checkliste import (
    get_status_map, CHECKLIST_SECTIONS, checklist_section_table, build_signature_row, FUNKTIONSCHECKLISTE_SIGNATURES,
)

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
            Paragraph(escape(r["room_name"] or "Allgemein"), styles["Body"]),
            Paragraph(escape(r["typ"]), styles["Body"]),
            Paragraph(escape(r["text"]), styles["Body"]),
            Paragraph(escape(r["status"]), styles["Body"]),
            Paragraph(escape(r["antwort"] or ""), styles["Body"]),
        ])
    table = Table(table_data, colWidths=[28 * mm, 20 * mm, 55 * mm, 20 * mm, 57 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return [table]


def _handbuecher_story(db, project_id, styles):
    """List-only rendering of the project's Handbücher tab: which used
    devices have a manufacturer manual curated in the catalog, and whether
    it's already been fetched into this project (routers/manuals.py). The
    PDFs themselves are deliberately NOT merged in here - they stay in
    their own project_manuals store, viewed/downloaded from the
    Handbücher tab - this is just a checklist-style record of what's on
    file, keeping the Dokumentation export itself lean."""
    devices = [d for d in device_summary(project_id) if d["manual_url"]]
    if not devices:
        return [Paragraph("Keine Handbuch-Links für verwendete Geräte hinterlegt.", styles["BodyMuted"])]

    fetched_ids = {
        r["device_type_id"]
        for r in db.execute(
            "SELECT device_type_id FROM project_manuals WHERE project_id=?", (project_id,)
        ).fetchall()
    }
    data = [["Gerät", "Vorhanden"]]
    for d in devices:
        data.append([Paragraph(escape(d["device_name"]), styles["Body"]), checkbox_cell(checked=d["device_type_id"] in fetched_ids)])
    table = Table(data, colWidths=[145 * mm, 35 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    return [
        Paragraph(
            "Die Handbücher selbst liegen im Unterreiter Handbücher des Projekts, nicht in diesem "
            "Dokument - hier nur ein Nachweis, für welche Geräte ein Handbuch hinterlegt bzw. "
            "bereits heruntergeladen ist.",
            styles["BodyMuted"],
        ),
        Spacer(1, 3 * mm),
        table,
    ]


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
    story.append(Spacer(1, 8 * mm))
    story.append(build_signature_row(db, project_id, styles, FUNKTIONSCHECKLISTE_SIGNATURES, optional=("fc_kunde",)))
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


# The chapters in PDF order, with the Setup → Dokumentation toggle that
# switches each one on (None = always included) and that toggle's default.
# One list for both the PDF (_build_dokumentation_chapters, whose
# Inhaltsverzeichnis is built from its result) and the "Inhalt" card on the
# Dokumentation tab (dokumentation_contents), so the two can't drift apart.
# Gruppenadressen last, deliberately - it's the longest/most
# reference-table-like section on a larger project (every GA in a dense
# table), so it goes at the very back rather than breaking up the more
# narrative sections above it.
DOKU_CHAPTERS = [
    ("pflichtenheft", "Pflichtenheft", None, True),
    ("funktionscheckliste", "Funktionscheckliste — Testergebnisse", "dokumentation_include_funktionscheckliste", True),
    ("uebergabe", "Übergabe-Checkliste — Ergebnisse", "dokumentation_include_uebergabe", True),
    ("handbuecher", "Handbücher", "dokumentation_include_handbuecher", True),
    ("abgangsliste", "Abgangsliste", "pflichtenheft_include_abgangsliste", False),
    ("verteilerplanung", "Verteilerplanung", "pflichtenheft_include_verteilerplanung", False),
    ("geraete-je-raum", "Geräte je Raum", "pflichtenheft_include_geraete_je_raum", False),
    ("klaerungsliste", "Klärungsliste", "pflichtenheft_include_klaerungsliste", False),
    ("gruppenadressen", "Gruppenadressen", "pflichtenheft_include_gruppenadressen", False),
]


def _chapter_enabled(company, toggle, default):
    return toggle is None or bool(company.get(toggle, default))


def _build_dokumentation_chapters(db, project_id, company, styles):
    """(anchor, title, content) for every enabled chapter with content, in
    DOKU_CHAPTERS order."""
    status_map = get_status_map(db, project_id)
    builders = {
        "pflichtenheft": lambda: build_pflichtenheft_spec_story(db, project_id, company, styles),
        "funktionscheckliste": lambda: _funktionscheckliste_story(db, project_id, styles, status_map),
        "uebergabe": lambda: _uebergabe_story(db, project_id, styles, status_map),
        "handbuecher": lambda: _handbuecher_story(db, project_id, styles),
        "abgangsliste": lambda: build_abgangsliste_story(db, project_id, styles, page_break_between_floors=False),
        "verteilerplanung": lambda: build_verteilerplanung_story(db, project_id, styles),
        "geraete-je-raum": lambda: build_geraete_je_raum_story(db, project_id, styles),
        "klaerungsliste": lambda: _klaerungsliste_story(db, project_id, styles),
        "gruppenadressen": lambda: _gruppenadressen_story(project_id, styles),
    }
    chapters = []
    for anchor, title, toggle, default in DOKU_CHAPTERS:
        if not _chapter_enabled(company, toggle, default):
            continue
        content = builders[anchor]()
        if content:  # e.g. Abgangsliste without any actuators is left out
            chapters.append((anchor, title, content))
    return chapters


def _assemble_dokumentation_story(chapters, company, project, styles):
    """Banner + intro + a clickable Inhaltsverzeichnis + the chapters
    themselves, each starting on its own page with a named anchor matching
    its Inhaltsverzeichnis entry."""
    story = company_header_block(company) + pdf_title_banner(
        f"Dokumentation — {project['name']}",
        "Vollständige Abschlussdokumentation",
    )
    story.append(Paragraph(
        "Dieses Dokument fasst die gesamte Projektdokumentation zusammen: den vereinbarten "
        "Funktionsumfang (Pflichtenheft), die tatsächlichen Testergebnisse der Funktions- und "
        "Übergabe-Checkliste sowie die unten aufgeführten Zusatzabschnitte.",
        styles["Body"],
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Inhaltsverzeichnis", styles["SectionHeading"]))
    for anchor, title, _ in chapters:
        story.append(Paragraph(f'<a href="#{anchor}">{title}</a>', styles["TOCLink"]))
    story.append(PageBreak())

    for i, (anchor, title, content) in enumerate(chapters):
        if i > 0:
            story.append(PageBreak())
        story.append(Paragraph(f'<a name="{anchor}"/>{title}', styles["SectionHeading"]))
        story.append(Spacer(1, 2 * mm))
        story += content

    return story


def build_dokumentation_pdf_bytes(project_id: int):
    """Shared by the HTTP download endpoint below and routers/email.py's
    send-by-mail action."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())

        def build_story():
            # Called twice (see build_pdf_bytes_two_pass) - each call must
            # produce genuinely fresh flowables, not reuse any from a
            # previous call, so this re-queries and rebuilds from scratch
            # every time rather than caching anything from the outer scope.
            styles = pdf_styles()
            chapters = _build_dokumentation_chapters(db, project_id, company, styles)
            return _assemble_dokumentation_story(chapters, company, project, styles)

        data = build_pdf_bytes_two_pass(
            build_story,
            footer_left_text=f"Dokumentation · {project['name']}",
            doc_title=f"Dokumentation {project['name']}",
            footer_center_text=company_footer_line(company),
        )
        return data, f"{project['name'].replace(' ', '_')}_dokumentation.pdf"


@router.get("/api/projects/{project_id}/export-dokumentation.pdf")
def export_dokumentation_pdf(project_id: int, inline: bool = False):
    data, filename = build_dokumentation_pdf_bytes(project_id)
    return pdf_response(data, filename, inline=inline)


# ---------- "Inhalt" card on the Dokumentation tab ----------
def _function_checklist_keys(db, project_id):
    keys = []
    for room in db.execute(
        "SELECT r.id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,)
    ).fetchall():
        for items in get_room_functions_by_category(db, room["id"]).values():
            keys += [it["key"] for it in items]
    for _, items in get_central_functions_overview(db, project_id):
        keys += [it["key"] for it in items]
    return keys


def _chapter_detail(db, project_id, anchor, status_map):
    """(detail text, warn, has_content) for one chapter - has_content False
    means the PDF leaves the chapter out even though it's switched on."""
    if anchor == "pflichtenheft":
        s = pflichtenheft_stats(db, project_id)
        return (f"{s['rooms']} Räume · {s['functions']} Funktionen · {s['device_types']} Gerätetypen "
                "(Details im Unterreiter Pflichtenheft)", not s["rooms"], True)
    if anchor == "funktionscheckliste":
        keys = _function_checklist_keys(db, project_id)
        tested = sum(1 for k in keys if status_map.get(k, {}).get("status") == "ok")
        if not keys:
            return "noch keine Funktionen geplant", True, True
        (signed,) = db.execute(
            "SELECT COUNT(*) FROM project_signatures WHERE project_id=? AND role='fc_systemintegrator'", (project_id,)
        ).fetchone()
        return (f"{tested} / {len(keys)} getestet · " + ("unterschrieben" if signed else "Unterschrift Systemintegrator fehlt"),
                tested < len(keys) or not signed, True)
    if anchor == "uebergabe":
        items = [f"uebergabe:{slug}" for _, section in CHECKLIST_SECTIONS for slug, _ in section]
        answered = sum(1 for k in items if status_map.get(k, {}).get("status") in ("ja", "nein", "nicht_noetig"))
        (signed,) = db.execute(
            "SELECT COUNT(*) FROM project_signatures WHERE project_id=? AND role IN ('systemintegrator', 'kunde')",
            (project_id,)).fetchone()
        return (f"{answered} / {len(items)} beantwortet · {signed} / 2 Unterschriften",
                answered < len(items) or signed < 2, True)
    if anchor == "handbuecher":
        devices = [d for d in device_summary(project_id) if d["manual_url"]]
        fetched = {r["device_type_id"] for r in db.execute(
            "SELECT device_type_id FROM project_manuals WHERE project_id=?", (project_id,))}
        n = sum(1 for d in devices if d["device_type_id"] in fetched)
        if not devices:
            return "keine Handbuch-Links für die verwendeten Geräte", False, True
        return f"{n} / {len(devices)} Handbücher im Projekt abgelegt", n < len(devices), True
    if anchor == "abgangsliste":
        (actors,) = db.execute("SELECT COUNT(*) FROM actor_instances WHERE project_id=?", (project_id,)).fetchone()
        circuits = get_circuits(db, project_id)
        assigned = sum(1 for c in circuits if c["assignment"])
        if not actors:
            return "noch keine Aktoren — entfällt", False, False
        return f"{actors} Aktoren · {assigned} / {len(circuits)} Abgänge zugeordnet", assigned < len(circuits), True
    if anchor == "verteilerplanung":
        (n,) = db.execute("SELECT COUNT(*) FROM verteiler WHERE project_id=?", (project_id,)).fetchone()
        return (f"{n} Verteiler" if n else "noch keine Verteiler angelegt"), False, True
    if anchor == "geraete-je-raum":
        s = pflichtenheft_stats(db, project_id)
        (actors,) = db.execute("SELECT COUNT(*) FROM actor_instances WHERE project_id=?", (project_id,)).fetchone()
        (floor_devices,) = db.execute(
            "SELECT COALESCE(SUM(fd.quantity), 0) FROM floor_devices fd JOIN floors f ON fd.floor_id = f.id "
            "WHERE f.project_id=?", (project_id,)).fetchone()
        total = s["devices"] + floor_devices + actors
        return (f"{total} Geräte" if total else "noch keine Geräte — entfällt"), False, total > 0
    if anchor == "klaerungsliste":
        (n,) = db.execute("SELECT COUNT(*) FROM klaerungen WHERE project_id=?", (project_id,)).fetchone()
        (open_,) = db.execute(
            "SELECT COUNT(*) FROM klaerungen WHERE project_id=? AND status='offen'", (project_id,)).fetchone()
        return (f"{n} Einträge · {open_} offen" if n else "keine Einträge"), open_ > 0, True
    if anchor == "gruppenadressen":
        tree = build_ga_tree(project_id, db)
        n = sum(1 for main in tree["main_groups"] for middle in main["middles"]
                for sub in middle["subs"] if not sub["name"].endswith("res"))
        return (f"{n} Gruppenadressen" if n else "noch keine — entfällt"), False, n > 0
    return "", False, True


@router.get("/api/projects/{project_id}/dokumentation-contents")
def dokumentation_contents(project_id: int):
    """DOKU_CHAPTERS with, per chapter, whether it's in the PDF and a short
    status - doubles as a readiness check before handing the PDF over."""
    with get_db() as db:
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        status_map = get_status_map(db, project_id)
        result = []
        for anchor, title, toggle, default in DOKU_CHAPTERS:
            if not _chapter_enabled(company, toggle, default):
                result.append({"title": title, "included": False, "detail": "aus (Setup → Dokumentation)", "warn": False})
                continue
            detail, warn, has_content = _chapter_detail(db, project_id, anchor, status_map)
            result.append({"title": title, "included": has_content, "detail": detail, "warn": warn})
        return result
